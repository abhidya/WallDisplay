from types import SimpleNamespace
import threading


def test_get_app_runtime_builds_manager_from_shared_services(monkeypatch):
    from web.backend.services import app_runtime as runtime_module

    captured = {}
    original_lifecycle = SimpleNamespace(owner="manager")
    manager = SimpleNamespace(
        name="manager",
        device_lifecycle_service=original_lifecycle,
        playback_monitoring_service="monitoring",
        _handle_streaming_issue=lambda session: None,
        device_state_lock="lock",
        connectivity_timeout=30,
        device_lock_timeout=5.0,
        assignment_lock="assignment-lock",
        _acquire_device_lock=lambda: True,
        _release_device_lock=lambda: None,
        discovery_coordinator="coordinator",
    )

    monkeypatch.setattr(runtime_module, "_app_runtime_instance", None)
    monkeypatch.setattr(runtime_module.ConfigService, "get_instance", lambda: "config")
    registry = SimpleNamespace(
        register_health_check_handler=lambda handler: captured.setdefault("registered_handlers", []).append(handler),
        unregister_health_check_handler=lambda handler: captured.setdefault("unregistered_handlers", []).append(handler),
    )
    monkeypatch.setattr(runtime_module.StreamingSessionRegistry, "get_instance", lambda: registry)
    monkeypatch.setattr(runtime_module.DiscoveryManager, "get_instance", lambda: "discovery")

    def fake_get_device_manager(**kwargs):
        captured.update(kwargs)
        return manager

    monkeypatch.setattr(runtime_module, "get_device_manager", fake_get_device_manager)

    runtime = runtime_module.get_app_runtime()

    assert runtime.config_service == "config"
    assert runtime.streaming_registry == registry
    assert runtime.discovery_manager == "discovery"
    assert runtime.unified_discovery_lifecycle_service.discovery_manager == "discovery"
    assert runtime.device_manager is manager
    assert runtime.device_lifecycle_service is manager.device_lifecycle_service
    assert runtime.device_lifecycle_service is not original_lifecycle
    assert runtime.device_lifecycle_service.owner is runtime
    assert runtime.playback_monitoring_service == manager.playback_monitoring_service
    assert runtime.runtime_playback_service.runtime is runtime
    assert runtime.device_state_lock == "lock"
    assert runtime.connectivity_timeout == 30
    assert runtime.legacy_streaming_issue_handler is manager._handle_streaming_issue
    assert runtime.device_lock_timeout == 5.0
    assert runtime.discovery_coordinator == "coordinator"
    assert captured["config_service"] == "config"
    assert captured["streaming_registry"] is registry
    assert captured["device_inventory"] is runtime.device_inventory_service
    assert captured["runtime_registry"] is runtime.runtime_registry_service
    assert captured["playback_intent_service"] is runtime.playback_intent_service
    assert captured["unregistered_handlers"] == [manager._handle_streaming_issue]
    assert captured["registered_handlers"] == [runtime.handle_streaming_issue]

    monkeypatch.setattr(runtime_module, "_app_runtime_instance", None)


def test_app_runtime_start_and_stop_background_services(monkeypatch):
    from web.backend.services import app_runtime as runtime_module

    discovery = SimpleNamespace(start=lambda: calls.append("start"), stop=lambda: calls.append("stop"))
    unified_discovery = SimpleNamespace(register_enabled_backends=lambda: calls.append("register_enabled_backends"))
    unified_lifecycle = SimpleNamespace(start=lambda: calls.append("unified_start"), stop=lambda: calls.append("unified_stop"))
    manager = SimpleNamespace(discovery_coordinator=discovery)
    calls = []
    stopped = []
    automation_calls = []

    migration_adapter = SimpleNamespace(stop_migration=lambda: stopped.append("migration"))
    automation_service = SimpleNamespace(
        start=lambda: automation_calls.append("start"),
        stop=lambda: automation_calls.append("stop"),
    )

    monkeypatch.setattr(
        runtime_module,
        "_start_discovery_migration",
        lambda device_manager: migration_adapter,
    )

    runtime = runtime_module.AppRuntime(
        config_service="config",
        streaming_registry="registry",
        discovery_manager=unified_discovery,
        unified_discovery_lifecycle_service=unified_lifecycle,
        device_inventory_service="inventory",
        runtime_registry_service="runtime_registry",
        playback_intent_service="playback_intent",
        device_manager=manager,
        airplay_projection_automation_service=automation_service,
    )

    runtime.start_background_services()
    assert calls == ["register_enabled_backends", "start"]
    assert automation_calls == ["start"]
    assert runtime.migration_adapter is migration_adapter

    runtime.stop_background_services()
    assert calls == ["register_enabled_backends", "start", "stop", "unified_stop"]
    assert automation_calls == ["start", "stop"]
    assert stopped == ["migration"]
    assert runtime.migration_adapter is None


