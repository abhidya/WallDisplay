"""Enhanced test helper utilities."""

import asyncio
import contextlib
import functools
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Union
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from web.backend.database.database import Base
from web.backend.models.device import DeviceModel
from web.backend.models.video import VideoModel
import random


class TestTimer:
    """Context manager for timing test operations."""
    
    def __init__(self, name: str = "Operation"):
        self.name = name
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        print(f"\n{self.name} took {self.duration:.3f} seconds")
    
    @property
    def elapsed(self) -> float:
        """Get elapsed time during execution."""
        if self.start_time is None:
            return 0
        return time.time() - self.start_time


class TestDataGenerator:
    """Generate test data with realistic patterns."""
    
    @staticmethod
    def generate_device_discovery_data(num_devices: int = 5) -> List[Dict[str, Any]]:
        """Generate realistic device discovery data."""
        devices = []
        
        device_templates = [
            {"manufacturer": "Samsung", "model_prefix": "UN", "type": "TV"},
            {"manufacturer": "LG", "model_prefix": "OLED", "type": "TV"},
            {"manufacturer": "Sony", "model_prefix": "KD", "type": "TV"},
            {"manufacturer": "Roku", "model_prefix": "Ultra", "type": "Streaming"},
            {"manufacturer": "Generic", "model_prefix": "DLNA", "type": "Renderer"}
        ]
        
        for i in range(num_devices):
            template = device_templates[i % len(device_templates)]
            device = {
                "name": f"{template['manufacturer']} {template['type']} {i+1}",
                "manufacturer": template["manufacturer"],
                "model": f"{template['model_prefix']}-{65 + i}X{900 + i}",
                "udn": f"uuid:{''.join(f'{i:02x}' for i in range(16))}",
                "ip": f"192.168.1.{100 + i}",
                "port": 8000 + i,
                "services": [
                    "urn:schemas-upnp-org:service:AVTransport:1",
                    "urn:schemas-upnp-org:service:RenderingControl:1"
                ]
            }
            devices.append(device)
        
        return devices
    
    @staticmethod
    def generate_streaming_load(duration_seconds: int = 60) -> Generator[Dict[str, Any], None, None]:
        """Generate streaming load patterns for testing."""
        start_time = time.time()
        
        while time.time() - start_time < duration_seconds:
            yield {
                "timestamp": datetime.now(timezone.utc),
                "bytes_requested": random.randint(1024, 1048576),  # 1KB to 1MB
                "latency_ms": random.randint(1, 100),
                "client_count": random.randint(1, 10)
            }
            time.sleep(random.uniform(0.1, 0.5))


