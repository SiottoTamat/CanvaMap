import math
import requests
from io import BytesIO
from dotenv import load_dotenv
import os
from Siotto_Utils.logger_utils import setup_logger

load_dotenv(".env")
user_email = os.getenv("user_email")

logger = setup_logger(__name__)

tile_memory_cache = {}


def degree2tile(lat_deg, lon_deg, zoom):
    """
    Convert geographic coordinates to fractional tile coordinates
    at a given zoom level.

    Uses the Web Mercator projection to transform latitude and longitude into
    continuous (x, y) tile space. Fractional values indicate sub-tile position.

    Args:
        lat_deg (float): Latitude in degrees.
        lon_deg (float): Longitude in degrees.
        zoom (int): Zoom level (typically 0–19).

    Returns:
        tuple[float, float]: (x_tile, y_tile)
        as floating-point tile coordinates.
    """
    lat_rad = math.radians(lat_deg)
    n = 2.0**zoom
    x_tile = (lon_deg + 180.0) / 360.0 * n
    y_tile = (
        (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi)
        / 2.0
        * n
    )

    return x_tile, y_tile


def tile2degree(x_tile, y_tile, zoom) -> tuple:
    """
    Convert tile coordinates back to geographic coordinates
    (latitude, longitude).

    This function performs the inverse of `degree2tile`,
    allowing fractional tile
    coordinates to be transformed into precise geographic positions.

    Args:
        x_tile (float): X tile coordinate (can be fractional).
        y_tile (float): Y tile coordinate (can be fractional).
        zoom (int): Zoom level (typically 0–19).

    Returns:
        tuple[float, float]: (latitude, longitude) in degrees.
    """
    n = 2.0**zoom
    lon_deg = x_tile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y_tile / n)))
    lat_deg = math.degrees(lat_rad)
    return lat_deg, lon_deg


def request_tile(
    x_tile, y_tile, zoom, provider: str = r"https://tile.openstreetmap.org"
) -> BytesIO | None:
    """Request tile from map provider."""
    key = (zoom, x_tile, y_tile)
    if key in tile_memory_cache:
        return tile_memory_cache[key]

    headers = {"User-Agent": f"canvamap/1.0 ({user_email})"}
    url = f"{provider}/{zoom}/{x_tile}/{y_tile}.png"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        tile_memory_cache[key] = BytesIO(response.content)
        return BytesIO(response.content)
    else:
        logger.error(
            f"Failed to fetch tile: {response.status_code}",
            f", {url}, {response.content}",
        )
        return None
