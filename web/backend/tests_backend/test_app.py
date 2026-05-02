"""
Tests for the main application entry point (app.py).
"""
import pytest
from unittest.mock import patch, MagicMock
import runpy
from pathlib import Path

# Import the app instance to ensure it's available for uvicorn.run
from web.backend.main import app as fastapi_app # This import is fine for context but not for direct comparison in this test
from unittest.mock import ANY # Import ANY for flexible argument matching

def test_app_py_main_block():
    """
    Test that app.py calls uvicorn.run when executed as __main__.
    """
    mock_uvicorn_run = MagicMock()

    with patch('uvicorn.run', mock_uvicorn_run):
        # Execute app.py as if it's the main script
        # We need to ensure that when app.py is run, its __name__ is "__main__"
        # runpy.run_module can achieve this, but it's simpler to use run_path
        # for a specific file.
        # However, app.py itself imports 'main.app', which is web.backend.main.app
        # The critical part is to check if uvicorn.run is called.
        
        # To simulate `python app.py`, we can use runpy.run_path
        # This will execute app.py in a way that its __name__ == "__main__"
        # We must ensure that web.backend.app is the target.
        # The app.py file is in the 'web/backend' directory.
        
        # The app.py script itself modifies sys.path, so that should be fine.
        # It then imports `from main import app`.
        # The `app` instance passed to uvicorn.run will be the one from web.backend.main.
        
        app_path = Path(__file__).resolve().parents[1] / 'app.py'
        runpy.run_path(str(app_path), run_name='__main__')

    mock_uvicorn_run.assert_called_once_with(ANY, host="0.0.0.0", port=8000)
