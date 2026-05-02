"""
Renderer Service implementation.

This module provides the main functionality for the Renderer Service,
which manages scene rendering on different display technologies.
"""

import logging
import os
import json
import threading
from typing import Dict, Any, Optional, List, Tuple

from .renderer import Renderer, ChromeRenderer
from ..dlna_device import DLNADevice
from ..twisted_streaming import TwistedStreamingServer
from web.backend.database.database import get_db
from web.backend.services.app_runtime import get_app_runtime


def _resolve_runtime_device(device_name: str):
    runtime = get_app_runtime()
    device = runtime.get_device(device_name)
    if device:
        return device

    db_generator = get_db()
    db = next(db_generator)
    try:
        device_service = runtime.build_device_service(db)
        db_device = device_service.get_device_by_name(device_name)
        if not db_device:
            return None
        return device_service.runtime_sync_service.get_or_register_core_device(db_device)
    finally:
        db_generator.close()


class RendererService:
    """
    Renderer Service for managing scene rendering on different display technologies.
    
    This service provides functionality to start and stop renderers, and to send
    rendered content to display devices.
    """
    
    def __init__(self, config_file: str = None, logger: Optional[logging.Logger] = None):
        """
        Initialize the Renderer Service with configuration.
        
        Args:
            config_file: Path to the configuration file
            logger: Logger instance for logging
        """
        self.logger = logger or logging.getLogger(__name__)
        self.config_file = config_file or os.path.join(os.path.dirname(__file__), '../../config/renderer_config.json')
        self.config = self._load_config()
        self.renderers = {}
        self.active_renderers = {}
        self.lock = threading.Lock()
        self.streaming_server = TwistedStreamingServer()
        self._lan_ip = None
        
    def start_streaming_server(self):
        """Starts the internal TwistedStreamingServer."""
        if not self._lan_ip:
            import socket
            try:
                # Create a socket that connects to an external server
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                self._lan_ip = s.getsockname()[0]
                s.close()
            except Exception as e:
                self.logger.error(f"Error detecting LAN IP: {str(e)}")
                self._lan_ip = '127.0.0.1'
            self.logger.info(f"Auto-detected LAN IP for streaming: {self._lan_ip}")

        if self.streaming_server:
            try:
                # Pass an empty dict for files initially, can be updated later
                self.streaming_server.start_server({}, serve_ip=self._lan_ip)
                self.logger.info(f"Streaming server started on {self._lan_ip} using configured port range.")
            except Exception as e:
                self.logger.error(f"Failed to start streaming server in RendererService: {e}")
                # Potentially re-raise or handle as critical failure
                raise
        
    def _load_config(self) -> Dict[str, Any]:
        """
        Load the configuration from the config file.
        
        Returns:
            Configuration dictionary
        """
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            self.logger.info(f"Loaded configuration from {self.config_file}")
            return config
        except Exception as e:
            self.logger.error(f"Error loading configuration: {str(e)}")
            return {
                'senders': {},
                'renderers': {},
                'scenes': {},
                'projectors': {}
            }
    
    def get_renderer(self, renderer_type: str) -> Optional[Renderer]:
        """
        Get a renderer instance of the specified type.
        
        Args:
            renderer_type: Type of renderer to get
            
        Returns:
            Renderer instance or None if the renderer type is not supported
        """
        with self.lock:
            if renderer_type in self.renderers:
                return self.renderers[renderer_type]
            
            # Check if the renderer type exists in the configuration
            renderer_config = self.config.get('renderers', {}).get(renderer_type)
            if renderer_config:
                # For now, we only support Chrome-based renderers
                if renderer_type.startswith('chrome'):
                    renderer = ChromeRenderer(renderer_config, self.logger)
                    self.renderers[renderer_type] = renderer
                    return renderer
            
            self.logger.error(f"Unsupported renderer type: {renderer_type}")
            return None
    
    def get_scene_config(self, scene_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the configuration for a scene.
        
        Args:
            scene_id: ID of the scene
            
        Returns:
            Scene configuration or None if the scene is not found
        """
        return self.config.get('scenes', {}).get(scene_id)
    
    def get_projector_config(self, projector_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the configuration for a projector.
        
        Args:
            projector_id: ID of the projector
            
        Returns:
            Projector configuration or None if the projector is not found
        """
        return self.config.get('projectors', {}).get(projector_id)
    
    def render_scene(self, scene_id: str, renderer_type: str = 'chrome') -> Optional[str]:
        """
        Render a scene using the specified renderer.
        
        Args:
            scene_id: ID of the scene to render
            renderer_type: Type of renderer to use
            
        Returns:
            URL or path to the rendered content, or None if rendering failed
        """
        scene_config = self.get_scene_config(scene_id)
        if not scene_config:
            self.logger.error(f"Scene not found: {scene_id}")
            return None
        
        renderer = self.get_renderer(renderer_type)
        if not renderer:
            self.logger.error(f"Renderer not found: {renderer_type}")
            return None
        
        try:
            template = scene_config.get('template')
            data = scene_config.get('data', {})
            
            # Render the scene
            rendered_content_url = renderer.render(template, data)
            self.logger.info(f"Rendered scene {scene_id} to {rendered_content_url}")
            
            return rendered_content_url
            
        except Exception as e:
            self.logger.error(f"Error rendering scene {scene_id}: {str(e)}")
            return None
    
    def start_renderer(self, scene_id: str, projector_id: str) -> bool:
        """
        Start a renderer for a scene on a projector.
        
        Args:
            scene_id: ID of the scene to render
            projector_id: ID of the projector to use
            
        Returns:
            True if the renderer was started successfully, False otherwise
        """
        with self.lock:
            # Check if the projector is already in use
            if projector_id in self.active_renderers:
                self.logger.warning(f"Projector {projector_id} is already in use. Stopping the current renderer.")
                self.stop_renderer(projector_id)
            
            # Get the projector configuration
            projector_config = self.get_projector_config(projector_id)
            if not projector_config:
                self.logger.error(f"Projector not found: {projector_id}")
                return False
            
            # Get the scene configuration
            scene_config = self.get_scene_config(scene_id)
            if not scene_config:
                self.logger.error(f"Scene not found: {scene_id}")
                return False
            
            # Get the renderer type from the projector configuration or use the default
            renderer_type = projector_config.get('renderer', 'chrome')
            
            # Render the scene
            rendered_content_url = self.render_scene(scene_id, renderer_type)
            if not rendered_content_url:
                self.logger.error(f"Failed to render scene {scene_id}")
                return False
            
            # Get the renderer
            renderer = self.get_renderer(renderer_type)
            if not renderer:
                self.logger.error(f"Renderer not found: {renderer_type}")
                return False
            
            # Start the renderer
            if not renderer.start():
                self.logger.error(f"Failed to start renderer for scene {scene_id}")
                return False
            
            # Send the rendered content to the projector
            sender_type = projector_config.get('sender')
            target_name = projector_config.get('target_name')
            
            if sender_type == 'dlna':
                # Use the DLNA sender
                success = self._send_to_dlna(target_name, rendered_content_url)
                if not success:
                    self.logger.error(f"Failed to send content to DLNA device {target_name}")
                    renderer.stop()
                    return False
            elif sender_type == 'direct':
                # Direct output is handled by the renderer itself
                pass
            elif sender_type == 'airplay':
                # Use the AirPlay sender
                from .sender.airplay import AirPlaySender # Changed to relative
                
                # Create AirPlay sender
                airplay_config = self.config.get('senders', {}).get('airplay', {})
                airplay_sender = AirPlaySender(airplay_config, self.logger)
                
                # Connect to the target device
                target_name = projector_config.get('target_name')
                if not target_name:
                    self.logger.error(f"No target name specified for AirPlay projector {projector_id}")
                    renderer.stop()
                    return False
                
                # Connect to the AirPlay device
                if not airplay_sender.connect(target_name):
                    self.logger.error(f"Failed to connect to AirPlay device {target_name}")
                    renderer.stop()
                    return False
                
                # Send content to the AirPlay device
                if not airplay_sender.send_content(rendered_content_url):
                    self.logger.error(f"Failed to send content to AirPlay device {target_name}")
                    airplay_sender.disconnect()
                    renderer.stop()
                    return False
                
                # Store the active renderer and sender
                self.active_renderers[projector_id] = {
                    'renderer': renderer,
                    'sender': airplay_sender,
                    'scene_id': scene_id,
                    'projector_id': projector_id,
                    'sender_type': sender_type,
                    'target_name': target_name
                }
                
                self.logger.info(f"Started renderer for scene {scene_id} on AirPlay projector {projector_id}")
                return True
            else:
                self.logger.error(f"Unsupported sender type: {sender_type}")
                renderer.stop()
                return False
            
            # Store the active renderer
            self.active_renderers[projector_id] = {
                'renderer': renderer,
                'scene_id': scene_id,
                'projector_id': projector_id,
                'sender_type': sender_type,
                'target_name': target_name
            }
            
            self.logger.info(f"Started renderer for scene {scene_id} on projector {projector_id}")
            return True
    
    def _send_to_dlna(self, device_name: str, content_url: str) -> bool:
        """
        Send content to a DLNA device.
        
        Args:
            device_name: Name of the DLNA device
            content_url: URL or path to the content
            
        Returns:
            True if the content was sent successfully, False otherwise
        """
        try:
            device = _resolve_runtime_device(device_name)
            
            if not device:
                self.logger.error(f"DLNA device not found: {device_name}")
                return False
            
            # If the content URL is a file:// URL, extract the file path
            if content_url.startswith('file://'):
                content_path = content_url[7:]
            else:
                content_path = content_url
            
            # Play the content on the device
            loop = True  # Always loop the content
            device.play(content_path, loop=loop)
            
            self.logger.info(f"Sent content to DLNA device {device_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending content to DLNA device {device_name}: {str(e)}")
            return False
    
    def stop_renderer(self, projector_id: str) -> bool:
        """
        Stop a renderer on a projector.
        
        Args:
            projector_id: ID of the projector
            
        Returns:
            True if the renderer was stopped successfully, False otherwise
        """
        with self.lock:
            if projector_id not in self.active_renderers:
                self.logger.warning(f"No active renderer found for projector {projector_id}")
                return True
            
            active_renderer = self.active_renderers[projector_id]
            renderer = active_renderer['renderer']
            sender_type = active_renderer['sender_type']
            target_name = active_renderer['target_name']
            
            # Stop the renderer
            if not renderer.stop():
                self.logger.error(f"Failed to stop renderer for projector {projector_id}")
                return False
            
            # Stop the content on the device
            if sender_type == 'dlna':
                try:
                    device = _resolve_runtime_device(target_name)
                    
                    if device:
                        device.stop()
                        self.logger.info(f"Stopped content on DLNA device {target_name}")
                    
                except Exception as e:
                    self.logger.error(f"Error stopping content on DLNA device {target_name}: {str(e)}")
            elif sender_type == 'airplay':
                try:
                    # Get the sender from the active renderer
                    sender = active_renderer.get('sender')
                    if sender:
                        # Disconnect from the AirPlay device
                        if sender.disconnect():
                            self.logger.info(f"Disconnected from AirPlay device {target_name}")
                        else:
                            self.logger.error(f"Failed to disconnect from AirPlay device {target_name}")
                except Exception as e:
                    self.logger.error(f"Error disconnecting from AirPlay device {target_name}: {str(e)}")
            
            # Remove the active renderer
            del self.active_renderers[projector_id]
            
            self.logger.info(f"Stopped renderer for projector {projector_id}")
            return True
    
    def pause_renderer(self, projector_id: str) -> bool:
        """
        Pause a renderer on a projector.
        
        Args:
            projector_id: ID of the projector
            
        Returns:
            True if the renderer was paused successfully, False otherwise
        """
        with self.lock:
            if projector_id not in self.active_renderers:
                self.logger.warning(f"No active renderer found for projector {projector_id}")
                return False
            
            active_renderer = self.active_renderers[projector_id]
            renderer = active_renderer['renderer']
            
            # Pause the renderer
            success = renderer.pause()
            
            if success:
                self.logger.info(f"Paused renderer for projector {projector_id}")
                # Update the status to indicate the renderer is paused
                active_renderer['status'] = 'paused'
            else:
                self.logger.error(f"Failed to pause renderer for projector {projector_id}")
            
            return success
    
    def resume_renderer(self, projector_id: str) -> bool:
        """
        Resume a paused renderer on a projector.
        
        Args:
            projector_id: ID of the projector
            
        Returns:
            True if the renderer was resumed successfully, False otherwise
        """
        with self.lock:
            if projector_id not in self.active_renderers:
                self.logger.warning(f"No active renderer found for projector {projector_id}")
                return False
            
            active_renderer = self.active_renderers[projector_id]
            renderer = active_renderer['renderer']
            
            # Resume the renderer
            success = renderer.resume()
            
            if success:
                self.logger.info(f"Resumed renderer for projector {projector_id}")
                # Update the status to indicate the renderer is running
                active_renderer['status'] = 'running'
            else:
                self.logger.error(f"Failed to resume renderer for projector {projector_id}")
            
            return success
    
    def get_renderer_status(self, projector_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a renderer on a projector.
        
        Args:
            projector_id: ID of the projector
            
        Returns:
            Status dictionary or None if no renderer is active on the projector
        """
        with self.lock:
            if projector_id not in self.active_renderers:
                return None
            
            active_renderer = self.active_renderers[projector_id]
            renderer = active_renderer['renderer']
            
            status = renderer.get_status()
            status.update({
                'scene_id': active_renderer['scene_id'],
                'projector_id': active_renderer['projector_id'],
                'sender_type': active_renderer['sender_type'],
                'target_name': active_renderer['target_name'],
                'status': active_renderer.get('status', 'running' if not renderer.is_paused else 'paused')
            })
            
            return status
    
    def list_active_renderers(self) -> List[Dict[str, Any]]:
        """
        List all active renderers.
        
        Returns:
            List of active renderer status dictionaries
        """
        with self.lock:
            return [self.get_renderer_status(projector_id) for projector_id in self.active_renderers]
    
    def shutdown(self) -> None:
        """
        Shutdown the Renderer Service.
        
        This method stops all active renderers and cleans up resources.
        """
        with self.lock:
            # Stop all active renderers
            for projector_id in list(self.active_renderers.keys()):
                self.stop_renderer(projector_id)
            
            # Stop the streaming server
            if self.streaming_server:
                self.streaming_server.stop_server()
            
            self.logger.info("Renderer Service shutdown complete")
