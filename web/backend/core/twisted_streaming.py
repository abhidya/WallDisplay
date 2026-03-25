0#!/usr/bin/env python3
# encoding: UTF-8

import os
import socket
import threading
import unicodedata
import re
import tempfile
import time
import logging
from typing import Dict, Any, Optional, Tuple

from twisted.internet import reactor
from twisted.web.resource import Resource
from twisted.web.server import Site
from twisted.web.static import File

# Get logger for this module (uses root logger configuration)
logger = logging.getLogger(__name__)

# Global flag to track if the reactor is running
reactor_running = False
reactor_lock = threading.Lock()

# Global flag to track if there's a thread active
server_thread = None
server_active = False

def normalize_file_name(value):
    """
    Normalize a file name for URLs
    """
    value = unicodedata\
        .normalize("NFKD", value)\
        .encode("ascii", "ignore")\
        .decode("ascii")
    value = re.sub(r"[^\.\w\s-]", "", value.lower())
    value = re.sub(r"[-\s]+", "-", value).strip("-_")
    return value


class DLNAMediaResource(Resource):
    """
    A resource that serves media files with proper DLNA headers
    """
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self.content_type = self._get_content_type()
        self.dlna_profile = self._get_dlna_profile()
        logger.debug(f"Created DLNAMediaResource for {file_path} with content type {self.content_type}")
        
    def _get_content_type(self):
        """Get the content type based on file extension"""
        ext = os.path.splitext(self.file_path)[1].lower()
        mime_types = {
            '.mp4': 'video/mp4',
            '.mkv': 'video/x-matroska',
            '.avi': 'video/x-msvideo',
            '.mov': 'video/quicktime',
            '.mpg': 'video/mpeg',
            '.mpeg': 'video/mpeg',
            '.wmv': 'video/x-ms-wmv',
            '.ts': 'video/MP2T',
            '.srt': 'text/plain'
        }
        return mime_types.get(ext, 'application/octet-stream')
        
    def _get_dlna_profile(self):
        """Get the DLNA profile based on file extension"""
        ext = os.path.splitext(self.file_path)[1].lower()
        dlna_profiles = {
            '.mp4': 'AVC_MP4_BL_CIF15_AAC_520',
            '.avi': 'MPEG_PS_PAL',
            '.mkv': 'MPEG_PS_PAL',
            '.mov': 'MPEG_PS_PAL', 
            '.mpg': 'MPEG_PS_PAL',
            '.mpeg': 'MPEG_PS_PAL',
            '.wmv': 'MPEG_PS_PAL',
            '.ts': 'MPEG_TS_SD_EU_ISO'
        }
        return dlna_profiles.get(ext, '*')
        
    def render(self, request):
        """Serve the file with proper DLNA headers"""
        # Verify file exists
        if not os.path.exists(self.file_path):
            logger.error(f"File not found: {self.file_path}")
            request.setResponseCode(404)
            return b"File not found"
            
        # Log request details
        client_ip = request.getClientAddress().host
        logger.info(f"Received request from {client_ip} for {self.file_path}")
        logger.debug(f"Request URI: {request.uri}, method: {request.method}")
        
        # Update streaming activity in the registry
        try:
            from core.streaming_registry import StreamingSessionRegistry
            registry = StreamingSessionRegistry.get_instance()
            # Find which device this stream belongs to by looking at the port
            port = request.getHost().port
            device_name = None
            
            # Try to determine device from the file path or other context
            # For now, update all active sessions on this port
            sessions = registry.get_active_sessions()
            for session in sessions:
                if session.server_port == port:
                    session.update_activity(client_ip=client_ip)
                    logger.debug(f"Updated streaming activity for session {session.session_id}")
                    device_name = session.device_name
                    
            # Also update the device's activity timer directly
            if device_name:
                try:
                    from services.app_runtime import get_app_runtime
                    device = get_app_runtime().get_device(device_name)
                    if device and hasattr(device, '_last_activity_time') and hasattr(device, '_thread_lock'):
                        import time
                        with device._thread_lock:
                            device._last_activity_time = time.time()
                        logger.debug(f"Updated device {device_name} activity timer")
                except Exception as e:
                    logger.debug(f"Could not update device activity timer: {e}")
        except Exception as e:
            logger.debug(f"Could not update streaming registry: {e}")
        
        # Add DLNA-specific headers
        request.setHeader(b'Content-Type', self.content_type.encode('utf-8'))
        request.setHeader(b'Accept-Ranges', b'bytes')
        
        # DLNA headers for better compatibility
        dlna_flags = '01500000000000000000000000000000'  # Standard DLNA flags
        request.setHeader(
            b'contentFeatures.dlna.org', 
            f'DLNA.ORG_PN={self.dlna_profile};DLNA.ORG_OP=01;DLNA.ORG_CI=0;DLNA.ORG_FLAGS={dlna_flags}'.encode('utf-8')
        )
        request.setHeader(b'transferMode.dlna.org', b'Streaming')
        
        # Log all headers for debugging
        logger.debug(f"Response headers: {request.responseHeaders}")
        
        # Log the request and file being served
        logger.info(f"Serving file: {self.file_path} as {self.content_type}")
        
        # Create a custom File resource with specialized logging
        class LoggingFile(File):
            """File that logs access"""
            def render(self, req):
                logger.debug(f"LoggingFile rendering {self.path}")
                return File.render(self, req)
                
            def openForReading(self):
                logger.debug(f"Opening file for reading: {self.path}")
                try:
                    f = File.openForReading(self)
                    logger.debug(f"Successfully opened file: {self.path}")
                    return f
                except Exception as e:
                    logger.error(f"Error opening file {self.path}: {e}", exc_info=True)
                    raise
            
        # Serve the file
        try:
            file_resource = LoggingFile(self.file_path)
            logger.debug(f"Created file resource for {self.file_path}")
            result = file_resource.render(request)
            logger.debug(f"File resource render result type: {type(result)}")
            return result
        except Exception as e:
            logger.error(f"Error serving file {self.file_path}: {e}", exc_info=True)
            request.setResponseCode(500)
            return f"Error serving file: {str(e)}".encode('utf-8')


