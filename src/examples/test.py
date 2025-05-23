import tkinter as tk
import json

from canvamap.canvas_map import CanvasMap

# from canvamap.map_layer import PointLayer, ShapeLayer, MapLayer
from canvamap.geojson_utils import load_geojson_to_map


def on_click(feat):
    print(feat)


def open_window(x, y, zoom=15, features: dict = {}, on_click=None):
    window = tk.Tk()
    window.title("Test Window")
    window.geometry("500x200")

    canvas = CanvasMap(window, x, y, zoom)
    canvas.pack(fill="both", expand=True)

    load_geojson_to_map(canvas, features, on_click, label_key="label")

    # for layer in layers:
    #     layer.on_click = on_click
    #     canvas.add_layer(layer)
    window.mainloop()


if __name__ == "__main__":
    lat, lon = (38.881359032440976, -77.03657933260475)
    zoom = 15

    geojson_features = json.load(open("src\examples\donut_example.geojson"))

    open_window(
        lat, lon, zoom=zoom, features=geojson_features, on_click=on_click
    )
