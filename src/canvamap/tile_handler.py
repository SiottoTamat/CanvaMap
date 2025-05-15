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
    """Convert latitude and longitude to tile coordinates."""
    lat_rad = math.radians(lat_deg)
    n = 2.0**zoom
    x_tile = (lon_deg + 180.0) / 360.0 * n
    y_tile = (
        (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi)
        / 2.0
        * n
    )

    return x_tile, y_tile


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


def tile2degree(x_tile, y_tile, zoom) -> tuple:
    """Convert tile coordinates to latitude and longitude."""
    n = 2.0**zoom
    lon_deg = x_tile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y_tile / n)))
    lat_deg = math.degrees(lat_rad)
    return lat_deg, lon_deg
