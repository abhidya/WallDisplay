#!/usr/bin/env python3
# encoding: UTF-8

import unittest
import numpy as np

# Import the module to test
from web.backend.core.depth_processing.core.segmentation import DepthSegmenter

class TestDepthSegmenter(unittest.TestCase):
    """Tests for the DepthSegmenter class"""
    
    def setUp(self):
        """Set up for tests"""
        # Create a test depth map with clear segments
        self.depth_map = np.zeros((100, 100), dtype=np.float32)
        self.depth_map[0:33, :] = 0.2  # First horizontal band
        self.depth_map[33:66, :] = 0.5  # Second horizontal band
        self.depth_map[66:100, :] = 0.8  # Third horizontal band
    
    def test_kmeans_segmentation(self):
        """Test KMeans segmentation"""
        # Segment with 3 clusters
        segmentation, centers = DepthSegmenter.kmeans_segmentation(
            self.depth_map, n_clusters=3, iterations=10
        )
        
        # Check that the segmentation has the right shape
        self.assertEqual(segmentation.shape, (100, 100))
        
        # Check that we have 3 unique segments
        unique_segments = np.unique(segmentation)
        self.assertEqual(len(unique_segments), 3)
        
        # Check that centers are returned
        self.assertEqual(len(centers), 3)
        
        # Check that the segments roughly align with the bands
        # (exact values depend on the KMeans implementation)
        self.assertEqual(segmentation[16, 50], segmentation[16, 60])  # Same segment in first band
        self.assertEqual(segmentation[50, 50], segmentation[50, 60])  # Same segment in second band
        self.assertEqual(segmentation[80, 50], segmentation[80, 60])  # Same segment in third band
        
        # Different bands should have different segment IDs
        self.assertNotEqual(segmentation[16, 50], segmentation[50, 50])
        self.assertNotEqual(segmentation[50, 50], segmentation[80, 50])
    
    def test_threshold_segmentation(self):
        """Test threshold segmentation"""
        # Segment with two thresholds
        thresholds = [0.3, 0.6]
        segmentation = DepthSegmenter.threshold_segmentation(
            self.depth_map, thresholds=thresholds
        )
        
        # Check that the segmentation has the right shape
        self.assertEqual(segmentation.shape, (100, 100))
        
        # Check that we have 3 unique segments (0, 1, 2)
        unique_segments = np.unique(segmentation)
        self.assertEqual(len(unique_segments), 3)
        
        # Check that the segments align with the thresholds
        # Values < 0.3 should be segment 0
        self.assertEqual(segmentation[16, 50], 0)
        
        # Values >= 0.3 and < 0.6 should be segment 1
        self.assertEqual(segmentation[50, 50], 1)
        
        # Values >= 0.6 should be segment 2
        self.assertEqual(segmentation[80, 50], 2)
    
    def test_depth_band_segmentation(self):
        """Test depth band segmentation"""
        # Segment into 3 bands
        segmentation = DepthSegmenter.depth_band_segmentation(
            self.depth_map, n_bands=3
        )
        
        # Check that the segmentation has the right shape
        self.assertEqual(segmentation.shape, (100, 100))
        
        # Check that we have 3 unique segments
        unique_segments = np.unique(segmentation)
        self.assertEqual(len(unique_segments), 3)
        
        # Since the depth map is designed with clear bands,
        # the segments should align with these bands
        # Band 1: 0.0-0.33
        self.assertEqual(segmentation[16, 50], 0)
        
        # Band 2: 0.33-0.67
        self.assertEqual(segmentation[50, 50], 1)
        
        # Band 3: 0.67-1.0
        self.assertEqual(segmentation[80, 50], 2)
    
    def test_extract_binary_mask(self):
        """Test extracting a binary mask"""
        # Create a simple segmentation mask
        segmentation = np.zeros((100, 100), dtype=np.int32)
        segmentation[25:75, 25:75] = 1  # Center square is segment 1
        
        # Extract a binary mask for segment 1
        binary_mask = DepthSegmenter.extract_binary_mask(segmentation, 1)
        
        # Check that the mask has the right shape
        self.assertEqual(binary_mask.shape, (100, 100))
        
        # Check that it contains only 0 and 255
        self.assertEqual(set(np.unique(binary_mask)), {0, 255})
        
        # Check that the center square is 255
        self.assertEqual(binary_mask[50, 50], 255)
        
        # Check that the corner is 0
        self.assertEqual(binary_mask[0, 0], 0)
    
    def test_clean_binary_mask(self):
        """Test cleaning a binary mask"""
        try:
            # This test requires OpenCV - skip if not available
            import cv2
            
            # Create a binary mask with noise
            binary_mask = np.zeros((100, 100), dtype=np.uint8)
            binary_mask[25:75, 25:75] = 255  # Center square
            binary_mask[10:15, 10:15] = 255  # Small square (noise)
            
            # Clean the mask with a min area larger than the small square
            cleaned_mask = DepthSegmenter.clean_binary_mask(
                binary_mask, min_area=50, kernel_size=3
            )
            
            # Check that the mask has the right shape
            self.assertEqual(cleaned_mask.shape, (100, 100))
            
            # Check that it contains only 0 and 255
            self.assertEqual(set(np.unique(cleaned_mask)), {0, 255})
            
            # Check that the center square is still 255
            self.assertEqual(cleaned_mask[50, 50], 255)
            
            # Check that the small square has been removed
            self.assertEqual(cleaned_mask[12, 12], 0)
            
        except ImportError:
            # Skip test if OpenCV is not available
            print("Skipping clean_binary_mask test - OpenCV not available")
    
    def test_empty_input(self):
        """Test handling of empty input"""
        # Test with None input
        result, centers = DepthSegmenter.kmeans_segmentation(None)
        self.assertIsNone(result)
        self.assertEqual(centers, [])
        
        # Test with empty array
        result = DepthSegmenter.threshold_segmentation(np.array([]), [0.5])
        self.assertIsNone(result)

if __name__ == "__main__":
    unittest.main() 