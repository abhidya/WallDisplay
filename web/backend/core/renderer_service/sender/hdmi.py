"""
HDMI/local-display sender for projector output.

HDMI is treated as a local display surface. The adapter can detect whether the
OS still exposes a target display and whether the launched browser is alive, but
it cannot know lamp power without external hardware.
"""

import ctypes
import logging
import os
import platform
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

from .base import Sender


@dataclass
class DisplayInfo:
    id: str
    index: int
    name: str
    x: int
    y: int
    width: int
    height: int
    is_primary: bool
    attached: bool = True
    device_name: Optional[str] = None

    @classmethod
    def fallback(cls) -> "DisplayInfo":
        return cls(
            id="hdmi_display_0",
            index=0,
            name="Primary display",
            x=0,
            y=0,
            width=1920,
            height=1080,
            is_primary=True,
            attached=True,
            device_name=None,
        )

    @classmethod
    def from_mapping(cls, value: Dict) -> "DisplayInfo":
        return cls(
            id=str(value.get("id") or value.get("device_name") or f"hdmi_display_{value.get('index', 0)}"),
            index=int(value.get("index", 0)),
            name=str(value.get("name") or value.get("device_name") or f"Display {int(value.get('index', 0)) + 1}"),
            x=int(value.get("x", 0)),
            y=int(value.get("y", 0)),
            width=int(value.get("width", 1920)),
            height=int(value.get("height", 1080)),
            is_primary=bool(value.get("is_primary", value.get("primary", False))),
            attached=bool(value.get("attached", True)),
            device_name=value.get("device_name"),
        )

    def to_dict(self) -> Dict:
        return asdict(self)


