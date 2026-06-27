from datetime import datetime, timezone
from types import SimpleNamespace

from web.backend.services.device_view_service import DeviceViewService


class _FakeCastService:
    def __init__(self, sessions):
        self._sessions = sessions

    def list_sessions(self):
        return list(self._sessions)


def test_build_device_dict_includes_manager_status_and_overlay(monkeypatch, device_manager):
    device = SimpleNamespace(
        id=1,
        name="Projector A",
        type="dlna",
        hostname="10.0.0.50",
        action_url="http://10.0.0.50:1400/action",
        friendly_name="Projector A",
        manufacturer="Test",
        location="http://10.0.0.50:1400/device.xml",
        status="disconnected",
        is_playing=False,
        current_video=None,
        playback_position=None,
        playback_duration=None,
        playback_progress=None,
        config={"auto_overlay_cast_enabled": True},
        playback_started_at=None,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    with device_manager.device_state_lock:
        device_manager.device_status[device.name] = {
            "status": "connected",
            "last_updated": 1000.0,
            "is_playing": True,
            "last_seen_at": 1000.0,
            "last_lost_at": None,
            "reconnect_count": 2,
            "degraded_count": 1,
            "offline_count": 0,
        }

    monkeypatch.setattr(
        "web.backend.services.device_view_service.get_overlay_cast_service",
        lambda: _FakeCastService(
            [
                {
                    "session_id": "cast-1",
                    "device_id": "dlna_10.0.0.50_1400",
                    "status": "running",
                    "current_step": "casting",
                    "ffmpeg_speed": 1.01,
                    "ffmpeg_fps": 29.97,
                    "ffmpeg_bitrate_kbps": 1600,
                    "active_clients": 1,
                    "started_at": "2026-01-02T12:00:00",
                }
            ]
        ),
    )
    monkeypatch.setattr(
        "web.backend.services.device_view_service.get_recent_live_projector_client",
        lambda _client_ip: None,
    )

    view_service = DeviceViewService(device_manager)
    device_dict = view_service.build_device_dict(device)

    assert device_dict["status"] == "connected"
    assert device_dict["availability"] == "offline"
    assert device_dict["manager_is_playing"] is True
    assert device_dict["active_overlay_cast"] is True
    assert device_dict["overlay_cast_source"] == "backend_cast"
    assert device_dict["overlay_cast_session_id"] == "cast-1"
    assert device_dict["reconnect_count"] == 2
    assert device_dict["created_at"] == "2026-01-01T00:00:00Z"


def test_build_device_dict_returns_empty_overlay_state_when_no_session(monkeypatch, device_manager):
    device = SimpleNamespace(
        id=2,
        name="TV A",
        type="dlna",
        hostname="10.0.0.60",
        action_url=None,
        friendly_name="TV A",
        manufacturer=None,
        location=None,
        status="disconnected",
        is_playing=False,
        current_video=None,
        playback_position=None,
        playback_duration=None,
        playback_progress=None,
        config=None,
        playback_started_at=None,
        created_at=None,
        updated_at=None,
    )

    monkeypatch.setattr(
        "web.backend.services.device_view_service.get_overlay_cast_service",
        lambda: _FakeCastService([]),
    )
    monkeypatch.setattr(
        "web.backend.services.device_view_service.get_recent_live_projector_client",
        lambda _client_ip: None,
    )

    view_service = DeviceViewService(device_manager)
    device_dict = view_service.build_device_dict(device)

    assert device_dict["active_overlay_cast"] is False
    assert device_dict["overlay_cast_source"] is None
    assert device_dict["overlay_cast_status"] is None
    assert device_dict["availability"] == "offline"


def test_build_device_detail_dict_includes_core_device_and_streaming_details(monkeypatch, device_manager):
    device = SimpleNamespace(
        id=3,
        name="Projector B",
        type="dlna",
        hostname="10.0.0.70",
        action_url="http://10.0.0.70:1400/action",
        friendly_name="Projector B",
        manufacturer="Test",
        location="http://10.0.0.70:1400/device.xml",
        status="connected",
        is_playing=False,
        current_video=None,
        playback_position=None,
        playback_duration=None,
        playback_progress=None,
        config=None,
        playback_started_at=None,
        created_at=None,
        updated_at=None,
    )

    core_device = SimpleNamespace(is_playing=True, current_video="/tmp/projector-b.mp4")
    device_manager.device_inventory.set(device.name, core_device)

    session = SimpleNamespace(
        active=True,
        session_id="sess-1",
        video_path="/tmp/projector-b.mp4",
        server_ip="10.0.0.5",
        server_port=9001,
        bytes_served=1024,
        client_ip="10.0.0.70",
        client_connections=2,
        connection_errors=0,
        status="active",
        last_activity_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        get_bandwidth=lambda: 4096,
    )

    monkeypatch.setattr(
        "web.backend.services.device_view_service.get_overlay_cast_service",
        lambda: _FakeCastService([]),
    )
    monkeypatch.setattr(
        "web.backend.services.device_view_service.get_recent_live_projector_client",
        lambda _client_ip: None,
    )

    fake_registry = SimpleNamespace(get_sessions_for_device=lambda device_name: [session] if device_name == device.name else [])
    monkeypatch.setattr(
        "core.streaming_registry.StreamingSessionRegistry.get_instance",
        lambda: fake_registry,
    )

    view_service = DeviceViewService(device_manager)
    device_dict = view_service.build_device_detail_dict(device)

    assert device_dict["is_playing"] is True
    assert device_dict["current_video"] == "/tmp/projector-b.mp4"
    assert device_dict["streaming_sessions"] == 1
    assert device_dict["streaming_session_ids"] == ["sess-1"]
    assert device_dict["streaming_details"]["server_port"] == 9001


def test_build_device_dict_uses_live_direct_overlay_client_when_ip_matches(monkeypatch, device_manager):
    device = SimpleNamespace(
        id=4,
        name="Projector C",
        type="projector",
        hostname="10.0.0.80",
        action_url=None,
        friendly_name="Projector C",
        manufacturer="Test",
        location=None,
        status="connected",
        is_playing=False,
        current_video=None,
        playback_position=None,
        playback_duration=None,
        playback_progress=None,
        config=None,
        playback_started_at=None,
        created_at=None,
        updated_at=None,
    )

    monkeypatch.setattr(
        "web.backend.services.device_view_service.get_overlay_cast_service",
        lambda: _FakeCastService([]),
    )
    monkeypatch.setattr(
        "web.backend.services.device_view_service.get_recent_live_projector_client",
        lambda client_ip: {
            "client_ip": client_ip,
            "path": "/backend-static/overlay_window.html",
            "query": "config_id=7&controls=hidden",
            "config_id": 7,
            "document_visibility": "visible",
            "first_seen_at": "2026-01-02T12:00:00+00:00",
            "last_seen_at": "2026-01-02T12:00:30+00:00",
            "heartbeat_count": 3,
        } if client_ip == "10.0.0.80" else None,
    )

    view_service = DeviceViewService(device_manager)
    device_dict = view_service.build_device_dict(device)

    assert device_dict["active_overlay_cast"] is True
    assert device_dict["overlay_cast_source"] == "direct_client"
    assert device_dict["overlay_cast_status"] == "direct-html"
    assert device_dict["overlay_cast_direct_config_id"] == 7
    assert device_dict["overlay_cast_direct_visibility"] == "visible"
    assert device_dict["overlay_cast_direct_url"] == "/backend-static/overlay_window.html?config_id=7&controls=hidden"
    assert device_dict["overlay_cast_session_id"] == "direct-client:10.0.0.80"


def test_build_device_dict_includes_hdmi_renderer_state(monkeypatch, device_manager):
    device = SimpleNamespace(
        id=5,
        name="proj-hdmi-local",
        type="hdmi",
        hostname=r"\\.\DISPLAY5",
        action_url=None,
        friendly_name="HDMI Projector",
        manufacturer="Local HDMI",
        location="renderer://projectors/proj-hdmi-local",
        status="disconnected",
        is_playing=False,
        current_video=None,
        playback_position=None,
        playback_duration=None,
        playback_progress=None,
        config={
            "casting_method": "hdmi",
            "managed_by": "renderer_config",
            "renderer_projector_id": "proj-hdmi-local",
            "target_name": r"\\.\DISPLAY5",
        },
        playback_started_at=None,
        created_at=None,
        updated_at=None,
    )

    renderer_service = SimpleNamespace(
        get_renderer_status=lambda projector_id: {
            "projector_id": projector_id,
            "sender_status": {
                "target": r"\\.\DISPLAY5",
                "connection_state": "attached",
                "projection_state": "projecting",
                "power_state": "manual_on",
                "content_url": "http://127.0.0.1:8088/backend-static/video.html",
                "display": {
                    "index": 5,
                    "name": r"\\.\DISPLAY5",
                    "x": 1920,
                    "y": 0,
                    "width": 3840,
                    "height": 2160,
                    "is_primary": False,
                },
            },
        },
        list_projectors=lambda: [],
    )
    monkeypatch.setattr(
        "web.backend.services.device_view_service.get_renderer_service_for_device_view",
        lambda: renderer_service,
    )
    monkeypatch.setattr(
        "web.backend.services.device_view_service.get_overlay_cast_service",
        lambda: _FakeCastService([]),
    )
    monkeypatch.setattr(
        "web.backend.services.device_view_service.get_recent_live_projector_client",
        lambda _client_ip: None,
    )

    view_service = DeviceViewService(device_manager)
    device_dict = view_service.build_device_dict(device)

    assert device_dict["casting_method"] == "hdmi"
    assert device_dict["renderer_projector_id"] == "proj-hdmi-local"
    assert device_dict["hdmi_target_name"] == r"\\.\DISPLAY5"
    assert device_dict["hdmi_connection_state"] == "attached"
    assert device_dict["hdmi_projection_state"] == "projecting"
    assert device_dict["hdmi_power_state"] == "manual_on"
    assert device_dict["hdmi_display"]["width"] == 3840
    assert device_dict["status"] == "connected"
    assert device_dict["manager_status"] == "connected"
    assert device_dict["manager_is_playing"] is True
    assert device_dict["is_playing"] is True
    assert device_dict["availability"] == "online"
    assert device_dict["current_video"].endswith("/backend-static/video.html")
