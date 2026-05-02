import asyncio
import socket
import subprocess

from web.backend.discovery.backends.dlna import DLNADiscoveryBackend
from web.backend.discovery.backends.overlay import OverlayDiscoveryBackend


class _FakeAiohttpSession:
    instances = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.closed = False
        _FakeAiohttpSession.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.closed = True

    async def close(self):
        self.closed = True


class _FakeDiscoverySocket:
    def __init__(self, responses):
        self._responses = list(responses)

    def setsockopt(self, *args, **kwargs):
        return None

    def bind(self, *args, **kwargs):
        return None

    def settimeout(self, *args, **kwargs):
        return None

    def sendto(self, *args, **kwargs):
        return None

    def recvfrom(self, _size):
        if self._responses:
            return self._responses.pop(0), ("10.0.0.10", 1900)
        raise socket.timeout()

    def close(self):
        return None


def test_dlna_discovery_reuses_one_http_session_per_cycle(monkeypatch):
    _FakeAiohttpSession.instances = []
    used_sessions = []

    async def fake_parse_device_description(_location_url, session):
        used_sessions.append(session)
        return None

    responses = [
        (
            "HTTP/1.1 200 OK\r\n"
            "ST: urn:schemas-upnp-org:service:AVTransport:1\r\n"
            "LOCATION: http://10.0.0.10:1234/device-1.xml\r\n\r\n"
        ).encode("utf-8"),
        (
            "HTTP/1.1 200 OK\r\n"
            "ST: urn:schemas-upnp-org:service:AVTransport:1\r\n"
            "LOCATION: http://10.0.0.11:1234/device-2.xml\r\n\r\n"
        ).encode("utf-8"),
    ]

    backend = DLNADiscoveryBackend()
    loop = asyncio.new_event_loop()
    try:
        monkeypatch.setattr(backend, "_candidate_discovery_hosts", lambda: ["0.0.0.0"])
        monkeypatch.setattr(backend, "_parse_device_description", fake_parse_device_description)
        monkeypatch.setattr("web.backend.discovery.backends.dlna.aiohttp.ClientSession", _FakeAiohttpSession)
        monkeypatch.setattr(
            "web.backend.discovery.backends.dlna.socket.socket",
            lambda *_args, **_kwargs: _FakeDiscoverySocket(responses),
        )

        loop.run_until_complete(backend.discover_devices())
    finally:
        loop.close()

    assert len(_FakeAiohttpSession.instances) == 1
    assert len(used_sessions) == 2
    assert used_sessions[0] is used_sessions[1]
    assert _FakeAiohttpSession.instances[0].closed is True


def test_dlna_stop_discovery_closes_persistent_http_session():
    backend = DLNADiscoveryBackend()
    session = _FakeAiohttpSession()
    backend._persistent_http_session = session
    backend.discovery_running = True

    asyncio.run(backend.stop_discovery())

    assert session.closed is True
    assert backend._persistent_http_session is None


def test_overlay_discovery_times_out_subprocess(monkeypatch, caplog):
    backend = OverlayDiscoveryBackend()
    monkeypatch.setattr("web.backend.discovery.backends.overlay.platform.system", lambda: "Darwin")
    monkeypatch.setattr(
        "web.backend.discovery.backends.overlay.subprocess.run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])
        ),
    )
    caplog.set_level("WARNING")

    devices = asyncio.run(backend._platform_specific_discovery())

    assert devices == []
    assert any("Timed out while collecting macOS display info" in record.message for record in caplog.records)
