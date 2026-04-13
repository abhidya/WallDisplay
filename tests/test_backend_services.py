#!/usr/bin/env python3
"""
Backend service layer tests aligned with current service APIs.
"""
import importlib
import os
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "web" / "backend"))


@pytest.fixture
def mock_db():
    return Mock()


@pytest.fixture
def runtime_stub():
    runtime = SimpleNamespace()
    runtime.device_status = {}
    runtime.device_state_lock = threading.RLock()
    runtime.connectivity_timeout = 30
    runtime.get_device = lambda _name: None
    runtime.devices = []
    runtime.get_devices = lambda: runtime.devices
    runtime.auto_play_video = Mock(return_value=True)
    runtime.get_assigned_video = lambda _name: None
    return runtime


class TestDeviceService:
    @pytest.fixture
    def device_service(self, mock_db, runtime_stub):
        device_service_module = importlib.import_module("services.device_service")
        return device_service_module.DeviceService(mock_db, runtime=runtime_stub)

    def test_get_devices_empty(self, device_service, mock_db):
        query = mock_db.query.return_value
        query.offset.return_value.limit.return_value.all.return_value = []

        assert device_service.get_devices() == []

    def test_get_devices_serializes_database_rows(self, device_service, mock_db):
        query = mock_db.query.return_value
        db_device = SimpleNamespace(id=1, name="Test Device")
        query.offset.return_value.limit.return_value.all.return_value = [db_device]
        device_service._device_to_dict = Mock(return_value={"id": 1, "name": "Test Device"})

        result = device_service.get_devices(skip=5, limit=10)

        assert result == [{"id": 1, "name": "Test Device"}]
        device_service._device_to_dict.assert_called_once_with(db_device)
        query.offset.assert_called_once_with(5)
        query.offset.return_value.limit.assert_called_once_with(10)

    def test_play_video_delegates_to_playback_service(self, device_service):
        device_service.device_playback_service.play_video = Mock(return_value=True)

        result = device_service.play_video(1, "test.mp4", loop=True)

        assert result is True
        device_service.device_playback_service.play_video.assert_called_once_with(1, "test.mp4", True)

    def test_stop_video_delegates_to_playback_service(self, device_service):
        device_service.device_playback_service.stop_video = Mock(return_value=True)

        result = device_service.stop_video(1)

        assert result is True
        device_service.device_playback_service.stop_video.assert_called_once_with(1)


class TestVideoService:
    @pytest.fixture
    def mock_streaming_service(self):
        service = Mock()
        service.get_serve_ip.return_value = "10.0.0.63"
        return service

    @pytest.fixture
    def video_service(self, mock_db, mock_streaming_service):
        video_service_module = importlib.import_module("services.video_service")
        return video_service_module.VideoService(mock_db, mock_streaming_service)

    def test_scan_directory_empty(self, video_service, monkeypatch):
        monkeypatch.setattr("services.video_service.os.path.exists", lambda _path: True)
        monkeypatch.setattr("services.video_service.os.path.isdir", lambda _path: True)
        monkeypatch.setattr("services.video_service.os.walk", lambda _path: [])

        assert video_service.scan_directory("/videos") == []

    def test_scan_directory_adds_only_video_files(self, video_service, monkeypatch):
        monkeypatch.setattr("services.video_service.os.path.exists", lambda _path: True)
        monkeypatch.setattr("services.video_service.os.path.isdir", lambda _path: True)
        monkeypatch.setattr(
            "services.video_service.os.walk",
            lambda _path: [
                ("/videos", [], ["test.mp4", "clip.avi", "notes.txt"]),
            ],
        )
        video_one = SimpleNamespace(name="test")
        video_two = SimpleNamespace(name="clip")
        video_service.get_video_by_path = Mock(side_effect=[None, None])
        video_service.create_video = Mock(side_effect=[video_one, video_two])

        result = video_service.scan_directory("/videos")

        assert result == [video_one, video_two]
        created = [call.args[0] for call in video_service.create_video.call_args_list]
        assert [video.name for video in created] == ["test", "clip"]
        assert [video.path for video in created] == ["/videos/test.mp4", "/videos/clip.avi"]
        assert [video.category for video in created] == ["background", "background"]
        assert [video.source_type for video in created] == ["directory_scan", "directory_scan"]

    def test_get_videos_returns_database_rows(self, video_service, mock_db):
        query = mock_db.query.return_value
        rows = [SimpleNamespace(id=1, name="Test Video")]
        query.offset.return_value.limit.return_value.all.return_value = rows

        result = video_service.get_videos(skip=2, limit=20)

        assert result == rows
        query.offset.assert_called_once_with(2)
        query.offset.return_value.limit.assert_called_once_with(20)