def test_app_runtime_discovery_controls_delegate_to_device_manager():
    calls = []
    discovery = SimpleNamespace(
        pause=lambda: calls.append("pause"),
        resume=lambda: calls.append("resume"),
        get_status=lambda: {"running": True},
    )
    manager = SimpleNamespace(discovery_coordinator=discovery)
    runtime = SimpleNamespace(device_manager=manager)

    from web.backend.services.app_runtime import AppRuntime

    AppRuntime.pause_discovery(runtime)
    AppRuntime.resume_discovery(runtime)
    status = AppRuntime.get_discovery_status(runtime)

    assert calls == ["pause", "resume"]
    assert status == {"running": True, "authority": "legacy", "unified_running": False}


def test_app_runtime_set_discovery_interval_delegates_to_legacy_manager():
    manager = SimpleNamespace(discovery_interval=10)
    runtime = SimpleNamespace(device_manager=manager)

    from web.backend.services.app_runtime import AppRuntime

    result = AppRuntime.set_discovery_interval(runtime, 25)

    assert result == 25
    assert manager.discovery_interval == 25


def test_app_runtime_discovery_controls_use_unified_lifecycle_in_unified_mode(monkeypatch):
    calls = []
    unified_lifecycle = SimpleNamespace(
        pause=lambda: calls.append("pause"),
        resume=lambda: calls.append("resume"),
        get_status=lambda: {"running": False, "paused": True, "devices_discovered": 3, "devices_playing": 1, "interval": 10},
        is_running=False,
    )
    runtime = SimpleNamespace(
        unified_discovery_lifecycle_service=unified_lifecycle,
        discovery_manager=SimpleNamespace(is_running=False),
        uses_unified_discovery_authority=True,
    )

    monkeypatch.setenv("NANODLNA_DISCOVERY_AUTHORITY", "unified")

    from web.backend.services.app_runtime import AppRuntime

    AppRuntime.pause_discovery(runtime)
    AppRuntime.resume_discovery(runtime)
    status = AppRuntime.get_discovery_status(runtime)

    assert calls == ["pause", "resume"]
    assert status == {
        "running": False,
        "paused": True,
        "devices_discovered": 3,
        "devices_playing": 1,
        "interval": 10,
        "authority": "unified",
        "unified_running": False,
    }


def test_app_runtime_set_discovery_interval_updates_unified_backends(monkeypatch):
    backends = {
        "DLNA": SimpleNamespace(discovery_interval=10),
        "Overlay": SimpleNamespace(discovery_interval=15),
    }
    runtime = SimpleNamespace(
        discovery_manager=SimpleNamespace(backends=backends),
        uses_unified_discovery_authority=True,
    )

    monkeypatch.setenv("NANODLNA_DISCOVERY_AUTHORITY", "unified")

    from web.backend.services.app_runtime import AppRuntime

    result = AppRuntime.set_discovery_interval(runtime, 20)

    assert result == 20
    assert backends["DLNA"].discovery_interval == 20
    assert backends["Overlay"].discovery_interval == 20


def test_app_runtime_start_background_services_skips_legacy_discovery_in_unified_mode(monkeypatch):
    from web.backend.services import app_runtime as runtime_module

    calls = []
    unified_discovery = SimpleNamespace(register_enabled_backends=lambda: calls.append("register_enabled_backends"), is_running=True)
    unified_lifecycle = SimpleNamespace(start=lambda: calls.append("unified_start"), stop=lambda: calls.append("unified_stop"))
    manager = SimpleNamespace(discovery_coordinator=SimpleNamespace(start=lambda: calls.append("legacy_start")))
    automation_calls = []

    monkeypatch.setenv("NANODLNA_DISCOVERY_AUTHORITY", "unified")
    monkeypatch.setattr(runtime_module, "_start_discovery_migration", lambda runtime: SimpleNamespace(stop_migration=lambda: None))

    runtime = runtime_module.AppRuntime(
        config_service="config",
        streaming_registry="registry",
        discovery_manager=unified_discovery,
        unified_discovery_lifecycle_service=unified_lifecycle,
        device_inventory_service="inventory",
        runtime_registry_service="runtime_registry",
        playback_intent_service="playback_intent",
        device_manager=manager,
        airplay_projection_automation_service=SimpleNamespace(start=lambda: automation_calls.append("start"), stop=lambda: automation_calls.append("stop")),
    )

    runtime.start_background_services()

    assert calls == ["register_enabled_backends", "unified_start"]
    assert automation_calls == ["start"]


