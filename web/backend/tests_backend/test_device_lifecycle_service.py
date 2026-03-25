import threading
from types import SimpleNamespace

from web.backend.services.device_inventory_service import DeviceInventoryService
from web.backend.services.device_lifecycle_service import DeviceLifecycleService
from web.backend.services.playback_intent_service import PlaybackIntentService
from web.backend.services.playback_monitoring_service import PlaybackMonitoringService
from web.backend.services.runtime_registry_service import RuntimeRegistryService


def test_device_lifecycle_service_registers_and_rebinds_device(monkeypatch):
    owner = SimpleNamespace(device_lock_timeout=5.0)
    inventory = DeviceInventoryService()
    runtime_registry = RuntimeRegistryService()
    playback_intent = PlaybackIntentService()
    monitoring = PlaybackMonitoringService(SimpleNamespace(playback_health_check_interval=1))

    monkeypatch.setattr(
        "web.backend.services.device_lifecycle_service.DLNADevice",
        lambda info: SimpleNamespace(
            name=info["device_name"],
            device_info=info,
            device_manager="global",
            runtime="global-runtime",
        ),
    )

    service = DeviceLifecycleService(
        owner=owner,
        device_inventory=inventory,
        runtime_registry=runtime_registry,
        playback_intent_service=playback_intent,
        playback_monitoring_service=monitoring,
        device_state_lock=threading.RLock(),
        assignment_lock=threading.Lock(),
        acquire_device_lock=lambda: True,
        release_device_lock=lambda: None,
    )

    device = service.register_device(
        {
            "device_name": "Device A",
            "type": "dlna",
            "hostname": "127.0.0.1",
            "action_url": "http://127.0.0.1/action",
        }
    )

    assert device is not None
    assert device.device_manager is owner
    assert device.runtime is owner
    assert inventory.get("Device A") is device
    assert "Device A" in runtime_registry.device_status


def test_device_lifecycle_service_cleanup_and_unregister_clear_runtime_state():
    owner = SimpleNamespace(device_lock_timeout=5.0)
    inventory = DeviceInventoryService()
    runtime_registry = RuntimeRegistryService()
    playback_intent = PlaybackIntentService()
    monitoring = PlaybackMonitoringService(SimpleNamespace(playback_health_check_interval=1))

    service = DeviceLifecycleService(
        owner=owner,
        device_inventory=inventory,
        runtime_registry=runtime_registry,
        playback_intent_service=playback_intent,
        playback_monitoring_service=monitoring,
        device_state_lock=threading.RLock(),
        assignment_lock=threading.Lock(),
        acquire_device_lock=lambda: True,
        release_device_lock=lambda: None,
    )

    inventory.set("Device B", SimpleNamespace(name="Device B", update_playing=lambda is_playing: None))
    runtime_registry.ensure_device("Device B")
    playback_intent.set_assigned_video("Device B", "/tmp/b.mp4")
    playback_intent.set_priority("Device B", 50)
    playback_intent.device_assignment_queue["Device B"] = {"state": "queued"}
    monitoring.playback_health_threads["Device B"] = {"active": True}

    service.cleanup_device_state("Device B")
    result = service.unregister_device("Device B")

    assert result is True
    assert inventory.get("Device B") is None
    assert "Device B" not in runtime_registry.device_status
    assert playback_intent.get_assigned_video("Device B") is None
    assert "Device B" not in playback_intent.video_assignment_priority
    assert "Device B" not in playback_intent.device_assignment_queue
