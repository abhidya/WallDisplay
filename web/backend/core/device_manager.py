import re
import socket
import struct
import sys
import xml.etree.ElementTree as ET
import logging
import json
import os
from typing import Dict, List, Optional, Any, Union, Tuple
import threading
import time
from datetime import datetime, timezone
import traceback
import asyncio

if sys.version_info.major == 3:
    import urllib.request as urllibreq
    import urllib.parse as urllibparse
else:
    import urllib2 as urllibreq
    import urlparse as urllibparse

from .device import Device
from .dlna_device import DLNADevice
from .transcreen_device import TranscreenDevice
from .config_service import ConfigService
from .streaming_registry import StreamingSessionRegistry
from services.overlay_cast_service import get_overlay_cast_service
from discovery.discovery_manager import DiscoveryManager

logger = logging.getLogger(__name__)

# SSDP constants for DLNA device discovery
SSDP_BROADCAST_PORT = 1900
SSDP_BROADCAST_ADDR = "239.255.255.250"

SSDP_BROADCAST_PARAMS = [
    "M-SEARCH * HTTP/1.1",
    "HOST: {0}:{1}".format(SSDP_BROADCAST_ADDR, SSDP_BROADCAST_PORT),
    "MAN: \"ssdp:discover\"", "MX: 10", "ST: ssdp:all", "", ""]
SSDP_BROADCAST_MSG = "\r\n".join(SSDP_BROADCAST_PARAMS)

UPNP_DEVICE_TYPE = "urn:schemas-upnp-org:device:MediaRenderer:1"
UPNP_SERVICE_TYPE = "urn:schemas-upnp-org:service:AVTransport:1"

# Constants for video assignment
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY_BASE = 5  # seconds
PLAYBACK_HEALTH_CHECK_INTERVAL = 30  # seconds