class DLNADirectoryResource(Resource):
    """
    A resource that maps file paths to DLNA Media Resources
    """
    def __init__(self):
        super().__init__()
        self.files_dict = {}  # Maps URL paths to absolute file paths
        self.file_names = {}  # Maps filenames to absolute file paths for secondary lookups
        
    def add_file(self, file_path, url_path):
        """Add a file to be served"""
        # Store the absolute path to ensure we can find it
        abs_path = os.path.abspath(file_path)
        self.files_dict[url_path] = abs_path
        
        # Also store by filename for easier lookups on secondary requests
        filename = os.path.basename(url_path)
        self.file_names[filename] = abs_path
        
        logger.debug(f"Added file to DLNA server: {url_path} -> {abs_path}")
        
    def getChild(self, path, request):
        """Get the child resource for a path"""
        path_str = path.decode('utf-8')
        logger.debug(f"DLNA server looking for: {path_str}")
        
        # First check for exact match
        if path_str in self.files_dict:
            logger.debug(f"Exact match found for {path_str}")
            return DLNAMediaResource(self.files_dict[path_str])
            
        # If not found, check for filename match (for DLNA's second request)
        filename = os.path.basename(path_str)
        if filename in self.file_names:
            logger.debug(f"Filename match found for {filename}")
            return DLNAMediaResource(self.file_names[filename])
        
        # Try case-insensitive matching for better compatibility
        lowercase_path = path_str.lower()
        for registered_path, file_path in self.files_dict.items():
            if registered_path.lower() == lowercase_path:
                logger.debug(f"Case-insensitive match found for {path_str}")
                return DLNAMediaResource(file_path)
                
        # Check filename in any part of the request for DLNA compatibility
        for registered_file, file_path in self.file_names.items():
            if registered_file in path_str or path_str in registered_file:
                logger.debug(f"Partial filename match: {registered_file} in {path_str}")
                return DLNAMediaResource(file_path)
        
        # Log the failed lookup
        logger.warning(f"No match found for {path_str} in DLNA server")
        logger.debug(f"Available files: {list(self.files_dict.keys())}")
        logger.debug(f"Available filenames: {list(self.file_names.keys())}")
        
        # Return NoResource for 404
        return Resource.getChild(self, path, request)


