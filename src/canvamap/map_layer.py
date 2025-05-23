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
        self.features.append(feat)

    def draw(
        self, canvas, project_fn: Callable[[float, float], tuple[float, float]]
    ) -> None:

        bbox = canvas.get_canvas_bounds()
        # feature_tag = f"{self.name}_{self._feat_counter}"

        for feat in self.features:
            # for Multipoint label position
            x_right = None
            y_top = None
            feature_tag = f"{self.name}_{self._feat_counter}"
            self._feat_counter += 1
            all_not_visible = True

            for point in feat["geometry"]["coordinates"]:
                if len(point) != 2:
                    pass
                visible = (
                    bbox[0] <= point[1] <= bbox[2]
                    and bbox[1] <= point[0] <= bbox[3]
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
                self._bind_feature(canvas, point_id, feat)
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
                # if points:
                #     points.extend([None, None])
                # for y, x in shape:
                #     px, py = project_fn(x, y)
                #     points.extend([px, py])
                points = [project_fn(x, y) for y, x in shape]
                outline = feat.get("outline", "black")

                shape = canvas.create_polygon(
                    *points,
                    fill="",
                    outline=outline,
                    tags=(self.name,),
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
                x1, y1, x2, y2 = canvas.bbox(shape_image)
                label.draw(canvas, x2, y1, tags=(self.name, shape))


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


def draw_feature_with_holes(canvas, project_fn, feat, tag, opacity=0.5):
    rings = feat["geometry"]["coordinates"]
    # 1) Project all rings into pixel coords
    all_xy = []
    for ring in rings:
        pts = [project_fn(lat, lon) for lon, lat in ring]
        all_xy.append(pts)

    # 2) Compute bounding box in pixel space
    xs = [x for ring in all_xy for x, y in ring]
    ys = [y for ring in all_xy for x, y in ring]
    min_x, max_x = int(min(xs)), int(max(xs))
    min_y, max_y = int(min(ys)), int(max(ys))
    w, h = max_x - min_x, max_y - min_y

    # 3) Create an RGBA overlay image of just that bbox
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    mask = Image.new("L", (w, h), 0)  # grayscale mask

    draw = ImageDraw.Draw(mask)
    # 4) Draw outer ring (fill=255) then holes (fill=0) on the mask
    draw.polygon([(x - min_x, y - min_y) for x, y in all_xy[0]], fill=255)
    for hole in all_xy[1:]:
        draw.polygon([(x - min_x, y - min_y) for x, y in hole], fill=0)

    # 5) Color the overlay and apply the mask
    fill_color = feat["properties"].get("fill", "red")
    alpha = int(feat["properties"].get("alpha", 0.5) * 255)
    color_img = Image.new(
        "RGBA", (w, h), (*ImageColor.getrgb(fill_color), alpha)
    )
    overlay.paste(color_img, (0, 0), mask)

    # 6) Convert to a PhotoImage and draw on the canvas
    tk_img = ImageTk.PhotoImage(overlay)
    img_id = canvas.create_image(
        min_x, min_y, image=tk_img, anchor="nw", tags=(tag,)
    )
    # Keep a reference so Python doesn’t garbage‐collect it:
    canvas._image_refs.append(tk_img)
    return img_id
