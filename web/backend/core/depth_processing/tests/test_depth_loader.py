#!/usr/bin/env python3
# encoding: UTF-8

import unittest
import os
import tempfile
import numpy as np
from PIL import Image

# Import the module to test
from web.backend.core.depth_processing.core.depth_loader import DepthLoader

class TestDepthLoader(unittest.TestCase):
    """Tests for the DepthLoader class"""
    
    def setUp(self):
        """Set up for tests"""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        
        # Create a test grayscale image
        self.test_image_path = os.path.join(self.temp_dir.name, "test_depth.png")
        test_depth = np.ones((100, 100), dtype=np.uint8) * 128  # Middle gray
        test_depth[25:75, 25:75] = 255  # White square in the middle
        test_image = Image.fromarray(test_depth)
        test_image.save(self.test_image_path)
        
        # Create a test RGB image
        self.test_rgb_path = os.path.join(self.temp_dir.name, "test_rgb.png")
        test_rgb = np.zeros((100, 100, 3), dtype=np.uint8)
        test_rgb[25:75, 25:75, 0] = 255  # Red square in the middle
        test_rgb_image = Image.fromarray(test_rgb)
        test_rgb_image.save(self.test_rgb_path)
    
    def tearDown(self):
        """Tear down after tests"""
        # Clean up the temporary directory
        self.temp_dir.cleanup()
    
    def test_load_grayscale_image(self):
        """Test loading a grayscale image"""
        depth_map = DepthLoader.load_depth_map(self.test_image_path)
        
        # Check that the depth map was loaded
        self.assertIsNotNone(depth_map)
        
        # Check the shape
        self.assertEqual(depth_map.shape, (100, 100))
        
        # Check the center square
        self.assertEqual(depth_map[50, 50], 255)
        
        # Check the corner
        self.assertEqual(depth_map[0, 0], 128)
    
    def test_load_rgb_image(self):
        """Test loading an RGB image"""
        depth_map = DepthLoader.load_depth_map(self.test_rgb_path)
        
        # Check that the depth map was loaded
        self.assertIsNotNone(depth_map)
        
        # Check the shape (should be converted to grayscale)
        self.assertEqual(depth_map.shape, (100, 100))
    
    def test_load_nonexistent_file(self):
        """Test loading a nonexistent file"""
        depth_map = DepthLoader.load_depth_map("nonexistent.png")
        
        # Should return None for nonexistent file
        self.assertIsNone(depth_map)
    
    def test_normalize_depth_map(self):
        """Test normalizing a depth map"""
        # Create a depth map with known range
        depth_map = np.zeros((100, 100), dtype=np.float32)
        depth_map[25:75, 25:75] = 100.0  # Set center square to 100
        
        # Normalize the depth map
        normalized = DepthLoader.normalize_depth_map(depth_map)
        
        # Check that the normalized map has correct range
        self.assertAlmostEqual(normalized.min(), 0.0)
        self.assertAlmostEqual(normalized.max(), 1.0)
        
        # Check that the center is 1.0 and corners are 0.0
        self.assertAlmostEqual(normalized[50, 50], 1.0)
        self.assertAlmostEqual(normalized[0, 0], 0.0)
    
    def test_visualize_depth_map(self):
        """Test visualizing a depth map"""
        # Create a normalized depth map
        depth_map = np.zeros((100, 100), dtype=np.float32)
        depth_map[25:75, 25:75] = 1.0  # Set center square to 1.0
        
        # Visualize the depth map
        visualization = DepthLoader.visualize_depth_map(depth_map)
        
        # Check that the visualization is uint8
        self.assertEqual(visualization.dtype, np.uint8)
        
        # Check that the center is 255 and corners are 0
        self.assertEqual(visualization[50, 50], 255)
        self.assertEqual(visualization[0, 0], 0)
    
    def test_normalize_already_normalized(self):
        """Test normalizing an already normalized depth map"""
        # Create a depth map already in [0, 1] range
        depth_map = np.zeros((100, 100), dtype=np.float32)
        depth_map[25:75, 25:75] = 0.5  # Set center square to 0.5
        
        # Normalize the depth map
        normalized = DepthLoader.normalize_depth_map(depth_map)
        
        # Check that the values are unchanged
        self.assertAlmostEqual(normalized[50, 50], 0.5)
        self.assertAlmostEqual(normalized[0, 0], 0.0)
    
    def test_normalize_constant_depth_map(self):
        """Test normalizing a constant depth map"""
        # Create a constant depth map
        depth_map = np.ones((100, 100), dtype=np.float32) * 10.0
        
        # Normalize the depth map
        normalized = DepthLoader.normalize_depth_map(depth_map)
        
        # Should be all zeros for constant input
        self.assertTrue(np.allclose(normalized, 0.0))

if __name__ == "__main__":
    unittest.main() 