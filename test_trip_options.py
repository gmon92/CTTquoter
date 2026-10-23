import unittest
from unittest.mock import patch

from app import HOME, make_quote
from base_rates import find_trip_reference_rates


class TripOptionTests(unittest.TestCase):
    def quote(self, **options):
        payload = {'pickup': 'IAD', 'destination': 'Charlottesville', **options}
        full = {'minutes': 120, 'miles': 100}
        customer = {'minutes': 60, 'miles': 40}
        with patch('app.geocode', side_effect=lambda address: (1, len(address))), \
                patch('app.calculate_route', side_effect=[full, customer]) as routing:
            result = make_quote(payload)
        return result, routing

    def test_extra_stops_preserve_order_in_both_routes(self):
        result, routing = self.quote(stops=['Keswick Hall', 'CHO'])
        full, customer = routing.call_args_list
        pickup = (1, len('IAD'))
        stops = [(1, len('Keswick Hall')), (1, len('CHO'))]
        destination = (1, len('Charlottesville'))
        self.assertEqual(full.kwargs['origin'], HOME)
        self.assertEqual(full.kwargs['destination'], HOME)
        self.assertEqual(full.kwargs['waypoints'], [pickup, *stops, destination])
        self.assertEqual(customer.kwargs['origin'], pickup)
        self.assertEqual(customer.kwargs['destination'], destination)
        self.assertEqual(customer.kwargs['waypoints'], stops)
        self.assertEqual([stop['address'] for stop in result['stops']], ['Keswick Hall', 'CHO'])

    def test_empty_stops_are_ignored_and_no_option_keeps_original_quote(self):
        result, routing = self.quote(stops=['', '  '])
        self.assertEqual(result['stops'], [])
        self.assertEqual(result['quote'], 140)
        self.assertEqual(result['trip_price'], 140)
        self.assertEqual(result['additional_charge'], 0)
        self.assertEqual(routing.call_args_list[1].kwargs['waypoints'], [])

    def test_charge_is_added_and_final_equivalent_rates_are_returned(self):
        result, _ = self.quote(additional_charge=20)
        self.assertEqual(result['trip_price'], 140)
        self.assertEqual(result['quote'], 160)
        self.assertEqual(result['additional_charge'], 20)
        self.assertEqual(result['hourly_rate'], 80)
        self.assertEqual(result['mileage_rate'], 4)

    def test_invalid_charge_is_rejected_before_api_calls(self):
        for amount in (-1, 'nan', 'inf', 'not money'):
            with self.subTest(amount=amount), patch('app.geocode') as geocode:
                with self.assertRaises((ValueError, TypeError)):
                    make_quote({'pickup': 'IAD', 'destination': 'Charlottesville', 'additional_charge': amount})
                geocode.assert_not_called()

    def test_invalid_stops_are_rejected_before_api_calls(self):
        for stops in ('CHO', [None], [123], ['CHO'] * 149):
            with self.subTest(stops=repr(stops)[:20]), patch('app.geocode') as geocode:
                with self.assertRaises(ValueError):
                    make_quote({'pickup': 'IAD', 'destination': 'Charlottesville', 'stops': stops})
                geocode.assert_not_called()

    def test_reference_rates_follow_each_customer_leg(self):
        addresses = ['Keswick Hall', 'IAD', 'Charlottesville']
        reference = find_trip_reference_rates(addresses, [None] * 3)
        rate = next(rate for rate in reference['matches'] if rate['route'] == 'Keswick  to IAD')
        self.assertIn('Leg 1:', rate['match'])
        self.assertEqual(reference['pickup_notes'], [])
        no_direct_ride = find_trip_reference_rates(['Keswick Hall', 'CHO', 'IAD'], [None] * 3)
        self.assertFalse(any(rate['route'] == 'Keswick  to IAD' for rate in no_direct_ride['matches']))

    def test_pickup_time_still_applies_with_stops(self):
        pickup_time = '2026-10-24T14:00:00Z'
        with patch('app.geocode', return_value=(38, -78)), patch('app.calculate_route', side_effect=[
                {'minutes': 30}, {'minutes': 120, 'miles': 100}, {'minutes': 60, 'miles': 40}]) as routing:
            make_quote({'pickup': 'IAD', 'destination': 'Charlottesville', 'stops': ['CHO'], 'pickup_time': pickup_time})
        self.assertEqual(routing.call_args_list[1].kwargs['depart_at'], '2026-10-24T13:30:00+00:00')
        self.assertEqual(routing.call_args_list[2].kwargs['depart_at'], pickup_time)


if __name__ == '__main__':
    unittest.main()
