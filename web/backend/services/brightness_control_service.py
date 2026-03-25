"""
Brightness control service that manages DLNA devices based on brightness settings
"""
import logging
import os
import time
from urllib.parse import urlparse
from typing import Dict, List, Optional, Any
from datetime import datetime

from services.app_runtime import get_app_runtime
from services.overlay_cast_service import get_overlay_cast_service
from utils.create_black_video import create_black_video

logger = logging.getLogger(__name__)

class BrightnessControlService:
    """
    Service to control DLNA devices based on brightness settings
    When brightness is 0, cast black video to all playing devices
    When brightness is restored, resume original videos
    """
    
    def __init__(self):
        self.runtime = get_app_runtime()
        self.black_video_path = None
        self.device_state_backup = {}  # Store device states before blackout
        self.is_blackout_active = False
        self._ensure_black_video()

    def _is_overlay_cast_device(self, device) -> bool:
        return self._get_overlay_cast_session(device) is not None

    def _get_overlay_cast_session(self, device) -> Optional[Dict[str, Any]]:
        if not getattr(device, "hostname", None):
            return None

        overlay_cast_service = get_overlay_cast_service()
        device_action_url = getattr(device, "action_url", None)
        action_port = None
        if device_action_url:
            parsed = urlparse(device_action_url)
            action_port = parsed.port

        for session in overlay_cast_service.list_sessions():
            if session.get("archived"):
                continue
            if session.get("status") not in {"queued", "preparing", "running"}:
                continue
            device_id = session.get("device_id") or ""
            expected_prefix = f"dlna_{device.hostname}_"
            if device_id.startswith(expected_prefix):
                if action_port is None:
                    return session
                if device_id == f"dlna_{device.hostname}_{action_port}":
                    return session
        return None
    
    def _ensure_black_video(self):
        """Ensure black video file exists"""
        try:
            # Create a 24-hour black video to avoid looping edge cases
            self.black_video_path = create_black_video(duration=86400)  # 24 hours
            logger.info(f"Black video available at: {self.black_video_path}")
        except Exception as e:
            logger.error(f"Failed to create black video: {e}")
            # Fallback to any existing black video
            fallback_paths = [
                "/Users/abdulrehmanbhidya/Movies/black.mp4",
                os.path.join(os.path.dirname(__file__), "..", "static", "black_video.mp4")
            ]
            for path in fallback_paths:
                if os.path.exists(path):
                    self.black_video_path = path
                    logger.info(f"Using existing black video at: {path}")
                    break
    
    def set_brightness(self, brightness: int) -> Dict[str, Any]:
        """
        Set brightness level and control DLNA devices accordingly
        
        Args:
            brightness: Brightness level (0-100)
            
        Returns:
            Dict with status information
        """
        logger.info(f"Setting brightness to {brightness}")
        
        if brightness == 0 and not self.is_blackout_active:
            # Activate blackout mode
            return self._activate_blackout()
        elif brightness > 0 and self.is_blackout_active:
            # Deactivate blackout mode
            return self._deactivate_blackout()
        else:
            # Just update brightness value without changing device states
            return {
                "brightness": brightness,
                "status": "updated",
                "blackout_active": self.is_blackout_active,
                "message": f"Brightness set to {brightness}%"
            }
    
    def _activate_blackout(self) -> Dict[str, Any]:
        """Activate blackout mode - display black video on all playing devices"""
        logger.info("Activating blackout mode")

        affected_devices = []
        errors = []
        overlay_cast_devices = []
        
        # Clean up any stalled streaming sessions before starting blackout
        try:
            from core.streaming_registry import StreamingSessionRegistry
            registry = StreamingSessionRegistry.get_instance()
            active_sessions = registry.get_active_sessions()
            
            # Mark all current sessions as completed before starting new ones
            for session in active_sessions:
                logger.info(f"Completing session {session.session_id} before blackout")
                session.complete()
        except Exception as e:
            logger.warning(f"Could not clean up streaming sessions: {e}")
        
        # Get all devices
        devices = self.runtime.get_devices()
        eligible_non_overlay_devices = [
            device for device in devices
            if device.status == "connected" and not self._is_overlay_cast_device(device)
        ]

        if eligible_non_overlay_devices and (not self.black_video_path or not os.path.exists(self.black_video_path)):
            logger.error("Black video not available")
            return {
                "brightness": 0,
                "status": "error",
                "error": "Black video file not available"
            }
        
        for device in devices:
            try:
                # Affect all connected DLNA devices (playing or idle)
                if device.status == "connected":
                    overlay_session = self._get_overlay_cast_session(device)
                    if overlay_session:
                        overlay_cast_devices.append(device.name)
                        logger.info(
                            "Skipping blackout video for overlay cast device %s; overlay window will dim in-page",
                            device.name,
                        )
                        continue

                    # Backup current state (even for idle devices)
                    # Get the actual file path (not the streaming URL) if device was playing
                    actual_video_path = None
                    was_playing = device.is_playing
                    
                    if was_playing and device.current_video:
                        # Device was playing - backup the video info
                        # First try to get the original file path from current_video_path
                        if hasattr(device, 'current_video_path') and device.current_video_path:
                            actual_video_path = device.current_video_path
                            logger.info(f"Using current_video_path for backup: {actual_video_path}")
                        else:
                            # Fallback to assigned_videos
                            assigned_path = self.runtime.get_assigned_video(device.name)
                            if assigned_path and os.path.exists(assigned_path):
                                actual_video_path = assigned_path
                                logger.info(f"Using assigned_videos for backup: {actual_video_path}")
                            else:
                                # Last resort - use current_video (which is the URL)
                                actual_video_path = device.current_video
                                logger.warning(f"Using current_video URL for backup: {actual_video_path}")
                    
                    self.device_state_backup[device.name] = {
                        "was_playing": was_playing,
                        "video_path": actual_video_path,
                        "video_url": getattr(device, 'streaming_url', None),
                        "is_looping": getattr(device, '_loop_enabled', False),
                        "timestamp": datetime.utcnow()
                    }
                    
                    logger.info(f"Backing up state for {device.name} (was_playing={was_playing}): {self.device_state_backup[device.name]}")
                    
                    # Stop current playback (if any)
                    if was_playing:
                        device.stop()
                        time.sleep(0.5)  # Brief pause
                    
                    # Display black video
                    # We'll use the auto_play_video method to play the black video
                    # The black video will loop continuously
                    success = self.runtime.auto_play_video(
                        device, 
                        self.black_video_path, 
                        loop=True  # Loop the black video
                    )
                    
                    if success:
                        device_info = f"{device.name} ({'was playing' if was_playing else 'was idle'})"
                        affected_devices.append(device_info)
                        logger.info(f"Successfully activated blackout on {device.name} (was_playing={was_playing})")
                    else:
                        errors.append(f"Failed to display black video on {device.name}")
                        logger.error(f"Failed to activate blackout on {device.name}")
                        
            except Exception as e:
                error_msg = f"Error processing device {device.name}: {e}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        self.is_blackout_active = True
        
        return {
            "brightness": 0,
            "status": "blackout_activated",
            "blackout_active": True,
            "affected_devices": affected_devices,
            "overlay_cast_devices": overlay_cast_devices,
            "device_count": len(affected_devices),
            "errors": errors if errors else None,
            "message": (
                f"Blackout activated on {len(affected_devices)} devices"
                if affected_devices
                else "Brightness dimming delegated to active overlay projections"
            )
        }
    
    def _deactivate_blackout(self) -> Dict[str, Any]:
        """Deactivate blackout mode - restore original videos"""
        logger.info("Deactivating blackout mode")
        
        restored_devices = []
        errors = []
        
        # Get all devices
        devices = self.runtime.get_devices()
        
        for device in devices:
            try:
                # Check if this device has a backed up state
                if device.name in self.device_state_backup:
                    backup = self.device_state_backup[device.name]
                    logger.info(f"Restoring state for {device.name}: {backup}")
                    
                    # Stop black video display
                    device.stop()
                    time.sleep(0.5)  # Brief pause
                    
                    # Check if device was playing before blackout
                    was_playing = backup.get("was_playing", False)
                    
                    if not was_playing:
                        # Device was idle before blackout - just leave it stopped
                        restored_devices.append(f"{device.name} (returned to idle)")
                        logger.info(f"Device {device.name} was idle before blackout, leaving in stopped state")
                        # Remove from backup after successful restore
                        del self.device_state_backup[device.name]
                        continue
                    
                    # Device was playing - restore original video
                    video_path = backup["video_path"]
                    
                    # Check if it's a URL or local file path
                    is_url = video_path.startswith(('http://', 'https://'))
                    
                    # For URLs, we can't check existence with os.path.exists
                    # For local files, verify they exist
                    can_restore = is_url or os.path.exists(video_path)
                    
                    if can_restore:
                        # If it's a URL, we need to extract the original file path
                        # The URL format is typically: http://ip:port/filename.mp4
                        if is_url:
                            logger.warning(f"Restoring from URL backup: {video_path}")
                            # Try to find the original file by searching for files with the same name
                            from urllib.parse import urlparse, unquote
                            parsed = urlparse(video_path)
                            filename = os.path.basename(unquote(parsed.path))
                            
                            # Search for the file in common locations
                            possible_paths = [
                                f"/Users/abdulrehmanbhidya/Movies/kitchendoorjune/{filename}",
                                f"/Users/abdulrehmanbhidya/Desktop/{filename}",
                                f"/Users/abdulrehmanbhidya/PycharmProjects/nano-dlna/web/backend/uploads/{filename}",
                                f"/Users/abdulrehmanbhidya/PycharmProjects/nano-dlna/web/uploads/videos/{filename}",
                            ]
                            
                            found_path = None
                            for path in possible_paths:
                                if os.path.exists(path):
                                    found_path = path
                                    logger.info(f"Found original file at: {found_path}")
                                    break
                            
                            if found_path:
                                video_path = found_path
                            else:
                                logger.error(f"Could not find original file for URL: {video_path}")
                                errors.append(f"Could not locate original file for {device.name}")
                                continue
                        
                        success = self.runtime.auto_play_video(
                            device,
                            video_path,
                            loop=backup.get("is_looping", True)
                        )
                        
                        if success:
                            restored_devices.append(f"{device.name} (restored video)")
                            logger.info(f"Successfully restored video on {device.name}")
                            # Remove from backup after successful restore
                            del self.device_state_backup[device.name]
                            
                            # Trigger overlay sync
                            try:
                                import requests
                                response = requests.post(
                                    "http://localhost:8000/api/overlay/sync",
                                    params={
                                        "triggered_by": "brightness_restore",
                                        "video_name": os.path.basename(video_path) if video_path else None
                                    },
                                    timeout=2
                                )
                                if response.status_code == 200:
                                    logger.info(f"Triggered overlay sync after brightness restore for {device.name}")
                            except Exception as e:
                                logger.warning(f"Failed to sync overlays after brightness restore: {e}")
                        else:
                            errors.append(f"Failed to restore video on {device.name}")
                            logger.error(f"Failed to restore video on {device.name}")
                    else:
                        errors.append(f"Original video not found for {device.name}: {video_path}")
                        logger.error(f"Original video not found: {video_path}")
                elif self._is_overlay_cast_device(device):
                    restored_devices.append(f"{device.name} (overlay cast dimming only)")
                    logger.info(f"Overlay cast device {device.name} did not require blackout restore")
                    continue
                        
            except Exception as e:
                error_msg = f"Error restoring device {device.name}: {e}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        self.is_blackout_active = False
        
        return {
            "brightness": 100,  # Default restored brightness
            "status": "blackout_deactivated", 
            "blackout_active": False,
            "restored_devices": restored_devices,
            "device_count": len(restored_devices),
            "errors": errors if errors else None,
            "message": f"Blackout deactivated, restored {len(restored_devices)} devices"
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get current brightness control status"""
        playing_devices = []
        
        devices = self.runtime.get_devices()
        for device in devices:
            if device.is_playing:
                playing_devices.append({
                    "name": device.name,
                    "current_video": device.current_video,
                    "is_black_video": device.current_video == self.black_video_path if device.current_video else False
                })
        
        return {
            "blackout_active": self.is_blackout_active,
            "black_video_available": bool(self.black_video_path and os.path.exists(self.black_video_path)),
            "black_video_path": self.black_video_path,
            "playing_devices": playing_devices,
            "backed_up_devices": list(self.device_state_backup.keys()),
            "overlay_cast_devices": [
                device.name for device in devices if self._is_overlay_cast_device(device)
            ],
            "total_devices": len(devices),
            "playing_count": len(playing_devices)
        }

# Singleton instance
_brightness_control_instance = None

def get_brightness_control_service() -> BrightnessControlService:
    """Get singleton instance of brightness control service"""
    global _brightness_control_instance
    if _brightness_control_instance is None:
        _brightness_control_instance = BrightnessControlService()
    return _brightness_control_instance