class StreamingServer:
    """
    A server that streams media files using Twisted
    """
    def __init__(self, files: Dict[str, str], serve_ip: str, port: int):
        self.files = files
        self.serve_ip = serve_ip
        self.port = port
        self.root = DLNADirectoryResource()
        self.site = None
        self.server = None
        
        # Add files to root resource
        for file_name, file_path in files.items():
            logger.debug(f"Adding file to DLNA server: {file_name} -> {file_path}")
            self.root.add_file(file_path, file_name)
    
    def start(self) -> None:
        """
        Start the streaming server
        """
        try:
            # Create site
            self.site = Site(self.root)
            
            # Start the server
            logger.debug(f"Starting Twisted streaming server on {self.serve_ip}:{self.port}")
            
            from twisted.internet import reactor
            self.server = reactor.listenTCP(self.port, self.site, interface=self.serve_ip)
            
            # Start the reactor if not already running
            global reactor_running
            with reactor_lock:
                if not reactor_running:
                    logger.debug("Starting Twisted reactor")
                    reactor_running = True
                    threading.Thread(target=lambda: reactor.run(installSignalHandlers=False), daemon=True).start()
            
            logger.info(f"Twisted streaming server started at http://{self.serve_ip}:{self.port}/")
        except Exception as e:
            logger.error(f"Error starting streaming server: {e}")
            raise
    
    def stop(self) -> None:
        """
        Stop the streaming server
        """
        try:
            if self.server:
                logger.debug("Stopping streaming server")
                self.server.stopListening()
                self.server = None
                logger.info("Streaming server stopped")
        except Exception as e:
            logger.error(f"Error stopping streaming server: {e}")
            raise


