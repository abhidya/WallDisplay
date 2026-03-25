from types import SimpleNamespace
from contextlib import nullcontext

from web.backend.services.device_playback_service import DevicePlaybackService


class _FakeQuery:
    def __init__(self, device):
        self._device = device

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._device


class _FakeDB:
    def __init__(self, device):
        self._device = device
        self.commit_count = 0

    def query(self, _model):
        return _FakeQuery(self._device)

    def commit(self):
        self.commit_count += 1


def test_pause_video_updates_status_when_core_device_exists():
    device = SimpleNamespace(id=1, name="Device A")
    core_device = SimpleNamespace(pause=lambda: True)
    status_updates = []

    service = DevicePlaybackService(
        db=_FakeDB(device),
        runtime=SimpleNamespace(),
        runtime_sync_service=SimpleNamespace(get_core_device=lambda device_name: core_device),
        get_device_instance=lambda device_id: None,
        update_device_status=lambda device_name, status, is_playing=False: status_updates.append(
            (device_name, status, is_playing)
        ),
    )

    result = service.pause_video(1)

    assert result is True
    assert status_updates == [("Device A", "connected", False)]


def test_seek_video_registers_core_device_when_missing():
    device = SimpleNamespace(id=2, name="Device B")
    seek_calls = []
    core_device = SimpleNamespace(seek=lambda position: seek_calls.append(position) or True)

    service = DevicePlaybackService(
        db=_FakeDB(device),
        runtime=SimpleNamespace(),
        runtime_sync_service=SimpleNamespace(
            get_core_device=lambda device_name: None,
            get_or_register_core_device=lambda db_device: core_device,
        ),
        get_device_instance=lambda device_id: None,
        update_device_status=lambda *_args, **_kwargs: True,
    )

    result = service.seek_video(2, "00:01:23")

    assert result is True
    assert seek_calls == ["00:01:23"]


def test_stop_video_cleans_runtime_state_and_marks_manual_stop():
    device = SimpleNamespace(
        id=3,
        name="Device C",
        streaming_url="http://127.0.0.1:9000/video.mp4",
        streaming_port=9000,
        current_video="/tmp/c.mp4",
        user_control_mode=None,
        user_control_reason=None,
    )
    core_device = SimpleNamespace(stop=lambda: True)
    cleanup_calls = []
    status_updates = []

    service = DevicePlaybackService(
        db=_FakeDB(device),
        runtime=SimpleNamespace(
            streaming_service=None,
            streaming_registry=None,
            cleanup_device_state=lambda device_name: cleanup_calls.append(device_name),
        ),
        runtime_sync_service=SimpleNamespace(get_core_device=lambda device_name: core_device),
        get_device_instance=lambda device_id: None,
        update_device_status=lambda device_name, status, is_playing=False: status_updates.append(
            (device_name, status, is_playing)
        ),
    )

    result = service.stop_video(3)

    assert result is True
    assert device.streaming_url is None
    assert device.streaming_port is None
    assert device.current_video is None
    assert device.user_control_mode == "manual"
    assert device.user_control_reason == "user_stopped"
    assert cleanup_calls == ["Device C"]
    assert status_updates == [("Device C", "connected", False)]


def test_update_playback_progress_updates_db_runtime_and_core_device():
    device = SimpleNamespace(
        id=4,
        name="Device D",
        playback_position=None,
        playback_duration=None,
        playback_progress=None,
    )
    core_device = SimpleNamespace(
        current_position=None,
        duration_formatted=None,
        playback_progress=None,
    )
    runtime_updates = []
    runtime = SimpleNamespace(
        update_runtime_playback_progress=lambda device_name, position, duration, progress: runtime_updates.append(
            (device_name, position, duration, progress)
        )
    )

    service = DevicePlaybackService(
        db=_FakeDB(device),
        runtime=runtime,
        runtime_sync_service=SimpleNamespace(get_core_device=lambda device_name: core_device),
        get_device_instance=lambda device_id: None,
        update_device_status=lambda *_args, **_kwargs: True,
    )

    result = service.update_playback_progress(4, "00:01:02", "00:10:00", 10)

    assert result is True
    assert device.playback_position == "00:01:02"
    assert device.playback_duration == "00:10:00"
    assert device.playback_progress == 10
    assert runtime_updates == [("Device D", "00:01:02", "00:10:00", 10)]
    assert core_device.current_position == "00:01:02"
    assert core_device.duration_formatted == "00:10:00"
    assert core_device.playback_progress == 10
