import math
import requests
from io import BytesIO
import logging
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

tile_memory_cache: dict[tuple[int, int, int], bytes] = {}


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
    x_tile,
    y_tile,
    zoom,
    email: str,
    provider_template: str = "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
) -> BytesIO | None:
    """Request tile from map provider."""
    # 1) sanity‐check zoom
    MAX_ZOOM = 19
    if not isinstance(zoom, int) or zoom < 0 or zoom > MAX_ZOOM:
        logger.error(f"Invalid zoom level: {zoom}")
        return None

    # 2) sanity‐check tile X/Y bounds
    max_index = 2**zoom - 1
    if x_tile < 0 or x_tile > max_index or y_tile < 0 or y_tile > max_index:
        # off‐map tile: skip fetching
        return None
    # 3) sanity check on placeholders validation
    if not all(kw in provider_template for kw in ("{x}", "{y}", "{z}")):
        logger.error("Tile provider template must include {x}, {y}, and {z}")
        return None

    key = (zoom, x_tile, y_tile)
    if key in tile_memory_cache:
        return BytesIO(tile_memory_cache[key])

    try:
        url = provider_template.format(z=zoom, x=x_tile, y=y_tile)
    except KeyError as e:
        logger.error(
            f"Invalid provider template: missing {{{e.args[0]}}}"
            f" in template: {provider_template}"
        )
        return None

    headers = {"User-Agent": f"canvamap/1.0 ({email})"}

    for attempt in range(2):  # Try up to 2 times
        try:
            response = requests.get(url, headers=headers, timeout=(3, 10))
            if response.status_code == 200:
                raw = response.content
                tile_memory_cache[key] = raw
                return BytesIO(raw)
            else:
                logger.warning(
                    f"Attempt {attempt+1}: status {response.status_code} for {url}"
                )
        except requests.RequestException as e:
            logger.warning(f"Attempt {attempt+1} failed: {e} ({url})")

    # Final fallback: gray tile
    logger.error(f"Failed to fetch tile after retries: {url}")

    tile_size = 256
    fallback_tile = Image.new(
        "RGB", (tile_size, tile_size), color=(240, 240, 240)
    )
    draw = ImageDraw.Draw(fallback_tile)
    text = "Missing Tile"
    font = ImageFont.load_default()
    text_width, text_height = draw.textsize(text, font=font)
    text_position = (
        (tile_size - text_width) // 2,
        (tile_size - text_height) // 2,
    )
    draw.text(text_position, text, fill="black", font=font)

    buffer = BytesIO()
    fallback_tile.save(buffer, format="PNG")
    buffer.seek(0)
    tile_memory_cache[key] = buffer.getvalue()
    return buffer
