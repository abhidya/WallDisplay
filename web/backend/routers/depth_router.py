from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Response
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
import tempfile
import os
import io
import json
import uuid

# Try to import depth processing modules
# These are wrapped in try-except to allow the app to start without these dependencies
try:
    from core.depth_processing import DepthLoader, DepthSegmenter, DepthVisualizer
    DEPTH_PROCESSING_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Depth processing modules not available: {e}")
    DEPTH_PROCESSING_AVAILABLE = False
    # Define placeholder classes to avoid reference errors
    class DepthLoader:
        @staticmethod
        def load_depth_map(*args, **kwargs): return None
        @staticmethod
        def normalize_depth_map(*args, **kwargs): return None
        @staticmethod
        def visualize_depth_map(*args, **kwargs): return None
    
    class DepthSegmenter:
        @staticmethod
        def kmeans_segmentation(*args, **kwargs): return None, []
        @staticmethod
        def threshold_segmentation(*args, **kwargs): return None
        @staticmethod
        def depth_band_segmentation(*args, **kwargs): return None
        @staticmethod
        def extract_binary_mask(*args, **kwargs): return None
        @staticmethod
        def clean_binary_mask(*args, **kwargs): return None
    
    class DepthVisualizer:
        @staticmethod
        def export_image(*args, **kwargs): return b""
        @staticmethod
        def create_overlay(*args, **kwargs): return None

# Configure logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/depth",
    tags=["depth"],
    responses={404: {"description": "Not found"}},
)

# Pydantic models for request/response
class SegmentationRequest(BaseModel):
    method: str = "kmeans"  # kmeans, threshold, bands
    n_clusters: int = 5
    thresholds: Optional[List[float]] = None
    n_bands: Optional[int] = None

class SegmentationResponse(BaseModel):
    success: bool
    message: str
    segment_count: int = 0
    segments: List[int] = []
    depth_id: Optional[str] = None

class MaskExportRequest(BaseModel):
    segment_ids: List[int]
    clean_mask: bool = True
    min_area: int = 100
    kernel_size: int = 3

class LidarSurfaceRequest(BaseModel):
    name: str
    video_path: Optional[str] = None
    segment_id: int
    position: Dict[str, float] = {"x": 0, "y": 0}
    scale: Dict[str, float] = {"width": 1, "height": 1}
    rotation: float = 0

class ProjectionConfig(BaseModel):
    device_id: int
    surfaces: List[LidarSurfaceRequest]
    depth_id: str

class ProjectionResponse(BaseModel):
    success: bool
    message: str
    page_url: Optional[str] = None
    config_id: Optional[str] = None

# Store uploaded depth maps temporarily
temp_depth_maps = {}

# Store projection configurations
projection_configs = {}

@router.post("/upload", response_model=SegmentationResponse)
async def upload_depth_map(
    file: UploadFile = File(...),
    normalize: bool = Form(True)
):
    """
    Upload a depth map file (PNG, TIFF, EXR)
    """
    # Check file extension
    filename = file.filename
    if not filename:
        raise HTTPException(status_code=400, detail="File has no name")
    
    # Get file extension
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.exr']:
        raise HTTPException(status_code=400, detail=f"Unsupported file format: {ext}")
    
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp:
            # Save the uploaded file
            content = await file.read()
            temp.write(content)
            temp_path = temp.name
        
        # Load the depth map
        depth_map = DepthLoader.load_depth_map(temp_path)
        if depth_map is None:
            raise HTTPException(status_code=400, detail="Failed to load depth map")
        
        # Normalize if requested
        if normalize:
            depth_map = DepthLoader.normalize_depth_map(depth_map)
            if depth_map is None:
                raise HTTPException(status_code=400, detail="Failed to normalize depth map")
        
        # Generate a unique ID for this depth map
        depth_id = str(uuid.uuid4())
        
        # Store the depth map in memory
        temp_depth_maps[depth_id] = {
            'depth_map': depth_map,
            'segmentation': None,
            'filename': filename,
            'temp_path': temp_path
        }
        
        return {
            "success": True,
            "message": f"Depth map uploaded successfully: {filename}",
            "depth_id": depth_id
        }
        
    except Exception as e:
        logger.error(f"Error uploading depth map: {e}")
        raise HTTPException(status_code=500, detail=f"Error uploading depth map: {str(e)}")

