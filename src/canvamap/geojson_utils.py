from typing import Iterator, List, Optional, Tuple

from canvamap.canvas_map import CanvasMap
from canvamap.map_layer import PointLayer, ShapeLayer, LineLayer
from canvamap.feature import Feature


def walk_features(
    obj: dict, parent_chain: Optional[List[str]] = None
) -> Iterator[Tuple[dict, List[str]]]:
    """
    Recursively yield each GeoJSON Feature leaf along with
    its parent collection chain.

    Args:
        obj: A GeoJSON object (FeatureCollection, Feature, or sub-geometry).
        parent_chain: List of ancestor collection names/IDs.

    Yields:
        Tuple of raw feature dict and its parent chain.
    """
    parent_chain = parent_chain or []
    typ = obj.get("type")

    if typ == "FeatureCollection":
        name = obj.get("properties", {}).get("name") or obj.get("id")
        for feat in obj.get("features", []):
            chain = parent_chain + [name] if name else parent_chain
            yield from walk_features(feat, chain)

    elif typ == "Feature":
        # Yield this feature
        yield obj, parent_chain
        # Handle GeometryCollection if present
        geom = obj.get("geometry", {})
        if geom.get("type") == "GeometryCollection":
            name = obj.get("properties", {}).get("name") or obj.get("id")
            chain = parent_chain + [name] if name else parent_chain
            for sub in geom.get("geometries", []):
                sub_feat = {
                    "type": "Feature",
                    "properties": obj.get("properties", {}),
                    "geometry": sub,
                }
                yield from walk_features(sub_feat, chain)

    # Other types (GeometryCollection at top level
    # or unsupported types) are ignored


def load_geojson_to_map(
    map_widget: CanvasMap, geojson: dict, click_fn=None, label_key=None
) -> List[Feature]:
    """
    Load GeoJSON into the CanvasMap by creating Feature objects, dispatching
    them into layers, and preserving the load sequence.

    Returns:
        A list of Feature instances in the exact order they were ingested.
    """
    point_layer = PointLayer("points", on_click=click_fn, label_key=label_key)
    line_layer = LineLayer("lines", on_click=click_fn, label_key=label_key)
    shape_layer = ShapeLayer(
        "polygons", on_click=click_fn, label_key=label_key
    )
    # Initialize widget sequence list if first load
    if not hasattr(map_widget, "load_feature_sequence"):
        map_widget.load_feature_sequence = []

    for raw_feat, chain in walk_features(geojson):
        idx = map_widget._feature_counter
        map_widget._feature_counter += 1
        collection = chain[-1] if chain else ""
        feat_obj = Feature.from_raw(
            raw_feature=raw_feat,
            sequence_index=idx,
            collection_name=collection,
            parent_chain=chain,
        )
        map_widget.load_feature_sequence.append(feat_obj)

        t = feat_obj.geometry_type
        if t in ("Point", "MultiPoint"):
            point_layer.add_feature(feat_obj)
        elif t in ("LineString", "MultiLineString"):
            line_layer.add_feature(feat_obj)
        elif t in ("Polygon", "MultiPolygon"):
            shape_layer.add_feature(feat_obj)
        # other types are skipped

    map_widget.add_layer(point_layer)
    map_widget.add_layer(line_layer)
    map_widget.add_layer(shape_layer)

    return map_widget.load_feature_sequence


def load_geojson_to_map_OLD(
    map_widget: CanvasMap, geojson: dict, project_fn=None, label_key=None
):
    # Create one of each layer (or reuse existing)
    point_layer = PointLayer(
        "points", on_click=project_fn, label_key=label_key
    )
    line_layer = LineLayer("lines", on_click=project_fn, label_key=label_key)
    shape_layer = ShapeLayer(
        "polygons", on_click=project_fn, label_key=label_key
    )

    for feat in geojson["features"]:
        norm_feat = normalize_geometry(feat)
        geom_type = norm_feat["geometry"]["type"]
        if geom_type in ("Point", "MultiPoint"):
            point_layer.add_feature(norm_feat)
        elif geom_type in ("LineString", "MultiLineString"):
            line_layer.add_feature(norm_feat)
        elif geom_type in ("Polygon", "MultiPolygon"):
            shape_layer.add_feature(norm_feat)
        else:
            # skip GeometryCollection or other types for now
            continue

    # Add them to canvas
    map_widget.add_layer(point_layer)
    map_widget.add_layer(line_layer)
    map_widget.add_layer(shape_layer)


def normalize_feature(feat: dict) -> dict:
    """
    Normalize a GeoJSON feature by flattening its properties and geometry.

    This function extracts the 'properties' field from a GeoJSON feature
    and combines it with the 'geometry' field into a single dictionary.
    It then reassigns the 'geometry' and 'properties' keys to maintain
    the original structure.

    Args:
        feat (dict): A GeoJSON feature dictionary containing 'geometry'
                    and 'properties' keys.

    Returns:
        dict: A normalized dictionary that includes the original geometry
            and properties of the feature.
    """

    props = feat.get("properties", {})
    flat = {**feat["geometry"], **props}
    flat["geometry"] = feat["geometry"]
    flat["properties"] = props
    return flat


def normalize_geometry(feature: dict) -> dict:

    geom = feature["geometry"]
    geom_type = geom.get("type")
    coords = geom.get("coordinates")

    if geom_type == "Point":
        list_coords = [tuple(coords)]
    elif geom_type == "MultiPoint":
        list_coords = [tuple(point) for point in coords]
    elif geom_type == "LineString":
        list_coords = [tuple(point) for point in coords]
    elif geom_type == "MultiLineString":
        list_coords = [[tuple(pt) for pt in line] for line in coords]
    elif geom_type == "Polygon":
        list_coords = [[tuple(coord) for coord in ring] for ring in coords]
    elif geom_type == "MultiPolygon":
        list_coords = [
            [[tuple(coord) for coord in ring] for ring in polygon]
            for polygon in coords
        ]
    else:
        raise ValueError(f"Unsupported geometry type: {geom_type}")

    return {
        "type": "Feature",
        "properties": feature.get("properties", {}),
        "geometry": {"type": geom_type, "coordinates": list_coords},
    }
