"""
Migration adapter to integrate the new unified discovery system with the existing codebase.
Provides backward compatibility while transitioning to the new architecture.
"""

import logging
import asyncio
from urllib.parse import urlparse
from typing import Dict, List, Optional, Any
import threading

from core.device_manager import DeviceManager
from core.dlna_device import DLNADevice
from core.transcreen_device import TranscreenDevice
from core.config_service import ConfigService

from .discovery_manager import DiscoveryManager
from .backends import DLNADiscoveryBackend, AirPlayDiscoveryBackend, OverlayDiscoveryBackend
from .base import Device, CastingMethod, DeviceCapability
from .config import ConfigurationManager

logger = logging.getLogger(__name__)


class DiscoveryMigrationAdapter:
    """
    Adapter to bridge the old DeviceManager with the new DiscoveryManager.
    Provides backward compatibility during migration.
    """
    
    def __init__(self, device_manager: DeviceManager):
        """
        Initialize the migration adapter.
        
        Args:
            device_manager: Existing DeviceManager instance
        """
        self.old_device_manager = device_manager
        self.new_discovery_manager = DiscoveryManager.get_instance()
        self.config_manager = ConfigurationManager.get_instance()
        
        # Map old device instances to new unified devices
        self._device_mapping: Dict[str, Device] = {}
        
        # Initialize discovery backends
        self._init_backends()
        
        # Start migration in background
        self._migration_thread = threading.Thread(target=self._run_migration_loop)
        self._migration_thread.daemon = True
        self._migration_running = False
        
    def _init_backends(self):
        """Initialize and register discovery backends."""
        # Register DLNA backend
        dlna_backend = DLNADiscoveryBackend()
        self.new_discovery_manager.register_backend(dlna_backend)
        
        # Register AirPlay backend
        airplay_backend = AirPlayDiscoveryBackend()
        self.new_discovery_manager.register_backend(airplay_backend)
        
        # Register Overlay backend
        overlay_backend = OverlayDiscoveryBackend()
        self.new_discovery_manager.register_backend(overlay_backend)
        
        logger.info("Initialized discovery backends for migration")
        
    def start_migration(self):
        """Start the migration process."""
        self._migration_running = True
        self._migration_thread.start()
        logger.info("Started discovery migration adapter")
        
    def stop_migration(self):
        """Stop the migration process."""
        self._migration_running = False
        if self._migration_thread.is_alive():
            self._migration_thread.join(timeout=5)
        logger.info("Stopped discovery migration adapter")
        
    def _run_migration_loop(self):
        """Main migration loop running in background thread."""
        # Create event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Initial migration of existing devices
            loop.run_until_complete(self._migrate_existing_devices())
            
            # Start discovery on new system
            loop.run_until_complete(self.new_discovery_manager.start_discovery())
            
            # Monitor and sync changes
            while self._migration_running:
                loop.run_until_complete(self._sync_devices())
                loop.run_until_complete(asyncio.sleep(5))  # Sync every 5 seconds
                
        except Exception as e:
            logger.error(f"Error in migration loop: {e}")
        finally:
            loop.run_until_complete(self.new_discovery_manager.stop_discovery())
            loop.close()
            
    async def _migrate_existing_devices(self):
        """Migrate existing devices from old system to new."""
        logger.info("Migrating existing devices to new discovery system")
        
        # Migrate configuration first
        self._migrate_configuration()
        
        # Get all devices from old manager
        old_devices = self.old_device_manager.get_devices()
        
        for old_device in old_devices:
            try:
                new_device = self._convert_old_to_new_device(old_device)
                if new_device:
                    # Add to mapping
                    self._device_mapping[old_device.name] = new_device
                    
                    # Register with new system
                    with self.new_discovery_manager._device_lock:
                        self.new_discovery_manager.all_devices[new_device.id] = new_device
                        
                    logger.info(f"Migrated device: {old_device.name}")
                    
            except Exception as e:
                logger.error(f"Failed to migrate device {old_device.name}: {e}")
                
    def _migrate_configuration(self):
        """Migrate configuration from old system to new."""
        try:
            # Get old config service
            old_config = ConfigService.get_instance()
            
            # Migrate device configs
            device_configs = old_config.get_all_device_configs()
            
            for device_name, config in device_configs.items():
                # Convert to new format
                new_config = {
                    "name": device_name,
                    "casting_method": config.get("type", "dlna"),
                    "content": {
                        "url": config.get("video_file", ""),
                        "type": config.get("mime_type", "video/mp4"),
                        "loop": config.get("loop", True)
                    },
                    "priority": config.get("priority", 50),
                    "metadata": {
                        "hostname": config.get("hostname"),
                        "action_url": config.get("action_url"),
                        "airplay_mode": config.get("airplay_mode", False),
                        "airplay_url": config.get("airplay_url")
                    }
                }
                
                self.config_manager.update_device_config(device_name, new_config)
                
            logger.info(f"Migrated {len(device_configs)} device configurations")
            
        except Exception as e:
            logger.error(f"Failed to migrate configuration: {e}")
            
    def _convert_old_to_new_device(self, old_device) -> Optional[Device]:
        """Convert old device instance to new unified Device."""
        try:
            port = getattr(old_device, "port", None)
            if port is None:
                action_url = getattr(old_device, "action_url", None)
                if action_url:
                    parsed = urlparse(action_url)
                    port = parsed.port
                    if port is None and parsed.scheme == "https":
                        port = 443
                if port is None:
                    port = 80

            # Determine casting method
            if isinstance(old_device, DLNADevice):
                casting_method = CastingMethod.DLNA
                capabilities = [
                    DeviceCapability.VIDEO_PLAYBACK,
                    DeviceCapability.AUDIO_PLAYBACK,
                    DeviceCapability.VOLUME_CONTROL,
                    DeviceCapability.SEEK_CONTROL
                ]
            elif isinstance(old_device, TranscreenDevice):
                casting_method = CastingMethod.DLNA  # Transcreen uses DLNA protocol
                capabilities = [
                    DeviceCapability.VIDEO_PLAYBACK,
                    DeviceCapability.IMAGE_DISPLAY
                ]
            else:
                logger.warning(f"Unknown device type: {type(old_device)}")
                return None
                
            # Create new device
            new_device = Device(
                id=f"{casting_method.value}_{old_device.hostname}_{port}",
                name=old_device.name,
                friendly_name=getattr(old_device, "friendly_name", None) or old_device.name,
                casting_method=casting_method,
                hostname=old_device.hostname,
                port=port,
                capabilities=capabilities,
                metadata={
                    "legacy_device": True,
                    "original_type": old_device.type
                },
                action_url=old_device.action_url if hasattr(old_device, 'action_url') else None,
                location=old_device.location if hasattr(old_device, 'location') else None,
                manufacturer=old_device.manufacturer if hasattr(old_device, 'manufacturer') else None
            )
            
            # Copy playing state
            new_device.is_online = True
            
            return new_device
            
        except Exception as e:
            logger.error(f"Failed to convert device {old_device.name}: {e}")
            return None
            
    async def _sync_devices(self):
        """Sync devices between old and new systems."""
        try:
            # Sync device states from old to new
            old_devices = self.old_device_manager.get_devices()
            
            for old_device in old_devices:
                if old_device.name in self._device_mapping:
                    new_device = self._device_mapping[old_device.name]
                    
                    # Update online status
                    with self.old_device_manager.device_state_lock:
                        if old_device.name in self.old_device_manager.device_status:
                            status = self.old_device_manager.device_status[old_device.name]
                            new_device.is_online = status.get("status") == "connected"
                            
            # Sync new discoveries back to old system
            new_devices = self.new_discovery_manager.get_all_devices()
            
            for new_device in new_devices:
                if new_device.casting_method == CastingMethod.DLNA:
                    # Check if device exists in old system
                    old_device = self.old_device_manager.get_device(new_device.name)
                    
                    if not old_device and not new_device.metadata.get("legacy_device"):
                        # Register new device in old system
                        device_info = {
                            "device_name": new_device.name,
                            "type": "dlna",
                            "hostname": new_device.hostname,
                            "action_url": new_device.action_url,
                            "friendly_name": new_device.friendly_name,
                            "manufacturer": new_device.manufacturer,
                            "location": new_device.location
                        }
                        
                        self.old_device_manager.register_device(device_info)
                        logger.info(f"Synced new device to old system: {new_device.name}")
                        
        except Exception as e:
            logger.error(f"Error syncing devices: {e}")
            
    def cast_content(self, device_name: str, content_url: str, 
                    content_type: str = "video/mp4") -> bool:
        """
        Cast content using the new system while maintaining old interface.
        
        Args:
            device_name: Name of device to cast to
            content_url: URL of content
            content_type: MIME type of content
            
        Returns:
            True if successful
        """
        try:
            # Find device in new system
            device = None
            for d in self.new_discovery_manager.get_all_devices():
                if d.name == device_name:
                    device = d
                    break
                    
            if not device:
                logger.error(f"Device {device_name} not found in new system")
                return False
                
            # Cast using new system
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            session = loop.run_until_complete(
                self.new_discovery_manager.cast_content(
                    device.id, content_url, content_type
                )
            )
            
            loop.close()
            
            return session is not None
            
        except Exception as e:
            logger.error(f"Failed to cast content: {e}")
            return False
            
    def get_discovery_status(self) -> Dict[str, Any]:
        """Get status of both old and new discovery systems."""
        old_status = {
            "devices": len(self.old_device_manager.devices),
            "playing": sum(1 for d in self.old_device_manager.devices.values() if d.is_playing)
        }
        
        new_status = self.new_discovery_manager.get_backend_status()
        
        return {
            "migration_active": self._migration_running,
            "old_system": old_status,
            "new_system": new_status,
            "device_mappings": len(self._device_mapping)
        }


# Utility function to start migration
def start_discovery_migration(device_manager: DeviceManager) -> DiscoveryMigrationAdapter:
    """
    Start the discovery system migration.
    
    Args:
        device_manager: Existing DeviceManager instance
        
    Returns:
        Migration adapter instance
    """
    adapter = DiscoveryMigrationAdapter(device_manager)
    adapter.start_migration()
    return adapter
