from canvamap.map_layer import PointLayer, ShapeLayer

# LineLayer
from canvamap.canvas_map import CanvasMap


def load_geojson_to_map(map_widget: CanvasMap, geojson: dict, project_fn=None):
    # Create one of each layer (or reuse existing)
    point_layer = PointLayer("points", [], on_click=project_fn)
    # line_layer = LineLayer("lines", [], on_click=project_fn)
    shape_layer = ShapeLayer("polygons", [], on_click=project_fn)

    for feat in geojson["features"]:
        geom_type = feat["geometry"]["type"]
        if geom_type in ("Point", "MultiPoint"):
            point_layer.add_feature(feat)
        # elif geom_type in ("LineString", "MultiLineString"):
        #     line_layer.add_feature(feat)
        elif geom_type in ("Polygon", "MultiPolygon"):
            shape_layer.add_feature(feat)
        else:
            # skip GeometryCollection or other types for now
            continue

    # Add them to canvas
    map_widget.add_layer(point_layer)
    # map_widget.add_layer(line_layer)
    map_widget.add_layer(shape_layer)
