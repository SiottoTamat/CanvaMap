from typing import Sequence
from PIL import Image, ImageTk, ImageDraw, ImageColor
from canvamap.feature import Feature


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
        canvas,
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
        canvas.tile_images.append(tk_img)
        image_ids.append(img_id)

    # Return either a single id or list of ids
    return image_ids
