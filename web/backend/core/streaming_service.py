import os
import socket
import threading
import logging
import re
import unicodedata
import tempfile
import errno
import time
from typing import Dict, List, Optional, Any, Tuple
from http.server import SimpleHTTPRequestHandler, HTTPServer
from functools import partial
from urllib.parse import parse_qs, urlparse

from .streaming_registry import StreamingSessionRegistry

logger = logging.getLogger(__name__)

class StreamingRequestHandler(SimpleHTTPRequestHandler):
    """
    Custom HTTP request handler that tracks streaming activity
    """
    def __init__(self, *args, **kwargs):
        self.streaming_session_id = kwargs.pop('streaming_session_id', None)
        self.registry = StreamingSessionRegistry.get_instance()
        self.file_map = kwargs.pop('file_map', {})
        self.files_served = {}  # Track when files were last served
        self.server_class = kwargs.pop('server_class', None)
        super().__init__(*args, **kwargs)
    
    def handle_one_request(self):
        try:
            # Get client IP before handling request
            client_ip = self.client_address[0]
            
            # Record connection established
            if self.streaming_session_id:
                self.registry.record_connection_event(self.streaming_session_id, True)
                
            return super().handle_one_request()
        except BrokenPipeError:
            logger.info("Broken pipe error - client disconnected")
            if self.streaming_session_id:
                self.registry.record_connection_event(self.streaming_session_id, False)
        except ConnectionResetError:
            logger.info("Connection reset by peer")
            if self.streaming_session_id:
                self.registry.record_connection_event(self.streaming_session_id, False)
        except Exception as e:
            logger.error(f"Error handling HTTP request: {e}")
            if self.streaming_session_id:
                self.registry.record_connection_event(self.streaming_session_id, False)
    
    def do_GET(self):
        """Handle GET requests with proper MIME type setting"""
        # Get clean path
        path = self.path.split('?')[0]
        if path.startswith('/'):
            path = path[1:]
            
        # For DLNA compatibility - if we get a second request for the same file within 5 seconds,
        # always treat it as valid even if the exact path has changed slightly
        # This is critical for DLNA devices which make a second request for format detection
        clean_path = path.lower()
        now = time.time()
        
        logger.debug(f"Received GET request for {path}")

        # First, honor the active stream's explicit file map. This allows
        # streamed files to live outside the backend uploads directory.
        mapped_file = self.file_map.get(path)
        if not mapped_file and path.startswith('uploads/'):
            mapped_file = self.file_map.get(path[len('uploads/'):])
        if mapped_file and os.path.exists(mapped_file) and os.path.isfile(mapped_file):
            logger.debug(f"Serving mapped file for {path}: {mapped_file}")
            self._serve_file_with_mime(mapped_file)
            self.files_served[clean_path] = (now, mapped_file)
            return
        
        # Get the requested filename regardless of path differences
        normalized_path = None
        for served_path, (timestamp, full_path) in list(self.files_served.items()):
            # Find matching file by filename portion (much more flexible matching)
            served_filename = os.path.basename(served_path).lower()
            request_filename = os.path.basename(clean_path).lower()
            
            # Match if:
            # 1. Full paths match or one contains the other
            # 2. Filenames match or one contains the other
            # 3. The request was made within the last 5 seconds (DLNA follow-up window)
            if ((served_path.endswith(clean_path) or clean_path.endswith(served_path) or
                 served_filename == request_filename or 
                 served_filename in request_filename or request_filename in served_filename) and
                 now - timestamp < 5):  # Extend window to 5 seconds for DLNA
                
                # This is likely the same file being requested again
                normalized_path = full_path
                # Refresh timestamp
                self.files_served[served_path] = (now, full_path)
                logger.debug(f"Recognized repeat request for {clean_path} (original: {served_path})")
                break
            elif now - timestamp > 60:
                # Clean up old entries
                del self.files_served[served_path]
        
        # If we found a normalized path, serve that file directly
        if normalized_path:
            # Serve previously served file directly (bypassing filesystem check)
            self._serve_file_with_mime(normalized_path)
            return
            
        # Try to translate the path to a local file
        file_path = self.translate_path(self.path)
        
        # Set specific MIME types that DLNA devices typically support well
        ext = os.path.splitext(file_path)[1].lower()
        
        # If the file exists, serve it with appropriate MIME type
        if os.path.exists(file_path) and os.path.isfile(file_path):
            self._serve_file_with_mime(file_path)
            # Remember we served this file
            self.files_served[clean_path] = (now, file_path)
            return
        
        # If we get here, let's check if the path might be a variant of a previously served file
        # This handles slight URL differences in follow-up requests
        for directory in [d for d in self.files_served if os.path.dirname(d)]:
            base_dir = os.path.dirname(directory)
            test_path = os.path.join(base_dir, path)
            if os.path.exists(test_path) and os.path.isfile(test_path):
                self._serve_file_with_mime(test_path)
                # Remember we served this file
                self.files_served[clean_path] = (now, test_path)
                return
        
        # Log the failed request
        logger.warning(f"File not found: {path}, translated to {file_path}")
        logger.debug(f"Currently tracking these files: {list(self.files_served.keys())}")
        
        # For all other files, use the default behavior
        return SimpleHTTPRequestHandler.do_GET(self)
    
    def _serve_file_with_mime(self, file_path):
        """Serve a file with the appropriate MIME type and DLNA headers"""
        ext = os.path.splitext(file_path)[1].lower()
        
        # Map extensions to MIME types that DLNA devices support well
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
        
        # DLNA profiles for different file types
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
        
        # Get content type based on extension or default to binary
        content_type = mime_types.get(ext, 'application/octet-stream')
        
        try:
            # Get file size
            file_size = os.path.getsize(file_path)
            
            # Send response headers
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(file_size))
            self.send_header('Accept-Ranges', 'bytes')
            
            # Add DLNA-specific headers for better compatibility
            dlna_flags = '01500000000000000000000000000000'  # Standard DLNA flags
            dlna_profile = dlna_profiles.get(ext, 'DLNA.ORG_PN=*')
            
            if dlna_profile:
                self.send_header('contentFeatures.dlna.org', 
                                f'DLNA.ORG_PN={dlna_profile};DLNA.ORG_OP=01;DLNA.ORG_CI=0;DLNA.ORG_FLAGS={dlna_flags}')
                self.send_header('transferMode.dlna.org', 'Streaming')
            
            self.end_headers()
            
            # Stream the file in chunks
            with open(file_path, 'rb') as f:
                self.copyfile(f, self.wfile)
                
            # Log successful transfer
            logger.debug(f"Successfully served file {file_path} with content type {content_type}")
            
        except (IOError, OSError) as e:
            logger.error(f"Error serving file {file_path}: {e}")
            self.send_error(404, "File not found")
    
    def copyfile(self, source, outputfile):
        """
        Copy a file from source to outputfile, handling broken pipe errors and tracking bytes
        """
        try:
            # Copy in chunks to avoid loading the entire file into memory
            chunk_size = 64 * 1024  # 64KB chunks
            bytes_transferred = 0
            
            while True:
                buf = source.read(chunk_size)
                if not buf:
                    break
                try:
                    outputfile.write(buf)
                    bytes_transferred += len(buf)
                    
                    # Update session activity every ~1MB
                    if bytes_transferred >= 1024 * 1024:
                        if self.streaming_session_id:
                            client_ip = self.client_address[0] if hasattr(self, 'client_address') else None
                            self.registry.update_session_activity(
                                self.streaming_session_id,
                                client_ip=client_ip,
                                bytes_transferred=bytes_transferred
                            )
                        bytes_transferred = 0
                        
                except (BrokenPipeError, ConnectionResetError):
                    logger.info("Client disconnected during file transfer")
                    if self.streaming_session_id:
                        self.registry.record_connection_event(self.streaming_session_id, False)
                    break
                except Exception as e:
                    logger.error(f"Error writing to output file: {e}")
                    break
                    
            # Update any remaining bytes
            if bytes_transferred > 0 and self.streaming_session_id:
                client_ip = self.client_address[0] if hasattr(self, 'client_address') else None
                self.registry.update_session_activity(
                    self.streaming_session_id,
                    client_ip=client_ip,
                    bytes_transferred=bytes_transferred
                )
                
        except Exception as e:
            logger.error(f"Error copying file: {e}")
            if self.streaming_session_id:
                self.registry.record_connection_event(self.streaming_session_id, False)

