import tkinter as tk

from canvamap.canvas_map import CanvasMap
from canvamap.map_layer import PointLayer, MapLayer


def open_window(x, y, zoom, layers: list[MapLayer] = []):

    def on_click(feat):
        print(feat)

    window = tk.Tk()
    window.title("Test Window")
    window.geometry("500x200")

    canvas = CanvasMap(window, x, y, zoom)
    canvas.pack(fill="both", expand=True)
    for layer in layers:
        layer.on_click = on_click
        canvas.add_layer(layer)
    window.mainloop()


if __name__ == "__main__":
    lat, lon = (38.881359032440976, -77.03657933260475)
    zoom = 15
    point1 = {
        "lat": 38.881359032440976,
        "lon": -77.03657933260475,
        "radius": 4,
        "color": "red",
        "label": "Jefferson Memorial",
    }
    point2 = {
        "lat": 38.88940640453685,
        "lon": -77.0353236213486,
        "radius": 4,
        "color": "blue",
        "label": "Washington Memorial",
    }

    open_window(
        lat, lon, zoom, layers=[PointLayer("points", [point1, point2])]
    )
