from web.backend.discovery.backends.dlna import DLNADiscoveryBackend


def test_dlna_backend_candidate_hosts_include_all_local_interfaces(monkeypatch):
    class _FakeSocket:
        def connect(self, _addr):
            return None

        def getsockname(self):
            return ("10.0.0.74", 12345)

        def close(self):
            return None

    monkeypatch.setattr(
        "web.backend.discovery.backends.dlna.get_local_ipv4_addresses",
        lambda: {"10.0.0.74", "10.0.0.99"},
    )
    monkeypatch.setattr("web.backend.discovery.backends.dlna.socket.socket", lambda *_args, **_kwargs: _FakeSocket())
    monkeypatch.setattr("web.backend.discovery.backends.dlna.socket.gethostname", lambda: "mini")
    monkeypatch.setattr(
        "web.backend.discovery.backends.dlna.socket.getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("10.0.0.99", 0))],
    )

    backend = DLNADiscoveryBackend()

    assert backend._candidate_discovery_hosts() == ["0.0.0.0", "10.0.0.74", "10.0.0.99"]
