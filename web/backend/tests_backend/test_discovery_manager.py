import asyncio
from types import SimpleNamespace

from web.backend.discovery.discovery_manager import DiscoveryManager


class _FakeBackend:
    def __init__(self, name, devices=None, timeout=2.0):
        self.name = name
        self.casting_method = SimpleNamespace(value=name.lower())
        self.discovery_running = False
        self.discovered_devices = {}
        self._devices = devices or []
        self.discovery_timeout = timeout

    def register_callback(self, callback):
        self.callback = callback

    async def discover_devices(self):
        return self._devices

    def get_online_devices(self):
        return self._devices

    def get_active_sessions(self):
        return []


def test_discovery_manager_get_device_alias_uses_device_by_id():
    manager = DiscoveryManager()
    device = SimpleNamespace(id="device-1")
    manager.all_devices[device.id] = device

    assert manager.get_device("device-1") is device


def test_discovery_manager_discover_devices_updates_inventory():
    manager = DiscoveryManager()
    device = SimpleNamespace(id="device-1")
    backend = _FakeBackend("DLNA", devices=[device], timeout=2.0)
    manager.register_backend(backend)

    discovered = asyncio.run(manager.discover_devices(timeout=9))

    assert discovered == [device]
    assert manager.get_device_by_id("device-1") is device
    assert backend.discovery_timeout == 2.0


def test_discovery_manager_finds_session_by_device_id():
    manager = DiscoveryManager()
    device = SimpleNamespace(id="device-1")
    session = SimpleNamespace(id="session-1", device=device, is_active=True)
    manager.device_sessions[device.id] = [session]

    assert manager._find_session_or_device_session("device-1") is session
    assert manager._find_session_or_device_session("session-1") is session


def test_discovery_manager_register_enabled_backends_from_config(monkeypatch):
    manager = DiscoveryManager()
    config_manager = SimpleNamespace(get_global_config=lambda: {"backends": {"dlna": True, "airplay": False, "overlay": True}})

    monkeypatch.setattr("web.backend.discovery.discovery_manager.ConfigurationManager.get_instance", lambda: config_manager)
    monkeypatch.setattr("web.backend.discovery.discovery_manager.DLNADiscoveryBackend", lambda: _FakeBackend("DLNA"))
    monkeypatch.setattr("web.backend.discovery.discovery_manager.AirPlayDiscoveryBackend", lambda: _FakeBackend("AirPlay"))
    monkeypatch.setattr("web.backend.discovery.discovery_manager.OverlayDiscoveryBackend", lambda: _FakeBackend("Overlay"))

    asyncio.run(manager._register_enabled_backends())

    assert set(manager.backends.keys()) == {"DLNA", "Overlay"}
    assert manager.is_running is False


def test_discovery_manager_register_enabled_backends_sync_wrapper(monkeypatch):
    manager = DiscoveryManager()
    calls = []
    monkeypatch.setattr(
        "web.backend.discovery.discovery_manager.ConfigurationManager.get_instance",
        lambda: SimpleNamespace(get_global_config=lambda: {"backends": {"dlna": True}}),
    )
    monkeypatch.setattr(
        "web.backend.discovery.discovery_manager.DLNADiscoveryBackend",
        lambda: calls.append("dlna") or _FakeBackend("DLNA"),
    )
    monkeypatch.setattr("web.backend.discovery.discovery_manager.AirPlayDiscoveryBackend", lambda: _FakeBackend("AirPlay"))
    monkeypatch.setattr("web.backend.discovery.discovery_manager.OverlayDiscoveryBackend", lambda: _FakeBackend("Overlay"))

    manager.register_enabled_backends()

    assert calls == ["dlna"]


def test_discovery_manager_unregister_callback():
    manager = DiscoveryManager()
    callback = lambda *_args: None

    manager.register_callback(callback)
    manager.unregister_callback(callback)

    assert callback not in manager._callbacks
