"""Monitor assíncrono de dispositivos de entrada de áudio e medidor de nível em tempo real.

Executa em uma QThread separada para evitar qualquer bloqueio na interface gráfica,
combinando notificações de eventos do Windows Core Audio (`IMMNotificationClient`)
com sincronização contínua de volume/mute e leitura de pico de áudio (VU Meter).
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Dict, List, Optional

import comtypes
from comtypes import CLSCTX_ALL, CoCreateInstance
from PySide6.QtCore import QMutex, QMutexLocker, QThread, Signal
from pycaw.callbacks import MMNotificationClient
from pycaw.constants import CLSID_MMDeviceEnumerator
from pycaw.pycaw import IMMDeviceEnumerator

from src.audio.controller import AudioController
from src.models.microphone import MicrophoneDevice

logger = logging.getLogger(__name__)


class _EndpointNotificationBridge(MMNotificationClient):
    """Callback COM do Windows (`IMMNotificationClient`) para eventos de hotplug e estado."""

    def __init__(self, on_topology_event: Callable[[], None]) -> None:
        super().__init__()
        self._on_topology_event = on_topology_event

    def on_default_device_changed(
        self, flow: str, flow_id: int, role: str, role_id: int, default_device_id: str
    ) -> None:
        if flow in ("eCapture", "eAll"):
            self._on_topology_event()

    def on_device_added(self, added_device_id: str) -> None:
        self._on_topology_event()

    def on_device_removed(self, removed_device_id: str) -> None:
        self._on_topology_event()

    def on_device_state_changed(
        self, device_id: str, new_state: str, new_state_id: int
    ) -> None:
        self._on_topology_event()


class AudioDeviceMonitor(QThread):
    """Thread de monitoramento contínuo para sincronização do estado dos microfones."""

    # Emitido quando a lista de dispositivos muda ou quando volume/mute é alterado externamente
    devices_updated = Signal(list)
    # Emitido em alta frequência (ex.: ~12 FPS) com {device_id: peak_float} para as barras de nível
    levels_updated = Signal(dict)
    # Emitido quando um dispositivo específico é conectado ou desconectado (mensagem discreta)
    topology_event_detected = Signal(str)
    # Emitido em caso de erro inesperado na comunicação com a API de áudio
    monitor_error = Signal(str)

    def __init__(
        self,
        include_inactive: bool = False,
        sync_interval_ms: int = 800,
        meter_interval_ms: int = 85,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._include_inactive = include_inactive
        self._sync_interval_s = max(0.25, sync_interval_ms / 1000.0)
        self._meter_interval_s = max(0.05, meter_interval_ms / 1000.0)

        self._mutex = QMutex()
        self._running = True
        self._meters_enabled = True
        self._force_refresh = True
        self._topology_dirty = False
        self._last_snapshot_signature: Optional[tuple] = None
        self._last_device_names: Dict[str, str] = {}
        self._interaction_locks: Dict[str, float] = {}

    def set_include_inactive(self, include_inactive: bool) -> None:
        """Altera o filtro de exibição de dispositivos inativos/desconectados e força atualização."""
        with QMutexLocker(self._mutex):
            if self._include_inactive != include_inactive:
                self._include_inactive = include_inactive
                self._force_refresh = True

    def set_meters_enabled(self, enabled: bool) -> None:
        """Pausa ou retoma a leitura de nível de pico (útil quando minimizado para a bandeja)."""
        with QMutexLocker(self._mutex):
            self._meters_enabled = enabled

    def request_refresh(self) -> None:
        """Solicita uma atualização imediata da lista de dispositivos na próxima iteração."""
        with QMutexLocker(self._mutex):
            self._force_refresh = True

    def notify_user_interaction(self, device_id: str, hold_seconds: float = 0.6) -> None:
        """Registra que o usuário está interagindo com o dispositivo (ex.: arrastando slider)."""
        with QMutexLocker(self._mutex):
            self._interaction_locks[device_id] = time.monotonic() + hold_seconds

    def stop(self) -> None:
        """Encerra a thread de monitoramento de forma limpa."""
        with QMutexLocker(self._mutex):
            self._running = False
        self.wait(2000)

    def _on_com_topology_event(self) -> None:
        """Acionado pelo Windows quando dispositivos são conectados, removidos ou mudam de estado."""
        with QMutexLocker(self._mutex):
            self._topology_dirty = True
            self._force_refresh = True

    @staticmethod
    def _compute_signature(devices: List[MicrophoneDevice]) -> tuple:
        """Gera uma assinatura imutável do estado relevante dos dispositivos para detectar mudanças."""
        return tuple(
            (
                d.id,
                d.hardware_state.value,
                d.is_muted,
                d.volume_percent,
                d.is_default_console,
                d.is_default_communications,
                d.display_title,
            )
            for d in devices
        )

    def _detect_hotplug_notifications(self, devices: List[MicrophoneDevice]) -> None:
        """Compara os dispositivos ativos atuais com o ciclo anterior para notificar conexões/remoções."""
        current_active = {
            d.id: d.display_title for d in devices if d.is_available
        }
        if self._last_device_names:
            added_ids = set(current_active.keys()) - set(self._last_device_names.keys())
            removed_ids = set(self._last_device_names.keys()) - set(current_active.keys())

            for dev_id in added_ids:
                name = current_active[dev_id]
                self.topology_event_detected.emit(f"Microfone conectado: {name}")
            for dev_id in removed_ids:
                name = self._last_device_names[dev_id]
                self.topology_event_detected.emit(f"Microfone desconectado: {name}")

        self._last_device_names = current_active

    def run(self) -> None:
        """Loop principal da thread de monitoramento com inicialização COM dedicada."""
        com_initialized = False
        try:
            comtypes.CoInitialize()
            com_initialized = True
        except OSError:
            pass

        enumerator = None
        callback_bridge = None

        try:
            controller = AudioController()

            # Registra o cliente de notificações do Windows Core Audio (IMMNotificationClient)
            try:
                enumerator = CoCreateInstance(
                    CLSID_MMDeviceEnumerator,
                    IMMDeviceEnumerator,
                    CLSCTX_ALL,
                )
                callback_bridge = _EndpointNotificationBridge(self._on_com_topology_event)
                enumerator.RegisterEndpointNotificationCallback(callback_bridge)
            except Exception as exc:
                logger.warning(
                    "Não foi possível registrar IMMNotificationClient (usando polling): %s",
                    exc,
                )

            last_sync_time = 0.0
            active_device_ids: List[str] = []

            while True:
                with QMutexLocker(self._mutex):
                    if not self._running:
                        break
                    include_inactive = self._include_inactive
                    force_refresh = self._force_refresh
                    topology_dirty = self._topology_dirty
                    meters_enabled = self._meters_enabled
                    now = time.monotonic()
                    locked_ids = {
                        dev_id
                        for dev_id, until in list(self._interaction_locks.items())
                        if until > now
                    }
                    # Limpa locks expirados
                    self._interaction_locks = {
                        k: v for k, v in self._interaction_locks.items() if v > now
                    }

                now = time.monotonic()
                should_sync = (
                    force_refresh
                    or topology_dirty
                    or (now - last_sync_time >= self._sync_interval_s)
                )

                if should_sync:
                    with QMutexLocker(self._mutex):
                        self._force_refresh = False
                        self._topology_dirty = False

                    try:
                        devices = controller.list_microphones(
                            include_inactive=include_inactive
                        )
                        active_device_ids = [
                            d.id for d in devices if d.is_available and d.supports_meter
                        ]

                        self._detect_hotplug_notifications(devices)
                        sig = self._compute_signature(devices)

                        # Evita sobrescrever controles enquanto o usuário arrasta um slider
                        if force_refresh or (
                            sig != self._last_snapshot_signature and not locked_ids
                        ):
                            self._last_snapshot_signature = sig
                            self.devices_updated.emit(devices)

                        last_sync_time = time.monotonic()
                    except Exception as exc:
                        logger.error("Erro na sincronização de microfones: %s", exc)
                        self.monitor_error.emit(str(exc))

                if meters_enabled and active_device_ids:
                    try:
                        levels = controller.get_peak_levels(active_device_ids)
                        if levels:
                            self.levels_updated.emit(levels)
                    except Exception:
                        pass

                time.sleep(self._meter_interval_s)

        finally:
            if enumerator is not None and callback_bridge is not None:
                try:
                    enumerator.UnregisterEndpointNotificationCallback(callback_bridge)
                except Exception:
                    pass
            if com_initialized:
                try:
                    comtypes.CoUninitialize()
                except Exception:
                    pass

