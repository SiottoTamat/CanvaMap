from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Union
import uuid
import copy
import logging

Point = Tuple[float, float]
LinearRing = List[Point]
PolygonRings = List[LinearRing]
GeometryCoords = Union[List[Point], PolygonRings]  # any point list type

logger = logging.getLogger(__name__)


@dataclass
class Feature:
    """
    Unified Feature abstraction wrapping a raw GeoJSON feature.

    The Feature object preserves the exact sub-dictionary from the original
    GeoJSON corresponding to this single feature (not including any
    sibling features or higher-level FeatureCollections).
    It also maintains a normalized representation
    for easy rendering and analysis.

    Attributes:
        raw: dict
            The original GeoJSON feature dictionary for **this** feature only.
        id: str
            A unique identifier for this feature (UUID by default).
        geometry_type: str
            The GeoJSON geometry type (Point, Polygon, etc.).
        geoms: List[GeometryCoords]
            One or more normalized geometry coordinate sets:
              - Point/MultiPoint/LineString/MultiLineString as flat List[Point]
              - Polygon/MultiPolygon as List of LinearRings
        properties: dict
            Flattened properties from the original feature.
        sequence_index: Optional[int]
            The order in which this feature was loaded.
        collection_name: Optional[str]
            If this feature came from a GeometryCollection,
            the name of the parent.
        parent_chain: List[str]
            List of ancestor Feature IDs (or names) this feature
            is nested within, from outermost to immediate parent.
    """

    raw: dict
    sequence_index: int = field(init=True)
    collection_name: Optional[str] = None
    parent_chain: List[str] = field(default_factory=list)

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    geometry_type: str = field(init=False)
    properties: dict = field(init=False)
    geoms: list[GeometryCoords] = field(init=False)
    dataset_name: str | None = None

    def __post_init__(self):
        geom = self.raw.get("geometry", {})
        self.geometry_type = geom.get("type", "") if geom else ""
        coords = geom.get("coordinates", None) if geom else None

        self.properties = self.raw.get("properties", {}) or {}
        self.geoms = []

        try:
            if self.geometry_type == "Point":
                self.geoms = [[tuple(coords)]]
            elif self.geometry_type == "MultiPoint":
                self.geoms = [[tuple(point) for point in coords]]
            elif self.geometry_type == "LineString":
                self.geoms = [[tuple(point) for point in coords]]
            elif self.geometry_type == "MultiLineString":
                self.geoms = [
                    [tuple(point) for point in line] for line in coords
                ]
            elif self.geometry_type == "Polygon":
                self.geoms = [
                    [tuple(point) for point in ring] for ring in coords
                ]
            elif self.geometry_type == "MultiPolygon":
                self.geoms = [
                    [[tuple(point) for point in ring] for ring in polygon]
                    for polygon in coords
                ]
            elif self.geometry_type:
                logger.warning(
                    f"Unsupported geometry type: {self.geometry_type}"
                )
        except Exception as e:
            logger.error(
                f"Failed to normalize geometry ({self.geometry_type}): {e}"
            )
            self.geoms = []

    @classmethod
    def from_raw(
        cls,
        raw_feature: dict,
        sequence_index: int,
        collection_name: Optional[str] = None,
        parent_chain: Optional[List[str]] = None,
        dataset_name: Optional[str] = None,
    ):
        """
        Factory to create a Feature from a GeoJSON feature dict, preserving
        the raw sub-dictionary (deep-copied) and tagging sequence, collection,
        and parent chain.
        """
        raw_copy = copy.deepcopy(raw_feature)  # isolate problems
        feature = cls(
            raw=raw_copy,
            sequence_index=sequence_index,
            collection_name=collection_name,
            parent_chain=parent_chain or [],
            dataset_name=dataset_name,
        )
        return feature
