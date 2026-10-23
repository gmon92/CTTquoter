from __future__ import annotations

import json
import math
import os
import threading
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from address_aliases import resolve_address
from quote_engine import calculate_quote
from base_rates import find_trip_reference_rates
from tomtom_client import calculate_route

HOME = (38.0360439, -78.4914661)  # 910 Anderson St., Charlottesville
SEARCH_URL = "https://api.tomtom.com/search/2/geocode/{}.json?key={}"
APP_DIR = Path(__file__).resolve().parent


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
    def _send(self, status, body, content_type="application/json"):
        raw = body if isinstance(body, bytes) else body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-Robots-Tag", "noindex, nofollow, noarchive")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(APP_DIR / "index.html", "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
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

    def do_POST(self):
        if self.path != "/api/quote":
            self._send(404, '{"error":"not found"}')
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            self._send(200, json.dumps(make_quote(payload)))
        except AddressErrors as exc:
            self._send(400, json.dumps({"error": str(exc), "field_errors": exc.fields}))
        except HTTPError as exc:
            self._send(502, json.dumps({"error": f"Routing service failed (HTTP {exc.code}). Check the trip route and pickup time, then try again."}))
        except Exception as exc:
            self._send(400, json.dumps({"error": str(exc)}))

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
    server = ThreadingHTTPServer((host, port), Handler)
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
