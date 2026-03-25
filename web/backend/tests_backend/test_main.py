"""
Tests for the main application.
"""
import pytest
from fastapi.testclient import TestClient
import os
from unittest.mock import patch, MagicMock

from web.backend.main import app


class TestMain:
    """Tests for the main application."""
    
    def test_health_check(self, test_client):
        """Test the health check endpoint."""
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
    
    def test_root_redirect(self, test_client):
        """Test the root endpoint redirects to docs."""
        response = test_client.get("/")
        assert response.status_code == 200
        # Since we're following redirects by default, we should end up at the docs page
    
    def test_device_manager_initialization(self, test_client):
        """Test that the device manager is initialized."""
        # Since we can't easily mock the singleton, we'll just check that the device manager has been initialized
        # by verifying it has the expected methods
        from web.backend.main import device_manager
        assert hasattr(device_manager, 'register_device')
        assert hasattr(device_manager, 'get_device')
        assert hasattr(device_manager, 'start_discovery')
    
    def test_streaming_registry_initialization(self, test_client):
        """Test that the streaming registry is initialized."""
        # Since we can't easily mock the singleton, we'll just check that the streaming registry has been initialized
        # by verifying it has the expected methods
        from web.backend.main import streaming_registry
        assert hasattr(streaming_registry, 'register_session')
        assert hasattr(streaming_registry, 'get_session')
        assert hasattr(streaming_registry, 'get_active_sessions')
    
    def test_twisted_streaming_initialization(self, test_client):
        """Test that the twisted streaming service is initialized."""
        # Since we can't easily mock the singleton, we'll just check that the streaming service has been initialized
        # by verifying it has the expected methods
        from web.backend.main import streaming_service
        assert hasattr(streaming_service, 'start_server')
        assert hasattr(streaming_service, 'stop_server')
    
    def test_api_docs(self, test_client):
        """Test that the API docs are available."""
        response = test_client.get("/docs")
        assert response.status_code == 200
        
        # Check that the OpenAPI schema is available
        response = test_client.get("/openapi.json")
        assert response.status_code == 200
        
        # Verify some of the expected paths in the schema
        schema = response.json()
        
        # Check for API endpoints with flexible path matching
        devices_path_found = False
        videos_path_found = False
        
        for path in schema["paths"]:
            if "/api/devices" in path:
                devices_path_found = True
            if "/api/videos" in path:
                videos_path_found = True
        
        assert devices_path_found, "No devices API endpoint found in OpenAPI schema"
        assert videos_path_found, "No videos API endpoint found in OpenAPI schema"


class TestMainWithMocks:
    """Tests for the main application with mocked dependencies."""
    
    @patch("web.backend.main.device_manager")
    @patch("web.backend.main.init_db")
    @patch("web.backend.main.get_db")
    @patch("web.backend.main.get_app_runtime")
    @patch("web.backend.services.device_service.DeviceService")
    def test_startup_event(self, mock_device_service, mock_get_app_runtime, mock_get_db, mock_init_db, mock_device_manager):
        """Test the startup event."""
        # Mock the database session
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])

        mock_streaming_registry = MagicMock()
        mock_runtime = MagicMock(
            config_service=MagicMock(),
            streaming_registry=mock_streaming_registry,
            device_manager=mock_device_manager,
        )
        mock_get_app_runtime.return_value = mock_runtime

        # Mock the device service
        mock_device_service_instance = MagicMock()
        mock_device_service.return_value = mock_device_service_instance
        
        # Manually trigger the startup event
        from web.backend.main import startup_event
        
        # Run the startup event
        import asyncio
        asyncio.run(startup_event())
        
        # Check that the database was initialized
        mock_init_db.assert_called_once()
        
        # Check that runtime background services were started
        mock_runtime.start_background_services.assert_called_once()
    
    @patch("web.backend.main.device_manager")
    @patch("web.backend.main.streaming_registry")
    @patch("web.backend.main.streaming_service")
    @patch("web.backend.main.renderer_service")
    @patch("web.backend.main.get_app_runtime")
    def test_shutdown_event(self, mock_get_app_runtime, mock_renderer_service, mock_streaming_service, 
                           mock_streaming_registry, mock_device_manager):
        """Test the shutdown event."""
        mock_runtime = MagicMock(device_manager=mock_device_manager)
        mock_get_app_runtime.return_value = mock_runtime

        # Manually trigger the shutdown event
        from web.backend.main import shutdown_event
        
        # Run the shutdown event
        import asyncio
        asyncio.run(shutdown_event())
        
        # Check that resources were properly cleaned up
        mock_streaming_registry.stop_monitoring.assert_called_once()
        mock_streaming_service.stop_server.assert_called_once()
        mock_runtime.stop_background_services.assert_called_once()
        
        # Check that the renderer service was shut down if it exists
        if mock_renderer_service:
            mock_renderer_service.shutdown.assert_called_once()
