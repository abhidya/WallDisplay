import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from types import ModuleType


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _ensure_package(name, path):
    module = sys.modules.get(name)
    if module is None:
        module = ModuleType(name)
        module.__path__ = [str(path)]
        sys.modules[name] = module
    return module


def _load_module(name, path):
    module = sys.modules.get(name)
    if module is not None:
        return module
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_ensure_package("core", BACKEND_ROOT / "core")
_ensure_package("core.renderer_service", BACKEND_ROOT / "core" / "renderer_service")
_ensure_package("core.renderer_service.sender", BACKEND_ROOT / "core" / "renderer_service" / "sender")
_ensure_package("discovery", BACKEND_ROOT / "discovery")
_ensure_package("services", BACKEND_ROOT / "services")

_load_module("core.renderer_service.sender.base", BACKEND_ROOT / "core" / "renderer_service" / "sender" / "base.py")
discovery_base = _load_module("discovery.base", BACKEND_ROOT / "discovery" / "base.py")
airplay_module = _load_module(
    "core.renderer_service.sender.airplay",
    BACKEND_ROOT / "core" / "renderer_service" / "sender" / "airplay.py",
)
automation_module = _load_module(
    "services.airplay_projection_automation_service",
    BACKEND_ROOT / "services" / "airplay_projection_automation_service.py",
)

AirPlaySender = airplay_module.AirPlaySender
CastingMethod = discovery_base.CastingMethod
Device = discovery_base.Device
AirPlayProjectionAutomationService = automation_module.AirPlayProjectionAutomationService
load_airplay_projection_automation_config = automation_module.load_airplay_projection_automation_config


def test_airplay_sender_connect_passes_display_mode(monkeypatch):
    calls = []

    def fake_run(cmd, stdout=None, stderr=None, timeout=None):
        calls.append(
            {
                "cmd": cmd,
                "stdout": stdout,
                "stderr": stderr,
                "timeout": timeout,
            }
        )
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(airplay_module.subprocess, "run", fake_run)

    sender = AirPlaySender({"script_path": "auto", "connect_timeout": 7, "display_mode": "mirror"})

    assert sender.connect("Hccast-3ADE76", display_mode="extend") is True
    assert sender.connected is True
    assert calls == [
        {
            "cmd": [
                "osascript",
                sender.applescript_path,
                "start",
                "Hccast-3ADE76",
                "extend",
            ],
            "stdout": -1,
            "stderr": -1,
            "timeout": 7,
        }
    ]


def test_load_airplay_projection_automation_config_uses_projector_defaults():
    renderer_service = SimpleNamespace(
        config={
            "senders": {
                "airplay": {
                    "script_path": "auto",
                    "connect_timeout": 9,
                }
            },
            "renderers": {
                "chrome-visible": {
                    "path": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                    "args": ["--disable-gpu"],
                }
            },
            "projectors": {
                "proj-hccast": {
                    "target_name": "Hccast-3ADE76",
                }
            },
            "automations": {
                "airplay_hccast_overlay": {
                    "enabled": True,
                    "projector_id": "proj-hccast",
                    "overlay_config_id": 2,
                    "display_mode": "separate",
                }
            },
        }
    )

    config = load_airplay_projection_automation_config(lambda: renderer_service)

    assert config.projector_id == "proj-hccast"
    assert config.target_name == "Hccast-3ADE76"
    assert config.target_name_pattern == "Hccast-3ADE76"
    assert config.display_mode == "extend"
    assert config.overlay_config_id == 2
    assert config.build_overlay_url() == "http://localhost:8000/backend-static/overlay_window.html?config_id=2&controls=hidden"
    assert "--disable-gpu" in config.chrome_args
    assert "--start-fullscreen" in config.chrome_args
    assert config.airplay_sender_config["connect_timeout"] == 9


