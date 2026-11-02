"""Road-network topology checks using synthetic metre-based geometry, not a site survey."""
from pyproj import Transformer
from shapely.geometry import LineString, Polygon, box

from app.road_network import screen_road_network

WORLD = Transformer.from_crs("EPSG:32647", "EPSG:4326", always_xy=True)
SITE = box(0, 0, 100, 100)


def scan(*coordinate_lines, site=SITE):
    return screen_road_network(site, [LineString(coords) for coords in coordinate_lines], WORLD)


def test_empty_network_reports_no_access_and_no_nodes():
    result = scan()
    assert result["network"]["status"] == "no_roads"
    assert result["network"]["component_count"] == 0
    assert result["network"]["external_access_verified"] is False
    assert result["layers"]["road_junctions"]["features"] == []


def test_endpoint_t_junction_is_connected_but_boundary_access_is_unverified():
    result = scan([(0, 50), (80, 50)], [(40, 50), (40, 80)])
    values = result["network"]
    assert values["status"] == "connected_boundary_candidate"
    assert values["components"] == [{"roads": [1, 2], "boundary_candidate": True}]
    assert values["component_count"] == 1
    assert values["boundary_candidate_endpoints"] == 1
    assert values["dangling_endpoints"] == 2
    assert values["crossing_pairs_unconfirmed"] == 0
    assert len(result["layers"]["road_junctions"]["features"]) == 1
    assert len(result["layers"]["road_boundary_candidates"]["features"]) == 1
    assert values["external_access_verified"] is False


def test_interior_only_crossing_is_not_assumed_a_turning_junction():
    result = scan([(10, 50), (90, 50)], [(40, 10), (40, 90)])
    values = result["network"]
    assert values["status"] == "disconnected"
    assert values["component_count"] == 2
    assert values["crossing_pairs_unconfirmed"] == 1
    assert values["boundary_candidate_endpoints"] == 0
    assert len(result["layers"]["road_junctions"]["features"]) == 1
    assert result["layers"]["road_junctions"]["features"][0]["properties"]["kind"] == "unconfirmed_crossing"
    assert any("grade-separated" in warning for warning in result["warnings"])


def test_two_independent_roads_both_touch_boundary_but_remain_disconnected():
    result = scan([(0, 20), (60, 20)], [(0, 80), (60, 80)])
    values = result["network"]
    assert values["component_count"] == 2
    assert values["boundary_candidate_endpoints"] == 2
    assert values["components_with_boundary_candidates"] == 2
    assert values["status"] == "disconnected"


def test_close_gap_is_not_automatically_snapped():
    result = scan([(0, 50), (40, 50)], [(40.7, 50), (80, 50)])
    values = result["network"]
    assert values["component_count"] == 2
    assert values["close_unconnected_pairs"] == 1
    assert values["boundary_candidate_endpoints"] == 1
    assert len(result["layers"]["road_close_pairs"]["features"]) == 2


def test_overlapping_lines_share_component_but_are_flagged_for_review():
    result = scan([(0, 50), (60, 50)], [(20, 50), (85, 50)])
    values = result["network"]
    assert values["component_count"] == 1
    assert values["overlap_pairs"] == 1
    assert any("overlap" in warning for warning in result["warnings"])


def test_hole_boundary_is_not_external_access_candidate():
    site = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)],
                   holes=[[(30, 30), (40, 30), (40, 40), (30, 40)]])
    result = scan([(30, 35), (20, 35)], site=site)
    assert result["network"]["boundary_candidate_endpoints"] == 0
    assert result["network"]["status"] == "connected_internal_only"
