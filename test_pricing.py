import unittest

from pricing import reprice_quote


class RepricingTests(unittest.TestCase):
    def price(self, **changes):
        return reprice_quote({"total_driver_minutes": 120, "one_way_miles": 40,
                              "vehicle": "sedan", "trip_price": 140,
                              "additional_charge": 0, "include_tip": False,
                              "edited": "additional_charge", **changes})

    def test_each_linked_control_keeps_the_existing_equivalence(self):
        for source, value in [("hourly_rate", 85), ("mileage_rate", 4.25), ("quote", 170), ("quote_slider", 170)]:
            with self.subTest(source=source):
                result = self.price(edited=source, value=value)
                self.assertEqual((result['quote'], result['hourly_rate'], result['mileage_rate']), (170, 85, 4.25))

    def test_charge_is_added_once_and_removed_without_changing_trip_price(self):
        first = self.price(additional_charge=20)
        again = self.price(trip_price=first['trip_price'], additional_charge=20)
        self.assertEqual(first, again)
        self.assertEqual((first['quote'], first['hourly_rate'], first['mileage_rate']), (160, 80, 4))
        self.assertEqual(self.price(trip_price=again['trip_price'])['quote'], 140)

    def test_edited_total_includes_charge_and_changes_trip_price(self):
        result = self.price(edited='quote', value=200, additional_charge=20)
        self.assertEqual(result['trip_price'], 180)
        self.assertEqual(result['hourly_rate'], 100)

    def test_quote_has_existing_additional_charge_floor(self):
        result = self.price(edited='quote', value=5, additional_charge=20)
        self.assertEqual((result['quote'], result['trip_price']), (20, 0))
        self.assertTrue(result['clamped'])

    def test_tip_is_last_and_does_not_change_the_three_linked_controls(self):
        result = self.price(additional_charge=20, include_tip=True)
        self.assertEqual((result['quote'], result['tip_amount'], result['all_inclusive_price']), (160, 32, 192))
        self.assertEqual((result['hourly_rate'], result['mileage_rate']), (80, 4))
        again = self.price(trip_price=result['trip_price'], additional_charge=20, include_tip=True)
        self.assertEqual(result, again)

    def test_browser_currency_and_tip_rounding_are_preserved(self):
        for value, tip, total in [(19.99, 4, 23.99), (0.03, 0.01, 0.04), (0.025, 0.01, 0.04), (0, 0, 0)]:
            with self.subTest(value=value):
                result = self.price(edited='quote', value=value, include_tip=True)
                self.assertEqual((result['tip_amount'], result['all_inclusive_price']), (tip, total))

    def test_fractional_driver_time_and_customer_mileage(self):
        result = self.price(total_driver_minutes=90, one_way_miles=35, edited='hourly_rate', value=70)
        self.assertEqual((result['quote'], result['mileage_rate']), (105, 3))

    def test_invalid_inputs_are_rejected(self):
        for changes in [dict(total_driver_minutes=0), dict(one_way_miles=0), dict(edited='unknown'),
                        dict(additional_charge=-1), dict(additional_charge=True), dict(include_tip='false'),
                        dict(vehicle='bus'), dict(trip_price='nan'), dict(total_driver_minutes='inf'),
                        dict(edited='hourly_rate', value=-1), dict(edited='quote', value='invalid'),
                        dict(edited='quote', value=1e308)]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.price(**changes)


if __name__ == '__main__':
    unittest.main()