@router.get("/preview/{depth_id}")
async def preview_depth_map(depth_id: str):
    """
    Get a preview of the depth map
    """
    if depth_id not in temp_depth_maps:
        raise HTTPException(status_code=404, detail="Depth map not found")
    
    depth_map = temp_depth_maps[depth_id]['depth_map']
    
    # Convert to visualization
    visualization = DepthLoader.visualize_depth_map(depth_map)
    
    # Convert to bytes
    preview_bytes = DepthVisualizer.export_image(visualization)
    
    return StreamingResponse(io.BytesIO(preview_bytes), media_type="image/png")

@router.post("/segment/{depth_id}", response_model=SegmentationResponse)
async def segment_depth_map(depth_id: str, request: SegmentationRequest):
    """
    Segment a depth map using the specified method
    """
    if depth_id not in temp_depth_maps:
        raise HTTPException(status_code=404, detail="Depth map not found")
    
    depth_map = temp_depth_maps[depth_id]['depth_map']
    
    try:
        segmentation = None
        centers = []
        
        if request.method == "kmeans":
            # KMeans segmentation
            segmentation, centers = DepthSegmenter.kmeans_segmentation(
                depth_map, 
                n_clusters=request.n_clusters
            )
            # Convert centers to Python list
            centers = centers.tolist() if hasattr(centers, 'tolist') else list(centers)
            
        elif request.method == "threshold":
            # Threshold segmentation
            if not request.thresholds:
                raise HTTPException(status_code=400, detail="Thresholds required for threshold segmentation")
            
            segmentation = DepthSegmenter.threshold_segmentation(
                depth_map,
                thresholds=request.thresholds
            )
            
        elif request.method == "bands":
            # Depth band segmentation
            n_bands = request.n_bands or 5
            segmentation = DepthSegmenter.depth_band_segmentation(
                depth_map,
                n_bands=n_bands
            )
            
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported segmentation method: {request.method}")
        
        if segmentation is None:
            raise HTTPException(status_code=500, detail="Segmentation failed")
        
        # Store the segmentation
        temp_depth_maps[depth_id]['segmentation'] = segmentation
        
        # Get unique segment IDs
        segments = sorted(list(map(int, set(segmentation.flatten()))))
        
        return {
            "success": True,
            "message": f"Depth map segmented using {request.method}",
            "segment_count": len(segments),
            "segments": segments,
            "centers": centers,
            "depth_id": depth_id
        }
        
    except Exception as e:
        logger.error(f"Error segmenting depth map: {e}")
        raise HTTPException(status_code=500, detail=f"Error segmenting depth map: {str(e)}")

@router.get("/segmentation_preview/{depth_id}")
async def preview_segmentation(depth_id: str, alpha: float = 0.5):
    """
    Get a preview of the segmentation as an overlay on the depth map
    """
    if depth_id not in temp_depth_maps:
        raise HTTPException(status_code=404, detail="Depth map not found")
    
    data = temp_depth_maps[depth_id]
    if data['segmentation'] is None:
        raise HTTPException(status_code=400, detail="Depth map not segmented yet")
    
    # Get the depth map and segmentation
    depth_map = data['depth_map']
    segmentation = data['segmentation']
    
    # Convert depth map to visualization
    depth_vis = DepthLoader.visualize_depth_map(depth_map)
    
    # Create an overlay
    overlay = DepthVisualizer.create_overlay(
        depth_vis,
        segmentation,
        alpha=alpha
    )
    
    # Convert to bytes
    preview_bytes = DepthVisualizer.export_image(overlay)
    
    return StreamingResponse(io.BytesIO(preview_bytes), media_type="image/png")

@router.post("/export_masks/{depth_id}")
async def export_masks(depth_id: str, request: MaskExportRequest):
    """
    Export binary masks for the specified segments
    """
    if depth_id not in temp_depth_maps:
        raise HTTPException(status_code=404, detail="Depth map not found")
    
    data = temp_depth_maps[depth_id]
    if data['segmentation'] is None:
        raise HTTPException(status_code=400, detail="Depth map not segmented yet")
    
    # Get the segmentation
    segmentation = data['segmentation']
    
    # Create a ZIP file with the masks
    import zipfile
    from io import BytesIO
    
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for segment_id in request.segment_ids:
            # Extract binary mask
            binary_mask = DepthSegmenter.extract_binary_mask(segmentation, segment_id)
            
            # Clean the mask if requested
            if request.clean_mask:
                binary_mask = DepthSegmenter.clean_binary_mask(
                    binary_mask,
                    min_area=request.min_area,
                    kernel_size=request.kernel_size
                )
            
            # Export the mask
            mask_bytes = DepthVisualizer.export_image(binary_mask)
            
            # Add to ZIP file
            zip_file.writestr(f"mask_{segment_id}.png", mask_bytes)
        
        # Add a metadata file
        metadata = {
            "filename": data['filename'],
            "segments": request.segment_ids,
            "cleaned": request.clean_mask,
            "min_area": request.min_area,
            "kernel_size": request.kernel_size
        }
        zip_file.writestr("metadata.json", json.dumps(metadata, indent=2))
    
    # Reset buffer position
    zip_buffer.seek(0)
    
    # Create a filename for the ZIP
    base_name = os.path.splitext(data['filename'])[0]
    zip_filename = f"{base_name}_masks.zip"
    
    # Return the ZIP file
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
    )

