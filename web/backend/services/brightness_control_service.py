"""
Brightness control service that manages DLNA devices based on brightness settings
"""
import logging
import os
import time
from typing import Dict, List, Optional, Any
from datetime import datetime

from routers.device_router import device_manager
from services.device_service import DeviceService
from database.database import get_db
from utils.create_black_video import create_black_video

logger = logging.getLogger(__name__)

class BrightnessControlService:
    """
    Service to control DLNA devices based on brightness settings
    When brightness is 0, cast black video to all playing devices
    When brightness is restored, resume original videos
    """
    
    def __init__(self):
        self.device_manager = device_manager
        self.black_video_path = None
        self.device_state_backup = {}  # Store device states before blackout
        self.is_blackout_active = False
        self._ensure_black_video()
    
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
        
        if not self.black_video_path or not os.path.exists(self.black_video_path):
            logger.error("Black video not available")
            return {
                "brightness": 0,
                "status": "error",
                "error": "Black video file not available"
            }
        
        affected_devices = []
        errors = []
        
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
        devices = self.device_manager.get_devices()
        
        for device in devices:
            try:
                # Affect all connected DLNA devices (playing or idle)
                if device.status == "connected":
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
                            with self.device_manager.device_state_lock:
                                assigned_path = self.device_manager.assigned_videos.get(device.name)
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
                    success = self.device_manager.auto_play_video(
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
            "device_count": len(affected_devices),
            "errors": errors if errors else None,
            "message": f"Blackout activated on {len(affected_devices)} devices"
        }
    
    def _deactivate_blackout(self) -> Dict[str, Any]:
        """Deactivate blackout mode - restore original videos"""
        logger.info("Deactivating blackout mode")
        
        restored_devices = []
        errors = []
        
        # Get all devices
        devices = self.device_manager.get_devices()
        
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
                        
                        success = self.device_manager.auto_play_video(
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
        
        devices = self.device_manager.get_devices()
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