def test_app_runtime_discover_dlna_devices_uses_unified_authority(monkeypatch):
    from web.backend.services import app_runtime as runtime_module

    class _Device:
        name = "Renderer A"
        friendly_name = "Renderer A"
        hostname = "10.0.0.8"
        action_url = "http://10.0.0.8/action"
        manufacturer = "Test"
        location = "http://10.0.0.8/device.xml"

    async def _discover_devices(backend_name=None, timeout=None):
        return [_Device()]

    runtime = SimpleNamespace(
        discovery_manager=SimpleNamespace(discover_devices=_discover_devices),
        uses_unified_discovery_authority=True,
    )

    monkeypatch.setenv("NANODLNA_DISCOVERY_AUTHORITY", "unified")

    result = runtime_module.AppRuntime.discover_dlna_devices(runtime, 4.0)

    assert result == [
        {
            "device_name": "Renderer A",
            "name": "Renderer A",
            "type": "dlna",
            "friendly_name": "Renderer A",
            "hostname": "10.0.0.8",
            "action_url": "http://10.0.0.8/action",
            "manufacturer": "Test",
            "location": "http://10.0.0.8/device.xml",
        }
    ]


def test_app_runtime_hydrates_database_devices_into_manager():
    registered = []
    status_updates = []
    runtime = SimpleNamespace(
        register_device=lambda device_info: registered.append(device_info) or object(),
        update_device_status=lambda **kwargs: status_updates.append(kwargs),
    )

    from web.backend.services.app_runtime import AppRuntime

    AppRuntime.hydrate_database_devices(
        runtime,
        [
            {
                "name": "Device A",
                "type": "dlna",
                "hostname": "10.0.0.10",
                "action_url": "http://10.0.0.10/action",
                "friendly_name": "Device A",
                "manufacturer": "Test",
                "location": "http://10.0.0.10/device.xml",
                "config": {"priority": 50},
                "is_playing": True,
                "current_video": "/tmp/a.mp4",
            }
        ],
    )

    assert registered == [
        {
            "device_name": "Device A",
            "type": "dlna",
            "hostname": "10.0.0.10",
            "action_url": "http://10.0.0.10/action",
            "friendly_name": "Device A",
            "manufacturer": "Test",
            "location": "http://10.0.0.10/device.xml",
            "priority": 50,
        }
    ]
    assert status_updates == [
        {
            "device_name": "Device A",
            "status": "disconnected",
            "is_playing": True,
            "current_video": "/tmp/a.mp4",
        }
    ]


def test_app_runtime_build_device_service_uses_runtime_manager(monkeypatch):
    import importlib

    from web.backend.services import app_runtime as runtime_module
    device_service_module = importlib.import_module("services.device_service")

    calls = []

    class _FakeDeviceService:
        def __init__(self, db, device_manager=None, runtime=None):
            calls.append((db, device_manager, runtime))

    runtime = runtime_module.AppRuntime(
        config_service="config",
        streaming_registry="registry",
        discovery_manager="discovery",
        unified_discovery_lifecycle_service=SimpleNamespace(),
        device_inventory_service="inventory",
        runtime_registry_service="runtime_registry",
        playback_intent_service="playback_intent",
        device_manager="manager",
        device_lifecycle_service=None,
    )

    monkeypatch.setattr(device_service_module, "DeviceService", _FakeDeviceService)

    runtime.build_device_service("db-session")

    assert calls == [("db-session", None, runtime)]


def test_app_runtime_fallback_properties_work_without_manager():
    from web.backend.services.app_runtime import AppRuntime

    runtime = SimpleNamespace(
        device_manager=None,
        device_state_lock_ref=None,
        connectivity_timeout_seconds=None,
        device_lock_timeout_seconds=None,
    )

    lock = AppRuntime.device_state_lock.fget(runtime)
    timeout = AppRuntime.connectivity_timeout.fget(runtime)
    device_lock_timeout = AppRuntime.device_lock_timeout.fget(runtime)
    controller = AppRuntime._get_discovery_controller(runtime)

    assert lock is runtime.device_state_lock_ref
    assert timeout == 30
    assert device_lock_timeout == 5.0
    assert controller is None


