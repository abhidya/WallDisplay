"""
Pytest configuration file with fixtures for testing.
"""
import os
import sys
import pytest
from fastapi.testclient import TestClient

# Calculate the project root directory (three levels up from tests_backend)
# __file__ is .../nano-dlna/web/backend/tests_backend/conftest.py
# project_root is .../nano-dlna
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set environment variable to indicate we're in test mode
os.environ["PYTEST_CURRENT_TEST"] = "true"

# Now imports like `from web.backend...` should work.

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, clear_mappers
import tempfile

# Import database components
from web.backend.database.database import Base, get_db, metadata_obj

# Import all models at module level to ensure they're registered with metadata
# This must happen before any Base.metadata operations
from web.backend.models.device import DeviceModel
from web.backend.models.video import VideoModel
from web.backend.models.overlay import OverlayConfig
from web.backend.models.projection import ProjectionConfig

# Clear and re-register models to avoid conflicts
try:
    print(f"INFO: web/backend/tests_backend/conftest.py: Clearing metadata and mappers")
    Base.metadata.clear()
    clear_mappers()
    
    # Re-import models after clearing to ensure clean registration
    from web.backend.models.device import DeviceModel as _DeviceModel
    from web.backend.models.video import VideoModel as _VideoModel
    from web.backend.models.overlay import OverlayConfig as _OverlayConfig
    from web.backend.models.projection import ProjectionConfig as _ProjectionConfig
    from web.backend.models.mapping_scene import MappingScene as _MappingScene
    from web.backend.models.scene_rank import SceneRank as _SceneRank
    from web.backend.models.media_directory import MediaDirectory as _MediaDirectory
    from web.backend.models.media_list import MediaList as _MediaList
    from web.backend.models.media_channel import MediaChannel as _MediaChannel
    from web.backend.models.photo import PhotoModel as _PhotoModel
    from web.backend.models.photo_list import PhotoList as _PhotoList
    
    print(f"INFO: web/backend/tests_backend/conftest.py: Models re-registered successfully")
except Exception as e:
    print(f"WARNING: Error during metadata clearing in web/backend/tests_backend/conftest.py: {e}")

# Import app and core components
from web.backend.main import app
from web.backend.core.device_manager import DeviceManager
from web.backend.core.streaming_registry import StreamingSessionRegistry
from web.backend.core.twisted_streaming import get_instance as get_twisted_streaming


# Database setup
@pytest.fixture(scope="function")
def test_db():
    """
    Create a test database and provide a single shared session for both
    the test function and the FastAPI app's dependency override.
    """
    temp_db_file = tempfile.NamedTemporaryFile(suffix=".db")
    engine = create_engine(
        f"sqlite:///{temp_db_file.name}",
        connect_args={"check_same_thread": False} # Necessary for SQLite
    )
    TestingSessionShared = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Ensure all tables are created using the Base from database.py
    # Models should be imported at the module level of this conftest.py
    # or via web.backend.database.database to populate Base.metadata
    print(f"DEBUG CONTEXT: web/backend/tests_backend/conftest.py - test_db (shared session) fixture")
    print(f"DEBUG: Attempting to create tables. Registered tables in Base.metadata: {list(Base.metadata.tables.keys())}")
    Base.metadata.create_all(bind=engine)
    print(f"DEBUG: Finished Base.metadata.create_all(bind=engine).")

    # Verify table creation
    from sqlalchemy import inspect
    inspector = inspect(engine)
    actual_tables = inspector.get_table_names()
    print(f"DEBUG: Actual tables found in database '{temp_db_file.name}' after create_all: {actual_tables}")
    if not ('devices' in actual_tables and 'videos' in actual_tables):
        metadata_keys = list(Base.metadata.tables.keys())
        error_message = (
            f"Test DB setup failed: Expected tables 'devices' and 'videos' were NOT created in {temp_db_file.name}.\n"
            f"Registered tables in Base.metadata before create_all: {metadata_keys}\n"
            f"Actual tables found in database after create_all: {actual_tables}"
        )
        print(f"ERROR: {error_message}")
        raise RuntimeError(error_message)

    # Create the single session instance to be shared
    shared_session = TestingSessionShared()

    # Define the override for get_db to use this shared session
    def override_get_db_with_shared():
        try:
            yield shared_session  # Yield the pre-existing shared_session
        finally:
            # The lifecycle of shared_session is managed by the test_db fixture's main try/finally block
            # Do not close it here, as it's used by the test function too.
            pass
            
    # Store original override if any, to restore it later
    original_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db_with_shared
    
    try:
        yield shared_session  # Provide the shared session to the test function
    finally:
        # Teardown: restore original override or clear it
        if original_override:
            app.dependency_overrides[get_db] = original_override
        elif get_db in app.dependency_overrides: # Check before deleting
            del app.dependency_overrides[get_db]
        
        shared_session.close()
        Base.metadata.drop_all(bind=engine)
        temp_db_file.close()


