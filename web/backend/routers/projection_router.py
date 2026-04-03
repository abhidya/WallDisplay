from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Query
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
import os
import uuid
import json
import re
from datetime import datetime
from PIL import Image
import numpy as np

from database.database import get_db
from services.mask_analyzer import MaskAnalyzer
from services.projection_service import ProjectionService
from schemas.projection import (
    ProjectionConfigCreate,
    ProjectionConfigUpdate,
    ProjectionConfigResponse,
    Zone,
    ZoneTransform,
    ZoneAssignment,
    MaskData
)

router = APIRouter(prefix="/api/projection", tags=["projection"])


def _animation_lists_path() -> str:
    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    storage_dir = os.path.join(backend_root, "uploads", "projection")
    os.makedirs(storage_dir, exist_ok=True)
    return os.path.join(storage_dir, "animation_lists.json")


def _read_animation_lists() -> List[Dict]:
    path = _animation_lists_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return []
    return payload if isinstance(payload, list) else []


def _write_animation_lists(items: List[Dict]) -> None:
    path = _animation_lists_path()
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(items, handle, indent=2, sort_keys=True)

ANIMATION_LIBRARY = [
    {
        "id": "neural_noise",
        "name": "Neural Noise",
        "description": "Flowing neural network patterns",
        "dataInputs": ["weather"],
        "thumbnail": "🧠",
        "source_codepen_id": "vYwgrWv",
    },
    {
        "id": "moving_clouds",
        "name": "Moving Clouds",
        "description": "Drifting cloud layers",
        "dataInputs": ["weather"],
        "thumbnail": "☁️",
        "source_codepen_id": "NWeqOVw",
    },
    {
        "id": "koi_fish",
        "name": "Koi Fish",
        "description": "Two koi gliding through bright water ripples",
        "dataInputs": ["weather"],
        "thumbnail": "🐟",
    },
    {
        "id": "swimming_fish",
        "name": "Swimming Fish",
        "description": "A school of simple fish drifting across a deep blue tank",
        "dataInputs": ["transit"],
        "thumbnail": "🐠",
    },
    {
        "id": "blob_fish",
        "name": "Blob Fish",
        "description": "Soft blobby fish drifting through a moody aquarium glow",
        "dataInputs": ["weather"],
        "thumbnail": "🫧",
    },
    {
        "id": "fish_pond",
        "name": "Fish Pond",
        "description": "A layered pond scene with plants, bubbles, and warm fish passes",
        "dataInputs": ["transit"],
        "thumbnail": "🐡",
    },
    {
        "id": "koi_pond_8bit",
        "name": "Koi Pond 8-bit",
        "description": "A pixel-art koi pond background with looping fish and shimmering water",
        "dataInputs": ["weather"],
        "thumbnail": "🎏",
    },
    {
        "id": "pokedex",
        "name": "Pokedex",
        "description": "A classic red pokedex layout with Psyduck in the main display",
        "dataInputs": [],
        "thumbnail": "📟",
    },
    {
        "id": "moon_view",
        "name": "Moon View",
        "description": "A cinematic moonlit shader scene with water, sky glow, and drifting stars",
        "dataInputs": [],
        "thumbnail": "🌕",
    },
    {
        "id": "meduses",
        "name": "Meduses",
        "description": "Glowing jellyfish drifting through a deep blue Shadertoy-style volumetric scene",
        "dataInputs": [],
        "thumbnail": "🪼",
    },
    {
        "id": "kelp_forest",
        "name": "Kelp Forest",
        "description": "A dense underwater kelp forest with fish, bubbles, caustics, and cinematic god rays",
        "dataInputs": [],
        "thumbnail": "🌿",
    },
    {
        "id": "train_up_in_the_cloud_sea",
        "name": "Train Up In The Cloud Sea",
        "description": "A drifting pixel-train crossing a bridge through layered sunset cloud seas",
        "dataInputs": [],
        "thumbnail": "🚂",
    },
    {
        "id": "cyber_fuji_2020",
        "name": "Cyber Fuji 2020",
        "description": "A retro neon mountain scene imported from Shadertoy Wt33Wf",
        "dataInputs": [],
        "thumbnail": "🌄",
    },
    {
        "id": "whale_raymarching",
        "name": "Whale Raymarching",
        "description": "A raymarched whale scene imported from Shadertoy t3X3Wf",
        "dataInputs": [],
        "thumbnail": "🐋",
    },
    {
        "id": "fractal_land",
        "name": "Fractal Land",
        "description": "A stylized fractal cartoon flythrough imported from Shadertoy XsBXWt",
        "dataInputs": [],
        "thumbnail": "🌈",
    },
    {
        "id": "swarming_anchoveta",
        "name": "Swarming Anchoveta",
        "description": "A multipass fish-swarm scene imported from Shadertoy mtSGDt",
        "dataInputs": [],
        "thumbnail": "🐟",
    },
    {
        "id": "spectrum_bars",
        "name": "Spectrum Bars",
        "description": "Animated spectrum visualization",
        "dataInputs": ["transit"],
        "thumbnail": "📊",
    },
    {
        "id": "webgl_flowers",
        "name": "WebGL Flowers",
        "description": "Blooming flower patterns",
        "dataInputs": ["weather", "transit"],
        "thumbnail": "🌸",
        "source_codepen_id": "poOMpzx",
    },
    {
        "id": "rainstorm",
        "name": "Rainstorm",
        "description": "Weather-driven rain effects",
        "dataInputs": ["weather"],
        "thumbnail": "🌧️",
        "source_codepen_id": "bNGExzZ",
    },
    {
        "id": "pride_spectrum",
        "name": "Pride Spectrum",
        "description": "Rainbow spectrum waves",
        "dataInputs": ["weather", "transit"],
        "thumbnail": "🌈",
        "source_codepen_id": "MKEpqW",
    },
]

