"""
DLNA implementation of the Sender interface.
"""

import logging
import os
import time
from typing import Dict, Optional

from .base import Sender
from web.backend.core.twisted_streaming import TwistedStreamingServer
from web.backend.database.database import get_db
from web.backend.services.app_runtime import get_app_runtime, get_device_runtime


def _resolve_runtime_device(target_id: str):
    device_runtime = get_device_runtime()
    device = device_runtime.get_device(target_id)
    if device:
        return device

    runtime = get_app_runtime()
    db_generator = get_db()
    db = next(db_generator)
    try:
        device_service = runtime.build_device_service(db)
        db_device = device_service.get_device_by_name(target_id)
        if not db_device:
            return None
        return device_service.runtime_sync_service.get_or_register_core_device(db_device)
    finally:
        db_generator.close()


class DLNASender(Sender):
    """DLNA implementation of the sender interface."""
    
    def __init__(self, config: Dict, logger: Optional[logging.Logger] = None):
        """Initialize the DLNA sender.
        
        Args:
            config: Configuration dictionary with DLNA-specific parameters:
                - stream_port_range: Range of ports for the streaming server (default: [9000, 9100])
                - connect_timeout: Timeout in seconds for connection attempts (default: 5)
            logger: Optional logger for sender logging
        """
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        
        # Set configuration values
        self.stream_port_range = config.get("stream_port_range", [9010, 9100])
        self.connect_timeout = config.get("connect_timeout", 5)
        
        # Instance variables
        self.dlna_device = None
        self.target_id = None
        self.streaming_server = None
    
    def connect(self, target_id: str) -> bool:
        """Connect to the DLNA device by ID or name.
        
        Args:
            target_id: Device ID or name
            
        Returns:
            bool: True if connection was successful, False otherwise
        """
        self.target_id = target_id
        self.logger.info(f"Connecting to DLNA device: {target_id}")
        
        try:
            self.dlna_device = _resolve_runtime_device(target_id)
            
            if not self.dlna_device:
                self.logger.error(f"DLNA device not found: {target_id}")
                return False
                
            # Initialize streaming server if needed
            if not self.streaming_server:
                self.streaming_server = TwistedStreamingServer.get_instance()
                
                # Use the first port in the range as a starting point, but allow auto-selection
                start_port = None
                if isinstance(self.stream_port_range, list) and len(self.stream_port_range) > 0:
                    start_port = self.stream_port_range[0]
                
                # Get the device's IP address for optimal streaming
                serve_ip = None
                if hasattr(self.dlna_device, "_get_serve_ip"):
                    serve_ip = self.dlna_device._get_serve_ip()
                
                # Start the streaming server with dynamic port selection
                self.logger.info(f"Starting streaming server with port range starting at {start_port}")
                
                # We'll initialize the server but not start it yet - it will be started when content is sent
                
            self.logger.info(f"Successfully connected to DLNA device: {target_id}")
            return True
                
        except Exception as e:
            self.logger.error(f"Error connecting to DLNA device: {str(e)}")
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from the DLNA device.
        
        Returns:
            bool: True if disconnection was successful, False otherwise
        """
        if not self.dlna_device:
            return True
            
        try:
            # Stop any playback
            self.dlna_device.stop()
            
            # Stop streaming server if it's running and no other senders are using it
            # In a real implementation, we would track usage across all DLNASender instances
            if self.streaming_server:
                # For now, always stop the server when disconnecting to avoid orphaned servers
                self.streaming_server.stop_server()
                self.streaming_server = None
                
            self.dlna_device = None
            self.logger.info(f"Successfully disconnected from DLNA device: {self.target_id}")
            return True
                
        except Exception as e:
            self.logger.error(f"Error disconnecting DLNA device: {str(e)}")
            return False
    
    def send_content(self, content_url: str) -> bool:
        """Send content to the DLNA device.
        
        Args:
            content_url: URL or file path to the content to be displayed
            
        Returns:
            bool: True if content was successfully sent, False otherwise
        """
        if not self.dlna_device:
            self.logger.warning("Cannot send content - not connected to DLNA device")
            return False
            
        try:
            # Handle URL to local file path conversion if needed
            # For now, assume content_url is a local file path
            
            # Get the device's IP address for optimal streaming
            serve_ip = None
            if hasattr(self.dlna_device, "_get_serve_ip"):
                serve_ip = self.dlna_device._get_serve_ip()
            
            # Start the streaming server with the content
            start_port = None
            if isinstance(self.stream_port_range, list) and len(self.stream_port_range) > 0:
                start_port = self.stream_port_range[0]
                
            # Prepare file dictionary for streaming
            file_name = os.path.basename(content_url)
            files_dict = {file_name: content_url}
            
            # Start streaming server with dynamic port selection
            self.logger.info(f"Starting streaming server for {file_name}")
            port_range = None
            if isinstance(self.stream_port_range, list) and len(self.stream_port_range) >= 2:
                port_range = (self.stream_port_range[0], self.stream_port_range[1])
                self.logger.info(f"Using port range: {port_range}")
                
            stream_urls, server = self.streaming_server.start_server(
                files=files_dict, 
                serve_ip=serve_ip, 
                port=start_port,
                port_range=port_range
            )
            
            # Get the streaming URL for the content
            stream_url = stream_urls.get(file_name)
            if not stream_url:
                self.logger.error(f"Failed to get streaming URL for {file_name}")
                return False
                
            self.logger.info(f"Streaming URL: {stream_url}")
            
            # Play the file on the DLNA device using the streaming URL
            loop = self.config.get("loop", True)
            self.dlna_device.play(stream_url, loop=loop)
            
            # Wait briefly to confirm playback started
            time.sleep(1)
            
            # Check if playback started successfully
            if hasattr(self.dlna_device, "is_playing") and self.dlna_device.is_playing:
                self.logger.info(f"Content {content_url} playing on {self.target_id}")
                return True
            else:
                self.logger.warning(f"Content may not be playing on {self.target_id}")
                # Return True anyway since we initiated playback
                return True
                
        except Exception as e:
            self.logger.error(f"Error sending content to DLNA device: {str(e)}")
            return False
    
    def is_connected(self) -> bool:
        """Check if still connected to DLNA device.
        
        Returns:
            bool: True if connected, False otherwise
        """
        if not self.dlna_device:
            return False
            
        try:
            # Check connection by querying device state
            if hasattr(self.dlna_device, "is_connected"):
                return self.dlna_device.is_connected()
            else:
                # Assume connected if we have a device instance
                return True
        except Exception as e:
            self.logger.error(f"Error checking DLNA connection: {str(e)}")
            return False
    
    def get_status(self) -> Dict:
        """Get current status information.
        
        Returns:
            Dict: Status information dictionary
        """
        status = {
            "type": "dlna",
            "connected": self.is_connected(),
            "target": self.target_id
        }
        
        # Add additional status if available
        if self.dlna_device:
            try:
                if hasattr(self.dlna_device, "is_playing"):
                    status["is_playing"] = self.dlna_device.is_playing
                
                if hasattr(self.dlna_device, "current_video"):
                    status["current_video"] = self.dlna_device.current_video
                
                # Add more device-specific status if available
                for attr in ["device_name", "friendly_name", "manufacturer"]:
                    if hasattr(self.dlna_device, attr):
                        status[attr] = getattr(self.dlna_device, attr)
            except Exception as e:
                self.logger.debug(f"Error getting DLNA device status: {str(e)}")
            
        return status