def test_device_service_normalizes_legacy_manager_to_app_runtime(monkeypatch):
    import importlib

    device_service_module = importlib.import_module("services.device_service")

    runtime = SimpleNamespace(
        device_manager="legacy-manager",
        device_status={},
        device_state_lock=threading.RLock(),
        get_device=lambda device_name: None,
        connectivity_timeout=30,
    )

    monkeypatch.setattr(device_service_module, "get_app_runtime", lambda: runtime)

    service = device_service_module.DeviceService.__new__(device_service_module.DeviceService)
    device_service_module.DeviceService.__init__(service, db=SimpleNamespace(), device_manager="other-manager")

    assert service.runtime is runtime


def test_app_runtime_recovers_runtime_device_from_database(monkeypatch):
    from web.backend.services import app_runtime as runtime_module

    calls = []
    db_session = object()
    recovered_device = SimpleNamespace(update_streaming_info=lambda url, port: calls.append(("stream", url, port)))
    db_device = SimpleNamespace(
        name="Device A",
        type="dlna",
        hostname="10.0.0.10",
        action_url="http://10.0.0.10/action",
        friendly_name="Device A",
        manufacturer="Test",
        location="http://10.0.0.10/device.xml",
        streaming_url="http://10.0.0.5:9000/video.mp4",
        streaming_port=9000,
    )

    class _FakeGenerator:
        def __iter__(self):
            return self

        def __next__(self):
            return db_session

        def close(self):
            calls.append(("closed",))

    runtime = SimpleNamespace(
        build_device_service=lambda db: SimpleNamespace(
            get_device_by_name=lambda device_name: db_device if device_name == "Device A" else None
        ),
        register_device=lambda device_info: calls.append(("register", device_info)) or recovered_device,
    )

    monkeypatch.setattr("database.database.get_db", lambda: _FakeGenerator())

    result = runtime_module.AppRuntime.recover_runtime_device(runtime, "Device A")

    assert result is recovered_device
    assert calls[0] == (
        "register",
        {
            "device_name": "Device A",
            "type": "dlna",
            "hostname": "10.0.0.10",
            "action_url": "http://10.0.0.10/action",
            "friendly_name": "Device A",
            "manufacturer": "Test",
            "location": "http://10.0.0.10/device.xml",
        },
    )
    assert ("stream", "http://10.0.0.5:9000/video.mp4", 9000) in calls


def test_app_runtime_get_db_device_by_name(monkeypatch):
    from web.backend.services import app_runtime as runtime_module

    db_session = object()
    db_device = SimpleNamespace(name="Device A")

    class _FakeGenerator:
        def __iter__(self):
            return self

        def __next__(self):
            return db_session

        def close(self):
            return None

    runtime = SimpleNamespace(
        build_device_service=lambda db: SimpleNamespace(
            get_device_by_name=lambda device_name: db_device if device_name == "Device A" else None
        )
    )

    monkeypatch.setattr("database.database.get_db", lambda: _FakeGenerator())

    assert runtime_module.AppRuntime.get_db_device_by_name(runtime, "Device A") is db_device
    assert runtime_module.AppRuntime.get_db_device_by_name(runtime, "Missing") is None


def test_app_runtime_plays_runtime_device_video_via_device_service(monkeypatch):
    from web.backend.services import app_runtime as runtime_module

    class _FakeGenerator:
        def __iter__(self):
            return self

        def __next__(self):
            return object()

        def close(self):
            return None

    runtime = SimpleNamespace(
        build_device_service=lambda db: SimpleNamespace(
            get_device_by_name=lambda device_name: SimpleNamespace(id=12) if device_name == "Device A" else None,
            play_video=lambda device_id, video_path, loop=False: (device_id, video_path, loop) == (12, "/tmp/a.mp4", True),
        )
    )

    monkeypatch.setattr("database.database.get_db", lambda: _FakeGenerator())

    assert runtime_module.AppRuntime.play_runtime_device_video(runtime, "Device A", "/tmp/a.mp4", True) is True
    assert runtime_module.AppRuntime.play_runtime_device_video(runtime, "Missing", "/tmp/a.mp4", True) is None


