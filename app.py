from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import threading
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit, parse_qs
from urllib.request import Request, urlopen

from address_aliases import resolve_address
from quote_engine import calculate_quote
from base_rates import find_trip_reference_rates
from tomtom_client import calculate_route
from pricing import reprice_quote
from employee_access import EmployeeAccess, OPEN_ACCESS
from quote_store import QuoteStore

HOME = (38.0360439, -78.4914661)  # 910 Anderson St., Charlottesville
SEARCH_URL = "https://api.tomtom.com/search/2/geocode/{}.json?key={}"
APP_DIR = Path(__file__).resolve().parent
PWA_FILES = {
    "/manifest.webmanifest": ("static/manifest.webmanifest", "application/manifest+json"),
    "/sw.js": ("static/sw.js", "text/javascript; charset=utf-8"),
    "/pwa.js": ("static/pwa.js", "text/javascript; charset=utf-8"),
    "/saved-quotes.js": ("static/saved-quotes.js", "text/javascript; charset=utf-8"),
    "/offline.html": ("static/offline.html", "text/html; charset=utf-8"),
    **{f"/icons/{name}": (f"static/icons/{name}", content_type) for name, content_type in (
        ("icon-192.png", "image/png"), ("icon-512.png", "image/png"),
        ("maskable-512.png", "image/png"), ("apple-touch-icon.png", "image/png"),
        ("icon.svg", "image/svg+xml"))},
}