def test_airplay_projection_automation_service_activates_and_tears_down(monkeypatch, tmp_path):
    device = Device(
        id="airplay-hccast",
        name="Hccast-3ADE76",
        friendly_name="Living Room HCCast",
        casting_method=CastingMethod.AIRPLAY,
        hostname="192.168.1.50",
        port=7000,
    )
    callbacks = []
    sender_events = []
    overlay_launches = []

    class FakeThread:
        def __init__(self, target=None, args=(), daemon=None, name=None):
            self.target = target
            self.args = args

        def start(self):
            self.target(*self.args)

    class FakeProcess:
        def __init__(self):
            self.running = True
            self.terminated = False

        def poll(self):
            return None if self.running else 0

        def terminate(self):
            self.running = False
            self.terminated = True

        def wait(self, timeout=None):
            self.running = False
            return 0

        def kill(self):
            self.running = False

    class FakeSender:
        def __init__(self, config, logger):
            sender_events.append(("init", config.copy()))
            self.connected = False

        def connect(self, target_id, display_mode=None):
            sender_events.append(("connect", target_id, display_mode))
            self.connected = True
            return True

        def disconnect(self):
            sender_events.append(("disconnect",))
            self.connected = False
            return True

    class FakeDiscoveryManager:
        def register_callback(self, callback):
            callbacks.append(callback)

        def unregister_callback(self, callback):
            callbacks.remove(callback)

        def get_devices_by_method(self, method, online_only=True):
            assert method == CastingMethod.AIRPLAY
            assert online_only is True
            return [device]

    renderer_service = SimpleNamespace(
        config={
            "senders": {
                "airplay": {
                    "script_path": "auto",
                    "connect_timeout": 9,
                }
            },
            "renderers": {
                "chrome-visible": {
                    "path": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                    "args": ["--test-flag"],
                }
            },
            "projectors": {
                "proj-hccast": {
                    "target_name": "Hccast-3ADE76",
                }
            },
            "automations": {
                "airplay_hccast_overlay": {
                    "enabled": True,
                    "projector_id": "proj-hccast",
                    "overlay_config_id": 2,
                    "display_mode": "extend",
                    "cooldown_seconds": 1,
                }
            },
        }
    )

    monkeypatch.setattr(automation_module.threading, "Thread", FakeThread)
    monkeypatch.setattr(automation_module, "AirPlaySender", FakeSender)

    service = AirPlayProjectionAutomationService(
        FakeDiscoveryManager(),
        renderer_service_getter=lambda: renderer_service,
    )

    fake_process = FakeProcess()
    profile_dir = tmp_path / "chrome-profile"
    profile_dir.mkdir()

    monkeypatch.setattr(service, "_get_display_snapshot", lambda: [])
    monkeypatch.setattr(
        service,
        "_wait_for_target_display_bounds",
        lambda baseline, config: {"x": 1440, "y": 0, "width": 1920, "height": 1080},
    )
    monkeypatch.setattr(
        service,
        "_launch_overlay_window",
        lambda overlay_url, display_bounds, config: overlay_launches.append(
            {
                "url": overlay_url,
                "display_bounds": display_bounds,
                "args": list(config.chrome_args),
            }
        )
        or (fake_process, str(profile_dir)),
    )

    service.start()

    status = service.get_status()
    assert len(callbacks) == 1
    assert status["running"] is True
    assert status["active_device_id"] == "airplay-hccast"
    assert status["active_device_name"] == "Hccast-3ADE76"
    assert status["chrome_running"] is True
    assert overlay_launches == [
        {
            "url": "http://localhost:8000/backend-static/overlay_window.html?config_id=2&controls=hidden",
            "display_bounds": {"x": 1440, "y": 0, "width": 1920, "height": 1080},
            "args": ["--test-flag", "--new-window", "--no-first-run", "--disable-session-crashed-bubble", "--disable-infobars", "--start-fullscreen"],
        }
    ]
    assert sender_events[:2] == [
        ("init", {"script_path": "auto", "connect_timeout": 9, "display_mode": "extend"}),
        ("connect", "Hccast-3ADE76", "extend"),
    ]

    callbacks[0]("device_lost", device)

    stopped_status = service.get_status()
    assert stopped_status["active_device_id"] is None
    assert stopped_status["chrome_running"] is False
    assert fake_process.terminated is True
    assert ("disconnect",) in sender_events
    assert not profile_dir.exists()

    service.stop()
    assert callbacks == []
