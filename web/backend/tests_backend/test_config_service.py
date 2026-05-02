"""
Tests for the ConfigService class, verifying thread-safe configuration management.
This file will be renamed to test_config_service.py.
"""

import pytest
import os
import json
import tempfile
import threading
import time
# from unittest.mock import patch, MagicMock # Not strictly needed for these tests yet

from web.backend.core.config_service import ConfigService

@pytest.fixture
def config_service_fixture():
    """
    Pytest fixture to set up and tear down ConfigService and temp files.
    """
    # Reset the ConfigService singleton for each test
    ConfigService._instance = None
    service = ConfigService.get_instance()
    service.clear_configurations()
    
    temp_dir = tempfile.TemporaryDirectory()
    
    test_config_data = [
        {
            "device_name": "TestDevice1",
            "type": "dlna",
            "hostname": "192.168.1.100",
            "action_url": "http://192.168.1.100/action",
            "video_file": os.path.join(temp_dir.name, "test_video1.mp4")
        },
        {
            "device_name": "TestDevice2",
            "type": "dlna",
            "hostname": "192.168.1.101",
            "action_url": "http://192.168.1.101/action",
            "video_file": os.path.join(temp_dir.name, "test_video2.mp4")
        }
    ]
    
    config_file_path = os.path.join(temp_dir.name, "test_config.json")
    with open(config_file_path, "w") as f:
        json.dump(test_config_data, f)
    
    # Create dummy video files
    for device_conf in test_config_data:
        with open(device_conf["video_file"], "w") as f:
            f.write("dummy_video_content")
            
    yield service, config_file_path, test_config_data, temp_dir.name # Provide service and paths to tests
    
    temp_dir.cleanup() # Implicitly removes files within


def test_singleton_pattern():
    """Test that the ConfigService follows the singleton pattern"""
    instance1 = ConfigService.get_instance()
    instance2 = ConfigService.get_instance()
    assert instance1 is instance2

def test_load_configs_from_file(config_service_fixture):
    """Test loading configurations from a file"""
    service, config_file_path, _, _ = config_service_fixture
    
    loaded_devices = service.load_configs_from_file(config_file_path)
    
    assert len(loaded_devices) == 2
    assert "TestDevice1" in loaded_devices
    assert "TestDevice2" in loaded_devices
    
    configs = service.get_all_device_configs()
    assert len(configs) == 2
    assert "TestDevice1" in configs
    assert "TestDevice2" in configs
    assert configs["TestDevice1"]["hostname"] == "192.168.1.100"
    assert configs["TestDevice2"]["hostname"] == "192.168.1.101"

def test_avoid_duplicate_loading(config_service_fixture):
    """Test that the same configuration file is not loaded twice"""
    service, config_file_path, _, _ = config_service_fixture

    # The ConfigService's load_configs_from_file now clears configs from the source file first.
    # So, loading twice will result in the same devices being loaded, not 0 on the second load.
    # The old test expected 0 on second load, which is no longer the behavior.
    # The important part is that it doesn't create duplicate *entries* in the service.
    
    first_load_names = service.load_configs_from_file(config_file_path)
    assert len(first_load_names) == 2
    configs_after_first_load = service.get_all_device_configs()
    assert len(configs_after_first_load) == 2

    second_load_names = service.load_configs_from_file(config_file_path)
    assert len(second_load_names) == 2 # It reloads them
    
    configs_after_second_load = service.get_all_device_configs()
    assert len(configs_after_second_load) == 2 # Still only 2 unique device configs


def test_add_device_config(config_service_fixture):
    """Test adding a device configuration manually"""
    service, _, _, temp_dir_path = config_service_fixture
    
    video_file_path = os.path.join(temp_dir_path, "test_video3.mp4")
    with open(video_file_path, "w") as f:
        f.write("dummy_video_content")

    device_config = {
        "type": "dlna",
        "hostname": "192.168.1.102",
        "action_url": "http://192.168.1.102/action",
        "video_file": video_file_path
    }
    
    result = service.add_device_config("TestDevice3", device_config)
    assert result is True
    
    configs = service.get_all_device_configs()
    assert len(configs) == 1
    assert "TestDevice3" in configs
    assert configs["TestDevice3"]["hostname"] == "192.168.1.102"