class DeviceManager:
    """
    Manages DLNA and Transcreen devices, handling device discovery, status tracking,
    and video playback coordination.
    """
    def __init__(self):
        """Initialize the device manager with consolidated locks for deadlock prevention"""
        # SECURITY FIX: Consolidated lock architecture (8 locks → 4 locks)
        # Hierarchical lock ordering: device_state_lock → assignment_lock → monitoring_lock → statistics_lock
        
        # Level 1: Core device and status state (consolidates device_lock + status_lock + assigned_videos_lock)
        self.device_state_lock = threading.RLock()  # RLock allows reentrant access for same thread
        self.device_lock_timeout = 5.0  # seconds
        
        # Level 2: Assignment coordination (consolidates video_assignment_lock + scheduled_assignments_lock)
        self.assignment_lock = threading.Lock()
        
        # Level 3: Monitoring and health checks (consolidates playback_history_lock + playback_health_threads_lock)
        self.monitoring_lock = threading.Lock()
        
        # Level 4: Statistics collection (separate for performance - read-heavy operations)
        self.statistics_lock = threading.Lock()
        
        # Core device tracking - protected by device_state_lock
        self.devices = {}  # name -> Device
        self.device_status = {}  # name -> status dict
        self.last_seen = {}  # name -> timestamp
        self.device_connected_at = {}  # name -> timestamp
        self.assigned_videos = {}  # name -> video path
        
        # Assignment tracking - protected by assignment_lock
        self.video_assignment_priority = {}  # name -> priority
        self.video_assignment_retries = {}  # name -> retry count
        self.scheduled_assignments = {}  # name -> scheduled assignment info
        self.device_assignment_queue = {}  # name -> assignment info
        
        # Monitoring data - protected by monitoring_lock
        self.playback_health_threads = {}  # name -> thread info
        self.video_playback_history = {}  # name -> playback stats
        
        # Statistics - protected by statistics_lock
        self.playback_stats = {}  # Dictionary for tracking playback stats
        
        # Get config service and streaming registry
        self.config_service = ConfigService.get_instance()
        self.streaming_registry = StreamingSessionRegistry.get_instance()
        self.streaming_registry.register_health_check_handler(self._handle_streaming_issue)
        
        # Discovery thread attributes
        self.discovery_thread = None
        self.discovery_running = False
        self.discovery_paused = False
        self.discovery_interval = 10  # Seconds between discovery cycles
        
        # Additional attributes
        self.device_service = None
        self.connectivity_timeout = 30  # Seconds to wait before considering a device offline

    def set_device_service(self, device_service):
        """
        Set the device service reference for database operations
        
        Args:
            device_service: The DeviceService instance to use
        """
        self.device_service = device_service
        logger.info("Device service reference set in DeviceManager")

    def _acquire_device_state_lock(self):
        """Acquire the device state lock with timeout to prevent deadlock"""
        acquired = self.device_state_lock.acquire(blocking=True, timeout=self.device_lock_timeout)
        if not acquired:
            logger.warning(f"Failed to acquire device_state_lock within {self.device_lock_timeout}s timeout")
        return acquired

    def _release_device_state_lock(self):
        """Release the device state lock"""
        try:
            self.device_state_lock.release()
        except RuntimeError:
            # Lock wasn't held
            pass

    # SECURITY: Legacy compatibility methods (deprecated)
    def _acquire_device_lock(self):
        """DEPRECATED: Use _acquire_device_state_lock instead"""
        return self._acquire_device_state_lock()

    def _release_device_lock(self):
        """DEPRECATED: Use _release_device_state_lock instead"""
        self._release_device_state_lock()

    def _handle_streaming_issue(self, session):
        """Handle streaming issues and attempt recovery"""
        try:
            device_name = session.device_name
            
            # Internal overlay streams are not persisted render devices, so skip device recovery.
            if getattr(session, "stream_type", None) in {"projection_stream", "overlay_mapping_stream"} or device_name in {"overlay", "overlay-mapping"}:
                logger.info(f"Streaming issue for internal overlay session {session.session_id}, skipping device-specific handling")
                return
            
            device = self.get_device(device_name)
            
            if not device:
                # Add debug info to understand why device not found
                logger.warning(f"Device {device_name} not found for streaming issue handling - attempting recovery")
                logger.debug(f"Current devices in manager: {list(self.devices.keys())}")
                logger.debug(f"Device state lock held: {self.device_state_lock.locked()}")
                with self.device_state_lock:
                    last_seen_time = self.last_seen.get(device_name, 0)
                    time_since_seen = time.time() - last_seen_time if last_seen_time else float('inf')
                    logger.debug(f"Device {device_name} last seen {time_since_seen:.1f}s ago")
                
                # Try to recover device from database if available
                if self.device_service:
                    try:
                        logger.info(f"Attempting to recover device {device_name} from database")
                        db_device = self.device_service.get_device_by_name(device_name)
                        if db_device:
                            logger.info(f"Found device {device_name} in database, attempting recovery")
                            device_info = {
                                "device_name": db_device.name,
                                "type": db_device.type,
                                "hostname": db_device.hostname,
                                "action_url": db_device.action_url,
                                "friendly_name": db_device.friendly_name,
                                "manufacturer": db_device.manufacturer,
                                "location": db_device.location,
                            }
                            device = self.register_device(device_info)
                            if device:
                                logger.info(f"Successfully recovered device {device_name} from database")
                                # Update with streaming info if available
                                if hasattr(db_device, 'streaming_url') and db_device.streaming_url and db_device.streaming_port:
                                    logger.info(f"Restoring streaming info: {db_device.streaming_url}:{db_device.streaming_port}")
                                    device.update_streaming_info(db_device.streaming_url, db_device.streaming_port)
                                # Continue with normal streaming issue handling
                            else:
                                logger.error(f"Failed to re-register device {device_name} during recovery")
                                return
                        else:
                            logger.warning(f"Device {device_name} not found in database - may have been removed")
                            return
                    except Exception as e:
                        logger.error(f"Error recovering device from database: {e}")
                        logger.debug(f"Recovery error details: {traceback.format_exc()}")
                        return
                else:
                    logger.warning(f"No device_service available for recovery of {device_name}")
                    return
                
            # Check if session is stalled
            if session.status == "stalled" and session.is_stalled(inactivity_threshold=30.0):
                # Only update status to streaming_issue if there's an actual problem
                self.update_device_status(
                    device_name=device_name,
                    status="streaming_issue",
                    error=f"Streaming session stalled"
                )
                logger.warning(f"Streaming session for {device_name} is stalled, attempting recovery")
                
                # Try to restart playback
                if device_name in self.assigned_videos:
                    video_path = self.assigned_videos[device_name]
                    if os.path.exists(video_path):
                        logger.info(f"Attempting to restart video {video_path} on device {device_name}")
                        
                        # Stop current playback
                        device.stop()
                        time.sleep(2)  # Give it time to stop
                        
                        # Attempt to play again
                        success = self.auto_play_video(device, video_path, loop=True)
                        
                        if success:
                            logger.info(f"Successfully recovered streaming for {device_name}")
                            self.update_device_status(
                                device_name=device_name,
                                status="connected",
                                is_playing=True,
                                current_video=video_path
                            )
                        else:
                            logger.error(f"Failed to recover streaming for {device_name}")
                            self.update_device_status(
                                device_name=device_name,
                                status="error",
                                is_playing=False,
                                error="Failed to recover from streaming issue"
                            )
                    else:
                        logger.error(f"Video file no longer exists: {video_path}")
                        self.update_device_status(
                            device_name=device_name,
                            status="error",
                            is_playing=False,
                            error="Video file no longer exists"
                        )
        except Exception as e:
            logger.error(f"Error handling streaming issue for {device_name}: {e}")
            self.update_device_status(
                device_name=device_name,
                status="error",
                error=str(e)
            )

    def _playback_health_check_loop(self, device_name: str, video_path: str) -> None:
        """
        Background thread for monitoring playback health
        
        Args:
            device_name: Name of the device to monitor
            video_path: Path to the video being played
        """
        logger.info(f"Starting playback health monitoring for {device_name}")
        consecutive_failures = 0
        max_consecutive_failures = 3
        check_interval = PLAYBACK_HEALTH_CHECK_INTERVAL
        
        while True:
            try:
                # Sleep between checks
                time.sleep(check_interval)
                
                # SECURITY FIX: Check if thread should exit using monitoring_lock
                with self.monitoring_lock:
                    if (device_name not in self.playback_health_threads or 
                            not self.playback_health_threads.get(device_name, {}).get("active", False)):
                        logger.info(f"Stopping playback health monitoring for {device_name}")
                        break
                
                # Get device with thread safety
                device = self.get_device(device_name)
                if not device:
                    logger.warning(f"Device {device_name} not found, stopping health check")
                    break
                
                # Check device playing status
                if not device.is_playing:
                    logger.warning(f"Device {device_name} is not playing but should be. Consecutive failure: {consecutive_failures+1}/{max_consecutive_failures}")
                    consecutive_failures += 1
                    
                    # Check if we should attempt recovery
                    if consecutive_failures >= max_consecutive_failures:
                        logger.warning(f"Device {device_name} playback consistently failing, attempting recovery")
                        
                        # Check if device was manually stopped
                        if self.device_service:
                            try:
                                db_device = self.device_service.get_device_by_name(device_name)
                                if db_device and db_device.user_control_mode == "manual" and db_device.user_control_reason == "user_stopped":
                                    logger.info(f"Device {device_name} was manually stopped, skipping auto-recovery")
                                    break
                            except Exception as e:
                                logger.warning(f"Could not check user control mode for {device_name}: {e}")
                        
                        # Check current video assignment
                        with self.device_state_lock:
                            current_video = self.assigned_videos.get(device_name)
                            
                        if current_video and os.path.exists(current_video):
                            logger.info(f"Attempting to restart video {current_video} on device {device_name}")
                            self.auto_play_video(device, current_video, loop=True)
                            consecutive_failures = 0  # Reset after recovery attempt
                else:
                    # Device is playing, reset failure counter
                    if consecutive_failures > 0:
                        logger.info(f"Device {device_name} is now playing correctly, resetting failure counter")
                        consecutive_failures = 0
                
                # Check for streaming sessions to validate device state
                active_sessions = self.streaming_registry.get_sessions_for_device(device_name)
                
                # If device is playing but there are no active sessions, this might indicate an issue
                if device.is_playing and not active_sessions:
                    logger.warning(f"Device {device_name} is playing but has no active streaming sessions")
                    
                    # Check if we need to restart the stream
                    with self.device_state_lock:
                        if device_name in self.assigned_videos and device.current_video != self.assigned_videos[device_name]:
                            logger.info(f"Restarting video {self.assigned_videos[device_name]} on device {device_name}")
                            self.auto_play_video(device, self.assigned_videos[device_name], loop=True)
                
                # If there are issues with any streaming sessions, log them
                streaming_issues = False
                for session in active_sessions:
                    if session.status in ["stalled", "error"]:
                        logger.warning(f"Streaming session {session.session_id} for device {device_name} has status {session.status}")
                        streaming_issues = True
                        
                # Update device status with streaming information
                with self.device_state_lock:
                    if device_name in self.device_status:
                        self.device_status[device_name]["active_streaming_sessions"] = len(active_sessions)
                        self.device_status[device_name]["streaming_issues"] = streaming_issues
                        
                        # Add detailed streaming info if available
                        if active_sessions:
                            total_bytes = sum(session.bytes_served for session in active_sessions)
                            avg_bandwidth = sum(session.get_bandwidth() for session in active_sessions) / len(active_sessions) if active_sessions else 0
                            
                            self.device_status[device_name]["streaming_bytes"] = total_bytes
                            self.device_status[device_name]["streaming_bandwidth_bps"] = avg_bandwidth
                
            except Exception as e:
                logger.error(f"Error in playback health check for {device_name}: {e}")
                time.sleep(5)  # Sleep on error to avoid tight loop
        
        logger.info(f"Playback health monitoring stopped for {device_name}")
        
        # SECURITY FIX: Clean up thread tracking using monitoring_lock
        with self.monitoring_lock:
            if device_name in self.playback_health_threads:
                del self.playback_health_threads[device_name]
    
    def get_devices(self) -> List[Device]:
        """
        Get all registered devices
        
        Returns:
            List[Device]: List of all registered devices
        """
        if not self._acquire_device_lock():
            return []
        try:
            return list(self.devices.values())
        finally:
            self._release_device_lock()
    
    def get_device(self, device_name: str) -> Optional[Device]:
        """
        Get a device by name
        
        Args:
            device_name: Name of the device to get
            
        Returns:
            Optional[Device]: The device if found, None otherwise
        """
        if not self._acquire_device_lock():
            return None
        try:
            return self.devices.get(device_name)
        finally:
            self._release_device_lock()
    
    def register_device(self, device_info: Dict[str, Any]) -> Optional[Device]:
        """
        Register a device
        
        Args:
            device_info: Device information
            
        Returns:
            Optional[Device]: The registered device if successful, None otherwise
        """
        try:
            device_name = device_info.get("device_name")
            device_type = device_info.get("type", "dlna")
            
            if not device_name:
                logger.error("Device missing name")
                return None
            
            # Create the appropriate device type
            if device_type == "dlna":
                device = DLNADevice(device_info)
            elif device_type == "transcreen":
                device = TranscreenDevice(device_info)
            else:
                logger.error(f"Unknown device type: {device_type}")
                return None
            
            # Register the device with thread safety
            if not self._acquire_device_lock():
                return None
            
            try:
                # Check if device already exists to avoid duplicates
                existing_device = None
                if device_name in self.devices:
                    existing_device = self.devices[device_name]
                    # Compare key attributes to see if it's really the same device
                    if (existing_device.device_info.get("hostname") == device_info.get("hostname") and
                        existing_device.device_info.get("location") == device_info.get("location")):
                        logger.info(f"Device {device_name} already registered with same parameters")
                        return existing_device
                    else:
                        logger.info(f"Device {device_name} already registered but with different parameters, updating")
                        # Preserve streaming information during update
                        if hasattr(existing_device, 'streaming_url') and existing_device.streaming_url:
                            logger.info(f"Preserving streaming info during device update: {existing_device.streaming_url}:{existing_device.streaming_port}")
                            device.update_streaming_info(existing_device.streaming_url, existing_device.streaming_port)
                        # Preserve playback state
                        if hasattr(existing_device, 'is_playing') and existing_device.is_playing:
                            device.update_playing(True)
                            if hasattr(existing_device, 'current_video'):
                                device.current_video = existing_device.current_video
                
                # Register or update the device
                self.devices[device_name] = device
                logger.info(f"Registered {device_type} device: {device_name}")
            finally:
                self._release_device_lock()
            
            # Initialize device status if not already present
            with self.device_state_lock:
                if device_name not in self.device_status:
                    self.device_status[device_name] = {
                        "status": "connected",
                        "last_updated": time.time(),
                        "is_playing": False,
                        "last_seen_at": time.time(),
                        "last_lost_at": None,
                        "reconnect_count": 0,
                        "degraded_count": 0,
                        "offline_count": 0,
                    }
                    logger.info(f"Initialized device_status for {device_name}")
                if device_name not in self.last_seen:
                    self.last_seen[device_name] = time.time()
            
            return device
        except Exception as e:
            logger.error(f"Error registering device: {e}")
            return None
    
    def cleanup_device_state(self, device_name: str):
        """
        Clean up all state for a device
        
        Args:
            device_name: Name of the device to clean up
        """
        logger.info(f"Cleaning up state for device {device_name}")
        
        # Stop health check
        self._stop_playback_health_check(device_name)
        
        # Clear assignments
        with self.device_state_lock:
            if device_name in self.assigned_videos:
                logger.info(f"Clearing assigned video for device {device_name}")
                self.assigned_videos.pop(device_name, None)
        
        # Clear priority
        if device_name in self.video_assignment_priority:
            logger.info(f"Clearing video assignment priority for device {device_name}")
            self.video_assignment_priority.pop(device_name, None)
        
        # Clear from device queue
        if device_name in self.device_assignment_queue:
            logger.info(f"Clearing device from assignment queue: {device_name}")
            self.device_assignment_queue.pop(device_name, None)
    
    def unregister_device(self, device_name: str) -> bool:
        """
        Unregister a device with secure hierarchical lock ordering
        
        Args:
            device_name: Name of the device to unregister
            
        Returns:
            bool: True if successful, False otherwise
        """
        # SECURITY FIX: Hierarchical lock acquisition to prevent deadlock
        # Order: device_state_lock → assignment_lock → monitoring_lock
        
        if not self._acquire_device_state_lock():
            return False
        
        try:
            if device_name not in self.devices:
                logger.warning(f"Device not found: {device_name}")
                return False
                
            # Get the device before cleanup
            device = self.devices[device_name]
            
            # Level 1: Clean device state data (already have device_state_lock)
            del self.devices[device_name]
            if device_name in self.device_status:
                del self.device_status[device_name]
            if device_name in self.last_seen:
                del self.last_seen[device_name]
            if device_name in self.device_connected_at:
                del self.device_connected_at[device_name]
            if device_name in self.assigned_videos:
                del self.assigned_videos[device_name]
            
            # Level 2: Clean assignment data
            with self.assignment_lock:
                if device_name in self.video_assignment_priority:
                    del self.video_assignment_priority[device_name]
                if device_name in self.video_assignment_retries:
                    del self.video_assignment_retries[device_name]
                if device_name in self.scheduled_assignments:
                    del self.scheduled_assignments[device_name]
                if device_name in self.device_assignment_queue:
                    del self.device_assignment_queue[device_name]
            
            # Level 3: Clean monitoring data and stop health checks
            with self.monitoring_lock:
                if device_name in self.video_playback_history:
                    del self.video_playback_history[device_name]
                # Stop health check thread safely
                if device_name in self.playback_health_threads:
                    self.playback_health_threads[device_name]["active"] = False
                    del self.playback_health_threads[device_name]
            
            logger.info(f"Unregistered device: {device_name}")
            return True
            
        finally:
            self._release_device_state_lock()
    
    def load_devices_from_config(self, config_file: str) -> List[Device]:
        """
        Load devices from a configuration file
        
        Args:
            config_file: Path to the configuration file
            
        Returns:
            List[Device]: List of loaded devices
        """
        try:
            # Log the absolute path for debugging
            abs_path = os.path.abspath(config_file)
            logger.info(f"Loading devices from config file: {abs_path}")
            
            # Use the config service to load configurations
            loaded_devices_names = self.config_service.load_configs_from_file(abs_path)
            logger.info(f"Loaded {len(loaded_devices_names)} device configurations from {abs_path}")
            
            # Return the devices that were loaded and registered
            loaded_devices = []
            with self.device_state_lock:
                for device_name in loaded_devices_names:
                    if device_name in self.devices:
                        loaded_devices.append(self.devices[device_name])
            
            return loaded_devices
        except Exception as e:
            logger.error(f"Error loading devices from {config_file}: {e}")
            return []
    
    def save_devices_to_config(self, config_file: str) -> bool:
        """
        Save devices to a configuration file
        
        Args:
            config_file: Path to the configuration file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get device information with thread safety
            with self.device_state_lock:
                # Create deep copies to avoid modification during saving
                devices_config = [device.device_info.copy() for device in self.devices.values()]
            
            # Use the config service to save configurations
            abs_path = os.path.abspath(config_file)
            
            with open(abs_path, "w") as f:
                json.dump(devices_config, f, indent=4)
            
            logger.info(f"Saved {len(devices_config)} devices to {abs_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving devices to {config_file}: {e}")
            return False
    
    def start_discovery(self) -> None:
        """
        Start discovering DLNA devices on the network
        """
        if "PYTEST_CURRENT_TEST" in os.environ:
            logger.info("Skipping DeviceManager discovery during pytest run.")
            self.discovery_running = False # Ensure it's not marked as running
            return

        if self.discovery_thread and self.discovery_thread.is_alive():
            self.discovery_paused = False
            logger.info("Discovery loop already running, cleared paused state")
            return
        
        self.discovery_running = True
        self.discovery_paused = False
        self.discovery_thread = threading.Thread(target=self._discovery_loop)
        self.discovery_thread.daemon = True
        self.discovery_thread.start()
        logger.info("Started DLNA device discovery")

    def _discovery_loop(self) -> None:
        """
        Loop for discovering DLNA devices
        """
        current_devices = set()
        
        # Load default configuration only on startup
        try:
            # Load default configuration file
            default_config_file = os.environ.get("DEVICE_CONFIG_FILE", "my_device_config.json")
            if os.path.exists(default_config_file):
                logger.info(f"Loading default configuration from {default_config_file}")
                self.config_service.load_configs_from_file(default_config_file)
            else:
                logger.warning(f"Default configuration file not found: {default_config_file}")
        except Exception as e:
            logger.error(f"Error loading default configuration: {e}")
        
        while self.discovery_running:
            try:
                if self.discovery_paused:
                    time.sleep(0.5)
                    continue

                logger.debug("Starting DLNA device discovery cycle")
                discovered_devices = self._discover_dlna_devices()
                logger.debug(f"Found {len(discovered_devices)} DLNA devices")
                
                # Clear current devices set for this cycle
                current_devices.clear()
                
                for device_info in discovered_devices:
                    device_name = device_info.get("friendly_name")
                    if not device_name:
                        logger.warning("Device missing friendly_name, skipping")
                        continue
                    
                    current_devices.add(device_name)
                    logger.debug(f"Processing discovered device: {device_name}")
                    
                    # Using thread-safe device lock access
                    is_new_device = False
                    is_changed_device = False
                    
                    if not self._acquire_device_lock():
                        logger.warning(f"Could not acquire device lock for {device_name}, skipping device")
                        continue
                    
                    try:
                        existing_device = self.devices.get(device_name)
                        is_new_device = existing_device is None
                        
                        if existing_device:
                            old_hostname = existing_device.device_info.get("hostname")
                            new_hostname = device_info.get("hostname")
                            old_location = existing_device.device_info.get("location")
                            new_location = device_info.get("location")
                            
                            if old_hostname != new_hostname or old_location != new_location:
                                logger.debug(f"Device {device_name} parameters changed")
                                is_changed_device = True
                    finally:
                        self._release_device_lock()
                    
                    device_info["device_name"] = device_name
                    device_info["type"] = "dlna"
                    
                    if "hostname" not in device_info and "location" in device_info:
                        try:
                            location = urllibparse.urlparse(device_info["location"])
                            device_info["hostname"] = location.hostname
                            logger.debug(f"Set hostname to {location.hostname} from location URL")
                        except Exception as e:
                            logger.error(f"Error parsing location URL: {e}")
                    
                    if is_new_device or is_changed_device:
                        # Atomic device registration/update - no unregister needed
                        # register_device() handles updating existing devices safely
                        if is_changed_device:
                            logger.debug(f"Device {device_name} parameters changed, updating atomically")
                        
                        device = self.register_device(device_info)
                        if device:
                            logger.debug(f"Successfully registered device: {device_name}")
                            self.update_device_status(device_name, "connected")
                            with self.device_state_lock:
                                self.last_seen[device_name] = time.time()
                                self.device_connected_at[device_name] = time.time()
                        else:
                            logger.warning(f"Failed to register device: {device_name}")
                            continue
                    else:
                        # Update last seen time for existing device
                        with self.device_state_lock:
                            self.last_seen[device_name] = time.time()
                            # Only update status if device was previously disconnected
                            if self.device_status.get(device_name, {}).get("status") != "connected":
                                self.update_device_status(device_name, "connected")
                    
                    # Process discovered device against configurations using improved assignment logic
                    self._process_device_video_assignment(device_name, is_new_device, is_changed_device)
                
                # Check for disconnected devices
                self._check_disconnected_devices(current_devices)
                
                logger.debug("Finished DLNA discovery cycle")
            
            except Exception as e:
                logger.error(f"Error during DLNA discovery loop: {e}")
                logger.error(f"Exception details: {traceback.format_exc()}")
            
            time.sleep(self.discovery_interval)
        
        logger.info("Discovery loop exited")

    def _process_device_video_assignment(self, device_name: str, is_new_device: bool, is_changed_device: bool) -> None:
        """
        Process video assignment for a device using improved assignment logic
        
        Args:
            device_name: Name of the device to process
            is_new_device: Whether this is a newly discovered device
            is_changed_device: Whether the device parameters have changed
        """
        device = self.get_device(device_name)
        if not device:
            logger.warning(f"Device {device_name} not found, cannot process video assignment")
            return
        
        # Check if device is under user control
        if self.device_service:
            try:
                db_device = self.device_service.get_device_by_name(device_name)
                if db_device and db_device.user_control_mode != 'auto':
                    logger.debug(f"Skipping {device_name} - under user control mode: {db_device.user_control_mode} (reason: {db_device.user_control_reason})")
                    return
                if db_device and self._process_device_overlay_cast(device_name, db_device):
                    return
            except Exception as e:
                logger.warning(f"Could not check user control mode for {device_name}: {e}")
        
        # Check for scheduled assignments that are due
        scheduled_video = self._check_scheduled_assignments(device_name)
        if scheduled_video:
            logger.info(f"Found scheduled video assignment for {device_name}: {scheduled_video}")
            self.assign_video_to_device(device_name, scheduled_video, priority=100)  # High priority for scheduled
            return
            
        # Check if there's a configuration for this device
        config = self.config_service.get_device_config(device_name)
        if not config:
            logger.debug(f"No configuration found for {device_name}, skipping video assignment")
            return
        
        # Check if this device is configured for airplay mode
        if config.get("airplay_mode"):
            logger.debug(f"Device {device_name} is configured for airplay mode")
            self._process_airplay_casting(device_name, config)
            return
            
        video_path = config.get("video_file")
        if not video_path or not os.path.exists(video_path):
            logger.error(f"Video file {video_path} not found or not specified in config")
            return
        
        # Get the current video assignment
        current_video = None
        with self.device_state_lock:
            current_video = self.assigned_videos.get(device_name)
        
        # Only assign if:
        # 1. No video is currently assigned
        # 2. A different video is assigned than what's in the config
        # 3. The device is new or changed
        # 4. The device should be playing but isn't
        if (not current_video or 
            current_video != video_path or 
            is_new_device or 
            is_changed_device or 
            (device.current_video != video_path and not device.is_playing)):
            
            logger.info(f"Assigning video {video_path} to device {device_name}")
            # Get priority from config or use default
            priority = config.get("priority", 50)  # Default medium priority
            self.assign_video_to_device(device_name, video_path, priority=priority)
        else:
            logger.debug(f"No need to reassign video for device {device_name}")

    def _process_device_overlay_cast(self, device_name: str, db_device) -> bool:
        config = db_device.config or {}
        if not config.get("auto_overlay_cast_enabled"):
            return False

        overlay_config_id = config.get("auto_overlay_config_id")
        if not overlay_config_id:
            logger.warning(f"Device {device_name} has auto overlay cast enabled without auto_overlay_config_id")
            return False

        discovery_device_id = self._resolve_discovery_device_id(device_name, db_device.hostname)
        if not discovery_device_id:
            logger.info(f"Device {device_name} has overlay auto-cast configured but is not available in discovery v2 yet")
            return False

        cast_service = get_overlay_cast_service()
        existing_session = cast_service.get_session_for_device(discovery_device_id)
        if (
            existing_session and
            existing_session.get("config_id") == overlay_config_id and
            existing_session.get("status") in {"starting", "preparing", "running"}
        ):
            logger.debug(f"Overlay auto-cast already active for {device_name} with config {overlay_config_id}")
            return True

        logger.info(f"Ensuring overlay config {overlay_config_id} is casting to {device_name}")
        try:
            asyncio.run(
                cast_service.start_cast(
                    device_id=discovery_device_id,
                    config_id=int(overlay_config_id),
                    overlay_base_url="http://localhost:8000",
                    controls_hidden=True,
                )
            )
            logger.info(f"Started overlay auto-cast for {device_name} using config {overlay_config_id}")
            return True
        except Exception as exc:
            logger.error(f"Failed to start overlay auto-cast for {device_name}: {exc}")
            return True

    def _resolve_discovery_device_id(self, device_name: str, hostname: Optional[str]) -> Optional[str]:
        discovery_manager = DiscoveryManager.get_instance()
        candidates = discovery_manager.get_all_devices(online_only=True)

        for device in candidates:
            if device.casting_method.value != "dlna":
                continue
            if device.name == device_name or device.friendly_name == device_name:
                return device.id
            if hostname and device.hostname == hostname:
                return device.id

        return None
            
    def assign_video_to_device(self, device_name: str, video_path: str, 
                              priority: int = 50, schedule_time: Optional[datetime] = None) -> bool:
        """
        Assign a video to a device with priority and optional scheduling
        
        Args:
            device_name: Name of the device
            video_path: Path to the video to assign
            priority: Priority of assignment (0-100, higher is more important)
            schedule_time: Optional time to schedule the assignment for
            
        Returns:
            bool: True if assignment was successful or scheduled, False otherwise
        """
        device = self.get_device(device_name)
        if not device:
            logger.error(f"Device {device_name} not found, cannot assign video")
            return False
            
        # Check if video file exists
        if not os.path.exists(video_path):
            logger.error(f"Video file {video_path} does not exist")
            return False
            
        # Handle scheduled assignments
        if schedule_time is not None:
            with self.assignment_lock:
                self.scheduled_assignments[device_name] = {
                    "video_path": video_path,
                    "priority": priority,
                    "scheduled_time": schedule_time
                }
            logger.info(f"Scheduled video {video_path} for device {device_name} at {schedule_time}")
            return True
        
        # Check if we should override the current assignment based on priority
        should_override = False
        current_priority = 0
        
        with self.assignment_lock:
            current_priority = self.video_assignment_priority.get(device_name, 0)
            if priority >= current_priority:
                should_override = True
                # Update priority tracking
                self.video_assignment_priority[device_name] = priority
        
        if not should_override:
            logger.debug(f"Not overriding current video assignment for {device_name} due to priority: {priority} < {current_priority}")
            return False
            
        # Proceed with assignment using device_state_lock for assigned videos
        with self.device_state_lock:
            current_video = self.assigned_videos.get(device_name)
            if current_video == video_path and device.is_playing:
                logger.debug(f"Device {device_name} is already playing {video_path}")
                return True
                
            if current_video and current_video != video_path and device.is_playing:
                logger.info(f"Device {device_name} is playing {current_video}, stopping first")
                device.stop()
                time.sleep(1)  # Give it time to stop
            
            # Store the assigned video
            self.assigned_videos[device_name] = video_path
            
        # Reset retry counter when assigning a new video
        with self.assignment_lock:
            self.video_assignment_retries[device_name] = 0
            
        # Get device config to check for loop setting
        config = self.config_service.get_device_config(device_name) if self.config_service else {}
        loop_enabled = config.get("loop", True) if config else True
        
        # Play the video
        logger.info(f"Auto-playing {video_path} on {device_name} with loop={loop_enabled}")
        result = self.auto_play_video(device, video_path, loop=loop_enabled, config=config)
        
        # Start health check if successful
        if result:
            self._start_playback_health_check(device_name, video_path)
            
        # Track result in playback history
        self._track_playback_result(device_name, video_path, result)
        
        # If failed, schedule a retry with exponential backoff
        if not result:
            self._schedule_retry(device_name, video_path, priority)
            
        return result
    
    def _schedule_retry(self, device_name: str, video_path: str, priority: int) -> None:
        """
        Schedule a retry for failed video assignment with exponential backoff
        
        Args:
            device_name: Name of the device
            video_path: Path to the video
            priority: Priority of the assignment
        """
        with self.assignment_lock:
            # Get current retry count
            retry_count = self.video_assignment_retries.get(device_name, 0)
            
            # Check if we've reached max retries
            if retry_count >= MAX_RETRY_ATTEMPTS:
                logger.warning(f"Max retry attempts ({MAX_RETRY_ATTEMPTS}) reached for {device_name}, giving up")
                self.video_assignment_retries[device_name] = 0
                return
                
            # Increment retry count
            self.video_assignment_retries[device_name] = retry_count + 1
            
            # Calculate backoff delay with exponential increase
            delay = RETRY_DELAY_BASE * (2 ** retry_count)
            logger.info(f"Scheduling retry {retry_count+1}/{MAX_RETRY_ATTEMPTS} for {device_name} in {delay}s")
        
        # Schedule retry using a timer
        retry_timer = threading.Timer(
            delay, 
            self.assign_video_to_device,
            args=[device_name, video_path, priority]
        )
        retry_timer.daemon = True
        retry_timer.start()
    
    def _track_playback_result(self, device_name: str, video_path: str, success: bool) -> None:
        """
        Track playback success/failure for analytics and decision-making
        
        Args:
            device_name: Name of the device
            video_path: Path to the video
            success: Whether playback was successful
        """
        with self.monitoring_lock:
            if device_name not in self.video_playback_history:
                self.video_playback_history[device_name] = {
                    "attempts": 0,
                    "successes": 0,
                    "last_attempt": time.time(),
                    "videos": {}
                }
                
            # Update overall stats
            history = self.video_playback_history[device_name]
            history["attempts"] += 1
            if success:
                history["successes"] += 1
            history["last_attempt"] = time.time()
            
            # Update video-specific stats
            if video_path not in history["videos"]:
                history["videos"][video_path] = {
                    "attempts": 0,
                    "successes": 0
                }
                
            video_stats = history["videos"][video_path]
            video_stats["attempts"] += 1
            if success:
                video_stats["successes"] += 1
    
    def _check_scheduled_assignments(self, device_name: str) -> Optional[str]:
        """
        Check if there are any scheduled assignments due for a device
        
        Args:
            device_name: Name of the device to check
            
        Returns:
            Optional[str]: Video path if a scheduled assignment is due, None otherwise
        """
        with self.assignment_lock:
            if device_name not in self.scheduled_assignments:
                return None
                
            assignment = self.scheduled_assignments[device_name]
            scheduled_time = assignment.get("scheduled_time")
            
            if not scheduled_time:
                return None
                
            # Check if scheduled time has passed
            if datetime.now(timezone.utc) >= scheduled_time:
                video_path = assignment.get("video_path")
                # Remove the scheduled assignment
                del self.scheduled_assignments[device_name]
                return video_path
                
        return None
    
    def _start_playback_health_check(self, device_name: str, video_path: str) -> None:
        """
        Start a health check thread for playback monitoring with secure lock ordering
        
        Args:
            device_name: Name of the device to monitor
            video_path: Path to the video being played
        """
        # Stop any existing health check thread first
        self._stop_playback_health_check(device_name)
        
        # Create a new thread for health checking
        health_thread = threading.Thread(
            target=self._playback_health_check_loop,
            args=[device_name, video_path],
            daemon=True
        )
        
        # SECURITY FIX: Use monitoring_lock for health thread management (was video_assignment_lock)
        with self.monitoring_lock:
            self.playback_health_threads[device_name] = {
                "thread": health_thread,
                "active": True,
                "video_path": video_path
            }
        
        # Start the thread
        health_thread.start()
        logger.info(f"Started playback health check for {device_name}")
    
    def _stop_playback_health_check(self, device_name: str) -> None:
        """
        Stop the health check thread for a device with secure lock ordering
        
        Args:
            device_name: Name of the device
        """
        # SECURITY FIX: Use monitoring_lock consistently (was video_assignment_lock)
        with self.monitoring_lock:
            if device_name in self.playback_health_threads:
                # Mark thread as not active
                self.playback_health_threads[device_name]["active"] = False
                logger.info(f"Stopped playback health check for {device_name}")
    
    def auto_play_video(self, device: Device, video_path: str, loop: bool = True, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Play a video on a device with improved error handling
        
        Args:
            device: Device to play the video on
            video_path: Path to the video to play
            loop: Whether to loop the video
            config: Optional device configuration
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Auto-playing video {video_path} on device {device.name}")
            
            # Use device_service if available for stream reuse
            if self.device_service:
                try:
                    # Get device ID from database
                    db_device = self.device_service.get_device_by_name(device.name)
                    if db_device and hasattr(db_device, 'id'):
                        logger.info(f"Using device_service for stream reuse on device {device.name}")
                        return self.device_service.play_video(db_device.id, video_path, loop)
                except Exception as e:
                    logger.warning(f"Failed to use device_service: {e}, falling back to direct play")
            
            # Validate video file
            if not os.path.exists(video_path):
                logger.error(f"Video file not found: {video_path}")
                self.update_device_status(
                    device_name=device.name,
                    status="error",
                    error="Video file not found"
                )
                return False
            
            # Stop any current playback
            if device.is_playing:
                logger.info(f"Stopping current playback on {device.name}")
                device.stop()
                time.sleep(1)  # Give it time to stop
            
            # Get serve IP for streaming
            serve_ip = self.get_serve_ip()
            
            # Set up streaming server
            file_name = os.path.basename(video_path)
            files_dict = {file_name: video_path}
            
            from .twisted_streaming import TwistedStreamingServer
            streaming_server = TwistedStreamingServer.get_instance()
            
            try:
                # Use port range (9000, 9100) to avoid conflicts with other services
                port_range = (9000, 9100)
                urls, server = streaming_server.start_server(
                    files=files_dict,
                    serve_ip=serve_ip,
                    port=None,  # Use dynamic port selection
                    port_range=port_range
                )
            except Exception as e:
                logger.error(f"Failed to start streaming server: {e}")
                self.update_device_status(
                    device_name=device.name,
                    status="error",
                    error=f"Failed to start streaming server: {str(e)}"
                )
                return False
            
            # Store streaming server reference
            device._current_streaming_server = server
            
            # Get video URL and attempt playback
            video_url = urls[file_name]
            
            # Extract port from URL and update device streaming info
            import re
            port_match = re.search(r':(\d+)/', video_url)
            streaming_port = int(port_match.group(1)) if port_match else None
            device.update_streaming_info(video_url, streaming_port)
            
            # Set the video file path on the device for duration detection
            if hasattr(device, 'current_video_path'):
                device.current_video_path = video_path
            
            success = device.play(video_url, loop)
            
            if not success:
                logger.error(f"Failed to play video on device {device.name}")
                streaming_server.stop_server()
                self.update_device_status(
                    device_name=device.name,
                    status="error",
                    error="Failed to play video"
                )
                return False
            
            # Update status on success
            self.update_device_status(
                device_name=device.name,
                status="connected",
                is_playing=True,
                current_video=video_path
            )
            
            # Register session with StreamingSessionRegistry
            from .streaming_registry import StreamingSessionRegistry
            registry = StreamingSessionRegistry.get_instance()
            session = registry.register_session(
                device_name=device.name,
                video_path=video_path,
                server_ip=serve_ip,
                server_port=streaming_port
            )
            logger.debug(f"Registered streaming session {session.session_id} for device {device.name}")
            
            # Start health monitoring
            self._start_playback_health_check(device.name, video_path)
            
            # Trigger overlay sync if configured
            if config and config.get("enable_overlay_sync"):
                sync_video_name = config.get("sync_video_name", os.path.basename(video_path))
                self._trigger_overlay_sync(sync_video_name)
            
            return True
            
        except Exception as e:
            logger.error(f"Error auto-playing video: {e}")
            self.update_device_status(
                device_name=device.name,
                status="error",
                error=str(e)
            )
            return False
    
    def get_device_playback_stats(self, device_name: str) -> Dict[str, Any]:
        """
        Get playback statistics for a device
        
        Args:
            device_name: Name of the device
            
        Returns:
            Dict[str, Any]: Playback statistics
        """
        with self.monitoring_lock:
            if device_name not in self.video_playback_history:
                return {
                    "attempts": 0,
                    "successes": 0,
                    "success_rate": 0,
                    "last_attempt": None,
                    "videos": {}
                }
            
            history = self.video_playback_history[device_name]
            success_rate = (history["successes"] / history["attempts"]) * 100 if history["attempts"] > 0 else 0
            
            return {
                "attempts": history["attempts"],
                "successes": history["successes"],
                "success_rate": success_rate,
                "last_attempt": history["last_attempt"],
                "videos": history["videos"]
            }
    
    def get_scheduled_assignments(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all scheduled video assignments
        
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary of scheduled assignments
        """
        with self.assignment_lock:
            return {k: v.copy() for k, v in self.scheduled_assignments.items()}
    
    def _check_disconnected_devices(self, current_devices: set) -> None:
        """
        Check for disconnected devices
        
        Args:
            current_devices: Set of currently discovered device names
        """
        with self.device_state_lock:
            for device_name in list(self.devices.keys()):
                if device_name not in current_devices:
                    last_seen = self.last_seen.get(device_name)
                    if last_seen is None:
                        logger.debug(f"Skipping disconnect evaluation for {device_name}; missing last_seen")
                        continue
                    time_since_last_seen = time.time() - last_seen
                    
                    # Get device from database
                    db_device = None
                    if self.device_service:
                        try:
                            db_device = self.device_service.get_device_by_name(device_name)
                        except Exception as e:
                            logger.error(f"Error loading device {device_name} from database: {e}")
                    
                    # Check if device should be marked as disconnected
                    grace_period = 10  # Reduced from 30 to 10 seconds
                    extended_grace = 20  # Reduced from 60 to 20 seconds
                    
                    if db_device:
                        updated_at = db_device.updated_at
                        is_playing = db_device.is_playing
                        
                        if updated_at:
                            seconds_since_update = (datetime.now(timezone.utc) - updated_at.replace(tzinfo=timezone.utc)).total_seconds()
                            limit = extended_grace if is_playing else grace_period
                            
                            if seconds_since_update < limit:
                                logger.debug(f"Skipping disconnect for {device_name}, updated {seconds_since_update:.1f}s ago")
                                continue
                    
                    if time_since_last_seen > self.connectivity_timeout:
                        logger.info(f"Device {device_name} not seen for {time_since_last_seen:.1f}s, marking disconnected")
                        self.update_device_status(device_name, "disconnected")
                        
                        # Clean up any active streaming sessions for this device
                        try:
                            from .streaming_registry import StreamingSessionRegistry
                            streaming_registry = StreamingSessionRegistry.get_instance()
                            device_sessions = streaming_registry.get_sessions_for_device(device_name)
                            for session in device_sessions:
                                logger.debug(f"Cleaning up streaming session {session.session_id} for disconnected device {device_name}")
                                streaming_registry.unregister_session(session.session_id)
                        except Exception as e:
                            logger.error(f"Error cleaning up streaming sessions for device {device_name}: {e}")
                        
                        # Clear device from memory if it's been disconnected for too long
                        if time_since_last_seen > self.connectivity_timeout * 2:
                            logger.info(f"Removing device {device_name} from memory due to extended disconnection")
                            
                            # Also clean up any lingering streaming sessions
                            try:
                                from .streaming_registry import StreamingSessionRegistry
                                streaming_registry = StreamingSessionRegistry.get_instance()
                                device_sessions = streaming_registry.get_sessions_for_device(device_name)
                                for session in device_sessions:
                                    logger.debug(f"Cleaning up streaming session {session.session_id} for removed device {device_name}")
                                    streaming_registry.unregister_session(session.session_id)
                            except Exception as e:
                                logger.error(f"Error cleaning up streaming sessions for removed device {device_name}: {e}")
                            
                            self.devices.pop(device_name, None)
                            self.device_status.pop(device_name, None)
                            self.last_seen.pop(device_name, None)
                            self.device_connected_at.pop(device_name, None)

    def stop_discovery(self) -> None:
        """
        Stop discovering DLNA devices on the network
        """
        self.discovery_running = False
        if self.discovery_thread:
            self.discovery_thread.join(timeout=1.0)
            logger.info("Stopped DLNA device discovery")
    
    def pause_discovery(self) -> None:
        """Pause discovery loop"""
        self.discovery_paused = True
        logger.info("Paused DLNA device discovery")
    
    def resume_discovery(self) -> None:
        """Resume discovery loop"""
        if self.discovery_thread and self.discovery_thread.is_alive():
            self.discovery_paused = False
        else:
            self.start_discovery()
        logger.info("Resumed DLNA device discovery")
    
    def get_discovery_status(self) -> dict:
        """Get current discovery status"""
        return {
            "running": self.discovery_running and not self.discovery_paused,
            "paused": self.discovery_paused,
            "interval": self.discovery_interval,
            "devices_discovered": len(self.devices),
            "devices_playing": sum(1 for d in self.devices.values() if d.is_playing)
        }
    
    def update_device_status(self, device_name: str, status: str, is_playing: bool = None, 
                           current_video: str = None, error: str = None) -> None:
        """
        Update a device's status with thread safety
        
        Args:
            device_name: Name of the device
            status: New status
            is_playing: Whether the device is playing (optional)
            current_video: Current video path (optional)
            error: Error message if any (optional)
        """
        with self.device_state_lock:
            if device_name not in self.device_status:
                self.device_status[device_name] = {
                    "reconnect_count": 0,
                    "degraded_count": 0,
                    "offline_count": 0,
                    "last_lost_at": None,
                }
            
            status_dict = self.device_status[device_name]
            now = time.time()
            previous_status = status_dict.get("status")
            previous_online = previous_status in {"connected", "playing"}
            next_online = status in {"connected", "playing"}

            status_dict["status"] = status
            status_dict["last_updated"] = now

            if next_online:
                status_dict["last_seen_at"] = now
                self.last_seen[device_name] = now
                if not previous_online and previous_status is not None:
                    status_dict["reconnect_count"] = int(status_dict.get("reconnect_count", 0)) + 1
            elif status in {"disconnected", "offline"}:
                if previous_status not in {"disconnected", "offline"}:
                    status_dict["offline_count"] = int(status_dict.get("offline_count", 0)) + 1
                    status_dict["last_lost_at"] = now
            elif status in {"streaming_issue", "error"}:
                if previous_status != status:
                    status_dict["degraded_count"] = int(status_dict.get("degraded_count", 0)) + 1
                if status == "error" and status_dict.get("last_lost_at") is None:
                    status_dict["last_lost_at"] = now
            
            if is_playing is not None:
                status_dict["is_playing"] = is_playing
            
            if current_video is not None:
                status_dict["current_video"] = current_video
                
            if error is not None:
                status_dict["last_error"] = error
                status_dict["last_error_time"] = time.time()
                
    def update_device_playback_progress(self, device_name: str, position: str, duration: str, progress: int) -> None:
        """
        Update a device's playback progress information
        
        Args:
            device_name: Name of the device
            position: Current playback position (HH:MM:SS)
            duration: Total video duration (HH:MM:SS)
            progress: Playback progress as a percentage (0-100)
        """
        # Validate inputs
        if not device_name:
            logger.error("Device name is required for updating playback progress")
            return
            
        if not position or not isinstance(position, str):
            logger.error(f"Invalid position format for {device_name}: {position}")
            position = "00:00:00"
            
        if not duration or not isinstance(duration, str):
            logger.error(f"Invalid duration format for {device_name}: {duration}")
            duration = "00:00:00"
            
        if not isinstance(progress, int) or progress < 0 or progress > 100:
            logger.error(f"Invalid progress value for {device_name}: {progress}")
            progress = 0
        
        # First update in-memory status
        with self.device_state_lock:
            if device_name not in self.device_status:
                self.device_status[device_name] = {}
            
            status_dict = self.device_status[device_name]
            status_dict["playback_position"] = position
            status_dict["playback_duration"] = duration
            status_dict["playback_progress"] = progress
            status_dict["last_updated"] = time.time()
            
            # Log the update for debugging
            logger.info(f"Updated in-memory playback progress for {device_name}: {position}/{duration} ({progress}%)")
        
        # Update the database outside the status lock to avoid potential deadlocks
        try:
            # Import here to avoid circular imports
            from database.database import get_db
            from services.device_service import DeviceService
            
            # Create a new database session
            try:
                # Get a new database session
                db_generator = get_db()
                db = next(db_generator)
                
                # Get the device from the database
                device_service = DeviceService(db, self)
                db_device = device_service.get_device_by_name(device_name)
                
                if db_device:
                    # Update the playback progress fields
                    db_device.playback_position = position
                    db_device.playback_duration = duration
                    db_device.playback_progress = progress
                    # Commit the changes
                    db.commit()
                    logger.info(f"Updated playback progress for {device_name} in database: {position}/{duration} ({progress}%)")
                else:
                    logger.warning(f"Device {device_name} not found in database, cannot update playback progress")
                
                # Close the database session
                try:
                    db_generator.close()
                except:
                    pass
                    
            except Exception as db_error:
                logger.error(f"Error creating database session: {db_error}")
                logger.debug(traceback.format_exc())
                
                # Fallback: Try to use device_service if it's already set
                if hasattr(self, 'device_service') and self.device_service:
                    try:
                        # Get the device from the database
                        db_device = self.device_service.get_device_by_name(device_name)
                        if db_device:
                            # Update the playback progress fields
                            db_device.playback_position = position
                            db_device.playback_duration = duration
                            db_device.playback_progress = progress
                            # Commit the changes
                            self.device_service.db.commit()
                            logger.info(f"Updated playback progress for {device_name} using existing device_service: {progress}%")
                        else:
                            logger.warning(f"Device {device_name} not found in database via device_service")
                    except Exception as service_error:
                        logger.error(f"Error updating via device_service: {service_error}")
        except ImportError as import_error:
            logger.error(f"Import error when updating playback progress: {import_error}")
            logger.debug(traceback.format_exc())
        except Exception as e:
            logger.error(f"Error updating device playback progress in database: {e}")
            logger.debug(traceback.format_exc())
            
        # Update the core device object if it exists
        try:
            device = self.get_device(device_name)
            if device and hasattr(device, 'current_position') and hasattr(device, 'duration_formatted') and hasattr(device, 'playback_progress'):
                device.current_position = position
                device.duration_formatted = duration
                device.playback_progress = progress
                logger.debug(f"Updated core device object playback progress for {device_name}")
        except Exception as e:
            logger.error(f"Error updating core device object playback progress: {e}")

    def update_device_playing_state(self, device_name: str, is_playing: bool, video_path: str = None) -> None:
        """
        Update the playing state of a device
        
        Args:
            device_name: Name of the device to update
            is_playing: Whether the device is playing
            video_path: Optional path to the video being played
        """
        device = self.get_device(device_name)
        if not device:
            return
            
        with self.device_state_lock:
            # Update device status
            device.update_playing(is_playing)
            if video_path:
                device.current_video = video_path
                
            # Update status dictionary
            if device_name not in self.device_status: # Initialize if not present
                self.device_status[device_name] = {}
            
            self.device_status[device_name].update({
                "is_playing": is_playing,
                "current_video": video_path if video_path else self.device_status[device_name].get("current_video"),
                "last_updated": time.time()
            })

    def _discover_dlna_devices(self, timeout: float = 2.0, host: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Discover DLNA devices on the network
        
        Args:
            timeout: Timeout for discovery in seconds
            host: Host to bind to for discovery
            
        Returns:
            List[Dict[str, Any]]: List of discovered DLNA devices
        """
        if not host:
            host = "0.0.0.0"
        logger.debug(f"Searching for DLNA devices on {host}")
        
        # Configure socket for SSDP broadcast
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        ttl = struct.pack("B", 4)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        s.bind((host, 0))
        
        # Send SSDP broadcast message
        logger.debug("Sending SSDP broadcast message")
        s.sendto(SSDP_BROADCAST_MSG.encode("UTF-8"), (SSDP_BROADCAST_ADDR, SSDP_BROADCAST_PORT))
        
        # Wait for responses
        logger.debug(f"Waiting for DLNA devices ({timeout} seconds)")
        s.settimeout(timeout)
        
        devices = []
        while True:
            try:
                data, addr = s.recvfrom(1024)
            except socket.timeout:
                break
            
            try:
                info = [a.split(":", 1) for a in data.decode("UTF-8").split("\r\n")[1:]]
                device = dict([(a[0].strip().lower(), a[1].strip()) for a in info if len(a) >= 2])
                devices.append(device)
                logger.debug(f"Received DLNA device broadcast response from {addr}")
            except Exception as e:
                logger.error(f"Error parsing DLNA device response: {e}")
        
        # Filter devices with AVTransport service
        devices_urls = [
            dev["location"]
            for dev in devices
            if "st" in dev and "AVTransport" in dev["st"]
        ]
        
        # Register devices
        registered_devices = []
        for location_url in devices_urls:
            device_info = self._register_dlna_device(location_url)
            if device_info:
                registered_devices.append(device_info)
        
        # Remove duplicates
        registered_devices = self._remove_duplicates(registered_devices)
        
        return registered_devices
    
    def _register_dlna_device(self, location_url: str) -> Optional[Dict[str, Any]]:
        """
        Register a DLNA device from its location URL
        
        Args:
            location_url: Location URL of the DLNA device
            
        Returns:
            Optional[Dict[str, Any]]: Device information if successful, None otherwise
        """
        try:
            logger.debug(f"Registering DLNA device at {location_url}")
            
            # Get device description with timeout
            xml_raw = urllibreq.urlopen(location_url, timeout=5).read().decode("UTF-8")
            xml = re.sub(r"""\s(xmlns="[^"]+"|xmlns='[^']+')""", '', xml_raw, count=1)
            info = ET.fromstring(xml)
            
            # Parse location URL
            location = urllibparse.urlparse(location_url)
            hostname = location.hostname
            port = location.port or 80  # Default to port 80 if not specified
            
            # Find device root
            device_root = info.find("./device")
            if not device_root:
                device_root = info.find(
                    "./device/deviceList/device/"
                    "[deviceType='{0}']".format(UPNP_DEVICE_TYPE)
                )
            
            # Get device information
            friendly_name = self._get_xml_field_text(device_root, "./friendlyName")
            manufacturer = self._get_xml_field_text(device_root, "./manufacturer")
            
            # Try multiple paths to find the control URL
            service_paths = [
                "./serviceList/service/[serviceType='{0}']/controlURL".format(UPNP_SERVICE_TYPE),
                "./serviceList/service/controlURL",
                ".//service/[serviceType='{0}']/controlURL".format(UPNP_SERVICE_TYPE),
                ".//service/controlURL"
            ]
            
            action_url_path = None
            for path in service_paths:
                action_url_path = self._get_xml_field_text(device_root, path)
                if action_url_path:
                    break
            
            # Build action URL
            if action_url_path is not None:
                # Make sure action_url_path starts with a slash
                if not action_url_path.startswith('/'):
                    action_url_path = '/' + action_url_path
                
                # Build the full action URL
                action_url = f"http://{hostname}:{port}{action_url_path}"
                logger.debug(f"Found action URL: {action_url}")
            else:
                # Fallback: try to construct a default action URL
                action_url = f"http://{hostname}:{port}/AVTransport/Control"
                logger.warning(f"No action URL found, using default: {action_url}")
            
            # Create device information with device_name set to friendly_name
            device = {
                "device_name": friendly_name,
                "type": "dlna",
                "location": location_url,
                "hostname": hostname,
                "manufacturer": manufacturer,
                "friendly_name": friendly_name,
                "action_url": action_url,
                "st": UPNP_SERVICE_TYPE
            }
            
            logger.info(f"Registered DLNA device: {friendly_name} with action URL: {action_url}")
            return device
        except Exception as e:
            logger.error(f"Error registering DLNA device at {location_url}: {e}")
            return None
    
    def _get_xml_field_text(self, xml_root, query):
        """
        Get text from an XML field
        
        Args:
            xml_root: XML root element
            query: XPath query
            
        Returns:
            str: Text from the XML field or None if not found
        """
        result = None
        if xml_root:
            node = xml_root.find(query)
            result = node.text if node is not None else None
        return result
    
    def _remove_duplicates(self, devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate devices
        
        Args:
            devices: List of devices
            
        Returns:
            List[Dict[str, Any]]: List of unique devices
        """
        seen = set()
        result_devices = []
        for device in devices:
            device_str = str(device)
            if device_str not in seen:
                result_devices.append(device)
                seen.add(device_str)
        return result_devices

    def _start_streaming_server(self, video_path: str, device_name: str, port_range: Optional[Tuple[int, int]] = None) -> Tuple[str, Any]:
        """
        Start a streaming server for a video file
        
        Args:
            video_path: Path to the video file to stream
            device_name: Name of the device to stream to
            port_range: Optional tuple of (min_port, max_port) for streaming server
            
        Returns:
            Tuple[str, Any]: URL of the video and server instance
        """
        try:
            # Get the serve IP
            serve_ip = self.get_serve_ip()
            
            # Create file dictionary for streaming server
            file_name = os.path.basename(video_path)
            files_dict = {file_name: video_path}
            
            # Start the streaming server
            from .twisted_streaming import TwistedStreamingServer
            streaming_server = TwistedStreamingServer.get_instance()
            # Use port range (9000-9100) to avoid conflicts with other services
            if port_range is None:
                port_range = (9000, 9100)
                
            urls, server = streaming_server.start_server(
                files=files_dict,
                serve_ip=serve_ip,
                port=None,  # Use dynamic port selection
                port_range=port_range
            )
            
            # Return the URL for the video
            return urls[file_name], server
        except Exception as e:
            logger.error(f"Error starting streaming server: {e}")
            raise
    
    def _trigger_overlay_sync(self, video_name: str):
        """
        Trigger overlay sync for the given video name
        
        Args:
            video_name: Name of the video to sync
        """
        try:
            import requests
            response = requests.post(
                "http://localhost:8000/api/overlay/sync",
                params={
                    "triggered_by": "dlna_auto_play",
                    "video_name": video_name
                },
                timeout=2  # Short timeout to not block
            )
            if response.status_code == 200:
                logger.info(f"Triggered overlay sync for video: {video_name}")
            else:
                logger.warning(f"Failed to trigger overlay sync: {response.status_code}")
        except Exception as e:
            logger.error(f"Failed to sync overlays: {e}")
            # Don't fail the operation if sync fails
    
    def _process_airplay_casting(self, device_name: str, config: Dict[str, Any]):
        """
        Process airplay casting for a device configured in airplay mode
        Since the device is DLNA, we'll stream the overlay page directly
        
        Args:
            device_name: Name of the device
            config: Device configuration
        """
        try:
            airplay_url = config.get("airplay_url")
            if not airplay_url:
                logger.error(f"Device {device_name} configured for airplay but no airplay_url provided")
                return
            
            # Get the device
            device = self.get_device(device_name)
            if not device:
                logger.error(f"Device {device_name} not found")
                return
            
            # For DLNA devices, we'll play the URL directly
            # The overlay page at the URL will be displayed
            logger.info(f"Starting overlay display on {device_name} via DLNA: {airplay_url}")
            
            # Use auto_play_video with the URL
            # Note: This assumes the DLNA device can render web content
            # If it can't, we may need to use a video stream instead
            success = self.auto_play_video(device, airplay_url, loop=True)
            
            if success:
                logger.info(f"Successfully started overlay display on {device_name}")
                self.update_device_status(
                    device_name=device_name,
                    status="playing",
                    current_uri=airplay_url,
                    playback_mode="airplay"
                )
            else:
                # If direct URL doesn't work, try using a black video as fallback
                logger.warning(f"Direct URL playback failed, trying fallback video")
                fallback_video = config.get("video_file")
                if fallback_video and os.path.exists(fallback_video):
                    success = self.auto_play_video(device, fallback_video, loop=True)
                    if success:
                        logger.info(f"Started fallback video on {device_name}")
                        self.update_device_status(
                            device_name=device_name,
                            status="playing",
                            current_uri=fallback_video,
                            playback_mode="video"
                        )
                    else:
                        logger.error(f"Failed to play fallback video on {device_name}")
                        self.update_device_status(
                            device_name=device_name,
                            status="error",
                            error="Failed to start playback"
                        )
                else:
                    logger.error(f"No fallback video available for {device_name}")
                    self.update_device_status(
                        device_name=device_name,
                        status="error",
                        error="Failed to display overlay"
                    )
        except Exception as e:
            logger.error(f"Error processing airplay casting for {device_name}: {e}")
            self.update_device_status(
                device_name=device_name,
                status="error",
                error=str(e)
            )

    def get_serve_ip(self):
        """
        Return the LAN IP address used for streaming. Checks STREAMING_SERVE_IP env var first.
        """
        import os
        import socket
        env_ip = os.environ.get("STREAMING_SERVE_IP")
        if env_ip:
            logger.info(f"Using STREAMING_SERVE_IP from environment: {env_ip}")
            if env_ip.startswith("127.") or env_ip == "localhost":
                logger.error("STREAMING_SERVE_IP is set to localhost/127.0.0.1, which is not valid for DLNA streaming.")
                raise RuntimeError("STREAMING_SERVE_IP must be a LAN IP, not localhost/127.0.0.1")
            return env_ip
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            if ip.startswith("127."):
                raise Exception("Auto-detected IP is localhost, not valid for DLNA streaming.")
            logger.info(f"Auto-detected LAN IP for streaming: {ip}")
            return ip
        except Exception as e:
            logger.error(f"Could not auto-detect LAN IP for streaming: {e}")
            raise RuntimeError("Could not determine LAN IP for streaming. Set STREAMING_SERVE_IP env variable.")
        finally:
            s.close()

# Add this at the end of the file
# Singleton instance for DeviceManager
_device_manager_instance = None

def get_device_manager() -> DeviceManager:
    """
    Get a singleton instance of DeviceManager
    
    Returns:
        DeviceManager: The singleton DeviceManager instance
    """
    global _device_manager_instance
    if _device_manager_instance is None:
        _device_manager_instance = DeviceManager()
    return _device_manager_instance
