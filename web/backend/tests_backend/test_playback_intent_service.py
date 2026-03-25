from datetime import datetime, timedelta, timezone

from web.backend.services.playback_intent_service import PlaybackIntentService


def test_playback_intent_service_tracks_assignment_priority_and_retries():
    service = PlaybackIntentService()

    service.set_assigned_video("Device A", "/tmp/video.mp4")
    service.set_priority("Device A", 70)
    service.reset_retries("Device A")
    retry_count = service.increment_retries("Device A")

    assert service.get_assigned_video("Device A") == "/tmp/video.mp4"
    assert service.get_priority("Device A") == 70
    assert retry_count == 1
    assert service.get_retry_count("Device A") == 1


def test_playback_intent_service_returns_due_scheduled_video_and_clears_it():
    service = PlaybackIntentService()
    now = datetime.now(timezone.utc)

    service.schedule_assignment(
        device_name="Device B",
        video_path="/tmp/future.mp4",
        priority=50,
        schedule_time=now - timedelta(seconds=1),
    )

    due_video = service.get_due_scheduled_video("Device B", now)

    assert due_video == "/tmp/future.mp4"
    assert "Device B" not in service.scheduled_assignments


def test_device_manager_assignment_properties_remain_compatible(device_manager):
    device_manager.playback_intent_service.set_assigned_video("Device C", "/tmp/test.mp4")
    device_manager.playback_intent_service.set_priority("Device C", 30)

    assert device_manager.assigned_videos["Device C"] == "/tmp/test.mp4"
    assert device_manager.video_assignment_priority["Device C"] == 30