class StreamingService:
    """
    Service for streaming media files over HTTP
    """
    def __init__(self, runtime=None):
        self.servers = {}
        self.temp_dirs = {}
        self.file_to_session_map = {}  # Map file paths to session IDs
        self.registry = StreamingSessionRegistry.get_instance()
        self.runtime = runtime
        
        # Register health check handler
        self.registry.register_health_check_handler(self._handle_stalled_session)

    def _get_runtime_device(self, device_name: str):
        if self.runtime is not None:
            return self.runtime.get_device(device_name)
        try:
            from services.app_runtime import get_app_runtime

            runtime = get_app_runtime()
            if runtime is not None:
                self.runtime = runtime
                return runtime.get_device(device_name)
        except Exception:
            pass
        return None
    
    def normalize_file_name(self, value: str) -> str:
        """
        Normalize a file name for use in URLs
        
        Args:
            value: File name to normalize
            
        Returns:
            str: Normalized file name
        """
        value = unicodedata\
            .normalize("NFKD", value)\
            .encode("ascii", "ignore")\
            .decode("ascii")
        value = re.sub(r"[^\.\w\s-]", "", value.lower())
        value = re.sub(r"[-\s]+", "-", value).strip("-_")
        return value
    
    def get_serve_ip(self, target_ip: Optional[str] = None) -> str:
        """
        Get the IP address to use for serving files
        
        Args:
            target_ip: Target IP address to connect to
            
        Returns:
            str: IP address to use for serving files
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((target_ip or '8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception as e:
            logger.error(f"Error getting serve IP: {e}")
            return '127.0.0.1'
    
    def start_server(
        self,
        files: Dict[str, str],
        serve_ip: str,
        serve_port: Optional[int] = None,
        port_range: Optional[Tuple[int, int]] = None,
        device_name: Optional[str] = None,
        stream_type: str = "device_stream",
        consumer_id: Optional[str] = None,
    ) -> Tuple[Dict[str, str], Any]:
        """
        Start an HTTP server to serve media files
        
        Args:
            files: Dictionary mapping file keys to file paths
            serve_ip: IP address to serve on
            serve_port: Starting port to serve on (optional, will use port_range if provided)
            port_range: Range of ports to try (min_port, max_port) (optional)
            device_name: Name of the device receiving the stream
            
        Returns:
            Tuple[Dict[str, str], Any]: Tuple of (file URLs, server instance)
        """
        # Determine port selection strategy
        if port_range and isinstance(port_range, (list, tuple)) and len(port_range) >= 2:
            min_port, max_port = port_range[0], port_range[1]
            logger.debug(f"Starting streaming server on {serve_ip} with port range {min_port}-{max_port}")
        elif serve_port:
            min_port, max_port = serve_port, serve_port + 100  # Try up to 100 ports from the starting port
            logger.debug(f"Starting streaming server on {serve_ip} starting at port {serve_port}")
        else:
            # Default port range if nothing specified
            min_port, max_port = 9010, 9100
            logger.debug(f"Starting streaming server on {serve_ip} with default port range {min_port}-{max_port}")
        
        # Create a temporary directory for serving files
        temp_dir = tempfile.TemporaryDirectory()
        
        # Create symbolic links to the files in the temporary directory
        normalized_files = {}
        served_files = {}
        for file_key, file_path in files.items():
            # Check if file_key contains path separators (indicating full path preservation is needed)
            if '/' in file_key and not file_key.startswith('file_'):
                # Preserve directory structure for paths like 'uploads/door6.mp4'
                dir_path = os.path.dirname(file_key)
                
                # Create subdirectory in temp dir if needed
                if dir_path:
                    os.makedirs(os.path.join(temp_dir.name, dir_path), exist_ok=True)
                    symlink_path = os.path.join(temp_dir.name, file_key)
                else:
                    symlink_path = os.path.join(temp_dir.name, file_key)
                
                os.symlink(os.path.abspath(file_path), symlink_path)
                normalized_files[file_key] = file_key  # Keep full path
                served_files[file_key] = os.path.abspath(file_path)
                logger.debug(f"Created symlink with path for {file_key}: {file_path} -> {symlink_path}")
            else:
                # Standard behavior for backward compatibility
                # This handles both "video.mp4" and "file_video" style keys
                file_name = self.normalize_file_name(os.path.basename(file_path))
                os.symlink(os.path.abspath(file_path), os.path.join(temp_dir.name, file_name))
                normalized_files[file_key] = file_name
                served_files[file_name] = os.path.abspath(file_path)
                logger.debug(f"Created symlink for {file_key}: {file_path} -> {file_name}")
        
        # Try ports in the specified range
        max_tries = max_port - min_port + 1
        httpd = None
        
        for port in range(min_port, max_port + 1):
            try:
                # Register streaming sessions for each file
                sessions = {}
                for file_key, file_path in files.items():
                    if device_name:
                        session = self.registry.register_session(
                            device_name=device_name,
                            video_path=file_path,
                            server_ip=serve_ip,
                            server_port=port,
                            stream_type=stream_type,
                            consumer_id=consumer_id,
                        )
                        sessions[normalized_files[file_key]] = session.session_id
                
                # Create a custom handler with session information
                def handler_factory(*args, **kwargs):
                    # Try to determine which file is being requested to get session ID
                    path = ""
                    if len(args) > 1:
                        if hasattr(args[1], 'path'):
                            path = args[1].path
                        elif isinstance(args[1], tuple) and len(args[1]) > 0:
                            # If it's a tuple from client_address, use a different approach
                            # In this case, we can't determine the path from args, so use a default
                            logger.debug(f"Using default session ID mapping due to tuple argument")
                            # Use the first session ID if available, better than failing
                            streaming_session_id = next(iter(sessions.values())) if sessions else None
                            return StreamingRequestHandler(*args, streaming_session_id=streaming_session_id, 
                                                         file_map=served_files, **kwargs)
                    
                    if path.startswith('/'):
                        path = path[1:]
                    
                    streaming_session_id = sessions.get(path)
                    logger.debug(f"Created handler for path: {path}, session ID: {streaming_session_id}")
                    return StreamingRequestHandler(*args, streaming_session_id=streaming_session_id, 
                                                 file_map=served_files, **kwargs)
                
                # Create the HTTP server with our handler
                httpd = HTTPServer((serve_ip, port), handler_factory)
                actual_port = port
                
                # Store session mapping
                for file_name, session_id in sessions.items():
                    self.file_to_session_map[f"{serve_ip}:{actual_port}/{file_name}"] = session_id
                
                break
            except OSError as e:
                if e.errno == errno.EADDRINUSE:  # Address already in use
                    logger.debug(f"Port {port} in use, trying next port")
                    continue
                else:
                    # Cancel any registered sessions before raising error
                    for file_key, file_path in files.items():
                        if device_name:
                            file_name = normalized_files[file_key]
                            if file_name in sessions:
                                self.registry.unregister_session(sessions[file_name])
                    raise
        else:
            logger.error(f"Could not find an available port after {max_tries} attempts")
            temp_dir.cleanup()
            raise OSError("No available port found for the HTTP server")
        
        # Store the temporary directory in the server instance to keep it alive
        httpd.temp_dir = temp_dir
        
        # Start the server in a separate thread
        server_thread = threading.Thread(target=httpd.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        logger.info(f"Serving at http://{serve_ip}:{actual_port}/")
        
        # Build URLs for the files
        files_urls = {}
        for file_key, file_path in files.items():
            file_name = normalized_files[file_key]
            url = f"http://{serve_ip}:{actual_port}/{file_name}"
            files_urls[file_key] = url
        
        # Store the server instance
        server_id = f"{serve_ip}:{actual_port}"
        self.servers[server_id] = httpd
        self.temp_dirs[server_id] = temp_dir
        
        return files_urls, httpd
    
    def stop_server(self, server: Any) -> None:
        """
        Stop an HTTP server
        
        Args:
            server: Server instance to stop
        """
        try:
            logger.debug("Stopping streaming server")
            
            # Find and remove the server from our dictionaries
            server_id = None
            for sid, s in list(self.servers.items()):
                if s == server:
                    server_id = sid
                    break
            
            if server_id:
                # Clean up any sessions related to this server
                for url, session_id in list(self.file_to_session_map.items()):
                    if url.startswith(f"http://{server_id}/"):
                        self.registry.unregister_session(session_id)
                        del self.file_to_session_map[url]
                
                # Stop the server
                server.shutdown()
                server.server_close()
                
                # Remove from dictionaries
                del self.servers[server_id]
                if server_id in self.temp_dirs:
                    self.temp_dirs[server_id].cleanup()
                    del self.temp_dirs[server_id]
            else:
                # If we can't find the server ID, just try to shut it down
                server.shutdown()
                server.server_close()
            
            logger.info("Streaming server stopped")
        except Exception as e:
            logger.error(f"Error stopping streaming server: {e}")
    
    def stop_all_servers(self) -> None:
        """
        Stop all HTTP servers
        """
        logger.debug("Stopping all streaming servers")
        
        # Clean up all sessions
        self.file_to_session_map.clear()
        
        for server_id, server in list(self.servers.items()):
            try:
                server.shutdown()
                server.server_close()
                if server_id in self.temp_dirs:
                    self.temp_dirs[server_id].cleanup()
            except Exception as e:
                logger.error(f"Error stopping streaming server {server_id}: {e}")
        
        self.servers.clear()
        self.temp_dirs.clear()
        logger.info("All streaming servers stopped")
        
    def _handle_stalled_session(self, session) -> None:
        """
        Handle a stalled streaming session
        
        Args:
            session: The streaming session that appears stalled
        """
        is_internal_overlay_session = (
            session.stream_type in {"projection_stream", "overlay_mapping_stream"}
            or session.device_name in {"overlay", "overlay-mapping"}
        )

        # Check if we've exceeded reconnection attempts
        if session.has_exceeded_reconnection_limit():
            logger.error(f"Session {session.session_id} has exceeded max reconnection attempts ({session.max_reconnection_attempts})")
            # Unregister the session to prevent infinite retries
            self.registry.unregister_session(session.session_id)
            # Clean up server reference if it exists
            server_key = f"{session.server_ip}:{session.server_port}"
            if server_key in self.servers and not self._has_other_active_sessions(server_key):
                logger.info(f"Cleaning up server {server_key} after session failure")
                server = self.servers[server_key]
                self.stop_server(server)
            return
        
        # Check if we should attempt reconnection (respects cooldown period)
        if not session.should_attempt_reconnection():
            logger.debug(f"Skipping reconnection for session {session.session_id} (cooldown period)")
            return
        
        # Internal overlay sessions are not real renderer devices and should not enter device recovery.
        if is_internal_overlay_session:
            logger.debug(f"Internal overlay session {session.session_id} is stalled, marking for cleanup")
            # Mark session as error state to prevent repeated health checks
            session.status = "error"
            session.active = False
            session.record_reconnection_attempt()
            return

        logger.warning(f"Handling stalled session {session.session_id} for device {session.device_name}")
        
        # Check if this is a false positive before taking action
        device = self._get_runtime_device(session.device_name)
        if device:
            # Get actual device state
            try:
                transport_info = device._get_transport_info() if hasattr(device, '_get_transport_info') else {}
                transport_state = transport_info.get("CurrentTransportState", "UNKNOWN")
                
                if transport_state == "PLAYING":
                    # Device is actually playing - this is a false positive
                    logger.info(f"Device {session.device_name} reports PLAYING state - ignoring stall detection")
                    # Just update activity to reset the stall timer
                    session.update_activity()
                    return
            except Exception as e:
                logger.debug(f"Could not check transport state: {e}")
        
        # Record the reconnection attempt
        session.record_reconnection_attempt()
        
        # Try to recover the streaming connection
        if self._attempt_streaming_reconnection(session):
            logger.info(f"Successfully recovered streaming session {session.session_id}")
        else:
            # If reconnection failed, notify the device manager to take action
            logger.info(f"Reconnection failed for session {session.session_id}, attempting device manager recovery")
            try:
                device = self._get_runtime_device(session.device_name)
                if device:
                    # Let the device handle the streaming health check
                    if hasattr(device, '_handle_streaming_health_check'):
                        device._handle_streaming_health_check(session.session_id, "streaming_stalled")
                    else:
                        logger.warning(f"Device {session.device_name} does not support streaming health checks")
                else:
                    logger.warning(f"Device {session.device_name} not found in runtime device inventory")
            except Exception as e:
                logger.error(f"Error notifying device manager about stalled session: {e}")
                # Mark session as error to prevent repeated attempts
                session.status = "error"
                
    def get_or_create_stream(
        self,
        video_path: str,
        device_name: str = "overlay",
        stream_type: str = "device_stream",
        consumer_id: Optional[str] = None,
    ) -> dict:
        """
        Get an existing stream or create a new one for the given video path
        Implements stream reuse to prevent port exhaustion (9000-9100 range)
        
        Args:
            video_path: Path to the video file
            device_name: Name for the streaming session (default: "overlay")
            
        Returns:
            dict: Dictionary with 'port' and 'url' keys
        """
        # Check for existing streams in file_to_session_map
        basename = os.path.basename(video_path)
        logger.debug(f"Looking for existing stream for {video_path}, basename: {basename}")
        logger.debug(f"Current file_to_session_map: {list(self.file_to_session_map.keys())}")
        
        # Also check for uploads path
        uploads_path = None
        if '/uploads/videos/' in video_path:
            idx = video_path.find('uploads/videos/')
            uploads_path = video_path[idx:]
        
        for map_key, session_id in self.file_to_session_map.items():
            # map_key format: "10.0.0.74:9000/door6.mp4" or "10.0.0.74:9000/uploads/videos/door6.mp4"
            if basename in map_key or (uploads_path and uploads_path in map_key):
                # Extract server info from key
                if '/' in map_key:
                    server_part = map_key.split('/')[0]  # "10.0.0.74:9000"
                    file_part = '/'.join(map_key.split('/')[1:])  # "door6.mp4" or "uploads/door6.mp4"
                    
                    logger.info(f"Reusing existing stream for {video_path} at {server_part}")
                    return {
                        "port": int(server_part.split(':')[1]),
                        "url": f"http://{server_part}/{file_part}"
                    }
        
        # No existing stream, create new one
        logger.info(f"Creating new stream for {video_path}")
        
        # Determine the file key for URL
        # Check if this is a video in the uploads directory
        if '/uploads/videos/' in video_path:
            # Extract the relative path from uploads/
            idx = video_path.find('uploads/videos/')
            file_key = video_path[idx:].replace('\\', '/')
            logger.info(f"Video is in uploads directory, using key: {file_key}")
        elif video_path.startswith('uploads/'):
            file_key = video_path.replace('\\', '/')
            logger.info(f"Video starts with uploads/, using key: {file_key}")
        else:
            file_key = basename
            logger.info(f"Using basename as key: {file_key}")
            
        files = {file_key: video_path}
        serve_ip = self.get_serve_ip()
        
        try:
            files_urls, server = self.start_server(
                files=files,
                serve_ip=serve_ip,
                port_range=(9010, 9100),
                device_name=device_name,
                stream_type=stream_type,
                consumer_id=consumer_id,
            )
            
            actual_port = server.server_address[1]
            
            result = {
                "port": actual_port,
                "url": files_urls.get(file_key, "")
            }
            logger.info(f"Created new stream, returning: {result}")
            return result
        except OSError as e:
            if "No available port" in str(e):
                logger.error(f"Port exhaustion detected: {e}")
                # Try to clean up stale streams
                self._cleanup_stale_streams()
                # Retry once after cleanup
                files_urls, server = self.start_server(
                    files=files,
                    serve_ip=serve_ip,
                    port_range=(9010, 9100),
                    device_name=device_name,
                    stream_type=stream_type,
                    consumer_id=consumer_id,
                )
                actual_port = server.server_address[1]
                return {
                    "port": actual_port,
                    "url": files_urls.get("video", "")
                }
            raise
    
    def set_runtime(self, runtime):
        """Set the runtime reference used for device lookup during recovery."""
        self.runtime = runtime
        logger.info("App runtime reference updated in StreamingService")
    
    def _cleanup_stale_streams(self):
        """Clean up streams that have no active sessions"""
        logger.info("Cleaning up stale streaming servers")
        
        for server_id in list(self.servers.keys()):
            # Check if any sessions are active for this server
            has_active_session = False
            for url, session_id in self.file_to_session_map.items():
                if server_id in url:
                    session = self.registry.get_session(session_id)
                    if session and session.active:
                        has_active_session = True
                        break
            
            if not has_active_session:
                logger.info(f"Removing stale server {server_id}")
                server = self.servers[server_id]
                try:
                    server.shutdown()
                    server.server_close()
                except:
                    pass
                
                del self.servers[server_id]
                if server_id in self.temp_dirs:
                    self.temp_dirs[server_id].cleanup()
                    del self.temp_dirs[server_id]
    
    def _has_other_active_sessions(self, server_key: str) -> bool:
        """
        Check if a server has other active sessions besides the current one
        
        Args:
            server_key: Server identifier (ip:port)
            
        Returns:
            bool: True if there are other active sessions, False otherwise
        """
        active_count = 0
        for url, session_id in self.file_to_session_map.items():
            if server_key in url:
                session = self.registry.get_session(session_id)
                if session and session.active:
                    active_count += 1
                    if active_count > 1:
                        return True
        return False

    def _attempt_streaming_reconnection(self, session) -> bool:
        """
        Attempt to recover a stalled streaming session
        
        Args:
            session: The streaming session to recover
            
        Returns:
            bool: True if reconnection was successful, False otherwise
        """
        logger.info(f"Attempting to reconnect streaming session {session.session_id}")
        
        # First, check if the server for this session is still running
        server_key = f"{session.server_ip}:{session.server_port}"
        if server_key not in self.servers:
            logger.warning(f"Server {server_key} for session {session.session_id} is no longer running")
            return False
            
        # Check if we need to restart the HTTP server
        try:
            # For now, we'll just mark the session as active again
            # In a more advanced implementation, we could restart the HTTP server
            # or implement more sophisticated recovery mechanisms
            session.status = "active"
            session.update_activity()
            logger.info(f"Reset session {session.session_id} status to active")
            
            # Record a reconnection event
            session.record_connection(True)
            
            return True
        except Exception as e:
            logger.error(f"Error during streaming reconnection attempt: {e}")
            return False


# Global singleton instance
_streaming_service_instance = None

def get_streaming_service():
    """Get the global StreamingService instance"""
    global _streaming_service_instance
    if _streaming_service_instance is None:
        _streaming_service_instance = StreamingService()
    return _streaming_service_instance
