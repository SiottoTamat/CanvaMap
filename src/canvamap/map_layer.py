from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Callable, Sequence
import tkinter as tk
import logging

from canvamap.feature import Feature
from canvamap.canvas_map import CanvasMap

from PIL import Image, ImageTk, ImageDraw, ImageColor

logger = logging.getLogger(__name__)


class MapLayer(ABC):
    def __init__(
        self,
        name: str,
        on_click: Callable[[Feature], None] | None = None,
        label_key: str | None = None,
    ):
        self.name = name
        self.visible = True
        self.on_click = on_click
        self.label_key = label_key
        self.features: list[Feature] = []

    @property
    def feature_count(self) -> int:
        return len(self.features)

    def add_feature(self, feat: Feature) -> None:
        """
        Append a Feature instance to this layer.
        """
        self.features.append(feat)

    def _bind_feature(
        self,
        canvas: tk.Canvas,
        tag: str,
        feature: Feature,
    ) -> None:
        if not self.on_click:
            return
        canvas.tag_bind(
            tag, "<Button-1>", lambda e, f=feature: self.on_click(f)
        )

    def _get_label_text(self, feature: Feature) -> str:
        if self.label_key:
            return feature.properties.get(self.label_key, "")
        return feature.properties.get("label", "")

    @abstractmethod
    def draw(
        self,
        canvas: CanvasMap,
        project_fn: Callable[[float, float], tuple[float, float]],
    ) -> None:
        """
        Draw this layer’s features on the canvas.
        """
        pass


class PointLayer(MapLayer):
    """
    Render point and multipoint features as circles with optional labels.
    """

    def __init__(
        self,
        name: str,
        on_click: Callable[[Feature], None] | None = None,
        label_key: str | None = None,
    ):
        super().__init__(name, on_click=on_click, label_key=label_key)

    def draw(
        self,
        canvas: CanvasMap,
        project_fn: Callable[[float, float], tuple[float, float]],
    ) -> None:
        min_lon, min_lat, max_lon, max_lat = canvas.get_canvas_bounds()

        for feat in self.features:
            # Each feat.geoms is a list of PointSequence
            for seq in feat.geoms:
                x_right = None
                y_top = None
                feature_tag = f"{self.name}_{feat.sequence_index}"

                for lon, lat in seq:
                    if not (
                        min_lon <= lon <= max_lon and min_lat <= lat <= max_lat
                    ):
                        continue
                    x, y = project_fn(lat, lon)
                    if x_right is None or x > x_right:
                        x_right, y_top = x, y
                    r = feat.properties.get("radius", 4)
                    color = feat.properties.get("color", "red")
                    outline = feat.properties.get("outline", "")
                    canvas.create_oval(
                        x - r,
                        y - r,
                        x + r,
                        y + r,
                        fill=color,
                        outline=outline,
                        tags=(self.name, feature_tag),
                    )
                    self._bind_feature(canvas, feature_tag, feat)

                # draw label at rightmost point
                label_text = self._get_label_text(feat)
                if x_right is not None:
                    if label_text:
                        from canvamap.map_layer import LabelAnnotation

                        label = LabelAnnotation(
                            text=label_text,
                            offset=feat.properties.get(
                                "label_offset", (r + 2, -r - 2)
                            ),
                            font=feat.properties.get(
                                "label_font", ("Arial", 10)
                            ),
                            text_color=feat.properties.get(
                                "label_color", "black"
                            ),
                            bg_color=feat.properties.get(
                                "label_bg", "lightgray"
                            ),
                            border_color=feat.properties.get(
                                "label_border_color", "gray"
                            ),
                            border_width=feat.properties.get(
                                "label_border_width", 1
                            ),
                        )
                        label.draw(
                            canvas,
                            x_right,
                            y_top,
                            tags=(self.name, feature_tag),
                        )


class ShapeLayer(MapLayer):
    """
    Render polygon and multipolygon features,
    respecting holes via image overlays.
    """

    def __init__(
        self,
        name: str,
        on_click: Callable[[Feature], None] | None = None,
        label_key: str | None = None,
    ):
        super().__init__(name, on_click=on_click, label_key=label_key)

    def draw(
        self,
        canvas: CanvasMap,
        project_fn: Callable[[float, float], tuple[float, float]],
    ) -> None:
        min_lon, min_lat, max_lon, max_lat = canvas.get_canvas_bounds()

        for feat in self.features:
            # Build a flat list of LinearRings for both Polygon & MultiPolygon:
            #
            # - Polygon:    feat.geoms == List[Ring]
            # - MultiPolygon: feat.geoms == List[Polygon],
            # where Polygon == List[Ring]
            first = feat.geoms[0]
            if first and isinstance(first[0], tuple):
                # Single Polygon: each element of geoms is already a LinearRing
                rings = feat.geoms
            else:
                # MultiPolygon: geoms is list of polygons;
                # flatten out all rings
                rings = [ring for polygon in feat.geoms for ring in polygon]

            # Eachring is always List[ (lon,lat), … ]
            lats = [lat for ring in rings for lon, lat in ring]
            lons = [lon for ring in rings for lon, lat in ring]
            if (
                max(lats) < min_lat
                or min(lats) > max_lat
                or max(lons) < min_lon
                or min(lons) > max_lon
            ):
                continue

            feature_tag = f"{self.name}_{feat.sequence_index}"
            # Draw holes via image overlay
            from canvamap.map_layer import draw_feature_with_holes

            image_ids = draw_feature_with_holes(
                canvas, project_fn, feat, feature_tag
            )
            if isinstance(image_ids, list):
                for image_id in image_ids:
                    self._bind_feature(canvas, image_id, feat)
            else:
                self._bind_feature(canvas, image_ids, feat)

            # Draw outline
            outline = feat.properties.get("outline", "")
            width = feat.properties.get("width", 2)
            points = [
                [project_fn(lat, lon) for lon, lat in ring] for ring in rings
            ]
            if outline:
                for ring in points:
                    canvas.create_line(
                        *ring,
                        fill=outline,
                        width=width,
                        tags=(self.name, feature_tag),
                    )
            flat_points = [point for ring in points for point in ring]
            right_x_point = max(flat_points, key=lambda x: x[0])

            # Label at first ring's first vertex
            label_text = self._get_label_text(feat)
            if label_text:
                x, y = right_x_point
                from canvamap.map_layer import LabelAnnotation

                label = LabelAnnotation(
                    text=label_text,
                    offset=feat.properties.get("label_offset", (0, 0)),
                    font=feat.properties.get("label_font", ("Arial", 10)),
                    text_color=feat.properties.get("label_color", "black"),
                    bg_color=feat.properties.get("label_bg", "lightgray"),
                    border_color=feat.properties.get(
                        "label_border_color", "gray"
                    ),
                    border_width=feat.properties.get("label_border_width", 1),
                )
                label.draw(canvas, x, y, tags=(self.name, feature_tag))


