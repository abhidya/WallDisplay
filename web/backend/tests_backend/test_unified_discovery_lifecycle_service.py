import asyncio
from types import SimpleNamespace

from web.backend.services.unified_discovery_lifecycle_service import UnifiedDiscoveryLifecycleService


def test_unified_discovery_lifecycle_service_starts_and_stops_manager():
    calls = []

    async def start_discovery():
        calls.append("start")
        manager.is_running = True

    async def stop_discovery():
        calls.append("stop")
        manager.is_running = False

    manager = SimpleNamespace(
        is_running=False,
        start_discovery=start_discovery,
        stop_discovery=stop_discovery,
    )

    service = UnifiedDiscoveryLifecycleService(manager)
    service.start()
    assert service.is_running is True

    service.stop()
    assert "start" in calls
    assert "stop" in calls
    assert manager.is_running is False


def test_unified_discovery_lifecycle_service_pause_resume_and_status():
    calls = []

    async def start_discovery():
        calls.append("start")
        manager.is_running = True

    async def stop_discovery():
        calls.append("stop")
        manager.is_running = False

    manager = SimpleNamespace(
        is_running=False,
        backends={"dlna": SimpleNamespace(discovery_interval=10)},
        device_sessions={"device-1": [SimpleNamespace(is_active=True), SimpleNamespace(is_active=False)]},
        start_discovery=start_discovery,
        stop_discovery=stop_discovery,
        get_all_devices=lambda: [object(), object()],
    )

    service = UnifiedDiscoveryLifecycleService(manager)
    service.start()

    assert service.get_status() == {
        "running": True,
        "paused": False,
        "devices_discovered": 2,
        "devices_playing": 1,
        "interval": 10,
    }

    service.pause()
    assert service.get_status() == {
        "running": False,
        "paused": True,
        "devices_discovered": 2,
        "devices_playing": 1,
        "interval": 10,
    }

    service.resume()

    assert calls == ["start", "stop", "start"]
    assert service.get_status() == {
        "running": True,
        "paused": False,
        "devices_discovered": 2,
        "devices_playing": 1,
        "interval": 10,
    }

    service.stop()
