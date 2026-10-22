import unittest
from tomtom_client import build_route_request, parse_route_response

class TomTomClientTests(unittest.TestCase):
    def test_builds_orbis_route_request_with_waypoints(self):
        req = build_route_request(
            origin=(38.036, -78.491),
            destination=(38.036, -78.491),
            waypoints=[(38.952, -77.453), (38.085, -78.644)],
            depart_at="2026-10-16T19:30:00-04:00",
        )
        self.assertEqual(req["url"], "https://api.tomtom.com/maps/orbis/routing/routes/calculate?apiVersion=3")
        self.assertEqual(req["headers"]["TomTom-Api-Version"], "3")
        self.assertEqual(req["body"]["routePlanningLocations"]["waypoints"]["type"], "MultiPoint")
        self.assertEqual(req["body"]["routePlanningLocations"]["waypoints"]["coordinates"], [[-77.453, 38.952], [-78.644, 38.085]])
        self.assertEqual(req["body"]["departureDateTime"], "2026-10-16T19:30:00-04:00")
        self.assertEqual(req["body"]["routeType"], "fast")

    def test_parses_distance_and_duration(self):
        data = {"routes": [{"summary": {"lengthInMeters": 16093, "travelDurationInSeconds": 3600}}]}
        result = parse_route_response(data)
        self.assertAlmostEqual(result["miles"], 10.0, places=2)
        self.assertEqual(result["minutes"], 60.0)

    def test_collects_orbis_leg_paths_in_map_coordinate_order(self):
        data = {"routes": [{
            "summary": {"lengthInMeters": 16093, "travelDurationInSeconds": 3600},
            "legs": [
                {"path": {"type": "LineString", "coordinates": [[-78.49, 38.03], [-78.5, 38.04]]}},
                {"path": {"type": "LineString", "coordinates": [[-78.5, 38.04], [-78.51, 38.05]]}},
            ],
        }]}
        self.assertEqual(parse_route_response(data)['points'], [
            [38.03, -78.49], [38.04, -78.5], [38.04, -78.5], [38.05, -78.51],
        ])

if __name__ == "__main__":
    unittest.main()
