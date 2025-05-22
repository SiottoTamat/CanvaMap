from canvamap.map_layer import PointLayer, ShapeLayer

# LineLayer
from canvamap.canvas_map import CanvasMap


def load_geojson_to_map(
    map_widget: CanvasMap, geojson: dict, project_fn=None, label_key=None
):
    # Create one of each layer (or reuse existing)
    point_layer = PointLayer(
        "points", on_click=project_fn, label_key=label_key
    )
    # line_layer = LineLayer("lines",
    # [],
    # on_click=project_fn,
    # label_key=label_key)
    shape_layer = ShapeLayer(
        "polygons", on_click=project_fn, label_key=label_key
    )

    for feat in geojson["features"]:
        norm_feat = normalize_feature(feat)
        geom_type = norm_feat["geometry"]["type"]
        if geom_type in ("Point", "MultiPoint"):
            point_layer.add_feature(norm_feat)
        # elif geom_type in ("LineString", "MultiLineString"):
        #     line_layer.add_feature(feat)
        elif geom_type in ("Polygon", "MultiPolygon"):
            shape_layer.add_feature(norm_feat)
        else:
            # skip GeometryCollection or other types for now
            continue

    # Add them to canvas
    map_widget.add_layer(point_layer)
    # map_widget.add_layer(line_layer)
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
