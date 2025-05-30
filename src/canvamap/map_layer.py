from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Callable
import tkinter as tk
import logging

from canvamap.feature import Feature
from canvamap.canvas_map import CanvasMap
from canvamap.drawing_utils import LabelAnnotation, draw_feature_with_holes


logger = logging.getLogger(__name__)


class MapLayer(ABC):
    def __init__(
        self,
        name: str,
        on_click_feature: Callable[[Feature], None] | None = None,
        on_right_click_feature: Callable[[Feature], None] | None = None,
        on_double_click_feature: Callable[[Feature], None] | None = None,
        on_middle_click_feature: Callable[[Feature], None] | None = None,
        on_mouse_enter_feature: Callable[[Feature], None] | None = None,
        on_mouse_leave_feature: Callable[[Feature], None] | None = None,
        label_key: str | None = None,
    ):
        self.name = name
        self.visible = True
        # feature callbacks
        self.on_click_feature = on_click_feature
        self.on_right_click_feature = on_right_click_feature
        self.on_double_click_feature = on_double_click_feature
        self.on_middle_click_feature = on_middle_click_feature
        self.on_mouse_enter_feature = on_mouse_enter_feature
        self.on_mouse_leave_feature = on_mouse_leave_feature

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
        if self.on_click_feature:
            canvas.tag_bind(
                tag,
                "<Button-1>",
                lambda e, f=feature: self.on_click_feature(f),
            )
        if self.on_right_click_feature:
            canvas.tag_bind(
                tag,
                "<Button-3>",
                lambda e, f=feature: self.on_right_click_feature(f),
            )
        if self.on_double_click_feature:
            canvas.tag_bind(
                tag,
                "<Double-Button-1>",
                lambda e, f=feature: self.on_double_click_feature(f),
            )
        if self.on_middle_click_feature:
            canvas.tag_bind(
                tag,
                "<Button-2>",
                lambda e, f=feature: self.on_middle_click_feature(f),
            )
        if self.on_mouse_enter_feature:
            canvas.tag_bind(
                tag,
                "<Enter>",
                lambda e, f=feature: self.on_mouse_enter_feature(f),
            )
        if self.on_mouse_leave_feature:
            canvas.tag_bind(
                tag,
                "<Leave>",
                lambda e, f=feature: self.on_mouse_leave_feature(f),
            )

    def _get_label_text(self, feature: Feature) -> str:
        if self.label_key:
            return feature.properties.get(self.label_key, "")
        return feature.properties.get("label", "")

    def _feature_tag(self, feature: Feature) -> str:
        return f"feature:{self.name}:{feature.sequence_index}"

    def set_visible(self, visible: bool) -> None:
        self.visible = visible

    def clear_features(self) -> None:
        """Remove all features from the layer."""
        self.features.clear()

    def remove_features(
        self,
        feature_id: str | None = None,
        geometry_type: str | None = None,
        property_filter: dict | None = None,
    ) -> int:
        """
        Remove features from the layer matching the given filters.

        Args:
            feature_id: Remove the feature with this exact ID.
            geometry_type: Remove all features of this geometry type.
            property_filter: Dict of key-value pairs that must match
                            exactly in the feature's properties.

        Returns:
            Number of features removed.
        """
        original_count = len(self.features)

        def matches(f: Feature) -> bool:
            if feature_id and f.id != feature_id:
                return False
            if geometry_type and f.geometry_type != geometry_type:
                return False
            if property_filter:
                for key, val in property_filter.items():
                    if f.properties.get(key) != val:
                        return False
            return True

        self.features = [f for f in self.features if not matches(f)]
        return original_count - len(self.features)

    def remove_features_and_redraw(
        self,
        canvas: CanvasMap,
        *,
        feature_id: str | None = None,
        geometry_type: str | None = None,
        property_filter: dict | None = None,
    ) -> int:
        """
        Remove matching features and delete their canvas representations.

        Args:
            canvas: The CanvasMap instance this layer is rendered on.
            feature_id, geometry_type, property_filter: See remove_features().

        Returns:
            Number of features removed.
        """
        removed = self.remove_features(
            feature_id=feature_id,
            geometry_type=geometry_type,
            property_filter=property_filter,
        )
        canvas.delete(f"layer:{self.name}")
        return removed

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
        super().__init__(name, on_click_feature=on_click, label_key=label_key)

    def draw(
        self,
        canvas: CanvasMap,
        project_fn: Callable[[float, float], tuple[float, float]],
    ) -> None:
        if not self.visible:
            return

        min_lon, min_lat, max_lon, max_lat = canvas.get_canvas_bounds()

        for feat in self.features:
            # Each feat.geoms is a list of PointSequence
            for seq in feat.geoms:
                x_right = None
                y_top = None
                feature_tag = self._feature_tag(feat)

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
                        tags=(self.name, feature_tag, "feature"),
                    )
                    self._bind_feature(canvas, feature_tag, feat)

                # draw label at rightmost point
                label_text = self._get_label_text(feat)
                if x_right is not None:
                    if label_text:

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
                            tags=(f"layer:{self.name}", feature_tag, "label"),
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
        super().__init__(name, on_click_feature=on_click, label_key=label_key)

    def draw(
        self,
        canvas: CanvasMap,
        project_fn: Callable[[float, float], tuple[float, float]],
    ) -> None:
        if not self.visible:
            return

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

            feature_tag = self._feature_tag(feat)

            # Draw holes via image overlay
            for image_id in draw_feature_with_holes(
                canvas, project_fn, feat, feature_tag
            ):
                self._bind_feature(canvas, image_id, feat)

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
                        tags=(f"layer:{self.name}", feature_tag, "feature"),
                    )

            # Label at first ring's first vertex
            label_text = self._get_label_text(feat)
            if label_text:
                flat_points = [point for ring in points for point in ring]
                right_x_point = max(flat_points, key=lambda x: x[0])
                x, y = right_x_point

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
                label.draw(
                    canvas,
                    x,
                    y,
                    tags=(f"layer:{self.name}", feature_tag, "label"),
                )


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
        super().__init__(name, on_click_feature=on_click, label_key=label_key)

    def draw(
        self,
        canvas: CanvasMap,
        project_fn: Callable[[float, float], tuple[float, float]],
    ) -> None:
        if not self.visible:
            return

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

                feature_tag = self._feature_tag(feat)

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
                    tags=(f"layer:{self.name}", feature_tag, "feature"),
                )
                self._bind_feature(canvas, feature_tag, feat)

                # Optional label at the last point
                label_text = self._get_label_text(feat)
                if label_text:
                    x_label, y_label = pts[-2], pts[-1]

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
                        tags=(f"layer:{self.name}", feature_tag, "label"),
                    )
