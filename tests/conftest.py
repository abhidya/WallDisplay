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
def clear_global_sqlalchemy_metadata_for_tests_directory(request):
    """
    Fixture to clear SQLAlchemy global metadata before tests in the 'tests/'
    directory run. This helps prevent "Table already defined" errors when
    models are imported multiple times across different test files that
    share the same global Base.metadata.
    """
    try:
        # Import and clear metadata at the start of the test session
        from sqlalchemy.orm import clear_mappers
        from web.backend.database.database import Base, metadata_obj
        
        print("INFO: tests/conftest.py: Clearing SQLAlchemy metadata and mappers.")
        
        # Clear existing metadata and mappers
        Base.metadata.clear()
        clear_mappers()
        
        # Re-import models to ensure they're registered with the cleared metadata
        # This is done inside init_db() which we'll call after clearing
        from web.backend.database.database import init_db
        init_db()
        
        print("INFO: tests/conftest.py: Metadata cleared and models re-registered.")
        
        yield
        
        # Cleanup after all tests
        Base.metadata.clear()
        clear_mappers()
        
    except ImportError as e:
        print(f"Warning: Could not import required modules in tests/conftest.py: {e}")
        yield
    except Exception as e:
        print(f"Warning: Error in metadata handling in tests/conftest.py: {e}")
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
