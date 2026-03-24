import os
import logging
import shutil
import socket
from typing import List, Optional, Dict, Any, BinaryIO
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, SQLAlchemyError
import subprocess
import json
from fastapi import Depends

from models.video import VideoModel
from schemas.video import VideoCreate, VideoUpdate
from core.twisted_streaming import get_instance as get_twisted_streaming
from database.database import ensure_sqlite_schema_compatibility, get_db

logger = logging.getLogger(__name__)

def get_video_service(db: Session = Depends(get_db)) -> 'VideoService':
    """
    Dependency for getting the VideoService
    
    Args:
        db: Database session
        
    Returns:
        VideoService: Video service instance
    """
    from core.twisted_streaming import get_instance as get_twisted_streaming
    streaming_service = get_twisted_streaming()
    return VideoService(db, streaming_service)

class VideoService:
    """
    Service for managing videos
    """
    def __init__(self, db: Session, streaming_service: Any):
        self.db = db
        self.streaming_service = streaming_service
    
    def get_videos(self, skip: int = 0, limit: int = 100) -> List[VideoModel]:
        """
        Get all videos
        
        Args:
            skip: Number of videos to skip
            limit: Maximum number of videos to return
            
        Returns:
            List[VideoModel]: List of videos
        """
        try:
            return self.db.query(VideoModel).offset(skip).limit(limit).all()
        except OperationalError as exc:
            if "no such column" not in str(exc).lower():
                raise
            logger.warning("Video query hit legacy schema; applying SQLite compatibility upgrade and retrying")
            self.db.rollback()
            ensure_sqlite_schema_compatibility()
            return self.db.query(VideoModel).offset(skip).limit(limit).all()
    
    def get_video_by_id(self, video_id: int) -> Optional[VideoModel]:
        """
        Get a video by ID
        
        Args:
            video_id: ID of the video to get
            
        Returns:
            Optional[VideoModel]: The video if found, None otherwise
        """
        try:
            return self.db.query(VideoModel).filter(VideoModel.id == video_id).first()
        except OperationalError as exc:
            if "no such column" not in str(exc).lower():
                raise
            logger.warning("Video lookup hit legacy schema; applying SQLite compatibility upgrade and retrying")
            self.db.rollback()
            ensure_sqlite_schema_compatibility()
            return self.db.query(VideoModel).filter(VideoModel.id == video_id).first()
    
    def get_video_by_path(self, path: str) -> Optional[VideoModel]:
        """
        Get a video by path
        
        Args:
            path: Path of the video to get
            
        Returns:
            Optional[VideoModel]: The video if found, None otherwise
        """
        try:
            return self.db.query(VideoModel).filter(VideoModel.path == path).first()
        except OperationalError as exc:
            if "no such column" not in str(exc).lower():
                raise
            logger.warning("Video lookup by path hit legacy schema; applying SQLite compatibility upgrade and retrying")
            self.db.rollback()
            ensure_sqlite_schema_compatibility()
            return self.db.query(VideoModel).filter(VideoModel.path == path).first()
    
    def create_video(self, video: VideoCreate) -> VideoModel:
        """
        Create a new video
        
        Args:
            video: Video to create
            
        Returns:
            VideoModel: The created video
        """
        from sqlalchemy.exc import IntegrityError
        
        try:
            # Check if the video file exists
            if not os.path.exists(video.path):
                raise ValueError(f"Video file not found: {video.path}")
            
            # Check for duplicate path
            existing = self.get_video_by_path(video.path)
            if existing:
                raise ValueError("This video has already been added to the library")
            
            # Get video file information
            file_name = video.file_name if video.file_name else os.path.basename(video.path)
            file_size = video.file_size if video.file_size is not None else os.path.getsize(video.path)
            
            # Get video metadata
            _duration, _format_name, _resolution = self._get_video_metadata(video.path)

            duration = video.duration if video.duration is not None else _duration
            format_name = video.format if video.format else _format_name
            resolution = video.resolution if video.resolution else _resolution
            
            # Check for subtitle file
            subtitle_path = self._find_subtitle_file(video.path)
            has_subtitle = subtitle_path is not None
            
            # Create the video in the database
            db_video = VideoModel(
                name=video.name,
                path=video.path,
                file_name=file_name,
                file_size=file_size,
                duration=duration,
                format=format_name,
                resolution=resolution,
                category=video.category,
                source_type=video.source_type,
                source_directory_id=video.source_directory_id,
                has_subtitle=bool(has_subtitle),  # Ensure it's a boolean
                subtitle_path=subtitle_path,
            )
            self.db.add(db_video)
            self.db.commit()
            self.db.refresh(db_video)
            
            return db_video
        except IntegrityError as e:
            self.db.rollback()
            if 'UNIQUE constraint failed' in str(e) or 'duplicate key' in str(e).lower():
                raise ValueError("This video has already been added to the library")
            logger.error(f"Database integrity error: {e}")
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error creating video: {e}")
            raise
    
    def update_video(self, video_id: int, video: VideoUpdate) -> Optional[VideoModel]:
        """
        Update a video
        
        Args:
            video_id: ID of the video to update
            video: Video data to update
            
        Returns:
            Optional[VideoModel]: The updated video if found, None otherwise
        """
        try:
            db_video = self.get_video_by_id(video_id)
            if not db_video:
                return None
            
            # Update the video in the database
            update_data = video.dict(exclude_unset=True)
            
            # If the path is updated, update file information
            if "path" in update_data and update_data["path"] != db_video.path:
                path = update_data["path"]
                
                # Check if the video file exists
                if not os.path.exists(path):
                    raise ValueError(f"Video file not found: {path}")
                
                # Get video file information
                update_data["file_name"] = os.path.basename(path)
                update_data["file_size"] = os.path.getsize(path)
                
                # Get video metadata
                duration, format_name, resolution = self._get_video_metadata(path)
                update_data["duration"] = duration
                update_data["format"] = format_name
                update_data["resolution"] = resolution
                
                # Check for subtitle file
                subtitle_path = self._find_subtitle_file(path)
                update_data["has_subtitle"] = subtitle_path is not None
                update_data["subtitle_path"] = subtitle_path
            
            # Update the video
            for key, value in update_data.items():
                setattr(db_video, key, value)
            
            self.db.commit()
            self.db.refresh(db_video)
            
            return db_video
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error updating video: {e}")
            raise
    
    def delete_video(self, video_id: int) -> bool:
        """
        Delete a video
        
        Args:
            video_id: ID of the video to delete
            
        Returns:
            bool: True if the video was deleted, False otherwise
        """
        try:
            db_video = self.get_video_by_id(video_id)
            if not db_video:
                return False
            
            # Delete the video from the database
            self.db.delete(db_video)
            self.db.commit()
            
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error deleting video: {e}")
            raise
    
    def upload_video(self, file: BinaryIO, filename: str, upload_dir: str, name: Optional[str] = None) -> Optional[VideoModel]:
        """
        Upload a video file
        
        Args:
            file: Video file to upload
            filename: Name of the file
            upload_dir: Directory to upload the file to
            name: Name of the video (defaults to filename without extension)
            
        Returns:
            Optional[VideoModel]: The uploaded video if successful, None otherwise
        """
        try:
            # Make upload_dir absolute if it's relative
            if not os.path.isabs(upload_dir):
                # Get the backend directory as base
                backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                upload_dir = os.path.join(backend_dir, upload_dir)
            
            # Create the upload directory if it doesn't exist
            os.makedirs(upload_dir, exist_ok=True)
            
            # Generate a path for the uploaded file
            file_path = os.path.join(upload_dir, filename)
            
            # Save the file
            with open(file_path, "wb") as f:
                shutil.copyfileobj(file, f)
            
            # Create the video
            video_name = name or os.path.splitext(filename)[0]
            video = VideoCreate(name=video_name, path=file_path)
            
            return self.create_video(video)
        except Exception as e:
            logger.error(f"Error uploading video: {e}")
            return None
    
    def stream_video(self, video_id: int, serve_ip: Optional[str] = None) -> Optional[str]:
        """
        Stream a video
        
        Args:
            video_id: ID of the video to stream
            serve_ip: IP address to serve the video on
            
        Returns:
            Optional[str]: URL of the video stream if successful, None otherwise
        """
        try:
            db_video = self.get_video_by_id(video_id)
            if not db_video:
                logger.error(f"Video with ID {video_id} not found")
                return None
            
            # Check if the video file exists
            if not os.path.exists(db_video.path):
                logger.error(f"Video file not found: {db_video.path}")
                return None
            
            # Get the serve IP
            if not serve_ip:
                try:
                    serve_ip = self.streaming_service.get_serve_ip()
                    logger.info(f"Using auto-detected serve IP: {serve_ip}")
                except Exception as e:
                    logger.error(f"Error getting serve IP: {e}")
                    # Default to localhost if we can't get the serve IP
                    serve_ip = "127.0.0.1"
                    logger.warning(f"Defaulting to serve IP: {serve_ip}")
            else:
                logger.info(f"Using provided serve IP: {serve_ip}")

            # Try to determine a better serve IP based on the device's hostname
            if serve_ip and serve_ip.startswith("10.0.0."):
                # We're on the same network, use our local IP
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.connect((serve_ip, 80))
                    local_ip = s.getsockname()[0]
                    s.close()

                    if local_ip.startswith("10.0.0."):
                        serve_ip = local_ip
                        logger.info(f"Using local network IP: {serve_ip}")
                except Exception as e:
                    logger.error(f"Error determining local IP: {e}")

            # Start the streaming server using the Twisted implementation
            files = {"file_video": db_video.path}
            if db_video.has_subtitle and db_video.subtitle_path:
                files["file_subtitle"] = db_video.subtitle_path

            # Make sure we have absolute paths
            for key, path in files.items():
                files[key] = os.path.abspath(path)
                if not os.path.exists(files[key]):
                    logger.error(f"File not found: {files[key]}")
                    files.pop(key)

            logger.info(f"Starting twisted streaming server for {db_video.path} on {serve_ip}")

            # Explicitly use port 8001 to avoid conflicts
            try:
                files_urls, server = self.streaming_service.start_server(files, serve_ip, serve_port=8001, device_name=db_video.name)

                # Return the video URL
                video_url = files_urls.get("file_video")
                logger.info(f"Streaming URL: {video_url}")
                return video_url
            except Exception as e:
                logger.error(f"Error starting streaming server: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return None
        except Exception as e:
            logger.error(f"Error streaming video: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _get_video_metadata(self, path: str) -> tuple:
        """
        Get video metadata using ffprobe
        
        Args:
            path: Path to the video file
            
        Returns:
            tuple: (duration, format_name, resolution)
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration,format_name:stream=width,height',
                '-of', 'json',
                path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"ffprobe error: {result.stderr}")
                return None, None, None
            
            data = json.loads(result.stdout)
            
            # Extract duration and format
            format_info = data.get('format', {})
            duration = format_info.get('duration')
            if duration:
                duration = float(duration)
            format_name = format_info.get('format_name', '').split(',')[0]
            
            # Extract resolution
            resolution = None
            streams = data.get('streams', [])
            for stream in streams:
                width = stream.get('width')
                height = stream.get('height')
                if width and height:
                    resolution = f"{width}x{height}"
                    break
            
            return duration, format_name, resolution
            
        except Exception as e:
            logger.error(f"Error getting video metadata: {e}")
            return None, None, None
    
    def _find_subtitle_file(self, video_path: str) -> Optional[str]:
        """
        Find subtitle file for a video
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Optional[str]: Path to the subtitle file if found
        """
        try:
            video_dir = os.path.dirname(video_path)
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            
            # Common subtitle extensions
            subtitle_extensions = ['.srt', '.vtt', '.sub', '.ass', '.ssa']
            
            for ext in subtitle_extensions:
                subtitle_path = os.path.join(video_dir, video_name + ext)
                if os.path.exists(subtitle_path):
                    return subtitle_path
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding subtitle file: {e}")
            return None
    
    def scan_directory(self, directory: str, category: str = "background", source_directory_id: Optional[int] = None) -> List[VideoModel]:
        """
        Scan a directory for video files and add them to the database
        
        Args:
            directory: Directory path to scan for videos
            
        Returns:
            List[VideoModel]: List of videos found and added
        """
        if not os.path.exists(directory):
            raise ValueError(f"Directory not found: {directory}")
        
        if not os.path.isdir(directory):
            raise ValueError(f"Path is not a directory: {directory}")
        
        video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.mpg', '.mpeg', '.wmv', '.ts', '.m4v', '.webm'}
        videos_added = []
        
        try:
            # Walk through directory and subdirectories
            for root, dirs, files in os.walk(directory):
                for file in files:
                    # Check if file has video extension
                    file_ext = os.path.splitext(file)[1].lower()
                    if file_ext in video_extensions:
                        file_path = os.path.abspath(os.path.join(root, file))
                        
                        # Check if video already exists in database
                        existing = self.get_video_by_path(file_path)
                        if existing:
                            logger.info(f"Video already exists in database: {file_path}")
                            continue
                        
                        # Create video entry
                        try:
                            video_name = os.path.splitext(file)[0]
                            video = VideoCreate(
                                name=video_name,
                                path=file_path,
                                category=category,
                                source_type="directory_scan",
                                source_directory_id=source_directory_id,
                            )
                            db_video = self.create_video(video)
                            videos_added.append(db_video)
                            logger.info(f"Added video: {file_path}")
                        except Exception as e:
                            logger.error(f"Error adding video {file_path}: {e}")
                            continue
            
            return videos_added
            
        except Exception as e:
            logger.error(f"Error scanning directory {directory}: {e}")
            raise