def load_env_file(path):
    """Load simple KEY=value settings while preserving existing environment values."""
    try:
        with open(path, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if line.startswith("export "):
                    line = line[7:].lstrip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, value = line.split("=", 1)
                name, value = name.strip(), value.strip()
                if not name.isidentifier():
                    continue
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                os.environ.setdefault(name, value)
    except OSError:
        return


def load_profile_env():
    """Load the project .env first, then profile fallbacks, preserving shell values."""
    candidates = [
        APP_DIR / ".env",
        os.path.join(os.path.expanduser("~"), ".hermes", "profiles", "business", ".env"),
        r"C:\\Users\\gabem\\AppData\\Local\\hermes\\profiles\\business\\.env",
    ]
    for path in candidates:
        load_env_file(path)


load_profile_env()


def geocode(address):
    address = resolve_address(address)
    key = os.environ.get("TOMTOM_API_KEY")
    if not key:
        raise RuntimeError("TOMTOM_API_KEY is not configured")
    url = SEARCH_URL.format(quote(address), quote(key))
    req = Request(url, headers={"User-Agent": "CharlottesvilleTransportationQuoter/0.1"})
    with urlopen(req, timeout=30) as response:
        data = json.load(response)
    results = data.get("results", [])
    if not results:
        raise ValueError(f"Could not find address: {address}")
    pos = results[0]["position"]
    return (float(pos["lat"]), float(pos["lon"]))


def fetch_map_tile(z, x, y):
    key = os.environ.get("TOMTOM_API_KEY")
    if not key:
        raise RuntimeError("TOMTOM_API_KEY is not configured")
    url = f"https://api.tomtom.com/map/1/tile/basic/main/{z}/{x}/{y}.png?key={quote(key)}"
    req = Request(url, headers={"User-Agent": "CharlottesvilleTransportationQuoter/0.1"})
    with urlopen(req, timeout=20) as response:
        return response.read(), response.headers.get("Content-Type", "image/png")


class AddressErrors(ValueError):
    def __init__(self, errors):
        super().__init__('Check the highlighted addresses.')
        self.fields = errors


def geocode_fields(pickup, stops, destination):
    errors = {}
    points = []
    for field, address in [('pickup', pickup), *[(f'stops.{i}', stop) for i, stop in enumerate(stops)], ('destination', destination)]:
        if not address:
            errors[field] = 'Enter an address or airport code.'
            points.append(None)
            continue
        try:
            points.append(geocode(address))
        except HTTPError as exc:
            if exc.code in (401, 403, 429):
                raise RuntimeError('Address lookup service unavailable. Check the TomTom API key, access, and usage limits.') from exc
            errors[field] = f'Address lookup failed (HTTP {exc.code}). Check this address or try its full street address.'
            points.append(None)
        except ValueError:
            errors[field] = f'Could not find “{address}”. Check the spelling or enter a full street address.'
            points.append(None)
        except (URLError, TimeoutError) as exc:
            raise RuntimeError('Could not reach the address lookup service. Please try again.') from exc
    if errors:
        raise AddressErrors(errors)
    return points[0], points[1:-1], points[-1]


def make_quote(payload):
    pickup = resolve_address(payload["pickup"])
    destination = resolve_address(payload["destination"])
    stops = payload.get("stops", [])
    if not isinstance(stops, list) or any(not isinstance(stop, str) for stop in stops):
        raise ValueError("Stops must be a list of addresses")
    stops = [resolve_address(stop) for stop in stops if stop.strip()]
    if len(stops) > 148:
        raise ValueError("A trip can have at most 148 additional stops")
    additional_charge = float(payload.get("additional_charge") or 0)
    if not math.isfinite(additional_charge) or additional_charge < 0:
        raise ValueError("Additional charge must be a non-negative dollar amount")
    additional_charge = round(additional_charge, 2)
    include_tip = payload.get("include_tip", False)
    if not isinstance(include_tip, bool):
        raise ValueError("Include tip must be true or false")
    vehicle = payload.get("vehicle", "sedan")
    pickup_time = payload.get("pickup_time") or None
    pickup_point, stop_points, destination_point = geocode_fields(pickup, stops, destination)
    driver_departure = None
    if pickup_time:
        approach = calculate_route(origin=HOME, destination=pickup_point)
        requested_pickup = datetime.fromisoformat(pickup_time.replace("Z", "+00:00"))
        if requested_pickup.tzinfo is None:
            requested_pickup = requested_pickup.replace(tzinfo=timezone.utc)
        driver_departure = (requested_pickup - timedelta(minutes=approach["minutes"])).isoformat()
    full = calculate_route(
        origin=HOME,
        destination=HOME,
        waypoints=[pickup_point, *stop_points, destination_point],
        depart_at=driver_departure,
    )
    one_way = calculate_route(
        origin=pickup_point,
        destination=destination_point,
        waypoints=stop_points,
        depart_at=pickup_time,
    )
    result = calculate_quote(
        total_driver_minutes=full["minutes"],
        one_way_miles=one_way["miles"],
        vehicle=vehicle,
    )
    trip_price = result["quote"]
    final_quote = round(trip_price + additional_charge, 2)
    tip_amount = round(final_quote * 0.2, 2) if include_tip else 0.0
    result.update({
        "trip_price": trip_price,
        "additional_charge": additional_charge,
        "quote": final_quote,
        "include_tip": include_tip,
        "tip_amount": tip_amount,
        "all_inclusive_price": round(final_quote + tip_amount, 2),
        "hourly_rate": round(final_quote / (full["minutes"] / 60), 2),
        "mileage_rate": round(final_quote / one_way["miles"], 2),
        "pickup": pickup,
        "destination": destination,
        "pickup_time": pickup_time,
        "pickup_point": [pickup_point[0], pickup_point[1]],
        "destination_point": [destination_point[0], destination_point[1]],
        "stops": [{"address": address, "point": list(point)} for address, point in zip(stops, stop_points)],
        "home_point": [HOME[0], HOME[1]],
        "full_cycle": full,
        "one_way": one_way,
        "home_base": "910 Anderson St., Charlottesville, VA",
        "base_rate_reference": find_trip_reference_rates(
            [pickup, *stops, destination], [pickup_point, *stop_points, destination_point]),
    })
    return result


class Handler(BaseHTTPRequestHandler):
    @property
    def access(self):
        return getattr(self.server, "employee_access", OPEN_ACCESS)

    def _send(self, status, body, content_type="application/json", headers=None):
        raw = body if isinstance(body, bytes) else body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-Robots-Tag", "noindex, nofollow, noarchive")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("X-Frame-Options", "DENY")
        if self.access.origin:
            self.send_header("Strict-Transport-Security", "max-age=31536000")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in PWA_FILES:
            filename, content_type = PWA_FILES[path]
            headers = {"Service-Worker-Allowed": "/"} if path == "/sw.js" else None
            self._send(200, (APP_DIR / filename).read_bytes(), content_type, headers)
            return
        if path == "/login":
            if not self.access.enabled or self.access.authorized(self.headers.get("Cookie")):
                self._send(303, "", headers={"Location": "/"})
            else:
                self._send(200, (APP_DIR / "static/login.html").read_bytes(), "text/html; charset=utf-8")
            return
        if path != "/health" and not self._require_access():
            return
        if path == "/api/account":
            self._send(200, json.dumps({'profile': self.account_context.public_profile()}))
            return
        if path == "/api/saved-quotes" or path.startswith("/api/saved-quotes/"):
            try:
                store = getattr(self.server, 'quote_store', None) or QuoteStore()
                if path == "/api/saved-quotes":
                    query = parse_qs(urlsplit(self.path).query)
                    search = query.get('q', [''])[0]
                    offset = int(query.get('offset', ['0'])[0])
                    if len(search) > 200 or not 0 <= offset <= 1000000:
                        raise ValueError("Invalid saved-quote search or page")
                    result = store.list(self.account_context, search, offset=offset)
                    result['profile'] = self.account_context.public_profile()
                    self._send(200, json.dumps(result))
                else:
                    quote_id = path[len('/api/saved-quotes/'):]
                    record = store.get(self.account_context, quote_id) if re.fullmatch(r'[a-f0-9]{32}', quote_id) else None
                    self._send(200 if record else 404, json.dumps(record if record else {'error': 'Saved quote not found'}))
            except (OSError, sqlite3.Error):
                self._send(503, '{"error":"Saved quotes are unavailable. Check the server storage and try again."}')
            except ValueError as exc:
                self._send(400, json.dumps({'error': str(exc)}))
            return
        if self.path in ("/", "/index.html"):
            page = (APP_DIR / "index.html").read_text(encoding="utf-8")
            sign_out = '<form action="/logout" method="post"><button class="secondary" type="submit">Sign out</button></form>' if self.access.enabled else ''
            self._send(200, page.replace("<!-- employee-sign-out -->", sign_out), "text/html; charset=utf-8")
        elif self.path == "/health":
            self._send(200, '{"status":"ok"}')
        elif self.path.startswith("/api/tiles/") and self.path.endswith(".png"):
            try:
                parts = self.path[:-4].split("/")
                if len(parts) != 6:
                    raise ValueError("invalid map tile path")
                z, x, y = (int(value) for value in parts[3:])
                if not (0 <= z <= 22 and 0 <= x < 2**z and 0 <= y < 2**z):
                    raise ValueError("map tile coordinates out of range")
                image, content_type = fetch_map_tile(z, x, y)
                self._send(200, image, content_type)
            except Exception:
                self._send(502, '{"error":"Map tile unavailable"}')
        else:
            self._send(404, '{"error":"not found"}')

    def _require_access(self):
        self.account_context = self.access.current_account(self.headers.get("Cookie"))
        if self.account_context is not None:
            return True
        if self.path.startswith("/api/"):
            self._send(401, '{"error":"Your session has expired. Sign in again to continue."}')
        else:
            self._send(303, "", headers={"Location": "/login"})
        return False

    def _same_origin(self):
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        # Existing unlisted HTTPS deployments need no new configuration. When
        # login is enabled publicly, the explicit HTTPS origin is authoritative.
        allowed = {self.access.origin} if self.access.origin else {f"http://{host}", f"https://{host}"}
        return ((origin is None or origin in allowed)
                and self.headers.get("Sec-Fetch-Site") != "cross-site")

    def _read_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= 131072:
            raise ValueError("Request body must be between 1 and 131072 bytes")
        return self.rfile.read(length)

    def do_POST(self):
        if not self._same_origin():
            self._send(403, '{"error":"Requests must come from the quoter website."}')
            return
        if self.path == "/login":
            if not self.access.enabled:
                self._send(303, "", headers={"Location": "/"})
                return
            try:
                form = parse_qs(self._read_body().decode())
                token, limited = self.access.login(form.get("password", [""])[0], self.client_address[0])
                if token:
                    self._send(303, "", headers={"Location": "/", "Set-Cookie": self.access.cookie(token)})
                else:
                    message = "Too many attempts. Wait a minute and try again." if limited else "Incorrect password. Please try again."
                    page = (APP_DIR / "static/login.html").read_text(encoding="utf-8").replace("<!-- login-error -->", message)
                    self._send(429 if limited else 401, page, "text/html; charset=utf-8")
            except (ValueError, UnicodeError):
                self._send(400, '{"error":"Invalid sign-in request"}')
            return
        if not self._require_access():
            return
        if self.path == "/logout":
            self.access.logout(self.headers.get("Cookie"))
            self._send(303, "", headers={"Location": "/login", "Set-Cookie": self.access.cookie("", clear=True)})
            return
        if self.path not in ("/api/quote", "/api/reprice", "/api/saved-quotes"):
            self._send(404, '{"error":"not found"}')
            return
        try:
            if (self.path in ("/api/reprice", "/api/saved-quotes")
                    and self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json"):
                self._send(415, '{"error":"Send JSON to the quote API."}')
                return
            payload = json.loads(self._read_body())
            if not isinstance(payload, dict):
                raise ValueError("Expected a JSON object")
            if self.path == "/api/saved-quotes":
                store = getattr(self.server, 'quote_store', None) or QuoteStore()
                try:
                    record = store.save(self.account_context, payload)
                except (OSError, sqlite3.Error):
                    self._send(503, '{"error":"Could not save the quote. Check the server storage and try again."}')
                    return
                self._send(201, json.dumps(record, allow_nan=False))
            else:
                result = make_quote(payload) if self.path == "/api/quote" else reprice_quote(payload)
                result['pricing_origin'] = 'route' if self.path == '/api/quote' else 'adjustment'
                self._send(200, json.dumps(result, allow_nan=False))
        except AddressErrors as exc:
            self._send(400, json.dumps({"error": str(exc), "field_errors": exc.fields}))
        except HTTPError as exc:
            self._send(502, json.dumps({"error": f"Routing service failed (HTTP {exc.code}). Check the trip route and pickup time, then try again."}))
        except Exception as exc:
            self._send(400, json.dumps({"error": str(exc)}))

    def do_DELETE(self):
        if not self._same_origin():
            self._send(403, '{"error":"Requests must come from the quoter website."}')
            return
        if not self._require_access():
            return
        match = re.fullmatch(r'/api/saved-quotes/([a-f0-9]{32})', self.path)
        if not match:
            self._send(404, '{"error":"Saved quote not found"}')
            return
        try:
            store = getattr(self.server, 'quote_store', None) or QuoteStore()
            deleted = store.delete(self.account_context, match[1])
            self._send(200 if deleted else 404, json.dumps({'deleted': True} if deleted else {'error': 'Saved quote not found'}))
        except (OSError, sqlite3.Error):
            self._send(503, '{"error":"Could not delete the saved quote. Try again."}')

    def log_message(self, *_):
        pass


def server_settings(environ=None):
    values = os.environ if environ is None else environ
    host = values.get("QUOTER_HOST", "127.0.0.1")
    try:
        port = int(values.get("PORT", "8765"))
    except ValueError:
        raise ValueError("PORT must be a number between 1 and 65535") from None
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be a number between 1 and 65535")
    open_browser = (values.get("QUOTER_OPEN_BROWSER", "1") == "1"
                    and host in ("127.0.0.1", "localhost"))
    return host, port, open_browser


def main():
    host, port, open_browser = server_settings()
    access = EmployeeAccess.from_environment(host)
    server = ThreadingHTTPServer((host, port), Handler)
    server.employee_access = access
    print(f"Charlottesville Transportation Quoter listening on {host}:{port}", flush=True)
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