@router.delete("/{depth_id}")
async def delete_depth_map(depth_id: str):
    """
    Delete a depth map and its temporary files
    """
    if depth_id not in temp_depth_maps:
        raise HTTPException(status_code=404, detail="Depth map not found")
    
    # Get the temporary file path
    temp_path = temp_depth_maps[depth_id]['temp_path']
    
    # Delete the temporary file
    try:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    except Exception as e:
        logger.error(f"Error deleting temporary file: {e}")
    
    # Remove from memory
    del temp_depth_maps[depth_id]
    
    return {"success": True, "message": "Depth map deleted"}

@router.get("/mask/{depth_id}/{segment_id}")
async def get_mask(depth_id: str, segment_id: int, clean: bool = True, min_area: int = 100, kernel_size: int = 3):
    """
    Get a binary mask for a specific segment
    """
    if depth_id not in temp_depth_maps:
        raise HTTPException(status_code=404, detail="Depth map not found")
    
    data = temp_depth_maps[depth_id]
    if data['segmentation'] is None:
        raise HTTPException(status_code=400, detail="Depth map not segmented yet")
    
    # Get the segmentation
    segmentation = data['segmentation']
    
    # Extract binary mask
    binary_mask = DepthSegmenter.extract_binary_mask(segmentation, segment_id)
    
    # Clean the mask if requested
    if clean:
        binary_mask = DepthSegmenter.clean_binary_mask(
            binary_mask,
            min_area=min_area,
            kernel_size=kernel_size
        )
    
    # Export the mask
    mask_bytes = DepthVisualizer.export_image(binary_mask)
    
    return StreamingResponse(io.BytesIO(mask_bytes), media_type="image/png")

@router.post("/projection/create", response_model=ProjectionResponse)
async def create_projection(config: ProjectionConfig):
    """
    Create a new projection mapping configuration using LiDAR/depth data
    """
    try:
        # Check if depth map exists
        if config.depth_id not in temp_depth_maps:
            raise HTTPException(status_code=404, detail="Depth map not found")
        
        data = temp_depth_maps[config.depth_id]
        if data['segmentation'] is None:
            raise HTTPException(status_code=400, detail="Depth map not segmented yet")
        
        # Generate a unique ID for this projection configuration
        config_id = str(uuid.uuid4())
        
        # Generate HTML for the projection
        html = generate_projection_html(config)
        
        # Save the HTML to a file
        html_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core", "templates", "projections")
        os.makedirs(html_dir, exist_ok=True)
        
        html_path = os.path.join(html_dir, f"projection_{config_id}.html")
        with open(html_path, "w") as f:
            f.write(html)
        
        # Store the configuration
        projection_configs[config_id] = {
            "config": config.dict(),
            "html_path": html_path,
            "url": f"/depth/projection/{config_id}"
        }
        
        # Start casting to the device if requested
        if config.device_id:
            # Import device service
            from services.device_service import DeviceService
            from services.app_runtime import get_app_runtime
            from database.database import get_db
            
            # Get database session
            db = next(get_db())
            
            # Create device service
            device_service = get_app_runtime().build_device_service(db)
            
            # Create a projection URL
            base_url = "http://localhost:8000"  # This should be configurable
            projection_url = f"{base_url}/api/depth/projection/{config_id}"
            
            # Cast to the device (this will need to be adjusted based on how your casting works)
            success = device_service.play_video(config.device_id, projection_url, loop=True)
            
            if not success:
                logger.warning(f"Failed to cast projection to device {config.device_id}")
        
        return {
            "success": True,
            "message": "Projection created successfully",
            "page_url": f"/api/depth/projection/{config_id}",
            "config_id": config_id
        }
    
    except Exception as e:
        logger.error(f"Error creating projection: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating projection: {str(e)}")

