import json
import unittest
from unittest.mock import patch, MagicMock
from urllib.parse import unquote

from address_aliases import AIRPORT_ADDRESSES, LOCATION_ADDRESSES, resolve_address
from app import geocode, make_quote


class AddressAliasTests(unittest.TestCase):
    def test_airport_codes_ignore_case_whitespace_and_optional_airport_suffix(self):
        for code, address in AIRPORT_ADDRESSES.items():
            for text in (code, f'  {code.lower()}  ', f'{code.lower()} airport'):
                with self.subTest(text=text):
                    self.assertEqual(resolve_address(text), address)
                    self.assertEqual(resolve_address(address), address)

    def test_does_not_replace_parts_of_street_addresses_or_guess_unknown_codes(self):
        for address in ('123 CHO Road', 'RIC Hotel', 'XYZ', 'Lynchburg'):
            self.assertEqual(resolve_address(address), address)
        self.assertEqual(resolve_address('  910 Anderson St  '), '910 Anderson St')

    def test_local_shortcuts_expand_exact_matches_only(self):
        for shortcut, address in LOCATION_ADDRESSES.items():
            for text in (shortcut, f'  {shortcut.lower()}  '):
                with self.subTest(text=text):
                    self.assertEqual(resolve_address(text), address)
            self.assertEqual(resolve_address(address), address)
        for text in ('123 Farmington Road', 'Keswick Road', 'BHI airport'):
            self.assertEqual(resolve_address(text), text)

    def test_local_shortcuts_flow_through_pickup_stop_and_destination(self):
        route = {'minutes': 60, 'miles': 40}
        with patch('app.geocode', return_value=(38, -78)) as lookup, \
                patch('app.calculate_route', return_value=route):
            result = make_quote({'pickup': 'bhi', 'destination': 'farmington', 'stops': ['keswick']})
        self.assertEqual([call.args[0] for call in lookup.call_args_list],
                         [LOCATION_ADDRESSES[key] for key in ('BHI', 'KESWICK', 'FARMINGTON')])
        self.assertEqual(result['pickup'], LOCATION_ADDRESSES['BHI'])
        self.assertEqual(result['destination'], LOCATION_ADDRESSES['FARMINGTON'])
        self.assertEqual(result['stops'][0]['address'], LOCATION_ADDRESSES['KESWICK'])

    def test_geocoder_searches_expanded_address(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            'results': [{'position': {'lat': 38.1396, 'lon': -78.4529}}]
        }).encode()
        with patch.dict('os.environ', {'TOMTOM_API_KEY': 'test-key'}), \
                patch('app.urlopen', return_value=response) as fetch:
            self.assertEqual(geocode('cho'), (38.1396, -78.4529))
        self.assertIn(AIRPORT_ADDRESSES['CHO'], unquote(fetch.call_args.args[0].full_url))

    def test_expands_pickup_destination_and_stops_before_routing_and_display(self):
        route = {'minutes': 60, 'miles': 40}
        with patch('app.geocode', return_value=(38, -78)) as lookup, \
                patch('app.calculate_route', return_value=route):
            result = make_quote({'pickup': ' cho ', 'destination': 'iad', 'stops': ['ric']})
        self.assertEqual([call.args[0] for call in lookup.call_args_list],
                         [AIRPORT_ADDRESSES[code] for code in ('CHO', 'RIC', 'IAD')])
        self.assertEqual(result['pickup'], AIRPORT_ADDRESSES['CHO'])
        self.assertEqual(result['destination'], AIRPORT_ADDRESSES['IAD'])
        self.assertEqual(result['stops'][0]['address'], AIRPORT_ADDRESSES['RIC'])


if __name__ == '__main__':
    unittest.main()

class AddressErrorTests(unittest.TestCase):
    def test_reports_all_unreadable_fields_with_matching_stop_indexes(self):
        from app import AddressErrors, geocode_fields
        with patch('app.geocode', side_effect=[ValueError('missing'), (38, -78), ValueError('missing'), ValueError('missing')]):
            with self.assertRaises(AddressErrors) as caught:
                geocode_fields('bad pickup', ['good stop', 'bad stop'], 'bad destination')
        self.assertEqual(set(caught.exception.fields), {'pickup', 'stops.1', 'destination'})

    def test_lookup_400_is_associated_with_destination(self):
        from app import AddressErrors, geocode_fields
        from urllib.error import HTTPError
        with patch('app.geocode', side_effect=[(38, -78), HTTPError('https://example.test', 400, 'Bad Request', {}, None)]):
            with self.assertRaises(AddressErrors) as caught:
                geocode_fields('valid pickup', [], 'bad destination')
        self.assertIn('HTTP 400', caught.exception.fields['destination'])

    def test_empty_required_addresses_are_field_errors(self):
        from app import AddressErrors, geocode_fields
        with patch('app.geocode') as lookup:
            with self.assertRaises(AddressErrors) as caught:
                geocode_fields('', [], '')
        lookup.assert_not_called()
        self.assertEqual(set(caught.exception.fields), {'pickup', 'destination'})
