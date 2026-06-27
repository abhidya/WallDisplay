"""
Unified configuration manager for the discovery system.
Provides centralized configuration with hot-reload support.
"""

import json
import os
import logging
import threading
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from pathlib import Path
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from sqlalchemy.orm import Session
from web.backend.database.database import get_db
from web.backend.models.device import DeviceModel

logger = logging.getLogger(__name__)


class ConfigurationManager:
    """
    Centralized configuration manager with database persistence and file watching.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls):
        """Get singleton instance of ConfigurationManager"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        """Initialize the configuration manager"""
        self._config_lock = threading.RLock()
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._config_sources: Dict[str, str] = {}
        self._callbacks: List[Callable] = []
        self._file_watchers: Dict[str, Observer] = {}
        
        # Configuration schema for validation
        self._schema = {
            "device": {
                "required": ["name", "casting_method", "content"],
                "optional": ["priority", "schedule", "group", "zone", "metadata"]
            },
            "global": {
                "required": [],
                "optional": ["discovery_interval", "auto_cast", "retry_policy", "health_check"]
            }
        }
        
        # Default global configuration
        self._global_config = {
            "discovery_interval": 10,
            "auto_cast": True,
            "retry_policy": {
                "max_attempts": 3,
                "delay_seconds": 5,
                "backoff_multiplier": 2
            },
            "health_check": {
                "enabled": True,
                "interval_seconds": 30,
                "timeout_seconds": 5
            }
        }
        
    def load_from_file(self, file_path: str, watch: bool = True) -> bool:
        """
        Load configuration from a JSON file.
        
        Args:
            file_path: Path to configuration file
            watch: Whether to watch the file for changes
            
        Returns:
            True if successful
        """
        try:
            abs_path = Path(file_path).resolve()
            if not abs_path.exists():
                logger.error(f"Configuration file not found: {abs_path}")
                return False
                
            with open(abs_path, 'r') as f:
                data = json.load(f)
                
            # Process configuration data
            if isinstance(data, list):
                # List of device configurations
                for device_config in data:
                    if self._validate_device_config(device_config):
                        self._add_device_config(device_config, str(abs_path))
                        
            elif isinstance(data, dict):
                # Could be global config or device configs
                if "devices" in data:
                    for device_config in data["devices"]:
                        if self._validate_device_config(device_config):
                            self._add_device_config(device_config, str(abs_path))
                            
                if "global" in data:
                    self._update_global_config(data["global"])
                    
            # Set up file watcher if requested
            if watch:
                self._setup_file_watcher(str(abs_path))
                
            logger.info(f"Loaded configuration from {abs_path}")
            self._notify_callbacks("config_loaded", {"source": str(abs_path)})
            return True
            
        except Exception as e:
            logger.error(f"Error loading configuration from {file_path}: {e}")
            return False
    
    def load_from_database(self, db: Session) -> bool:
        """
        Load device configurations from database.
        
        Args:
            db: Database session
            
        Returns:
            True if successful
        """
        try:
            devices = db.query(DeviceModel).all()
            
            for device in devices:
                config = {
                    "name": device.name,
                    "casting_method": device.type,
                    "content": {
                        "url": device.current_video,
                        "type": "video/mp4"
                    },
                    "metadata": device.config or {}
                }
                
                if device.config:
                    # Merge device-specific config
                    config.update(device.config)
                    
                self._add_device_config(config, "database")
                
            logger.info(f"Loaded {len(devices)} device configurations from database")
            return True
            
        except Exception as e:
            logger.error(f"Error loading configurations from database: {e}")
            return False
    
    def save_to_file(self, file_path: str, include_global: bool = True) -> bool:
        """
        Save current configuration to a file.
        
        Args:
            file_path: Path to save configuration
            include_global: Whether to include global configuration
            
        Returns:
            True if successful
        """
        try:
            with self._config_lock:
                data = {
                    "devices": list(self._configs.values())
                }
                
                if include_global:
                    data["global"] = self._global_config.copy()
                    
            abs_path = Path(file_path).resolve()
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(abs_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
                
            logger.info(f"Saved configuration to {abs_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving configuration to {file_path}: {e}")
            return False
    
    def get_device_config(self, device_name: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific device.
        
        Args:
            device_name: Name of the device
            
        Returns:
            Device configuration if found
        """
        with self._config_lock:
            return self._configs.get(device_name, {}).copy()
    
    def get_all_device_configs(self) -> Dict[str, Dict[str, Any]]:
        """Get all device configurations."""
        with self._config_lock:
            return self._configs.copy()
    
    def get_global_config(self) -> Dict[str, Any]:
        """Get global configuration."""
        with self._config_lock:
            return self._global_config.copy()
    
    def update_device_config(self, device_name: str, config: Dict[str, Any]) -> bool:
        """
        Update configuration for a device.
        
        Args:
            device_name: Name of the device
            config: New configuration
            
        Returns:
            True if successful
        """
        if not self._validate_device_config(config):
            return False
            
        with self._config_lock:
            self._configs[device_name] = config
            self._config_sources[device_name] = "api"
            
        self._notify_callbacks("device_config_updated", {
            "device": device_name,
            "config": config
        })
        
        return True
    
    def update_global_config(self, config: Dict[str, Any]) -> bool:
        """
        Update global configuration.
        
        Args:
            config: Configuration updates
            
        Returns:
            True if successful
        """
        with self._config_lock:
            self._global_config.update(config)
            
        self._notify_callbacks("global_config_updated", config)
        return True
    
    def remove_device_config(self, device_name: str) -> bool:
        """
        Remove configuration for a device.
        
        Args:
            device_name: Name of the device
            
        Returns:
            True if successful
        """
        with self._config_lock:
            if device_name in self._configs:
                del self._configs[device_name]
                self._config_sources.pop(device_name, None)
                
                self._notify_callbacks("device_config_removed", {
                    "device": device_name
                })
                
                return True
                
        return False
    
    def register_callback(self, callback: Callable):
        """
        Register a callback for configuration changes.
        
        Args:
            callback: Function to call on configuration changes
        """
        self._callbacks.append(callback)
    
    def _validate_device_config(self, config: Dict[str, Any]) -> bool:
        """Validate device configuration against schema."""
        required = self._schema["device"]["required"]
        
        for field in required:
            if field not in config:
                logger.error(f"Device config missing required field: {field}")
                return False
                
        # Additional validation
        if "casting_method" in config:
            valid_methods = ["dlna", "airplay", "hdmi", "overlay", "chromecast", "miracast"]
            if config["casting_method"] not in valid_methods:
                logger.error(f"Invalid casting method: {config['casting_method']}")
                return False
                
        return True
    
    def _add_device_config(self, config: Dict[str, Any], source: str):
        """Add or update device configuration."""
        device_name = config.get("name") or config.get("device_name")
        if not device_name:
            logger.error("Device configuration missing name")
            return
            
        # Normalize configuration
        normalized = {
            "name": device_name,
            "casting_method": config.get("casting_method", config.get("type", "dlna")),
            "content": config.get("content", {
                "url": config.get("video_file"),
                "type": config.get("mime_type", "video/mp4")
            }),
            "priority": config.get("priority", 50),
            "metadata": config.get("metadata", {})
        }
        
        # Copy additional fields
        for key in [
            "schedule",
            "group",
            "zone",
            "loop",
            "airplay_mode",
            "airplay_url",
            "renderer_projector_id",
            "target_name",
        ]:
            if key in config:
                normalized[key] = config[key]
                
        with self._config_lock:
            self._configs[device_name] = normalized
            self._config_sources[device_name] = source
    
    def _update_global_config(self, config: Dict[str, Any]):
        """Update global configuration."""
        with self._config_lock:
            self._global_config.update(config)
    
    def _setup_file_watcher(self, file_path: str):
        """Set up file watcher for configuration hot-reload."""
        if file_path in self._file_watchers:
            return
            
        class ConfigFileHandler(FileSystemEventHandler):
            def __init__(self, manager, path):
                self.manager = manager
                self.path = path
                
            def on_modified(self, event):
                if isinstance(event, FileModifiedEvent) and event.src_path == self.path:
                    logger.info(f"Configuration file modified: {self.path}")
                    # Reload configuration
                    asyncio.create_task(self.manager._reload_file(self.path))
                    
        handler = ConfigFileHandler(self, file_path)
        observer = Observer()
        observer.schedule(handler, os.path.dirname(file_path), recursive=False)
        observer.start()
        
        self._file_watchers[file_path] = observer
        logger.info(f"Watching configuration file: {file_path}")
    
    async def _reload_file(self, file_path: str):
        """Reload configuration from file."""
        # Small delay to ensure file write is complete
        await asyncio.sleep(0.5)
        
        logger.info(f"Reloading configuration from {file_path}")
        self.load_from_file(file_path, watch=False)
        
        self._notify_callbacks("config_reloaded", {"source": file_path})
    
    def _notify_callbacks(self, event_type: str, data: Any):
        """Notify all callbacks of a configuration event."""
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(event_type, data))
                else:
                    callback(event_type, data)
            except Exception as e:
                logger.error(f"Error in configuration callback: {e}")
    
    def stop_watchers(self):
        """Stop all file watchers."""
        for observer in self._file_watchers.values():
            observer.stop()
            observer.join()
            
        self._file_watchers.clear()
        logger.info("Stopped all configuration file watchers")
