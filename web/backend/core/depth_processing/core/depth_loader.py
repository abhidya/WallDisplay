#!/usr/bin/env python3
# encoding: UTF-8

import os
import logging
import numpy as np
from PIL import Image
from typing import Optional, Tuple

# Configure logger for this module
logger = logging.getLogger(__name__)

class DepthLoader:
    """Class for loading depth maps from various file formats"""
    
    @staticmethod
    def load_depth_map(file_path: str) -> Optional[np.ndarray]:
        """
        Load a depth map from a file
        
        Args:
            file_path: Path to the depth map file
            
        Returns:
            Numpy array containing the depth map, or None if loading failed
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return None
            
        try:
            # Get file extension
            ext = os.path.splitext(file_path)[1].lower()
            
            if ext in ['.png', '.jpg', '.jpeg']:
                return DepthLoader._load_image(file_path)
            elif ext == '.tif' or ext == '.tiff':
                return DepthLoader._load_tiff(file_path)
            elif ext == '.exr':
                return DepthLoader._load_exr(file_path)
            else:
                logger.error(f"Unsupported file format: {ext}")
                return None
        except Exception as e:
            logger.error(f"Error loading depth map {file_path}: {e}")
            return None
    
    @staticmethod
    def _load_image(file_path: str) -> np.ndarray:
        """Load a depth map from an image file (PNG, JPG)"""
        with Image.open(file_path) as image:
            if image.mode == 'L':
                depth_map = np.array(image)
            elif image.mode == 'RGB':
                depth_map = np.array(image.convert('L'))
            else:
                depth_map = np.array(image.convert('L'))
        return depth_map
    
    @staticmethod
    def _load_tiff(file_path: str) -> np.ndarray:
        """Load a depth map from a 16-bit TIFF file"""
        try:
            # Try using PIL first
            with Image.open(file_path) as image:
                depth_map = np.array(image)
            
            # Check if it's a 16-bit TIFF
            if depth_map.dtype == np.uint16:
                logger.debug(f"Loaded 16-bit TIFF: {file_path}")
            else:
                logger.debug(f"Loaded TIFF with dtype: {depth_map.dtype}")
            
            return depth_map
        except Exception as e:
            logger.error(f"Error loading TIFF with PIL: {e}")
            
            try:
                # Try using tifffile as fallback
                import tifffile
                depth_map = tifffile.imread(file_path)
                return depth_map
            except ImportError:
                logger.error("tifffile not available for fallback TIFF loading")
                raise
            except Exception as e:
                logger.error(f"Error loading TIFF with tifffile: {e}")
                raise
    
    @staticmethod
    def _load_exr(file_path: str) -> np.ndarray:
        """Load a depth map from an OpenEXR file"""
        try:
            # Try using OpenEXR
            import OpenEXR
            import Imath
            import array
            
            exr_file = OpenEXR.InputFile(file_path)
            header = exr_file.header()
            
            # Get the data window (dimensions)
            dw = header['dataWindow']
            width = dw.max.x - dw.min.x + 1
            height = dw.max.y - dw.min.y + 1
            
            # Get the first channel (assuming it's the depth channel)
            channel_names = header['channels'].keys()
            if not channel_names:
                logger.error(f"No channels found in EXR file: {file_path}")
                return None
                
            # Try to find a depth channel, or use the first channel
            depth_channel = None
            for name in channel_names:
                if 'depth' in name.lower() or 'z' == name.lower():
                    depth_channel = name
                    break
            
            if depth_channel is None:
                depth_channel = list(channel_names)[0]
                logger.warning(f"No explicit depth channel found, using {depth_channel}")
            
            # Get the pixel type
            pixel_type = header['channels'][depth_channel].type
            if pixel_type == Imath.PixelType(Imath.PixelType.FLOAT):
                # Float32 pixel type
                data_str = exr_file.channel(depth_channel, Imath.PixelType(Imath.PixelType.FLOAT))
                data = np.frombuffer(data_str, dtype=np.float32)
            elif pixel_type == Imath.PixelType(Imath.PixelType.HALF):
                # Float16 pixel type
                data_str = exr_file.channel(depth_channel, Imath.PixelType(Imath.PixelType.HALF))
                data = np.frombuffer(data_str, dtype=np.float16)
            else:
                logger.error(f"Unsupported pixel type in EXR: {pixel_type}")
                return None
            
            # Reshape to image dimensions
            depth_map = data.reshape(height, width)
            return depth_map
            
        except ImportError:
            logger.error("OpenEXR not available; install via pip: pip install openexr")
            
            try:
                # Try using OpenCV as fallback
                import cv2
                depth_map = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
                return depth_map
            except ImportError:
                logger.error("OpenCV not available for fallback EXR loading")
                raise
            except Exception as e:
                logger.error(f"Error loading EXR with OpenCV: {e}")
                raise
        except Exception as e:
            logger.error(f"Error loading EXR file: {e}")
            raise

    @staticmethod
    def normalize_depth_map(depth_map: np.ndarray) -> np.ndarray:
        """
        Normalize a depth map to [0, 1] range
        
        Args:
            depth_map: Input depth map
            
        Returns:
            Normalized depth map
        """
        # Handle empty or invalid depth maps
        if depth_map is None or depth_map.size == 0:
            return None
            
        # Get the min and max values, handling non-finite values
        valid_mask = np.isfinite(depth_map)
        if not np.any(valid_mask):
            logger.error("Depth map contains only non-finite values")
            return None
            
        # Get min and max values from valid pixels
        min_val = np.min(depth_map[valid_mask])
        max_val = np.max(depth_map[valid_mask])
        
        # Check if the depth map is already normalized
        if min_val >= 0 and max_val <= 1:
            logger.debug("Depth map already normalized")
            return depth_map
            
        # Normalize depth map to [0, 1]
        if max_val > min_val:
            normalized = (depth_map - min_val) / (max_val - min_val)
            # Replace non-finite values with 0
            normalized[~valid_mask] = 0
            return normalized
        else:
            logger.warning("Depth map has constant value, returning zeros")
            return np.zeros_like(depth_map)
    
    @staticmethod
    def visualize_depth_map(depth_map: np.ndarray) -> np.ndarray:
        """
        Convert a depth map to a visualization (grayscale or color)
        
        Args:
            depth_map: Input depth map
            
        Returns:
            Visualization as uint8 array
        """
        if depth_map is None:
            return None
            
        # Normalize if not already in [0, 1]
        if depth_map.min() < 0 or depth_map.max() > 1:
            normalized = DepthLoader.normalize_depth_map(depth_map)
        else:
            normalized = depth_map
            
        # Convert to uint8 [0, 255]
        visualization = (normalized * 255).astype(np.uint8)
        return visualization 
