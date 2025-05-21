# CanvaMap

**Work in Progress**  
A lightweight, modular tile-based map viewer for `tkinter` with OpenStreetMap integration and GeoJSON support.

---

## Features

- **OSM Tiles**: Renders OpenStreetMap tiles with in-memory caching.  
- **Pan & Zoom**: Click-and-drag panning and mouse-wheel zooming.  
- **Layer Architecture**: Easily add multiple layers (`PointLayer`, `ShapeLayer`, and future `LineLayer`) that render on top of your tiles.  
- **GeoJSON Import**: `load_geojson_to_map` auto-loads `Point`, `MultiPoint`, `Polygon`, and `MultiPolygon` features into the appropriate layers.  
- **Interactivity**: Bind click callbacks to features for custom behavior.  
- **Accurate Projection**: Uses Web Mercator math (`degree2tile` / `tile2degree`) for precise lat/lon ↔ pixel alignment.

---

## Installation

```bash
pip install canvamap
# or from source:
git clone https://github.com/SiottoTamat/CanvaMap.git
cd canvamap
pip install -e .

## Quickstart

```python
import json
import tkinter as tk
from canvamap.canvas_map import CanvasMap
from canvamap.geojson_utils import load_geojson_to_map

# Callback for feature clicks
def handle_click(feature):
    print("Clicked feature:", feature)

# Initialize Tk and the map canvas
root = tk.Tk()
canvas_map = CanvasMap(root, lat=38.8813, lon=-77.0366, zoom=15)
canvas_map.pack(fill="both", expand=True)

# Load a GeoJSON file
with open("data/my_features.geojson") as f:
    geojson = json.load(f)

# Populate layers and set up click handling
load_geojson_to_map(canvas_map, geojson, on_click=handle_click)

# Run the application loop
root.mainloop()
```

---

## Overview

### `CanvasMap(master, lat, lon, zoom, provider=None, **kwargs)`

Create a map canvas. Inherits from `tkinter.Canvas`.

- **master**: Parent Tk widget.  
- **lat, lon**: Initial center coordinates (WGS84).  
- **zoom**: Initial zoom level (0–19).  
- **provider**: (Optional) Tile server base URL (default: `https://tile.openstreetmap.org`).  
- **kwargs**: Standard `tk.Canvas` options.

**Key Methods:**
- `add_layer(layer)`: Add any `MapLayer` subclass.  
- `get_canvas_bounds()`: Returns `(min_lat, min_lon, max_lat, max_lon)` of visible area.  
- `project_latlon_to_canvas(lat, lon)`: Convert geographic coordinates to pixel `(x, y)` on canvas.

### Layers

#### `PointLayer(name, features, on_click=None)`

Render GeoJSON `Point` / `MultiPoint` features as circles (and optional labels).  
- Use `add_feature(feat: dict)` to append GeoJSON Feature dicts.  
- Configurable properties: `radius`, `color`, `outline`, `label`, `opacity`, etc.  
- `on_click`: Optional callback invoked with `feat` on click.

#### `ShapeLayer(name, features, on_click=None)`

Render GeoJSON `Polygon` / `MultiPolygon` features with hole support and simulated transparency (via stipple).  
- Use `add_feature(feat: dict)` to append or flatten MultiPolygons.  
- Configurable properties: `fill`, `outline`, `opacity`.

#### `LineLayer` *(coming soon)*

Stub for `LineString` / `MultiLineString` support—implement `draw()` to render polylines.

### GeoJSON Utility

#### `load_geojson_to_map(map_widget: CanvasMap, geojson: dict, on_click: Callable[[dict], None] = None)`

- Automatically creates and populates `PointLayer` and `ShapeLayer` layers.  
- Adds layers to the map in correct draw order.  
- `on_click`: Callback bound to feature clicks.

---

## License

MIT
