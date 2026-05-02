# nano-dlna MCP Servers

## DesktopHut MCP

Run:

```bash
python run_desktophut_mcp_server.py
```

Config example: `mcp-desktophut-config.json`.

Key tools:

- `list_desktophut_categories()`
- `preview_desktophut_category(category, limit=20)`
- `search_desktophut_videos(query, category=null, limit=20)`
- `download_desktophut_category(category, max_videos=10)`
- `download_desktophut_search(query, max_videos=10)`
- `index_video_directory(directory, category)`
- `download_and_index_desktophut_search(query, library_category)`
- `download_fish_and_create_wall_scene(clients, scene_name="Fish Walls")`

Safe defaults bound downloads to 10 videos / 3 pages unless caller raises limits.

Example agent request:

```json
{
  "query": "fish",
  "library_category": "fish",
  "max_videos": 12,
  "output_root": "~/Desktop/Archive"
}
```

## Scene Control MCP

Run:

```bash
python run_scene_control_mcp_server.py
```

Config example: `mcp-scene-control-config.json`.

Key tools:

- `list_mapping_scenes()`
- `create_mapping_scene(name, canvas_width, canvas_height)`
- `add_polygon_mask(scene_id, name, points)`
- `update_scene_groups(scene_id, groups)`
- `create_scene_rank(name, scene_ids, gap_px=0)`
- `create_scene_control_preset(name, scene_ids, ...)`
- `create_scene_across_clients(name, clients, group_template)`
- `create_all_walls_scene_from_media(name, clients, background_video_ids, pattern_layers)`

Example all-walls scene:

```json
{
  "name": "Fish Walls",
  "clients": [
    {"name": "left-wall", "canvas_width": 1920, "canvas_height": 1080},
    {"name": "center-wall", "canvas_width": 1920, "canvas_height": 1080},
    {"name": "right-wall", "canvas_width": 1920, "canvas_height": 1080}
  ],
  "background_video_ids": [1, 2, 3],
  "pattern_layers": [
    {"name": "water caustics", "color_a": "#5bc0eb", "color_b": "#0b3954", "z_index": 10},
    {"name": "bubble shimmer", "color_a": "#bfd7ea", "color_b": "#087e8b", "z_index": 20}
  ],
  "use_media_list": true
}
```

This creates one mapping scene per wall, full-canvas masks, fish background group(s), pattern fill layers, rank metadata, and scene-control preset.