@router.get("/projection/{config_id}")
async def get_projection(config_id: str):
    """
    Get a projection HTML page
    """
    if config_id not in projection_configs:
        raise HTTPException(status_code=404, detail="Projection configuration not found")
    
    config = projection_configs[config_id]
    html_path = config["html_path"]
    
    if not os.path.exists(html_path):
        raise HTTPException(status_code=404, detail="Projection HTML file not found")
    
    with open(html_path, "r") as f:
        html = f.read()
    
    return Response(content=html, media_type="text/html")

@router.delete("/projection/{config_id}")
async def delete_projection(config_id: str):
    """
    Delete a projection configuration
    """
    if config_id not in projection_configs:
        raise HTTPException(status_code=404, detail="Projection configuration not found")
    
    config = projection_configs[config_id]
    html_path = config["html_path"]
    
    # Delete the HTML file
    try:
        if os.path.exists(html_path):
            os.unlink(html_path)
    except Exception as e:
        logger.error(f"Error deleting projection HTML file: {e}")
    
    # Remove from memory
    del projection_configs[config_id]
    
    return {"success": True, "message": "Projection deleted"}

def generate_projection_html(config: ProjectionConfig) -> str:
    """
    Generate HTML for a projection mapping configuration
    
    Args:
        config: Projection configuration
        
    Returns:
        HTML string
    """
    # Get depth map data
    depth_id = config.depth_id
    data = temp_depth_maps[depth_id]
    segmentation = data['segmentation']
    
    # Create masks for each surface
    surface_masks = {}
    for surface in config.surfaces:
        # Extract binary mask
        binary_mask = DepthSegmenter.extract_binary_mask(segmentation, surface.segment_id)
        
        # Clean the mask
        binary_mask = DepthSegmenter.clean_binary_mask(binary_mask, min_area=100, kernel_size=3)
        
        # Convert to base64 for embedding in HTML
        import base64
        mask_bytes = DepthVisualizer.export_image(binary_mask)
        mask_base64 = base64.b64encode(mask_bytes).decode("utf-8")
        
        # Store the mask
        surface_masks[surface.name] = mask_base64
    
    # Generate HTML
    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Projection Mapping</title>
    <style>
        body, html {
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            overflow: hidden;
            background-color: #000;
        }
        
        .container {
            position: relative;
            width: 100%;
            height: 100%;
        }
        
        .surface {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            overflow: hidden;
        }
        
        .surface video {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        .surface .mask {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
            mix-blend-mode: multiply;
        }
    </style>
</head>
<body>
    <div class="container">
"""
    
    # Add surfaces
    for surface in config.surfaces:
        # Add surface div
        html += f"""
        <div class="surface" id="surface_{surface.name}" style="transform: translate({surface.position.get('x', 0)}px, {surface.position.get('y', 0)}px) rotate({surface.rotation}deg) scale({surface.scale.get('width', 1)}, {surface.scale.get('height', 1)});">
"""
        
        # Add video if provided
        if surface.video_path:
            html += f"""
            <video autoplay loop muted playsinline>
                <source src="{surface.video_path}" type="video/mp4">
                Your browser does not support the video tag.
            </video>
"""
        
        # Add mask
        mask_base64 = surface_masks.get(surface.name, "")
        if mask_base64:
            html += f"""
            <img class="mask" src="data:image/png;base64,{mask_base64}" alt="Mask">
"""
        
        # Close surface div
        html += """
        </div>
"""
    
    # Close HTML
    html += """
    </div>
    
    <script>
        // Auto-refresh the page if connection is lost
        function checkConnection() {
            fetch('/health')
                .then(response => {
                    if (!response.ok) {
                        location.reload();
                    }
                })
                .catch(() => {
                    // Reload after a short delay if connection fails
                    setTimeout(() => {
                        location.reload();
                    }, 5000);
                });
        }
        
        // Check connection every 30 seconds
        setInterval(checkConnection, 30000);
        
        // Initialize videos
        document.addEventListener('DOMContentLoaded', function() {
            const videos = document.querySelectorAll('video');
            videos.forEach(video => {
                video.play().catch(error => {
                    console.error('Error playing video:', error);
                });
            });
        });
    </script>
</body>
</html>
"""
    
    return html
