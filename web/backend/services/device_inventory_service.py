from typing import Any, Dict, Iterable, List, Optional, Tuple


class DeviceInventoryService:
    """
    Own the live in-memory device inventory while preserving the legacy dict access pattern.
    """

    def __init__(self):
        self._devices: Dict[str, Any] = {}

    @property
    def devices(self) -> Dict[str, Any]:
        return self._devices

    def get(self, device_name: str) -> Optional[Any]:
        return self._devices.get(device_name)

    def set(self, device_name: str, device: Any) -> Any:
        self._devices[device_name] = device
        return device

    def remove(self, device_name: str) -> Optional[Any]:
        return self._devices.pop(device_name, None)

    def contains(self, device_name: str) -> bool:
        return device_name in self._devices

    def keys(self) -> Iterable[str]:
        return self._devices.keys()

    def values(self) -> Iterable[Any]:
        return self._devices.values()

    def items(self) -> Iterable[Tuple[str, Any]]:
        return self._devices.items()

    def list_devices(self) -> List[Any]:
        return list(self._devices.values())

    def clear(self) -> None:
        self._devices.clear()
