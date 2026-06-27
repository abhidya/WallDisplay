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

if sys.version_info.major == 3:
    import urllib.request as urllibreq
    import urllib.parse as urllibparse
else:
    import urllib2 as urllibreq
    import urlparse as urllibparse

from .device import Device
from .config_service import ConfigService
from .streaming_registry import StreamingSessionRegistry
from web.backend.services.device_inventory_service import DeviceInventoryService
from web.backend.services.device_lifecycle_service import DeviceLifecycleService
from web.backend.services.playback_intent_service import PlaybackIntentService
from web.backend.services.playback_monitoring_service import PlaybackMonitoringService
from web.backend.services.playback_orchestrator import PlaybackOrchestrator
from web.backend.services.runtime_registry_service import RuntimeRegistryService
from web.backend.services.discovery_coordinator import DiscoveryCoordinator
from web.backend.discovery.discovery_manager import DiscoveryManager

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
    def __init__(
        self,
        *,
        config_service: Optional[ConfigService] = None,
        streaming_registry: Optional[StreamingSessionRegistry] = None,
        device_inventory: Optional[DeviceInventoryService] = None,
        runtime_registry: Optional[RuntimeRegistryService] = None,
        playback_intent_service: Optional[PlaybackIntentService] = None,
        playback_monitoring_service: Optional[PlaybackMonitoringService] = None,
    ):
        """Initialize the device manager with consolidated locks for deadlock prevention"""
        # SECURITY FIX: Consolidated lock architecture (8 locks → 4 locks)
        # Hierarchical lock ordering: device_state_lock → assignment_lock → monitoring_lock → statistics_lock
        
        # Level 1: Core device and status state (consolidates device_lock + status_lock + assigned_videos_lock)
        self.device_state_lock = threading.RLock()  # RLock allows reentrant access for same thread
        self.device_lock_timeout = 5.0  # seconds
        
        # Level 2: Assignment coordination (consolidates video_assignment_lock + scheduled_assignments_lock)
        self.assignment_lock = threading.Lock()
        
        # Level 4: Statistics collection (separate for performance - read-heavy operations)
        self.statistics_lock = threading.Lock()
        
        # Core device tracking - protected by device_state_lock
        self.device_inventory = device_inventory or DeviceInventoryService()
        self.runtime_registry = runtime_registry or RuntimeRegistryService()
        
        # Assignment tracking - protected by assignment_lock / device_state_lock by caller
        self.playback_intent_service = playback_intent_service or PlaybackIntentService()
        self.playback_orchestrator = PlaybackOrchestrator(self)
        self.playback_monitoring_service = playback_monitoring_service or PlaybackMonitoringService(self)
        self.device_lifecycle_service = DeviceLifecycleService(
            owner=self,
            device_inventory=self.device_inventory,
            runtime_registry=self.runtime_registry,
            playback_intent_service=self.playback_intent_service,
            playback_monitoring_service=self.playback_monitoring_service,
            device_state_lock=self.device_state_lock,
            assignment_lock=self.assignment_lock,
            acquire_device_lock=self._acquire_device_lock,
            release_device_lock=self._release_device_lock,
        )
        self.discovery_coordinator = DiscoveryCoordinator(self)
        
        # Get config service and streaming registry
        self.config_service = config_service or ConfigService.get_instance()
        self.streaming_registry = streaming_registry or StreamingSessionRegistry.get_instance()
        self.streaming_registry.register_health_check_handler(self._handle_streaming_issue)
        
        # Discovery thread attributes
        self.discovery_thread = None
        self.discovery_running = False
        self.discovery_paused = False
        self.discovery_interval = 10  # Seconds between discovery cycles
        self.max_retry_attempts = MAX_RETRY_ATTEMPTS
        self.retry_delay_base = RETRY_DELAY_BASE
        self.playback_health_check_interval = PLAYBACK_HEALTH_CHECK_INTERVAL
        self.connectivity_timeout = 30  # Seconds to wait before considering a device offline

    @property
    def devices(self):
        return self.device_inventory.devices

    @property
    def device_status(self):
        return self.runtime_registry.device_status

    @property
    def last_seen(self):
        return self.runtime_registry.last_seen

    @property
    def device_connected_at(self):
        return self.runtime_registry.device_connected_at

    @property
    def assigned_videos(self):
        return self.playback_intent_service.assigned_videos

    @property
    def video_assignment_priority(self):
        return self.playback_intent_service.video_assignment_priority

    @property
    def video_assignment_retries(self):
        return self.playback_intent_service.video_assignment_retries

    @property
    def scheduled_assignments(self):
        return self.playback_intent_service.scheduled_assignments

    @property
    def device_assignment_queue(self):
        return self.playback_intent_service.device_assignment_queue

    @property
    def monitoring_lock(self):
        return self.playback_monitoring_service.monitoring_lock

    @property
    def playback_health_threads(self):
        return self.playback_monitoring_service.playback_health_threads

    @property
    def video_playback_history(self):
        return self.playback_monitoring_service.video_playback_history

    @property
    def playback_stats(self):
        return self.playback_monitoring_service.playback_stats

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
            from web.backend.services.app_runtime import get_device_runtime

            get_device_runtime().owner.handle_streaming_issue(session)
        except Exception as e:
            device_name = getattr(session, "device_name", "<unknown>")
            logger.error(f"Error handling streaming issue for {device_name}: {e}")
            self.update_device_status(device_name=device_name, status="error", error=str(e))

    def _playback_health_check_loop(self, device_name: str, video_path: str) -> None:
        try:
            from web.backend.services.app_runtime import get_device_runtime

            get_device_runtime().owner.playback_monitoring_service.run_health_check_loop(device_name, video_path)
        except Exception:
            self.playback_monitoring_service.run_health_check_loop(device_name, video_path)
    
    def get_devices(self) -> List[Device]:
        """
        Get all registered devices
        
        Returns:
            List[Device]: List of all registered devices
        """
        return self.device_lifecycle_service.get_devices()
    
    def get_device(self, device_name: str) -> Optional[Device]:
        """
        Get a device by name
        
        Args:
            device_name: Name of the device to get
            
        Returns:
            Optional[Device]: The device if found, None otherwise
        """
        return self.device_lifecycle_service.get_device(device_name)
    
    def register_device(self, device_info: Dict[str, Any]) -> Optional[Device]:
        """
        Register a device
        
        Args:
            device_info: Device information
            
        Returns:
            Optional[Device]: The registered device if successful, None otherwise
        """
        return self.device_lifecycle_service.register_device(device_info)
    
    def cleanup_device_state(self, device_name: str):
        """
        Clean up all state for a device
        
        Args:
            device_name: Name of the device to clean up
        """
        self.device_lifecycle_service.cleanup_device_state(device_name)
    
    def unregister_device(self, device_name: str) -> bool:
        """
        Unregister a device with secure hierarchical lock ordering
        
        Args:
            device_name: Name of the device to unregister
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.device_lifecycle_service.unregister_device(device_name)
    
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
                    device = self.device_inventory.get(device_name)
                    if device:
                        loaded_devices.append(device)
            
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
                devices_config = [device.device_info.copy() for device in self.device_inventory.values()]
            
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
        self.discovery_coordinator.start()

    def _discovery_loop(self) -> None:
        self.discovery_coordinator.run_loop()

    def _process_device_video_assignment(self, device_name: str, is_new_device: bool, is_changed_device: bool) -> None:
        self.playback_orchestrator.process_discovered_device(
            device_name=device_name,
            is_new_device=is_new_device,
            is_changed_device=is_changed_device,
        )

    def _process_device_overlay_cast(self, device_name: str, db_device) -> bool:
        return self.playback_orchestrator.process_overlay_cast(device_name, db_device)

    def _resolve_discovery_device_id(self, device_name: str, hostname: Optional[str]) -> Optional[str]:
        try:
            from web.backend.services.app_runtime import get_device_runtime

            discovery_manager = get_device_runtime().discovery_manager
        except Exception:
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
        return self.playback_orchestrator.apply_video_assignment(
            device_name=device_name,
            video_path=video_path,
            priority=priority,
            schedule_time=schedule_time,
        )
    
    def _schedule_retry(self, device_name: str, video_path: str, priority: int) -> None:
        self.playback_orchestrator.schedule_retry(device_name, video_path, priority)
    
    def _track_playback_result(self, device_name: str, video_path: str, success: bool) -> None:
        try:
            from web.backend.services.app_runtime import get_device_runtime

            get_device_runtime().track_playback_result(device_name, video_path, success)
        except Exception:
            self.playback_monitoring_service.track_playback_result(device_name, video_path, success)
    
    def _check_scheduled_assignments(self, device_name: str) -> Optional[str]:
        """
        Check if there are any scheduled assignments due for a device
        
        Args:
            device_name: Name of the device to check
            
        Returns:
            Optional[str]: Video path if a scheduled assignment is due, None otherwise
        """
        with self.assignment_lock:
            return self.playback_intent_service.get_due_scheduled_video(
                device_name,
                datetime.now(timezone.utc),
            )
    
    def _start_playback_health_check(self, device_name: str, video_path: str) -> None:
        """
        Start a health check thread for playback monitoring with secure lock ordering
        
        Args:
            device_name: Name of the device to monitor
            video_path: Path to the video being played
        """
        try:
            from web.backend.services.app_runtime import get_device_runtime

            get_device_runtime().start_playback_health_check(device_name, video_path)
        except Exception:
            self.playback_monitoring_service.start_health_check(device_name, video_path)
    
    def _stop_playback_health_check(self, device_name: str) -> None:
        """
        Stop the health check thread for a device with secure lock ordering
        
        Args:
            device_name: Name of the device
        """
        try:
            from web.backend.services.app_runtime import get_device_runtime

            get_device_runtime().stop_playback_health_check(device_name)
        except Exception:
            self.playback_monitoring_service.stop_health_check(device_name)
    
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
            from web.backend.services.app_runtime import get_device_runtime

            runtime = get_device_runtime().owner
            playback_service = getattr(runtime, "runtime_playback_service", None)
            if playback_service is not None:
                return playback_service.auto_play_video(
                    device,
                    video_path,
                    loop=loop,
                    config=config,
                )
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
        try:
            from web.backend.services.app_runtime import get_device_runtime

            return get_device_runtime().get_device_playback_stats(device_name)
        except Exception:
            return self.playback_monitoring_service.get_device_playback_stats(device_name)
    
    def get_scheduled_assignments(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all scheduled video assignments
        
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary of scheduled assignments
        """
        with self.assignment_lock:
            return self.playback_intent_service.get_scheduled_assignments_copy()
    
    def _check_disconnected_devices(self, current_devices: set) -> None:
        self.discovery_coordinator.evaluate_disconnected_devices(current_devices)

    def stop_discovery(self) -> None:
        """
        Stop discovering DLNA devices on the network
        """
        self.discovery_coordinator.stop()
    
    def pause_discovery(self) -> None:
        """Pause discovery loop"""
        self.discovery_coordinator.pause()
    
    def resume_discovery(self) -> None:
        """Resume discovery loop"""
        self.discovery_coordinator.resume()
    
    def get_discovery_status(self) -> dict:
        """Get current discovery status"""
        return self.discovery_coordinator.get_status()
    
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
            self.runtime_registry.update_status(
                device_name=device_name,
                status=status,
                is_playing=is_playing,
                current_video=current_video,
                error=error,
            )
                
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
            self.runtime_registry.update_playback_progress(device_name, position, duration, progress)
            
            # Log the update for debugging
            logger.info(f"Updated in-memory playback progress for {device_name}: {position}/{duration} ({progress}%)")
        
        # Update the database outside the status lock to avoid potential deadlocks.
        try:
            from web.backend.services.app_runtime import get_device_runtime

            persisted = get_device_runtime().owner.persist_runtime_playback_progress(
                device_name=device_name,
                position=position,
                duration=duration,
                progress=progress,
            )
            if persisted:
                logger.info(f"Updated playback progress for {device_name} in database: {position}/{duration} ({progress}%)")
            else:
                logger.warning(f"Device {device_name} not found in database, cannot update playback progress")
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
        self.device_lifecycle_service.update_device_playing_state(device_name, is_playing, video_path)

    def _discover_dlna_devices(self, timeout: float = 2.0, host: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.discovery_coordinator.discover_dlna_devices(timeout=timeout, host=host)
    
    def _register_dlna_device(self, location_url: str) -> Optional[Dict[str, Any]]:
        return self.discovery_coordinator.register_dlna_device(location_url)
    
    def _get_xml_field_text(self, xml_root, query):
        return self.discovery_coordinator._get_xml_field_text(xml_root, query)
    
    def _remove_duplicates(self, devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self.discovery_coordinator.remove_duplicates(devices)

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
            from web.backend.services.app_runtime import get_device_runtime

            get_device_runtime().owner.trigger_overlay_sync(video_name)
        except Exception as e:
            logger.error(f"Failed to sync overlays: {e}")
            # Don't fail the operation if sync fails
    
    def _process_airplay_casting(self, device_name: str, config: Dict[str, Any]):
        try:
            from web.backend.services.app_runtime import get_device_runtime

            get_device_runtime().owner.process_airplay_casting(device_name, config)
        except Exception as exc:
            logger.error("Error delegating airplay casting for %s: %s", device_name, exc)
            self.update_device_status(device_name=device_name, status="error", error=str(exc))

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

def get_device_manager(
    *,
    config_service: Optional[ConfigService] = None,
    streaming_registry: Optional[StreamingSessionRegistry] = None,
    device_inventory: Optional[DeviceInventoryService] = None,
    runtime_registry: Optional[RuntimeRegistryService] = None,
    playback_intent_service: Optional[PlaybackIntentService] = None,
    playback_monitoring_service: Optional[PlaybackMonitoringService] = None,
) -> DeviceManager:
    """
    Get a singleton instance of DeviceManager
    
    Returns:
        DeviceManager: The singleton DeviceManager instance
    """
    global _device_manager_instance
    if _device_manager_instance is None:
        _device_manager_instance = DeviceManager(
            config_service=config_service,
            streaming_registry=streaming_registry,
            device_inventory=device_inventory,
            runtime_registry=runtime_registry,
            playback_intent_service=playback_intent_service,
            playback_monitoring_service=playback_monitoring_service,
        )
    return _device_manager_instance
