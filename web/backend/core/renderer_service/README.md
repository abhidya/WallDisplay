# Renderer Service

The Renderer Service is a component of the WallDisplay Dashboard that provides a unified interface for managing scene projections on different types of displays.

## Features

- Abstract sender interface for different display technologies (DLNA, AirPlay, direct)
- Scene management with configurable templates and data
- Projector configuration with sender type and target information
- Health monitoring and automatic recovery
- RESTful API for control and status

## Configuration

The Renderer Service is configured using a JSON file. By default, it looks for a configuration file at `web/backend/config/renderer_config.json`. A typical configuration looks like:

```json
{
  "senders": {
    "direct": {
      "enabled": true,
      "default_display": 0
    },
    "dlna": {
      "enabled": true,
      "stream_port": 8000
    },
    "airplay": {
      "enabled": true,
      "script_path": "auto"
    }
  },
  "scenes": {
    "frontdoor-v1": {
      "template": "overlay_frontdoor/index.html",
      "data": {
        "video_file": "door6.mp4"
      }
    },
    "kitchen-v1": {
      "template": "kitchendoorv2.mp4",
      "data": {
        "loop": true
      }
    }
  },
  "projectors": {
    "proj-hallway": {
      "sender": "airplay",
      "target_name": "Hallway TV"
    },
    "proj-kitchen": {
      "sender": "dlna",
      "target_name": "Kitchen_TV_DLNA"
    }
  }
}
```

## API Endpoints

The Renderer Service exposes the following API endpoints:

### Start a Renderer

```http
POST /renderer/start
{
  "scene": "scene-id",
  "projector": "projector-id",
  "options": {
    "loop": true,
    "timeout": 300
  }
}
```

### Stop a Renderer

```http
POST /renderer/stop
{
  "projector": "projector-id"
}
```

### Get Renderer Status

```http
GET /renderer/status?projector=projector-id
```

### List All Renderers

```http
GET /renderer/list
```

## Usage Examples

### Start a Renderer

```bash
curl -X POST http://localhost:8000/renderer/start \
  -H "Content-Type: application/json" \
  -d '{"scene":"kitchen-v1","projector":"proj-kitchen"}'
```

### Stop a Renderer

```bash
curl -X POST http://localhost:8000/renderer/stop \
  -H "Content-Type: application/json" \
  -d '{"projector":"proj-kitchen"}'
```

### Get Renderer Status

```bash
curl -X GET http://localhost:8000/renderer/status?projector=proj-kitchen
```

### List All Renderers

```bash
curl -X GET http://localhost:8000/renderer/list
```

## Adding a New Sender

To add a new sender for a different display technology:

1. Create a new class that inherits from `Sender` in `sender/`
2. Implement all the required methods: `connect`, `disconnect`, `send_content`, `is_connected`, and `get_status`
3. Add the sender to the `senders` dictionary in `service.py`
4. Add configuration for the new sender type in the config file

## Testing

Unit tests for the Renderer Service are located in `tests/test_renderer_service.py`. Run the tests with:

```bash
cd web/backend
python -m unittest tests/test_renderer_service.py
``` 