class AsyncTestHelper:
    """Helper for async test operations."""
    
    @staticmethod
    def run_async(coro):
        """Run an async coroutine in a test."""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro)
    
    @staticmethod
    async def wait_for_condition(
        condition_func,
        timeout: float = 5.0,
        interval: float = 0.1
    ) -> bool:
        """Wait for a condition to become true."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if await condition_func():
                return True
            await asyncio.sleep(interval)
        
        return False
    
    @staticmethod
    @contextlib.asynccontextmanager
    async def timeout(seconds: float):
        """Async timeout context manager."""
        async def _timeout():
            await asyncio.sleep(seconds)
            raise TimeoutError(f"Operation timed out after {seconds} seconds")
        
        task = asyncio.create_task(_timeout())
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


class DatabaseTestHelper:
    """Helper for database testing."""
    
    @staticmethod
    @contextlib.contextmanager
    def temp_database() -> Generator[Session, None, None]:
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
            db_url = f"sqlite:///{tmp_file.name}"
            
        engine = create_engine(db_url)
        Base.metadata.create_all(engine)
        
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
        try:
            yield session
        finally:
            session.close()
            engine.dispose()
            os.unlink(tmp_file.name)
    
    @staticmethod
    def seed_test_data(session: Session) -> Dict[str, List[Any]]:
        """Seed database with simple representative data."""
        devices = []
        for i in range(5):
            db_device = DeviceModel(
                name=f"TestDevice{i}",
                type="dlna",
                hostname=f"192.168.1.{100 + i}",
                action_url=f"http://192.168.1.{100 + i}/action",
                friendly_name=f"Test Device {i}",
                status="connected",
                is_playing=False,
            )
            session.add(db_device)
            devices.append(db_device)

        videos = []
        for i in range(10):
            db_video = VideoModel(
                name=f"Test Video {i}",
                path=f"/tmp/test_video_{i}.mp4",
                file_name=f"test_video_{i}.mp4",
                file_size=1024 * (i + 1),
                duration=60.0 + i,
                format="mp4",
                resolution="1920x1080",
            )
            session.add(db_video)
            videos.append(db_video)

        session.commit()

        return {
            "devices": devices,
            "videos": videos,
        }


class NetworkTestHelper:
    """Helper for network-related testing."""
    
    @staticmethod
    @contextlib.contextmanager
    def mock_network_conditions(
        latency_ms: int = 0,
        packet_loss: float = 0.0,
        bandwidth_limit_mbps: Optional[float] = None
    ):
        """Mock network conditions for testing."""
        original_socket = __import__('socket').socket
        
        class MockSocket(original_socket):
            def send(self, data, flags=0):
                # Simulate latency
                if latency_ms > 0:
                    time.sleep(latency_ms / 1000.0)
                
                # Simulate packet loss
                if packet_loss > 0 and random.random() < packet_loss:
                    raise ConnectionError("Simulated packet loss")
                
                # Simulate bandwidth limit
                if bandwidth_limit_mbps:
                    bytes_per_second = bandwidth_limit_mbps * 1024 * 1024 / 8
                    sleep_time = len(data) / bytes_per_second
                    time.sleep(sleep_time)
                
                return super().send(data, flags)
        
        with patch('socket.socket', MockSocket):
            yield
    
    @staticmethod
    def simulate_device_disconnect(device: Device):
        """Simulate a device disconnection."""
        device.status = "disconnected"
        device.is_playing = False
        device.current_video = None


class FileTestHelper:
    """Helper for file-related testing."""
    
    @staticmethod
    @contextlib.contextmanager
    def temp_video_files(count: int = 3) -> Generator[List[Path], None, None]:
        """Create temporary video files for testing."""
        temp_dir = tempfile.mkdtemp()
        files = []
        
        try:
            for i in range(count):
                file_path = Path(temp_dir) / f"test_video_{i}.mp4"
                # Create a small test file
                with open(file_path, 'wb') as f:
                    f.write(b'FAKE_VIDEO_DATA' * 1000)
                files.append(file_path)
            
            yield files
        finally:
            for file in files:
                if file.exists():
                    file.unlink()
            Path(temp_dir).rmdir()
    
    @staticmethod
    def create_large_file(path: Path, size_mb: int):
        """Create a large file for testing."""
        chunk_size = 1024 * 1024  # 1MB
        
        with open(path, 'wb') as f:
            for _ in range(size_mb):
                f.write(os.urandom(chunk_size))


class MockHelper:
    """Helper for creating common mocks."""
    
    @staticmethod
    def create_mock_websocket() -> MagicMock:
        """Create a mock WebSocket connection."""
        mock_ws = MagicMock()
        mock_ws.send = MagicMock(return_value=asyncio.Future())
        mock_ws.send.return_value.set_result(None)
        mock_ws.recv = MagicMock(return_value=asyncio.Future())
        mock_ws.close = MagicMock(return_value=asyncio.Future())
        mock_ws.close.return_value.set_result(None)
        return mock_ws
    
    @staticmethod
    def create_mock_http_response(
        status_code: int = 200,
        json_data: Optional[Dict] = None,
        text: str = ""
    ) -> MagicMock:
        """Create a mock HTTP response."""
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.text = text
        mock_response.json.return_value = json_data or {}
        mock_response.raise_for_status = MagicMock()
        
        if status_code >= 400:
            mock_response.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
        
        return mock_response


class PerformanceTestHelper:
    """Helper for performance testing."""
    
    @staticmethod
    def measure_memory_usage(func):
        """Decorator to measure memory usage of a function."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import tracemalloc
            
            tracemalloc.start()
            result = func(*args, **kwargs)
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            
            print(f"\nMemory usage for {func.__name__}:")
            print(f"  Current: {current / 1024 / 1024:.2f} MB")
            print(f"  Peak: {peak / 1024 / 1024:.2f} MB")
            
            return result
        
        return wrapper
    
    @staticmethod
    def benchmark(iterations: int = 100):
        """Decorator to benchmark function execution."""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                times = []
                
                for _ in range(iterations):
                    start = time.perf_counter()
                    result = func(*args, **kwargs)
                    end = time.perf_counter()
                    times.append(end - start)
                
                avg_time = sum(times) / len(times)
                min_time = min(times)
                max_time = max(times)
                
                print(f"\nBenchmark for {func.__name__} ({iterations} iterations):")
                print(f"  Average: {avg_time * 1000:.3f} ms")
                print(f"  Min: {min_time * 1000:.3f} ms")
                print(f"  Max: {max_time * 1000:.3f} ms")
                
                return result
            
            return wrapper
        
        return decorator


# Convenience functions
def assert_eventually(
    condition_func,
    timeout: float = 5.0,
    interval: float = 0.1,
    message: str = "Condition was not met within timeout"
):
    """Assert that a condition eventually becomes true."""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if condition_func():
            return
        time.sleep(interval)
    
    raise AssertionError(message)


def wait_for(condition_func, timeout: float = 5.0) -> bool:
    """Wait for a condition to be true."""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if condition_func():
            return True
        time.sleep(0.1)
    
    return False


# Test data fixtures
TEST_VIDEO_URLS = [
    "http://example.com/video1.mp4",
    "http://example.com/video2.mp4",
    "http://example.com/video3.mp4"
]

TEST_DEVICE_IPS = [
    "192.168.1.100",
    "192.168.1.101",
    "192.168.1.102"
]

TEST_OVERLAY_CONFIGS = [
    {
        "type": "text",
        "config": {
            "text": "Test Overlay",
            "position": {"x": 10, "y": 10},
            "size": 24
        }
    },
    {
        "type": "image",
        "config": {
            "url": "http://example.com/overlay.png",
            "position": {"x": 50, "y": 50}
        }
    }
]