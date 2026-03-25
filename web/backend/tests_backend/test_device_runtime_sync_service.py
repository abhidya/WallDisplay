from types import SimpleNamespace

from web.backend.services.device_runtime_sync_service import DeviceRuntimeSyncService


def test_runtime_sync_service_builds_device_info_from_model():
    runtime = SimpleNamespace()
    service = DeviceRuntimeSyncService(runtime)
    device = SimpleNamespace(
        name="Device A",
        type="dlna",
        hostname="10.0.0.10",
        action_url="http://10.0.0.10/action",
        friendly_name="Device A",
        manufacturer="Test",
        location="http://10.0.0.10/device.xml",
        config={"priority": 60},
    )

    result = service.build_device_info(device)

    assert result == {
        "device_name": "Device A",
        "type": "dlna",
        "hostname": "10.0.0.10",
        "action_url": "http://10.0.0.10/action",
        "friendly_name": "Device A",
        "manufacturer": "Test",
        "location": "http://10.0.0.10/device.xml",
        "priority": 60,
    }


def test_runtime_sync_service_register_and_update_delegates_to_manager():
    calls = []
    runtime = SimpleNamespace(
        register_device=lambda device_info: calls.append(("register", device_info)) or "device",
        update_device_status=lambda **kwargs: calls.append(("status", kwargs)),
        get_device=lambda device_name: None,
    )
    service = DeviceRuntimeSyncService(runtime)

    result = service.register_and_update(
        {
            "device_name": "Device B",
            "type": "dlna",
            "hostname": "10.0.0.20",
        },
        status="connected",
        is_playing=True,
        current_video="/tmp/b.mp4",
    )

    assert result == "device"
    assert calls == [
        (
            "register",
            {
                "device_name": "Device B",
                "type": "dlna",
                "hostname": "10.0.0.20",
                "action_url": "",
                "friendly_name": "Device B",
                "manufacturer": "",
                "location": "",
            },
        ),
        (
            "status",
            {
                "device_name": "Device B",
                "status": "connected",
                "is_playing": True,
                "current_video": "/tmp/b.mp4",
            },
        ),
    ]


def test_runtime_sync_service_gets_or_registers_missing_core_device():
    registered = []
    runtime = SimpleNamespace(
        get_device=lambda device_name: None,
        register_device=lambda device_info: registered.append(device_info) or "core-device",
    )
    service = DeviceRuntimeSyncService(runtime)
    device = SimpleNamespace(
        name="Device C",
        type="dlna",
        hostname="10.0.0.30",
        action_url="http://10.0.0.30/action",
        friendly_name="Device C",
        manufacturer="Test",
        location="http://10.0.0.30/device.xml",
        config=None,
    )

    result = service.get_or_register_core_device(device)

    assert result == "core-device"
    assert registered == [
        {
            "device_name": "Device C",
            "type": "dlna",
            "hostname": "10.0.0.30",
            "action_url": "http://10.0.0.30/action",
            "friendly_name": "Device C",
            "manufacturer": "Test",
            "location": "http://10.0.0.30/device.xml",
        }
    ]


def test_runtime_sync_service_discovers_devices_through_runtime():
    runtime = SimpleNamespace(discover_dlna_devices=lambda timeout: [{"device_name": "Device D", "timeout": timeout}])
    service = DeviceRuntimeSyncService(runtime)

    result = service.discover_dlna_devices(3.5)

    assert result == [{"device_name": "Device D", "timeout": 3.5}]
