"""Controlador de dispositivos de entrada de áudio para Windows 10 e Windows 11.

Utiliza a Windows Core Audio API (MMDevice API, EndpointVolume API, AudioMeterInformation
e PolicyConfig) por meio de PyCAW e comtypes para listar e controlar microfones reais
sem simulações.
"""

from __future__ import annotations

import logging
import warnings
from contextlib import contextmanager
from typing import Iterator, List, Optional

# Suprime aviso de IntFlag do comtypes em versões recentes do Python (3.14+/3.15+)
warnings.filterwarnings(
    "ignore",
    message=r".*You are running 'comtypes' on Python.*",
    category=FutureWarning,
)

import comtypes
from comtypes import CLSCTX_ALL, COMError, CoCreateInstance
from pycaw.constants import CLSID_MMDeviceEnumerator
from pycaw.pycaw import (
    DEVICE_STATE,
     AudioUtilities,
    EDataFlow,
    ERole,
    IAudioEndpointVolume,
    IAudioMeterInformation,
    IMMDevice,
    IMMDeviceEnumerator,
)
from pycaw.utils import CLSID_CPolicyConfigClient, IPolicyConfig

from src.audio.exceptions import (
    AudioControllerError,
    DeviceNotFoundError,
    DeviceUnavailableError,
    PermissionDeniedError,
    UnsupportedOperationError,
)
from src.models.microphone import (
    DeviceHardwareState,
    MicrophoneDevice,
    OperationResult,
)

logger = logging.getLogger(__name__)

# Chaves de propriedades do Windows Property System (PKEYs)
PKEY_DEVICE_DESC = "{A45C254E-DF1C-4EFD-8020-67D146A850E0} 2"
PKEY_DEVICE_FRIENDLY_NAME = "{A45C254E-DF1C-4EFD-8020-67D146A850E0} 14"
PKEY_DEVICE_ENUMERATOR_NAME = "{A45C254E-DF1C-4EFD-8020-67D146A850E0} 24"
PKEY_INTERFACE_FRIENDLY_NAME = "{026E516E-B814-414B-83CD-856D6FEF4822} 2"
PKEY_INTERFACE_ALT_FRIENDLY_NAME = "{B3F8FA53-0004-438E-9003-51A46E139BFC} 6"

# Códigos HRESULT comuns do Windows Core Audio / COM
HRESULT_DEVICE_INVALIDATED = -2004287484  # 0x88890004 (AUDCLNT_E_DEVICE_INVALIDATED)
HRESULT_ACCESS_DENIED = -2147024891       # 0x80070005 (E_ACCESSDENIED)
HRESULT_NOT_FOUND = -2147023728           # 0x80070490 (ERROR_NOT_FOUND / E_PROP_ID_UNSUPPORTED)
HRESULT_NOT_IMPL = -2147467263            # 0x80004001 (E_NOTIMPL)


@contextmanager
def com_apartment() -> Iterator[None]:
    """Garante que o COM esteja inicializado na thread atual durante a operação."""
    initialized = False
    try:
        comtypes.CoInitialize()
        initialized = True
    except OSError:
        # RPC_E_CHANGED_MODE: COM já foi inicializado em modo MTA nesta thread
        initialized = False
    try:
        yield
    finally:
        if initialized:
            try:
                comtypes.CoUninitialize()
            except Exception:
                pass


