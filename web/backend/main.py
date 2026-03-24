import logging
import os
import sys
import traceback
import time

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from database.database import init_db, get_db
from routers import device_router, video_router, streaming_router, renderer_router, overlay_router, projection_router, log_router, mapping_router, media_library_router
from api.discovery_router import router as discovery_router
from core.device_manager import get_device_manager
from core.streaming_registry import StreamingSessionRegistry
from core.twisted_streaming import get_instance as get_twisted_streaming
from core.streaming_service import get_streaming_service
from services.overlay_cast_service import get_overlay_cast_service

# Configure logging - check if already configured by run.py
import logging.handlers

# Create custom filter to exclude repetitive endpoint logs
class EndpointFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self.excluded_paths = [
            "GET /api/devices/",
            "GET /api/videos/",
            "GET /api/devices HTTP",
            "GET /api/videos HTTP",
            "/health",
            "/api/streaming/active-sessions",
            "/api/projector",
        ]
    
    def filter(self, record):
        # Filter out repetitive GET requests for polling endpoints
        message = record.getMessage()
        return not any(path in message for path in self.excluded_paths)

# Check if logging is already configured
root_logger = logging.getLogger()
if not root_logger.handlers:
    # Only configure if not already done
    try:
        from logging_config import setup_logging
        setup_logging(log_level="INFO", log_file="dashboard_run.log")
    except ImportError:
        # Fallback configuration
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.addFilter(EndpointFilter())
        
        file_handler = logging.handlers.RotatingFileHandler(
            'dashboard_run.log',
            maxBytes=10485760,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        file_handler.addFilter(EndpointFilter())
        
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        formatter = logging.Formatter(log_format)
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
else:
    # Add endpoint filter to existing handlers
    endpoint_filter = EndpointFilter()
    for handler in root_logger.handlers:
        handler.addFilter(endpoint_filter)

# Get logger for this module
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="nano-dlna Dashboard",
    description="Web dashboard for managing DLNA and Transcreen projectors",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers with /api prefix
app.include_router(device_router, prefix="/api")
app.include_router(video_router, prefix="/api")
app.include_router(streaming_router, prefix="/api")
app.include_router(renderer_router, prefix="/api")  # Add the renderer router
app.include_router(overlay_router)  # Overlay router already has /api prefix
app.include_router(projection_router)  # Projection router already has /api prefix
app.include_router(mapping_router)
app.include_router(media_library_router)
app.include_router(log_router.router)  # Log streaming router
app.include_router(discovery_router)  # New unified discovery API (already has /api/v2/discovery prefix)

# Try to include depth_router if dependencies are available
try:
    # First check if numpy is available without importing anything from depth_processing
    import numpy
    import cv2
    import PIL
    import sklearn
    # Only if all dependencies are available, import the depth_router
    from routers import depth_router
    app.include_router(depth_router, prefix="/api")  # Add the depth router
    logger.info("Depth processing module loaded successfully")
except ImportError as e:
    logger.warning(f"Depth processing module not loaded due to missing dependencies: {e}")
    logger.warning("Install required packages with: pip install numpy opencv-python pillow scikit-learn")

# Root endpoint
@app.get("/")
async def root():
    return RedirectResponse(url="/docs")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Global service variables (initialized in startup)
device_manager = None
streaming_service = None
streaming_registry = None
renderer_service = None
migration_adapter = None

# Mount static files for the frontend
@app.on_event("startup")
async def startup_event():
    global device_manager, streaming_service, streaming_registry, renderer_service, migration_adapter
    
    logger.info("Starting nano-dlna Dashboard API")
    
    # Initialize log aggregation service
    try:
        from log_aggregation_service import get_log_aggregation_service, setup_log_collectors
        log_service = get_log_aggregation_service()
        setup_log_collectors()
        await log_service.start()
        logger.info("Log aggregation service started")
    except Exception as e:
        logger.error(f"Failed to start log aggregation service: {e}")
    
    # Initialize services here to prevent multiple executions during imports  
    device_manager = get_device_manager()  # Use singleton
    # Stop any existing streaming servers to prevent port conflicts
    streaming_service = get_twisted_streaming()
    streaming_service.stop_server()  # Explicitly stop any existing servers
    streaming_registry = StreamingSessionRegistry.get_instance()
    
    # Inject device_manager into the StreamingService singleton
    overlay_streaming_service = get_streaming_service()
    overlay_streaming_service.set_device_manager(device_manager)

    # Get or create the renderer service
    try:
        from core.renderer_service.service import RendererService
        from routers.renderer_router import get_renderer_service
        renderer_service = get_renderer_service()
        logger.info("Renderer Service initialized successfully")
    except Exception as e:
        logger.warning(f"Renderer Service initialization failed: {e}")
        renderer_service = None
    
    # Initialize the database
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
    
    # Create and set device service
    try:
        db_generator = get_db()
        db = next(db_generator)
        try:
            # Create a device service instance
            from services.device_service import DeviceService
            device_service = DeviceService(db, device_manager)
            
            # Set the device service in device manager for recovery operations
            device_manager.set_device_service(device_service)
            logger.info("Device service set in device manager")
        finally:
            db_generator.close()
    except Exception as e:
        logger.error(f"Error creating device service: {e}")
    
    # Load devices from configuration files
    try:
        # First, check for configuration files in the project root
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_files = [
            os.path.join(root_dir, "tramscreem+device_config.json"),
            os.path.join(os.path.dirname(__file__), "my_device_config.json"),
            os.path.join(os.path.dirname(__file__), "tramscreem+device_config.json"),
            os.path.join(root_dir, "my_device_config.json"),
        ]
        
        # Remove duplicates
        config_files = list(set(config_files))
        
        # Log all potential config files for debugging
        logger.info(f"Checking for config files: {config_files}")
        
        loaded = False
        for config_file in config_files:
            if os.path.exists(config_file):
                logger.info(f"Loading devices from {config_file}")
                try:
                    # Load devices from the config file using the existing device_service
                    devices = device_service.load_devices_from_config(config_file)
                    logger.info(f"Loaded {len(devices)} devices from {config_file}")
                    
                    loaded = True
                except Exception as e:
                    logger.error(f"Error loading devices from {config_file}: {e}")
        
        if not loaded:
            logger.warning("No configuration files found or loaded. Using sample data.")
        
        # Initialize all devices from database into device_manager memory
        # This ensures devices are immediately available even before discovery
        logger.info("Initializing devices from database into device_manager")
        try:
            db_devices = device_service.get_devices()
            logger.info(f"Found {len(db_devices)} devices in database")
            
            for device_dict in db_devices:
                device_name = device_dict.get("name")
                if not device_name:
                    continue
                    
                # Create device_info for registration
                device_info = {
                    "device_name": device_name,
                    "type": device_dict.get("type", "dlna"),
                    "hostname": device_dict.get("hostname", ""),
                    "action_url": device_dict.get("action_url", ""),
                    "friendly_name": device_dict.get("friendly_name", device_name),
                    "manufacturer": device_dict.get("manufacturer", ""),
                    "location": device_dict.get("location", ""),
                }
                
                # Add any additional config from the database
                if device_dict.get("config"):
                    device_info.update(device_dict["config"])
                
                # Register the device with device_manager
                registered_device = device_manager.register_device(device_info)
                if registered_device:
                    logger.info(f"Initialized device {device_name} from database")
                    
                    # Initialize device status as disconnected until discovery confirms
                    device_manager.update_device_status(
                        device_name=device_name,
                        status="disconnected",  # Will be updated by discovery if online
                        is_playing=device_dict.get("is_playing", False),
                        current_video=device_dict.get("current_video")
                    )
                else:
                    logger.warning(f"Failed to initialize device {device_name} from database")
                    
        except Exception as e:
            logger.error(f"Error initializing devices from database: {e}")
            logger.error(f"Exception details: {traceback.format_exc()}")
        
        # Start device discovery to find devices on the network
        # This will automatically play videos on devices when they are discovered
        # based on the configuration files loaded above
        logger.info("Starting device discovery")
        device_manager.start_discovery()
        
        # Start the migration adapter to bridge old and new discovery systems
        try:
            from discovery.migration import start_discovery_migration
            migration_adapter = start_discovery_migration(device_manager)
            logger.info("Started discovery system migration adapter")
        except Exception as e:
            logger.error(f"Failed to start discovery migration: {e}")
        
        # Log the number of devices in the device manager
        logger.info(f"Device manager has {len(device_manager.devices)} devices")
        
        # Log all devices in the device manager
        for device_name, device in device_manager.devices.items():
            logger.info(f"Device in manager: {device_name}, type: {device.type}, hostname: {device.hostname}, action_url: {device.action_url}")

        # Start the renderer service's streaming server
        if renderer_service:
            try:
                renderer_service.start_streaming_server()
                logger.info("RendererService streaming server started.")
            except Exception as e:
                logger.error(f"Failed to start RendererService streaming server: {e}")
        
    except Exception as e:
        logger.error(f"Error loading devices from config: {e}")
        logger.error(f"Exception details: {traceback.format_exc()}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down nano-dlna Dashboard API")
    
    # Stop log aggregation service
    try:
        from log_aggregation_service import get_log_aggregation_service
        log_service = get_log_aggregation_service()
        await log_service.stop()
        logger.info("Log aggregation service stopped")
    except Exception as e:
        logger.error(f"Failed to stop log aggregation service: {e}")
    
    # Stop streaming session monitoring
    if streaming_registry:
        streaming_registry.stop_monitoring()

    # Stop overlay cast sessions
    try:
        await get_overlay_cast_service().stop_all()
    except Exception as e:
        logger.error(f"Error stopping overlay cast service: {e}")
    
    # Stop all streaming servers
    if streaming_service:
        streaming_service.stop_server()
    
    # Stop device discovery
    if device_manager:
        device_manager.stop_discovery()
    
    # Stop migration adapter
    if migration_adapter:
        try:
            migration_adapter.stop_migration()
            logger.info("Discovery migration adapter stopped")
        except Exception as e:
            logger.error(f"Error stopping migration adapter: {e}")
    
    # Stop renderer service if it's running
    if renderer_service:
        try:
            renderer_service.shutdown()
            logger.info("Renderer Service stopped")
        except Exception as e:
            logger.error(f"Error stopping Renderer Service: {e}")

# Serve the frontend if the directory exists
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "build")
if os.path.exists(frontend_dir):
    app.mount("/app", StaticFiles(directory=frontend_dir, html=True), name="frontend")

# Serve static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
    
app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.mount("/backend-static", StaticFiles(directory=static_dir), name="backend-static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