def test_app_runtime_persists_runtime_playback_progress(monkeypatch):
    from web.backend.services import app_runtime as runtime_module

    class _FakeGenerator:
        def __iter__(self):
            return self

        def __next__(self):
            return object()

        def close(self):
            return None

    db_device = SimpleNamespace(
        playback_position=None,
        playback_duration=None,
        playback_progress=None,
    )
    commits = []
    runtime = SimpleNamespace(
        build_device_service=lambda db: SimpleNamespace(
            db=SimpleNamespace(commit=lambda: commits.append("commit")),
            get_device_by_name=lambda device_name: db_device if device_name == "Device A" else None,
        )
    )

    monkeypatch.setattr("database.database.get_db", lambda: _FakeGenerator())

    assert runtime_module.AppRuntime.persist_runtime_playback_progress(runtime, "Device A", "00:00:05", "00:10:00", 1) is True
    assert db_device.playback_position == "00:00:05"
    assert db_device.playback_duration == "00:10:00"
    assert db_device.playback_progress == 1
    assert commits == ["commit"]
    assert runtime_module.AppRuntime.persist_runtime_playback_progress(runtime, "Missing", "00:00:05", "00:10:00", 1) is False


def test_app_runtime_get_devices_uses_inventory_service_fallback():
    devices = [SimpleNamespace(name="Device A"), SimpleNamespace(name="Device B")]
    runtime = SimpleNamespace(device_inventory_service=SimpleNamespace(list_devices=lambda: devices))

    from web.backend.services.app_runtime import AppRuntime

    assert AppRuntime.get_devices(runtime) == devices


def test_app_runtime_inventory_helpers_use_inventory_service():
    inventory_service = SimpleNamespace(
        items=lambda: [("Device A", SimpleNamespace(is_playing=True)), ("Device B", SimpleNamespace(is_playing=False))],
        values=lambda: [SimpleNamespace(is_playing=True), SimpleNamespace(is_playing=False)],
        devices={"Device A": object(), "Device B": object()},
    )
    runtime = SimpleNamespace(device_inventory_service=inventory_service)

    from web.backend.services.app_runtime import AppRuntime

    assert AppRuntime.get_device_items(runtime) == [("Device A", inventory_service.items()[0][1]), ("Device B", inventory_service.items()[1][1])]
    assert AppRuntime.get_device_count(runtime) == 2
    assert AppRuntime.get_playing_device_count(runtime) == 1


def test_app_runtime_lifecycle_helpers_use_lifecycle_service():
    calls = []
    device_entry = SimpleNamespace(name="Device A")
    lifecycle_service = SimpleNamespace(
        get_devices=lambda: calls.append("get_devices") or [device_entry],
        get_device=lambda device_name: calls.append(("get_device", device_name)) or {"device_name": device_name},
        register_device=lambda device_info: calls.append(("register", device_info)) or {"registered": device_info["device_name"]},
        unregister_device=lambda device_name: calls.append(("unregister", device_name)) or True,
        cleanup_device_state=lambda device_name: calls.append(("cleanup", device_name)),
    )
    runtime = SimpleNamespace(device_lifecycle_service=lifecycle_service)

    from web.backend.services.app_runtime import AppRuntime

    assert AppRuntime.get_devices(runtime) == [device_entry]
    assert AppRuntime.get_device(runtime, "Device A") == {"device_name": "Device A"}
    assert AppRuntime.register_device(runtime, {"device_name": "Device A"}) == {"registered": "Device A"}
    assert AppRuntime.unregister_device(runtime, "Device A") is True
    AppRuntime.cleanup_device_state(runtime, "Device A")

    assert calls == [
        "get_devices",
        ("get_device", "Device A"),
        ("register", {"device_name": "Device A"}),
        ("unregister", "Device A"),
        ("cleanup", "Device A"),
    ]


def test_app_runtime_update_device_status_uses_runtime_registry():
    calls = []

    class _Lock:
        def __enter__(self):
            calls.append("enter")

        def __exit__(self, exc_type, exc, tb):
            calls.append("exit")

    runtime = SimpleNamespace(
        device_state_lock=_Lock(),
        runtime_registry_service=SimpleNamespace(
            update_status=lambda **kwargs: calls.append(("update_status", kwargs))
        ),
    )

    from web.backend.services.app_runtime import AppRuntime

    AppRuntime.update_device_status(
        runtime,
        device_name="Device A",
        status="connected",
        is_playing=True,
        current_video="/tmp/a.mp4",
        error=None,
    )

    assert calls == [
        "enter",
        (
            "update_status",
            {
                "device_name": "Device A",
                "status": "connected",
                "is_playing": True,
                "current_video": "/tmp/a.mp4",
                "error": None,
            },
        ),
        "exit",
    ]