ANIMATION_LIBRARY.extend([
    {
        "id": "star_psf",
        "name": "Star PSF",
        "description": "An imported Shadertoy star point-spread scene from XdsGWs",
        "dataInputs": [],
        "thumbnail": "🌌",
    },
    {
        "id": "alien_tech",
        "name": "Alien Tech",
        "description": "An imported Shadertoy scene from XtX3zj",
        "dataInputs": [],
        "thumbnail": "🌌",
    },
    {
        "id": "maze_automata",
        "name": "maze automata",
        "description": "An imported Shadertoy scene from lsccDB",
        "dataInputs": [],
        "thumbnail": "🌌",
    },
    {
        "id": "outer_space_planet",
        "name": "[Planet] Outer Space",
        "description": "An imported Shadertoy scene from 4llBD8",
        "dataInputs": [],
        "thumbnail": "🪐",
    },
    {
        "id": "alien_tunnel",
        "name": "Alien Tunnel",
        "description": "An imported Shadertoy scene from X3ySRc",
        "dataInputs": [],
        "thumbnail": "👾",
    },
    {
        "id": "alien_waterworld",
        "name": "Alien Waterworld",
        "description": "An imported Shadertoy scene from WtXyW4",
        "dataInputs": [],
        "thumbnail": "🌊",
    },
    {
        "id": "alien_space_jockey",
        "name": "Alien Space Jockey",
        "description": "An imported Shadertoy scene from mdB3Rh",
        "dataInputs": [],
        "thumbnail": "🚀",
    },
    {
        "id": "alien_core",
        "name": "Alien Core",
        "description": "An imported Shadertoy scene from 4tcXRr",
        "dataInputs": [],
        "thumbnail": "💠",
    },
    {
        "id": "volcanic",
        "name": "Volcanic",
        "description": "An imported Shadertoy scene from XsX3RB",
        "dataInputs": [],
        "thumbnail": "🌋",
    },
    {
        "id": "kepler_256o",
        "name": "Kepler 256o",
        "description": "An imported Shadertoy scene from XsjGRd",
        "dataInputs": [],
        "thumbnail": "🪐",
    },
    {
        "id": "night_skyline_buffered",
        "name": "Night Skyline Buffered",
        "description": "An imported Shadertoy scene from ws2yRh",
        "dataInputs": [],
        "thumbnail": "🌃",
    },
    {
        "id": "vaporwave_0001",
        "name": "Vaporwave__0001",
        "description": "An imported Shadertoy scene from wtSXD1",
        "dataInputs": [],
        "thumbnail": "🌆",
    },
    {
        "id": "anime_background_3",
        "name": "90s Anime Background 3",
        "description": "An imported Shadertoy scene from fsGXW1",
        "dataInputs": [],
        "thumbnail": "🌇",
    },
    {
        "id": "grid_and_lines",
        "name": "grid and lines",
        "description": "An imported Shadertoy scene from lcBcDw",
        "dataInputs": [],
        "thumbnail": "📐",
    },
    {
        "id": "anime_background",
        "name": "90s Anime Background",
        "description": "An imported Shadertoy scene from fdyXzz",
        "dataInputs": [],
        "thumbnail": "🎞️",
    },
    {
        "id": "unstable_universe",
        "name": "Unstable Universe",
        "description": "An imported Shadertoy scene from wtlfz8",
        "dataInputs": [],
        "thumbnail": "🌀",
    },
    {
        "id": "lensing",
        "name": "Lensing",
        "description": "An imported Shadertoy scene from MtByRh",
        "dataInputs": [],
        "thumbnail": "🔭",
    },
    {
        "id": "kerr_newman_black_hole",
        "name": "Kerr Newman Black Hole",
        "description": "An imported Shadertoy scene from wXdfzj",
        "dataInputs": [],
        "thumbnail": "🕳️",
    },
    {
        "id": "descent_3d",
        "name": "Descent 3D",
        "description": "An imported Shadertoy scene from wdfGW4",
        "dataInputs": [],
        "thumbnail": "🛰️",
    },
    {
        "id": "singularity_381",
        "name": "Singularity [381]",
        "description": "An imported Shadertoy scene from 3csSWB",
        "dataInputs": [],
        "thumbnail": "✨",
    },
    {
        "id": "gargantua_hdr_bloom",
        "name": "Gargantua With HDR Bloom",
        "description": "An imported Shadertoy scene from lstSRS",
        "dataInputs": [],
        "thumbnail": "🕳️",
    },
    {
        "id": "mandelbrot_orbit_traps",
        "name": "Mandelbrot - orbit traps",
        "description": "An imported Shadertoy scene from ldf3DN",
        "dataInputs": [],
        "thumbnail": "🧮",
    },
    {
        "id": "steel_lattice",
        "name": "Steel Lattice",
        "description": "An imported Shadertoy scene from 4tlSWl",
        "dataInputs": [],
        "thumbnail": "🧱",
    },
    {
        "id": "black_hole_accretion_disk",
        "name": "Black hole with accretion disk",
        "description": "An imported Shadertoy scene from tsBXW3",
        "dataInputs": [],
        "thumbnail": "🌌",
    },
    {
        "id": "simple_greeble_split4",
        "name": "Simple Greeble - Split4",
        "description": "An imported Shadertoy scene from 4tXcRl",
        "dataInputs": [],
        "thumbnail": "🧩",
    },
    {
        "id": "windows_95",
        "name": "Windows 95",
        "description": "An imported Shadertoy scene from XstXR2",
        "dataInputs": [],
        "thumbnail": "💾",
    },
])

