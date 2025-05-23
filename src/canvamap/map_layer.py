from abc import ABC, abstractmethod
from typing import Callable, Sequence
import tkinter as tk
import logging
from PIL import Image, ImageTk, ImageDraw, ImageColor


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
        self.features = []

    @property
    def feature_count(self):
        return len(self.features)

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

    def add_feature(self, feat: dict):
        self.features.append(feat)


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
        self.label_key = label_key

    def draw(
        self, canvas, project_fn: Callable[[float, float], tuple[float, float]]
    ) -> None:

        min_lon, min_lat, max_lon, max_lat = canvas.get_canvas_bounds()
        # feature_tag = f"{self.name}_{self._feat_counter}"

        for feat in self.features:
            # for Multipoint label position
            x_right = None
            y_top = None
            feature_tag = f"{self.name}_{self.feature_count}"
            all_not_visible = True

            for point in feat["geometry"]["coordinates"]:
                if len(point) != 2:
                    pass
                visible = (
                    min_lon <= point[0] <= max_lon
                    and min_lat <= point[1] <= max_lat
                )
                if not visible:
                    continue
                all_not_visible = False
                x, y = project_fn(
                    point[1],
                    point[0],
                )
                if x_right is None or x > x_right:
                    x_right = x
                    y_top = y

                # Draw a small circle at each point
                r = feat["properties"].get("radius", 4)
                color = feat["properties"].get("color", "red")
                outline = feat["properties"].get("outline", "")
                point_id = canvas.create_oval(
                    x - r,
                    y - r,
                    x + r,
                    y + r,
                    fill=color,
                    outline=outline,
                    tags=(self.name, feature_tag),
                )
                self._bind_feature(canvas, point_id, feature_tag)
            if all_not_visible:
                continue
            label_text = (
                feat["properties"].get(self.label_key)
                if self.label_key
                else None
            )
            if label_text:
                # if feat['geometry'].get("type") == "MultiPoint":

                # x1, y1, x2, y2 = canvas.bbox(feature_tag)
                label = LabelAnnotation(
                    text=label_text,
                    offset=feat.get("label_offset", (r + 2, -r - 2)),
                    font=feat.get("label_font", ("Arial", 10)),
                    text_color=feat.get("label_color", "black"),
                    bg_color=feat.get("label_bg", "lightgray"),
                    border_color=feat.get("label_border_color", "gray"),
                    border_width=feat.get("label_border_width", 1),
                )
                label.draw(
                    canvas, x_right, y_top, tags=(self.name, feature_tag)
                )


class ShapeLayer(MapLayer):

    def __init__(
        self,
        name: str,
        on_click=None,
        label_key=None,
    ):
        super().__init__(name, on_click=on_click)
        self.name = name
        self.label_key = label_key

    def draw(
        self,
        canvas: CanvasMap,
        project_fn: Callable[[float, float], tuple[float, float]],
    ):

        min_lon, min_lat, max_lon, max_lat = canvas.get_canvas_bounds()

        for feat in self.features:
            feature_tag = f"{self.name}_{self.feature_count}"
            geom = feat["geometry"]
            raw = geom["coordinates"]

            # normalize both Polygon and MultiPolygon into a list of rings
            if geom["type"] == "MultiPolygon":
                rings = [ring for polygon in raw for ring in polygon]
            else:  # "Polygon"
                rings = raw

            # pull all the rings into a single list
            lats = [lat for ring in rings for lon, lat in ring]
            lons = [lon for ring in rings for lon, lat in ring]

            visible = (
                min_lon <= min(lons) <= max_lon
                and min_lat <= min(lats) <= max_lat
            )
            if not visible:
                continue

            # if max(lats) < min_lat or min(lats) > max_lat:
            #     continue
            # if max(lons) < min_lon or min(lons) > max_lon:
            #     continue

            for ring in rings:
                x_right = None
                y_right = None
                points = [project_fn(lat, lon) for lon, lat in ring]
                for x, y in points:  # find the rightmost point for the label
                    if x_right is None or x > x_right:
                        x_right, y_right = x, y

                outline = feat.get(
                    "outline", "black"
                )  # just the outline because it does not work with the image
                _ = canvas.create_polygon(
                    *points,
                    fill="",
                    outline=outline,
                    tags=(self.name, feature_tag),
                )
                shape_image = draw_feature_with_holes(
                    canvas, project_fn, feat, self.name
                )
                self._bind_feature(canvas, shape_image, feat)

            label_text = (
                feat["properties"].get(self.label_key)
                if self.label_key
                else None
            )
            if label_text:
                label = LabelAnnotation(
                    text=label_text,
                    offset=feat["properties"].get("label_offset", (0, 0)),
                    font=feat["properties"].get("label_font", ("Arial", 10)),
                    text_color=feat["properties"].get("label_color", "black"),
                    bg_color=feat["properties"].get("label_bg", "lightgray"),
                    border_color=feat["properties"].get(
                        "label_border_color", "gray"
                    ),
                    border_width=feat["properties"].get(
                        "label_border_width", 1
                    ),
                )
                # x1, y1, x2, y2 = canvas.bbox(shape_image)
                label.draw(
                    canvas, x_right, y_right, tags=(self.name, feature_tag)
                )


