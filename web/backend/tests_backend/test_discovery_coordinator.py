import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from web.backend.services.discovery_coordinator import DiscoveryCoordinator
from web.backend.services.runtime_registry_service import RuntimeRegistryService


def test_discovery_coordinator_reconciles_new_and_existing_devices():
    registered = []
    status_updates = []
    runtime_registry = RuntimeRegistryService()

    existing_device = SimpleNamespace(device_info={"hostname": "10.0.0.1", "location": "http://old"})
    manager = SimpleNamespace(
        devices={"Existing": existing_device},
        device_status={},
        runtime_registry=runtime_registry,
        device_state_lock=threading.RLock(),
        _acquire_device_lock=lambda: True,
        _release_device_lock=lambda: None,
        register_device=lambda info: registered.append(info) or SimpleNamespace(name=info["device_name"]),
        update_device_status=lambda device_name, status: status_updates.append((device_name, status)),
    )

    coordinator = DiscoveryCoordinator(manager)
    observations = coordinator.reconcile_discovered_devices(
        [
            {
                "friendly_name": "New Device",
                "hostname": "10.0.0.2",
                "location": "http://new",
            },
            {
                "friendly_name": "Existing",
                "hostname": "10.0.0.3",
                "location": "http://changed",
            },
        ]
    )

    assert {obs["device_name"] for obs in observations} == {"New Device", "Existing"}
    assert any(obs["is_new_device"] for obs in observations if obs["device_name"] == "New Device")
    assert any(obs["is_changed_device"] for obs in observations if obs["device_name"] == "Existing")
    assert ("New Device", "connected") in status_updates
    assert ("Existing", "connected") in status_updates
    assert len(registered) == 2


def test_discovery_coordinator_removes_duplicate_devices():
    coordinator = DiscoveryCoordinator(SimpleNamespace())
    devices = [
        {"friendly_name": "A", "hostname": "1.1.1.1"},
        {"friendly_name": "A", "hostname": "1.1.1.1"},
        {"friendly_name": "B", "hostname": "2.2.2.2"},
    ]

    result = coordinator.remove_duplicates(devices)

    assert result == [
        {"friendly_name": "A", "hostname": "1.1.1.1"},
        {"friendly_name": "B", "hostname": "2.2.2.2"},
    ]


def test_discovery_coordinator_marks_and_removes_disconnected_device():
    runtime_registry = RuntimeRegistryService()
    runtime_registry.last_seen["Ghost"] = 0.0
    runtime_registry.device_status["Ghost"] = {"status": "connected"}
    updates = []

    manager = SimpleNamespace(
        devices={"Ghost": SimpleNamespace(is_playing=False)},
        device_state_lock=threading.RLock(),
        runtime_registry=runtime_registry,
        last_seen=runtime_registry.last_seen,
        get_db_device_by_name=lambda _device_name: None,
        connectivity_timeout=10,
        update_device_status=lambda device_name, status: updates.append((device_name, status)),
    )

    coordinator = DiscoveryCoordinator(manager)
    coordinator.evaluate_disconnected_devices(set())

    assert ("Ghost", "disconnected") in updates
    assert "Ghost" not in manager.devices
    assert "Ghost" not in runtime_registry.device_status


def test_discovery_coordinator_uses_runtime_db_lookup_fallback(monkeypatch):
    runtime_registry = RuntimeRegistryService()
    runtime_registry.last_seen["Ghost"] = 0.0
    runtime_registry.device_status["Ghost"] = {"status": "connected"}
    updates = []

    manager = SimpleNamespace(
        devices={"Ghost": SimpleNamespace(is_playing=False)},
        device_state_lock=threading.RLock(),
        runtime_registry=runtime_registry,
        last_seen=runtime_registry.last_seen,
        connectivity_timeout=10,
        update_device_status=lambda device_name, status: updates.append((device_name, status)),
    )

    monkeypatch.setattr(
        "services.app_runtime.get_app_runtime",
        lambda: SimpleNamespace(
            get_db_device_by_name=lambda device_name: None if device_name == "Ghost" else object()
        ),
    )

    coordinator = DiscoveryCoordinator(manager)
    coordinator.evaluate_disconnected_devices(set())

    assert ("Ghost", "disconnected") in updates


@patch("web.backend.services.discovery_coordinator.threading.Thread")
def test_discovery_coordinator_start_and_status(mock_thread, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    thread_instance = MagicMock()
    thread_instance.is_alive.return_value = False
    mock_thread.return_value = thread_instance

    manager = SimpleNamespace(
        discovery_thread=None,
        discovery_running=False,
        discovery_paused=False,
        discovery_interval=10,
        devices={"A": SimpleNamespace(is_playing=True), "B": SimpleNamespace(is_playing=False)},
    )

    coordinator = DiscoveryCoordinator(manager)
    coordinator.start()
    status = coordinator.get_status()
    coordinator.pause()
    coordinator.stop()

    mock_thread.assert_called_once()
    thread_instance.start.assert_called_once()
    assert status["running"] is True
    assert status["paused"] is False
    assert status["interval"] == 10
    assert status["devices_discovered"] == 0
    assert status["devices_playing"] == 1
    assert status["observed_devices"] == 2
    assert "candidate_hosts" in status
    assert manager.discovery_running is False


def test_discovery_coordinator_does_not_start_in_unified_authority(monkeypatch):
    monkeypatch.setenv("NANODLNA_DISCOVERY_AUTHORITY", "unified")
    manager = SimpleNamespace(
        discovery_thread=None,
        discovery_running=False,
        discovery_paused=False,
        discovery_interval=10,
    )

    coordinator = DiscoveryCoordinator(manager)
    coordinator.start()

    assert manager.discovery_running is False
    assert manager.discovery_paused is True
