"""Modelos de domínio para os dispositivos de entrada de áudio (microfones)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DeviceHardwareState( str, Enum ):
    """Estado físico/sistema do endpoint de áudio no Windows Core Audio."""

    ACTIVE = "Active"          # Dispositivo conectado e habilitado no sistema
    DISABLED = "Disabled"      # Dispositivo desabilitado nas configurações de som do Windows
    UNPLUGGED = "Unplugged"    # Dispositivo presente mas cabo/conector desconectado
    NOT_PRESENT = "NotPresent" # Dispositivo ausente ou driver inativo
    UNKNOWN = "Unknown"        # Estado não identificado

    @classmethod
    def from_raw(cls, raw_state: str | int) -> "DeviceHardwareState":
        """Converte o estado retornado pelo PyCAW/Windows para o enum interno."""
        if isinstance(raw_state, int):
            mapping = {
                1: cls.ACTIVE,
                2: cls.DISABLED,
                4: cls.NOT_PRESENT,
                8: cls.UNPLUGGED,
            }
            return mapping.get(raw_state, cls.UNKNOWN)

        text = str(raw_state)
        if "." in text:
            text = text.split(".")[-1]
        for item in cls:
            if item.value.lower() == text.lower():
                return item
        return cls.UNKNOWN

    @property
    def label_pt(self) -> str:
        """Retorna a descrição legível em português para o estado do hardware."""
        labels = {
            DeviceHardwareState.ACTIVE: "Conectado",
            DeviceHardwareState.DISABLED: "Desabilitado no Sistema",
            DeviceHardwareState.UNPLUGGED: "Desconectado (Cabo)",
            DeviceHardwareState.NOT_PRESENT: "Não Presente",
            DeviceHardwareState.UNKNOWN: "Estado Desconhecido",
        }
        return labels.get(self, "Desconhecido")


@dataclass(slots=True)
class MicrophoneDevice:
    """Representa o estado completo de um dispositivo de entrada de áudio."""

    id: str
    name: str
    adapter_name: str = ""
    full_friendly_name: str = ""
    bus_type: str = ""
    hardware_state: DeviceHardwareState = DeviceHardwareState.ACTIVE

    # Estado de captura e volume (disponíveis quando hardware_state == ACTIVE)
    is_muted: bool = False
    volume_percent: int = 100
    volume_scalar: float = 1.0
    volume_db: Optional[float] = None
    min_db: Optional[float] = None
    max_db: Optional[float] = None
    peak_level: float = 0.0  # Nível de pico atual (0.0 a 1.0)
    channels: int = 1

    # Indicadores de dispositivo padrão no Windows
    is_default_console: bool = False         # Padrão do Sistema
    is_default_communications: bool = False  # Padrão de Comunicação

    # Capacidades suportadas pelo endpoint/driver
    supports_volume: bool = True
    supports_mute: bool = True
    supports_meter: bool = True
    error_message: Optional[str] = field(default=None)

    @property
    def is_available(self) -> bool:
        """Indica se o dispositivo está pronto para controle de mute e volume."""
        return self.hardware_state == DeviceHardwareState.ACTIVE

    @property
    def is_enabled(self) -> bool:
        """
        Indica se o microfone está ATIVO (capturando áudio).
        Um microfone está ativo quando está disponível no sistema e NÃO está em mute.
        """
        return self.is_available and not self.is_muted

    @property
    def short_id(self) -> str:
        """Retorna um identificador curto extraído do GUID do endpoint para desambiguação."""
        if "}.{" in self.id:
            guid_part = self.id.split("}.{")[-1].strip("{}")
            return guid_part[:6].upper()
        return self.id[-6:].upper()

    @property
    def display_title(self) -> str:
        """Título principal amigável do microfone."""
        return self.name or self.full_friendly_name or "Microfone Desconhecido"

    @property
    def display_subtitle(self) -> str:
        """Subtítulo com o nome do adaptador/driver e código curto do endpoint."""
        parts = []
        if self.adapter_name and self.adapter_name != self.name:
            parts.append(self.adapter_name)
        if self.bus_type:
            bus_map = {
                "USB": "USB",
                "HDAUDIO": "Áudio HD Interno",
                "BTHHFENUM": "Bluetooth Hands-Free",
                "BTHENUM": "Bluetooth",
                "MMDEVAPI": " Endpoint de Áudio",
                "ROOT": " Dispositivo Virtual",
                "SWD": "Software Audio",
            }
            readable_bus = bus_map.get(self.bus_type.upper(), self.bus_type)
            parts.append(readable_bus.strip())
        parts.append(f"ID #{self.short_id}")
        return " • ".join(parts)

    @property
    def status_badge_text(self) -> str:
        """Texto descritivo do badge principal de estado."""
        if not self.is_available:
            return self.hardware_state.label_pt.upper()
        return "ATIVO" if self.is_enabled else "DESATIVADO"


@dataclass(slots=True)
class OperationResult:
    """Resultado padronizado de uma operação sobre um dispositivo de áudio."""

    success: bool
    device_id: str
    message: str
    device: Optional[MicrophoneDevice] = None
    error_details: Optional[str] = None
    unsupported_operation: bool = False

