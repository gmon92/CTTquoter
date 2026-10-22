import unittest
from quote_engine import calculate_quote

class QuoteEngineTests(unittest.TestCase):
    def test_linked_quote_starts_from_vehicle_hourly_rate(self):
        for vehicle, expected_quote, expected_mileage in [('sedan', 140, 3.5), ('suv', 170, 4.25)]:
            with self.subTest(vehicle=vehicle):
                result = calculate_quote(total_driver_minutes=120, one_way_miles=40, vehicle=vehicle)
                self.assertEqual(result['quote'], expected_quote)
                self.assertEqual(result['mileage_rate'], expected_mileage)

    def test_editing_each_value_produces_the_same_quote(self):
        edits = [
            {'edited': 'hourly_rate', 'hourly_rate': 85},
            {'edited': 'mileage_rate', 'mileage_rate': 4.25},
            {'edited': 'quote', 'quote': 170},
        ]
        for edit in edits:
            with self.subTest(edit=edit):
                result = calculate_quote(total_driver_minutes=120, one_way_miles=40, vehicle='sedan', **edit)
                self.assertEqual(result['quote'], 170)
                self.assertEqual(result['hourly_rate'], 85)
                self.assertEqual(result['mileage_rate'], 4.25)

    def test_fractional_driver_hours_and_one_way_mileage(self):
        result = calculate_quote(total_driver_minutes=90, one_way_miles=35, vehicle='sedan')
        self.assertEqual(result['quote'], 105)
        self.assertEqual(result['mileage_rate'], 3)

    def test_zero_time_or_miles_cannot_define_equivalent_rates(self):
        for minutes, miles in [(0, 40), (120, 0)]:
            with self.subTest(minutes=minutes, miles=miles):
                with self.assertRaises(ValueError):
                    calculate_quote(total_driver_minutes=minutes, one_way_miles=miles, vehicle='sedan')

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
