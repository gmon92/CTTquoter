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
        self.assertEqual(req["body"]["routePlanningLocations"]["waypoints"][0]["type"], "Point")
        self.assertEqual(req["body"]["routePlanningLocations"]["waypoints"][0]["coordinates"], [-77.453, 38.952])
        self.assertEqual(req["body"]["departAt"], "2026-10-16T19:30:00-04:00")

    def test_parses_distance_and_duration(self):
        data = {"routes": [{"summary": {"lengthInMeters": 16093, "travelTimeInSeconds": 3600}}]}
        result = parse_route_response(data)
        self.assertAlmostEqual(result["miles"], 10.0, places=2)
        self.assertEqual(result["minutes"], 60.0)

if __name__ == "__main__":
    unittest.main()