class TestStreamingService:
    @pytest.fixture
    def streaming_service(self):
        streaming_registry_module = importlib.import_module("core.streaming_registry")
        streaming_registry_module.StreamingSessionRegistry._instance = None

        streaming_service_module = importlib.import_module("core.streaming_service")
        service = streaming_service_module.StreamingService(runtime=None)
        yield service

        service.registry.stop_monitoring()
        streaming_registry_module.StreamingSessionRegistry._instance = None

    def test_normalize_file_name(self, streaming_service):
        assert streaming_service.normalize_file_name("Tést Video 01!.mp4") == "test-video-01.mp4"

    def test_get_or_create_stream_reuses_existing_mapping(self, streaming_service):
        streaming_service.file_to_session_map = {
            "10.0.0.5:9011/uploads/videos/test-video.mp4": "session-1",
        }

        result = streaming_service.get_or_create_stream(
            "/tmp/uploads/videos/test-video.mp4",
            device_name="Projector A",
        )

        assert result == {
            "port": 9011,
            "url": "http://10.0.0.5:9011/uploads/videos/test-video.mp4",
        }

    def test_get_or_create_stream_starts_new_server_when_missing(self, streaming_service):
        streaming_service.get_serve_ip = Mock(return_value="10.0.0.5")
        server = SimpleNamespace(server_address=("10.0.0.5", 9012))
        streaming_service.start_server = Mock(
            return_value=(
                {"sample.mp4": "http://10.0.0.5:9012/sample.mp4"},
                server,
            )
        )

        result = streaming_service.get_or_create_stream(
            "/videos/sample.mp4",
            device_name="Projector A",
        )

        assert result == {
            "port": 9012,
            "url": "http://10.0.0.5:9012/sample.mp4",
        }
        streaming_service.start_server.assert_called_once_with(
            files={"sample.mp4": "/videos/sample.mp4"},
            serve_ip="10.0.0.5",
            port_range=(9010, 9100),
            device_name="Projector A",
            stream_type="device_stream",
            consumer_id=None,
        )


class TestBrightnessControlService:
    @pytest.fixture
    def brightness_service(self, monkeypatch, runtime_stub):
        brightness_module = importlib.import_module("services.brightness_control_service")
        monkeypatch.setattr(brightness_module, "get_app_runtime", lambda: runtime_stub)
        monkeypatch.setattr(brightness_module, "create_black_video", lambda duration=86400: "/tmp/black.mp4")
        monkeypatch.setattr(
            brightness_module,
            "get_overlay_cast_service",
            lambda: SimpleNamespace(list_sessions=lambda: []),
        )
        return brightness_module.BrightnessControlService()

    def test_get_status_reports_no_devices(self, brightness_service):
        status = brightness_service.get_status()

        assert status["blackout_active"] is False
        assert status["playing_devices"] == []
        assert status["backed_up_devices"] == []
        assert status["playing_count"] == 0
        assert status["total_devices"] == 0

    def test_set_brightness_updates_without_blackout_transition(self, brightness_service):
        result = brightness_service.set_brightness(50)

        assert result == {
            "brightness": 50,
            "status": "updated",
            "blackout_active": False,
            "message": "Brightness set to 50%",
        }

    def test_set_brightness_to_zero_errors_when_black_video_missing(self, brightness_service, runtime_stub, monkeypatch):
        runtime_stub.devices = [
            SimpleNamespace(
                name="Projector A",
                status="connected",
                hostname=None,
                action_url=None,
                is_playing=False,
                current_video=None,
            )
        ]
        monkeypatch.setattr("services.brightness_control_service.os.path.exists", lambda _path: False)

        result = brightness_service.set_brightness(0)

        assert result == {
            "brightness": 0,
            "status": "error",
            "error": "Black video file not available",
        }

    def test_set_brightness_deactivates_existing_blackout(self, brightness_service):
        brightness_service.is_blackout_active = True

        result = brightness_service.set_brightness(75)

        assert result["status"] == "blackout_deactivated"
        assert result["blackout_active"] is False
        assert result["restored_devices"] == []
        assert result["device_count"] == 0


class TestStreamingSessionRegistry:
    @pytest.fixture
    def streaming_registry(self):
        registry_module = importlib.import_module("core.streaming_registry")
        registry_module.StreamingSessionRegistry._instance = None
        registry = registry_module.StreamingSessionRegistry.get_instance()
        yield registry
        registry.stop_monitoring()
        registry_module.StreamingSessionRegistry._instance = None

    def test_register_session(self, streaming_registry):
        session = streaming_registry.register_session(
            device_name="Test Device",
            video_path="/videos/test.mp4",
            server_ip="127.0.0.1",
            server_port=8888,
        )

        sessions = streaming_registry.get_active_sessions()
        assert session.session_id
        assert len(sessions) == 1
        assert sessions[0].device_name == "Test Device"
        assert sessions[0].server_port == 8888

    def test_unregister_session(self, streaming_registry):
        session = streaming_registry.register_session(
            device_name="Test Device",
            video_path="/videos/test.mp4",
            server_ip="127.0.0.1",
            server_port=8888,
        )

        assert streaming_registry.unregister_session(session.session_id) is True
        assert streaming_registry.get_active_sessions() == []

    def test_get_sessions_for_device(self, streaming_registry):
        session = streaming_registry.register_session(
            device_name="Test Device",
            video_path="/videos/test.mp4",
            server_ip="127.0.0.1",
            server_port=8888,
        )

        sessions = streaming_registry.get_sessions_for_device("Test Device")

        assert len(sessions) == 1
        assert sessions[0].session_id == session.session_id
        assert streaming_registry.get_sessions_for_device("Unknown Device") == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
