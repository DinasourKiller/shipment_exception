"""Spatial Geometry & Geospatial Calculation Algorithms.

Pure-Python implementation of Haversine distance, Ray-Casting Point-in-Polygon (PIP),
and Great-Circle Cross-Track Corridor Deviation.
"""

import math
from typing import List, Optional

EARTH_RADIUS_METERS = 6371000.0


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute the great-circle spherical distance between two GPS coordinates in meters."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return EARTH_RADIUS_METERS * c


def is_point_in_circular_geofence(
    lat: float,
    lon: float,
    center_lat: Optional[float],
    center_lon: Optional[float],
    radius_meters: Optional[float],
) -> bool:
    """Determine whether a GPS coordinate falls within a circular geofence perimeter."""
    if center_lat is None or center_lon is None or radius_meters is None:
        return False
    distance = haversine_distance_meters(lat, lon, center_lat, center_lon)
    return distance <= radius_meters


def is_point_in_polygon(lat: float, lon: float, polygon: Optional[List[List[float]]]) -> bool:
    """Determine whether a GPS coordinate is inside a 2D polygon using the Ray-Casting algorithm.

    polygon is expected as a list of vertex pairs [[lat0, lon0], [lat1, lon1], ...]
    """
    if not polygon or len(polygon) < 3:
        return False

    num_vertices = len(polygon)
    inside = False

    p1_lat, p1_lon = polygon[0]
    for i in range(1, num_vertices + 1):
        p2_lat, p2_lon = polygon[i % num_vertices]

        # Check ray crossing
        if (p1_lon > lon) != (p2_lon > lon):
            # Compute x-coordinate of intersection of edge with horizontal line y = lon
            x_inters = (p2_lat - p1_lat) * (lon - p1_lon) / (p2_lon - p1_lon + 1e-12) + p1_lat
            if lat < x_inters:
                inside = not inside

        p1_lat, p1_lon = p2_lat, p2_lon

    return inside


def initial_bearing_radians(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the initial forward azimuth (bearing) from point 1 to point 2 in radians."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)

    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    return math.atan2(y, x)


def calculate_cross_track_deviation_meters(
    current_lat: float,
    current_lon: float,
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> float:
    """Calculate the cross-track error (orthogonal distance) from a planned route corridor.

    Calculates the shortest distance in meters from the current coordinate to the
    great-circle route path extending between origin and destination.
    """
    # Angular distance from origin to current point
    d13 = haversine_distance_meters(origin_lat, origin_lon, current_lat, current_lon) / EARTH_RADIUS_METERS

    # Bearings from origin
    bearing13 = initial_bearing_radians(origin_lat, origin_lon, current_lat, current_lon)
    bearing12 = initial_bearing_radians(origin_lat, origin_lon, dest_lat, dest_lon)

    # Cross-track distance formula
    d_xt_angular = math.asin(math.sin(d13) * math.sin(bearing13 - bearing12))
    return abs(d_xt_angular * EARTH_RADIUS_METERS)
