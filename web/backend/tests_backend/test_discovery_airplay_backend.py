from web.backend.discovery.backends.airplay import AirPlayDiscoveryBackend


def test_airplay_backend_zeroconf_unavailable_warning_logged_once(monkeypatch, caplog):
    backend = AirPlayDiscoveryBackend()
    monkeypatch.setattr("web.backend.discovery.backends.airplay.ZEROCONF_AVAILABLE", False)
    caplog.set_level("WARNING")

    import asyncio
    asyncio.run(backend.discover_devices())
    asyncio.run(backend.discover_devices())

    warning_records = [
        rec for rec in caplog.records
        if "Zeroconf not available, cannot discover AirPlay devices" in rec.message
    ]
    assert len(warning_records) == 1