@pytest.fixture(scope="function")
def test_client(test_db):
    """Create a test client."""
    # Ensure dependency overrides for services are set up if needed by other tests using this client
    # For example, if router tests need mocked services:
    # from unittest.mock import MagicMock
    # from services.device_service import get_device_service as get_device_service_dependency
    # from services.video_service import get_video_service as get_video_service_dependency
    # mock_device_service = MagicMock()
    # mock_video_service = MagicMock()
    # app.dependency_overrides[get_device_service_dependency] = lambda: mock_device_service
    # app.dependency_overrides[get_video_service_dependency] = lambda: mock_video_service

    with TestClient(app) as client:
        yield client
    
    # Teardown: Stop all streaming servers after tests using the client are done
    try:
        streaming_server_instance = get_twisted_streaming()
        if streaming_server_instance:
            streaming_server_instance.stop_server() # Corrected method name
            print("INFO: All streaming servers stopped by test_client fixture teardown.")
    except Exception as e:
        print(f"ERROR: Exception during test_client teardown trying to stop streaming servers: {e}")

    # Stop device discovery after tests using the client are done
    try:
        from web.backend.core.device_manager import get_device_manager # Ensure we get the singleton
        dm = get_device_manager()
        if dm.discovery_running: # Check if discovery is actually running
            dm.stop_discovery()
            print("INFO: Device discovery stopped by test_client fixture teardown.")
        # Optionally clear state if needed, though new DB per test helps
        # with dm.device_lock:
        #     dm.devices.clear()
        # with dm.status_lock:
        #     dm.device_status.clear()
        # print("INFO: Device manager state potentially reset by test_client fixture teardown.")
    except Exception as e:
        print(f"ERROR: Exception during test_client teardown trying to stop/reset device manager: {e}")
    
    # Clear dependency overrides made by this fixture or individual tests if any were added above
    # app.dependency_overrides.clear() # This was already done by test_db fixture for get_db


@pytest.fixture(scope="function")
def device_manager():
    """Create a device manager."""
    return DeviceManager()


@pytest.fixture(scope="function")
def streaming_registry():
    """Create a streaming registry."""
    return StreamingSessionRegistry.get_instance()


@pytest.fixture(scope="function")
def twisted_streaming():
    """Get twisted streaming instance."""
    return get_twisted_streaming()


@pytest.fixture(scope="function")
def sample_device():
    """Create a sample device."""
    return DeviceModel(
        name="Test Device",
        type="dlna",
        hostname="127.0.0.1",
        action_url="http://127.0.0.1:8000/action",
        location="http://127.0.0.1:8000/location",
        friendly_name="Test Device",
        status="online"
    )


@pytest.fixture(scope="function")
def sample_video():
    """Create a sample video."""
    return VideoModel(
        name="Test Video",
        path="/path/to/test_video.mp4",
        file_name="test_video.mp4",
        file_size=1024,
        format="mp4",
        duration=60.0,
        resolution="1920x1080",
        has_subtitle=False
    )


@pytest.fixture(scope="function")
def tmp_video_file():
    """Create a temporary video file."""
    # Create a temporary file to simulate a video
    temp_file = tempfile.NamedTemporaryFile(suffix=".mp4")
    # Write some dummy content to the file
    temp_file.write(b"test video content")
    temp_file.flush()
    
    yield temp_file.name
    
    # Clean up
    temp_file.close()


@pytest.fixture(scope="function")
def tmp_config_file():
    """Create a temporary config file."""
    # Create a temporary file to simulate a config file
    temp_file = tempfile.NamedTemporaryFile(suffix=".json")
    # Write a sample configuration
    temp_file.write(b'''
    {
        "devices": [
            {
                "name": "Test Device",
                "type": "dlna",
                "hostname": "127.0.0.1",
                "location": "http://127.0.0.1:8000/location",
                "action_url": "http://127.0.0.1:8000/action",
                "control_url": "http://127.0.0.1:8000/control"
            }
        ]
    }
    ''')
    temp_file.flush()
    
    yield temp_file.name
    
    # Clean up
    temp_file.close()
