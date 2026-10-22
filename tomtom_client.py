from __future__ import annotations

import json
import os
from urllib.request import Request, urlopen

BASE_URL = "https://api.tomtom.com/maps/orbis/routing/routes/calculate?apiVersion=3"


def _point(coords):
    lat, lon = coords
    return {"type": "Point", "coordinates": [float(lon), float(lat)]}


def build_route_request(*, origin, destination, waypoints=None, depart_at=None):
    locations = {"origin": _point(origin), "destination": _point(destination)}
    if waypoints:
        locations["waypoints"] = {
            "type": "MultiPoint",
            "coordinates": [_point(p)["coordinates"] for p in waypoints],
        }
    body = {"routePlanningLocations": locations, "routeType": "fast"}
    if depart_at:
        body["departureDateTime"] = depart_at
    return {
        "url": BASE_URL,
        "headers": {
            "Content-Type": "application/json",
            "TomTom-Api-Version": "3",
            "TomTom-Api-Key": os.environ.get("TOMTOM_API_KEY", ""),
            "Attributes": "routes",
        },
        "body": body,
    }


def parse_route_response(data):
    route = data["routes"][0]
    summary = route["summary"]
    points = []
    for leg in route.get("legs", []):
        coordinates = leg.get("path", {}).get("coordinates", [])
        points.extend([[float(lat), float(lon)] for lon, lat in coordinates])
    return {
        "miles": round(summary["lengthInMeters"] / 1609.344, 2),
        "minutes": round(summary["travelDurationInSeconds"] / 60, 2),
        "points": points,
    }


def calculate_route(*, origin, destination, waypoints=None, depart_at=None):
    request = build_route_request(
        origin=origin, destination=destination, waypoints=waypoints, depart_at=depart_at
    )
    if not request["headers"]["TomTom-Api-Key"]:
        raise RuntimeError("TOMTOM_API_KEY is not configured")
    req = Request(
        request["url"],
        data=json.dumps(request["body"]).encode(),
        headers=request["headers"],
        method="POST",
    )
    with urlopen(req, timeout=30) as response:
        return parse_route_response(json.load(response))
