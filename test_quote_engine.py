import unittest
from quote_engine import calculate_quote

class QuoteEngineTests(unittest.TestCase):
    def test_uses_hourly_floor_and_reports_mileage_comparison(self):
        result = calculate_quote(
            base_rate=295,
            total_driver_minutes=331,
            one_way_miles=111,
            vehicle="sedan",
        )
        self.assertEqual(result["base_rate"], 295)
        self.assertAlmostEqual(result["hourly_price"], 386.17, places=2)
        self.assertAlmostEqual(result["mileage_price"], 333.0, places=2)
        self.assertEqual(result["recommended_price"], result["hourly_price"])
        self.assertEqual(result["recommended_method"], "hourly")

    def test_suv_uses_suv_rates(self):
        result = calculate_quote(
            base_rate=355,
            total_driver_minutes=331,
            one_way_miles=111,
            vehicle="suv",
        )
        self.assertAlmostEqual(result["hourly_price"], 468.92, places=2)
        self.assertAlmostEqual(result["mileage_price"], 399.60, places=2)

if __name__ == "__main__":
    unittest.main()
