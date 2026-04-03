import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlencode

from discovery.base import CastingMethod, Device

try:
    from Quartz import CGGetActiveDisplayList, CGDisplayBounds, CGMainDisplayID

    QUARTZ_AVAILABLE = True
except ImportError:
    QUARTZ_AVAILABLE = False

from core.renderer_service.sender.airplay import AirPlaySender

logger = logging.getLogger(__name__)


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_display_mode(value: Any) -> str:
    normalized = str(value or "extend").strip().lower()
    if normalized in {"extend", "extended", "separate", "separate_display"}:
        return "extend"
    if normalized in {"mirror", "mirroring"}:
        return "mirror"
    return "extend"


@dataclass
class AirPlayProjectionAutomationConfig:
    enabled: bool = True
    projector_id: str = "proj-hccast"
    target_name: str = ""
    target_name_pattern: str = "hccast"
    overlay_config_id: int = 2
    overlay_base_url: str = "http://localhost:8000"
    controls_hidden: bool = True
    display_mode: str = "extend"
    cooldown_seconds: int = 15
    display_wait_seconds: int = 12
    launch_stabilization_seconds: float = 1.5
    chrome_path: str = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    chrome_args: list[str] = field(default_factory=list)
    airplay_sender_config: Dict[str, Any] = field(default_factory=dict)

    def matches_device(self, device: Device) -> bool:
        candidate_name = str(device.name or "").strip().lower()
        friendly_name = str(device.friendly_name or "").strip().lower()
        exact_name = str(self.target_name or "").strip().lower()
        pattern = str(self.target_name_pattern or "").strip().lower()

        if exact_name and (candidate_name == exact_name or friendly_name == exact_name):
            return True

        if pattern and (pattern in candidate_name or pattern in friendly_name):
            return True

        return False

    def build_overlay_url(self) -> str:
        base_url = self.overlay_base_url.rstrip("/")
        query = {
            "config_id": self.overlay_config_id,
        }
        if self.controls_hidden:
            query["controls"] = "hidden"
        return f"{base_url}/backend-static/overlay_window.html?{urlencode(query)}"


