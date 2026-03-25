from web.backend.services.runtime_registry_service import RuntimeRegistryService
from web.backend.services.playback_intent_service import PlaybackIntentService
from web.backend.core.config_service import ConfigService
from web.backend.core.streaming_registry import StreamingSessionRegistry
from web.backend.core.device_manager import DeviceManager


def test_runtime_registry_updates_status_and_reconnect_counts():
    service = RuntimeRegistryService()

    service.update_status("Device A", "connected", is_playing=False, now=100.0)
    service.update_status("Device A", "disconnected", now=110.0)
    status = service.update_status("Device A", "connected", now=120.0)

    assert status["status"] == "connected"
    assert status["reconnect_count"] == 1
    assert status["offline_count"] == 1
    assert service.last_seen["Device A"] == 120.0


def test_runtime_registry_updates_playback_state_and_progress():
    service = RuntimeRegistryService()

    service.update_playing_state("Device B", True, "/tmp/video.mp4")
    status = service.update_playback_progress("Device B", "00:00:05", "00:01:00", 8)

    assert status["is_playing"] is True
    assert status["current_video"] == "/tmp/video.mp4"
    assert status["playback_position"] == "00:00:05"
    assert status["playback_progress"] == 8


def test_device_manager_runtime_registry_properties_remain_compatible(device_manager):
    device_manager.runtime_registry.update_status("Device C", "connected", now=50.0)

    assert device_manager.device_status["Device C"]["status"] == "connected"
    assert device_manager.last_seen["Device C"] == 50.0


def test_device_manager_accepts_injected_services():
    runtime_registry = RuntimeRegistryService()
    playback_intent_service = PlaybackIntentService()
    config_service = ConfigService.get_instance()
    streaming_registry = StreamingSessionRegistry.get_instance()

    manager = DeviceManager(
        config_service=config_service,
        streaming_registry=streaming_registry,
        runtime_registry=runtime_registry,
        playback_intent_service=playback_intent_service,
    )

    assert manager.runtime_registry is runtime_registry
    assert manager.playback_intent_service is playback_intent_service
    assert manager.config_service is config_service
    assert manager.streaming_registry is streaming_registry
