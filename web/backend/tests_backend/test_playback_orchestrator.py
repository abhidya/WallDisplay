import threading
from datetime import datetime, timezone
from types import SimpleNamespace

from web.backend.services.playback_intent_service import PlaybackIntentService
from web.backend.services.playback_orchestrator import PlaybackOrchestrator


class _FakeConfigService:
    def __init__(self, config):
        self._config = config

    def get_device_config(self, device_name):
        return self._config.get(device_name)


class _FakeCastService:
    def __init__(self):
        self.started = []

    def get_session_for_device(self, device_id):
        return None

    async def start_cast(self, **kwargs):
        self.started.append(kwargs)
        return {"status": "started"}


def test_orchestrator_assigns_configured_video(monkeypatch, tmp_path):
    video_path = tmp_path / "video.mp4"
    video_path.write_text("x")

    assigned = []
    playback_results = []
    playback_monitoring_service = SimpleNamespace(
        start_health_check=lambda device_name, video_path: playback_results.append(
            ("health", device_name, video_path)
        ),
        track_playback_result=lambda device_name, video_path, success: playback_results.append(
            ("result", device_name, video_path, success)
        ),
    )
    manager = SimpleNamespace(
        config_service=_FakeConfigService(
            {"Device A": {"video_file": str(video_path), "priority": 80}}
        ),
        assignment_lock=threading.Lock(),
        device_state_lock=threading.RLock(),
        playback_intent_service=PlaybackIntentService(),
        playback_monitoring_service=playback_monitoring_service,
        max_retry_attempts=3,
        retry_delay_base=5,
        get_device=lambda device_name: SimpleNamespace(
            name=device_name,
            current_video=None,
            is_playing=False,
            stop=lambda: None,
        ),
        auto_play_video=lambda device, path, loop=True, config=None: assigned.append(
            (device.name, path, loop, config)
        ) or True,
        _process_airplay_casting=lambda device_name, config: None,
    )

    orchestrator = PlaybackOrchestrator(manager)
    orchestrator.process_discovered_device("Device A", is_new_device=True, is_changed_device=False)

    assert assigned == [
        ("Device A", str(video_path), True, {"video_file": str(video_path), "priority": 80})
    ]
    assert playback_results[-1] == ("result", "Device A", str(video_path), True)


def test_orchestrator_schedules_assignment_without_playing(tmp_path):
    video_path = tmp_path / "scheduled.mp4"
    video_path.write_text("x")

    manager = SimpleNamespace(
        assignment_lock=threading.Lock(),
        device_state_lock=threading.RLock(),
        playback_intent_service=PlaybackIntentService(),
        playback_monitoring_service=SimpleNamespace(
            start_health_check=lambda *args, **kwargs: None,
            track_playback_result=lambda *args, **kwargs: None,
        ),
        get_device=lambda device_name: SimpleNamespace(name=device_name, is_playing=False, current_video=None),
        config_service=None,
        auto_play_video=lambda *args, **kwargs: True,
        max_retry_attempts=3,
        retry_delay_base=5,
    )

    orchestrator = PlaybackOrchestrator(manager)
    result = orchestrator.apply_video_assignment(
        "Device S",
        str(video_path),
        priority=60,
        schedule_time=datetime.now(timezone.utc),
    )

    assert result is True
    assert manager.playback_intent_service.scheduled_assignments["Device S"]["video_path"] == str(video_path)


def test_orchestrator_starts_overlay_cast(monkeypatch):
    cast_service = _FakeCastService()
    manager = SimpleNamespace(
        _resolve_discovery_device_id=lambda device_name, hostname: "dlna_10.0.0.50_1400",
    )

    monkeypatch.setattr(
        "web.backend.services.playback_orchestrator.get_overlay_cast_service",
        lambda: cast_service,
    )

    db_device = SimpleNamespace(
        hostname="10.0.0.50",
        config={
            "auto_overlay_cast_enabled": True,
            "auto_overlay_config_id": 7,
        },
    )

    orchestrator = PlaybackOrchestrator(manager)
    result = orchestrator.process_overlay_cast("Projector A", db_device)

    assert result is True
    assert cast_service.started == [
        {
            "device_id": "dlna_10.0.0.50_1400",
            "config_id": 7,
            "overlay_base_url": "http://localhost:8000",
            "controls_hidden": True,
        }
    ]


