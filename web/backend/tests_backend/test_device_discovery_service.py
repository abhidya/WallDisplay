import json
from types import SimpleNamespace

from web.backend.services.device_discovery_service import DeviceDiscoveryService


class _FakeQuery:
    def __init__(self, devices):
        self._devices = devices

    def all(self):
        return self._devices


class _FakeDB:
    def __init__(self, devices):
        self._devices = devices
        self.rollback_count = 0

    def query(self, _model):
        return _FakeQuery(self._devices)

    def rollback(self):
        self.rollback_count += 1


def test_sync_device_status_with_discovery_preserves_playing_signals():
    devices = [
        SimpleNamespace(name="Device A", is_playing=False, current_video=None),
        SimpleNamespace(name="Device B", is_playing=True, current_video=None),
        SimpleNamespace(name="Device C", is_playing=False, current_video="/tmp/c.mp4"),
    ]
    status_updates = []

    runtime_sync_service = SimpleNamespace(
        get_core_device=lambda device_name: (
            SimpleNamespace(is_playing=True) if device_name == "Device A" else None
        )
    )
    service = DeviceDiscoveryService(
        db=_FakeDB(devices),
        runtime=SimpleNamespace(),
        runtime_sync_service=runtime_sync_service,
        get_device_by_name=lambda device_name: None,
        update_device_status=lambda device_name, status, is_playing=False: status_updates.append(
            (device_name, status, is_playing)
        ),
    )

    service.sync_device_status_with_discovery({"Device A", "Device B", "Device C"})

    assert status_updates == [
        ("Device A", "connected", True),
        ("Device B", "connected", True),
        ("Device C", "connected", True),
    ]


def test_sync_device_status_with_discovery_marks_missing_devices_disconnected():
    devices = [SimpleNamespace(name="Missing Device", is_playing=False, current_video=None)]
    status_updates = []

    service = DeviceDiscoveryService(
        db=_FakeDB(devices),
        runtime=SimpleNamespace(),
        runtime_sync_service=SimpleNamespace(get_core_device=lambda device_name: None),
        get_device_by_name=lambda device_name: None,
        update_device_status=lambda device_name, status, is_playing=False: status_updates.append(
            (device_name, status, is_playing)
        ),
    )

    service.sync_device_status_with_discovery(set())

    assert status_updates == [("Missing Device", "disconnected", False)]


def test_load_devices_from_config_resolves_relative_video_paths(tmp_path):
    config_path = tmp_path / "devices.json"
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    video_path = media_dir / "clip.mp4"
    video_path.write_text("test")

    config_path.write_text(
        json.dumps(
            [
                {
                    "name": "Device A",
                    "video_file": "media/clip.mp4",
                    "config": {"priority": 50},
                }
            ]
        )
    )

    registered = []
    db_device = SimpleNamespace(
        name="Device A",
        type="dlna",
        hostname="",
        action_url="",
        friendly_name="Device A",
        manufacturer="",
        location="",
        status="connected",
        is_playing=False,
        config=None,
        to_dict=lambda: {"name": "Device A"},
    )

    class _ConfigDB:
        def __init__(self):
            self.added = []
            self.commits = 0

        def add(self, obj):
            self.added.append(obj)

        def commit(self):
            self.commits += 1

        def refresh(self, _obj):
            return None

        def rollback(self):
            return None

    db = _ConfigDB()
    service = DeviceDiscoveryService(
        db=db,
        runtime=SimpleNamespace(save_devices_to_config=lambda config_file: True),
        runtime_sync_service=SimpleNamespace(
            register_and_update=lambda device_info, status: registered.append((device_info, status))
        ),
        get_device_by_name=lambda device_name: None,
        update_device_status=lambda *_args, **_kwargs: True,
    )

    class _FakeDeviceModel:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

        def to_dict(self):
            return {
                "name": self.name,
                "status": self.status,
                "config": self.config,
            }

    import web.backend.services.device_discovery_service as discovery_module

    original_device_model = discovery_module.DeviceModel
    discovery_module.DeviceModel = _FakeDeviceModel
    try:
        result = service.load_devices_from_config(str(config_path))
    finally:
        discovery_module.DeviceModel = original_device_model

    assert len(result) == 1
    assert result[0]["name"] == "Device A"
    assert result[0]["status"] == "disconnected"
    assert result[0]["config"] == {"priority": 50}
    assert registered[0][0]["video_file"] == str(video_path.resolve())
    assert registered[0][1] == "disconnected"
