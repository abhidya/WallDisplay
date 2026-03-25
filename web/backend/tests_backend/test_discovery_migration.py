import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from web.backend.discovery.migration import DiscoveryMigrationAdapter


def test_migration_adapter_uses_runtime_inventory_helpers_for_status(monkeypatch):
    runtime = SimpleNamespace(
        get_device_count=lambda: 4,
        get_playing_device_count=lambda: 2,
        uses_unified_discovery_authority=False,
    )

    adapter = DiscoveryMigrationAdapter(runtime)
    monkeypatch.setattr(
        adapter.new_discovery_manager,
        "get_backend_status",
        lambda: {"dlna": {"discovered_devices": 3}},
    )

    status = adapter.get_discovery_status()

    assert status["authority"] == "legacy"
    assert status["old_system"] == {"devices": 4, "playing": 2}
    assert status["new_system"] == {"dlna": {"discovered_devices": 3}}


def test_migration_adapter_migrates_existing_devices_from_runtime(monkeypatch):
    old_devices = [SimpleNamespace(name="Device A"), SimpleNamespace(name="Device B")]
    runtime = SimpleNamespace(get_devices=lambda: old_devices, uses_unified_discovery_authority=False)

    adapter = DiscoveryMigrationAdapter(runtime)
    migrated = []
    monkeypatch.setattr(adapter, "_migrate_configuration", lambda: None)
    monkeypatch.setattr(
        adapter,
        "_convert_old_to_new_device",
        lambda old_device: SimpleNamespace(id=f"id-{old_device.name}", name=old_device.name),
    )

    manager_store = {}

    class _Lock:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    adapter.new_discovery_manager._device_lock = _Lock()
    adapter.new_discovery_manager.all_devices = manager_store

    asyncio.run(adapter._migrate_existing_devices())

    assert set(adapter._device_mapping.keys()) == {"Device A", "Device B"}
    assert set(manager_store.keys()) == {"id-Device A", "id-Device B"}


def test_migration_adapter_uses_runtime_discovery_manager_and_registration(monkeypatch):
    discovery_manager = SimpleNamespace(register_enabled_backends=lambda: calls.append("register_enabled_backends"))
    calls = []
    runtime = SimpleNamespace(discovery_manager=discovery_manager, uses_unified_discovery_authority=False)

    adapter = DiscoveryMigrationAdapter(runtime)

    assert adapter.new_discovery_manager is discovery_manager
    assert calls == ["register_enabled_backends"]


def test_migration_adapter_does_not_own_unified_discovery_lifecycle(monkeypatch):
    discovery_manager = SimpleNamespace(
        is_running=False,
        register_enabled_backends=lambda: None,
        start_discovery=AsyncMock(),
        stop_discovery=AsyncMock(),
    )
    runtime = SimpleNamespace(discovery_manager=discovery_manager, uses_unified_discovery_authority=False)
    adapter = DiscoveryMigrationAdapter(runtime)

    monkeypatch.setattr(adapter, "_migrate_existing_devices", AsyncMock())
    monkeypatch.setattr(adapter, "_sync_devices", AsyncMock(side_effect=[None, RuntimeError("stop-loop")]))
    monkeypatch.setattr("web.backend.discovery.migration.asyncio.sleep", AsyncMock(return_value=None))

    adapter._migration_running = True
    adapter._run_migration_loop()

    discovery_manager.start_discovery.assert_not_called()
    discovery_manager.stop_discovery.assert_not_called()


def test_migration_adapter_skips_legacy_to_unified_seed_in_unified_mode(monkeypatch):
    runtime = SimpleNamespace(get_devices=lambda: [SimpleNamespace(name="Legacy A")], uses_unified_discovery_authority=True)
    adapter = DiscoveryMigrationAdapter(runtime)

    migrated = []
    monkeypatch.setattr(adapter, "_migrate_configuration", lambda: migrated.append("config"))
    monkeypatch.setattr(adapter, "_backfill_unified_devices_to_old_runtime", lambda: migrated.append("backfill"))

    asyncio.run(adapter._migrate_existing_devices())

    assert migrated == ["config", "backfill"]
    assert adapter._device_mapping == {}


def test_migration_adapter_reports_unified_authority(monkeypatch):
    runtime = SimpleNamespace(
        get_device_count=lambda: 2,
        get_playing_device_count=lambda: 1,
        uses_unified_discovery_authority=True,
    )
    adapter = DiscoveryMigrationAdapter(runtime)
    monkeypatch.setattr(adapter.new_discovery_manager, "get_backend_status", lambda: {})

    status = adapter.get_discovery_status()

    assert status["authority"] == "unified"


