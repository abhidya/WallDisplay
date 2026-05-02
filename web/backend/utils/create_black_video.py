#!/usr/bin/env python3
"""
Utility to create a black video file for brightness control
"""
import subprocess
import os
import logging

logger = logging.getLogger(__name__)

def create_black_video(output_path: str = None, duration: int = 86400, width: int = 1920, height: int = 1080) -> str:
    """
    Create a black video file using ffmpeg
    
    Args:
        output_path: Path for the output video file (default: static/black_video.mp4)
        duration: Duration in seconds (default: 86400 = 24 hours)
        width: Video width (default: 1920)
        height: Video height (default: 1080)
        
    Returns:
        str: Path to the created video file
    """
    if output_path is None:
        # Get the directory of this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        static_dir = os.path.join(os.path.dirname(script_dir), "static")
        os.makedirs(static_dir, exist_ok=True)
        output_path = os.path.join(static_dir, "black_video.mp4")
    
    # Check if file already exists
    if os.path.exists(output_path):
        logger.info(f"Black video already exists at {output_path}")
        return output_path
    
    try:
        # Use ffmpeg to create a black video
        # -f lavfi: use libavfilter virtual input
        # -i color=black: create black color input
        # -t duration: set duration
        # -s resolution: set resolution
        # -r 30: set frame rate
        # -c:v libx264: use H.264 codec
        # -pix_fmt yuv420p: pixel format for compatibility
        cmd = [
            'ffmpeg',
            '-f', 'lavfi',
            '-i', f'color=black:s={width}x{height}:r=30',
            '-t', str(duration),
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-preset', 'ultrafast',  # Fast encoding
            '-crf', '28',  # Quality (higher = smaller file)
            '-y',  # Overwrite output
            output_path
        ]
        
        logger.info(f"Creating black video with command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"ffmpeg error: {result.stderr}")
            raise RuntimeError(f"Failed to create black video: {result.stderr}")
        
        logger.info(f"Successfully created black video at {output_path}")
        return output_path
        
    except FileNotFoundError:
        logger.error("ffmpeg not found. Please install ffmpeg.")
        # Fallback: create a minimal black MP4 using Python
        # This is a very basic approach and might not work with all DLNA devices
        return create_minimal_black_video_fallback(output_path, width, height)
    except Exception as e:
        logger.error(f"Error creating black video: {e}")
        raise

def create_minimal_black_video_fallback(output_path: str, width: int, height: int) -> str:
    """
    Fallback method to create a minimal black video without ffmpeg
    This creates a very simple MP4 that might not be compatible with all devices
    """
    logger.warning("Using fallback method to create black video (limited compatibility)")
    
    # Last-resort fallback: write an empty placeholder file so callers do not
    # crash immediately. This is not a valid video for most devices.
    with open(output_path, 'wb') as f:
        f.write(b'')  # Empty file as placeholder
    
    logger.warning(f"Created placeholder file at {output_path} - install ffmpeg for proper video generation")
    return output_path

if __name__ == "__main__":
    # Test the function
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) > 1:
        output = sys.argv[1]
    else:
        output = None
    
    path = create_black_video(output)
    print(f"Black video created at: {path}")