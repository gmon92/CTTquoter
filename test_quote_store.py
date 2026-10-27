import json
import tempfile
import threading
from http.server import ThreadingHTTPServer
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from app import Handler
from employee_access import EmployeeAccess
from quote_store import QuoteStore, storage_path
from accounts import AccountContext, SHARED_TEAM


def quote_payload(**changes):
    payload = {'name': 'Smith airport pickup', 'notes': 'Two bags',
               'trip': {'pickup': 'CHO', 'destination': 'Keswick Hall',
                        'stops': [{'address': 'Boar’s Head Resort'}], 'vehicle': 'sedan',
                        'pickup_time': '2026-10-28T14:30:00Z',
                        'full_cycle': {'minutes': 120, 'miles': 100},
                        'one_way': {'minutes': 60, 'miles': 40}},
               'pricing': {'quote': 160, 'additional_charge': 20, 'include_tip': True}}
    payload.update(changes)
    return payload


class QuoteStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'private' / 'quotes.sqlite3'
        self.store = QuoteStore(self.path)

    def test_save_survives_new_store_and_keeps_all_historical_fields(self):
        record = self.store.save(SHARED_TEAM, quote_payload())
        reopened = QuoteStore(self.path).get(SHARED_TEAM, record['id'])
        self.assertEqual(record, reopened)
        self.assertEqual(reopened['stops'], ['Boar’s Head Resort'])
        self.assertEqual(reopened['pickup_time'], '2026-10-28T14:30:00+00:00')
        self.assertEqual(reopened['notes'], 'Two bags')
        self.assertEqual(reopened['pricing']['all_inclusive_price'], 192)
        self.assertEqual(reopened['pricing']['hourly_rate'], 80)
        self.assertEqual(reopened['pricing']['mileage_rate'], 4)
        self.assertIn('+00:00', record['created_at'])

    def test_saved_money_is_computed_by_server_and_stays_fixed(self):
        payload = quote_payload()
        payload['pricing'].update({'tip_amount': 0, 'all_inclusive_price': 1, 'hourly_rate': 1})
        record = self.store.save(SHARED_TEAM, payload)
        payload['pricing']['quote'] = 500
        stored = self.store.get(SHARED_TEAM, record['id'])
        self.assertEqual(stored['pricing']['tip_amount'], 32)
        self.assertEqual(stored['pricing']['all_inclusive_price'], 192)

    def test_initial_route_and_adjusted_rates_keep_their_existing_rounding(self):
        payload = quote_payload()
        payload['trip']['full_cycle']['minutes'] = 360
        payload['trip']['one_way']['miles'] = 160
        payload['pricing'] = {'quote': 420, 'additional_charge': 0, 'include_tip': False, 'pricing_origin': 'route'}
        original = self.store.save(SHARED_TEAM, payload)
        self.assertEqual(original['pricing']['mileage_rate'], 2.62)
        payload['pricing']['pricing_origin'] = 'adjustment'
        adjusted = self.store.save(SHARED_TEAM, payload)
        self.assertEqual(adjusted['pricing']['mileage_rate'], 2.63)

    def test_search_names_routes_stops_notes_unicode_and_literal_sql_characters(self):
        first = self.store.save(SHARED_TEAM, quote_payload(name='José 100% pickup', notes="Customer's bags"))
        self.store.save(SHARED_TEAM, quote_payload(name='Other quote', notes='none', trip={**quote_payload()['trip'], 'stops': [], 'pickup': 'RIC', 'destination': 'UVA'}))
        for query in ['JOSÉ', '100%', "Customer's", 'Boar’s Head', 'Keswick']:
            self.assertEqual([r['id'] for r in self.store.list(SHARED_TEAM, query)['quotes']], [first['id']])
        self.assertEqual(self.store.list(SHARED_TEAM, "' OR 1=1 --")['quotes'], [])

    def test_pagination_and_delete_preserve_other_records(self):
        records = [self.store.save(SHARED_TEAM, quote_payload(name=str(i))) for i in range(4)]
        page1 = self.store.list(SHARED_TEAM, limit=2)
        page2 = self.store.list(SHARED_TEAM, limit=2, offset=2)
        self.assertTrue(page1['has_more'])
        self.assertFalse(page2['has_more'])
        self.assertEqual(len({r['id'] for r in [*page1['quotes'], *page2['quotes']]}), 4)
        self.assertTrue(self.store.delete(SHARED_TEAM, records[0]['id']))
        self.assertFalse(self.store.delete(SHARED_TEAM, records[0]['id']))
        self.assertIsNone(self.store.get(SHARED_TEAM, records[0]['id']))
        self.assertEqual(len(self.store.list(SHARED_TEAM)['quotes']), 3)

    def test_concurrent_saves_keep_distinct_records(self):
        with ThreadPoolExecutor(max_workers=4) as workers:
            records = list(workers.map(lambda i: self.store.save(SHARED_TEAM, quote_payload(name=str(i))), range(8)))
        self.assertEqual(len({r['id'] for r in records}), 8)
        self.assertEqual(len(self.store.list(SHARED_TEAM)['quotes']), 8)

    def test_invalid_snapshots_create_no_database(self):
        invalid = []
        for changes in ({'name': ''}, {'name': 'x'*121}, {'notes': 'x'*10001}, {'trip': None}, {'pricing': None}):
            invalid.append(quote_payload(**changes))
        for branch, key, value in [('trip', 'pickup', ''), ('trip', 'stops', [None]), ('trip', 'pickup_time', 'tomorrow'),
                                   ('trip', 'pickup_time', '2026-10-28T14:30:00'), ('pricing', 'quote', 'nan'),
                                   ('pricing', 'quote', 10), ('pricing', 'include_tip', 'yes')]:
            item = quote_payload()
            item[branch][key] = value
            invalid.append(item)
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises((ValueError, TypeError)):
                self.store.save(SHARED_TEAM, payload)
        self.assertFalse(self.path.exists())

    def test_configured_data_directory_is_used(self):
        with patch.dict('os.environ', {'QUOTER_DATA_DIR': str(self.path.parent)}):
            self.assertEqual(storage_path(), self.path)

    def test_profile_and_workspace_isolation_and_ownership_cannot_be_spoofed(self):
        alice = AccountContext('alice', 'alice-profile', 'ctt', 'Alice')
        bob = AccountContext('bob', 'bob-profile', 'ctt', 'Bob')
        other_workspace = AccountContext('alice', 'alice-profile', 'other-company', 'Alice')
        payload = quote_payload(profile_id=bob.profile_id, workspace_id='other-company', created_by='bob')
        record = self.store.save(alice, payload)
        for other in (bob, other_workspace, SHARED_TEAM):
            self.assertEqual(self.store.list(other)['quotes'], [])
            self.assertIsNone(self.store.get(other, record['id']))
            self.assertFalse(self.store.delete(other, record['id']))
        self.assertEqual(self.store.get(alice, record['id'])['id'], record['id'])
        with self.assertRaises(ValueError):
            self.store.save(None, payload)


class SavedQuoteHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def setUp(self):
        self.server.employee_access = EmployeeAccess()
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.server.quote_store = QuoteStore(Path(folder.name) / 'quotes.sqlite3')

    def request(self, path, method='GET', body=None, headers=None):
        import http.client
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_http_saved_lifecycle(self):
        headers = {'Content-Type': 'application/json'}
        status, response_headers, raw = self.request('/api/saved-quotes', 'POST', json.dumps(quote_payload()), headers)
        self.assertEqual(status, 201)
        self.assertEqual(response_headers['Cache-Control'], 'no-store')
        record = json.loads(raw)
        path = '/api/saved-quotes/' + record['id']
        self.assertEqual(json.loads(self.request(path)[2]), record)
        self.assertEqual(len(json.loads(self.request('/api/saved-quotes?q=SMITH')[2])['quotes']), 1)
        self.assertEqual(self.request(path, 'DELETE')[0], 200)
        self.assertEqual(self.request(path)[0], 404)
        self.assertEqual(self.request(path, 'DELETE')[0], 404)

    def test_saved_routes_require_signin_and_same_origin(self):
        self.server.employee_access = EmployeeAccess('a-long-test-team-password')
        for method, path in [('GET', '/api/saved-quotes'), ('GET', '/api/saved-quotes/'+'a'*32),
                             ('POST', '/api/saved-quotes'), ('DELETE', '/api/saved-quotes/'+'a'*32)]:
            self.assertEqual(self.request(path, method, '{}', {'Content-Type': 'application/json'})[0], 401)
        self.server.employee_access = EmployeeAccess()
        for method, path in [('POST', '/api/saved-quotes'), ('DELETE', '/api/saved-quotes/'+'a'*32)]:
            self.assertEqual(self.request(path, method, '{}', {'Origin': 'https://other.example'})[0], 403)
        self.assertEqual(self.request('/data/quotes.sqlite3')[0], 404)

    def test_history_validation_and_storage_failures(self):
        self.assertEqual(self.request('/api/saved-quotes?offset=-1')[0], 400)
        self.assertEqual(self.request('/api/saved-quotes?offset=bad')[0], 400)
        self.assertEqual(self.request('/api/saved-quotes/not-an-id')[0], 404)
        self.assertEqual(self.request('/api/saved-quotes', 'POST', '{}', {'Content-Type': 'application/json'})[0], 400)
        with patch.object(self.server.quote_store, 'save', side_effect=OSError('full disk')):
            self.assertEqual(self.request('/api/saved-quotes', 'POST', json.dumps(quote_payload()), {'Content-Type': 'application/json'})[0], 503)
        with patch.object(self.server.quote_store, 'list', side_effect=OSError('unavailable')):
            self.assertEqual(self.request('/api/saved-quotes')[0], 503)

    def test_api_binds_ownership_to_authenticated_account_adapter(self):
        alice = AccountContext('alice', 'alice-profile', 'ctt', 'Alice')
        bob = AccountContext('bob', 'bob-profile', 'ctt', 'Bob')
        # Stand in for a future account provider; the storage and HTTP API stay unchanged.
        self.server.employee_access.current_account = lambda cookie: {'alice-session': alice, 'bob-session': bob}.get(cookie)
        headers = {'Content-Type': 'application/json', 'Cookie': 'alice-session'}
        status, _, raw = self.request('/api/saved-quotes', 'POST', json.dumps(quote_payload(profile_id='bob-profile')), headers)
        self.assertEqual(status, 201)
        record = json.loads(raw)
        for method in ('GET', 'DELETE'):
            self.assertEqual(self.request('/api/saved-quotes/'+record['id'], method, headers={'Cookie': 'bob-session'})[0], 404)
        self.assertEqual(json.loads(self.request('/api/saved-quotes', headers={'Cookie': 'bob-session'})[2])['quotes'], [])
        status, _, raw = self.request('/api/account', headers={'Cookie': 'alice-session'})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)['profile']['display_name'], 'Alice')
        self.assertEqual(self.request('/api/account')[0], 401)


if __name__ == '__main__':
    unittest.main()
