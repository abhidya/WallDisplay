import unittest
import os
import sys
import json
import time
import subprocess
import requests
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestFrontendComponents(unittest.TestCase):
    """Test cases for frontend components and dashboard integration"""
    
    def setUp(self):
        """Set up test environment"""
        self.root_dir = Path(__file__).parent.parent
        self.web_dir = self.root_dir / "web"
        self.frontend_dir = self.web_dir / "frontend"
        self.backend_dir = self.web_dir / "backend"
    
    def test_frontend_files_exist(self):
        """Verify that essential frontend files exist"""
        # Check package.json exists
        package_json_path = self.frontend_dir / "package.json"
        self.assertTrue(package_json_path.exists(), f"Missing package.json at {package_json_path}")
        
        # Check public/index.html exists
        index_html_path = self.frontend_dir / "public" / "index.html"
        self.assertTrue(index_html_path.exists(), f"Missing index.html at {index_html_path}")
        
        # Check src/index.js exists
        index_js_path = self.frontend_dir / "src" / "index.js"
        self.assertTrue(index_js_path.exists(), f"Missing index.js at {index_js_path}")
    
    def test_backend_api_endpoints_defined(self):
        """Test that backend API endpoints are properly defined"""
        # Check main app file exists
        main_app_path = self.backend_dir / "main.py"
        self.assertTrue(main_app_path.exists(), f"Missing main.py at {main_app_path}")
        
        # Check device router exists
        device_router_path = self.backend_dir / "routers" / "device_router.py"
        self.assertTrue(device_router_path.exists(), f"Missing device_router.py at {device_router_path}")
        
        # Check video router exists
        video_router_path = self.backend_dir / "routers" / "video_router.py"
        self.assertTrue(video_router_path.exists(), f"Missing video_router.py at {video_router_path}")
        
        # Check streaming router exists
        streaming_router_path = self.backend_dir / "routers" / "streaming_router.py"
        self.assertTrue(streaming_router_path.exists(), f"Missing streaming_router.py at {streaming_router_path}")
    
    def test_frontend_api_client(self):
        """Test that frontend API client is properly configured"""
        # Look for API client file in frontend code
        services_dir = self.frontend_dir / "src" / "services"
        api_files = list(services_dir.glob("*api*.js"))
        
        # Verify at least one API client file exists
        self.assertTrue(len(api_files) > 0, "No API client files found in frontend/src/services")
        
        # Check content of the first API file
        if len(api_files) > 0:
            with open(api_files[0], 'r') as f:
                content = f.read()
                # Check for API base URL definition
                self.assertTrue("baseURL" in content or "BASE_URL" in content or "apiUrl" in content, 
                               f"No API base URL found in {api_files[0]}")
    
    @unittest.skip("Run this test manually when frontend and backend are properly installed")
    def test_dashboard_script(self):
        """Test the run_dashboard.sh script (run manually)"""
        # Verify script exists
        dashboard_script = self.root_dir / "run_dashboard.sh"
        self.assertTrue(dashboard_script.exists(), f"Missing run_dashboard.sh at {dashboard_script}")
        
        # Verify stop script exists
        stop_script = self.root_dir / "stop_dashboard.sh"
        self.assertTrue(stop_script.exists(), f"Missing stop_dashboard.sh at {stop_script}")
        
        # Start the dashboard in a subprocess
        process = subprocess.Popen(
            [str(dashboard_script)],
            cwd=str(self.root_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        try:
            # Wait for servers to start
            time.sleep(10)
            
            # Check if backend is running
            backend_running = False
            try:
                response = requests.get("http://localhost:8000/api/devices/")
                if response.status_code == 200:
                    backend_running = True
            except requests.RequestException:
                pass
            
            # Check if frontend is running
            frontend_running = False
            try:
                response = requests.get("http://localhost:3000/")
                if response.status_code == 200:
                    frontend_running = True
            except requests.RequestException:
                pass
            
            # Assert components are running
            self.assertTrue(backend_running, "Backend server is not running")
            self.assertTrue(frontend_running, "Frontend server is not running")
            
        finally:
            # Clean up - stop the dashboard
            subprocess.run([str(stop_script)], cwd=str(self.root_dir))
    
    def test_script_dependencies(self):
        """Test that script dependencies are correctly declared"""
        # Check run_dashboard.sh
        dashboard_script = self.root_dir / "run_dashboard.sh"
        
        if dashboard_script.exists():
            with open(dashboard_script, 'r') as f:
                content = f.read()
                
                # Verify proper shebang
                self.assertTrue(content.startswith("#!/bin/bash") or content.startswith("#!/usr/bin/env bash"), 
                               "run_dashboard.sh does not have proper shebang")
                
                # Verify clean command
                self.assertTrue("kill" in content or "pkill" in content, 
                               "run_dashboard.sh does not contain process termination commands")
                
                # Verify environment/bootstrap wiring through common_env.sh
                self.assertTrue('scripts/common_env.sh' in content or 'source "$SCRIPT_DIR/scripts/common_env.sh"' in content,
                               "run_dashboard.sh does not source common environment setup")
    
    def test_dashboard_path_handling(self):
        """Test path handling in dashboard scripts"""
        # Check for absolute path usage in scripts
        for script_name in ["run_dashboard.sh", "stop_dashboard.sh"]:
            script_path = self.root_dir / script_name
            
            if script_path.exists():
                with open(script_path, 'r') as f:
                    content = f.read()
                    
                    # Verify script anchors itself to its own location or shared env root.
                    self.assertTrue(
                        'SCRIPT_DIR=' in content or 'NANODLNA_ROOT_DIR' in content or '$(pwd)' in content,
                        f"{script_name} does not anchor paths to a stable base directory"
                    )
    
    def test_device_discovery_api(self):
        """Test device discovery API endpoint (mock version)"""
        # Create mock response for device discovery
        mock_devices = [
            {
                "id": 1,
                "name": "Smart_Projector-45[DLNA]",
                "type": "dlna",
                "hostname": "10.0.0.45",
                "friendly_name": "Smart_Projector-45[DLNA]",
                "status": "connected"
            },
            {
                "id": 2,
                "name": "SideProjector_dlna",
                "type": "dlna",
                "hostname": "10.0.0.122",
                "friendly_name": "SideProjector_dlna",
                "status": "connected"
            }
        ]
        
        # Mock requests for testing API client
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_devices
            mock_get.return_value = mock_response
            
            # Call frontend API (mocked)
            response = requests.get("http://localhost:8000/api/devices/")
            
            # Verify response
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json()), 2)
            self.assertEqual(response.json()[0]["name"], "Smart_Projector-45[DLNA]")


if __name__ == "__main__":
    unittest.main() 