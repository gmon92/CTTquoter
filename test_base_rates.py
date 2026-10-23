from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from app import make_quote
from base_rates import WORKBOOK, find_reference_rates, locations


def find(result, schedule, route):
    return next((rate for rate in result['matches']
                 if rate['schedule'] == schedule and rate['route'] == route), None)


class BaseRateTests(unittest.TestCase):
    def test_airport_code_and_name_show_labeled_schedules(self):
        for address in ('IAD', 'Washington Dulles International Airport, VA'):
            with self.subTest(address=address):
                result = find_reference_rates(address, 'Charlottesville, VA')
                self.assertEqual(result['status'], 'ok')
                airport = find(result, 'Airports', 'IAD')
                self.assertEqual((airport['sedan'], airport['suv']), (295, 355))
                aa = find(result, 'AA (All Inclusive)', 'IAD')
                self.assertEqual((aa['sedan'], aa['suv']), (355, 430))

    def test_specific_route_requires_both_ends_in_either_direction(self):
        for pickup, destination in [('Keswick Hall', 'IAD'), ('IAD', 'Keswick Hall')]:
            with self.subTest(pickup=pickup):
                rate = find(find_reference_rates(pickup, destination), 'Airports', 'Keswick  to IAD')
                self.assertIsNotNone(rate)
                self.assertEqual((rate['sedan'], rate['suv']), (315, 395))
        self.assertIsNone(find(find_reference_rates('Charlottesville', 'IAD'), 'Airports', 'Keswick  to IAD'))

    def test_aliases_and_missing_vehicle_rate(self):
        result = find_reference_rates("Boar's Head Resort", 'CHO')
        self.assertIsNotNone(find(result, 'Airports', 'Farmington/ BHI to CHO'))
        miller = find(find_reference_rates('Miller School of Albemarle', 'CHO'), 'Misc', 'Miller school to CHO')
        self.assertEqual(miller['sedan'], 95)
        self.assertIsNone(miller['suv'])

    def test_single_amount_in_combined_column_is_preserved(self):
        rate = find(find_reference_rates('Lynchburg', 'Charlottesville'), 'AA (All Inclusive)', 'Lynchburg')
        self.assertEqual(rate['shared_rate'], 285)
        self.assertIsNone(rate['sedan'])
        self.assertIsNone(rate['suv'])

    def test_airport_street_address_can_match_by_location(self):
        result = find_reference_rates('1 Saarinen Circle, VA', 'Charlottesville', (38.9531, -77.4565))
        rate = find(result, 'Airports', 'IAD')
        self.assertIn('near IAD', rate['match'])

    def test_codes_are_whole_tokens_and_airport_is_not_city_proper(self):
        self.assertNotIn('CHO', locations('123 School Road'))
        self.assertNotIn('Cville', locations('Charlottesville-Albemarle Airport'))
        self.assertEqual(find_reference_rates('123 School Road', '456 Elm Street')['matches'], [])

    def test_pickup_notes_only_apply_to_pickup_airport(self):
        pickup = find_reference_rates('CHO', 'Charlottesville')['pickup_notes']
        self.assertEqual(pickup[0]['base'], 'Base $65')
        self.assertIn('6-10PM: ADD $20', pickup[0]['items'])
        self.assertTrue(any('plane delays' in item for item in pickup[0]['items']))
        self.assertEqual(find_reference_rates('Charlottesville', 'CHO')['pickup_notes'], [])

    def test_reads_updated_rates_from_excel(self):
        namespace = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        with tempfile.TemporaryDirectory() as folder:
            updated = Path(folder) / 'Taxi Pricing.xlsx'
            with ZipFile(WORKBOOK) as original, ZipFile(updated, 'w') as output:
                for name in original.namelist():
                    data = original.read(name)
                    if name == 'xl/worksheets/sheet1.xml':
                        sheet = ET.fromstring(data)
                        sheet.find(".//s:c[@r='A7']/s:v", namespace).text = '301'
                        data = ET.tostring(sheet)
                    output.writestr(name, data)
            rate = find(find_reference_rates('IAD', 'Charlottesville', path=updated), 'Airports', 'IAD')
            self.assertEqual(rate['sedan'], 301)

    def test_missing_or_invalid_workbook_has_clear_status(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'Taxi Pricing.xlsx'
            self.assertEqual(find_reference_rates('IAD', 'Charlottesville', path=path)['status'], 'unavailable')
            path.write_text('invalid spreadsheet', encoding='utf-8')
            self.assertEqual(find_reference_rates('IAD', 'Charlottesville', path=path)['status'], 'unavailable')

    def test_reference_rate_does_not_replace_calculated_quote(self):
        full = {'minutes': 120, 'miles': 100}
        one_way = {'minutes': 60, 'miles': 40}
        with patch('app.geocode', return_value=(38.03, -78.49)), patch('app.calculate_route', side_effect=[full, one_way]):
            result = make_quote({'pickup': 'IAD', 'destination': 'Charlottesville'})
        self.assertEqual(result['quote'], 140)
        self.assertEqual(find(result['base_rate_reference'], 'Airports', 'IAD')['sedan'], 295)


if __name__ == '__main__':
    unittest.main()
