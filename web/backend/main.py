import asyncio
import logging
import os
import sys
import traceback
import time
import ipaddress
from urllib.parse import urlsplit

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from web.backend.database.database import init_db, get_db, SessionLocal
from web.backend.routers.device_router import router as device_router
from web.backend.routers.video_router import router as video_router
from web.backend.routers.streaming_router import router as streaming_router
from web.backend.routers.renderer_router import router as renderer_router
from web.backend.routers.overlay_router import router as overlay_router
from web.backend.routers.projection_router import router as projection_router
from web.backend.routers.log_router import router as log_router
from web.backend.routers.mapping_router import router as mapping_router
from web.backend.routers.media_library_router import router as media_library_router
from web.backend.routers.structured_lighting_router import router as structured_lighting_router
from web.backend.routers.widget_router import router as widget_router
from web.backend.routers.diagnostics_router import router as diagnostics_router
from web.backend.routers.photo_router import router as photo_router
from web.backend.routers.photo_list_router import router as photo_list_router
from web.backend.api.discovery_router import router as discovery_router
from web.backend.core.twisted_streaming import get_instance as get_twisted_streaming
from web.backend.core.streaming_service import get_streaming_service
from web.backend.services.overlay_cast_service import get_overlay_cast_service
from web.backend.services.app_runtime import get_app_runtime
from web.backend.services.mask_preprocessing_service import get_mask_preprocessing_service
from web.backend.services.video_preprocessing_service import get_video_preprocessing_service
from web.backend.services.overlay_service import OverlayService
from web.backend.services.projector_redirect_runtime import record_projector_request
from web.backend.services.service_diagnostics_service import get_service_diagnostics_service

# Configure logging - check if already configured by run.py
import logging.handlers


def _resolve_backend_log_file() -> str:
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(backend_dir, "..", ".."))
    log_dir = os.environ.get("NANODLNA_LOG_DIR") or os.path.join(root_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "dashboard_run.log")


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
        setup_logging(log_level="INFO", log_file=_resolve_backend_log_file())
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
service_diagnostics = get_service_diagnostics_service()
service_diagnostics.install_exception_hooks()


def _normalize_ip_candidate(value: str) -> str:
    candidate = str(value or "").strip().strip("\"'")
    if not candidate:
        return ""
    if candidate.lower().startswith("for="):
        candidate = candidate[4:].strip().strip("\"'")
    if candidate.startswith("[") and "]" in candidate:
        candidate = candidate[1:candidate.index("]")]
    elif candidate.count(":") == 1 and "." in candidate:
        candidate = candidate.rsplit(":", 1)[0]
    if candidate.startswith("::ffff:"):
        candidate = candidate[7:]
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return candidate


def _get_request_client_ip(request: Request) -> str:
    x_forwarded_for = request.headers.get("x-forwarded-for", "")
    if x_forwarded_for:
        for value in x_forwarded_for.split(","):
            candidate = _normalize_ip_candidate(value)
            if candidate and candidate.lower() != "unknown":
                return candidate

    forwarded = request.headers.get("forwarded", "")
    if forwarded:
        for entry in forwarded.split(","):
            for part in entry.split(";"):
                part = part.strip()
                if part.lower().startswith("for="):
                    candidate = _normalize_ip_candidate(part)
                    if candidate and candidate.lower() != "unknown":
                        return candidate

    x_real_ip = _normalize_ip_candidate(request.headers.get("x-real-ip", ""))
    if x_real_ip:
        return x_real_ip

    return _normalize_ip_candidate(request.client.host if request.client else "")


def _request_targets_html_document(request: Request) -> bool:
    sec_fetch_dest = (request.headers.get("sec-fetch-dest") or "").lower()
    if sec_fetch_dest in {"document", "iframe", "frame"}:
        return True

    sec_fetch_mode = (request.headers.get("sec-fetch-mode") or "").lower()
    if sec_fetch_mode == "navigate":
        return True

    accept = (request.headers.get("accept") or "").lower()
    if "text/html" in accept:
        return True

    request_path = request.url.path or ""
    return request.method in {"GET", "HEAD"} and request_path == "/" and accept in {"", "*/*"}


def _target_matches_request(request: Request, target_path: str) -> bool:
    target = urlsplit(target_path or "")
    request_path = request.url.path or ""
    target_path_value = target.path or ""
    canonical_request_path = request_path.replace("/backend-static/", "/static/", 1)
    canonical_target_path = target_path_value.replace("/backend-static/", "/static/", 1)
    request_query = request.url.query or ""
    target_query = target.query or ""
    return canonical_request_path == canonical_target_path and request_query == target_query


