import os
import pkgutil
import sys
import logging
import traceback
import time
import socket
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from xml.sax.saxutils import escape as xmlescape

if sys.version_info.major == 3:
    import urllib.request as urllibreq
else:
    import urllib2 as urllibreq

from .device import Device

logger = logging.getLogger(__name__)

# Delay between retries in seconds
RETRY_DELAY = 2

class DLNADevice(Device):
    """
    Implementation of a DLNA device
    """
    def __init__(self, device_info: Dict[str, Any]):
        super().__init__(device_info)
        self.type = "dlna"
        self.action_url = device_info.get("action_url")
        self.hostname = device_info.get("hostname")
        self.st = device_info.get("st", "urn:schemas-upnp-org:service:AVTransport:1")
        self.max_retries = 3  # Number of retries for DLNA actions
        
        # Thread management
        self._thread_lock = threading.Lock()
        self._loop_enabled = False
        self._loop_thread = None  # Explicitly initialize loop_thread
        self._stop_event = threading.Event()  # Event for clean thread shutdown
        self._last_activity_time = None
        self._inactivity_timeout = 90  # Default seconds of inactivity before considering playback stalled
        self._dynamic_inactivity_timeout = True  # Enable dynamic timeout based on video duration
        self._zero_position_count = 0  # Track consecutive times position is at 00:00:00
        
        # Video playback attributes
        self.current_video_duration = None  # Duration of current video in seconds
        self.current_video_path = None  # Local file path of current video
        
        # Playback progress tracking
        self.current_position = "00:00:00"
        self.duration_formatted = "00:00:00"
        self.playback_progress = 0
        
        # Get device manager reference
        from services.app_runtime import get_device_runtime
        self.runtime = get_device_runtime()
        
        # Try to infer missing fields
        if not self.action_url and self.hostname:
            # Default action URL if not provided
            port = 80  # Default port
            if "location" in device_info:
                try:
                    location = urllibreq.urlparse(device_info["location"])
                    if location.port:
                        port = location.port
                except Exception:
                    pass
            
            self.action_url = f"http://{self.hostname}:{port}/AVTransport/Control"
            logger.warning(f"Inferred action_url for {self.name}: {self.action_url}")
        
        # Log warnings for missing fields but don't raise exceptions during discovery
        if not self.action_url:
            logger.error(f"DLNA device {self.name} missing action_url")
        
        if not self.hostname:
            logger.error(f"DLNA device {self.name} missing hostname")
    
    def play(self, video_url: str, loop: bool = False, port_range: Optional[Tuple[int, int]] = (9000, 9100)) -> bool:
        """
        Play a video on the DLNA device
        
        Args:
            video_url: URL of the video to play
            loop: Whether to loop the video
            port_range: Optional tuple of (min_port, max_port) for streaming server
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Playing {video_url} on DLNA device {self.name} (loop={loop})")
            
            # Store the current video URL
            self.current_video = video_url
            
            # Create metadata for the video
            metadata = self._create_didl_metadata(video_url)
            
            # Set up AV transport
            data = {
                "CurrentURI": video_url,
                "CurrentURIMetaData": metadata
            }
            if not self._send_dlna_action(data, "SetAVTransportURI"):
                logger.error(f"Failed to set AV transport URI for {self.name}")
                return False
                
            # Start playback
            if not self._send_dlna_action(None, "Play"):
                logger.error(f"Failed to start playback on {self.name}")
                return False
                
            # Update device status
            self.update_status("playing")
            self.update_playing(True)
            
            # Reset stop event and loop flag for new playback
            with self._thread_lock:
                self._stop_event.clear()
                # If we're starting a new playback with loop, ensure loop is enabled
                # This prevents race conditions with stop() method
                if loop:
                    self._loop_enabled = True
                else:
                    self._loop_enabled = False
            
            # Set up loop monitoring if needed
            if loop:
                self._setup_loop_monitoring_v2(video_url) # Changed to v2
            
            return True
        except Exception as e:
            logger.error(f"Error playing video on {self.name}: {e}")
            return False
    
    def _try_play_with_config(self, video_data: Dict[str, Any], video_url: str, loop: bool, is_retry: bool = False) -> bool:
        """
        Try to play a video with a specific configuration
        
        Args:
            video_data: Video data dictionary 
            video_url: URL of the video
            loop: Whether to loop the video
            is_retry: Whether this is a retry attempt
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Send SetAVTransportURI command
            logger.info(f"Setting video URI on device {self.name}")
            self._send_dlna_action(video_data, "SetAVTransportURI")
            
            # Send Play command
            logger.info(f"Sending play command to device {self.name}")
            self._send_dlna_action(video_data, "Play")
            
            # Reset last activity time
            self._last_activity_time = time.time()
            
            # Wait a bit to check if play was successful
            if is_retry:
                logger.info(f"Waiting 2 seconds to check play status...")
                time.sleep(2)
                
                # Check if actually playing
                transport_info = self._get_transport_info()
                state = transport_info.get("CurrentTransportState", "UNKNOWN")
                
                if state != "PLAYING":
                    logger.warning(f"Play command sent but device not playing (state: {state})")
                    return False
            
            # If loop is enabled, we need to set up a background thread to monitor playback
            # and restart the video when it ends
            if loop:
                logger.info(f"Loop enabled for {self.name}, setting up background monitoring")
                self._setup_loop_monitoring_v2(video_url) # Changed to v2
            
            # Update device status
            self.update_status("connected")
            self.update_video(video_url)
            self.update_playing(True)
            
            logger.info(f"Successfully started playing video on {self.name}")
            return True
        except Exception as e:
            logger.error(f"Error in _try_play_with_config for {self.name}: {e}")
            return False
    
    # This is the first version of _setup_loop_monitoring, which seems to be the problematic one
    def _setup_loop_monitoring(self, video_url: str) -> None:
        """
        Set up monitoring thread for video looping
        
        Args:
            video_url: URL of the video to monitor
        """
        logger.info(f"[{self.name}] Setting up loop monitoring (v1) for {video_url}")
        
        with self._thread_lock:
            # Initialize thread attribute if it doesn't exist
            if not hasattr(self, '_loop_thread'):
                self._loop_thread = None
                
            # Check if thread exists and is alive before trying to stop it
            thread_is_running = False
            if self._loop_thread is not None:
                try:
                    # First check if the thread object exists and has the is_alive attribute
                    if hasattr(self._loop_thread, 'is_alive'):
                        # Then check if the thread is alive
                        thread_is_running = self._loop_thread.is_alive()
                        if thread_is_running:
                            logger.debug(f"[{self.name}] Stopping existing loop thread (v1)")
                            self._loop_enabled = False
                            # Wait short time for thread to exit
                            self._loop_thread.join(timeout=2.0)
                except (AttributeError, TypeError, RuntimeError) as e:
                    logger.warning(f"[{self.name}] Error checking thread status (v1): {e}")
                    # Reset thread to None if there was an error
                    self._loop_thread = None
            
            # Enable looping
            self._loop_enabled = True
            self._last_activity_time = time.time()
            
            # Define monitoring function
            def monitor_and_restart_v1(): # Renamed to v1
                try:
                    logger.info(f"[{self.name}] Loop monitoring thread started (v1)")
                    current_video = video_url
                    # ... (rest of the original monitor_and_restart logic) ...
                    # For brevity, assuming the original logic of this version is here
                    # This version had issues with duration and restart logic
                    while True:
                        with self._thread_lock:
                            if not self._loop_enabled:
                                logger.info(f"[{self.name}] Loop monitoring (v1) flag is False, exiting thread.")
                                break
                        logger.debug(f"[{self.name}] Loop v1 still active, sleeping...")
                        time.sleep(10) # Simplified for this example
                    logger.info(f"[{self.name}] Loop monitoring thread (v1) finished.")
                except Exception as e:
                    logger.error(f"[{self.name}] Error in loop monitoring thread (v1): {e}")
                    logger.error(traceback.format_exc())
            
            # Start monitoring thread
            try:
                self._loop_thread = threading.Thread(target=monitor_and_restart_v1, name=f"loop-monitor-v1-{self.name}")
                self._loop_thread.daemon = True
                self._loop_thread.start()
                logger.info(f"[{self.name}] Loop monitoring thread (v1) started successfully.")
            except Exception as e:
                logger.error(f"[{self.name}] Error starting loop monitoring thread (v1): {e}")
                logger.error(traceback.format_exc())
                self._loop_thread = None
                self._loop_enabled = False

    def _get_position_info(self) -> Dict[str, str]:
        """
        Get the position info from the device
        
        Returns:
            Dict[str, str]: Position info including current time and duration
        """
        try:
            # Send GetPositionInfo action
            response = self._send_dlna_action_with_response(None, "GetPositionInfo")
            
            # Parse the response
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response)
            
            # Extract the relevant information
            rel_time = root.find(".//{urn:schemas-upnp-org:service:AVTransport:1}RelTime")
            abs_time = root.find(".//{urn:schemas-upnp-org:service:AVTransport:1}AbsTime")
            track_duration = root.find(".//{urn:schemas-upnp-org:service:AVTransport:1}TrackDuration")
            
            return {
                "RelTime": rel_time.text if rel_time is not None else "NOT_IMPLEMENTED",
                "AbsTime": abs_time.text if abs_time is not None else "NOT_IMPLEMENTED",
                "TrackDuration": track_duration.text if track_duration is not None else "NOT_IMPLEMENTED"
            }
        except Exception as e:
            logger.error(f"Error getting position info for {self.name}: {e}")
            return {"RelTime": "UNKNOWN", "AbsTime": "UNKNOWN", "TrackDuration": "UNKNOWN"}
    
    def _get_transport_info(self) -> Dict[str, str]:
        """
        Get the transport info from the device
        
        Returns:
            Dict[str, str]: Transport info
        """
        try:
            # Send GetTransportInfo action
            response = self._send_dlna_action_with_response(None, "GetTransportInfo")
            
            # Parse the response
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response)
            
            # Extract the transport state
            transport_state = root.find(".//{urn:schemas-upnp-org:service:AVTransport:1}CurrentTransportState")
            transport_status = root.find(".//{urn:schemas-upnp-org:service:AVTransport:1}CurrentTransportStatus")
            
            state = transport_state.text if transport_state is not None else "UNKNOWN"
            status = transport_status.text if transport_status is not None else "UNKNOWN"
            
            # If we got a non-null state response, update the last activity time
            if state != "UNKNOWN":
                with self._thread_lock:
                    self._last_activity_time = time.time()
            
            return {
                "CurrentTransportState": state,
                "CurrentTransportStatus": status
            }
        except Exception as e:
            logger.error(f"Error getting transport info for {self.name}: {e}")
            return {"CurrentTransportState": "UNKNOWN", "CurrentTransportStatus": "UNKNOWN"}
    
    def _send_dlna_action_with_response(self, data: Optional[Dict[str, Any]], action: str) -> str:
        """
        Send a DLNA action to the device and return the response
        
        Args:
            data: Data to send with the action
            action: Action to send
            
        Returns:
            str: Response from the device
        """
        logger.debug(f"Sending DLNA action {action} to device {self.name} with response")
        
        # Check if action_url is available
        if not self.action_url:
            raise ValueError(f"Cannot send action to device {self.name}: action_url is missing")
        
        # Get the action template
        try:
            template_data = pkgutil.get_data(
                "nanodlna", f"templates/action-{action}.xml")
            if template_data is not None:
                action_data = template_data.decode("UTF-8")
            else:
                # If template_data is None, try to find it in our package
                template_path = os.path.join(os.path.dirname(__file__), "templates", f"action-{action}.xml")
                if os.path.exists(template_path):
                    with open(template_path, "r") as f:
                        action_data = f.read()
                else:
                    raise FileNotFoundError(f"Template for action {action} not found")
        except (ImportError, FileNotFoundError):
            # If the template is not found in the nanodlna package, try to find it in our package
            template_path = os.path.join(os.path.dirname(__file__), "templates", f"action-{action}.xml")
            if os.path.exists(template_path):
                with open(template_path, "r") as f:
                    action_data = f.read()
            else:
                raise FileNotFoundError(f"Template for action {action} not found")
        
        # Format the action data with the provided data
        if data:
            action_data = action_data.format(**data)
        action_data = action_data.encode("UTF-8")
        
        # Prepare headers
        headers = {
            "Content-Type": "text/xml; charset=\"utf-8\"",
            "Content-Length": f"{len(action_data)}",
            "Connection": "close",
            "SOAPACTION": f"\"{self.st}#{action}\""
        }
        
        # Send the request with retry logic
        last_exception = None
        for retry in range(self.max_retries):
            try:
                logger.debug(f"Sending DLNA request to {self.action_url} (attempt {retry+1}/{self.max_retries})")
                request = urllibreq.Request(self.action_url, action_data, headers)
                with urllibreq.urlopen(request) as response:
                    response_data = response.read().decode("UTF-8")
                logger.debug(f"DLNA request sent successfully")
                return response_data
            except Exception as e:
                last_exception = e
                logger.warning(f"DLNA request failed (attempt {retry+1}/{self.max_retries}): {e}")
                error_text = str(e)
                if "No route to host" in error_text or "Errno 65" in error_text:
                    if self._recover_control_route():
                        logger.info("Recovered control route for %s, retrying %s", self.name, action)
                if retry < self.max_retries - 1:
                    logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                    time.sleep(RETRY_DELAY)
        
        # If we get here, all retries failed
        logger.error(f"DLNA request failed after {self.max_retries} attempts")
        if last_exception:
            raise last_exception
        return ""

    def stop(self) -> bool:
        """
        Stop playback on the DLNA device
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Stopping playback on DLNA device {self.name}")
            
            # Safely handle thread cleanup
            loop_thread_to_join = None
            with self._thread_lock:
                self._loop_enabled = False # Signal the loop thread to stop
                self._stop_event.set()  # Signal stop event
                
                # Reset activity timer
                self._last_activity_time = None
                
                # Safely get thread reference
                if hasattr(self, '_loop_thread') and self._loop_thread is not None:
                    loop_thread_to_join = self._loop_thread # Get a reference before nullifying
                    self._loop_thread = None # Nullify to prevent new starts while stopping

            # Join thread outside the lock to avoid deadlock
            if loop_thread_to_join is not None:
                try:
                    if hasattr(loop_thread_to_join, 'is_alive') and loop_thread_to_join.is_alive():
                        logger.debug(f"[{self.name}] Waiting for loop monitoring thread to exit...")
                        loop_thread_to_join.join(timeout=5.0) # Wait for the thread to finish
                        if loop_thread_to_join.is_alive():
                            logger.warning(f"[{self.name}] Loop monitoring thread did not exit in time.")
                except (AttributeError, TypeError, RuntimeError) as e:
                    logger.warning(f"[{self.name}] Error joining thread during stop: {e}")
            
            # Send stop command
            if not self._send_dlna_action(None, "Stop"):
                logger.error(f"Failed to stop playback on {self.name}")
                return False
            
            # Update device status
            self.update_status("connected")
            self.update_playing(False)
            self.current_video = None
            self.current_video_duration = None  # Clear cached duration
            self.current_video_path = None  # Clear cached path
            self.update_streaming_info(None, None)  # Clear streaming info
            
            # Clean up streaming sessions
            try:
                from core.streaming_registry import StreamingSessionRegistry
                registry = StreamingSessionRegistry.get_instance()
                sessions = registry.get_sessions_for_device(self.name)
                for session in sessions:
                    logger.info(f"Completing streaming session {session.session_id} on device stop")
                    session.complete()
            except Exception as e:
                logger.warning(f"Could not clean up streaming sessions: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Error stopping playback on {self.name}: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def pause(self) -> bool:
        """
        Pause playback on the DLNA device
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Pausing playback on DLNA device {self.name}")
            
            # Send pause command
            if not self._send_dlna_action(None, "Pause"):
                logger.error(f"Failed to pause playback on {self.name}")
                return False
            
            # Update device status
            self.update_status("paused")
            self.update_playing(False)
            
            return True
        except Exception as e:
            logger.error(f"Error pausing playback on {self.name}: {e}")
            return False
    
    def seek(self, position: str) -> bool:
        """
        Seek to a position in the current video
        
        Args:
            position: Position to seek to (format: HH:MM:SS)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Seeking to position {position} on DLNA device {self.name}")
            action_data = {
                "seek_target": position, # Corrected key for _send_dlna_action
            }
            # Use _send_av_transport_action directly for more control if needed, or ensure _send_dlna_action handles "Seek" correctly
            if not self._send_av_transport_action("Seek", {"Unit": "REL_TIME", "Target": position}):
                 logger.error(f"Failed to seek on {self.name}")
                 return False
            
            # Update last activity time to prevent false inactivity detection
            with self._thread_lock:
                self._last_activity_time = time.time()
                
            return True
        except Exception as e:
            logger.error(f"Error seeking on DLNA device {self.name}: {e}")
            logger.debug(traceback.format_exc())
            return False
    
    def _send_dlna_action(self, data: Optional[Dict[str, Any]], action: str) -> bool:
        """
        Send a DLNA action to the device.
        This is a simplified wrapper around _send_av_transport_action.
        
        Args:
            data: Data for the action (specific to the action type)
            action: Name of the action (e.g., "Play", "Stop", "SetAVTransportURI")
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            parameters = {}
            if action == "SetAVTransportURI":
                if not data or "CurrentURI" not in data or "CurrentURIMetaData" not in data:
                    logger.error("SetAVTransportURI requires CurrentURI and CurrentURIMetaData")
                    return False
                parameters = {
                    "CurrentURI": data["CurrentURI"],
                    "CurrentURIMetaData": data["CurrentURIMetaData"]
                }
            elif action == "Play":
                parameters = {"Speed": "1"}
            elif action == "Stop" or action == "Pause":
                parameters = {} # No additional parameters needed
            elif action == "Seek":
                # This action is better handled by calling _send_av_transport_action directly
                # due to specific parameter names like "Unit" and "Target".
                # However, if we want to keep this wrapper, data should contain "Unit" and "Target".
                if not data or "Unit" not in data or "Target" not in data:
                    logger.error("Seek action requires Unit and Target in data")
                    return False
                parameters = {"Unit": data["Unit"], "Target": data["Target"]}
            else:
                logger.error(f"Unknown DLNA action in _send_dlna_action: {action}")
                return False
            
            return self._send_av_transport_action(action, parameters)
            
        except Exception as e:
            logger.error(f"Error sending DLNA action {action} via simplified wrapper: {e}")
            return False

    def _send_av_transport_action(self, action: str, parameters: dict) -> bool:
        """
        Send an AVTransport action to the device
        
        Args:
            action: Name of the action
            parameters: Parameters for the action
            
        Returns:
            bool: True if successful, False otherwise
        """
        import requests # Ensure requests is imported if not globally
        import xml.etree.ElementTree as ET
        
        # Define SOAP namespaces
        ns = {
            "s": "http://schemas.xmlsoap.org/soap/envelope/",
            "u": "urn:schemas-upnp-org:service:AVTransport:1",
        }
        
        # Create SOAP envelope
        envelope = ET.Element("{http://schemas.xmlsoap.org/soap/envelope/}Envelope")
        envelope.set("xmlns:s", ns["s"])
        envelope.set("s:encodingStyle", "http://schemas.xmlsoap.org/soap/encoding/")
        
        # Create SOAP body
        body = ET.SubElement(envelope, "{http://schemas.xmlsoap.org/soap/envelope/}Body")
        
        # Create action element
        action_element = ET.SubElement(body, "{urn:schemas-upnp-org:service:AVTransport:1}" + action)
        
        # Add instance ID (always 0 for standard DLNA)
        instance_id = ET.SubElement(action_element, "InstanceID")
        instance_id.text = "0"
        
        # Add parameters
        for name, value in parameters.items():
            param = ET.SubElement(action_element, name)
            param.text = str(value) # Ensure value is string
        
        # Convert to XML string
        from xml.dom.minidom import parseString
        xml_str_bytes = ET.tostring(envelope, encoding="utf-8", method="xml")
        xml_str = xml_str_bytes.decode('utf-8') # Ensure it's a string for requests
        
        # Log the request
        logger.debug(f"Sending AVTransport action {action} to {self.name}")
        logger.debug(f"Action URL: {self.action_url}")
        # logger.debug(f"SOAP request: {parseString(xml_str).toprettyxml(indent='  ')}") # Can be verbose
        
        # Define SOAP headers
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f'"urn:schemas-upnp-org:service:AVTransport:1#{action}"',
        }
        
        # Send the request with one endpoint-refresh retry for transient routing failures.
        for attempt in range(2):
            try:
                response = requests.post(self.action_url, data=xml_str_bytes, headers=headers, timeout=10)
                if response.status_code == 200:
                    logger.debug(f"AVTransport action {action} succeeded")
                    return True
                logger.error(f"AVTransport action {action} failed with status {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False
            except requests.exceptions.RequestException as e:
                error_text = str(e)
                should_retry = (
                    attempt == 0
                    and ("No route to host" in error_text or "Errno 65" in error_text)
                    and self._recover_control_route()
                )
                if should_retry:
                    logger.warning(
                        "Retrying AVTransport action %s on refreshed endpoint %s",
                        action,
                        self.action_url,
                    )
                    continue
                logger.error(f"Error sending AVTransport action {action}: {e}")
                return False
        return False

    def _refresh_endpoint_from_discovery(self) -> bool:
        runtime = getattr(self, "runtime", None)
        if runtime is None or not hasattr(runtime, "discover_dlna_devices"):
            return False

        try:
            discovered = runtime.discover_dlna_devices(timeout=3)
        except Exception as exc:
            logger.debug("Endpoint refresh discovery failed for %s: %s", self.name, exc)
            return False

        for device_info in discovered or []:
            discovered_name = (
                device_info.get("friendly_name")
                or device_info.get("name")
                or device_info.get("device_name")
            )
            if discovered_name != self.name:
                continue

            new_action_url = device_info.get("action_url") or self.action_url
            new_hostname = device_info.get("hostname") or self.hostname
            if new_action_url != self.action_url or new_hostname != self.hostname:
                logger.info(
                    "Refreshed DLNA endpoint for %s: host %s -> %s, action_url %s -> %s",
                    self.name,
                    self.hostname,
                    new_hostname,
                    self.action_url,
                    new_action_url,
                )
            self.hostname = new_hostname
            self.action_url = new_action_url
            return True

        return False

    def _recover_control_route(self) -> bool:
        """
        Try to recover connectivity to the renderer control endpoint after route failures.
        """
        from urllib.parse import urlparse

        parsed = urlparse(self.action_url or "")
        host = parsed.hostname or self.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if not host:
            return False

        def can_reach() -> bool:
            try:
                probe = socket.create_connection((host, port), timeout=2.0)
                probe.close()
                return True
            except OSError:
                return False

        # Fast path: route is already back.
        if can_reach():
            return True

        # Refresh endpoint metadata first.
        self._refresh_endpoint_from_discovery()

        # If we have a location URL, probing it can wake some renderers.
        location_url = getattr(self, "location", None)
        if location_url:
            try:
                with urllibreq.urlopen(location_url, timeout=3) as response:
                    response.read(1)
            except Exception:
                pass

        # Retry route probe briefly.
        for _ in range(3):
            if can_reach():
                return True
            time.sleep(0.5)

        return False

    def _handle_streaming_health_check(self, session_id: str, reason: str) -> None:
        """
        Handle streaming health check events
        
        Args:
            session_id: ID of the streaming session
            reason: Reason for the health check event
        """
        logger.warning(f"[{self.name}] Handling streaming health check for session {session_id}")
        
        # Check if this session belongs to this device by checking with the registry
        try:
            from core.streaming_registry import StreamingSessionRegistry
            registry = StreamingSessionRegistry.get_instance()
            session = registry.get_session(session_id)
            if not session or session.device_name != self.name:
                logger.warning(f"[{self.name}] Session {session_id} does not belong to this device")
                return
        except Exception as e:
            logger.error(f"Error checking session ownership: {e}")
            return
            
        # Handle different health check reasons
        if reason == "stalled":
            # Try to restart the video
            logger.info(f"[{self.name}] Streaming session {session_id} stalled, attempting restart")
            if self.is_playing and self.current_video:
                self.play(self.current_video, loop=self._loop_enabled) # Use self._loop_enabled
            
        elif reason == "completed":
            # Video playback completed naturally
            logger.info(f"[{self.name}] Streaming session {session_id} completed naturally")
            # If we're supposed to be looping, restart
            if self._loop_enabled and self.current_video: # Use self._loop_enabled
                logger.info(f"[{self.name}] Restarting video in loop mode")
                self.play(self.current_video, loop=True) # loop=True will trigger _setup_loop_monitoring_v2
                
                # Trigger overlay sync on loop restart
                try:
                    import requests
                    response = requests.post(
                        "http://localhost:8000/api/overlay/sync",
                        params={
                            "triggered_by": "dlna_loop",
                            "video_name": os.path.basename(self.current_video_path) if self.current_video_path else None
                        },
                        timeout=2  # Short timeout to not block loop monitoring
                    )
                    if response.status_code == 200:
                        logger.info(f"[{self.name}] Triggered overlay sync on loop restart")
                except Exception as e:
                    logger.warning(f"[{self.name}] Failed to sync overlays on loop: {e}")
                    # Don't fail loop monitoring if sync fails
                
    # This is the refactored version for loop monitoring (Task 1)
    def _setup_loop_monitoring_v2(self, video_url: str) -> None:
        """
        Set up monitoring of video playback for looping (Version 2 - Refactored for Task 1)
        
        Args:
            video_url: URL of the video
        """
        with self._thread_lock:
            if self._loop_thread and self._loop_thread.is_alive():
                logger.info(f"[{self.name}] Loop monitoring thread (v2) already running. Stopping it first.")
                self._loop_enabled = False
                current_thread = self._loop_thread
                self._loop_thread = None # Allow new thread to be created
                current_thread.join(timeout=5.0)
                if current_thread.is_alive():
                    logger.warning(f"[{self.name}] Previous loop thread (v2) did not terminate in time.")

            self._loop_enabled = True
            self._last_activity_time = time.time() # Reset activity time
            
            self._loop_thread = threading.Thread(
                target=self._monitor_and_loop_v2, # Target the refactored monitor
                args=(video_url,),
                daemon=True,
                name=f"loop-monitor-v2-{self.name}"
            )
            try:
                self._loop_thread.start()
                logger.info(f"[{self.name}] Loop monitoring thread (v2) started successfully for {video_url}.")
            except Exception as e:
                logger.error(f"[{self.name}] Error starting loop monitoring thread (v2): {e}")
                self._loop_thread = None # Ensure thread is None if start fails
                self._loop_enabled = False # Disable looping if thread fails to start

    # This is the refactored monitoring logic (Task 1)
    def _monitor_and_loop_v2(self, video_url: str) -> None:
        """
        Monitor video playback and restart when completed (Version 2 - Refactored for Task 1)
        
        Args:
            video_url: URL of the video
        """
        logger.info(f"[{self.name}] Starting playback monitoring (v2) for {video_url}")
        
        # Set up dedicated progress debug logger
        progress_logger = logging.getLogger(f"{__name__}.progress_debug")
        progress_logger.setLevel(logging.DEBUG)
        
        # Create file handler for progress debugging
        import os
        from logging.handlers import RotatingFileHandler
        debug_log_path = "/tmp/dlna_progress_debug.log"
        if not any(isinstance(h, RotatingFileHandler) and h.baseFilename == debug_log_path 
                   for h in progress_logger.handlers):
            handler = RotatingFileHandler(debug_log_path, maxBytes=10*1024*1024, backupCount=2)
            handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            progress_logger.addHandler(handler)
        
        progress_logger.info(f"[PROGRESS_DEBUG] [{self.name}] === MONITOR THREAD STARTED === URL: {video_url}")
        
        if not hasattr(self, 'current_video_duration') or self.current_video_duration is None:
            self.current_video_duration = None # Will attempt to determine
        
        self.current_position = "00:00:00"
        self.playback_progress = 0
        
        monitoring_start_time = time.time()
        update_interval = 2  # Check every 2 seconds
        last_progress_update_time = 0
        seeking_triggered = False  # Track if we've triggered seek for this loop

        # Attempt to determine duration
        retry_count = 0
        max_duration_retries = 5
        progress_logger.info(f"[PROGRESS_DEBUG] [{self.name}] Attempting to determine video duration...")
        
        while retry_count < max_duration_retries:
            with self._thread_lock: # Check loop_enabled under lock
                if not self._loop_enabled:
                    logger.info(f"[{self.name}] Loop disabled (v2) during duration check. Exiting monitor thread.")
                    progress_logger.info(f"[PROGRESS_DEBUG] [{self.name}] Loop disabled during duration check, exiting")
                    return

            try:
                position_info = self._get_position_info()
                track_duration_str = position_info.get("TrackDuration")
                progress_logger.debug(f"[PROGRESS_DEBUG] [{self.name}] Duration attempt {retry_count + 1}: TrackDuration={track_duration_str}")
                
                if track_duration_str and track_duration_str not in ("UNKNOWN", "NOT_IMPLEMENTED", "0:00:00"):
                    self.current_video_duration = self._parse_time(track_duration_str)
                    progress_logger.info(f"[PROGRESS_DEBUG] [{self.name}] Got duration from device: {track_duration_str} = {self.current_video_duration}s")
                    logger.info(f"[{self.name}] Video duration (v2) from position info: {self.current_video_duration}s")
                    break
            except Exception as e:
                progress_logger.warning(f"[PROGRESS_DEBUG] [{self.name}] Error getting duration (attempt {retry_count + 1}): {e}")
                logger.warning(f"[{self.name}] Error getting video duration (v2) (attempt {retry_count + 1}): {e}")
            
            retry_count += 1
            if retry_count < max_duration_retries:
                time.sleep(update_interval)


        if not self.current_video_duration:
            # Try to get duration from video file if DLNA device doesn't provide it
            try:
                # Extract video path from URL (e.g., http://10.0.0.74:9001/door6.mp4 -> door6.mp4)
                import os
                from urllib.parse import urlparse, unquote
                parsed_url = urlparse(video_url)
                filename = unquote(os.path.basename(parsed_url.path))
                logger.debug(f"[{self.name}] Extracted filename from URL: {filename}")
                
                # Try multiple ways to find the video file
                video_path = None
                
                # Method 1: Check if we have the path stored directly
                if hasattr(self, 'current_video_path') and self.current_video_path:
                    video_path = self.current_video_path
                    logger.debug(f"[{self.name}] Using stored video path: {video_path}")
                
                # Method 2: Check runtime-assigned videos
                elif hasattr(self, 'runtime') and self.runtime:
                    logger.debug(f"[{self.name}] Checking runtime assigned_videos")
                    video_path = self.runtime.get_assigned_video(self.name)
                    logger.debug(f"[{self.name}] Found in assigned_videos: {video_path}")
                else:
                    logger.debug(f"[{self.name}] No runtime available for assigned_videos lookup")
                
                # Method 3: Try common paths if not found
                if not video_path or not os.path.exists(video_path):
                    # Try to find the file in common locations
                    possible_paths = [
                        os.path.join("/Users/abdulrehmanbhidya/PycharmProjects/nano-dlna", filename),
                        os.path.join(os.getcwd(), filename),
                        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", filename),
                    ]
                    for path in possible_paths:
                        if os.path.exists(path):
                            video_path = path
                            logger.debug(f"[{self.name}] Found video at: {video_path}")
                            break
                
                if video_path and os.path.exists(video_path):
                            # Use ffprobe to get duration
                            import subprocess
                            try:
                                result = subprocess.run(
                                    ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
                                     '-of', 'default=noprint_wrappers=1:nokey=1', video_path],
                                    capture_output=True, text=True, timeout=5
                                )
                                logger.debug(f"[{self.name}] ffprobe result: returncode={result.returncode}, stdout='{result.stdout}', stderr='{result.stderr}'")
                                if result.returncode == 0 and result.stdout.strip():
                                    duration_seconds = float(result.stdout.strip())
                                    self.current_video_duration = int(duration_seconds)
                                    logger.info(f"[{self.name}] Got video duration from file: {self.current_video_duration}s")
                                else:
                                    logger.warning(f"[{self.name}] ffprobe failed: returncode={result.returncode}, stderr={result.stderr}")
                            except subprocess.TimeoutExpired as e:
                                logger.warning(f"[{self.name}] ffprobe timed out: {e}")
                            except FileNotFoundError:
                                logger.error(f"[{self.name}] ffprobe not found in PATH")
                            except ValueError as e:
                                logger.error(f"[{self.name}] Could not parse ffprobe output: {e}")
                            except Exception as e:
                                logger.error(f"[{self.name}] Unexpected error with ffprobe: {e}")
            except Exception as e:
                logger.debug(f"[{self.name}] Error getting duration from file: {e}")
            
            # Final fallback - use a more reasonable default for video files
            if not self.current_video_duration:
                logger.warning(f"[{self.name}] Couldn't determine video duration (v2), using default 1800s (30 min).")
                progress_logger.warning(f"[PROGRESS_DEBUG] [{self.name}] Duration unknown after all attempts, using default 1800s")
                self.current_video_duration = 1800  # 30 minutes is more reasonable default for videos 
            
        self.duration_formatted = self._format_time(self.current_video_duration)
        progress_logger.info(f"[PROGRESS_DEBUG] [{self.name}] Final duration: {self.duration_formatted} ({self.current_video_duration}s)")
        
        if hasattr(self, 'runtime') and self.runtime:
            self.runtime.update_device_playback_progress(self.name, "00:00:00", self.duration_formatted, 0)
            progress_logger.debug(f"[PROGRESS_DEBUG] [{self.name}] Initial progress update sent to device manager")

        progress_logger.info(f"[PROGRESS_DEBUG] [{self.name}] Entering main monitoring loop")
        loop_iteration = 0
        
        while True: # Main monitoring loop
            loop_iteration += 1
            progress_logger.debug(f"[PROGRESS_DEBUG] [{self.name}] Loop iteration {loop_iteration} starting")
            
            loop_active_check = False
            with self._thread_lock:
                loop_active_check = self._loop_enabled
            
            if not loop_active_check:
                logger.info(f"[{self.name}] Loop disabled (v2). Exiting monitor thread.")
                progress_logger.info(f"[PROGRESS_DEBUG] [{self.name}] Loop disabled, exiting monitor thread")
                break

            try:
                current_time = time.time()
                
                # Update progress
                if current_time - last_progress_update_time >= update_interval:
                    progress_logger.debug(f"[PROGRESS_DEBUG] [{self.name}] Time to update progress (interval: {update_interval}s)")
                    
                    position_info = self._get_position_info()
                    rel_time_str = position_info.get("RelTime")
                    transport_info = self._get_transport_info()
                    transport_state = transport_info.get("CurrentTransportState", "UNKNOWN")
                    
                    progress_logger.info(f"[PROGRESS_DEBUG] [{self.name}] Got position info: RelTime={rel_time_str}, State={transport_state}")
                    progress_logger.debug(f"[PROGRESS_DEBUG] [{self.name}] Full position_info: {position_info}")
                    progress_logger.debug(f"[PROGRESS_DEBUG] [{self.name}] Full transport_info: {transport_info}")
                    
                    logger.debug(f"[{self.name}] Monitor (v2): Pos={rel_time_str}, State={transport_state}")

                    # Determine position and progress
                    use_time_based_tracking = False
                    position_seconds = 0
                    progress = 0
                    
                    if rel_time_str and rel_time_str not in ("UNKNOWN", "NOT_IMPLEMENTED"):
                        # Device reports position - use it
                        self.current_position = rel_time_str
                        position_seconds = self._parse_time(rel_time_str)
                        progress_logger.debug(f"[PROGRESS_DEBUG] [{self.name}] Device reports position: {rel_time_str} = {position_seconds}s")
                        
                        # Track zero position count
                        if position_seconds == 0 and transport_state == "PLAYING":
                            self._zero_position_count += 1
                            progress_logger.info(f"[PROGRESS_DEBUG] [{self.name}] Position at 0 while PLAYING, count: {self._zero_position_count}")
                            logger.debug(f"[{self.name}] Position at 0, count: {self._zero_position_count}")
                            
                            # If stuck at 0 for too long, switch to time-based tracking
                            if self._zero_position_count > 3:
                                use_time_based_tracking = True
                                elapsed_time = current_time - monitoring_start_time
                                position_seconds = int(elapsed_time) % int(self.current_video_duration) if self.current_video_duration else 0
                                self.current_position = self._format_time(position_seconds)
                                progress_logger.warning(f"[PROGRESS_DEBUG] [{self.name}] SWITCHING TO TIME-BASED: stuck at 0 after {self._zero_position_count} checks")
                                logger.info(f"[{self.name}] Device stuck at 0 after {self._zero_position_count} checks, switching to time-based tracking: position={self.current_position}")
                        else:
                            if self._zero_position_count > 0:
                                progress_logger.info(f"[PROGRESS_DEBUG] [{self.name}] Position changed from 0, resetting zero_position_count")
                            self._zero_position_count = 0  # Reset if position changes
                    else:
                        # Device doesn't report position - use time-based tracking
                        progress_logger.warning(f"[PROGRESS_DEBUG] [{self.name}] Device doesn't report position (RelTime={rel_time_str})")
                        
                        # Allow time-based tracking for devices that report UNKNOWN state
                        if (transport_state in ["PLAYING", "UNKNOWN"]) and self.current_video_duration:
                            use_time_based_tracking = True
                            elapsed_time = current_time - monitoring_start_time
                            
                            # Calculate position within current loop
                            position_seconds = int(elapsed_time) % int(self.current_video_duration)
                            self.current_position = self._format_time(position_seconds)
                            
                            progress_logger.info(f"[PROGRESS_DEBUG] [{self.name}] Using TIME-BASED tracking (state={transport_state}): elapsed={elapsed_time:.1f}s, position={self.current_position}")
                            logger.info(f"[{self.name}] Time-based tracking (state={transport_state}): elapsed={elapsed_time:.1f}s, position={self.current_position}")
                    
                    # Calculate progress
                    if self.current_video_duration and self.current_video_duration > 0:
                        if use_time_based_tracking:
                            # For time-based tracking, use position_seconds (which wraps at duration) for progress
                            progress = min(100, int((position_seconds / self.current_video_duration) * 100))
                            progress_logger.info(f"[PROGRESS_DEBUG] [{self.name}] TIME-BASED progress: {progress}% (pos={position_seconds}s / duration={self.current_video_duration}s)")
                        else:
                            # For position-based tracking
                            progress = min(100, int((position_seconds / self.current_video_duration) * 100))
                            progress_logger.info(f"[PROGRESS_DEBUG] [{self.name}] POSITION-BASED progress: {progress}% (pos={position_seconds}s / duration={self.current_video_duration}s)")
                        
                        self.playback_progress = progress
                        progress_logger.debug(f"[PROGRESS_DEBUG] [{self.name}] Final progress calculation: position={self.current_position}, progress={self.playback_progress}%")
                        
                        if hasattr(self, 'runtime') and self.runtime:
                            self.runtime.update_device_playback_progress(self.name, self.current_position, self.duration_formatted, self.playback_progress)
                            progress_logger.debug(f"[PROGRESS_DEBUG] [{self.name}] Updated device manager with progress")
                    else:
                        progress_logger.warning(f"[PROGRESS_DEBUG] [{self.name}] Cannot calculate progress: duration={self.current_video_duration}")
                    
                    # Keep streaming session alive by updating its activity
                    # This prevents false stall detection for devices that buffer entire videos
                    try:
                        from core.streaming_registry import StreamingSessionRegistry
                        registry = StreamingSessionRegistry.get_instance()
                        sessions = registry.get_sessions_for_device(self.name)
                        for session in sessions:
                            if session.active:
                                session.update_activity()
                                logger.debug(f"[{self.name}] Updated streaming session activity to prevent false stall detection")
                    except Exception as e:
                        # Don't break playback if session update fails
                        logger.debug(f"[{self.name}] Could not update session activity: {e}")
                    
                    # Seek-based looping logic
                    # Try to seek at 90% to avoid gap, fall back to restart if needed
                    if progress >= 90 and not seeking_triggered and transport_state in ["PLAYING", "UNKNOWN"]:
                        logger.info(f"[{self.name}] Approaching end (progress {progress}%), attempting seek to beginning")
                        
                        if self.seek("00:00:00"):
                            logger.info(f"[{self.name}] Successfully seeked to beginning for seamless loop")
                            seeking_triggered = True
                            monitoring_start_time = time.time()  # Reset time tracking
                            last_progress_update_time = time.time()
                            self._zero_position_count = 0
                            # Don't reset duration - we still know it
                            
                            # Wait a moment then reset the seeking flag for next loop
                            time.sleep(0.5)
                            seeking_triggered = False
                            continue
                        else:
                            logger.warning(f"[{self.name}] Seek failed, will use restart fallback")
                    
                    # Restart logic (fallback when seek fails or video ends)
                    # Consider restarting if:
                    # 1. Very close to end (progress >= 98%)
                    # 2. State is STOPPED/NO_MEDIA with position at 0
                    # 3. Position stuck at 0 while claiming to play for >3 checks
                    # 4. Time-based: elapsed time exceeds duration (for UNKNOWN position)
                    should_restart = False
                    restart_reason = ""
                    
                    if progress >= 98:
                        should_restart = True
                        restart_reason = f"near end (progress {progress}%)"
                    elif transport_state in ["STOPPED", "NO_MEDIA_PRESENT"] and position_seconds == 0:
                        should_restart = True
                        restart_reason = "stopped state"
                    elif position_seconds == 0 and self._zero_position_count > 3:
                        should_restart = True
                        restart_reason = "stuck at position 00:00:00"
                    elif use_time_based_tracking and elapsed_time >= self.current_video_duration:
                        should_restart = True
                        restart_reason = f"time-based: elapsed {elapsed_time:.1f}s >= duration {self.current_video_duration}s"
                    
                    if should_restart:
                        logger.info(f"[{self.name}] Restarting video: {restart_reason}")
                        
                        if self._try_restart_video(video_url):
                            monitoring_start_time = time.time() # Reset monitoring time
                            last_progress_update_time = time.time() # Reset update time
                            self.current_video_duration = None # Re-fetch duration
                            self._zero_position_count = 0  # Reset zero position counter
                            seeking_triggered = False  # Reset seeking flag for next loop
                            # Re-fetch duration immediately
                            retry_count = 0
                            while retry_count < max_duration_retries:
                                with self._thread_lock:
                                    if not self._loop_enabled: break
                                try:
                                    pos_info_restart = self._get_position_info()
                                    dur_str_restart = pos_info_restart.get("TrackDuration")
                                    if dur_str_restart and dur_str_restart not in ("UNKNOWN", "NOT_IMPLEMENTED", "0:00:00"):
                                        self.current_video_duration = self._parse_time(dur_str_restart)
                                        self.duration_formatted = self._format_time(self.current_video_duration)
                                        logger.info(f"[{self.name}] Re-fetched duration after restart (v2): {self.current_video_duration}s")
                                        break
                                except Exception: pass
                                retry_count += 1
                                if retry_count < max_duration_retries: time.sleep(1)
                            if not self.current_video_duration: self.current_video_duration = 60
                            self.duration_formatted = self._format_time(self.current_video_duration)

                            if hasattr(self, 'runtime') and self.runtime: # Reset progress display
                                self.runtime.update_device_playback_progress(self.name, "00:00:00", self.duration_formatted, 0)
                            continue # Restart loop immediately
                        else:
                            logger.error(f"[{self.name}] Failed to restart video (v2). Will retry.")
                            time.sleep(5) # Wait before next cycle if restart fails
                            continue
                    
                    elif transport_state not in ["PLAYING", "TRANSITIONING", "UNKNOWN"]:
                        logger.warning(f"[{self.name}] Device not playing (state: {transport_state}) (v2). Attempting restart.")
                        if self._try_restart_video(video_url):
                            monitoring_start_time = time.time()
                            last_progress_update_time = time.time()
                            seeking_triggered = False  # Reset seeking flag
                            # Re-fetch duration as above
                        else:
                            time.sleep(5)
                        continue
                    last_progress_update_time = current_time

                # Inactivity check (if no progress for a while)
                # First check if there's an active streaming session before declaring inactivity
                has_active_stream = False
                try:
                    from core.streaming_registry import StreamingSessionRegistry
                    registry = StreamingSessionRegistry.get_instance()
                    sessions = registry.get_sessions_for_device(self.name)
                    for session in sessions:
                        # Check if there's recent activity, regardless of session.active status
                        # This prevents false inactivity detection when registry marks session as stalled
                        time_since_activity = (datetime.now() - session.last_activity_time).total_seconds()
                        if time_since_activity < 30:  # Accept activity within last 30 seconds
                            has_active_stream = True
                            # Update our last activity time based on streaming activity
                            with self._thread_lock:
                                self._last_activity_time = time.time()
                            logger.debug(f"[{self.name}] Found recent streaming activity {time_since_activity:.1f}s ago")
                            break
                except Exception as e:
                    logger.debug(f"[{self.name}] Could not check streaming registry: {e}")
                
                # Calculate dynamic timeout based on video duration
                effective_timeout = self._inactivity_timeout
                if self._dynamic_inactivity_timeout and self.current_video_duration:
                    # For buffering devices, set timeout to video duration + 30 seconds
                    effective_timeout = self.current_video_duration + 30
                    logger.debug(f"[{self.name}] Using dynamic timeout: {effective_timeout}s (video duration: {self.current_video_duration}s)")
                
                if not has_active_stream and self._last_activity_time and (time.time() - self._last_activity_time > effective_timeout):
                    logger.warning(f"[{self.name}] Inactivity detected (v2) after {effective_timeout}s. Checking state and attempting restart.")
                    if self._try_restart_video(video_url):
                        monitoring_start_time = time.time() # Reset monitoring time
                        last_progress_update_time = time.time()
                        seeking_triggered = False  # Reset seeking flag
                    else:
                        time.sleep(5) # Wait on failure
                    continue

                time.sleep(1) # Main loop sleep
            
            except Exception as e:
                logger.error(f"[{self.name}] Error in loop monitoring (v2): {e}")
                logger.error(traceback.format_exc())
                progress_logger.error(f"[PROGRESS_DEBUG] [{self.name}] ERROR in monitoring loop iteration {loop_iteration}: {e}")
                progress_logger.error(f"[PROGRESS_DEBUG] [{self.name}] Traceback: {traceback.format_exc()}")
                time.sleep(5) # Sleep on error
        
        logger.info(f"[{self.name}] Playback monitoring (v2) for {video_url} finished.")
        progress_logger.info(f"[PROGRESS_DEBUG] [{self.name}] === MONITOR THREAD EXITED === After {loop_iteration} iterations")

    def _parse_time(self, time_str: str) -> int:
        """
        Parse time string in format HH:MM:SS to seconds
        
        Args:
            time_str: Time string
            
        Returns:
            int: Time in seconds, or 0 if parsing fails
        """
        try:
            parts = time_str.split(':')
            if len(parts) == 3:
                hours, minutes, seconds_float = parts # seconds can be float e.g. "00:00:05.321"
                return int(hours) * 3600 + int(minutes) * 60 + int(float(seconds_float))
            elif len(parts) == 2: # MM:SS
                minutes, seconds_float = parts
                return int(minutes) * 60 + int(float(seconds_float))
            elif len(parts) == 1: # SSSSS
                 return int(float(parts[0]))
            logger.warning(f"[{self.name}] Could not parse time string: {time_str}")
            return 0
        except ValueError: # Handles non-integer parts or float conversion issues
            logger.warning(f"[{self.name}] ValueError parsing time string: {time_str}")
            return 0
        except Exception as e: # Catch any other parsing errors
            logger.error(f"[{self.name}] Unexpected error parsing time string '{time_str}': {e}")
            return 0

    def _format_time(self, total_seconds: int) -> str:
        """
        Format total seconds into HH:MM:SS string
        """
        if total_seconds < 0: total_seconds = 0
        hours, remainder = divmod(int(total_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _get_serve_ip(self) -> str:
        """
        Get the best IP address to serve content to this device
        
        Returns:
            str: IP address
        """
        import socket
        
        # If we know the device's hostname/IP, try to find the best interface
        if self.hostname and not self.hostname.startswith('127.') and not self.hostname == 'localhost':
            # Get all network interfaces
            try:
                interfaces = socket.getaddrinfo(socket.gethostname(), None)
            except socket.gaierror: # Could happen if hostname not resolvable
                 interfaces = []

            for interface in interfaces:
                # Only consider IPv4 addresses
                if interface[0] == socket.AF_INET:
                    local_ip = interface[4][0]
                    
                    # Skip loopback addresses
                    if not local_ip.startswith('127.'):
                        # Check if this interface can reach the device network
                        device_ip_to_check = self.hostname
                        if ':' in device_ip_to_check: # Handle host:port format
                            device_ip_to_check = device_ip_to_check.split(':')[0]
                        
                        try:
                            # Attempt to resolve device_ip_to_check if it's a hostname
                            resolved_device_ip = socket.gethostbyname(device_ip_to_check)
                        except socket.gaierror:
                            logger.warning(f"[{self.name}] Could not resolve device hostname {device_ip_to_check} for IP matching.")
                            continue # Skip if device hostname can't be resolved

                        # Simple subnet check - compare the first three octets
                        local_subnet = '.'.join(local_ip.split('.')[:3])
                        device_subnet = '.'.join(resolved_device_ip.split('.')[:3])
                        
                        if local_subnet == device_subnet:
                            logger.debug(f"Found matching interface for device {self.name}: {local_ip}")
                            return local_ip
        
        # Fallback: find a non-loopback interface
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Doesn't have to be reachable
            s.connect(('10.255.255.255', 1)) # Target a non-existent IP in a common private range
            ip = s.getsockname()[0]
            if ip == '0.0.0.0': # Handle cases where getsockname might return 0.0.0.0
                ip = '127.0.0.1' 
        except Exception: # Catch broad exceptions as network conditions vary
            ip = '127.0.0.1' # Default to loopback on error
        finally:
            s.close()
        
        logger.debug(f"Using fallback interface for device {self.name}: {ip}")
        return ip

    def _create_didl_metadata(self, url: str) -> str:
        """
        Create DIDL-Lite metadata for a video
        
        Args:
            url: URL of the video
            
        Returns:
            str: DIDL-Lite metadata
        """
        # Base DIDL template
        didl_template = """<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" 
                         xmlns:dc="http://purl.org/dc/elements/1.1/" 
                         xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/" 
                         xmlns:sec="http://www.sec.co.kr/">
        <item id="0" parentID="-1" restricted="1">
            <dc:title>Video</dc:title>
            <upnp:class>object.item.videoItem</upnp:class>
            <res protocolInfo="http-get:*:video/mp4:DLNA.ORG_PN=AVC_MP4_BL_CIF15_AAC_520;DLNA.ORG_OP=01;DLNA.ORG_CI=0;DLNA.ORG_FLAGS=01500000000000000000000000000000" sec:URIType="public">{url}</res>
        </item>
        </DIDL-Lite>"""
        
        # Insert the URL
        metadata = didl_template.format(url=xmlescape(url)) # Escape URL
        return metadata
    
    def _create_image_didl_metadata(self, url: str) -> str:
        """
        Create DIDL-Lite metadata for an image
        
        Args:
            url: URL of the image
            
        Returns:
            str: DIDL-Lite metadata for image
        """
        # DIDL template for images
        didl_template = """<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" 
                         xmlns:dc="http://purl.org/dc/elements/1.1/" 
                         xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">
        <item id="0" parentID="-1" restricted="1">
            <dc:title>Black Screen</dc:title>
            <upnp:class>object.item.imageItem.photo</upnp:class>
            <res protocolInfo="http-get:*:image/jpeg:DLNA.ORG_PN=JPEG_LRG;DLNA.ORG_OP=01;DLNA.ORG_CI=0;DLNA.ORG_FLAGS=00D00000000000000000000000000000">{url}</res>
        </item>
        </DIDL-Lite>"""
        
        # Insert the URL
        metadata = didl_template.format(url=xmlescape(url))
        return metadata
    
    def display_image(self, image_url: str) -> bool:
        """
        Display an image on the DLNA device
        
        Args:
            image_url: URL of the image to display
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Displaying image {image_url} on DLNA device {self.name}")
            
            # Store the current URL
            self.current_video = image_url
            
            # Create metadata for the image
            metadata = self._create_image_didl_metadata(image_url)
            
            # Set up AV transport with image
            data = {
                "CurrentURI": image_url,
                "CurrentURIMetaData": metadata
            }
            if not self._send_dlna_action(data, "SetAVTransportURI"):
                logger.error(f"Failed to set AV transport URI for image on {self.name}")
                return False
                
            # Start playback (even for images, this is needed)
            if not self._send_dlna_action(None, "Play"):
                logger.error(f"Failed to start display on {self.name}")
                return False
                
            # Update device status
            self.update_status("displaying")
            self.update_playing(True)
            
            # No loop monitoring needed for images
            
            return True
        except Exception as e:
            logger.error(f"Error displaying image on {self.name}: {e}")
            return False

    def _try_restart_video(self, video_url: str) -> bool:
        """
        Attempt to restart video playback using optimal restart strategy
        
        Args:
            video_url: URL of the video to restart
            
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"[{self.name}] Attempting to restart video (v2): {video_url}")
        
        try:
            # First try to get transport info to see if the device is responsive
            transport_info = self._get_transport_info()
            current_state = transport_info.get("CurrentTransportState", "UNKNOWN")
            logger.info(f"[{self.name}] Current transport state (for restart v2): {current_state}")
            
            # Check if video is already playing (possible false restart trigger)
            if current_state == "PLAYING":
                try:
                    position_info = self._get_position_info()
                    rel_time = position_info.get("RelTime", "UNKNOWN")
                    if rel_time and rel_time not in ("UNKNOWN", "NOT_IMPLEMENTED", "00:00:00", "0:00:00"):
                        # If it's playing and not at the very beginning, assume it's fine
                        logger.info(f"[{self.name}] Video seems to be playing at {rel_time} (v2), no restart needed now.")
                        with self._thread_lock: self._last_activity_time = time.time() # Update activity
                        return True 
                except Exception as e:
                    logger.warning(f"[{self.name}] Error checking position info during restart (v2): {e}")
            
            # Attempt: full restart with Stop+SetAVTransportURI+Play
            logger.info(f"[{self.name}] Performing full restart sequence (v2)...")
            
            # Stop current playback
            try:
                self._send_dlna_action(None, "Stop")
                time.sleep(0.5)  # Shorter pause
            except Exception as stop_error:
                logger.warning(f"[{self.name}] Error stopping video (v2) (continuing anyway): {stop_error}")
            
            # Create metadata
            metadata = self._create_didl_metadata(video_url)
            set_uri_data = {"CurrentURI": video_url, "CurrentURIMetaData": metadata}

            if not self._send_dlna_action(set_uri_data, "SetAVTransportURI"):
                logger.error(f"[{self.name}] Failed to set AV transport URI for restart (v2)")
                return False
            time.sleep(0.5) # Short pause

            if not self._send_dlna_action(None, "Play"):
                logger.error(f"[{self.name}] Failed to start playback after SetURI for restart (v2)")
                return False
            
            self.update_playing(True) # Update internal state
            logger.info(f"[{self.name}] Video restarted successfully (v2)")
            
            with self._thread_lock:
                self._last_activity_time = time.time()
                
            return True
            
        except Exception as e:
            logger.error(f"[{self.name}] Error during video restart (v2): {e}")
            logger.debug(traceback.format_exc())
            return False
