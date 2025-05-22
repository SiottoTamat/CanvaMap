from abc import ABC, abstractmethod
from typing import Callable, Sequence
import tkinter as tk
import logging


from canvamap.canvas_map import CanvasMap

logger = logging.getLogger(__name__)


class MapLayer(ABC):
    def __init__(
        self,
        name: str,
        on_click: Callable[[dict], None] | None = None,
        label_key: str | None = None,
    ):
        self.name = name
        self.visible = True
        self.on_click = on_click
        self.label_key = label_key

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

    def __init__(
        self,
        name: str,
        on_click=None,
        label_key=None,
    ):
        super().__init__(name, on_click=on_click)
        self._feat_counter = 0
        self.features = []
        self.label_key = label_key

    def add_feature(self, feat: dict):
        """
        Accepts either a Point or MultiPoint Feature dict, normalizes it,
        and appends one or more normalized features to self.features.
        """
        geom = feat.get("geometry", {})
        geom_type = geom.get("type")

        if geom_type == "Point":
            self.features.append(feat)

        elif geom_type == "MultiPoint":
            # Split into individual Point features
            for coords in geom.get("coordinates", []):
                self.features.append(feat)

        else:
            logger.warning(
                "PointLayer.add_feature: unsupported geometry '%s'", geom_type
            )

    def draw(
        self, canvas, project_fn: Callable[[float, float], tuple[float, float]]
    ) -> None:

        bbox = canvas.get_canvas_bounds()
        visible = [
            f
            for f in self.features
            if bbox[0] <= f["geometry"]["coordinates"][1] <= bbox[2]
            and bbox[1] <= f["geometry"]["coordinates"][0] <= bbox[3]
        ]

        for feat in visible:
            feature_tag = f"{self.name}_{self._feat_counter}"
            self._feat_counter += 1

            x, y = project_fn(
                feat["geometry"]["coordinates"][1],
                feat["geometry"]["coordinates"][0],
            )
            # Draw a small circle at each point
            r = feat.get("radius", 4)
            color = feat.get("color", "red")
            outline = feat.get("outline", "")
            point = canvas.create_oval(
                x - r, y - r, x + r, y + r, fill=color, outline=outline
            )
            self._bind_feature(canvas, point, feat)

            label_text = feat.get(self.label_key) if self.label_key else None
            if label_text:
                label = LabelAnnotation(
                    text=label_text,
                    offset=feat.get("label_offset", (r + 2, -r - 2)),
                    font=feat.get("label_font", ("Arial", 10)),
                    text_color=feat.get("label_color", "black"),
                    bg_color=feat.get("label_bg", "lightgray"),
                    border_color=feat.get("label_border_color", "gray"),
                    border_width=feat.get("label_border_width", 1),
                )
                label.draw(canvas, x, y, tags=(self.name, feature_tag))


class ShapeLayer(MapLayer):

    def __init__(
        self,
        name: str,
        on_click=None,
        label_key=None,
    ):
        super().__init__(name, on_click=on_click)
        self.name = name
        self.features = []
        self.label_key = label_key

    def add_feature(self, feat: dict):
        geom = feat["geometry"]
        geom_type = geom["type"]

        if geom_type == "Polygon":
            self.features.append(feat)

        elif geom_type == "MultiPolygon":
            # split into individual polygons
            for polygon_coords in geom["coordinates"]:
                self.add_feature(feat)

        else:
            # optional: warn about unexpected geometry
            logger.warning(
                f"ShapeLayer.add_feature: unsupported geometry '{geom_type}'"
            )

    def draw(
        self,
        canvas: CanvasMap,
        project_fn: Callable[[float, float], tuple[float, float]],
    ):

        min_lat, min_lon, max_lat, max_lon = canvas.get_canvas_bounds()

        visible: list[dict] = []
        for feat in self.features:
            # pull all the rings (outer + holes)
            outer_shapes = feat["geometry"]["coordinates"]

            lats = [lat for shape in outer_shapes for lon, lat in shape]
            lons = [lon for shape in outer_shapes for lon, lat in shape]

            if (
                max(lats) >= min_lat
                and min(lats) <= max_lat
                and max(lons) >= min_lon
                and min(lons) <= max_lon
            ):
                visible.append(feat)

        for feat in visible:

            points = []
            for shape in feat["geometry"]["coordinates"]:
                if points:
                    points.extend([None, None])
                for y, x in shape:
                    px, py = project_fn(x, y)
                    points.extend([px, py])

            fill = feat.get("fill", "red")
            outline = feat.get("outline", "black")
            alpha = feat.get("alpha", 0.5)
            if alpha < 1.0:
                # gray12=~12% opaque, gray25=25%, gray50=50%, gray75=75%
                stipple = f"gray{int(alpha*100)}"
            else:
                stipple = ""

            shape = canvas.create_polygon(
                *points,
                fill=fill,
                outline=outline,
                stipple=stipple,
                tags=(self.name,),
            )
            self._bind_feature(canvas, shape, feat)

            label_text = feat.get(self.label_key) if self.label_key else None
            if label_text:
                label = LabelAnnotation(
                    text=label_text,
                    offset=feat.get("label_offset", (0, 0)),
                    font=feat.get("label_font", ("Arial", 10)),
                    text_color=feat.get("label_color", "black"),
                    bg_color=feat.get("label_bg", "lightgray"),
                    border_color=feat.get("label_border_color", "gray"),
                    border_width=feat.get("label_border_width", 1),
                )

                label.draw(
                    canvas, points[0], points[1], tags=(self.name, shape)
                )


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


class LabelAnnotation:
    def __init__(
        self,
        text: str,
        offset: tuple[int, int] = (0, 0),
        text_color: str = "black",
        font: tuple[str, int] = ("Arial", 10),
        bg_color: str = "lightgray",
        border_color: str = "gray",
        border_width: int = 1,
    ):
        self.text = text
        self.offset = offset
        self.text_color = text_color
        self.font = font
        self.bg_color = bg_color
        self.border_color = border_color
        self.border_width = border_width

    def draw(
        self, canvas: CanvasMap, x: float, y: float, tags: Sequence[str] = ()
    ) -> None:
        dx, dy = self.offset
        tx, ty = x + dx, y + dy
        text_id = canvas.create_text(
            tx,
            ty,
            text=self.text,
            anchor="nw",
            fill=self.text_color,
            font=self.font,
            tags=tags,
        )
        bbox = canvas.bbox(text_id)
        rect_id = canvas.create_rectangle(
            bbox,
            fill=self.bg_color,
            outline=self.border_color,
            width=self.border_width,
            tags=tags,
        )
        canvas.tag_lower(rect_id, text_id)