def load_airplay_projection_automation_config(
    renderer_service_getter: Optional[Callable[[], Any]] = None,
) -> AirPlayProjectionAutomationConfig:
    if renderer_service_getter is None:
        from routers.renderer_router import get_renderer_service

        renderer_service_getter = get_renderer_service

    renderer_service = renderer_service_getter()
    renderer_config = getattr(renderer_service, "config", {}) or {}
    automation_config = (renderer_config.get("automations") or {}).get("airplay_hccast_overlay", {})
    projector_id = str(automation_config.get("projector_id") or "proj-hccast")
    projector_config = (renderer_config.get("projectors") or {}).get(projector_id, {})
    chrome_config = (
        (renderer_config.get("renderers") or {}).get("chrome-visible")
        or (renderer_config.get("renderers") or {}).get("chrome")
        or {}
    )
    sender_config = dict((renderer_config.get("senders") or {}).get("airplay", {}) or {})

    target_name = str(automation_config.get("target_name") or projector_config.get("target_name") or "").strip()
    target_pattern = str(
        automation_config.get("target_name_pattern")
        or target_name
        or "hccast"
    ).strip()

    chrome_args = list(chrome_config.get("args") or [])
    if "--new-window" not in chrome_args:
        chrome_args.append("--new-window")
    if "--no-first-run" not in chrome_args:
        chrome_args.append("--no-first-run")
    if "--disable-session-crashed-bubble" not in chrome_args:
        chrome_args.append("--disable-session-crashed-bubble")
    if "--disable-infobars" not in chrome_args:
        chrome_args.append("--disable-infobars")
    if "--start-fullscreen" not in chrome_args:
        chrome_args.append("--start-fullscreen")

    overlay_base_url = str(
        automation_config.get("overlay_base_url")
        or os.environ.get("NANODLNA_AIRPLAY_AUTOMATION_BASE_URL")
        or "http://localhost:8000"
    ).strip()

    return AirPlayProjectionAutomationConfig(
        enabled=_coerce_bool(automation_config.get("enabled"), True),
        projector_id=projector_id,
        target_name=target_name,
        target_name_pattern=target_pattern,
        overlay_config_id=_coerce_int(automation_config.get("overlay_config_id"), 2),
        overlay_base_url=overlay_base_url,
        controls_hidden=_coerce_bool(automation_config.get("controls_hidden"), True),
        display_mode=_normalize_display_mode(automation_config.get("display_mode")),
        cooldown_seconds=max(1, _coerce_int(automation_config.get("cooldown_seconds"), 15)),
        display_wait_seconds=max(1, _coerce_int(automation_config.get("display_wait_seconds"), 12)),
        launch_stabilization_seconds=max(
            0.0,
            float(automation_config.get("launch_stabilization_seconds") or 1.5),
        ),
        chrome_path=str(chrome_config.get("path") or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        chrome_args=chrome_args,
        airplay_sender_config=sender_config,
    )


class AirPlayProjectionAutomationService:
    def __init__(
        self,
        discovery_manager: Any,
        renderer_service_getter: Optional[Callable[[], Any]] = None,
        logger_: Optional[logging.Logger] = None,
    ):
        self.discovery_manager = discovery_manager
        self.renderer_service_getter = renderer_service_getter
        self.logger = logger_ or logging.getLogger(__name__)
        self._lock = threading.RLock()
        self._callback_registered = False
        self._running = False
        self._active_device_id: Optional[str] = None
        self._active_device_name: Optional[str] = None
        self._active_overlay_url: Optional[str] = None
        self._last_activation_attempt_at = 0.0
        self._chrome_process: Optional[subprocess.Popen] = None
        self._chrome_profile_dir: Optional[str] = None
        self._airplay_sender: Optional[AirPlaySender] = None

    def start(self) -> None:
        config = self._load_config()
        if not config.enabled:
            self.logger.info("AirPlay projection automation is disabled")
            return

        with self._lock:
            if self._callback_registered:
                return
            self.discovery_manager.register_callback(self._handle_discovery_event)
            self._callback_registered = True
            self._running = True

        for device in self.discovery_manager.get_devices_by_method(CastingMethod.AIRPLAY, online_only=True):
            self._handle_discovery_event("device_discovered", device)

    def stop(self) -> None:
        with self._lock:
            self._running = False
            if self._callback_registered:
                self.discovery_manager.unregister_callback(self._handle_discovery_event)
                self._callback_registered = False
            self._stop_active_session_locked()

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "active_device_id": self._active_device_id,
                "active_device_name": self._active_device_name,
                "active_overlay_url": self._active_overlay_url,
                "chrome_running": bool(self._chrome_process and self._chrome_process.poll() is None),
            }

    def _load_config(self) -> AirPlayProjectionAutomationConfig:
        return load_airplay_projection_automation_config(self.renderer_service_getter)

    def _handle_discovery_event(self, event_type: str, device: Any) -> None:
        if not isinstance(device, Device):
            return
        if device.casting_method != CastingMethod.AIRPLAY:
            return

        config = self._load_config()
        if not config.enabled or not config.matches_device(device):
            return

        if event_type == "device_lost":
            with self._lock:
                if device.id == self._active_device_id:
                    self.logger.info("Active AirPlay target %s disappeared; tearing down automation", device.name)
                    self._stop_active_session_locked()
            return

        if event_type != "device_discovered":
            return

        worker = threading.Thread(
            target=self._activate_for_device,
            args=(device,),
            daemon=True,
            name=f"airplay-automation-{device.id}",
        )
        worker.start()

    def _activate_for_device(self, device: Device) -> None:
        config = self._load_config()
        if not config.enabled or not config.matches_device(device):
            return

        with self._lock:
            if not self._running:
                return

            if (
                self._active_device_id == device.id
                and self._chrome_process is not None
                and self._chrome_process.poll() is None
            ):
                return

            now = time.monotonic()
            if now - self._last_activation_attempt_at < config.cooldown_seconds:
                return
            self._last_activation_attempt_at = now
            self._stop_active_session_locked()

        baseline_displays = self._get_display_snapshot()
        sender_config = dict(config.airplay_sender_config)
        sender_config["display_mode"] = config.display_mode
        sender = AirPlaySender(sender_config, self.logger)
        if not sender.connect(device.name, display_mode=config.display_mode):
            self.logger.error("Failed to connect AirPlay automation target %s", device.name)
            return

        display_bounds = self._wait_for_target_display_bounds(baseline_displays, config)
        overlay_url = config.build_overlay_url()
        launch_result = self._launch_overlay_window(overlay_url, display_bounds, config)
        if launch_result is None:
            self.logger.error("Failed to launch overlay window for %s", device.name)
            sender.disconnect()
            return

        chrome_process, chrome_profile_dir = launch_result
        with self._lock:
            self._airplay_sender = sender
            self._chrome_process = chrome_process
            self._chrome_profile_dir = chrome_profile_dir
            self._active_device_id = device.id
            self._active_device_name = device.name
            self._active_overlay_url = overlay_url

    def _launch_overlay_window(
        self,
        overlay_url: str,
        display_bounds: Optional[Dict[str, int]],
        config: AirPlayProjectionAutomationConfig,
    ) -> Optional[tuple[subprocess.Popen, str]]:
        profile_dir = tempfile.mkdtemp(prefix="airplay_overlay_")
        cmd = [config.chrome_path]
        cmd.extend(config.chrome_args)
        cmd.append(f"--user-data-dir={profile_dir}")
        if display_bounds:
            cmd.append(f"--window-position={display_bounds['x']},{display_bounds['y']}")
            cmd.append(f"--window-size={display_bounds['width']},{display_bounds['height']}")
        cmd.append(overlay_url)

        try:
            chrome_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(config.launch_stabilization_seconds)
            if chrome_process.poll() is not None:
                shutil.rmtree(profile_dir, ignore_errors=True)
                self.logger.error("Chrome exited immediately while launching overlay automation")
                return None
            self.logger.info("Launched overlay automation window: %s", overlay_url)
            return chrome_process, profile_dir
        except Exception as exc:
            shutil.rmtree(profile_dir, ignore_errors=True)
            self.logger.error("Error launching overlay automation window: %s", exc)
            return None

    def _get_display_snapshot(self) -> list[Dict[str, int]]:
        if not QUARTZ_AVAILABLE:
            return []

        max_displays = 16
        active_displays, _, err = CGGetActiveDisplayList(max_displays, None, None)
        if err != 0:
            return []

        main_display_id = CGMainDisplayID()
        snapshot = []
        for display_id in active_displays:
            bounds = CGDisplayBounds(display_id)
            snapshot.append(
                {
                    "id": int(display_id),
                    "x": int(bounds.origin.x),
                    "y": int(bounds.origin.y),
                    "width": int(bounds.size.width),
                    "height": int(bounds.size.height),
                    "is_primary": int(display_id) == int(main_display_id),
                }
            )
        snapshot.sort(key=lambda item: (item["is_primary"], item["x"], item["y"]))
        return snapshot

    def _wait_for_target_display_bounds(
        self,
        baseline_displays: list[Dict[str, int]],
        config: AirPlayProjectionAutomationConfig,
    ) -> Optional[Dict[str, int]]:
        deadline = time.monotonic() + config.display_wait_seconds
        baseline_ids = {display["id"] for display in baseline_displays}
        fallback_display = self._choose_non_primary_display(baseline_displays)

        while time.monotonic() < deadline:
            current_displays = self._get_display_snapshot()
            new_displays = [display for display in current_displays if display["id"] not in baseline_ids]
            if new_displays:
                return self._choose_non_primary_display(new_displays) or new_displays[-1]

            candidate = self._choose_non_primary_display(current_displays)
            if candidate and len(current_displays) > len(baseline_displays):
                return candidate
            time.sleep(0.5)

        return self._choose_non_primary_display(self._get_display_snapshot()) or fallback_display

    @staticmethod
    def _choose_non_primary_display(displays: list[Dict[str, int]]) -> Optional[Dict[str, int]]:
        secondary_displays = [display for display in displays if not display.get("is_primary")]
        if not secondary_displays:
            return None
        secondary_displays.sort(key=lambda item: (item["x"], item["y"], item["width"] * item["height"]))
        return secondary_displays[-1]

    def _stop_active_session_locked(self) -> None:
        chrome_process = self._chrome_process
        chrome_profile_dir = self._chrome_profile_dir
        airplay_sender = self._airplay_sender

        self._chrome_process = None
        self._chrome_profile_dir = None
        self._airplay_sender = None
        self._active_device_id = None
        self._active_device_name = None
        self._active_overlay_url = None

        if chrome_process is not None and chrome_process.poll() is None:
            chrome_process.terminate()
            try:
                chrome_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                chrome_process.kill()
                chrome_process.wait(timeout=5)

        if chrome_profile_dir:
            shutil.rmtree(chrome_profile_dir, ignore_errors=True)

        if airplay_sender is not None:
            airplay_sender.disconnect()
