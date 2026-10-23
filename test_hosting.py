import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from app import Handler, server_settings


class HostingTests(unittest.TestCase):
    def test_local_defaults_preserve_desktop_launchers(self):
        self.assertEqual(server_settings({}), ('127.0.0.1', 8765, True))

    def test_cloud_uses_platform_port_and_disables_browser(self):
        self.assertEqual(server_settings({'PORT': '10000', 'QUOTER_HOST': '0.0.0.0',
                                         'QUOTER_OPEN_BROWSER': '0'}), ('0.0.0.0', 10000, False))

    def test_external_binding_does_not_open_a_desktop_browser(self):
        self.assertEqual(server_settings({'QUOTER_HOST': '0.0.0.0'})[2], False)

    def test_invalid_port_has_clear_error(self):
        for port in ('invalid', '0', '65536'):
            with self.subTest(port=port), self.assertRaisesRegex(ValueError, 'PORT must be'):
                server_settings({'PORT': port})

    def test_health_and_homepage_do_not_require_tomtom_and_discourage_indexing(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch('app.make_quote') as quote, patch('app.fetch_map_tile') as tile:
                for path in ('/health', '/'):
                    connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                    connection.request('GET', path)
                    response = connection.getresponse()
                    body = response.read().decode()
                    self.assertEqual(response.status, 200)
                    self.assertIn('noindex', response.getheader('X-Robots-Tag'))
                    if path == '/health':
                        self.assertEqual(json.loads(body), {'status': 'ok'})
                    else:
                        self.assertIn('name="robots" content="noindex', body)
                    connection.close()
                quote.assert_not_called()
                tile.assert_not_called()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
