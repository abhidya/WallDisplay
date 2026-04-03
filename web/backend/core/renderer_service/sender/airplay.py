"""
AirPlay implementation of the Sender interface for screen mirroring.
"""

import os
import subprocess
import logging
from typing import Dict, Optional

from .base import Sender


class AirPlaySender(Sender):
    """AirPlay implementation of the sender interface for screen mirroring."""
    
    def __init__(self, config: Dict, logger: Optional[logging.Logger] = None):
        """Initialize the AirPlay sender.
        
        Args:
            config: Configuration dictionary with AirPlay-specific parameters:
                - script_path: Path to the AppleScript file (or "auto" to use default)
                - connect_timeout: Timeout in seconds for connection attempts
            logger: Optional logger for sender logging
        """
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        
        # Set script path from config or use default
        if config.get("script_path", "auto") == "auto":
            self.applescript_path = os.path.join(
                os.path.dirname(__file__), 
                "scripts", 
                "airplay_mirror.scpt"
            )
        else:
            self.applescript_path = config["script_path"]
            
        # Ensure script exists
        if not os.path.exists(self.applescript_path):
            self.logger.warning(f"AppleScript not found at: {self.applescript_path}")
            # Create scripts directory if it doesn't exist
            scripts_dir = os.path.join(os.path.dirname(__file__), "scripts")
            if not os.path.exists(scripts_dir):
                os.makedirs(scripts_dir)
            
        # Instance variables
        self.target_name = None
        self.process = None
        self.connected = False
        self.connect_timeout = config.get("connect_timeout", 10)
        self.display_mode = config.get("display_mode", "mirror")
    
    def connect(self, target_id: str, display_mode: Optional[str] = None) -> bool:
        """Connect to the AirPlay device by name.
        
        Args:
            target_id: Name of the AirPlay device to connect to
            
        Returns:
            bool: True if connection was successful, False otherwise
        """
        self.target_name = target_id
        self.logger.info(f"Connecting to AirPlay device: {target_id}")
        requested_mode = str(display_mode or self.display_mode or "mirror").strip().lower()
        
        try:
            # Execute the AppleScript to start mirroring
            cmd = [
                "osascript", 
                self.applescript_path, 
                "start",
                target_id,
                requested_mode,
            ]

            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.connect_timeout,
            )

            if result.returncode == 0:
                self.connected = True
                self.process = None
                self.logger.info(f"Successfully connected to AirPlay device: {target_id}")
                return True

            stderr = result.stderr.decode('utf-8')
            self.logger.error(f"AirPlay connection failed: {stderr}")
            return False
                
        except Exception as e:
            self.logger.error(f"Error connecting to AirPlay: {str(e)}")
            return False
    
    def disconnect(self) -> bool:
        """Stop AirPlay mirroring.
        
        Returns:
            bool: True if disconnection was successful, False otherwise
        """
        if not self.connected:
            return True
            
        try:
            # Execute the AppleScript to stop mirroring
            cmd = [
                "osascript", 
                self.applescript_path, 
                "stop"
            ]
            
            result = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            
            if result.returncode == 0:
                self.connected = False
                self.logger.info(f"Successfully disconnected from AirPlay device: {self.target_name}")
                
                # Kill the process if still running
                if self.process and self.process.poll() is None:
                    self.process.terminate()
                    self.process = None
                return True
            else:
                stderr = result.stderr.decode('utf-8')
                self.logger.error(f"AirPlay disconnection failed: {stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error disconnecting AirPlay: {str(e)}")
            return False
    
    def send_content(self, content_url: str) -> bool:
        """
        AirPlay mirroring doesn't need explicit content URLs,
        as it mirrors the entire screen. This is a no-op.
        
        Args:
            content_url: Not used for AirPlay mirroring
            
        Returns:
            bool: True if connected, False otherwise
        """
        if not self.connected:
            self.logger.warning("Cannot send content - not connected to AirPlay device")
            return False
        return True
    
    def is_connected(self) -> bool:
        """Check if still connected to AirPlay device.
        
        Returns:
            bool: True if connected, False otherwise
        """
        if not self.process:
            return self.connected

        if self.process.poll() is None:
            return True

        if self.connected:
            self.logger.info(f"AirPlay connection to {self.target_name} was lost")
            self.connected = False

        return False
    
    def get_status(self) -> Dict:
        """Get current status information.
        
        Returns:
            Dict: Status information dictionary
        """
        status = {
            "type": "airplay",
            "connected": self.is_connected(),
            "target": self.target_name
        }
        
        # Add additional status if available
        if self.process and self.process.poll() is None:
            status["process_running"] = True
        else:
            status["process_running"] = False
            
        return status
