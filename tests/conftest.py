import pytest
import sys
import os
from pathlib import Path
from unittest.mock import patch
import tempfile
import shutil

# Ensure the project root is on the Python path so that `web.backend` can be imported
project_root = Path(__file__).parent.parent
backend_root = project_root / 'web' / 'backend'
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(backend_root))

# Set environment variable to indicate we're in test mode
os.environ["PYTEST_CURRENT_TEST"] = "true"

@pytest.fixture(scope="session", autouse=True)
def ensure_sqlalchemy_models_registered_for_tests():
    """
    Keep the shared SQLAlchemy metadata populated for the whole pytest run.

    Older tests tried to clear Base.metadata between suites to avoid duplicate
    table registration. That is unsafe with already-imported declarative model
    classes: clearing metadata detaches the table definitions from those
    classes, and later imports return cached modules without re-registering
    them. The backend fixture then sees an empty metadata collection.
    """
    try:
        from web.backend.database.database import Base
        from web.backend.models.device import DeviceModel  # noqa: F401
        from web.backend.models.video import VideoModel  # noqa: F401
        from web.backend.models.overlay import OverlayConfig  # noqa: F401
        from web.backend.models.projection import ProjectionConfig  # noqa: F401
        from web.backend.models.mapping_scene import MappingScene  # noqa: F401
        from web.backend.models.scene_rank import SceneRank  # noqa: F401
        from web.backend.models.scene_control_preset import SceneControlPreset  # noqa: F401
        from web.backend.models.media_directory import MediaDirectory  # noqa: F401
        from web.backend.models.media_list import MediaList  # noqa: F401
        from web.backend.models.media_channel import MediaChannel  # noqa: F401
        from web.backend.models.photo import PhotoModel  # noqa: F401
        from web.backend.models.photo_list import PhotoList  # noqa: F401

        if not {"devices", "videos"}.issubset(Base.metadata.tables):
            raise RuntimeError(
                f"SQLAlchemy test metadata missing required tables: {list(Base.metadata.tables)}"
            )
    except ImportError as e:
        print(f"Warning: Could not import required SQLAlchemy models in tests/conftest.py: {e}")
    yield

@pytest.fixture(scope="function")
def temp_test_dir():
    """Create a temporary directory for test files"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture(scope="function") 
def mock_dlna_discovery():
    """Mock DLNA device discovery to avoid network calls"""
    from tests.mocks.dlna_mocks import mock_discover_devices
    
    with patch('nanodlna.dlna._discover_upnp_devices', side_effect=mock_discover_devices):
        yield mock_discover_devices

@pytest.fixture(scope="function")
def mock_streaming_service():
    """Provide a mock streaming service"""
    from tests.mocks.streaming_mocks import MockStreamingService
    
    service = MockStreamingService()
    yield service
    service.stop_all_servers()

@pytest.fixture(scope="function")
def cleanup_twisted():
    """Ensure Twisted reactor is cleaned up after tests"""
    yield
    
    # Clean up any running Twisted servers
    try:
        from web.backend.core.twisted_streaming import get_instance
        instance = get_instance()
        if instance:
            instance.stop_server()
    except Exception:
        pass
