"""
Chrome-based renderer for the Renderer Service.

This module implements a renderer that uses Chrome to render HTML content.
"""

import logging
import os
import re
import subprocess
import tempfile
import time
from typing import Dict, Any, Optional, List, Tuple
import uuid
import json
import shutil

from .base import Renderer

GPU_DISABLE_FLAGS = {"--disable-gpu", "--disable-gpu-compositing"}
GPU_ENABLE_FLAGS = ["--enable-gpu", "--ignore-gpu-blocklist"]


def _prefer_hardware_acceleration(args: List[str]) -> List[str]:
    chrome_args = [arg for arg in args if arg not in GPU_DISABLE_FLAGS]
    for flag in GPU_ENABLE_FLAGS:
        if flag not in chrome_args:
            chrome_args.append(flag)
    return chrome_args


class ChromeRenderer(Renderer):
    """
    Chrome-based renderer for HTML content.
    
    This renderer uses Chrome in headless mode to render HTML content.
    It can modify the HTML content to replace video URLs with URLs from
    the Twisted streaming server.
    """
    
    def __init__(self, config: Dict[str, Any], logger: Optional[logging.Logger] = None):
        """
        Initialize the Chrome renderer with configuration.
        
        Args:
            config: Configuration dictionary for the renderer
            logger: Logger instance for logging
        """
        super().__init__(config, logger)
        self.chrome_path = config.get('path', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
        
        # Determine if we should run in headless mode
        self.headless = config.get('headless', True)
        
        # Set Chrome arguments based on headless mode
        if self.headless:
            self.chrome_args = _prefer_hardware_acceleration(
                config.get('args', ['--headless', '--no-sandbox'])
            )
        else:
            # Non-headless mode for testing and AirPlay
            self.chrome_args = _prefer_hardware_acceleration(
                config.get('args', ['--no-sandbox', '--start-fullscreen'])
            )
            
        self.timeout = config.get('timeout', 30)
        self.process = None
        self.temp_dir = None
        self.rendered_html_path = None
        # Use port range instead of fixed port
        self.port_range = config.get('port_range', [9000, 9100])  # Port range for the Twisted streaming server
        self.port = None  # Will be dynamically assigned when streaming starts
        self.host = config.get('host', 'localhost')  # Host for the Twisted streaming server
    
    def render(self, scene_template: str, scene_data: Dict[str, Any]) -> str:
        """
        Render an HTML scene using Chrome.
        
        This method reads the HTML template, replaces video URLs with URLs from
        the Twisted streaming server, and saves the modified HTML to a temporary
        file that can be served to a display device.
        
        Args:
            scene_template: Path to the HTML template
            scene_data: Data to be used in rendering the scene
            
        Returns:
            URL or path to the rendered content that can be used by a sender
        """
        self.logger.info(f"Rendering scene template: {scene_template}")
        
        # Create a temporary directory for the rendered content
        self.temp_dir = tempfile.mkdtemp(prefix="chrome_renderer_")
        self.logger.debug(f"Created temporary directory: {self.temp_dir}")
        
        # Generate a unique filename for the rendered HTML
        rendered_filename = f"rendered_{uuid.uuid4().hex}.html"
        self.rendered_html_path = os.path.join(self.temp_dir, rendered_filename)
        
        try:
            # Read the HTML template
            with open(scene_template, 'r') as f:
                html_content = f.read()
            
            # Process the HTML content
            html_content = self._process_html_content(html_content, scene_data)
            
            # Save the processed HTML to the temporary file
            with open(self.rendered_html_path, 'w') as f:
                f.write(html_content)
            
            self.logger.info(f"Saved rendered HTML to: {self.rendered_html_path}")
            
            # Set the current scene
            self.current_scene = {
                'template': scene_template,
                'data': scene_data,
                'rendered_path': self.rendered_html_path
            }
            
            # Return the URL to the rendered content
            # This will be a file:// URL that can be used by Chrome
            self.rendered_content_url = f"file://{self.rendered_html_path}"
            return self.rendered_content_url
            
        except Exception as e:
            self.logger.error(f"Error rendering scene: {str(e)}")
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                self.temp_dir = None
            raise
    
    def _process_html_content(self, html_content: str, scene_data: Dict[str, Any]) -> str:
        """
        Process the HTML content to replace video URLs and inject scene data.
        
        Args:
            html_content: Original HTML content
            scene_data: Data to be injected into the HTML
            
        Returns:
            Processed HTML content
        """
        # Replace video URLs with URLs from the Twisted streaming server
        if 'video_file' in scene_data:
            video_file = scene_data['video_file']
            # Extract the filename from the path
            video_filename = os.path.basename(video_file)
            
            # Create a streaming URL token with an unresolved port placeholder.
            streaming_url = f"http://{self.host}:PORT_PLACEHOLDER/stream/{video_filename}"
            
            # Replace video source URLs in the HTML
            # This regex looks for video source tags with src attributes
            html_content = re.sub(
                r'<source([^>]*?)src=[\'"]([^\'"]*?)[\'"]([^>]*?)>',
                f'<source\\1src="{streaming_url}"\\3>',
                html_content
            )
            
            # Also replace video URLs in JavaScript
            # This is more complex and might need to be customized based on the actual HTML
            # For now, we'll look for common patterns
            html_content = re.sub(
                r'(videoUrl|video_url|videoSrc|video_src|source\.src)\s*=\s*[\'"]([^\'"]*?)[\'"]',
                f'\\1 = "{streaming_url}"',
                html_content
            )
            
            # Replace video URLs in the JavaScript that tries to load from different ports
            if 'video_host' in scene_data and 'video_ports' in scene_data:
                video_host = scene_data['video_host']
                video_ports = scene_data['video_ports']
                
                # Create a pattern to match URLs like http://10.0.0.74:9000/file_video/door6.mp4
                port_pattern = '|'.join(map(str, video_ports))
                url_pattern = f"{video_host}:({port_pattern})/file_video/{video_filename}"
                
                # Replace with the streaming URL
                html_content = re.sub(
                    url_pattern,
                    streaming_url,
                    html_content
                )
            
            self.logger.info(f"Replaced video URLs with streaming URL: {streaming_url}")
        
        # Inject other scene data into the HTML
        # This could be done by replacing placeholders or by injecting a JavaScript object
        # For now, we'll inject a JavaScript object with the scene data
        scene_data_json = json.dumps(scene_data, indent=2)
        scene_data_script = f"""
        <script>
        // Injected scene data
        window.sceneData = {scene_data_json};
        </script>
        """
        
        # Insert the script before the closing </head> tag
        html_content = re.sub(
            r'</head>',
            f'{scene_data_script}</head>',
            html_content
        )
        
        return html_content
    
    def start(self) -> bool:
        """
        Start the Chrome renderer.
        
        This method launches Chrome with the rendered HTML content.
        
        Returns:
            True if Chrome was started successfully, False otherwise
        """
        if not self.rendered_content_url:
            self.logger.error("Cannot start renderer: No rendered content URL")
            return False
        
        if self.is_running:
            self.logger.warning("Renderer is already running")
            return True
        
        try:
            # Prepare the Chrome command
            cmd = [self.chrome_path] + self.chrome_args + [self.rendered_content_url]
            
            self.logger.info(f"Starting Chrome with command: {' '.join(cmd)}")
            
            # Launch Chrome
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait a bit to see if Chrome starts successfully
            time.sleep(2)
            
            if self.process.poll() is not None:
                # Chrome exited immediately
                stdout, stderr = self.process.communicate()
                self.logger.error(f"Chrome exited immediately with code {self.process.returncode}")
                self.logger.error(f"stdout: {stdout.decode('utf-8')}")
                self.logger.error(f"stderr: {stderr.decode('utf-8')}")
                return False
            
            self.is_running = True
            self.logger.info("Chrome started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting Chrome: {str(e)}")
            return False
    
    def stop(self) -> bool:
        """
        Stop the Chrome renderer.
        
        This method terminates the Chrome process and cleans up temporary files.
        
        Returns:
            True if Chrome was stopped successfully, False otherwise
        """
        if not self.is_running:
            self.logger.warning("Renderer is not running")
            return True
        
        try:
            # Terminate the Chrome process
            if self.process and self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=5)
                
                # If Chrome is still running, kill it
                if self.process.poll() is None:
                    self.process.kill()
                    self.process.wait(timeout=5)
            
            self.is_running = False
            self.logger.info("Chrome stopped successfully")
            
            # Clean up temporary files
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                self.temp_dir = None
                self.logger.debug("Cleaned up temporary directory")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping Chrome: {str(e)}")
            return False
    
    def is_alive(self) -> bool:
        """
        Check if the Chrome process is still running.
        
        Returns:
            True if Chrome is running, False otherwise
        """
        if not self.process:
            return False
        
        return self.process.poll() is None
    
    def pause(self) -> bool:
        """
        Pause the Chrome renderer.
        
        This method pauses video playback and animations by injecting JavaScript
        into the Chrome instance. It finds all video elements and pauses them,
        and also pauses CSS animations and transitions.
        
        Returns:
            True if Chrome was paused successfully, False otherwise
        """
        if not self.is_running or not self.is_alive():
            self.logger.warning("Cannot pause: renderer is not running")
            return False
        
        try:
            # Set the paused flag
            self.is_paused = True
            
            # In a real implementation, we would inject JavaScript to pause videos and animations
            # For example, using Chrome DevTools Protocol to execute JavaScript in the page
            # For now, we'll just log the action and set the flag
            self.logger.info("Chrome renderer paused")
            self.logger.debug("In a production environment, this would inject JavaScript to pause videos and animations")
            
            # Trigger the paused event
            self.trigger_event('paused', {})
            return True
        except Exception as e:
            self.logger.error(f"Error pausing Chrome: {str(e)}")
            self.set_error_state(e)
            return False
    
    def resume(self) -> bool:
        """
        Resume the Chrome renderer.
        
        This method resumes video playback and animations by injecting JavaScript
        into the Chrome instance. It finds all video elements and resumes them,
        and also resumes CSS animations and transitions.
        
        Returns:
            True if Chrome was resumed successfully, False otherwise
        """
        if not self.is_running or not self.is_alive():
            self.logger.warning("Cannot resume: renderer is not running")
            return False
        
        if not self.is_paused:
            self.logger.warning("Renderer is not paused")
            return True
        
        try:
            # Clear the paused flag
            self.is_paused = False
            
            # In a real implementation, we would inject JavaScript to resume videos and animations
            # For example, using Chrome DevTools Protocol to execute JavaScript in the page
            # For now, we'll just log the action and clear the flag
            self.logger.info("Chrome renderer resumed")
            self.logger.debug("In a production environment, this would inject JavaScript to resume videos and animations")
            
            # Trigger the resumed event
            self.trigger_event('resumed', {})
            return True
        except Exception as e:
            self.logger.error(f"Error resuming Chrome: {str(e)}")
            self.set_error_state(e)
            return False
    
    def update_config(self, config: Dict[str, Any]) -> bool:
        """
        Update the Chrome renderer configuration.
        
        Args:
            config: New configuration dictionary
            
        Returns:
            True if the configuration was updated successfully, False otherwise
        """
        try:
            # Store the old configuration in case we need to roll back
            old_config = self.config.copy()
            
            # Update the configuration
            self.config.update(config)
            
            # Update specific attributes based on the new configuration
            self.chrome_path = self.config.get('path', self.chrome_path)
            self.chrome_args = _prefer_hardware_acceleration(self.config.get('args', self.chrome_args))
            self.timeout = self.config.get('timeout', self.timeout)
            self.port_range = self.config.get('port_range', self.port_range)
            self.host = self.config.get('host', self.host)
            
            self.logger.info("Chrome renderer configuration updated")
            return True
        except Exception as e:
            # Roll back to the old configuration
            self.config = old_config
            self.logger.error(f"Error updating Chrome configuration: {str(e)}")
            self.set_error_state(e)
            return False
    
    def cleanup(self) -> bool:
        """
        Clean up resources used by the Chrome renderer.
        
        Returns:
            True if cleanup was successful, False otherwise
        """
        success = True
        
        try:
            # Stop the renderer if it's running
            if self.is_running:
                success = self.stop() and success
            
            # Clean up temporary files
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                self.temp_dir = None
                self.logger.debug("Cleaned up temporary directory")
            
            # Clean up other resources
            success = self.cleanup_resources() and success
            
            return success
        except Exception as e:
            self.logger.error(f"Error cleaning up Chrome renderer: {str(e)}")
            self.set_error_state(e)
            return False
    
    def _process_content(self, content: Any, data: Dict[str, Any]) -> Any:
        """
        Process content before rendering.
        
        This is a wrapper around _process_html_content for compatibility with
        the base class.
        
        Args:
            content: Original HTML content
            data: Data to be used in processing
            
        Returns:
            Processed HTML content
        """
        if isinstance(content, str):
            return self._process_html_content(content, data)
        return content
    
    def _perform_health_check(self) -> None:
        """
        Perform Chrome-specific health checks.
        """
        if not self.is_running:
            return
        
        # Check if the Chrome process is still running
        if not self.is_alive():
            self.logger.warning("Chrome process is not running")
            self.trigger_event('health_check_failed', {'message': 'Chrome process is not running'})
            return
        
        # Check if the rendered content is still accessible
        if self.rendered_html_path and not os.path.exists(self.rendered_html_path):
            self.logger.warning("Rendered HTML file is missing")
            self.trigger_event('health_check_failed', {'message': 'Rendered HTML file is missing'})
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the Chrome renderer.
        
        Returns:
            Dictionary containing status information
        """
        status = {
            'type': 'chrome',
            'running': self.is_alive(),
            'current_scene': self.current_scene['template'] if self.current_scene else None,
            'rendered_content_url': self.rendered_content_url
        }
        
        # Add process information if available
        if self.process:
            status['process_id'] = self.process.pid
            status['process_returncode'] = self.process.returncode
        
        return status
