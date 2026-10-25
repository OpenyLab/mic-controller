"""Módulo de gerenciamento de áudio via Windows Core Audio API (PyCAW / COM)."""

from .controller import AudioController
from .exceptions import (
    AudioControllerError,
    DeviceNotFoundError,
    DeviceUnavailableError,
    PermissionDeniedError,
    UnsupportedOperationError,
)
from .monitor import AudioDeviceMonitor

__all__ = [
    "AudioController",
    "AudioControllerError",
    "AudioDeviceMonitor",
    "DeviceNotFoundError",
    "DeviceUnavailableError",
    "PermissionDeniedError",
    "UnsupportedOperationError",
]

