import tkinter as tk

from canvamap.canvas_map import CanvasMap


def open_window(x, y, zoom):
    window = tk.Tk()
    window.title("Test Window")
    window.geometry("1000x1000")

    canvas = CanvasMap(window, x, y, zoom)
    canvas.pack(fill="both", expand=True)

    window.mainloop()


if __name__ == "__main__":
    lat, lon = (38.947533, -77.115167)
    zoom = 15

    open_window(lat, lon, zoom)