def _should_redirect_request(request: Request, redirect_config: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    if not redirect_config:
        return None

    if request.method not in {"GET", "HEAD"} or not _request_targets_html_document(request):
        return None

    client_ip = _get_request_client_ip(request)
    raw_rules = redirect_config.get("rules") if isinstance(redirect_config, dict) else None
    rules = raw_rules if isinstance(raw_rules, list) and raw_rules else [{
        "name": "Default projector",
        "enabled": bool(redirect_config.get("enabled")),
        "client_ip": redirect_config.get("client_ip"),
        "target_path": redirect_config.get("target_path"),
    }]
    for rule in rules:
        if not isinstance(rule, dict) or not rule.get("enabled"):
            continue
        configured_client_ip = _normalize_ip_candidate(rule.get("client_ip"))
        if not configured_client_ip or client_ip != configured_client_ip:
            continue
        target_path = str(rule.get("target_path") or "").strip()
        if not target_path or _target_matches_request(request, target_path):
            continue
        return {
            "target_path": target_path,
            "rule_name": str(rule.get("name") or "").strip() or "Projector redirect",
        }
    return None

@asynccontextmanager
async def lifespan(_app: FastAPI):
    await startup_event()
    try:
        yield
    finally:
        await shutdown_event()


# Create FastAPI app
app = FastAPI(
    title="WallDisplay Dashboard",
    description="Web dashboard for managing HDMI, DLNA, and Transcreen projectors",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def projector_redirect_middleware(request: Request, call_next):
    db = SessionLocal()
    try:
        redirect_config = OverlayService(db).get_projector_redirect_config()
    except Exception as exc:
        logger.warning("Failed to load projector redirect config: %s", exc)
        redirect_config = None
    finally:
        db.close()

    redirect_match = _should_redirect_request(request, redirect_config)
    client_ip = _get_request_client_ip(request)
    if request.method in {"GET", "HEAD"} and _request_targets_html_document(request):
        record_projector_request(
            client_ip=client_ip,
            method=request.method,
            path=request.url.path,
            query=request.url.query or "",
            matched_rule_name=redirect_match.get("rule_name") if redirect_match else "",
            redirect_target=redirect_match.get("target_path") if redirect_match else "",
            redirected=bool(redirect_match),
        )

    if redirect_match:
        logger.info(
            "Redirecting client %s from %s to %s",
            client_ip,
            request.url.path,
            redirect_match["target_path"],
        )
        return RedirectResponse(url=redirect_match["target_path"], status_code=307)

    return await call_next(request)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    GZipMiddleware,
    minimum_size=1024,
    compresslevel=6,
)

# Include routers with /api prefix
app.include_router(device_router, prefix="/api")
app.include_router(video_router, prefix="/api")
app.include_router(photo_router, prefix="/api")
app.include_router(photo_list_router)
app.include_router(streaming_router, prefix="/api")
app.include_router(renderer_router, prefix="/api")  # Add the renderer router
app.include_router(overlay_router)  # Overlay router already has /api prefix
app.include_router(projection_router)  # Projection router already has /api prefix
app.include_router(mapping_router)
app.include_router(media_library_router)
app.include_router(widget_router)
app.include_router(structured_lighting_router)
app.include_router(log_router)  # Log streaming router
app.include_router(diagnostics_router)
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
async def root(request: Request):
    db = SessionLocal()
    try:
        redirect_config = OverlayService(db).get_projector_redirect_config()
    except Exception:
        redirect_config = None
    finally:
        db.close()

    client_ip = _get_request_client_ip(request)
    redirect_match = _should_redirect_request(request, redirect_config)
    if redirect_match:
        return RedirectResponse(url=redirect_match["target_path"] or "/docs", status_code=307)

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
video_preprocessing_service = None
mask_preprocessing_service = None


def _resolve_config_path(root_dir: str, path_value: str) -> str:
    path_value = os.path.expanduser(os.path.expandvars(path_value))
    if os.path.isabs(path_value):
        return path_value
    return os.path.abspath(os.path.join(root_dir, path_value))


def _get_startup_config_files(root_dir: str, backend_dir: str) -> List[str]:
    env_config_files = os.environ.get("NANODLNA_CONFIG_FILES", "").strip()
    env_config_file = os.environ.get("NANODLNA_CONFIG_FILE", "").strip()

    if env_config_files:
        raw_paths = [item.strip() for item in env_config_files.split(os.pathsep) if item.strip()]
        candidates = [_resolve_config_path(root_dir, item) for item in raw_paths]
    elif env_config_file:
        candidates = [_resolve_config_path(root_dir, env_config_file)]
    else:
        candidates = [
            os.path.join(root_dir, "tramscreem+device_config.json"),
            os.path.join(backend_dir, "my_device_config.json"),
            os.path.join(backend_dir, "tramscreem+device_config.json"),
            os.path.join(root_dir, "my_device_config.json"),
        ]

    unique_paths = []
    for path_value in candidates:
        if path_value not in unique_paths:
            unique_paths.append(path_value)
    return unique_paths

def _is_pytest_run() -> bool:
    return "PYTEST_CURRENT_TEST" in os.environ


# Mount static files for the frontend
async def startup_event():
    global device_manager, streaming_service, streaming_registry, renderer_service, migration_adapter, video_preprocessing_service, mask_preprocessing_service
    
    logger.info("Starting WallDisplay Dashboard API")
    service_diagnostics.start_run()
    service_diagnostics.install_asyncio_exception_handler(asyncio.get_running_loop())
    await service_diagnostics.start_heartbeat()
    
    # Initialize log aggregation service
    try:
        from web.backend.log_aggregation_service import get_log_aggregation_service, setup_log_collectors
        log_service = get_log_aggregation_service()
        setup_log_collectors()
        await log_service.start()
        logger.info("Log aggregation service started")
    except Exception as e:
        logger.error(f"Failed to start log aggregation service: {e}")
    
    # Initialize services here to prevent multiple executions during imports  
    # Stop any existing streaming servers to prevent port conflicts
    streaming_service = get_twisted_streaming()
    streaming_service.stop_server()  # Explicitly stop any existing servers
    app_runtime = get_app_runtime()
    config_service = app_runtime.config_service
    streaming_registry = app_runtime.streaming_registry
    device_manager = app_runtime

    overlay_streaming_service = get_streaming_service()
    overlay_streaming_service.set_runtime(app_runtime)

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

    if _is_pytest_run():
        logger.info("Skipping preprocessing workers during pytest run.")
    else:
        try:
            video_preprocessing_service = get_video_preprocessing_service()
            video_preprocessing_service.start()
        except Exception as e:
            logger.error(f"Failed to start video preprocessing worker: {e}")

        try:
            mask_preprocessing_service = get_mask_preprocessing_service()
            mask_preprocessing_service.start()
        except Exception as e:
            logger.error(f"Failed to start mask preprocessing worker: {e}")
    
    # Create and set device service
    try:
        db_generator = get_db()
        db = next(db_generator)
        try:
            # Create a device service instance
            device_service = app_runtime.build_device_service(db)
        finally:
            db_generator.close()
    except Exception as e:
        logger.error(f"Error creating device service: {e}")
    
    if _is_pytest_run():
        logger.info("Skipping config hydration, background discovery, and renderer streaming startup during pytest run.")
    else:
        # Load devices from configuration files
        try:
            # First, check for configuration files in the project root
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            backend_dir = os.path.dirname(__file__)
            config_files = _get_startup_config_files(root_dir, backend_dir)
            
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
            
            # Initialize all devices from database into runtime memory
            # This ensures devices are immediately available even before discovery
            logger.info("Initializing devices from database into runtime inventory")
            try:
                db_devices = device_service.get_devices()
                logger.info(f"Found {len(db_devices)} devices in database")
                app_runtime.hydrate_database_devices(db_devices)
                        
            except Exception as e:
                logger.error(f"Error initializing devices from database: {e}")
                logger.error(f"Exception details: {traceback.format_exc()}")
            
            # Start runtime background services after initial device hydration.
            app_runtime.start_background_services()
            migration_adapter = app_runtime.migration_adapter
            
            # Log the number of devices in the runtime inventory
            logger.info(f"Runtime has {app_runtime.get_device_count()} devices")

            # Log all devices in the runtime inventory
            for device_name, device in app_runtime.get_device_items():
                logger.info(f"Device in runtime: {device_name}, type: {device.type}, hostname: {device.hostname}, action_url: {device.action_url}")

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

async def shutdown_event():
    global migration_adapter, video_preprocessing_service, mask_preprocessing_service
    logger.info("Shutting down WallDisplay Dashboard API")
    service_diagnostics.mark_clean_shutdown("shutdown_event")
    await service_diagnostics.stop_heartbeat()
    
    # Stop log aggregation service
    try:
        from web.backend.log_aggregation_service import get_log_aggregation_service
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
    
    # Stop runtime background services
    app_runtime = get_app_runtime()
    if app_runtime:
        app_runtime.stop_background_services()
        migration_adapter = app_runtime.migration_adapter
    if video_preprocessing_service is not None:
        try:
            video_preprocessing_service.stop()
        except Exception as e:
            logger.error(f"Failed to stop video preprocessing worker: {e}")
        finally:
            video_preprocessing_service = None
    if mask_preprocessing_service is not None:
        try:
            mask_preprocessing_service.stop()
        except Exception as e:
            logger.error(f"Failed to stop mask preprocessing worker: {e}")
        finally:
            mask_preprocessing_service = None
    
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

frontend_static_dir = os.path.join(frontend_dir, "static")


def _safe_static_file(base_dir: str, requested_path: str) -> Optional[str]:
    if not base_dir or not os.path.exists(base_dir):
        return None
    base_path = os.path.abspath(base_dir)
    candidate_path = os.path.abspath(os.path.join(base_path, requested_path))
    if os.path.commonpath([base_path, candidate_path]) != base_path:
        return None
    if not os.path.isfile(candidate_path):
        return None
    return candidate_path


@app.get("/static/{requested_path:path}", include_in_schema=False)
@app.head("/static/{requested_path:path}", include_in_schema=False)
async def serve_static_asset(requested_path: str):
    for base_dir in (frontend_static_dir, static_dir):
        candidate_path = _safe_static_file(base_dir, requested_path)
        if candidate_path:
            return FileResponse(candidate_path)
    raise HTTPException(status_code=404, detail="Static asset not found")


app.mount("/backend-static", StaticFiles(directory=static_dir), name="backend-static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web.backend.main:app", host="0.0.0.0", port=8000, reload=True)