def test_app_runtime_update_device_playback_progress_uses_runtime_registry_and_device():
    calls = []
    device = SimpleNamespace(current_position=None, duration_formatted=None, playback_progress=None)
    runtime = SimpleNamespace(
        update_runtime_playback_progress=lambda device_name, position, duration, progress: calls.append(
            ("runtime_progress", device_name, position, duration, progress)
        ),
        get_device=lambda device_name: calls.append(("get_device", device_name)) or device,
    )

    from web.backend.services.app_runtime import AppRuntime

    AppRuntime.update_device_playback_progress(runtime, "Device A", "00:00:05", "00:01:00", 8)

    assert calls == [
        ("runtime_progress", "Device A", "00:00:05", "00:01:00", 8),
        ("get_device", "Device A"),
    ]
    assert device.current_position == "00:00:05"
    assert device.duration_formatted == "00:01:00"
    assert device.playback_progress == 8


def test_app_runtime_discover_dlna_devices_uses_discovery_controller():
    discovery = SimpleNamespace(
        discover_dlna_devices=lambda timeout=2.0: [{"friendly_name": "Device A", "timeout": timeout}]
    )
    runtime = SimpleNamespace(
        discovery_coordinator=discovery,
        device_manager=SimpleNamespace(discovery_coordinator=discovery),
        _get_discovery_controller=lambda: discovery,
    )

    from web.backend.services.app_runtime import AppRuntime

    assert AppRuntime.discover_dlna_devices(runtime, 3.5) == [{"friendly_name": "Device A", "timeout": 3.5}]


def test_app_runtime_save_devices_to_config_uses_inventory_service(tmp_path):
    config_path = tmp_path / "devices.json"
    runtime = SimpleNamespace(
        device_inventory_service=SimpleNamespace(
            values=lambda: [
                SimpleNamespace(device_info={"device_name": "Device A", "friendly_name": "Device A"}),
                SimpleNamespace(device_info={"device_name": "Device B", "friendly_name": "Device B"}),
            ]
        ),
        device_state_lock=None,
    )

    from web.backend.services.app_runtime import AppRuntime

    assert AppRuntime.save_devices_to_config(runtime, str(config_path)) is True
    assert config_path.exists()
    assert config_path.read_text().count("device_name") == 2


def test_app_runtime_get_serve_ip_uses_environment(monkeypatch):
    from web.backend.services.app_runtime import AppRuntime

    runtime = SimpleNamespace()
    monkeypatch.setenv("STREAMING_SERVE_IP", "192.168.1.50")

    assert AppRuntime.get_serve_ip(runtime) == "192.168.1.50"


def test_app_runtime_runtime_helpers_use_runtime_services():
    calls = []
    runtime = SimpleNamespace(
        runtime_playback_service=SimpleNamespace(
            auto_play_video=lambda device, video_path, loop=True, config=None: calls.append(
                ("auto_play_video", device, video_path, loop, config)
            )
            or True,
        ),
        device_manager=SimpleNamespace(),
        device_lifecycle_service=SimpleNamespace(
            cleanup_device_state=lambda device_name: calls.append(("cleanup_device_state", device_name))
        ),
        playback_intent_service=SimpleNamespace(
            get_assigned_video=lambda device_name: f"/tmp/{device_name}.mp4"
        ),
    )

    from web.backend.services.app_runtime import AppRuntime

    assert AppRuntime.auto_play_video(runtime, "device", "/tmp/test.mp4", loop=False, config={"x": 1}) is True
    AppRuntime.cleanup_device_state(runtime, "Device A")
    assigned = AppRuntime.get_assigned_video(runtime, "Device A")

    assert assigned == "/tmp/Device A.mp4"
    assert calls == [
        ("auto_play_video", "device", "/tmp/test.mp4", False, {"x": 1}),
        ("cleanup_device_state", "Device A"),
    ]