class LineLayer(MapLayer):
    """
    Layer for rendering LineString / MultiLineString features.

    TODO: implement `draw()` to convert features into canvas lines.
    """

    def __init__(self, name, on_click=None, label_key=None):
        super().__init__(name, on_click, label_key)

    def draw(
        self,
        canvas: CanvasMap,
        project_fn: Callable[[float, float], tuple[float, float]],
    ):
        """
        Draw the line features on the canvas.
        Raise NotImplementedError until this is implemented.
        """
        min_lon, min_lat, max_lon, max_lat = canvas.get_canvas_bounds()
        for feat in self.features:
            x_right = None
            y_right = None
            feature_tag = f"{self.name}_{self.feature_count}"
            geom = feat["geometry"]
            raw = geom["coordinates"]

            # normalize both Polygon and MultiPolygon into a list of rings
            if geom["type"] == "MultiLineString":
                lines = raw
            else:  # "LineString"
                lines = [raw]
            lats = [lat for line in lines for lon, lat in line]
            lons = [lon for line in lines for lon, lat in line]
            print("Canvas  lon range:", max_lon, "→", min_lon)
            print("Canvas  lat range:", min_lat, "→", max_lat)
            print("Feature lon range:", min(lons), "→", max(lons))
            print("Feature lat range:", min(lats), "→", max(lats))

            visible = (
                min_lon <= min(lons) <= max_lon
                and min_lat <= min(lats) <= max_lat
            )
            if not visible:
                continue

            props = feat.get("properties", {})
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

            for line in lines:

                points = [project_fn(lat, lon) for lon, lat in line]
                for x, y in points:  # find the rightmost point for the label
                    if x_right is None or x > x_right:
                        x_right, y_right = x, y

                line_id = canvas.create_line(
                    *points, **canvas_opts, tags=(self.name, feature_tag)
                )
                self._bind_feature(canvas, line_id, feat)
            label_text = (
                feat["properties"].get(self.label_key)
                if self.label_key
                else None
            )
            if label_text:
                label = LabelAnnotation(
                    text=label_text,
                    offset=feat["properties"].get("label_offset", (0, 0)),
                    font=feat["properties"].get("label_font", ("Arial", 10)),
                    text_color=feat["properties"].get("label_color", "black"),
                    bg_color=feat["properties"].get("label_bg", "lightgray"),
                    border_color=feat["properties"].get(
                        "label_border_color", "gray"
                    ),
                    border_width=feat["properties"].get(
                        "label_border_width", 1
                    ),
                )
                # x1, y1, x2, y2 = canvas.bbox(shape_image)
                label.draw(
                    canvas, x_right, y_right, tags=(self.name, feature_tag)
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


def draw_feature_with_holes(canvas, project_fn, feat, tag, opacity=0.5):
    geom = feat["geometry"]
    coords = geom["coordinates"]

    if geom["type"] == "MultiPolygon":
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
        fill_color = feat["properties"].get("fill", "red")
        alpha = int(feat["properties"].get("alpha", opacity) * 255)
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
