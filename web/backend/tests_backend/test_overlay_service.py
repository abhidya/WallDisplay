import requests
from datetime import UTC, datetime

from web.backend.schemas.overlay import ApiConfigs, OverlayConfigResponse, VideoTransform, Widget, WidgetPosition, WidgetSize
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


def test_window_refresh_state_revision_changes_when_config_content_changes(tmp_path):
    background = tmp_path / "background.mp4"
    background.write_bytes(b"video")

    video = type(
        "VideoStub",
        (),
        {
            "id": 1,
            "name": "Background",
            "path": str(background),
            "file_name": "background.mp4",
            "file_size": 1024,
            "format": "mp4",
            "duration": 10.0,
            "resolution": "1920x1080",
            "category": None,
            "source_type": None,
            "overlay_optimized": False,
            "has_subtitle": False,
            "subtitle_path": None,
            "created_at": None,
            "updated_at": None,
        },
    )()
    config = type(
        "OverlayConfigStub",
        (),
        {
            "id": 7,
            "name": "Config A",
            "background_type": "video",
            "video_id": video.id,
            "mapping_scene_id": None,
            "video_transform": {"x": 0, "y": 0, "scale": 1.0, "rotation": 0},
            "widgets": [
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
            "api_configs": {},
            "created_at": None,
            "updated_at": datetime.now(UTC),
        },
    )()

    class _FakeQuery:
        def __init__(self, result):
            self._result = result

        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return self._result

    class _FakeDB:
        def query(self, model):
            if model.__name__ == "OverlayConfig":
                return _FakeQuery(config)
            if model.__name__ == "VideoModel":
                return _FakeQuery(video)
            return _FakeQuery(None)

    service = OverlayService(_FakeDB())
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
    config.updated_at = datetime.now(UTC)

    updated_state = service.get_window_refresh_state(config.id)

    assert initial_state["config_id"] == config.id
    assert updated_state["config_id"] == config.id
    assert initial_state["revision"] != updated_state["revision"]


def test_minimize_window_init_config_drops_hidden_widgets_and_api_secrets():
    service = OverlayService.__new__(OverlayService)
    config = OverlayConfigResponse(
        id=1,
        name="Config A",
        background_type="mapping",
        video_id=None,
        mapping_scene_id=1,
        video_transform=VideoTransform(),
        widgets=[
            Widget(
                id="weather-1",
                type="weather",
                position=WidgetPosition(x=0, y=0),
                size=WidgetSize(width=200, height=100),
                config={"city": "SF"},
                visible=True,
            ),
            Widget(
                id="steam-1",
                type="steam",
                position=WidgetPosition(x=0, y=0),
                size=WidgetSize(width=200, height=100),
                config={"steam_id": "123"},
                visible=False,
            ),
        ],
        api_configs=ApiConfigs(
            transit_stop_id="13915",
            spotify_access_token="secret",
        ),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    minimized = service._minimize_window_init_config(config)

    assert [widget.id for widget in minimized.widgets] == ["weather-1"]
    assert minimized.api_configs.spotify_access_token == ""
    assert minimized.api_configs.transit_stop_id == ""


def test_minimize_mapping_scene_payload_deduplicates_repeated_media_sets():
    service = OverlayService.__new__(OverlayService)
    repeated_media = [
        {"url": "/api/photos/1/file", "kind": "image", "duration_ms": None},
        {"url": "/api/photos/2/file", "kind": "image", "duration_ms": None},
    ]
    scene = {
        "groups": [
            {"id": "g1", "media_items": repeated_media, "media_urls": [item["url"] for item in repeated_media]},
            {"id": "g2", "media_items": repeated_media, "media_urls": [item["url"] for item in repeated_media]},
            {"id": "g3", "media_items": [{"url": "/api/videos/1/file", "kind": "video", "duration_ms": 1000}]},
        ]
    }

    minimized = service._minimize_mapping_scene_payload(scene)

    assert minimized["groups"][0]["media_items_key"] == minimized["groups"][1]["media_items_key"]
    assert "media_items" not in minimized["groups"][0]
    assert "media_urls" not in minimized["groups"][1]
    assert minimized["groups"][2]["media_items"] == [{"url": "/api/videos/1/file", "kind": "video", "duration_ms": 1000}]
    assert len(minimized["shared_media_sets"]) == 1