def test_app_runtime_auto_play_video_uses_runtime_playback_service():
    calls = []
    runtime = SimpleNamespace(
        runtime_playback_service=SimpleNamespace(
            auto_play_video=lambda device, video_path, loop=True, config=None: calls.append(
                (device, video_path, loop, config)
            )
            or True
        ),
        device_manager=SimpleNamespace(auto_play_video=lambda *args, **kwargs: False),
    )

    from web.backend.services.app_runtime import AppRuntime

    assert AppRuntime.auto_play_video(runtime, "device", "/tmp/test.mp4", loop=False, config={"x": 1}) is True
    assert calls == [("device", "/tmp/test.mp4", False, {"x": 1})]


def test_app_runtime_auto_play_video_builds_runtime_playback_service(monkeypatch):
    from web.backend.services import app_runtime as runtime_module

    calls = []

    class _FakeRuntimePlaybackService:
        def __init__(self, runtime):
            calls.append(("init", runtime))
            self.runtime = runtime

        def auto_play_video(self, device, video_path, loop=True, config=None):
            calls.append(("auto_play_video", device, video_path, loop, config))
            return True

    runtime = SimpleNamespace(device_manager=SimpleNamespace())

    monkeypatch.setattr(runtime_module, "RuntimePlaybackService", _FakeRuntimePlaybackService)

    assert runtime_module.AppRuntime.auto_play_video(
        runtime,
        "device",
        "/tmp/test.mp4",
        loop=False,
        config={"x": 1},
    ) is True
    assert isinstance(runtime.runtime_playback_service, _FakeRuntimePlaybackService)
    assert calls == [
        ("init", runtime),
        ("auto_play_video", "device", "/tmp/test.mp4", False, {"x": 1}),
    ]


def test_app_runtime_start_playback_health_check_uses_runtime_monitoring():
    calls = []
    runtime = SimpleNamespace(
        playback_monitoring_service=SimpleNamespace(
            start_health_check=lambda device_name, video_path: calls.append(
                (device_name, video_path)
            )
        )
    )

    from web.backend.services.app_runtime import AppRuntime

    AppRuntime.start_playback_health_check(runtime, "Device A", "/tmp/a.mp4")

    assert calls == [("Device A", "/tmp/a.mp4")]


def test_app_runtime_playback_monitoring_helpers_use_runtime_monitoring():
    calls = []
    runtime = SimpleNamespace(
        playback_monitoring_service=SimpleNamespace(
            stop_health_check=lambda device_name: calls.append(("stop", device_name)),
            track_playback_result=lambda device_name, video_path, success: calls.append(
                ("track", device_name, video_path, success)
            ),
            get_device_playback_stats=lambda device_name: {"device": device_name, "attempts": 2},
        )
    )

    from web.backend.services.app_runtime import AppRuntime

    AppRuntime.stop_playback_health_check(runtime, "Device A")
    AppRuntime.track_playback_result(runtime, "Device A", "/tmp/a.mp4", True)
    stats = AppRuntime.get_device_playback_stats(runtime, "Device A")

    assert calls == [
        ("stop", "Device A"),
        ("track", "Device A", "/tmp/a.mp4", True),
    ]
    assert stats == {"device": "Device A", "attempts": 2}


def test_app_runtime_handle_streaming_issue_ignores_internal_overlay_session():
    calls = []
    runtime = SimpleNamespace(
        get_device=lambda device_name: calls.append(("get_device", device_name)),
        get_device_items=lambda: [],
        device_state_lock=threading.RLock(),
        runtime_registry_service=SimpleNamespace(last_seen={}),
        recover_runtime_device=lambda device_name: calls.append(("recover", device_name)),
        playback_orchestrator=SimpleNamespace(
            handle_stalled_streaming_session=lambda session, device: calls.append(("orchestrate", session, device))
        ),
        update_device_status=lambda **kwargs: calls.append(("status", kwargs)),
    )
    session = SimpleNamespace(
        device_name="overlay-mapping",
        stream_type="overlay_mapping_stream",
        session_id="s1",
    )

    from web.backend.services.app_runtime import AppRuntime

    AppRuntime.handle_streaming_issue(runtime, session)

    assert calls == []


