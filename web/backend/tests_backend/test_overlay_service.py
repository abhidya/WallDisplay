import requests

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
        "status": "active",
        "title": "Track Name",
        "artist": "Artist Name",
        "album_art": "https://example.com/cover.jpg",
        "progress_ms": 60000,
        "duration_ms": 180000,
    }