class LineLayer(MapLayer):
    """
    Render LineString and MultiLineString features
    as polylines with optional labels.
    """

    def __init__(
        self,
        name: str,
        on_click: Callable[[Feature], None] | None = None,
        label_key: str | None = None,
    ):
        super().__init__(name, on_click=on_click, label_key=label_key)

    def draw(
        self,
        canvas: CanvasMap,
        project_fn: Callable[[float, float], tuple[float, float]],
    ) -> None:
        # Get view bounds
        min_lon, min_lat, max_lon, max_lat = canvas.get_canvas_bounds()
        for feat in self.features:
            for seq in feat.geoms:
                # Build sequence of projected points
                pts = []
                for lon, lat in seq:
                    if not (
                        min_lon <= lon <= max_lon and min_lat <= lat <= max_lat
                    ):
                        continue
                    x, y = project_fn(lat, lon)
                    pts.extend([x, y])
                if len(pts) < 4:
                    continue  # need at least two points to draw a line

                feature_tag = f"{self.name}_{feat.sequence_index}"

                props = feat.properties
                style = {
                    "fill": props.get("fill", "black"),
                    "width": props.get("width", 1),
                    "dash": tuple(props["dash"]) if "dash" in props else None,
                    "arrow": props.get("arrow", "none"),
                    "capstyle": props.get("capstyle", "round"),
                    "joinstyle": props.get("joinstyle", "round"),
                    "smooth": props.get("smooth", False),
                    "splinesteps": props.get("splinesteps", 12),
                }
                canvas_opts = {k: v for k, v in style.items() if v is not None}

                # Draw polyline
                canvas.create_line(
                    *pts,
                    **canvas_opts,
                    tags=(self.name, feature_tag),
                )
                self._bind_feature(canvas, feature_tag, feat)

                # Optional label at the last point
                label_text = self._get_label_text(feat)
                if label_text:
                    x_label, y_label = pts[-2], pts[-1]
                    from canvamap.map_layer import LabelAnnotation

                    label = LabelAnnotation(
                        text=label_text,
                        offset=feat.properties.get("label_offset", (0, 0)),
                        font=feat.properties.get("label_font", ("Arial", 10)),
                        text_color=feat.properties.get("label_color", "black"),
                        bg_color=feat.properties.get("label_bg", "lightgray"),
                        border_color=feat.properties.get(
                            "label_border_color", "gray"
                        ),
                        border_width=feat.properties.get(
                            "label_border_width", 1
                        ),
                    )
                    label.draw(
                        canvas,
                        x_label,
                        y_label,
                        tags=(self.name, feature_tag),
                    )


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
        self,
        canvas: CanvasMap,
        x: float,
        y: float,
        tags: Sequence[str] = (),
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


def draw_feature_with_holes(
    canvas, project_fn, feat: Feature, tag, opacity=0.5
):

    coords = feat.geoms

    if feat.geometry_type == "MultiPolygon":
        polygons = coords
    else:  # "Polygon"
        polygons = [coords]

    image_ids = []
    for polygon_rings in polygons:
        # Project each ring
        all_xy = []
        for ring in polygon_rings:
            pts = [project_fn(lat, lon) for lon, lat in ring]
            all_xy.append(pts)

        # Compute overlay size
        xs = [x for ring in all_xy for x, y in ring]
        ys = [y for ring in all_xy for x, y in ring]
        min_x, max_x = int(min(xs)), int(max(xs))
        min_y, max_y = int(min(ys)), int(max(ys))
        w, h = max_x - min_x, max_y - min_y

        # Build mask: first ring = fill, subsequent = holes
        mask = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(mask)
        draw.polygon([(x - min_x, y - min_y) for x, y in all_xy[0]], fill=255)
        for hole in all_xy[1:]:
            draw.polygon([(x - min_x, y - min_y) for x, y in hole], fill=0)

        # Fill color + alpha
        fill_color = feat.properties.get("fill", "red")
        alpha = int(feat.properties.get("alpha", opacity) * 255)
        color_img = Image.new(
            "RGBA", (w, h), (*ImageColor.getrgb(fill_color), alpha)
        )

        # Composite
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        overlay.paste(color_img, (0, 0), mask)

        # Turn into a Tk image and draw on canvas
        tk_img = ImageTk.PhotoImage(overlay)
        img_id = canvas.create_image(
            min_x, min_y, image=tk_img, anchor="nw", tags=(tag,)
        )
        canvas._image_refs.append(tk_img)
        image_ids.append(img_id)

    # Return either a single id or list of ids
    return image_ids[0] if len(image_ids) == 1 else image_ids