class AudioController:
    """Gerencia a detecção, leitura e controle de microfones no Windows."""

    def __init__(self, include_inactive: bool = False) -> None:
        self.include_inactive = include_inactive

    @staticmethod
    def _create_enumerator() -> IMMDeviceEnumerator:
        """Instancia o enumerador de dispositivos multimídia do Windows."""
        try:
            return CoCreateInstance(
                CLSID_MMDeviceEnumerator,
                IMMDeviceEnumerator,
                CLSCTX_ALL,
            )
        except (COMError, OSError) as exc:
            raise AudioControllerError(
                "Não foi possível acessar o subsistema de áudio do Windows (MMDeviceEnumerator).",
                details=str(exc),
            ) from exc

    @staticmethod
    def _get_default_endpoint_id(
        enumerator: IMMDeviceEnumerator,
        role: ERole,
    ) -> Optional[str]:
        """Obtém o ID do microfone padrão para o papel especificado (Console ou Comunicação)."""
        try:
            endpoint = enumerator.GetDefaultAudioEndpoint(
                EDataFlow.eCapture.value,
                role.value,
            )
            if endpoint is not None:
                return endpoint.GetId()
        except (COMError, OSError):
            # Nenhum microfone padrão configurado/conectado no momento
            return None
        return None

    @staticmethod
    def _translate_com_error(exc: Exception, operation_desc: str) -> AudioControllerError:
        """Converte erros COM de baixo nível em exceções amigáveis e informativas."""
        hresult = getattr(exc, "hresult", None)
        details = str(exc)

        if hresult == HRESULT_DEVICE_INVALIDATED:
            return DeviceUnavailableError(
                f"O dispositivo foi desconectado ou alterado durante: {operation_desc}.",
                details=details,
            )
        if hresult == HRESULT_ACCESS_DENIED:
            return PermissionDeniedError(
                f"Permissão negada pelo Windows ao executar: {operation_desc}. "
                "Verifique as configurações de privacidade do microfone no Windows.",
                details=details,
            )
        if hresult == HRESULT_NOT_FOUND:
            return DeviceNotFoundError(
                f"Dispositivo ou propriedade não encontrada durante: {operation_desc}.",
                details=details,
            )
        if hresult == HRESULT_NOT_IMPL:
            return UnsupportedOperationError(
                f"O driver deste microfone não suporta a operação: {operation_desc}.",
                details=details,
            )
        return AudioControllerError(
            f"Falha ao executar '{operation_desc}' no dispositivo de áudio.",
            details=details,
        )

    def _build_microphone_model(
        self,
        imm_device: IMMDevice,
        default_console_id: Optional[str],
        default_comm_id: Optional[str],
    ) -> Optional[MicrophoneDevice]:
        """Constrói o objeto `MicrophoneDevice` a partir de um ponteiro `IMMDevice`."""
        try:
            py_device = AudioUtilities.CreateDevice(imm_device)
            if py_device is None:
                return None

            device_id = py_device.id
            hw_state = DeviceHardwareState.from_raw(py_device.state)
            props = py_device.properties or {}

            full_friendly = (
                props.get(PKEY_DEVICE_FRIENDLY_NAME)
                or py_device.FriendlyName
                or "Microfone"
            )
            device_desc = props.get(PKEY_DEVICE_DESC) or ""
            adapter_name = (
                props.get(PKEY_INTERFACE_FRIENDLY_NAME)
                or props.get(PKEY_INTERFACE_ALT_FRIENDLY_NAME)
                or ""
            )
            bus_type = props.get(PKEY_DEVICE_ENUMERATOR_NAME) or ""

            # Se o nome descritivo estiver vazio, extrai do FriendlyName completo
            if not device_desc:
                if "(" in full_friendly and full_friendly.endswith(")"):
                    idx = full_friendly.rfind("(")
                    device_desc = full_friendly[:idx].strip()
                    if not adapter_name:
                        adapter_name = full_friendly[idx + 1 : -1].strip()
                else:
                    device_desc = full_friendly

            mic = MicrophoneDevice(
                id=device_id,
                name=str(device_desc).strip(),
                adapter_name=str(adapter_name).strip(),
                full_friendly_name=str(full_friendly).strip(),
                bus_type=str(bus_type).strip(),
                hardware_state=hw_state,
                is_default_console=(device_id == default_console_id),
                is_default_communications=(device_id == default_comm_id),
            )

            # Apenas endpoints ATIVOS possuem IAudioEndpointVolume e IAudioMeterInformation acessíveis
            if hw_state == DeviceHardwareState.ACTIVE:
                self._populate_active_audio_state(imm_device, mic)
            else:
                mic.supports_volume = False
                mic.supports_mute = False
                mic.supports_meter = False
                mic.is_muted = True
                mic.volume_percent = 0
                mic.volume_scalar = 0.0

            return mic
        except Exception as exc:
            logger.warning("Erro ao inspecionar dispositivo de áudio: %s", exc)
            return None

    def _populate_active_audio_state(
        self,
        imm_device: IMMDevice,
        mic: MicrophoneDevice,
    ) -> None:
        """Lê volume, estado de mute, ganho dB e nível de pico de um dispositivo ativo."""
        try:
            iface = imm_device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            ep_volume = iface.QueryInterface(IAudioEndpointVolume)

            try:
                mute_val = ep_volume.GetMute()
                mic.is_muted = bool(mute_val)
                mic.supports_mute = True
            except (COMError, OSError) as exc:
                mic.supports_mute = False
                mic.error_message = f"Controle de mute não suportado pelo driver ({exc})."

            try:
                scalar = float(ep_volume.GetMasterVolumeLevelScalar())
                scalar = max(0.0, min(1.0, scalar))
                mic.volume_scalar = scalar
                mic.volume_percent = int(round(scalar * 100))
                mic.supports_volume = True
            except (COMError, OSError) as exc:
                mic.supports_volume = False
                mic.error_message = f"Controle de volume não suportado pelo driver ({exc})."

            try:
                mic.volume_db = round(float(ep_volume.GetMasterVolumeLevel()), 1)
                vol_range = ep_volume.GetVolumeRange()
                if vol_range and len(vol_range) >= 2:
                    mic.min_db = round(float(vol_range[0]), 1)
                    mic.max_db = round(float(vol_range[1]), 1)
            except (COMError, OSError):
                pass

            try:
                mic.channels = int(ep_volume.GetChannelCount())
            except (COMError, OSError):
                mic.channels = 1

        except (COMError, OSError) as exc:
            mic.supports_volume = False
            mic.supports_mute = False
            mic.error_message = f"Não foi possível acessar controles de áudio: {exc}"

        # Nível de entrada (Peak Meter)
        try:
            meter_iface = imm_device.Activate(
                IAudioMeterInformation._iid_,
                CLSCTX_ALL,
                None,
            )
            meter = meter_iface.QueryInterface(IAudioMeterInformation)
            peak = float(meter.GetPeakValue())
            mic.peak_level = max(0.0, min(1.0, peak)) if not mic.is_muted else 0.0
            mic.supports_meter = True
        except (COMError, OSError):
            mic.peak_level = 0.0
            mic.supports_meter = False

    def list_microphones(
        self,
        include_inactive: Optional[bool] = None,
    ) -> List[MicrophoneDevice]:
        """Lista todos os dispositivos de entrada de áudio disponíveis no sistema.

        Ordena automaticamente colocando o microfone padrão do sistema no topo,
        seguido pelos demais dispositivos ativos em ordem alfabética e, por fim,
        os dispositivos desabilitados/desconectados (se `include_inactive=True`).
        """
        show_inactive = (
            self.include_inactive if include_inactive is None else include_inactive
        )

        with com_apartment():
            enumerator = self._create_enumerator()
            default_console_id = self._get_default_endpoint_id(
                enumerator, ERole.eConsole
            )
            default_comm_id = self._get_default_endpoint_id(
                enumerator, ERole.eCommunications
            )

            state_mask = DEVICE_STATE.ACTIVE.value
            if show_inactive:
                state_mask |= (
                    DEVICE_STATE.DISABLED.value | DEVICE_STATE.UNPLUGGED.value
                )

            try:
                collection = enumerator.EnumAudioEndpoints(
                    EDataFlow.eCapture.value,
                    state_mask,
                )
                count = collection.GetCount()
            except (COMError, OSError) as exc:
                raise self._translate_com_error(
                    exc, "listagem de dispositivos de captura"
                ) from exc

            devices: List[MicrophoneDevice] = []
            for idx in range(count):
                try:
                    raw_dev = collection.Item(idx)
                    mic = self._build_microphone_model(
                        raw_dev,
                        default_console_id,
                        default_comm_id,
                    )
                    if mic is not None:
                        devices.append(mic)
                except Exception as exc:
                    logger.debug("Falha ao ler item %d da coleção: %s", idx, exc)

            # Ordenação: 1º Padrão Console, 2º Padrão Comunicação, 3º Ativos, 4º Nome
            devices.sort(
                key=lambda d: (
                    0 if d.is_default_console else (1 if d.is_default_communications else 2),
                    0 if d.is_available else 1,
                    d.display_title.lower(),
                    d.adapter_name.lower(),
                    d.id,
                )
            )
            return devices

    def get_microphone(self, device_id: str) -> MicrophoneDevice:
        """Busca e retorna o estado atualizado de um microfone específico pelo seu ID."""
        with com_apartment():
            enumerator = self._create_enumerator()
            default_console_id = self._get_default_endpoint_id(
                enumerator, ERole.eConsole
            )
            default_comm_id = self._get_default_endpoint_id(
                enumerator, ERole.eCommunications
            )
            try:
                raw_dev = enumerator.GetDevice(device_id)
            except (COMError, OSError) as exc:
                raise DeviceNotFoundError(
                    "O microfone selecionado não foi encontrado no sistema.",
                    details=str(exc),
                ) from exc

            mic = self._build_microphone_model(
                raw_dev,
                default_console_id,
                default_comm_id,
            )
            if mic is None:
                raise DeviceNotFoundError(
                    "Não foi possível carregar as informações do microfone selecionado."
                )
            return mic

    def get_peak_levels(self, device_ids: Optional[List[str]] = None) -> dict[str, float]:
        """Obtém de forma leve os níveis de pico (VU meter) dos microfones ativos."""
        levels: dict[str, float] = {}
        with com_apartment():
            try:
                enumerator = self._create_enumerator()
                collection = enumerator.EnumAudioEndpoints(
                    EDataFlow.eCapture.value,
                    DEVICE_STATE.ACTIVE.value,
                )
                count = collection.GetCount()
                for idx in range(count):
                    try:
                        raw_dev = collection.Item(idx)
                        dev_id = raw_dev.GetId()
                        if device_ids is not None and dev_id not in device_ids:
                            continue

                        ep_vol = raw_dev.Activate(
                            IAudioEndpointVolume._iid_, CLSCTX_ALL, None
                        ).QueryInterface(IAudioEndpointVolume)
                        if bool(ep_vol.GetMute()):
                            levels[dev_id] = 0.0
                            continue

                        meter = raw_dev.Activate(
                            IAudioMeterInformation._iid_, CLSCTX_ALL, None
                        ).QueryInterface(IAudioMeterInformation)
                        levels[dev_id] = max(0.0, min(1.0, float(meter.GetPeakValue())))
                    except Exception:
                        continue
            except Exception:
                pass
        return levels

    def set_device_enabled(self, device_id: str, enabled: bool) -> OperationResult:
        """Ativa (`enabled=True`, desmuta) ou desativa (`enabled=False`, silencia/muta) um microfone.

        Verifica o estado real após aplicar a alteração para garantir que o driver
        efetivamente acatou o comando.
        """
        target_mute = not enabled
        action_label = "ativar" if enabled else "desativar"

        with com_apartment():
            try:
                enumerator = self._create_enumerator()
                raw_dev = enumerator.GetDevice(device_id)
            except (COMError, OSError) as exc:
                err = self._translate_com_error(exc, f"{action_label} microfone")
                return OperationResult(
                    success=False,
                    device_id=device_id,
                    message=err.message,
                    error_details=err.details,
                )

            py_dev = AudioUtilities.CreateDevice(raw_dev)
            hw_state = DeviceHardwareState.from_raw(py_dev.state if py_dev else 0)
            if hw_state != DeviceHardwareState.ACTIVE:
                return OperationResult(
                    success=False,
                    device_id=device_id,
                    message=(
                        f"Não é possível {action_label} este microfone porque ele está "
                        f"'{hw_state.label_pt}'."
                    ),
                    unsupported_operation=(hw_state == DeviceHardwareState.UNPLUGGED),
                )

            try:
                iface = raw_dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                ep_volume = iface.QueryInterface(IAudioEndpointVolume)
                ep_volume.SetMute(1 if target_mute else 0, None)

                # Lê o estado real diretamente do hardware/driver para validar a operação
                actual_mute = bool(ep_volume.GetMute())
            except (COMError, OSError) as exc:
                err = self._translate_com_error(exc, f"{action_label} microfone")
                return OperationResult(
                    success=False,
                    device_id=device_id,
                    message=err.message,
                    error_details=err.details,
                    unsupported_operation=isinstance(err, UnsupportedOperationError),
                )

            updated_mic = self.get_microphone(device_id)

            if actual_mute != target_mute:
                return OperationResult(
                    success=False,
                    device_id=device_id,
                    device=updated_mic,
                    message=(
                        f"O driver de '{updated_mic.display_title}' não permitiu "
                        f"{action_label} o microfone (o estado permaneceu inalterado)."
                    ),
                    unsupported_operation=True,
                )

            state_word = "ativado" if enabled else "desativado (silenciado)"
            return OperationResult(
                success=True,
                device_id=device_id,
                device=updated_mic,
                message=f"Microfone '{updated_mic.display_title}' {state_word} com sucesso.",
            )

    def toggle_device_enabled(self, device_id: str) -> OperationResult:
        """Alterna o estado de ativação (ativo <-> desativado) de um microfone."""
        try:
            mic = self.get_microphone(device_id)
        except AudioControllerError as exc:
            return OperationResult(
                success=False,
                device_id=device_id,
                message=exc.message,
                error_details=exc.details,
            )

        if not mic.is_available:
            return OperationResult(
                success=False,
                device_id=device_id,
                device=mic,
                message=(
                    f"O dispositivo '{mic.display_title}' não está ativo no sistema "
                    f"({mic.hardware_state.label_pt})."
                ),
            )

        return self.set_device_enabled(device_id, enabled=mic.is_muted)

    def set_device_volume(self, device_id: str, volume_percent: int) -> OperationResult:
        """Ajusta o volume de captura de um microfone (0% a 100%) em tempo real."""
        clamped_percent = max(0, min(100, int(volume_percent)))
        target_scalar = clamped_percent / 100.0

        with com_apartment():
            try:
                enumerator = self._create_enumerator()
                raw_dev = enumerator.GetDevice(device_id)
            except (COMError, OSError) as exc:
                err = self._translate_com_error(exc, "ajustar volume do microfone")
                return OperationResult(
                    success=False,
                    device_id=device_id,
                    message=err.message,
                    error_details=err.details,
                )

            py_dev = AudioUtilities.CreateDevice(raw_dev)
            hw_state = DeviceHardwareState.from_raw(py_dev.state if py_dev else 0)
            if hw_state != DeviceHardwareState.ACTIVE:
                return OperationResult(
                    success=False,
                    device_id=device_id,
                    message=(
                        f"Não é possível ajustar o volume porque o dispositivo está "
                        f"'{hw_state.label_pt}'."
                    ),
                    unsupported_operation=True,
                )

            try:
                iface = raw_dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                ep_volume = iface.QueryInterface(IAudioEndpointVolume)
                ep_volume.SetMasterVolumeLevelScalar(target_scalar, None)

                # Sincroniza lendo o valor real aplicado pelo driver
                actual_scalar = float(ep_volume.GetMasterVolumeLevelScalar())
                actual_percent = int(round(max(0.0, min(1.0, actual_scalar)) * 100))
            except (COMError, OSError) as exc:
                err = self._translate_com_error(exc, "ajustar volume do microfone")
                return OperationResult(
                    success=False,
                    device_id=device_id,
                    message=err.message,
                    error_details=err.details,
                    unsupported_operation=isinstance(err, UnsupportedOperationError),
                )

            updated_mic = self.get_microphone(device_id)

            # Alguns drivers têm granularidade de passos (ex.: passos de 2%), então toleramos até 3%
            if abs(actual_percent - clamped_percent) > 5:
                return OperationResult(
                    success=False,
                    device_id=device_id,
                    device=updated_mic,
                    message=(
                        f"O dispositivo '{updated_mic.display_title}' possui volume fixo ou "
                        f"limitado pelo driver (valor real: {actual_percent}%)."
                    ),
                    unsupported_operation=True,
                )

            return OperationResult(
                success=True,
                device_id=device_id,
                device=updated_mic,
                message=f"Volume de '{updated_mic.display_title}' ajustado para {actual_percent}%.",
            )

    def set_default_device(
        self,
        device_id: str,
        include_communications: bool = True,
    ) -> OperationResult:
        """Define o microfone especificado como dispositivo de entrada padrão do Windows."""
        with com_apartment():
            try:
                mic = self.get_microphone(device_id)
            except AudioControllerError as exc:
                return OperationResult(
                    success=False,
                    device_id=device_id,
                    message=exc.message,
                    error_details=exc.details,
                )

            if not mic.is_available:
                return OperationResult(
                    success=False,
                    device_id=device_id,
                    device=mic,
                    message=(
                        f"Apenas dispositivos conectados podem ser definidos como padrão "
                        f"(estado atual: {mic.hardware_state.label_pt})."
                    ),
                    unsupported_operation=True,
                )

            roles = [ERole.eConsole, ERole.eMultimedia]
            if include_communications:
                roles.append(ERole.eCommunications)

            try:
                AudioUtilities.SetDefaultDevice(device_id, roles=roles)
            except Exception as exc:
                return OperationResult(
                    success=False,
                    device_id=device_id,
                    device=mic,
                    message=(
                        "Esta versão do Windows não permitiu alterar o dispositivo padrão "
                        "via PolicyConfig."
                    ),
                    error_details=str(exc),
                    unsupported_operation=True,
                )

            updated_mic = self.get_microphone(device_id)
            if not updated_mic.is_default_console:
                return OperationResult(
                    success=False,
                    device_id=device_id,
                    device=updated_mic,
                    message=(
                        "O sistema não confirmou a alteração de microfone padrão "
                        f"para '{updated_mic.display_title}'."
                    ),
                    unsupported_operation=True,
                )

            return OperationResult(
                success=True,
                device_id=device_id,
                device=updated_mic,
                message=f"'{updated_mic.display_title}' definido como microfone padrão do sistema.",
            )

    def set_endpoint_hardware_visibility(
        self,
        device_id: str,
        visible: bool,
    ) -> OperationResult:
        """Habilita ou desabilita o endpoint de áudio no nível do sistema (Painel de Som do Windows).

        Utiliza a interface COM `IPolicyConfig::SetEndpointVisibility`. Caso não seja
        suportada pelo dispositivo/sistema, informa claramente ao usuário.
        """
        action_label = "habilitar" if visible else "desabilitar"
        with com_apartment():
            try:
                policy_config = CoCreateInstance(
                    CLSID_CPolicyConfigClient,
                    IPolicyConfig,
                    CLSCTX_ALL,
                )
                hr = policy_config.SetEndpointVisibility(device_id, 1 if visible else 0)
                if hr != 0:
                    return OperationResult(
                        success=False,
                        device_id=device_id,
                        message=(
                            f"O Windows retornou código {hr:#x} ao tentar {action_label} "
                            "o dispositivo no sistema."
                        ),
                        unsupported_operation=True,
                    )
                updated_mic = self.get_microphone(device_id)
                expected_state = (
                    DeviceHardwareState.ACTIVE
                    if visible
                    else DeviceHardwareState.DISABLED
                )
                if updated_mic.hardware_state != expected_state:
                    return OperationResult(
                        success=False,
                        device_id=device_id,
                        device=updated_mic,
                        message=(
                            f"A operação de {action_label} o dispositivo no nível do sistema "
                            "não é suportada diretamente sem privilégios elevados."
                        ),
                        unsupported_operation=True,
                    )
                state_desc = "habilitado no Windows" if visible else "desabilitado no Windows"
                return OperationResult(
                    success=True,
                    device_id=device_id,
                    device=updated_mic,
                    message=f"Dispositivo '{updated_mic.display_title}' {state_desc}.",
                )
            except Exception as exc:
                return OperationResult(
                    success=False,
                    device_id=device_id,
                    message=(
                        f"Não foi possível {action_label} este endpoint no nível do sistema."
                    ),
                    error_details=str(exc),
                    unsupported_operation=True,
                )

