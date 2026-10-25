"""Exceções específicas para operações de gerenciamento de microfones."""

from __future__ import annotations


class AudioControllerError(Exception):
    """Exceção base para falhas no controlador de áudio."""

    def __init__(self, message: str, details: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class DeviceNotFoundError(AudioControllerError):
    """Dispositivo não encontrado na enumeração do sistema."""


class DeviceUnavailableError(AudioControllerError):
    """Dispositivo desconectado, desabilitado no sistema ou indisponível."""


class PermissionDeniedError(AudioControllerError):
    """Permissão negada pelo sistema operacional ou política de privacidade."""


class UnsupportedOperationError(AudioControllerError):
    """Operação não suportada pelo driver ou pela interface do dispositivo."""

