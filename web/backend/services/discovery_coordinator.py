import logging
import os
import re
import socket
import struct
import threading
import time
import traceback
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

if __import__("sys").version_info.major == 3:
    import urllib.request as urllibreq
    import urllib.parse as urllibparse
else:
    import urllib2 as urllibreq
    import urlparse as urllibparse

logger = logging.getLogger(__name__)

SSDP_BROADCAST_PORT = 1900
SSDP_BROADCAST_ADDR = "239.255.255.250"
SSDP_BROADCAST_PARAMS = [
    "M-SEARCH * HTTP/1.1",
    "HOST: {0}:{1}".format(SSDP_BROADCAST_ADDR, SSDP_BROADCAST_PORT),
    'MAN: "ssdp:discover"',
    "MX: 10",
    "ST: ssdp:all",
    "",
    "",
]
SSDP_BROADCAST_MSG = "\r\n".join(SSDP_BROADCAST_PARAMS)
UPNP_DEVICE_TYPE = "urn:schemas-upnp-org:device:MediaRenderer:1"
UPNP_SERVICE_TYPE = "urn:schemas-upnp-org:service:AVTransport:1"


class DiscoveryCoordinator:
    """
    Own raw DLNA discovery and discovery-time device reconciliation.

    During the first extraction phase this still delegates registration and status
    updates back to DeviceManager, but the loop body no longer owns the SSDP/XML logic.
    """

    def __init__(self, manager: Any):
        self.manager = manager
        self.device_inventory = getattr(manager, "device_inventory", None)

    def _inventory_len(self) -> int:
        if self.device_inventory is not None:
            return len(self.device_inventory.devices)
        return len(getattr(self.manager, "devices", {}))

    def _inventory_values(self):
        if self.device_inventory is not None:
            return list(self.device_inventory.values())
        return list(getattr(self.manager, "devices", {}).values())

    def _inventory_keys(self):
        if self.device_inventory is not None:
            return list(self.device_inventory.keys())
        return list(getattr(self.manager, "devices", {}).keys())

    def _inventory_get(self, device_name: str):
        if self.device_inventory is not None:
            return self.device_inventory.get(device_name)
        return getattr(self.manager, "devices", {}).get(device_name)

    def _inventory_remove(self, device_name: str) -> None:
        if self.device_inventory is not None:
            self.device_inventory.remove(device_name)
            return
        getattr(self.manager, "devices", {}).pop(device_name, None)

    def start(self) -> None:
        authority = os.environ.get("NANODLNA_DISCOVERY_AUTHORITY", "legacy").strip().lower()
        if authority == "unified":
            logger.info("Unified discovery authority enabled; legacy DLNA discovery loop disabled")
            self.manager.discovery_running = False
            self.manager.discovery_paused = True
            return

        if "PYTEST_CURRENT_TEST" in os.environ:
            logger.info("Skipping DeviceManager discovery during pytest run.")
            self.manager.discovery_running = False
            return

        if self.manager.discovery_thread and self.manager.discovery_thread.is_alive():
            self.manager.discovery_paused = False
            logger.info("Discovery loop already running, cleared paused state")
            return

        self.manager.discovery_running = True
        self.manager.discovery_paused = False
        self.manager.discovery_thread = threading.Thread(target=self.run_loop)
        self.manager.discovery_thread.daemon = True
        self.manager.discovery_thread.start()
        logger.info("Started DLNA device discovery")

    def stop(self) -> None:
        self.manager.discovery_running = False
        if self.manager.discovery_thread:
            self.manager.discovery_thread.join(timeout=1.0)
            logger.info("Stopped DLNA device discovery")

    def pause(self) -> None:
        self.manager.discovery_paused = True
        logger.info("Paused DLNA device discovery")

    def resume(self) -> None:
        if self.manager.discovery_thread and self.manager.discovery_thread.is_alive():
            self.manager.discovery_paused = False
        else:
            self.start()
        logger.info("Resumed DLNA device discovery")

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self.manager.discovery_running and not self.manager.discovery_paused,
            "paused": self.manager.discovery_paused,
            "interval": self.manager.discovery_interval,
            "devices_discovered": self._inventory_len(),
            "devices_playing": sum(1 for d in self._inventory_values() if d.is_playing),
        }

    def run_loop(self) -> None:
        current_devices = set()

        try:
            default_config_file = os.environ.get("DEVICE_CONFIG_FILE", "my_device_config.json")
            if os.path.exists(default_config_file):
                logger.info("Loading default configuration from %s", default_config_file)
                self.manager.config_service.load_configs_from_file(default_config_file)
            else:
                logger.warning("Default configuration file not found: %s", default_config_file)
        except Exception as exc:
            logger.error("Error loading default configuration: %s", exc)

        while self.manager.discovery_running:
            try:
                if self.manager.discovery_paused:
                    time.sleep(0.5)
                    continue

                logger.debug("Starting DLNA device discovery cycle")
                discovered_devices = self.discover_dlna_devices()
                logger.debug("Found %s DLNA devices", len(discovered_devices))

                current_devices.clear()
                observations = self.reconcile_discovered_devices(discovered_devices)
                for observation in observations:
                    current_devices.add(observation["device_name"])
                    self.manager._process_device_video_assignment(
                        observation["device_name"],
                        observation["is_new_device"],
                        observation["is_changed_device"],
                    )

                self.evaluate_disconnected_devices(current_devices)
                logger.debug("Finished DLNA discovery cycle")
            except Exception as exc:
                logger.error("Error during DLNA discovery loop: %s", exc)
                logger.error("Exception details: %s", traceback.format_exc())

            time.sleep(self.manager.discovery_interval)

        logger.info("Discovery loop exited")

    def discover_dlna_devices(self, timeout: float = 2.0, host: Optional[str] = None) -> List[Dict[str, Any]]:
        if not host:
            host = "0.0.0.0"
        logger.debug("Searching for DLNA devices on %s", host)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            ttl = struct.pack("B", 4)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
            sock.bind((host, 0))

            logger.debug("Sending SSDP broadcast message")
            sock.sendto(SSDP_BROADCAST_MSG.encode("UTF-8"), (SSDP_BROADCAST_ADDR, SSDP_BROADCAST_PORT))
        except OSError as exc:
            logger.warning("DLNA discovery send failed on host %s: %s", host, exc)
            sock.close()
            return []

        logger.debug("Waiting for DLNA devices (%s seconds)", timeout)
        sock.settimeout(timeout)

        devices = []
        while True:
            try:
                data, _addr = sock.recvfrom(1024)
            except socket.timeout:
                break

            try:
                info = [line.split(":", 1) for line in data.decode("UTF-8").split("\r\n")[1:]]
                device = {left[0].strip().lower(): left[1].strip() for left in info if len(left) >= 2}
                devices.append(device)
            except Exception as exc:
                logger.error("Error parsing DLNA device response: %s", exc)

        sock.close()

        devices_urls = [
            dev["location"]
            for dev in devices
            if "st" in dev and "AVTransport" in dev["st"]
        ]

        registered_devices = []
        for location_url in devices_urls:
            device_info = self.register_dlna_device(location_url)
            if device_info:
                registered_devices.append(device_info)

        return self.remove_duplicates(registered_devices)

    def reconcile_discovered_devices(self, discovered_devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        observations: List[Dict[str, Any]] = []

        for device_info in discovered_devices:
            device_name = device_info.get("friendly_name")
            if not device_name:
                logger.warning("Device missing friendly_name, skipping")
                continue

            is_new_device = False
            is_changed_device = False

            if not self.manager._acquire_device_lock():
                logger.warning("Could not acquire device lock for %s, skipping device", device_name)
                continue

            try:
                existing_device = self._inventory_get(device_name)
                is_new_device = existing_device is None

                if existing_device:
                    old_hostname = existing_device.device_info.get("hostname")
                    new_hostname = device_info.get("hostname")
                    old_location = existing_device.device_info.get("location")
                    new_location = device_info.get("location")
                    old_action_url = existing_device.device_info.get("action_url")
                    new_action_url = device_info.get("action_url")
                    if (
                        old_hostname != new_hostname
                        or old_location != new_location
                        or old_action_url != new_action_url
                    ):
                        logger.debug("Device %s parameters changed", device_name)
                        is_changed_device = True
            finally:
                self.manager._release_device_lock()

            device_info["device_name"] = device_name
            device_info["type"] = "dlna"

            if "hostname" not in device_info and "location" in device_info:
                try:
                    location = urllibparse.urlparse(device_info["location"])
                    device_info["hostname"] = location.hostname
                except Exception as exc:
                    logger.error("Error parsing location URL: %s", exc)

            if is_new_device or is_changed_device:
                if is_changed_device:
                    logger.debug("Device %s parameters changed, updating atomically", device_name)

                device = self.manager.register_device(device_info)
                if not device:
                    logger.warning("Failed to register device: %s", device_name)
                    continue

                self.manager.update_device_status(device_name, "connected")
                with self.manager.device_state_lock:
                    now = time.time()
                    self.manager.runtime_registry.mark_seen(device_name, now)
                    self.manager.runtime_registry.set_connected_at(device_name, now)
            else:
                with self.manager.device_state_lock:
                    self.manager.runtime_registry.mark_seen(device_name)
                    if self.manager.device_status.get(device_name, {}).get("status") != "connected":
                        self.manager.update_device_status(device_name, "connected")

            observations.append(
                {
                    "device_name": device_name,
                    "is_new_device": is_new_device,
                    "is_changed_device": is_changed_device,
                }
            )

        return observations

    def evaluate_disconnected_devices(self, current_devices: set) -> None:
        with self.manager.device_state_lock:
            for device_name in self._inventory_keys():
                if device_name in current_devices:
                    continue

                last_seen = self.manager.last_seen.get(device_name)
                if last_seen is None:
                    logger.debug("Skipping disconnect evaluation for %s; missing last_seen", device_name)
                    continue

                time_since_last_seen = time.time() - last_seen

                db_device = None
                get_db_device_by_name = getattr(self.manager, "get_db_device_by_name", None)
                if get_db_device_by_name is None:
                    try:
                        from services.app_runtime import get_app_runtime

                        get_db_device_by_name = get_app_runtime().get_db_device_by_name
                    except Exception:
                        get_db_device_by_name = None

                if get_db_device_by_name is not None:
                    try:
                        db_device = get_db_device_by_name(device_name)
                    except Exception as exc:
                        logger.error("Error loading device %s from database: %s", device_name, exc)

                grace_period = 10
                extended_grace = 20

                if db_device:
                    updated_at = db_device.updated_at
                    is_playing = db_device.is_playing
                    if updated_at:
                        seconds_since_update = (
                            datetime.now(timezone.utc) - updated_at.replace(tzinfo=timezone.utc)
                        ).total_seconds()
                        limit = extended_grace if is_playing else grace_period
                        if seconds_since_update < limit:
                            logger.debug(
                                "Skipping disconnect for %s, updated %.1fs ago",
                                device_name,
                                seconds_since_update,
                            )
                            continue

                if time_since_last_seen > self.manager.connectivity_timeout:
                    logger.info(
                        "Device %s not seen for %.1fs, marking disconnected",
                        device_name,
                        time_since_last_seen,
                    )
                    self.manager.update_device_status(device_name, "disconnected")
                    self._cleanup_streaming_sessions(device_name, removed=False)

                    if time_since_last_seen > self.manager.connectivity_timeout * 2:
                        logger.info(
                            "Removing device %s from memory due to extended disconnection",
                            device_name,
                        )
                        self._cleanup_streaming_sessions(device_name, removed=True)
                        self._inventory_remove(device_name)
                        self.manager.runtime_registry.remove_device(device_name)

    def register_dlna_device(self, location_url: str) -> Optional[Dict[str, Any]]:
        try:
            logger.debug("Registering DLNA device at %s", location_url)

            xml_raw = urllibreq.urlopen(location_url, timeout=5).read().decode("UTF-8")
            xml = re.sub(r"""\s(xmlns="[^"]+"|xmlns='[^']+')""", "", xml_raw, count=1)
            info = ET.fromstring(xml)

            location = urllibparse.urlparse(location_url)
            hostname = location.hostname
            port = location.port or 80

            device_root = info.find("./device")
            if not device_root:
                device_root = info.find(
                    "./device/deviceList/device/[deviceType='{0}']".format(UPNP_DEVICE_TYPE)
                )

            friendly_name = self._get_xml_field_text(device_root, "./friendlyName")
            manufacturer = self._get_xml_field_text(device_root, "./manufacturer")

            service_paths = [
                "./serviceList/service/[serviceType='{0}']/controlURL".format(UPNP_SERVICE_TYPE),
                "./serviceList/service/controlURL",
                ".//service/[serviceType='{0}']/controlURL".format(UPNP_SERVICE_TYPE),
                ".//service/controlURL",
            ]

            action_url_path = None
            for path in service_paths:
                action_url_path = self._get_xml_field_text(device_root, path)
                if action_url_path:
                    break

            if action_url_path is not None:
                if action_url_path.startswith("http://") or action_url_path.startswith("https://"):
                    action_url = action_url_path
                else:
                    if not action_url_path.startswith("/"):
                        action_url_path = "/" + action_url_path
                    action_url = f"http://{hostname}:{port}{action_url_path}"
            else:
                action_url = f"http://{hostname}:{port}/AVTransport/Control"
                logger.warning("No action URL found, using default: %s", action_url)

            return {
                "device_name": friendly_name,
                "type": "dlna",
                "location": location_url,
                "hostname": hostname,
                "manufacturer": manufacturer,
                "friendly_name": friendly_name,
                "action_url": action_url,
                "st": UPNP_SERVICE_TYPE,
            }
        except Exception as exc:
            logger.error("Error registering DLNA device at %s: %s", location_url, exc)
            return None

    def remove_duplicates(self, devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        result_devices = []
        for device in devices:
            device_str = str(device)
            if device_str not in seen:
                result_devices.append(device)
                seen.add(device_str)
        return result_devices

    def _get_xml_field_text(self, xml_root: Any, query: str) -> Optional[str]:
        result = None
        if xml_root:
            node = xml_root.find(query)
            result = node.text if node is not None else None
        return result

    def _cleanup_streaming_sessions(self, device_name: str, *, removed: bool) -> None:
        action = "removed" if removed else "disconnected"
        try:
            from core.streaming_registry import StreamingSessionRegistry

            streaming_registry = StreamingSessionRegistry.get_instance()
            device_sessions = streaming_registry.get_sessions_for_device(device_name)
            for session in device_sessions:
                logger.debug(
                    "Cleaning up streaming session %s for %s device %s",
                    session.session_id,
                    action,
                    device_name,
                )
                streaming_registry.unregister_session(session.session_id)
        except Exception as exc:
            logger.error(
                "Error cleaning up streaming sessions for %s device %s: %s",
                action,
                device_name,
                exc,
            )
