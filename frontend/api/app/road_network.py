"""Conservative topology screening for manually sketched road centrelines.

All inputs are already projected into the site's local metre-based UTM CRS.
Only endpoint-to-line touches (or overlapping sketches) join components;
interior-only crossings are NOT assumed to be at-grade junctions. A line
endpoint close to the OUTER project boundary is a candidate, never verified
public-road access, legal access, road design, or PBT permission.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from shapely.geometry import GeometryCollection, LineString, MultiPolygon, Point, Polygon, mapping
from shapely.ops import nearest_points, transform, unary_union

BOUNDARY_CONTACT_TOLERANCE_M = 0.5
CLOSE_PAIR_THRESHOLD_M = 1.0
EXACT_JOIN_TOLERANCE_M = 1e-5
MAX_MAP_POINTS = 100


def _points(geometry: Any) -> list[Point]:
    if isinstance(geometry, Point):
        return [geometry]
    if isinstance(geometry, GeometryCollection) or geometry.geom_type == "MultiPoint":
        return [p for item in geometry.geoms for p in _points(item)]
    return []


def _has_overlap(geometry: Any) -> bool:
    if geometry.geom_type in ("LineString", "MultiLineString"):
        return geometry.length > EXACT_JOIN_TOLERANCE_M
    if isinstance(geometry, GeometryCollection):
        return any(_has_overlap(item) for item in geometry.geoms)
    return False


def _endpoints(line: LineString) -> list[Point]:
    return [Point(line.coords[0]), Point(line.coords[-1])]


def _feature(point: Point, convert: Any, kind: str) -> dict[str, Any]:
    return {
        "type": "Feature",
        "properties": {"kind": kind, "screening_only": True},
        "geometry": mapping(transform(convert.transform, point)),
    }


def screen_road_network(site: Polygon | MultiPolygon, roads: list[LineString], convert: Any) -> dict[str, Any]:
    """Return separate network metrics and lightweight diagnostic map point layers."""
    n = len(roads)
    parents = list(range(n))

    def root(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def join(left: int, right: int) -> None:
        parents[root(right)] = root(left)

    outer = unary_union([poly.exterior for poly in (
        [site] if isinstance(site, Polygon) else list(site.geoms)
    )])
    endpoints = [_endpoints(line) for line in roads]
    boundary_by_line: list[bool] = []
    boundary_points: list[Point] = []
    dangling_ends = 0
    for index, road in enumerate(roads):
        hits = [point for point in endpoints[index]
                if point.distance(outer) <= BOUNDARY_CONTACT_TOLERANCE_M]
        boundary_by_line.append(bool(hits))
        boundary_points.extend(hits)
        if road.is_ring:
            continue
        for endpoint in endpoints[index]:
            if endpoint.distance(outer) <= BOUNDARY_CONTACT_TOLERANCE_M:
                continue
            if not any(endpoint.distance(other) <= EXACT_JOIN_TOLERANCE_M
                       for j, other in enumerate(roads) if j != index):
                dangling_ends += 1

    junction_points: list[tuple[Point, str]] = []
    close_points: list[Point] = []
    unconfirmed_crossings = 0
    overlaps = 0
    close_pairs = 0
    for i in range(n):
        for j in range(i + 1, n):
            a, b = roads[i], roads[j]
            if not a.intersects(b):
                distance = a.distance(b)
                if distance <= CLOSE_PAIR_THRESHOLD_M:
                    close_pairs += 1
                    close_points.extend(nearest_points(a, b))
                continue
            intersection = a.intersection(b)
            overlap = _has_overlap(intersection)
            linked_by_endpoint = any(p.distance(b) <= EXACT_JOIN_TOLERANCE_M
                                     for p in endpoints[i]) or any(
                p.distance(a) <= EXACT_JOIN_TOLERANCE_M for p in endpoints[j]
            )
            if overlap:
                overlaps += 1
            if linked_by_endpoint or overlap:
                join(i, j)
            else:
                unconfirmed_crossings += 1
            for point in _points(intersection):
                junction_points.append((point, "endpoint_join" if linked_by_endpoint else "unconfirmed_crossing"))

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[root(i)].append(i + 1)
    components = []
    for roads_in_component in sorted(groups.values(), key=lambda group: group[0]):
        components.append({
            "roads": roads_in_component,
            "boundary_candidate": any(boundary_by_line[number - 1] for number in roads_in_component),
        })
    components_with_boundary = sum(1 for comp in components if comp["boundary_candidate"])
    candidate_count = len(boundary_points)
    status = ("no_roads" if not n else "disconnected" if len(components) > 1
              else "connected_boundary_candidate" if candidate_count else "connected_internal_only")

    def render(points: list[tuple[Point, str]]) -> dict[str, Any]:
        seen: set[tuple[int, int, str]] = set()
        features = []
        for point, kind in points:
            key = (round(point.x * 10), round(point.y * 10), kind)
            if key in seen:
                continue
            seen.add(key)
            if len(features) >= MAX_MAP_POINTS:
                break
            features.append(_feature(point, convert, kind))
        return {"type": "FeatureCollection", "features": features,
                "map_truncated": len(seen) > MAX_MAP_POINTS or len(points) > MAX_MAP_POINTS}

    warnings = []
    if n:
        if len(components) > 1:
            warnings.append(
                f"Road sketches form {len(components)} endpoint-linked components, not one connected network. "
                "Interior-only line crossings are unverified and do not merge components."
            )
        if not candidate_count:
            warnings.append(
                "No drawn road endpoint reaches within 0.5 m of the OUTER site boundary; "
                "no possible edge-access contact is sketched. This does not prove access is unavailable."
            )
        else:
            warnings.append(
                f"{candidate_count} sketched endpoint(s) approach the outer site boundary (0.5 m tolerance). "
                "These are candidate contacts ONLY; adjoining public roads, legal rights, grade, and approvals are unverified."
            )
            if components_with_boundary < len(components):
                warnings.append(
                    f"Only {components_with_boundary} of {len(components)} disconnected component(s) "
                    "have a boundary-contact candidate."
                )
        if unconfirmed_crossings:
            warnings.append(
                f"{unconfirmed_crossings} interior-only crossing pair(s) may be grade-separated. "
                "Draw explicit endpoint junctions and verify at-grade design before treating these as connected."
            )
        if close_pairs:
            warnings.append(
                f"{close_pairs} distinct road pair(s) pass within 1.0 m without intersecting. "
                "They remain disconnected; nearby alignments are not automatically snapped together."
            )
        if overlaps:
            warnings.append(
                f"{overlaps} pair(s) of road sketches overlap. Repeated centreline geometry "
                "can conceal intended junctions; review these alignments."
            )
        if dangling_ends:
            warnings.append(
                f"{dangling_ends} endpoint(s) do not connect to another sketch or the outer boundary. "
                "They are possible dead ends; turning areas and emergency access are not assessed."
            )
    return {
        "network": {
            "status": status,
            "component_count": len(components),
            "components": components,
            "boundary_candidate_endpoints": candidate_count,
            "components_with_boundary_candidates": components_with_boundary,
            "dangling_endpoints": dangling_ends,
            "close_unconnected_pairs": close_pairs,
            "crossing_pairs_unconfirmed": unconfirmed_crossings,
            "overlap_pairs": overlaps,
            "boundary_contact_tolerance_m": BOUNDARY_CONTACT_TOLERANCE_M,
            "external_access_verified": False,
            "topology_screening_only": True,
            "method": "Local UTM metre geometry: roads join only at sketched endpoints or overlap; interior crossings are unconfirmed. Outer-boundary endpoints are provisional contact candidates, not public-road access.",
        },
        "layers": {
            "road_junctions": render(junction_points),
            "road_boundary_candidates": render([(p, "boundary_candidate") for p in boundary_points]),
            "road_close_pairs": render([(p, "close_unconnected") for p in close_points]),
        },
        "warnings": warnings,
    }
