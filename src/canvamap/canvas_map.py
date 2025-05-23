from PIL import Image, ImageTk
import tkinter as tk
import math

from canvamap.tile_handler import request_tile, degree2tile, tile2degree

tile_size = 256


class CanvasMap(tk.Canvas):
    def __init__(
        self,
        master,
        lat,
        lon,
        zoom,
        provider="https://tile.openstreetmap.org",
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self.lat = lat
        self.lon = lon
        self.zoom = zoom
        self.provider = provider
        self.tile_size = tile_size
        self.tile_images = []
        self.layers = []
        self._redraw_after_id = None
        self._image_refs: list[tk.PhotoImage] = []

        # Track pan state
        self._is_dragging = False
        self._drag_start_x = 0
        self._drag_start_y = 0
        self.offset_x = 0
        self.offset_y = 0

        self.bind("<Configure>", self._on_resize)
        self.bind("<ButtonPress-1>", self._start_drag)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._end_drag)
        self.bind("<MouseWheel>", self._on_zoom)  # Windows
        self.bind("<Button-4>", self._on_zoom)  # Linux scroll up
        self.bind("<Button-5>", self._on_zoom)  # Linux scroll down

        self.after(100, self.draw_map)

    def _on_resize(self, event):
        if self._redraw_after_id:
            self.after_cancel(self._redraw_after_id)
        self._redraw_after_id = self.after(200, self.draw_map)

    def _start_drag(self, event):
        self._is_dragging = True
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_drag(self, event):
        dx = event.x - self._drag_start_x
        dy = event.y - self._drag_start_y
        self._drag_start_x = event.x
        self._drag_start_y = event.y
        self.offset_x -= dx
        self.offset_y -= dy
        self.move("tile", dx, dy)

    def _end_drag(self, event):
        if self.offset_x != 0 or self.offset_y != 0:
            self._update_center_after_pan()
            self.draw_map()

    def _on_zoom(self, event):
        if event.num == 5 or event.delta < 0:
            if self.zoom > 1:
                self.zoom -= 1
        elif event.num == 4 or event.delta > 0:
            if self.zoom < 19:
                self.zoom += 1
        self.draw_map()

    def _get_origin_px(self):
        """
        Compute the origin (top-left corner) of the map in pixel coordinates.

        This method calculates:
        - the starting tile indices (top-left tile) visible on the canvas,
        - the pixel offset of the exact map center within that tile,
        - the pixel coordinates of the origin (top-left of first tile)
        on the canvas.

        This logic ensures perfect alignment between map tiles
        and projected lat/lon features,
        and is reused across all projection and rendering operations.

        Returns:
            tuple[int, int, float, float]:
                start_tile_x: X index of top-left tile,
                start_tile_y: Y index of top-left tile,
                origin_px_x: X coordinate of the tile origin on canvas,
                origin_px_y: Y coordinate of the tile origin on canvas.
        """
        canvas_width = self.winfo_width()
        canvas_height = self.winfo_height()

        num_x_tiles = (canvas_width // self.tile_size) + 2
        num_y_tiles = (canvas_height // self.tile_size) + 2

        exact_tile_x, exact_tile_y = degree2tile(self.lat, self.lon, self.zoom)

        start_tile_x = int(math.floor(exact_tile_x - num_x_tiles / 2))
        start_tile_y = int(math.floor(exact_tile_y - num_y_tiles / 2))

        offset_px_x = (exact_tile_x - start_tile_x) * self.tile_size
        offset_px_y = (exact_tile_y - start_tile_y) * self.tile_size

        origin_px_x = (canvas_width / 2) - offset_px_x
        origin_px_y = (canvas_height / 2) - offset_px_y

        return start_tile_x, start_tile_y, origin_px_x, origin_px_y

    def draw_map(self, event=None):
        """
        Render the current visible map area on the canvas.

        This includes:
        - Determining visible tiles based on center coordinates and zoom level,
        - Requesting and drawing each tile image,
        - Recalculating the center coordinates based on updated tile positions,
        - Drawing all visible layers (e.g., points) on top of the map.

        This is the core function driving the dynamic,
        zoomable tile map rendering.
        """
        self.delete("all")
        canvas_width = self.winfo_width()
        canvas_height = self.winfo_height()

        if canvas_width <= 1 or canvas_height <= 1:
            self.after(50, self.draw_map)
            return

        num_x_tiles = (canvas_width // self.tile_size) + 2
        num_y_tiles = (canvas_height // self.tile_size) + 2

        start_tile_x, start_tile_y, origin_px_x, origin_px_y = (
            self._get_origin_px()
        )

        self.tile_images.clear()

        for j in range(num_y_tiles):
            for i in range(num_x_tiles):
                x = start_tile_x + i
                y = start_tile_y + j

                tile_data = request_tile(x, y, self.zoom, self.provider)
                if tile_data:
                    image = Image.open(tile_data)
                    tk_image = ImageTk.PhotoImage(image)

                    px = origin_px_x + i * self.tile_size
                    py = origin_px_y + j * self.tile_size

                    self.create_image(
                        px,
                        py,
                        image=tk_image,
                        anchor="nw",
                        tags="tile",
                    )
                    self.tile_images.append(tk_image)

        self.offset_x = 0
        self.offset_y = 0
        self.lat, self.lon = self.get_center_latlon()
        self.create_text(
            self.winfo_width() - 5,
            self.winfo_height() - 5,
            text=f"Lat: {self.lat:.5f}, Lon: {self.lon:.5f},"
            f" Zoom: {self.zoom}",
            anchor="se",
            fill="black",
            font=("Arial", 10),
            tags="latlonoverlay",
        )
        self._draw_layers()

    def _draw_layers(self):
        project = self.project_latlon_to_canvas
        for layer in self.layers:
            if layer.visible:
                layer.draw(self, project)

    def _update_center_after_pan(self):
        """Adjust self.lat/lon based on accumulated pixel drag offset."""
        dx_tiles = self.offset_x / self.tile_size
        dy_tiles = self.offset_y / self.tile_size
        tile_x, tile_y = degree2tile(self.lat, self.lon, self.zoom)
        new_tile_x = tile_x + dx_tiles
        new_tile_y = tile_y + dy_tiles

        self.lat, self.lon = tile2degree(new_tile_x, new_tile_y, self.zoom)
        self.offset_x = 0
        self.offset_y = 0
        print(f"After: {self.lat}, {self.lon}")

    def get_center_latlon(self) -> tuple[float, float]:
        """
        Compute the geographic coordinates of the current center of the canvas.

        This method performs the reverse of `project_latlon_to_canvas`,
        projecting the visual center of the canvas back into a (lat, lon)
        based on tile origin and zoom level.

        It is used to update the internal state after panning or zooming,
        ensuring the logical center matches the visual center.

        Returns:
            tuple[float, float]: (latitude, longitude) of the canvas center.
        """
        canvas_width = self.winfo_width()
        canvas_height = self.winfo_height()

        exact_tile_x, exact_tile_y = degree2tile(self.lat, self.lon, self.zoom)

        num_x_tiles = (canvas_width // self.tile_size) + 2
        num_y_tiles = (canvas_height // self.tile_size) + 2

        # Match EXACTLY the _get_origin_px calculation:
        start_tile_x = int(math.floor(exact_tile_x - num_x_tiles / 2))
        start_tile_y = int(math.floor(exact_tile_y - num_y_tiles / 2))

        offset_px_x = (exact_tile_x - start_tile_x) * self.tile_size
        offset_px_y = (exact_tile_y - start_tile_y) * self.tile_size

        origin_px_x = (canvas_width / 2) - offset_px_x
        origin_px_y = (canvas_height / 2) - offset_px_y

        # Now recalculate exact center tile coordinates:
        center_tile_x = (
            start_tile_x + (canvas_width / 2 - origin_px_x) / self.tile_size
        )
        center_tile_y = (
            start_tile_y + (canvas_height / 2 - origin_px_y) / self.tile_size
        )

        return tile2degree(center_tile_x, center_tile_y, self.zoom)

    def add_layer(self, layer):
        self.layers.append(layer)

    def get_canvas_bounds(self) -> tuple[float, float, float, float]:
        # Return the geographic bounding box
        # (min_lat, min_lon, max_lat, max_lon)
        w, h = self.winfo_width(), self.winfo_height()
        top_left = self.project_canvas_to_latlon(0, 0)
        bottom_right = self.project_canvas_to_latlon(w, h)
        min_lat = min(top_left[0], bottom_right[0])
        max_lat = max(top_left[0], bottom_right[0])
        min_lon = min(top_left[1], bottom_right[1])
        max_lon = max(top_left[1], bottom_right[1])
        return (min_lon, min_lat, max_lon, max_lat)

    def project_latlon_to_canvas(self, lat, lon) -> tuple[float, float]:
        """
        Project a geographic coordinate (latitude, longitude)
        to canvas pixel coordinates.

        Uses the current zoom level and map center to calculate
        where the point should appear on screen.
        Relies on `_get_origin_px` to ensure consistency with tile rendering.

        Args:
            lat (float): Latitude of the geographic point.
            lon (float): Longitude of the geographic point.

        Returns:
            tuple[float, float]: (x, y) pixel coordinates on the canvas.
        """
        start_tile_x, start_tile_y, origin_px_x, origin_px_y = (
            self._get_origin_px()
        )

        # Tile coordinates of point
        exact_point_x, exact_point_y = degree2tile(lat, lon, self.zoom)

        # Pixel position relative to origin
        dx = (exact_point_x - start_tile_x) * self.tile_size
        dy = (exact_point_y - start_tile_y) * self.tile_size

        return origin_px_x + dx, origin_px_y + dy

    def project_canvas_to_latlon(self, x_px, y_px) -> tuple[float, float]:
        exact_tile_x, exact_tile_y = degree2tile(self.lat, self.lon, self.zoom)
        canvas_width = self.winfo_width()
        canvas_height = self.winfo_height()
        dx_tiles = (x_px - (canvas_width / 2)) / self.tile_size
        dy_tiles = (y_px - (canvas_height / 2)) / self.tile_size
        lonlat = tile2degree(
            exact_tile_x + dx_tiles, exact_tile_y + dy_tiles, self.zoom
        )
        return lonlat
