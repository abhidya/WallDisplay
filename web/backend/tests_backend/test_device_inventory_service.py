from types import SimpleNamespace

from web.backend.core.device_manager import DeviceManager
from web.backend.services.device_inventory_service import DeviceInventoryService


def test_device_inventory_service_tracks_devices_by_name():
    inventory = DeviceInventoryService()
    device = SimpleNamespace(name="Device A")

    inventory.set("Device A", device)

    assert inventory.contains("Device A") is True
    assert inventory.get("Device A") is device
    assert inventory.list_devices() == [device]
    assert list(inventory.keys()) == ["Device A"]
    assert list(inventory.values()) == [device]
    assert list(inventory.items()) == [("Device A", device)]

    removed = inventory.remove("Device A")

    assert removed is device
    assert inventory.contains("Device A") is False
    assert inventory.list_devices() == []


def test_device_manager_devices_property_uses_inventory_service():
    inventory = DeviceInventoryService()
    inventory.set("Device B", SimpleNamespace(name="Device B"))

    manager = DeviceManager(device_inventory=inventory)

    assert manager.devices is inventory.devices
    assert manager.get_device("Device B") is inventory.get("Device B")
    assert manager.get_devices() == inventory.list_devices()


def test_register_device_rebinds_core_device_to_owning_manager(monkeypatch):
    monkeypatch.setattr(
        "web.backend.services.device_lifecycle_service.DLNADevice",
        lambda info: SimpleNamespace(name=info["device_name"], device_info=info, device_manager="global"),
    )

    manager = DeviceManager()
    device = manager.register_device(
        {
            "device_name": "Device C",
            "type": "dlna",
            "hostname": "127.0.0.1",
            "action_url": "http://127.0.0.1/action",
        }
    )

    assert device is not None
    assert device.device_manager is manager
