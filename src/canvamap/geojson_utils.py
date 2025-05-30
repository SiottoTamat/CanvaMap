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
        if obj.get("type") == "GeometryCollection":
            name = obj.get("properties", {}).get("name") or obj.get("id")
            chain = parent_chain + [name] if name else parent_chain
            for sub in geom.get("geometries", []):
                sub_feat = {
                    "type": "Feature",
                    "properties": obj.get("properties", {}),
                    "geometry": sub,
                }
                yield from walk_features(sub_feat, chain)

    elif typ == "GeometryCollection":
        # Top-level GeometryCollection (not inside a Feature)
        for i, geom in enumerate(obj.get("geometries", [])):
            pseudo_feature = {
                "type": "Feature",
                "geometry": geom,
                "properties": obj.get("properties", {}),
                "id": f"{obj.get('id', 'gc')}_{i}",
            }
            yield pseudo_feature, parent_chain


def load_geojson_to_map(
    map_widget: CanvasMap,
    geojson: dict,
    click_fn=None,
    label_key=None,
    clear_existing: bool = True,
    dataset_name: str | None = None,
) -> list[Feature]:
    """
    Load GeoJSON into the CanvasMap by creating or updating layers.

    Args:
        map_widget: the CanvasMap widget
        geojson: the parsed GeoJSON dictionary
        click_fn: a callable for click interactivity
        label_key: property key to use for labels
        clear_existing: if True, features in reused layers are cleared

    Returns:
        A list of Feature instances loaded, in sequence
    """

    def get_or_create_layer(name: str, layer_type):
        for layer in map_widget.layers:
            if layer.name == name and isinstance(layer, layer_type):
                if clear_existing:
                    layer.clear_features()
                    map_widget.delete(f"layer:{name}")
                return layer
        new_layer = layer_type(name, on_click=click_fn, label_key=label_key)
        map_widget.add_layer(new_layer)
        return new_layer

    point_layer = get_or_create_layer("points", PointLayer)
    line_layer = get_or_create_layer("lines", LineLayer)
    shape_layer = get_or_create_layer("polygons", ShapeLayer)

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
        if dataset_name:
            feat_obj.properties["dataset"] = dataset_name

        map_widget.load_feature_sequence.append(feat_obj)

        t = feat_obj.geometry_type
        if t in ("Point", "MultiPoint"):
            point_layer.add_feature(feat_obj)
        elif t in ("LineString", "MultiLineString"):
            line_layer.add_feature(feat_obj)
        elif t in ("Polygon", "MultiPolygon"):
            shape_layer.add_feature(feat_obj)
        # unsupported geometries skipped

    return map_widget.load_feature_sequence