def test_orchestrator_restart_assigned_video_updates_status(monkeypatch, tmp_path):
    video_path = tmp_path / "recover.mp4"
    video_path.write_text("x")
    status_updates = []

    manager = SimpleNamespace(
        playback_intent_service=PlaybackIntentService(),
        playback_monitoring_service=SimpleNamespace(
            start_health_check=lambda *args, **kwargs: None,
            track_playback_result=lambda *args, **kwargs: None,
        ),
        auto_play_video=lambda device, path, loop=True: True,
        update_device_status=lambda **kwargs: status_updates.append(kwargs),
    )
    manager.playback_intent_service.set_assigned_video("Device R", str(video_path))

    device = SimpleNamespace(stop=lambda: None)
    orchestrator = PlaybackOrchestrator(manager)

    result = orchestrator.restart_assigned_video("Device R", device, loop=True)

    assert result is True
    assert status_updates[-1] == {
        "device_name": "Device R",
        "status": "connected",
        "is_playing": True,
        "current_video": str(video_path),
    }


def test_orchestrator_uses_runtime_db_lookup_fallback_for_manual_mode(monkeypatch, tmp_path):
    video_path = tmp_path / "video.mp4"
    video_path.write_text("x")

    assigned = []
    manager = SimpleNamespace(
        config_service=_FakeConfigService(
            {"Device A": {"video_file": str(video_path), "priority": 80}}
        ),
        assignment_lock=threading.Lock(),
        device_state_lock=threading.RLock(),
        playback_intent_service=PlaybackIntentService(),
        playback_monitoring_service=SimpleNamespace(
            start_health_check=lambda *args, **kwargs: None,
            track_playback_result=lambda *args, **kwargs: None,
        ),
        max_retry_attempts=3,
        retry_delay_base=5,
        get_device=lambda device_name: SimpleNamespace(
            name=device_name,
            current_video=None,
            is_playing=False,
            stop=lambda: None,
        ),
        auto_play_video=lambda device, path, loop=True, config=None: assigned.append(
            (device.name, path, loop, config)
        ) or True,
        _process_airplay_casting=lambda device_name, config: None,
    )

    monkeypatch.setattr(
        "services.app_runtime.get_app_runtime",
        lambda: SimpleNamespace(
            get_db_device_by_name=lambda device_name: SimpleNamespace(
                user_control_mode="manual",
                user_control_reason="user_play",
                config={},
            )
        ),
    )

    orchestrator = PlaybackOrchestrator(manager)
    orchestrator.process_discovered_device("Device A", is_new_device=True, is_changed_device=False)

    assert assigned == []


def test_orchestrator_uses_runtime_airplay_fallback(monkeypatch):
    calls = []
    manager = SimpleNamespace(
        config_service=_FakeConfigService(
            {"Device A": {"airplay_mode": True, "airplay_url": "http://localhost:8000/overlay"}}
        ),
        assignment_lock=threading.Lock(),
        device_state_lock=threading.RLock(),
        playback_intent_service=PlaybackIntentService(),
        playback_monitoring_service=SimpleNamespace(
            start_health_check=lambda *args, **kwargs: None,
            track_playback_result=lambda *args, **kwargs: None,
        ),
        max_retry_attempts=3,
        retry_delay_base=5,
        get_device=lambda device_name: SimpleNamespace(
            name=device_name,
            current_video=None,
            is_playing=False,
            stop=lambda: None,
        ),
        auto_play_video=lambda *args, **kwargs: True,
    )

    monkeypatch.setattr(
        "services.app_runtime.get_app_runtime",
        lambda: SimpleNamespace(
            get_db_device_by_name=lambda device_name: SimpleNamespace(
                user_control_mode="auto",
                user_control_reason="",
                config={},
            ),
            process_airplay_casting=lambda device_name, config: calls.append((device_name, config)),
        ),
    )

    orchestrator = PlaybackOrchestrator(manager)
    orchestrator.process_discovered_device("Device A", is_new_device=True, is_changed_device=False)

    assert calls == [
        (
            "Device A",
            {"airplay_mode": True, "airplay_url": "http://localhost:8000/overlay"},
        )
    ]