class TwistedStreamingServer:
    """
    Streaming server using Twisted for better DLNA compatibility
    """
    _instance = None
    _servers = {}  # Track all servers by port
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        self.servers = {}
        self.reactor_running = False
        self.server_sites = {}
        self.files_dict = {}
        self.lock = threading.Lock()
        
    def cleanup_old_servers(self, keep_last=5):
        """
        Clean up old servers to prevent port exhaustion
        Keep only the most recent servers
        """
        current_count = len(self.server_sites)
        if current_count > keep_last:
            logger.info(f"Cleaning up old servers. Current count: {current_count}, will keep {keep_last}")
            # Sort by port number (assuming higher ports are newer)
            sorted_ports = sorted(self.server_sites.keys())
            # Stop oldest servers
            ports_to_remove = sorted_ports[:-keep_last]
            for port in ports_to_remove:
                logger.info(f"Stopping old server on port {port}")
                try:
                    site = self.server_sites.pop(port)
                    site.stopListening()
                except Exception as e:
                    logger.error(f"Error stopping old server on port {port}: {e}")
            logger.info(f"Cleanup complete. Remaining servers: {len(self.server_sites)}")
    
    def start_server(self, files: Dict[str, str], serve_ip: Optional[str] = None, 
                    port: Optional[int] = None, port_range: Optional[Tuple[int, int]] = None) -> Tuple[Dict[str, str], Any]:
        """
        Start a streaming server for the given files
        
        Args:
            files: Dictionary mapping file keys to file paths
            serve_ip: IP address to serve on (optional)
            port: Port to serve on (optional)
            port_range: Tuple of (min_port, max_port) to try (optional)
            
        Returns:
            Tuple[Dict[str, str], Any]: Dictionary mapping file keys to URLs and server instance
        """
        import errno
        import socket
        import traceback
        
        # Define port range
        if port_range and isinstance(port_range, (list, tuple)) and len(port_range) >= 2:
            base_port, max_port = port_range[0], port_range[1]
            logger.debug(f"Using specified port range: {base_port}-{max_port}")
        else:
            max_port = 9100
            base_port = port if port else 9000
            logger.debug(f"Using default port range: {base_port}-{max_port}")
        
        # Clean up old servers before trying to create new ones
        self.cleanup_old_servers(keep_last=5)
        
        # Track ports we've already tried to avoid retrying the same port
        tried_ports = set()
        
        # First try the specified port if provided
        if port is not None:
            ports_to_try = [port] + list(range(base_port, max_port + 1))
        else:
            ports_to_try = list(range(base_port, max_port + 1))
        
        for try_port in ports_to_try:
            # Skip if we've already tried this port
            if try_port in tried_ports:
                continue
                
            tried_ports.add(try_port)
            
            try:
                # Stop any existing server
                self.stop_server()
                
                # Get the serve IP if not provided
                if not serve_ip:
                    serve_ip = self.get_serve_ip()
                
                # Test if port is available before creating server
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.settimeout(1)
                
                try:
                    # Try to bind to the port
                    test_socket.bind((serve_ip, try_port))
                    # Port is available, close the test socket
                    test_socket.close()
                except socket.error:
                    # Port is in use, try the next one
                    test_socket.close()
                    logger.warning(f"Port {try_port} is already in use, trying next port...")
                    continue
                
                # Create the server
                server = StreamingServer(files, serve_ip, try_port)
                
                # Start the server
                server.start()
                
                # Store the server instance
                self._current_server = server
                
                # Track this server
                self.server_sites[try_port] = server.server
                
                # Get the URLs for each file
                urls = {}
                for file_key, file_path in files.items():
                    urls[file_key] = f"http://{serve_ip}:{try_port}/{file_key}"
                
                logger.info(f"Started streaming server on {serve_ip}:{try_port}. Total active servers: {len(self.server_sites)}")
                return urls, server
            except Exception as e:
                # Check if it's an address in use error
                if hasattr(e, 'errno') and e.errno == errno.EADDRINUSE:
                    logger.warning(f"Port {try_port} in use, trying next port...")
                    continue
                elif 'Address already in use' in str(e):
                    logger.warning(f"Port {try_port} in use (string match), trying next port...")
                    continue
                else:
                    logger.error(f"Error starting streaming server: {e}\n{traceback.format_exc()}")
                    # Don't raise immediately, try other ports
                    if len(tried_ports) >= len(ports_to_try):
                        # Only raise if we've tried all ports
                        raise
        
        logger.error(f"Could not find an available port between {base_port} and {max_port} for streaming server.")
        raise RuntimeError(f"No available port found for streaming server in range {base_port}-{max_port}")
    
    def stop_server(self, port=None):
        """
        Stop the streaming server
        
        Args:
            port (int, optional): Port to stop server on. If None, stop all servers.
        """
        if port is not None:
            if port in self.server_sites:
                logger.info(f"Stopping streaming server on port {port}")
                site = self.server_sites.pop(port)
                site.stopListening()
        else:
            if self.server_sites:
                logger.info(f"Stopping {len(self.server_sites)} streaming servers")
                for port, site in list(self.server_sites.items()):
                    try:
                        site.stopListening()
                        logger.debug(f"Stopped server on port {port}")
                    except Exception as e:
                        logger.error(f"Error stopping server on port {port}: {e}")
                    self.server_sites.pop(port, None)
            else:
                logger.debug("No streaming servers to stop")
        
        # If no more servers, stop the reactor
        if not self.server_sites and self.reactor_running:
            try:
                from twisted.internet import reactor
                logger.debug("Stopping Twisted reactor")
                reactor.stop()
                self.reactor_running = False
            except Exception as e:
                logger.debug(f"Reactor not running, nothing to stop")
    
    def get_file_path(self, file_name):
        """
        Get the file path for a given file name
        
        Args:
            file_name (str): File name
            
        Returns:
            str: File path
        """
        for name, path in self.files_dict.items():
            if name == file_name:
                return path
        return None

# Global instance
_instance = None

def get_instance():
    """Get the global instance"""
    global _instance
    if _instance is None:
        _instance = TwistedStreamingServer()
    return _instance 

def start_server(files: Dict[str, str], serve_ip: str, serve_port: Optional[int] = None, 
                port_range: Optional[Tuple[int, int]] = None) -> tuple:
    """
    Start a streaming server.
    
    Args:
        files_dict: Dictionary mapping file names to file paths.
        ip: IP address to bind to.
        port: Port to bind to (optional). If not provided, will try ports starting from 9000.
        
    Returns:
        tuple: URL mapping and server object.
    """
    global reactor_running, server_thread, server_active, reactor_lock
    
    logger.info(f"Starting streaming server with files: {files}")
    logger.info(f"Server IP: {serve_ip}, port: {serve_port if serve_port else 'auto-select'}")
    
    # Get singleton instance
    service = get_instance()
    
    # Start server with dynamic port selection if needed
    return service.start_server(files, serve_ip, serve_port, port_range)