def test_app_runtime_handle_streaming_issue_recovers_and_restarts_stalled_session():
    calls = []
    device = SimpleNamespace(name="Device A")
    runtime = SimpleNamespace(
        get_device=lambda device_name: None,
        get_device_items=lambda: [("Device A", object())],
        device_state_lock=threading.RLock(),
        runtime_registry_service=SimpleNamespace(last_seen={"Device A": 0.0}),
        recover_runtime_device=lambda device_name: calls.append(("recover", device_name)) or device,
        playback_orchestrator=SimpleNamespace(
            handle_stalled_streaming_session=lambda session, target_device: calls.append(
                ("orchestrate", session.device_name, target_device.name)
            )
        ),
        update_device_status=lambda **kwargs: calls.append(("status", kwargs)),
    )
    session = SimpleNamespace(
        device_name="Device A",
        stream_type="device_stream",
        status="stalled",
        is_stalled=lambda inactivity_threshold=30.0: True,
    )

    from web.backend.services.app_runtime import AppRuntime

    AppRuntime.handle_streaming_issue(runtime, session)

    assert calls == [
        ("recover", "Device A"),
        ("orchestrate", "Device A", "Device A"),
    ]


def test_app_runtime_rebinds_streaming_health_handler():
    from web.backend.services import app_runtime as runtime_module

    calls = []
    legacy_handler = lambda session: None
    runtime = SimpleNamespace(
        streaming_registry=SimpleNamespace(
            unregister_health_check_handler=lambda handler: calls.append(("unregister", handler)),
            register_health_check_handler=lambda handler: calls.append(("register", handler)),
        ),
        legacy_streaming_issue_handler=legacy_handler,
        handle_streaming_issue=lambda session: None,
    )

    runtime_module._rebind_streaming_health_handler(runtime)

    assert calls == [
        ("unregister", legacy_handler),
        ("register", runtime.handle_streaming_issue),
    ]


def test_app_runtime_process_airplay_casting_plays_direct_url_first():
    calls = []
    device = SimpleNamespace(name="Device A")
    runtime = SimpleNamespace(
        get_device=lambda device_name: calls.append(("get_device", device_name)) or device,
        auto_play_video=lambda target, video_path, loop=True: calls.append(
            ("auto_play_video", target, video_path, loop)
        )
        or True,
        update_device_status=lambda **kwargs: calls.append(("update_device_status", kwargs)),
    )

    from web.backend.services.app_runtime import AppRuntime

    AppRuntime.process_airplay_casting(
        runtime,
        "Device A",
        {"airplay_url": "http://localhost:8000/overlay"},
    )

    assert calls == [
        ("get_device", "Device A"),
        ("auto_play_video", device, "http://localhost:8000/overlay", True),
        (
            "update_device_status",
            {
                "device_name": "Device A",
                "status": "connected",
                "is_playing": True,
                "current_video": "http://localhost:8000/overlay",
            },
        ),
    ]


def test_app_runtime_process_airplay_casting_uses_fallback_video(tmp_path):
    fallback_video = tmp_path / "fallback.mp4"
    fallback_video.write_text("x")

    calls = []
    device = SimpleNamespace(name="Device A")
    results = iter([False, True])
    runtime = SimpleNamespace(
        get_device=lambda device_name: device,
        auto_play_video=lambda target, video_path, loop=True: calls.append(
            ("auto_play_video", video_path, loop)
        )
        or next(results),
        update_device_status=lambda **kwargs: calls.append(("update_device_status", kwargs)),
    )

    from web.backend.services.app_runtime import AppRuntime

    AppRuntime.process_airplay_casting(
        runtime,
        "Device A",
        {
            "airplay_url": "http://localhost:8000/overlay",
            "video_file": str(fallback_video),
        },
    )

    assert calls == [
        ("auto_play_video", "http://localhost:8000/overlay", True),
        ("auto_play_video", str(fallback_video), True),
        (
            "update_device_status",
            {
                "device_name": "Device A",
                "status": "connected",
                "is_playing": True,
                "current_video": str(fallback_video),
            },
        ),
    ]


def test_app_runtime_trigger_overlay_sync_posts_request(monkeypatch):
    calls = []

    class _Response:
        status_code = 200

    monkeypatch.setattr(
        "web.backend.services.app_runtime.requests.post",
        lambda url, params=None, timeout=None: calls.append((url, params, timeout)) or _Response(),
    )

    from web.backend.services.app_runtime import AppRuntime

    AppRuntime.trigger_overlay_sync(SimpleNamespace(), "video.mp4")

    assert calls == [
        (
            "http://localhost:8000/api/overlay/sync",
            {"triggered_by": "dlna_auto_play", "video_name": "video.mp4"},
            2,
        )
    ]
