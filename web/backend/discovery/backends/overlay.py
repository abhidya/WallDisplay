"""
Overlay/Extended Desktop discovery backend implementation.
"""

import asyncio
import logging
import subprocess
import uuid
import platform
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    import screeninfo
    SCREENINFO_AVAILABLE = True
except ImportError:
    SCREENINFO_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("screeninfo not installed. Display enumeration will not be available.")
    logger.info("Install with: pip install screeninfo")

from ..base import DiscoveryBackend, Device, CastingMethod, CastingSession, DeviceCapability

logger = logging.getLogger(__name__)
DISPLAY_DISCOVERY_TIMEOUT_SECONDS = 3


class OverlayDiscoveryBackend(DiscoveryBackend):
    """
    Discovery backend for overlay casting to extended displays.
    This method uses the system's display configuration to project overlays.
    """
    
    def __init__(self):
        super().__init__("Overlay", CastingMethod.OVERLAY)
        self._overlay_windows = {}  # Track active overlay windows
        
    async def discover_devices(self) -> List[Device]:
        """
        Discover available displays for overlay casting.
        """
        logger.debug("Starting overlay/display discovery")
        
        devices = []
        
        # Method 1: Use screeninfo to enumerate displays
        if SCREENINFO_AVAILABLE:
            try:
                monitors = screeninfo.get_monitors()
                for idx, monitor in enumerate(monitors):
                    device = self._create_device_from_monitor(idx, monitor)
                    devices.append(device)
                    logger.info(f"Discovered display: {device.name}")
            except Exception as e:
                logger.error(f"Error enumerating displays with screeninfo: {e}")
        
        # Method 2: Platform-specific display enumeration
        if not devices:
            devices = await self._platform_specific_discovery()
            
        # Method 3: Always add a virtual overlay device for web-based overlay
        virtual_device = Device(
            id="overlay_virtual_web",
            name="Web Overlay (Browser)",
            friendly_name="Web-based Overlay Window",
            casting_method=CastingMethod.OVERLAY,
            hostname="localhost",
            port=8000,  # Default web server port
            capabilities=[
                DeviceCapability.WEB_CONTENT,
                DeviceCapability.VIDEO_PLAYBACK,
                DeviceCapability.IMAGE_DISPLAY
            ],
            metadata={
                "type": "virtual",
                "url_template": "http://localhost:8000/static/overlay_window.html"
            },
            display_index=-1,  # Virtual display
            resolution=(1920, 1080)  # Default resolution
        )
        devices.append(virtual_device)
        
        logger.info(f"Discovered {len(devices)} overlay display targets")
        return devices
    
    def _create_device_from_monitor(self, index: int, monitor: Any) -> Device:
        """Create Device object from monitor info."""
        # Determine if this is the primary display
        is_primary = getattr(monitor, 'is_primary', index == 0)
        
        name = f"Display {index + 1}"
        if is_primary:
            name += " (Primary)"
            
        device = Device(
            id=f"overlay_display_{index}",
            name=name,
            friendly_name=f"{monitor.name if hasattr(monitor, 'name') else name} - {monitor.width}x{monitor.height}",
            casting_method=CastingMethod.OVERLAY,
            hostname="localhost",
            port=0,  # No network port for local displays
            capabilities=[
                DeviceCapability.WEB_CONTENT,
                DeviceCapability.VIDEO_PLAYBACK,
                DeviceCapability.IMAGE_DISPLAY,
                DeviceCapability.SCREEN_MIRRORING
            ],
            metadata={
                "type": "physical",
                "is_primary": is_primary,
                "x": monitor.x,
                "y": monitor.y,
                "width": monitor.width,
                "height": monitor.height
            },
            display_index=index,
            resolution=(monitor.width, monitor.height)
        )
        
        return device
    
    async def _platform_specific_discovery(self) -> List[Device]:
        """Platform-specific display discovery as fallback."""
        devices = []
        system = platform.system()
        
        if system == "Darwin":  # macOS
            # Use system_profiler to get display info
            try:
                result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType", "-json"],
                    capture_output=True,
                    text=True,
                    timeout=DISPLAY_DISCOVERY_TIMEOUT_SECONDS,
                )
                if result.returncode == 0:
                    import json
                    data = json.loads(result.stdout)
                    # Parse display data (simplified)
                    logger.debug("Found displays via system_profiler")
            except subprocess.TimeoutExpired:
                logger.warning("Timed out while collecting macOS display info")
            except Exception as e:
                logger.error(f"Failed to get macOS display info: {e}")
                
        elif system == "Windows":
            # Use WMI or similar to get display info
            try:
                # Simplified - would need pywin32 or wmi package
                logger.debug("Windows display enumeration not fully implemented")
            except Exception as e:
                logger.error(f"Failed to get Windows display info: {e}")
                
        elif system == "Linux":
            # Use xrandr or similar
            try:
                result = subprocess.run(
                    ["xrandr", "--query"],
                    capture_output=True,
                    text=True,
                    timeout=DISPLAY_DISCOVERY_TIMEOUT_SECONDS,
                )
                if result.returncode == 0:
                    # Parse xrandr output (simplified)
                    logger.debug("Found displays via xrandr")
            except subprocess.TimeoutExpired:
                logger.warning("Timed out while collecting Linux display info")
            except Exception as e:
                logger.error(f"Failed to get Linux display info: {e}")
                
        return devices
    
    async def cast_content(self, device: Device, content_url: str,
                          content_type: str = "video/mp4",
                          metadata: Optional[Dict[str, Any]] = None) -> CastingSession:
        """
        Cast content to an overlay display.
        This creates an overlay window on the specified display.
        """
        if device.casting_method != CastingMethod.OVERLAY:
            raise ValueError(f"Device {device.name} is not an overlay device")
            
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # Determine overlay type
        if device.display_index == -1:  # Virtual web overlay
            # Return URL for web-based overlay
            overlay_url = self._create_web_overlay_url(content_url, metadata)
            
            casting_session = CastingSession(
                id=session_id,
                device=device,
                content_url=overlay_url,
                content_type="text/html",
                metadata={
                    "original_content": content_url,
                    "original_type": content_type,
                    **(metadata or {})
                }
            )
            
            logger.info(f"Created web overlay session: {overlay_url}")
            
        else:  # Physical display overlay
            # This would create a native window on the specified display
            # For now, we'll use the web overlay approach
            overlay_url = self._create_web_overlay_url(content_url, metadata)
            
            casting_session = CastingSession(
                id=session_id,
                device=device,
                content_url=overlay_url,
                content_type="text/html",
                metadata={
                    "original_content": content_url,
                    "original_type": content_type,
                    "display_index": device.display_index,
                    "display_bounds": device.metadata,
                    **(metadata or {})
                }
            )
            
            logger.info(f"Created display overlay session for {device.name}")
            
        # Track session
        self.active_sessions[session_id] = casting_session
        self._overlay_windows[session_id] = {
            "url": overlay_url,
            "device": device,
            "created_at": datetime.now()
        }
        
        return casting_session
    
    def _create_web_overlay_url(self, content_url: str, 
                               metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create URL for web-based overlay with content."""
        base_url = "http://localhost:8000/static/overlay_window.html"
        
        # Add query parameters for configuration
        params = []
        
        # If it's a video URL, set it as the background video
        if content_url and any(content_url.endswith(ext) for ext in ['.mp4', '.webm', '.ogg']):
            params.append(f"video={content_url}")
            
        # Add metadata as query params
        if metadata:
            if "widgets" in metadata:
                # This would need to be encoded properly
                params.append("widgets=configured")
            if "title" in metadata:
                params.append(f"title={metadata['title']}")
                
        if params:
            return f"{base_url}?{'&'.join(params)}"
        return base_url
    
    async def stop_casting(self, session: CastingSession) -> bool:
        """Stop overlay casting."""
        try:
            # Remove from tracking
            if session.id in self._overlay_windows:
                del self._overlay_windows[session.id]
                
            session.is_active = False
            self.active_sessions.pop(session.id, None)
            
            # For web overlays, the user closes the browser window
            # For native overlays, we would close the window here
            
            logger.info(f"Stopped overlay session {session.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop overlay casting: {e}")
            return False
    
    async def pause_casting(self, session: CastingSession) -> bool:
        """Pause overlay content (if applicable)."""
        # For video overlays, this would pause the video
        # Implementation depends on the overlay mechanism
        session.is_paused = True
        return True
    
    async def resume_casting(self, session: CastingSession) -> bool:
        """Resume overlay content."""
        session.is_paused = False
        return True
    
    async def seek(self, session: CastingSession, position: float) -> bool:
        """Seek in overlay content (if video)."""
        # This would require communication with the overlay window
        # For web overlays, could use WebSocket or polling
        session.position = position
        return True
    
    async def get_status(self, session: CastingSession) -> Dict[str, Any]:
        """Get overlay session status."""
        overlay_info = self._overlay_windows.get(session.id, {})
        
        return {
            "is_active": session.is_active,
            "is_paused": session.is_paused,
            "content_url": session.content_url,
            "overlay_url": overlay_info.get("url"),
            "device": session.device.name,
            "created_at": overlay_info.get("created_at", session.started_at).isoformat(),
            "metadata": session.metadata
        }
    
    def supports_capability(self, capability: DeviceCapability) -> bool:
        """Check if overlay backend supports a capability."""
        # Overlay supports web content and media display
        supported = [
            DeviceCapability.WEB_CONTENT,
            DeviceCapability.VIDEO_PLAYBACK,
            DeviceCapability.IMAGE_DISPLAY,
            DeviceCapability.SCREEN_MIRRORING
        ]
        return capability in supported
