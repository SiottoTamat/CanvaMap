import tkinter as tk
import json
import os
from dotenv import load_dotenv

from canvamap.canvas_map import CanvasMap, PROVIDERS_TEMPLATES

# from canvamap.map_layer import PointLayer, ShapeLayer, MapLayer
from canvamap.geojson_utils import load_geojson_to_map

load_dotenv(".env")
email = os.getenv("user_email")


def on_click(feat):
    print(feat)


def open_window(x, y, zoom=15, features: dict = {}, on_click=None):
    window = tk.Tk()
    window.title("Test Window")
    window.geometry("1000x1000")

    canvas = CanvasMap(
        window,
        x,
        y,
        zoom,
        email,
        provider_template=PROVIDERS_TEMPLATES["carto_light"],
    )
    canvas.pack(fill="both", expand=True)
    canvas.on(
        # any virtual event has to be prefixed with `<<CanvasMap-...>>`
        "<<CanvasMap-Button-3>>",
        lambda e: print(
            "right-clicked at", canvas.project_canvas_to_latlon(e.x, e.y)
        ),
    )

    load_geojson_to_map(canvas, features, on_click, label_key="label")
    window.mainloop()


if __name__ == "__main__":
    lat, lon = (38.881359032440976, -77.03657933260475)
    zoom = 14

    geojson_features = json.load(open(r"src\examples\donut_example.geojson"))

    open_window(
        lat, lon, zoom=zoom, features=geojson_features, on_click=on_click
    )