def test_remove_device_config(config_service_fixture):
    """Test removing a device configuration"""
    service, config_file_path, _, _ = config_service_fixture
    service.load_configs_from_file(config_file_path) # Load initial
    
    result = service.remove_device_config("TestDevice1")
    assert result is True
    
    configs = service.get_all_device_configs()
    assert len(configs) == 1
    assert "TestDevice1" not in configs
    assert "TestDevice2" in configs

def test_update_device_config(config_service_fixture):
    """Test updating a device configuration"""
    service, config_file_path, _, _ = config_service_fixture
    service.load_configs_from_file(config_file_path) # Load initial

    update = {"hostname": "192.168.1.200"}
    result = service.update_device_config("TestDevice1", update)
    assert result is True
    
    configs = service.get_all_device_configs()
    assert configs["TestDevice1"]["hostname"] == "192.168.1.200"
    assert configs["TestDevice1"]["type"] == "dlna" # Original value

def test_invalid_video_file(config_service_fixture):
    """Test that a device configuration with a non-existent video file fails"""
    service, _, _, temp_dir_path = config_service_fixture
    
    non_existent_video_path = os.path.join(temp_dir_path, "non_existent_video.mp4")
    device_config = {
        "type": "dlna",
        "hostname": "192.168.1.103",
        "action_url": "http://192.168.1.103/action",
        "video_file": non_existent_video_path
    }
    
    result = service.add_device_config("TestDevice4", device_config)
    assert result is False # Should fail as video_file doesn't exist
    
    configs = service.get_all_device_configs()
    assert "TestDevice4" not in configs

def test_save_configs_to_file(config_service_fixture):
    """Test saving configurations to a file"""
    service, config_file_path, _, temp_dir_path = config_service_fixture
    service.load_configs_from_file(config_file_path) # Load initial

    new_file_path = os.path.join(temp_dir_path, "saved_config.json")
    result = service.save_configs_to_file(new_file_path)
    assert result is True
    
    assert os.path.exists(new_file_path)
    
    with open(new_file_path, "r") as f:
        saved_data = json.load(f)
    
    assert len(saved_data) == 2
    saved_device_names = [d["device_name"] for d in saved_data]
    assert "TestDevice1" in saved_device_names
    assert "TestDevice2" in saved_device_names

def test_thread_safety(config_service_fixture):
    """Test thread safety of configuration operations"""
    service, _, _, temp_dir_path = config_service_fixture

    def add_configs_thread_target(thread_id):
        for i in range(5):
            device_name = f"ThreadDevice{thread_id}_{i}"
            video_file_path = os.path.join(temp_dir_path, f"thread_video_{thread_id}_{i}.mp4")
            with open(video_file_path, "w") as f:
                f.write("dummy")
            
            config = {
                "type": "dlna",
                "hostname": f"192.168.{thread_id}.{i}",
                "action_url": f"http://192.168.{thread_id}.{i}/action",
                "video_file": video_file_path
            }
            service.add_device_config(device_name, config)
            time.sleep(0.01) 
    
    threads = []
    for i in range(5):
        thread = threading.Thread(target=add_configs_thread_target, args=(i,))
        thread.start()
        threads.append(thread)
    
    for thread in threads:
        thread.join()
    
    configs = service.get_all_device_configs()
    assert len(configs) == 25 
    
    for thread_id in range(5):
        for i in range(5):
            device_name = f"ThreadDevice{thread_id}_{i}"
            assert device_name in configs
            assert configs[device_name]["hostname"] == f"192.168.{thread_id}.{i}"
