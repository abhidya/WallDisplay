import requests

from web.backend.models.overlay import OverlayConfig
from web.backend.models.video import VideoModel
from web.backend.services.overlay_service import OverlayService


class _FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


def test_fetch_spotify_refreshes_after_unauthorized(monkeypatch):
    service = OverlayService(db=None)
    access_tokens = []

    def fake_spotify_currently_playing(access_token):
        access_tokens.append(access_token)
        if access_token == "stale-token":
            return _FakeResponse(401)
        return _FakeResponse(
            200,
            {
                "item": {
                    "name": "Track Name",
                    "artists": [{"name": "Artist Name"}],
                    "album": {"images": [{"url": "https://example.com/cover.jpg"}]},
                    "duration_ms": 180000,
                },
                "progress_ms": 60000,
            },
        )

    monkeypatch.setattr(service, "_spotify_currently_playing", fake_spotify_currently_playing)
    monkeypatch.setattr(service, "_refresh_oauth_access_token", lambda *args: "fresh-token")

    result = service._fetch_spotify_now_playing(
        {
            "spotify_access_token": "stale-token",
            "spotify_refresh_token": "refresh-token",
            "spotify_client_id": "client-id",
            "spotify_client_secret": "client-secret",
        }
    )

    assert access_tokens == ["stale-token", "fresh-token"]
    assert result == {
        "status": "paused",
        "message": "Playback paused",
        "title": "Track Name",
        "artist": "Artist Name",
        "album_art": "https://example.com/cover.jpg",
        "progress": 60000 / 180000,
        "progress_ms": 60000,
        "duration_ms": 180000,
        "is_playing": False,
        "album": "",
        "device_name": "",
    }


def test_fetch_spotify_idle_when_nothing_playing(monkeypatch):
    service = OverlayService(db=None)
    monkeypatch.setattr(service, "_spotify_currently_playing", lambda _: _FakeResponse(204))

    result = service._fetch_spotify_now_playing({"spotify_access_token": "token"})

    assert result == {
        "status": "idle",
        "message": "Nothing is playing right now",
    }


def test_fetch_gmail_refreshes_after_unauthorized(monkeypatch):
    service = OverlayService(db=None)
    calls = []

    def fake_get(url, headers=None, params=None, timeout=None):
        calls.append(headers["Authorization"])
        if len(calls) == 1:
            return _FakeResponse(401)
        if "messages/" in url:
            return _FakeResponse(
                200,
                {
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "Sender"},
                            {"name": "Subject", "value": "Subject"},
                        ]
                    }
                },
            )
        return _FakeResponse(200, {"messages": [{"id": "abc"}]})

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(service, "_refresh_oauth_access_token", lambda *args: "fresh-gmail-token")

    result = service._fetch_gmail_summary(
        {
            "gmail_access_token": "stale-token",
            "gmail_refresh_token": "refresh-token",
            "gmail_client_id": "client-id",
            "gmail_client_secret": "client-secret",
        }
    )

    assert calls[:2] == ["Bearer stale-token", "Bearer fresh-gmail-token"]
    assert result == {
        "status": "active",
        "message": "1 unread messages",
        "items": [{"sender": "Sender", "title": "Subject"}],
        "count": 1,
    }


def test_window_refresh_state_revision_changes_when_config_content_changes(test_db, tmp_path):
    video = VideoModel(
        name="Background",
        path=str(tmp_path / "background.mp4"),
        file_name="background.mp4",
        file_size=1024,
        format="mp4",
        duration=10.0,
        resolution="1920x1080",
        has_subtitle=False,
    )
    test_db.add(video)
    test_db.commit()
    test_db.refresh(video)

    config = OverlayConfig(
        name="Config A",
        background_type="video",
        video_id=video.id,
        mapping_scene_id=None,
        video_transform={"x": 0, "y": 0, "scale": 1.0, "rotation": 0},
        widgets=[
            {
                "id": "time-1",
                "type": "time",
                "position": {"x": 0, "y": 0},
                "size": {"width": 200, "height": 80},
                "config": {"format": "12h"},
                "visible": True,
                "rotation": 0,
            }
        ],
        api_configs={},
    )
    test_db.add(config)
    test_db.commit()
    test_db.refresh(config)

    service = OverlayService(test_db)
    service._global_api_config_path = str(tmp_path / "global_api.json")

    initial_state = service.get_window_refresh_state(config.id)

    config.widgets = [
        {
            "id": "time-1",
            "type": "time",
            "position": {"x": 50, "y": 25},
            "size": {"width": 220, "height": 90},
            "config": {"format": "24h"},
            "visible": True,
            "rotation": 15,
        }
    ]
    test_db.commit()
    test_db.refresh(config)

    updated_state = service.get_window_refresh_state(config.id)

    assert initial_state["config_id"] == config.id
    assert updated_state["config_id"] == config.id
    assert initial_state["revision"] != updated_state["revision"]
