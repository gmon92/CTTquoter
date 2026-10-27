import http.client
import json
import struct
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.parse import urlencode
from unittest.mock import patch

from app import APP_DIR, Handler
from employee_access import EmployeeAccess


class PwaHTTPTests(unittest.TestCase):
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

    def request(self, path, method='GET', body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_manifest_and_all_icons_are_served_at_root_with_correct_types_and_sizes(self):
        status, headers, raw = self.request('/manifest.webmanifest')
        self.assertEqual(status, 200)
        self.assertEqual(headers['Content-Type'], 'application/manifest+json')
        manifest = json.loads(raw)
        self.assertEqual((manifest['display'], manifest['start_url'], manifest['scope']), ('standalone', '/', '/'))
        for icon in manifest['icons'] + [{'src': '/icons/apple-touch-icon.png', 'sizes': '180x180'}]:
            with self.subTest(icon=icon):
                status, headers, png = self.request(icon['src'])
                self.assertEqual(status, 200)
                self.assertEqual(headers['Content-Type'], 'image/png')
                self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')
                width, height = struct.unpack('>II', png[16:24])
                self.assertEqual(f'{width}x{height}', icon['sizes'])
                self.assertEqual(png[25], 2, 'Icons must be opaque RGB PNGs')

    def test_apple_metadata_and_touch_controls_are_present(self):
        status, headers, raw = self.request('/')
        self.assertEqual(status, 200)
        page = raw.decode()
        for marker in ['viewport-fit=cover', 'apple-mobile-web-app-capable', 'apple-touch-icon',
                       'rel="manifest"', 'inputmode="decimal"', 'safe-area-inset-bottom']:
            self.assertIn(marker, page)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')

    def test_worker_and_offline_assets_are_served_without_api_calls(self):
        with patch('app.make_quote') as quote, patch('app.fetch_map_tile') as tile:
            for path in ['/sw.js', '/pwa.js', '/offline.html']:
                status, headers, _ = self.request(path)
                self.assertEqual(status, 200)
                if path == '/sw.js':
                    self.assertEqual(headers['Service-Worker-Allowed'], '/')
                    self.assertEqual(headers['Cache-Control'], 'no-store')
            quote.assert_not_called()
            tile.assert_not_called()

    def test_allowlist_does_not_serve_arbitrary_project_files(self):
        for path in ['/.env', '/Taxi%20Pricing.xlsx', '/app.py', '/icons/../app.py', '/static/login.html', '/icons/missing.png']:
            self.assertEqual(self.request(path)[0], 404, path)

    def test_repricing_api_uses_python_without_routing(self):
        with patch('app.calculate_route') as routing:
            status, headers, body = self.request('/api/reprice', 'POST', json.dumps({
                'total_driver_minutes': 120, 'one_way_miles': 40, 'edited': 'hourly_rate',
                'value': 85, 'additional_charge': 20, 'include_tip': True}), {'Content-Type': 'application/json'})
            self.assertEqual(status, 200)
            self.assertEqual(headers['Cache-Control'], 'no-store')
            result = json.loads(body)
            self.assertEqual((result['quote'], result['trip_price'], result['tip_amount']), (170, 150, 34))
            routing.assert_not_called()

    def test_existing_quote_route_keeps_initial_business_rules(self):
        for headers in ({'Content-Type': 'application/json'}, {}):
            with self.subTest(headers=headers), patch('app.geocode', return_value=(38, -78)), patch('app.calculate_route', side_effect=[
                {'minutes': 120, 'miles': 100}, {'minutes': 60, 'miles': 40}]):
                status, _, body = self.request('/api/quote', 'POST', json.dumps({
                    'pickup': 'IAD', 'destination': 'Keswick', 'additional_charge': 20, 'include_tip': True}), headers)
                self.assertEqual(status, 200)
                result = json.loads(body)
                self.assertEqual((result['trip_price'], result['quote'], result['tip_amount'], result['all_inclusive_price']), (140, 160, 32, 192))

    def test_json_and_same_origin_validation(self):
        self.assertEqual(self.request('/api/reprice', 'POST', '{}')[0], 415)
        self.assertEqual(self.request('/api/reprice', 'POST', '[]', {'Content-Type': 'application/json'})[0], 400)
        self.assertEqual(self.request('/api/reprice', 'POST', '{}', {'Origin': 'https://other.example'})[0], 403)

    def test_existing_unlisted_https_origin_does_not_require_new_settings(self):
        origin = f'https://127.0.0.1:{self.server.server_port}'
        payload = {'total_driver_minutes': 120, 'one_way_miles': 40, 'edited': 'quote', 'value': 170}
        status, _, _ = self.request('/api/reprice', 'POST', json.dumps(payload),
                                    {'Content-Type': 'application/json', 'Origin': origin})
        self.assertEqual(status, 200)

    def test_optional_login_blocks_quote_tiles_and_home_before_outbound_requests(self):
        self.server.employee_access = EmployeeAccess('a-long-test-team-password')
        with patch('app.make_quote') as quote, patch('app.fetch_map_tile') as tile:
            self.assertEqual(self.request('/')[0], 303)
            self.assertEqual(self.request('/api/tiles/0/0/0.png')[0], 401)
            self.assertEqual(self.request('/api/quote', 'POST', '{}', {'Content-Type': 'application/json'})[0], 401)
            self.assertEqual(self.request('/api/reprice', 'POST', '{}', {'Content-Type': 'application/json'})[0], 401)
            for path in ['/health', '/manifest.webmanifest', '/icons/apple-touch-icon.png', '/sw.js', '/login']:
                self.assertEqual(self.request(path)[0], 200)
            quote.assert_not_called()
            tile.assert_not_called()

    def test_login_cookie_expiry_and_logout(self):
        access = self.server.employee_access = EmployeeAccess('a-long-test-team-password')
        status, headers, _ = self.request('/login', 'POST', urlencode({'password': access.password}))
        self.assertEqual(status, 303)
        cookie = headers['Set-Cookie']
        self.assertIn('HttpOnly', cookie)
        self.assertIn('SameSite=Strict', cookie)
        cookie = cookie.split(';')[0]
        status, _, body = self.request('/', headers={'Cookie': cookie})
        self.assertEqual(status, 200)
        self.assertIn(b'action="/logout"', body)
        self.assertEqual(self.request('/logout', 'POST', headers={'Cookie': cookie})[0], 303)
        self.assertEqual(self.request('/', headers={'Cookie': cookie})[0], 303)
        token, _ = access.login(access.password, 'test')
        access.sessions[token] = 0
        self.assertEqual(self.request('/', headers={'Cookie': f'ctt_session={token}'})[0], 303)

    def test_login_throttles_failures_and_rejects_cross_origin(self):
        self.server.employee_access = EmployeeAccess('a-long-test-team-password')
        self.assertEqual(self.request('/login', 'POST', 'password=x', {'Origin': 'https://other.example'})[0], 403)
        for _ in range(5):
            self.assertEqual(self.request('/login', 'POST', 'password=wrong')[0], 401)
        self.assertEqual(self.request('/login', 'POST', 'password=wrong')[0], 429)

    def test_https_origin_enables_secure_cookies_and_rejects_spoofed_origin(self):
        access = self.server.employee_access = EmployeeAccess('a-long-test-team-password', 'https://quotes.example.com')
        status, headers, _ = self.request('/login', 'POST', urlencode({'password': access.password}), {'Origin': access.origin})
        self.assertEqual(status, 303)
        self.assertIn('; Secure', headers['Set-Cookie'])
        self.assertEqual(headers['Strict-Transport-Security'], 'max-age=31536000')
        self.assertEqual(self.request('/login', 'POST', 'password=x', {'Origin': 'http://quotes.example.com', 'X-Forwarded-Proto': 'https'})[0], 403)

    def test_invalid_public_auth_configuration_fails_closed_at_startup(self):
        with patch.dict('os.environ', {'QUOTER_ACCESS_PASSWORD': 'a-long-test-team-password', 'QUOTER_PUBLIC_ORIGIN': ''}):
            with self.assertRaisesRegex(ValueError, 'QUOTER_PUBLIC_ORIGIN'):
                EmployeeAccess.from_environment('0.0.0.0')
        for password, origin in [('short', ''), ('a-long-test-team-password', 'http://example.com'),
                                 ('a-long-test-team-password', 'https://example.com/path')]:
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                EmployeeAccess(password, origin)


if __name__ == '__main__':
    unittest.main()