def test_migration_adapter_registers_and_unregisters_event_callback():
    callbacks = []
    discovery_manager = SimpleNamespace(
        register_enabled_backends=lambda: None,
        register_callback=lambda callback: callbacks.append(("register", callback)),
        unregister_callback=lambda callback: callbacks.append(("unregister", callback)),
    )
    runtime = SimpleNamespace(discovery_manager=discovery_manager, uses_unified_discovery_authority=True)
    adapter = DiscoveryMigrationAdapter(runtime)
    adapter._migration_thread = SimpleNamespace(start=lambda: None, is_alive=lambda: False, join=lambda timeout=5: None)

    adapter.start_migration()
    adapter.stop_migration()

    assert callbacks[0][0] == "register"
    assert callbacks[1][0] == "unregister"
    assert callbacks[0][1] == callbacks[1][1]


def test_migration_adapter_handles_unified_discovery_event_for_legacy_runtime():
    from web.backend.discovery.base import CastingMethod

    updates = []
    registrations = []
    runtime = SimpleNamespace(
        uses_unified_discovery_authority=True,
        discovery_manager=SimpleNamespace(register_enabled_backends=lambda: None),
        get_device=lambda device_name: None,
        register_device=lambda device_info: registrations.append(device_info),
        update_device_status=lambda **kwargs: updates.append(kwargs),
    )
    adapter = DiscoveryMigrationAdapter(runtime)
    device = SimpleNamespace(
        name="Renderer A",
        friendly_name="Renderer A",
        hostname="10.0.0.9",
        action_url="http://10.0.0.9/action",
        manufacturer="Test",
        location="http://10.0.0.9/device.xml",
        casting_method=CastingMethod.DLNA,
    )

    asyncio.run(adapter._handle_unified_discovery_event("device_discovered", device))
    asyncio.run(adapter._handle_unified_discovery_event("device_lost", device))

    assert registrations == [
        {
            "device_name": "Renderer A",
            "type": "dlna",
            "hostname": "10.0.0.9",
            "action_url": "http://10.0.0.9/action",
            "friendly_name": "Renderer A",
            "manufacturer": "Test",
            "location": "http://10.0.0.9/device.xml",
        }
    ]
    assert updates == [
        {"device_name": "Renderer A", "status": "connected", "is_playing": False},
    ]


def test_migration_adapter_backfills_unified_devices_to_legacy_runtime():
    from web.backend.discovery.base import CastingMethod

    registrations = []
    updates = []
    runtime = SimpleNamespace(
        uses_unified_discovery_authority=True,
        discovery_manager=SimpleNamespace(register_enabled_backends=lambda: None),
        get_device=lambda device_name: None,
        register_device=lambda device_info: registrations.append(device_info),
        update_device_status=lambda **kwargs: updates.append(kwargs),
    )
    adapter = DiscoveryMigrationAdapter(runtime)
    adapter.new_discovery_manager.get_all_devices = lambda: [
        SimpleNamespace(
            name="Renderer A",
            friendly_name="Renderer A",
            hostname="10.0.0.10",
            action_url="http://10.0.0.10/action",
            manufacturer="Test",
            location="http://10.0.0.10/device.xml",
            casting_method=CastingMethod.DLNA,
            is_online=True,
        )
    ]

    adapter._backfill_unified_devices_to_old_runtime()

    assert registrations == [
        {
            "device_name": "Renderer A",
            "type": "dlna",
            "hostname": "10.0.0.10",
            "action_url": "http://10.0.0.10/action",
            "friendly_name": "Renderer A",
            "manufacturer": "Test",
            "location": "http://10.0.0.10/device.xml",
        }
    ]
    assert updates == [
        {"device_name": "Renderer A", "status": "connected", "is_playing": False}
    ]


def test_migration_adapter_skips_periodic_sync_in_unified_mode(monkeypatch):
    discovery_manager = SimpleNamespace(register_enabled_backends=lambda: None)
    runtime = SimpleNamespace(discovery_manager=discovery_manager, uses_unified_discovery_authority=True)
    adapter = DiscoveryMigrationAdapter(runtime)

    monkeypatch.setattr(adapter, "_migrate_existing_devices", AsyncMock())
    monkeypatch.setattr(adapter, "_sync_devices", AsyncMock())

    async def _sleep(_seconds):
        adapter._migration_running = False

    monkeypatch.setattr("web.backend.discovery.migration.asyncio.sleep", _sleep)

    adapter._migration_running = True
    adapter._run_migration_loop()

    adapter._sync_devices.assert_not_called()


def test_migration_adapter_exits_after_initial_backfill_in_unified_mode(monkeypatch):
    discovery_manager = SimpleNamespace(register_enabled_backends=lambda: None)
    runtime = SimpleNamespace(discovery_manager=discovery_manager, uses_unified_discovery_authority=True)
    adapter = DiscoveryMigrationAdapter(runtime)

    migrated = []
    monkeypatch.setattr(adapter, "_migrate_existing_devices", AsyncMock(side_effect=lambda: migrated.append("migrated")))
    monkeypatch.setattr(adapter, "_sync_devices", AsyncMock(side_effect=lambda: migrated.append("synced")))

    adapter._migration_running = True
    adapter._run_migration_loop()

    assert migrated == ["migrated"]
    adapter._sync_devices.assert_not_called()