class HDMISender(Sender):
    """Display content on a projector attached as a local HDMI display."""

    VALID_POWER_STATES = {"unknown", "manual_on", "manual_off"}
    VALID_CONNECTION_STATES = {"attached", "detached", "unresponsive"}
    VALID_PROJECTION_STATES = {"idle", "launching", "projecting", "stale"}

    def __init__(self, config: Dict, logger: Optional[logging.Logger] = None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.browser_path = config.get("browser_path", "")
        self.default_display = str(config.get("default_display", 0))
        self.kiosk_mode = bool(config.get("kiosk_mode", True))
        self.heartbeat_timeout_seconds = float(config.get("heartbeat_timeout_seconds", 15))
        self.use_isolated_profile = bool(config.get("isolated_profile", True))

        self.target_id: Optional[str] = None
        self.display: Optional[DisplayInfo] = None
        self.process: Optional[subprocess.Popen] = None
        self.content_url: Optional[str] = None
        self.connected = False
        self.connection_state = "detached"
        self.projection_state = "idle"
        self.power_state = config.get("power_state", "unknown")
        if self.power_state not in self.VALID_POWER_STATES:
            self.power_state = "unknown"
        self.last_error: Optional[str] = None
        self.last_heartbeat_at: Optional[float] = None
        self.started_at: Optional[float] = None
        self.profile_dir: Optional[str] = None
        self.expect_heartbeat = False

    @classmethod
    def discover_displays(cls) -> List[Dict]:
        displays: List[DisplayInfo] = []
        if platform.system() == "Windows":
            displays = cls._discover_windows()
        if not displays:
            displays = cls._discover_with_screeninfo()
        if not displays:
            displays = [DisplayInfo.fallback()]
        return [display.to_dict() for display in displays]

    @staticmethod
    def _discover_windows() -> List[DisplayInfo]:
        if platform.system() != "Windows":
            return []

        try:
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            MONITORINFOF_PRIMARY = 1

            class MONITORINFOEXW(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD),
                    ("szDevice", ctypes.c_wchar * 32),
                ]

            monitors: List[DisplayInfo] = []

            def _friendly_name(device_name: str, index: int) -> str:
                try:
                    class DISPLAY_DEVICEW(ctypes.Structure):
                        _fields_ = [
                            ("cb", wintypes.DWORD),
                            ("DeviceName", ctypes.c_wchar * 32),
                            ("DeviceString", ctypes.c_wchar * 128),
                            ("StateFlags", wintypes.DWORD),
                            ("DeviceID", ctypes.c_wchar * 128),
                            ("DeviceKey", ctypes.c_wchar * 128),
                        ]

                    display_device = DISPLAY_DEVICEW()
                    display_device.cb = ctypes.sizeof(DISPLAY_DEVICEW)
                    if user32.EnumDisplayDevicesW(device_name, 0, ctypes.byref(display_device), 0):
                        label = display_device.DeviceString.strip()
                        if label:
                            return f"{device_name} ({label})"
                except Exception:
                    pass
                return device_name or f"Display {index + 1}"

            MONITORENUMPROC = ctypes.WINFUNCTYPE(
                wintypes.BOOL,
                wintypes.HANDLE,
                wintypes.HDC,
                ctypes.POINTER(wintypes.RECT),
                wintypes.LPARAM,
            )

            def _callback(hmonitor, _hdc, _rect, _data):
                info = MONITORINFOEXW()
                info.cbSize = ctypes.sizeof(MONITORINFOEXW)
                if not user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
                    return True

                index = len(monitors)
                device_name = info.szDevice.strip()
                left = int(info.rcMonitor.left)
                top = int(info.rcMonitor.top)
                right = int(info.rcMonitor.right)
                bottom = int(info.rcMonitor.bottom)
                monitors.append(
                    DisplayInfo(
                        id=device_name or f"hdmi_display_{index}",
                        index=index,
                        name=_friendly_name(device_name, index),
                        x=left,
                        y=top,
                        width=max(0, right - left),
                        height=max(0, bottom - top),
                        is_primary=bool(info.dwFlags & MONITORINFOF_PRIMARY),
                        attached=True,
                        device_name=device_name or None,
                    )
                )
                return True

            if not user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(_callback), 0):
                return []
            return monitors
        except Exception:
            return []

    @staticmethod
    def _discover_with_screeninfo() -> List[DisplayInfo]:
        try:
            import screeninfo
        except ImportError:
            return []

        displays: List[DisplayInfo] = []
        try:
            for index, monitor in enumerate(screeninfo.get_monitors()):
                monitor_name = getattr(monitor, "name", None) or f"Display {index + 1}"
                displays.append(
                    DisplayInfo(
                        id=str(monitor_name or f"hdmi_display_{index}"),
                        index=index,
                        name=str(monitor_name),
                        x=int(getattr(monitor, "x", 0)),
                        y=int(getattr(monitor, "y", 0)),
                        width=int(getattr(monitor, "width", 1920)),
                        height=int(getattr(monitor, "height", 1080)),
                        is_primary=bool(getattr(monitor, "is_primary", index == 0)),
                        attached=True,
                        device_name=str(monitor_name) if monitor_name else None,
                    )
                )
        except Exception:
            return []
        return displays

    def connect(self, target_id: str) -> bool:
        self.target_id = str(target_id or self.default_display)
        self.display = self._resolve_display(self.target_id)
        if not self.display:
            self.connected = False
            self.connection_state = "detached"
            self.projection_state = "stale"
            self.last_error = f"Display target not found: {self.target_id}"
            self.logger.error(self.last_error)
            return False

        self.connected = True
        self.connection_state = "attached"
        if self.projection_state == "stale":
            self.projection_state = "idle"
        self.last_error = None
        self.logger.info("Connected HDMI sender to %s", self.display.name)
        return True

    def disconnect(self) -> bool:
        self._stop_process()
        self.connected = False
        self.connection_state = "detached"
        self.display = None
        self.target_id = None
        return True

    def send_content(self, content_url: str) -> bool:
        if not self.connected or not self.display:
            self.last_error = "Cannot start HDMI output before a display is connected"
            self.connection_state = "unresponsive"
            self.projection_state = "stale"
            return False

        if self.process and self.process.poll() is None:
            self._stop_process()

        browser_cmd = self._get_browser_command()
        if not browser_cmd:
            self.last_error = "No supported browser was found for HDMI output"
            self.connection_state = "unresponsive"
            self.projection_state = "stale"
            return False

        self.projection_state = "launching"
        try:
            cmd = self._prepare_browser_command(browser_cmd, content_url)
            self.logger.info("Launching HDMI browser: %s", " ".join(cmd))
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            time.sleep(0.5)
            if self.process.poll() is not None:
                stderr = self.process.stderr.read().decode("utf-8", errors="replace")
                self.last_error = f"Browser exited immediately: {stderr}".strip()
                self.connection_state = "unresponsive"
                self.projection_state = "stale"
                return False

            self.content_url = content_url
            self.started_at = time.time()
            self.last_heartbeat_at = None
            self.expect_heartbeat = self._content_supports_heartbeat(content_url)
            self.connection_state = "attached"
            self.projection_state = "projecting"
            self.last_error = None
            return True
        except Exception as exc:
            self.last_error = str(exc)
            self.connection_state = "unresponsive"
            self.projection_state = "stale"
            self.logger.error("Error launching HDMI content: %s", exc)
            return False

    def record_heartbeat(self) -> None:
        self.last_heartbeat_at = time.time()
        if self.is_process_running():
            self.connection_state = "attached"
            self.projection_state = "projecting"

    def set_power_state(self, power_state: str) -> None:
        if power_state not in self.VALID_POWER_STATES:
            raise ValueError(f"Invalid HDMI power state: {power_state}")
        self.power_state = power_state

    def is_connected(self) -> bool:
        if not self.connected:
            return False
        if not self._resolve_display(self.target_id or self.default_display):
            self.connection_state = "detached"
            return False
        if self.connection_state != "unresponsive":
            self.connection_state = "attached"
        return self.connection_state == "attached"

    def is_process_running(self) -> bool:
        return bool(self.process and self.process.poll() is None)

    def get_status(self) -> Dict:
        attached = self.is_connected()
        process_running = self.is_process_running()
        if self.content_url and not process_running and self.projection_state != "idle":
            self.connection_state = "unresponsive" if attached else "detached"
            self.projection_state = "stale"
        elif process_running and self.expect_heartbeat and self._heartbeat_is_stale():
            self.connection_state = "unresponsive"
            self.projection_state = "stale"

        status = {
            "type": "hdmi",
            "connected": attached,
            "target": self.target_id,
            "connection_state": self.connection_state,
            "projection_state": self.projection_state,
            "power_state": self.power_state,
            "process_running": process_running,
            "content_url": self.content_url,
            "last_error": self.last_error,
            "last_heartbeat_at": self.last_heartbeat_at,
        }
        if self.display:
            status["display"] = self.display.to_dict()
        return status

    def _stop_process(self) -> None:
        if self.process:
            try:
                self.process.terminate()
                time.sleep(0.5)
                if self.process.poll() is None:
                    self.process.kill()
            except Exception as exc:
                self.logger.warning("Error stopping HDMI browser process: %s", exc)
            finally:
                self.process = None

        if self.profile_dir and os.path.exists(self.profile_dir):
            shutil.rmtree(self.profile_dir, ignore_errors=True)
            self.profile_dir = None

        self.content_url = None
        self.last_heartbeat_at = None
        self.started_at = None
        self.expect_heartbeat = False
        self.projection_state = "idle"

    def _heartbeat_is_stale(self) -> bool:
        if not self.expect_heartbeat:
            return False
        if self.last_heartbeat_at is None:
            return self.started_at is not None and time.time() - self.started_at > self.heartbeat_timeout_seconds
        return time.time() - self.last_heartbeat_at > self.heartbeat_timeout_seconds

    @staticmethod
    def _content_supports_heartbeat(content_url: str) -> bool:
        heartbeat_pages = {
            "hdmi_identify.html",
            "structured_light.html",
            "blank.html",
            "overlay_window.html",
        }
        return any(page in content_url for page in heartbeat_pages)

    def _resolve_display(self, target_id: str) -> Optional[DisplayInfo]:
        target = str(target_id or "")
        for raw_display in self.discover_displays():
            display = DisplayInfo.from_mapping(raw_display)
            aliases = {
                display.id,
                str(display.index),
                display.name,
            }
            if display.device_name:
                aliases.add(display.device_name)
            if target in aliases:
                return display
        return None

    def _get_browser_command(self) -> Optional[str]:
        if self.browser_path and os.path.exists(self.browser_path):
            return self.browser_path

        candidates = [
            os.environ.get("CHROME_PATH"),
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
            "/usr/bin/firefox",
        ]
        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return candidate

        for command in ["google-chrome", "chromium", "chromium-browser", "chrome", "msedge", "firefox"]:
            resolved = shutil.which(command)
            if resolved:
                return resolved
        return None

    def _prepare_browser_command(self, browser_cmd: str, content_url: str) -> List[str]:
        display = self.display or DisplayInfo.fallback()
        lower_cmd = browser_cmd.lower()

        if "chrome" in lower_cmd or "chromium" in lower_cmd or "msedge" in lower_cmd:
            args = [browser_cmd, "--new-window", "--no-first-run", "--disable-infobars"]
            if self.kiosk_mode:
                args.append("--kiosk")
            else:
                args.append("--start-fullscreen")
            args.extend(
                [
                    f"--window-position={display.x},{display.y}",
                    f"--window-size={display.width},{display.height}",
                ]
            )
            if self.use_isolated_profile:
                self.profile_dir = tempfile.mkdtemp(prefix="walldisplay_hdmi_")
                args.append(f"--user-data-dir={self.profile_dir}")
            args.append(content_url)
            return args

        if "firefox" in lower_cmd:
            args = [browser_cmd]
            if self.kiosk_mode:
                args.append("--kiosk")
            args.append(content_url)
            if platform.system() in {"Linux", "Darwin"}:
                os.environ["DISPLAY"] = f":{display.index}"
            return args

        return [browser_cmd, content_url]
