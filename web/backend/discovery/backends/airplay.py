"""
AirPlay discovery backend implementation.
"""

import asyncio
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
import aiohttp

try:
    from zeroconf import ServiceBrowser, Zeroconf
    from zeroconf.asyncio import AsyncZeroconf
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("python-zeroconf not installed. AirPlay discovery will not be available.")
    logger.info("Install with: pip install zeroconf")

from ..base import DiscoveryBackend, Device, CastingMethod, CastingSession, DeviceCapability

logger = logging.getLogger(__name__)


class AirPlayDiscoveryBackend(DiscoveryBackend):
    """
    Discovery backend for AirPlay devices using Bonjour/mDNS.
    """
    
    def __init__(self):
        super().__init__("AirPlay", CastingMethod.AIRPLAY)
        self._zeroconf = None
        self._browser = None
        self._discovered_services = {}
        self._zeroconf_unavailable_warning_logged = False
        
    async def discover_devices(self) -> List[Device]:
        """
        Discover AirPlay devices on the network using mDNS.
        """
        if not ZEROCONF_AVAILABLE:
            if not self._zeroconf_unavailable_warning_logged:
                logger.warning("Zeroconf not available, cannot discover AirPlay devices")
                self._zeroconf_unavailable_warning_logged = True
            return []
            
        logger.debug("Starting AirPlay device discovery")
        
        try:
            # Initialize Zeroconf
            self._zeroconf = AsyncZeroconf()
            
            # Create service listener
            listener = AirPlayListener(self)
            
            # Browse for AirPlay services
            self._browser = ServiceBrowser(
                self._zeroconf.zeroconf,
                ["_airplay._tcp.local.", "_raop._tcp.local."],
                listener
            )
            
            # Wait for discovery
            await asyncio.sleep(3)
            
            # Convert discovered services to devices
            devices = []
            for service_name, service_info in self._discovered_services.items():
                device = self._create_device_from_service(service_info)
                if device:
                    devices.append(device)
                    
            logger.info(f"Discovered {len(devices)} AirPlay devices")
            return devices
            
        except Exception as e:
            logger.error(f"Error during AirPlay discovery: {e}")
            return []
    
    def _create_device_from_service(self, service_info: Dict[str, Any]) -> Optional[Device]:
        """Create Device object from mDNS service info."""
        try:
            # Extract device information
            name = service_info.get("name", "Unknown AirPlay Device")
            hostname = service_info.get("hostname", "")
            port = service_info.get("port", 7000)
            
            # Parse TXT record for additional info
            properties = service_info.get("properties", {})
            model = properties.get("model", "Unknown")
            features = properties.get("features", 0)
            
            # Determine capabilities based on features
            capabilities = [
                DeviceCapability.VIDEO_PLAYBACK,
                DeviceCapability.AUDIO_PLAYBACK,
                DeviceCapability.SCREEN_MIRRORING
            ]
            
            if features & 0x20:  # Supports volume control
                capabilities.append(DeviceCapability.VOLUME_CONTROL)
                
            # Create device object
            device = Device(
                id=f"airplay_{hostname}_{port}",
                name=name,
                friendly_name=name,
                casting_method=CastingMethod.AIRPLAY,
                hostname=hostname,
                port=port,
                capabilities=capabilities,
                metadata={
                    "features": features,
                    "flags": properties.get("flags", 0),
                    "pk": properties.get("pk"),
                    "pi": properties.get("pi"),
                    "vv": properties.get("vv", 1)
                },
                model=model,
                features=features
            )
            
            logger.info(f"Discovered AirPlay device: {name} at {hostname}:{port}")
            return device
            
        except Exception as e:
            logger.error(f"Error creating device from service: {e}")
            return None
    
    async def cast_content(self, device: Device, content_url: str,
                          content_type: str = "video/mp4",
                          metadata: Optional[Dict[str, Any]] = None) -> CastingSession:
        """
        Cast content to an AirPlay device.
        
        Note: This is a simplified implementation. Full AirPlay protocol
        requires authentication and encryption for many devices.
        """
        if device.casting_method != CastingMethod.AIRPLAY:
            raise ValueError(f"Device {device.name} is not an AirPlay device")
            
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # Prepare playback info
        playback_info = {
            "Content-Location": content_url,
            "Start-Position": "0.0"
        }
        
        # Add metadata if provided
        if metadata:
            if "title" in metadata:
                playback_info["X-Apple-Session-Name"] = metadata["title"]
                
        # Send play request
        url = f"http://{device.hostname}:{device.port}/play"
        headers = {
            "User-Agent": "nano-dlna/1.0",
            "X-Apple-Session-ID": session_id
        }
        headers.update(playback_info)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers) as response:
                    if response.status != 200:
                        raise Exception(f"Failed to start playback: {response.status}")
                        
            # Create session
            casting_session = CastingSession(
                id=session_id,
                device=device,
                content_url=content_url,
                content_type=content_type,
                metadata=metadata or {}
            )
            
            # Track session
            self.active_sessions[session_id] = casting_session
            
            logger.info(f"Started AirPlay casting to {device.name}")
            return casting_session
            
        except Exception as e:
            logger.error(f"Failed to cast to AirPlay device: {e}")
            raise
    
    async def stop_casting(self, session: CastingSession) -> bool:
        """Stop casting on AirPlay device."""
        try:
            url = f"http://{session.device.hostname}:{session.device.port}/stop"
            headers = {
                "User-Agent": "nano-dlna/1.0",
                "X-Apple-Session-ID": session.id
            }
            
            async with aiohttp.ClientSession() as http_session:
                async with http_session.post(url, headers=headers) as response:
                    success = response.status == 200
                    
            if success:
                session.is_active = False
                self.active_sessions.pop(session.id, None)
                
            return success
            
        except Exception as e:
            logger.error(f"Failed to stop AirPlay casting: {e}")
            return False
    
    async def pause_casting(self, session: CastingSession) -> bool:
        """Pause casting on AirPlay device."""
        try:
            url = f"http://{session.device.hostname}:{session.device.port}/pause"
            headers = {
                "User-Agent": "nano-dlna/1.0",
                "X-Apple-Session-ID": session.id
            }
            
            async with aiohttp.ClientSession() as http_session:
                async with http_session.post(url, headers=headers) as response:
                    if response.status == 200:
                        session.is_paused = True
                        return True
                        
            return False
            
        except Exception as e:
            logger.error(f"Failed to pause AirPlay casting: {e}")
            return False
    
    async def resume_casting(self, session: CastingSession) -> bool:
        """Resume casting on AirPlay device."""
        try:
            url = f"http://{session.device.hostname}:{session.device.port}/play"
            headers = {
                "User-Agent": "nano-dlna/1.0",
                "X-Apple-Session-ID": session.id
            }
            
            async with aiohttp.ClientSession() as http_session:
                async with http_session.post(url, headers=headers) as response:
                    if response.status == 200:
                        session.is_paused = False
                        return True
                        
            return False
            
        except Exception as e:
            logger.error(f"Failed to resume AirPlay casting: {e}")
            return False
    
    async def seek(self, session: CastingSession, position: float) -> bool:
        """Seek to position on AirPlay device."""
        try:
            url = f"http://{session.device.hostname}:{session.device.port}/scrub"
            headers = {
                "User-Agent": "nano-dlna/1.0",
                "X-Apple-Session-ID": session.id
            }
            params = {"position": str(position)}
            
            async with aiohttp.ClientSession() as http_session:
                async with http_session.post(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        session.position = position
                        return True
                        
            return False
            
        except Exception as e:
            logger.error(f"Failed to seek on AirPlay device: {e}")
            return False
    
    async def get_status(self, session: CastingSession) -> Dict[str, Any]:
        """Get playback status from AirPlay device."""
        try:
            url = f"http://{session.device.hostname}:{session.device.port}/scrub"
            headers = {
                "User-Agent": "nano-dlna/1.0",
                "X-Apple-Session-ID": session.id
            }
            
            async with aiohttp.ClientSession() as http_session:
                async with http_session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.text()
                        # Parse playback status (simplified)
                        # Real implementation would parse the plist response
                        return {
                            "is_playing": session.is_active and not session.is_paused,
                            "position": session.position,
                            "duration": session.duration,
                            "content_url": session.content_url
                        }
                        
            return {"error": "Failed to get status"}
            
        except Exception as e:
            logger.error(f"Failed to get AirPlay status: {e}")
            return {"error": str(e)}
    
    async def stop_discovery(self):
        """Stop AirPlay discovery."""
        await super().stop_discovery()
        
        if self._browser:
            self._browser.cancel()
            self._browser = None
            
        if self._zeroconf:
            await self._zeroconf.close()
            self._zeroconf = None
            
        self._discovered_services.clear()


class AirPlayListener:
    """mDNS service listener for AirPlay discovery."""
    
    def __init__(self, backend: AirPlayDiscoveryBackend):
        self.backend = backend
        
    def add_service(self, zeroconf, service_type, name):
        """Called when a service is discovered."""
        info = zeroconf.get_service_info(service_type, name)
        if info:
            # Parse service info
            service_info = {
                "name": info.name,
                "hostname": info.server,
                "port": info.port,
                "properties": {}
            }
            
            # Parse TXT record properties
            if info.properties:
                for key, value in info.properties.items():
                    if isinstance(key, bytes):
                        key = key.decode('utf-8', errors='ignore')
                    if isinstance(value, bytes):
                        try:
                            value = value.decode('utf-8')
                        except:
                            value = str(value)
                    service_info["properties"][key] = value
                    
            self.backend._discovered_services[name] = service_info
            logger.debug(f"Discovered AirPlay service: {name}")
            
    def remove_service(self, zeroconf, service_type, name):
        """Called when a service is removed."""
        if name in self.backend._discovered_services:
            del self.backend._discovered_services[name]
            logger.debug(f"Removed AirPlay service: {name}")
            
    def update_service(self, zeroconf, service_type, name):
        """Called when a service is updated."""
        # Re-add the service with updated info
        self.add_service(zeroconf, service_type, name)