CODEPEN_IMPORTS = {
    item["source_codepen_id"]: item
    for item in ANIMATION_LIBRARY
    if item.get("source_codepen_id")
}

# In-memory storage for masks and temporary sessions
projection_sessions = {}
uploaded_masks = {}

@router.post("/mask")
async def upload_mask(
    masks: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """Upload multiple projection masks - each becomes one zone"""
    try:
        # Ensure masks is a list (handle single file upload)
        if not isinstance(masks, list):
            masks = [masks]
            
        # Validate file types
        for mask in masks:
            if not mask.filename.lower().endswith('.png'):
                raise HTTPException(status_code=400, detail=f"Only PNG files are supported. Invalid file: {mask.filename}")
        
        # Create uploads directory if it doesn't exist
        upload_dir = os.path.join(os.path.dirname(__file__), "..", "uploads", "masks")
        os.makedirs(upload_dir, exist_ok=True)
        
        # Process all masks
        all_zones = []
        mask_id = str(uuid.uuid4())  # Single ID for this batch of masks
        
        for index, mask in enumerate(masks):
            # Generate unique filename for each mask
            filename = f"{mask_id}_{index}.png"
            filepath = os.path.join(upload_dir, filename)
            
            # Save file
            content = await mask.read()
            with open(filepath, "wb") as f:
                f.write(content)
            
            # Analyze mask to find white regions
            analyzer = MaskAnalyzer()
            detected_zones = analyzer.analyze_mask(filepath)
            
            # Add source mask info to each detected zone
            for zone in detected_zones:
                zone["sourceMask"] = mask.filename
            all_zones.extend(detected_zones)
        
        # Store mask info
        mask_info = {
            "id": mask_id,
            "name": f"{len(masks)} masks uploaded",
            "filepath": upload_dir,  # Directory containing all masks
            "width": max(zone["bounds"]["width"] for zone in all_zones) if all_zones else 0,
            "height": max(zone["bounds"]["height"] for zone in all_zones) if all_zones else 0,
            "zones": all_zones,
            "uploaded_at": datetime.utcnow().isoformat()
        }
        
        uploaded_masks[mask_id] = mask_info
        
        return mask_info
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/masks/{mask_id}")
async def get_mask(mask_id: str, db: Session = Depends(get_db)):
    """Get mask information by ID"""
    if mask_id not in uploaded_masks:
        raise HTTPException(status_code=404, detail="Mask not found")
    
    return uploaded_masks[mask_id]

@router.get("/masks/{session_id}/image")
async def get_mask_image(session_id: str):
    """Get the mask image file for a session - returns composite of all masks"""
    # First check if this is a session ID
    if session_id in projection_sessions:
        session = projection_sessions[session_id]
        mask_id = session.get("maskId")
        if mask_id and mask_id in uploaded_masks:
            upload_dir = uploaded_masks[mask_id]["filepath"]
            mask_info = uploaded_masks[mask_id]
            
            # Create composite mask with all uploaded mask files
            composite = None
            # Iterate through all possible mask files (not zones)
            mask_index = 0
            while True:
                mask_file = f"{mask_id}_{mask_index}.png"
                filepath = os.path.join(upload_dir, mask_file)
                
                if os.path.exists(filepath):
                    with Image.open(filepath) as opened:
                        img = opened.convert('RGBA')
                    if composite is None:
                        composite = Image.new('RGBA', img.size, (0, 0, 0, 255))
                    
                    # Paste white areas from this mask onto composite
                    composite.paste(img, (0, 0), img)
                    mask_index += 1
                else:
                    # No more mask files
                    break
            
            if composite:
                # Save composite temporarily
                composite_path = os.path.join(upload_dir, f"{mask_id}_composite.png")
                composite.save(composite_path)
                return FileResponse(composite_path, media_type="image/png")
    
    # Try direct mask ID lookup
    if session_id in uploaded_masks:
        upload_dir = uploaded_masks[session_id]["filepath"]
        mask_file = f"{session_id}_0.png"
        filepath = os.path.join(upload_dir, mask_file)
        
        if os.path.exists(filepath):
            return FileResponse(filepath, media_type="image/png")
    
    raise HTTPException(status_code=404, detail="Mask image not found")

@router.get("/animations")
async def get_animations():
    """Get list of available animations"""
    return {"animations": ANIMATION_LIBRARY}


@router.get("/animation-lists")
async def get_animation_lists():
    """Get saved animation lists"""
    return {"animation_lists": _read_animation_lists()}


@router.get("/animation-lists/{list_id}")
async def get_animation_list(list_id: str):
    """Get a saved animation list"""
    items = _read_animation_lists()
    animation_list = next((item for item in items if item.get("id") == list_id), None)
    if not animation_list:
        raise HTTPException(status_code=404, detail="Animation list not found")
    return animation_list


@router.post("/animation-lists")
async def create_animation_list(data: Dict[str, object]):
    """Create an animation list"""
    name = str(data.get("name") or "").strip()
    animation_ids = [
        animation_id for animation_id in (data.get("animation_ids") or [])
        if isinstance(animation_id, str) and animation_id
    ]
    if not name:
        raise HTTPException(status_code=400, detail="Animation list name is required")
    if not animation_ids:
        raise HTTPException(status_code=400, detail="Animation list must include at least one animation")

    valid_ids = {item["id"] for item in ANIMATION_LIBRARY}
    invalid_ids = [animation_id for animation_id in animation_ids if animation_id not in valid_ids]
    if invalid_ids:
        raise HTTPException(status_code=400, detail=f"Unknown animation ids: {', '.join(invalid_ids)}")

    items = _read_animation_lists()
    now = datetime.utcnow().isoformat()
    entry = {
        "id": uuid.uuid4().hex,
        "name": name,
        "animation_ids": animation_ids,
        "auto_advance_seconds": max(3, int(data.get("auto_advance_seconds") or 12)),
        "shuffle": bool(data.get("shuffle")),
        "created_at": now,
        "updated_at": now,
    }
    items.append(entry)
    _write_animation_lists(items)
    return entry


@router.put("/animation-lists/{list_id}")
async def update_animation_list(list_id: str, data: Dict[str, object]):
    """Update an animation list"""
    items = _read_animation_lists()
    index = next((idx for idx, item in enumerate(items) if item.get("id") == list_id), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Animation list not found")

    current = items[index]
    name = str(data.get("name") or current.get("name") or "").strip()
    animation_ids = data.get("animation_ids")
    if animation_ids is None:
        animation_ids = current.get("animation_ids") or []
    animation_ids = [
        animation_id for animation_id in animation_ids
        if isinstance(animation_id, str) and animation_id
    ]
    if not name:
        raise HTTPException(status_code=400, detail="Animation list name is required")
    if not animation_ids:
        raise HTTPException(status_code=400, detail="Animation list must include at least one animation")

    valid_ids = {item["id"] for item in ANIMATION_LIBRARY}
    invalid_ids = [animation_id for animation_id in animation_ids if animation_id not in valid_ids]
    if invalid_ids:
        raise HTTPException(status_code=400, detail=f"Unknown animation ids: {', '.join(invalid_ids)}")

    updated = {
        **current,
        "name": name,
        "animation_ids": animation_ids,
        "auto_advance_seconds": max(3, int(data.get("auto_advance_seconds") or current.get("auto_advance_seconds") or 12)),
        "shuffle": bool(data.get("shuffle", current.get("shuffle", False))),
        "updated_at": datetime.utcnow().isoformat(),
    }
    items[index] = updated
    _write_animation_lists(items)
    return updated


@router.delete("/animation-lists/{list_id}")
async def delete_animation_list(list_id: str):
    """Delete an animation list"""
    items = _read_animation_lists()
    updated = [item for item in items if item.get("id") != list_id]
    if len(updated) == len(items):
        raise HTTPException(status_code=404, detail="Animation list not found")
    _write_animation_lists(updated)
    return {"deleted": True, "id": list_id}

@router.post("/animations/import")
async def import_codepen(
    data: Dict[str, str],
    db: Session = Depends(get_db)
):
    """Import animation from CodePen URL"""
    url = data.get("url", "")
    
    if not url or "codepen.io" not in url:
        raise HTTPException(status_code=400, detail="Invalid CodePen URL")

    match = re.search(r"codepen\.io/[^/]+/(?:pen|full|details)/([A-Za-z0-9]+)", url)
    if not match:
        raise HTTPException(status_code=400, detail="Could not parse CodePen pen id from URL")

    pen_id = match.group(1)
    animation = CODEPEN_IMPORTS.get(pen_id)
    if not animation:
        supported_ids = ", ".join(sorted(CODEPEN_IMPORTS.keys()))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported CodePen import. Supported curated pen ids: {supported_ids}",
        )

    return {
        **animation,
        "imported": True,
        "source": url,
    }

@router.post("/sessions/create")
async def create_session(
    session_data: Dict,
    db: Session = Depends(get_db)
):
    """Create a new projection session"""
    try:
        session_id = str(uuid.uuid4())
        
        # Validate mask exists
        mask_id = session_data.get("maskId")
        if mask_id not in uploaded_masks:
            raise HTTPException(status_code=400, detail="Invalid mask ID")
        
        # Store session
        session = {
            "id": session_id,
            "maskId": mask_id,
            "mask": uploaded_masks[mask_id],
            "zones": session_data.get("zones", []),
            "created_at": datetime.utcnow().isoformat()
        }
        
        projection_sessions[session_id] = session
        
        return {"id": session_id, "status": "created"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get projection session data"""
    if session_id not in projection_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return projection_sessions[session_id]

@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Delete a projection session"""
    if session_id not in projection_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    del projection_sessions[session_id]
    return {"status": "deleted"}

# Configuration endpoints (database-backed)
@router.post("/configs", response_model=ProjectionConfigResponse)
async def create_projection_config(
    config: ProjectionConfigCreate,
    db: Session = Depends(get_db)
):
    """Create a new projection configuration"""
    try:
        service = ProjectionService(db)
        return service.create_config(config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/configs", response_model=List[ProjectionConfigResponse])
async def list_projection_configs(
    db: Session = Depends(get_db)
):
    """List all projection configurations"""
    service = ProjectionService(db)
    return service.get_configs()

@router.get("/configs/{config_id}", response_model=ProjectionConfigResponse)
async def get_projection_config(
    config_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific projection configuration"""
    service = ProjectionService(db)
    config = service.get_config_by_id(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return config

@router.put("/configs/{config_id}", response_model=ProjectionConfigResponse)
async def update_projection_config(
    config_id: int,
    update_data: ProjectionConfigUpdate,
    db: Session = Depends(get_db)
):
    """Update a projection configuration"""
    service = ProjectionService(db)
    config = service.update_config(config_id, update_data)
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return config

@router.delete("/configs/{config_id}")
async def delete_projection_config(
    config_id: int,
    db: Session = Depends(get_db)
):
    """Delete a projection configuration"""
    service = ProjectionService(db)
    if not service.delete_config(config_id):
        raise HTTPException(status_code=404, detail="Configuration not found")
    return {"status": "deleted"}

@router.post("/configs/{config_id}/duplicate", response_model=ProjectionConfigResponse)
async def duplicate_projection_config(
    config_id: int,
    new_name: str = Query(..., description="Name for the duplicated configuration"),
    db: Session = Depends(get_db)
):
    """Duplicate a projection configuration"""
    service = ProjectionService(db)
    config = service.duplicate_config(config_id, new_name)
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return config

@router.post("/configs/{config_id}/launch")
async def launch_from_config(
    config_id: int,
    db: Session = Depends(get_db)
):
    """Create a session from a saved configuration"""
    service = ProjectionService(db)
    config = service.get_config_by_id(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    # Create session from config
    session_id = str(uuid.uuid4())
    session = {
        "id": session_id,
        "config_id": config_id,
        "maskId": config.mask_data.get("id"),
        "mask": config.mask_data,
        "zones": config.zones,
        "created_at": datetime.utcnow().isoformat()
    }
    
    projection_sessions[session_id] = session
    return {"id": session_id, "status": "created"}

@router.get("/data/weather")
async def get_weather_data():
    """Get current weather data for animations"""
    # Mock data for now. Real implementation would fetch from weather API
    return {
        "temperature": 22,
        "humidity": 65,
        "windSpeed": 15,
        "windDirection": 180,
        "conditions": "partly_cloudy",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/data/transit")
async def get_transit_data():
    """Get current transit data for animations"""
    # Mock data for now. Real implementation would fetch from transit API
    return {
        "nextArrival": "5 minutes",
        "routeName": "Blue Line",
        "destination": "Downtown",
        "timestamp": datetime.utcnow().isoformat()
    }
