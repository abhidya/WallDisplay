"""
Tests for the DeviceManager class, verifying thread-safe device management and configuration integration.
"""

import unittest
import os
import json
import tempfile
import threading
import time
from unittest.mock import patch, MagicMock, Mock

# Import the required classes for testing
import sys
sys.path.append('web/backend')
from core.device_manager import DeviceManager
from core.config_service import ConfigService


class TestDeviceManager(unittest.TestCase):
    """
    Tests for the DeviceManager class
    """
    
    def setUp(self):
        """
        Set up test fixtures
        """
        # Reset the ConfigService singleton for each test
        ConfigService._instance = None
        
        # Create a device manager for testing
        self.device_manager = DeviceManager()
        
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        
        # Create a test config file
        self.test_config = [
            {
                "device_name": "TestDevice1",
                "type": "dlna",
                "hostname": "192.168.1.100",
                "friendly_name": "Test Device 1",
                "action_url": "http://192.168.1.100:49152/AVTransport/Control",
                "video_file": "/tmp/test_video1.mp4"
            },
            {
                "device_name": "TestDevice2",
                "type": "dlna",
                "hostname": "192.168.1.101",
                "friendly_name": "Test Device 2",
                "action_url": "http://192.168.1.101:49152/AVTransport/Control",
                "video_file": "/tmp/test_video2.mp4"
            }
        ]
        
        self.config_file_path = os.path.join(self.temp_dir.name, "test_config.json")
        with open(self.config_file_path, "w") as f:
            json.dump(self.test_config, f)
        
        # Create test video files (empty files for path existence checks)
        for device in self.test_config:
            with open(device["video_file"], "w") as f:
                f.write("")
    
    def tearDown(self):
        """
        Clean up test fixtures
        """
        # Stop discovery if running
        self.device_manager.stop_discovery()
        
        # Remove temp files
        for device in self.test_config:
            if os.path.exists(device["video_file"]):
                os.remove(device["video_file"])
        
        # Remove temp directory
        self.temp_dir.cleanup()
    
    @patch('core.dlna_device.DLNADevice.play')
    def test_register_device(self, mock_play):
        """Test registering a device"""
        # Set up mock
        mock_play.return_value = True
        
        # Register a device
        device_info = self.test_config[0].copy()
        device = self.device_manager.register_device(device_info)
        
        # Verify the device was registered
        self.assertIsNotNone(device)
        self.assertEqual(device.name, "TestDevice1")
        
        # Verify the device is in the device manager
        registered_devices = self.device_manager.get_devices()
        self.assertEqual(len(registered_devices), 1)
        self.assertEqual(registered_devices[0].name, "TestDevice1")
        
        # Verify the get_device method
        retrieved_device = self.device_manager.get_device("TestDevice1")
        self.assertIsNotNone(retrieved_device)
        self.assertEqual(retrieved_device.name, "TestDevice1")
    
    @patch('core.dlna_device.DLNADevice.play')
    def test_register_duplicate_device(self, mock_play):
        """Test registering a device that already exists"""
        # Set up mock
        mock_play.return_value = True
        
        # Register a device
        device_info1 = self.test_config[0].copy()
        device1 = self.device_manager.register_device(device_info1)
        
        # Register the same device again (with exact same parameters)
        device_info2 = self.test_config[0].copy()
        device2 = self.device_manager.register_device(device_info2)
        
        # Verify we got back the same device instance
        self.assertIs(device1, device2)
        
        # Verify only one device in the device manager
        registered_devices = self.device_manager.get_devices()
        self.assertEqual(len(registered_devices), 1)
        
        # Register the device with different parameters
        device_info3 = self.test_config[0].copy()
        device_info3["hostname"] = "192.168.1.200"  # Change hostname
        device3 = self.device_manager.register_device(device_info3)
        
        # Verify we got a new device instance
        self.assertIsNot(device1, device3)
        
        # Verify still only one device in the device manager (replaced)
        registered_devices = self.device_manager.get_devices()
        self.assertEqual(len(registered_devices), 1)
        self.assertEqual(registered_devices[0].device_info["hostname"], "192.168.1.200")
    
    @patch('core.dlna_device.DLNADevice.play')
    def test_unregister_device(self, mock_play):
        """Test unregistering a device"""
        # Set up mock
        mock_play.return_value = True
        
        # Register a device
        device_info = self.test_config[0].copy()
        device = self.device_manager.register_device(device_info)
        
        # Verify the device was registered
        self.assertIsNotNone(device)
        
        # Unregister the device
        result = self.device_manager.unregister_device("TestDevice1")
        self.assertTrue(result)
        
        # Verify the device is no longer in the device manager
        registered_devices = self.device_manager.get_devices()
        self.assertEqual(len(registered_devices), 0)
        
        # Verify get_device returns None
        retrieved_device = self.device_manager.get_device("TestDevice1")
        self.assertIsNone(retrieved_device)
    
    @patch('core.dlna_device.DLNADevice.play')
    def test_load_devices_from_config(self, mock_play):
        """Test loading devices from a configuration file"""
        # Set up mock
        mock_play.return_value = True
        
        # Register the devices manually first (simulating discovery)
        for device_info in self.test_config:
            self.device_manager.register_device(device_info.copy())
        
        # Load devices from the config file
        loaded_devices = self.device_manager.load_devices_from_config(self.config_file_path)
        
        # Verify the devices were loaded
        self.assertEqual(len(loaded_devices), 2)
        
        # Verify the configs were loaded into ConfigService
        config_service = ConfigService.get_instance()
        configs = config_service.get_all_device_configs()
        self.assertEqual(len(configs), 2)
        self.assertIn("TestDevice1", configs)
        self.assertIn("TestDevice2", configs)
        
        # Verify configuration data
        self.assertEqual(configs["TestDevice1"]["hostname"], "192.168.1.100")
        self.assertEqual(configs["TestDevice2"]["hostname"], "192.168.1.101")
    
    @patch('core.dlna_device.DLNADevice.play')
    @patch('os.path.exists')
    @patch('core.device_manager.DeviceManager.get_serve_ip')
    def test_auto_play_video(self, mock_get_serve_ip, mock_exists, mock_play):
        """Test auto-playing a video on a device"""
        # Set up mocks
        mock_play.return_value = True
        mock_exists.return_value = True
        mock_get_serve_ip.return_value = "192.168.1.10"
        
        # Mock the streaming server
        with patch('core.twisted_streaming.TwistedStreamingServer') as mock_streaming:
            mock_server_instance = Mock()
            mock_streaming.get_instance.return_value = mock_server_instance
            # Mock URL that would be generated by streaming server
            video_path = "/tmp/test_video1.mp4"
            streaming_url = f"http://192.168.1.10:9000/test_video1.mp4"
            mock_server_instance.start_server.return_value = (
                {"test_video1.mp4": streaming_url}, 
                Mock()
            )
            
            # Register a device
            device_info = self.test_config[0].copy()
            device = self.device_manager.register_device(device_info)
            
            # Auto-play a video
            result = self.device_manager.auto_play_video(device, video_path)
            
            # Verify the play method was called with streaming URL
            self.assertTrue(result)
            mock_play.assert_called_once_with(streaming_url, True)
    
    @patch('core.dlna_device.DLNADevice.play')
    @patch('core.dlna_device.DLNADevice.stop')
    @patch('os.path.exists')
    @patch('core.device_manager.DeviceManager.get_serve_ip')
    def test_auto_play_different_video(self, mock_get_serve_ip, mock_exists, mock_stop, mock_play):
        """Test auto-playing a different video on a device that's already playing"""
        # Set up mocks
        mock_play.return_value = True
        mock_exists.return_value = True
        mock_get_serve_ip.return_value = "192.168.1.10"
        
        # Mock the streaming server
        with patch('core.twisted_streaming.TwistedStreamingServer') as mock_streaming:
            mock_server_instance = Mock()
            mock_streaming.get_instance.return_value = mock_server_instance
            # Mock URL for second video
            video2_path = "/tmp/test_video2.mp4"
            streaming_url = f"http://192.168.1.10:9000/test_video2.mp4"
            mock_server_instance.start_server.return_value = (
                {"test_video2.mp4": streaming_url}, 
                Mock()
            )
            
            device_info = self.test_config[0].copy()
            device = self.device_manager.register_device(device_info)
            
            # Simulate device already playing a video
            device.is_playing = True
            video1_path = "/tmp/test_video1.mp4"
            with self.device_manager.device_state_lock:
                self.device_manager.assigned_videos["TestDevice1"] = video1_path
            
            # Auto-play a different video
            result = self.device_manager.auto_play_video(device, video2_path)
            
            # Verify the stop method was called first
            mock_stop.assert_called_once()
            
            # Verify the play method was called with the streaming URL
            mock_play.assert_called_once_with(streaming_url, True)
    
    def test_discovery_loop_delegates_to_discovery_coordinator(self):
        """Test that the discovery loop delegates to DiscoveryCoordinator"""
        self.device_manager.discovery_coordinator.run_loop = Mock()

        self.device_manager._discovery_loop()

        self.device_manager.discovery_coordinator.run_loop.assert_called_once_with()
    
    def test_thread_safety_register_device(self):
        """Test thread safety of device registration"""
        # Function to register devices in a thread
        def register_devices(thread_id):
            for i in range(5):
                device_name = f"ThreadDevice{thread_id}_{i}"
                device_info = {
                    "device_name": device_name,
                    "type": "dlna",
                    "hostname": f"192.168.{thread_id}.{i}",
                    "action_url": f"http://192.168.{thread_id}.{i}:49152/AVTransport/Control"
                }
                self.device_manager.register_device(device_info)
                time.sleep(0.01)  # Small delay to increase thread interleaving
        
        # Create and start threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=register_devices, args=(i,))
            thread.start()
            threads.append(thread)
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all devices were registered correctly
        registered_devices = self.device_manager.get_devices()
        self.assertEqual(len(registered_devices), 25)  # 5 threads * 5 devices each
        
        # Verify all expected device names are present
        device_names = [device.name for device in registered_devices]
        for thread_id in range(5):
            for i in range(5):
                device_name = f"ThreadDevice{thread_id}_{i}"
                self.assertIn(device_name, device_names)


if __name__ == "__main__":
    unittest.main() 
