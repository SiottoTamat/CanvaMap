from abc import ABC, abstractmethod
from typing import Callable
import tkinter as tk

from canvamap.canvas_map import CanvasMap


class MapLayer(ABC):
    def __init__(
        self, name: str, on_click: Callable[[dict], None] | None = None
    ):
        self.name = name
        self.visible = True
        self.on_click = on_click

    @abstractmethod
    def draw(
        self,
        canvas,
        project_fn: Callable[[float, float], tuple[float, float]],
    ) -> None:
        """Draw the layer on the given canvas using a projection function."""
        pass

    def _bind_feature(
        self,
        canvas: tk.Canvas,
        item_id: int,
        feature: dict,
    ):

        if not self.on_click:
            return
        canvas.tag_bind(
            item_id, "<Button-1>", lambda e, f=feature: self.on_click(f)
        )


# --------------------------------------------------------------------------
# Layer implementations
# --------------------------------------------------------------------------


class PointLayer(MapLayer):
    """
    A layer of point features, each may have:
      - 'lat', 'lon'           (required)
      - 'label': str           (optional text to show)
      - 'radius': int          (optional circle radius)
      - 'label_offset': (dx,dy)  (optional tuple to nudge text)
      - 'color': str           (optional fill color)
      - 'alpha': 0<float<1     (optional transparency)
    """

    def __init__(self, name: str, features: list[dict], on_click=None):
        super().__init__(name, on_click=on_click)
        self.features = features
        self.name = name

    def add_feature(self, feat: dict):
        geom = feat["geometry"]
        if geom["type"] == "Point":
            self.features.append(
                {
                    "lat": geom["coordinates"][1],
                    "lon": geom["coordinates"][0],
                    **feat.get("properties", {}),
                }
            )
        else:
            for lon, lat in geom["coordinates"]:
                self.features.append(
                    {
                        "lat": lat,
                        "lon": lon,
                        **feat.get("properties", {}),
                    }
                )

    def draw(
        self, canvas, project_fn: Callable[[float, float], tuple[float, float]]
    ) -> None:

        bbox = canvas.get_canvas_bounds()
        visible = [
            f
            for f in self.features
            if bbox[0] <= f["lat"] <= bbox[2]
            and bbox[1] <= f["lon"] <= bbox[3]
        ]

        for feat in visible:
            x, y = project_fn(feat["lat"], feat["lon"])
            # Draw a small circle at each point
            r = feat.get("radius", 4)
            color = feat.get("color", "red")
            outline = feat.get("outline", "")
            point = canvas.create_oval(
                x - r, y - r, x + r, y + r, fill=color, outline=outline
            )
            self._bind_feature(canvas, point, feat)

            label = feat.get("label", "")
            if label:
                dx, dy = feat.get("label_offset", (r + 2, -r - 2))
                text_id = canvas.create_text(
                    x + dx,
                    y + dy,
                    text=label,
                    anchor="nw",  # so (x+dx,y+dy) is top‐left of text
                    fill=feat.get("label_color", "black"),
                    font=feat.get("label_font", ("Arial", 10)),
                )
                # optional offset so text doesn’t overlap the point
                bbox = canvas.bbox(text_id)
                rect_id = canvas.create_rectangle(
                    bbox,
                    fill=feat.get("label_bg", "lightgray"),
                    outline=feat.get("label_border_color", "gray"),
                    width=feat.get("label_border_width", 1),
                    tags="label_bg",
                )
                canvas.tag_lower(rect_id, text_id)


class ShapeLayer(MapLayer):

    def __init__(self, name: str, features: list[dict], on_click=None):
        super().__init__(name, on_click=on_click)
        self.features = features
        self.name = name

    def add_feature(self, feat: dict):
        geom = feat["geometry"]
        if geom["type"] == "Polygon":
            self.features.append(feat)
        else:
            for coords in geom["coordinates"]:
                self.add_feature(
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": coords,
                        },
                        "properties": feat.get("properties", {}),
                    }
                )

    def draw(
        self,
        canvas: CanvasMap,
        project_fn: Callable[[float, float], tuple[float, float]],
    ):

        # here implement visibility
        visible = self.features

        for feat in visible:

            outer_ring = feat["geometry"]["coordinates"][0]
            all_points = [[project_fn(p[1], p[0]) for p in outer_ring]]
            if len(feat["geometry"]["coordinates"]) > 1:
                all_points.append(
                    [
                        project_fn(p[1], p[0])
                        for p in feat["geometry"]["coordinates"][1]
                    ]
                )

            for pts in all_points:
                fill = feat["properties"].get("fill", "red")
                outline = feat["properties"].get("outline", "black")
                alpha = feat["properties"].get("alpha", 0.5)
                if alpha < 1.0:
                    # gray12=~12% opaque, gray25=25%, gray50=50%, gray75=75%
                    stipple = f"gray{int(alpha*100)}"
                else:
                    stipple = ""

                shape = canvas.create_polygon(
                    *pts,
                    fill=fill,
                    outline=outline,
                    stipple=stipple,
                    tags=(self.name,),
                )
                self._bind_feature(canvas, shape, feat)


class Linelayer(MapLayer):
    """
    Layer for rendering LineString / MultiLineString features.

    TODO: implement `draw()` to convert features into canvas lines.
    """

    @abstractmethod
    def draw(self, canvas, project_fn):
        """
        Draw the line features on the canvas.
        Raise NotImplementedError until this is implemented.
        """
        raise NotImplementedError("LineLayer.draw() is not implemented yet.")
