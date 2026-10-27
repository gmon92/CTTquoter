"""Optional browser tests: pip install -r requirements-dev.txt, then run this file."""
import os
import threading
import tempfile
from pathlib import Path
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from playwright.sync_api import sync_playwright, expect

from app import Handler, HOME
from employee_access import EmployeeAccess
from quote_store import QuoteStore
from accounts import SHARED_TEAM


class BrowserHandler(Handler):
    def do_GET(self):
        if getattr(self.server, 'drop_connections', False):
            # A real failed upstream fetch exercises service-worker fallback.
            # WebKit's context.set_offline() can abort navigation before the SW.
            self.close_connection = True
            return
        super().do_GET()


def route_fixture(*, origin, destination, waypoints=None, **_):
    full = origin == HOME and destination == HOME
    return {'minutes': 120 if full else 60, 'miles': 100 if full else 40,
            'points': [[38.036, -78.491], [38.14, -78.45], [38.03, -78.5]]}


class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.geocode = patch('app.geocode', return_value=(38.14, -78.45))
        cls.routes = patch('app.calculate_route', side_effect=route_fixture)
        cls.tiles = patch('app.fetch_map_tile', return_value=(b'', 'image/png'))
        for mock in (cls.geocode, cls.routes, cls.tiles):
            mock.start()
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), BrowserHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'
        cls.playwright = sync_playwright().start()
        cls.browser = getattr(cls.playwright, os.environ.get('CTT_TEST_BROWSER', 'chromium')).launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        for mock in (cls.geocode, cls.routes, cls.tiles):
            mock.stop()

    def setUp(self):
        self.server.drop_connections = False
        self.server.employee_access = EmployeeAccess()
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.server.quote_store = QuoteStore(Path(folder.name) / 'quotes.sqlite3')
        self.context = self.browser.new_context(**self.playwright.devices['iPhone 13'])
        # Keep these tests deterministic; map service behavior has its own unit tests.
        self.context.route('https://unpkg.com/**', lambda route: route.abort())
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(error))
        self.page.goto(self.url)

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [])

    def quote(self):
        self.page.locator('#pickup').fill('CHO')
        self.page.locator('#destination').fill('Keswick')
        self.page.locator('#calculate_button').click()
        expect(self.page.locator('#fare_total')).to_have_text('$140.00')

    def test_mobile_and_desktop_layout_touch_controls_and_original_quote(self):
        self.quote()
        expect(self.page.locator('#customer_itinerary')).to_contain_text('Keswick Hall')
        expect(self.page.locator('#base_rate_references')).to_contain_text('Base rates from your Excel file')
        for width in (320, 375, 390, 430, 1280):
            self.page.set_viewport_size({'width': width, 'height': 844})
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'), f'Overflow at {width}')
            self.assertGreaterEqual(self.page.locator('#calculate_button').bounding_box()['height'], 48)
        for selector in ('#hourly_rate', '#mileage_rate', '#final_quote'):
            expect(self.page.locator(selector)).to_have_attribute('inputmode', 'decimal')
            self.assertGreaterEqual(float(self.page.locator(selector).evaluate('e=>parseFloat(getComputedStyle(e).fontSize)')), 16)
        # Recalculate at desktop width to check desktop-specific initial state.
        self.page.locator('#calculate_button').click()
        expect(self.page.locator('#fare_total')).to_have_text('$140.00')
        self.assertTrue(self.page.locator('#base_rate_details').evaluate('e=>e.open'))
        self.assertEqual(self.page.locator('.rates').evaluate("e=>getComputedStyle(e).gridTemplateColumns.split(' ').length"), 3)

    def test_stops_charge_tip_linked_rates_slider_and_comparison(self):
        self.page.locator('#include_stops').check()
        self.page.locator('.extra-stop-address').fill('BHI')
        self.quote()
        expect(self.page.locator('#customer_itinerary')).to_contain_text('Boar')
        self.page.locator('#include_charge').check()
        self.page.locator('#additional_charge').fill('20')
        expect(self.page.locator('#fare_total')).to_have_text('$160.00')
        self.page.locator('#include_tip').check()
        expect(self.page.locator('#fare_total')).to_have_text('$192.00')
        self.page.locator('#hourly_rate').fill('85')
        expect(self.page.locator('#final_quote')).to_have_value('170.00')
        expect(self.page.locator('#mileage_rate')).to_have_value('4.25')
        expect(self.page.locator('#fare_total')).to_have_text('$204.00')
        self.page.locator('#mileage_rate').fill('5')
        expect(self.page.locator('#fare_total')).to_have_text('$240.00')
        expect(self.page.locator('#hourly_rate')).to_have_value('100.00')
        self.page.locator('#final_quote').fill('100')
        expect(self.page.locator('#fare_total')).to_have_text('$120.00')
        self.page.locator('#quote_slider').evaluate("e=>{e.value='180';e.dispatchEvent(new Event('input',{bubbles:true}));}")
        expect(self.page.locator('#fare_total')).to_have_text('$216.00')
        self.page.locator('#add_comparison').click()
        expect(self.page.locator('#comparison_table')).to_contain_text('$216.00')
        self.page.locator('#final_quote').fill('200')
        expect(self.page.locator('#fare_total')).to_have_text('$240.00')
        expect(self.page.locator('#comparison_table')).to_contain_text('$216.00')

    def test_quick_rate_then_charge_uses_ordered_server_results(self):
        self.quote()
        # Both changes happen before the input debounce timer fires.
        self.page.evaluate("""() => {
          const hourly=document.getElementById('hourly_rate');hourly.value='85';hourly.dispatchEvent(new Event('input'));
          const toggle=document.getElementById('include_charge');toggle.checked=true;toggle.dispatchEvent(new Event('change'));
          const charge=document.getElementById('additional_charge');charge.value='20';charge.dispatchEvent(new Event('input'));
        }""")
        expect(self.page.locator('#fare_total')).to_have_text('$190.00')
        expect(self.page.locator('#trip_price_text')).to_have_text('170.00')

    def test_failed_repricing_is_not_saved_and_can_retry(self):
        self.quote()
        self.context.set_offline(True)
        self.page.locator('#hourly_rate').fill('85')
        expect(self.page.locator('#fare_total')).to_have_text('Price unavailable')
        expect(self.page.locator('#add_comparison')).to_be_disabled()
        expect(self.page.locator('#retry_pricing')).to_be_visible()
        expect(self.page.locator('#tip_breakdown')).to_be_hidden()
        self.context.set_offline(False)
        self.page.locator('#retry_pricing').click()
        expect(self.page.locator('#fare_total')).to_have_text('$170.00')
        expect(self.page.locator('#add_comparison')).to_be_enabled()

    def test_worker_registers_and_offline_launch_does_not_reveal_cached_quotes(self):
        self.quote()
        self.page.evaluate('navigator.serviceWorker.ready')
        self.page.wait_for_function('navigator.serviceWorker.controller !== null')
        names = self.page.evaluate("async()=>{const c=await caches.open('ctt-public-v1');return (await c.keys()).map(r=>new URL(r.url).pathname)}")
        self.assertIn('/offline.html', names)
        self.assertFalse(any(path.startswith('/api/') or path in ('/', '/index.html', '/login') for path in names))
        self.server.drop_connections = True
        try:
            self.page.reload()
            expect(self.page.get_by_role('heading', name='You’re offline')).to_be_visible()
            expect(self.page.locator('#fare_total')).to_have_count(0)
        finally:
            self.server.drop_connections = False
        self.page.get_by_role('link', name='Try again').click()
        expect(self.page.locator('#pickup')).to_have_value('')

    def test_team_sign_in_and_logout_guard_the_api(self):
        self.server.employee_access = EmployeeAccess('a-long-browser-test-password')
        self.page.reload()
        expect(self.page.get_by_role('button', name='Sign in', exact=True)).to_be_visible()
        self.assertEqual(self.context.request.post(self.url+'/api/reprice', data={}).status, 401)
        self.page.locator('#password').fill('a-long-browser-test-password')
        self.page.get_by_role('button', name='Sign in', exact=True).click()
        self.quote()
        cookies = self.context.cookies()
        session = next(cookie for cookie in cookies if cookie['name'] == 'ctt_session')
        self.assertTrue(session['httpOnly'])
        self.assertEqual(session['sameSite'], 'Strict')
        self.page.get_by_role('button', name='Sign out', exact=True).click()
        expect(self.page.get_by_role('button', name='Sign in', exact=True)).to_be_visible()
        self.assertEqual(self.context.request.get(self.url+'/api/tiles/0/0/0.png').status, 401)

    def test_pending_price_response_cannot_restore_a_cleared_quote(self):
        self.quote()
        self.page.evaluate("""() => {
          const original=window.fetch;window.fetch=async(...args)=>{
            const response=await original(...args);
            if(args[0]==='/api/reprice') await new Promise(r=>setTimeout(r,350));
            return response;
          };
        }""")
        with self.page.expect_request('**/api/reprice'):
            self.page.locator('#hourly_rate').fill('85')
        self.page.get_by_role('button', name='New quote / clear all', exact=True).click()
        self.page.wait_for_timeout(500)
        expect(self.page.locator('#fare_total')).to_have_count(0)
        expect(self.page.locator('#pickup')).to_have_value('')

    def test_expired_session_blocks_price_updates_and_offers_sign_in(self):
        self.server.employee_access = EmployeeAccess('a-long-browser-test-password')
        self.page.reload()
        self.page.locator('#password').fill('a-long-browser-test-password')
        self.page.get_by_role('button', name='Sign in', exact=True).click()
        self.quote()
        with self.server.employee_access.lock:
            self.server.employee_access.sessions.clear()
        self.page.locator('#hourly_rate').fill('85')
        expect(self.page.locator('#fare_total')).to_have_text('Price unavailable')
        expect(self.page.locator('#pricing_status').get_by_role('link', name='Sign in again')).to_be_visible()
        expect(self.page.locator('#add_comparison')).to_be_disabled()

    def test_saved_quote_survives_reload_and_can_be_reused_without_changing_history(self):
        self.quote()
        self.page.locator('#notes').fill('Customer asks for two bags')
        self.page.locator('#include_charge').check()
        self.page.locator('#additional_charge').fill('20')
        expect(self.page.locator('#fare_total')).to_have_text('$160.00')
        self.page.locator('#include_tip').check()
        expect(self.page.locator('#fare_total')).to_have_text('$192.00')
        self.page.locator('#save_quote_name').fill('Smith airport pickup')
        self.page.locator('#save_quote_button').click()
        expect(self.page.locator('#saved_quote_detail')).to_contain_text('$192.00')
        self.page.reload()
        self.page.locator('#saved_quotes_panel > summary').click()
        expect(self.page.locator('#saved_quotes_list')).to_contain_text('Smith airport pickup')
        self.page.get_by_role('button', name='View quote', exact=True).click()
        expect(self.page.locator('#saved_quote_detail')).to_contain_text('Customer asks for two bags')
        expect(self.page.locator('#saved_quote_detail')).to_contain_text('$192.00')
        self.page.get_by_role('button', name='Use trip for a new quote').click()
        self.assertIn('Albemarle', self.page.locator('#pickup').input_value())
        expect(self.page.locator('#include_charge')).to_be_checked()
        expect(self.page.locator('#additional_charge')).to_have_value('20.00')
        expect(self.page.locator('#include_tip')).to_be_checked()
        self.assertEqual(len(self.server.quote_store.list(SHARED_TEAM)['quotes']), 1)

    def test_saved_search_delete_confirmation_and_text_are_safe(self):
        from test_quote_store import quote_payload
        self.server.quote_store.save(SHARED_TEAM, quote_payload(name='<img src=x onerror=alert(1)>'))
        self.server.quote_store.save(SHARED_TEAM, quote_payload(name='Other pickup'))
        self.page.locator('#saved_quotes_panel > summary').click()
        expect(self.page.locator('#saved_quotes_list article')).to_have_count(2)
        expect(self.page.locator('#saved_quotes_list img')).to_have_count(0)
        self.page.locator('#saved_search').fill('Other')
        self.page.get_by_role('button', name='Search saved quotes').click()
        expect(self.page.locator('#saved_quotes_list article')).to_have_count(1)
        self.page.once('dialog', lambda dialog: dialog.dismiss())
        self.page.locator('#saved_quotes_list').get_by_role('button', name='Delete', exact=True).click()
        expect(self.page.locator('#saved_quotes_list article')).to_have_count(1)
        self.page.once('dialog', lambda dialog: dialog.accept())
        self.page.locator('#saved_quotes_list').get_by_role('button', name='Delete', exact=True).click()
        expect(self.page.locator('#saved_quotes_status')).to_contain_text('Deleted')
        self.assertEqual(len(self.server.quote_store.list(SHARED_TEAM)['quotes']), 1)

    def test_save_waits_for_pricing_and_failed_storage_never_claims_success(self):
        self.quote()
        disabled = self.page.evaluate("""() => {const input=document.getElementById('hourly_rate');
          input.value='85';input.dispatchEvent(new Event('input'));return document.getElementById('save_quote_button').disabled;}""")
        self.assertTrue(disabled)
        expect(self.page.locator('#fare_total')).to_have_text('$170.00')
        self.page.locator('#save_quote_name').fill('Storage failure')
        with patch.object(self.server.quote_store, 'save', side_effect=OSError('disk full')):
            self.page.locator('#save_quote_button').click()
            expect(self.page.locator('#saved_quotes_status')).to_contain_text('Could not save')
        expect(self.page.locator('#save_quote_button')).to_be_enabled()


if __name__ == '__main__':
    unittest.main(verbosity=2)
