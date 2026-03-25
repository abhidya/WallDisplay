from types import SimpleNamespace

from web.backend.core.device_manager import DeviceManager
from web.backend.services.playback_monitoring_service import PlaybackMonitoringService


def test_playback_monitoring_service_tracks_result_history():
    monitoring = PlaybackMonitoringService(SimpleNamespace(playback_health_check_interval=1))

    monitoring.track_playback_result("Device A", "/tmp/a.mp4", True)
    monitoring.track_playback_result("Device A", "/tmp/a.mp4", False)

    stats = monitoring.get_device_playback_stats("Device A")

    assert stats["attempts"] == 2
    assert stats["successes"] == 1
    assert stats["success_rate"] == 50
    assert stats["videos"]["/tmp/a.mp4"] == {"attempts": 2, "successes": 1}


def test_playback_monitoring_service_stops_and_clears_device_state():
    monitoring = PlaybackMonitoringService(SimpleNamespace(playback_health_check_interval=1))
    monitoring.playback_health_threads["Device B"] = {"active": True}
    monitoring.track_playback_result("Device B", "/tmp/b.mp4", True)

    monitoring.clear_device_state("Device B")

    assert "Device B" not in monitoring.playback_health_threads
    assert "Device B" not in monitoring.video_playback_history


def test_device_manager_monitoring_properties_delegate_to_service():
    monitoring = PlaybackMonitoringService(SimpleNamespace(playback_health_check_interval=1))
    manager = DeviceManager(playback_monitoring_service=monitoring)

    assert manager.monitoring_lock is monitoring.monitoring_lock
    assert manager.playback_health_threads is monitoring.playback_health_threads
    assert manager.video_playback_history is monitoring.video_playback_history
    assert manager.playback_stats is monitoring.playback_stats
