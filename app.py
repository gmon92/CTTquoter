from __future__ import annotations

import json
import os
import threading
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote
from urllib.request import Request, urlopen

from quote_engine import calculate_quote
from tomtom_client import calculate_route

HOME = (38.0360439, -78.4914661)  # 910 Anderson St., Charlottesville
SEARCH_URL = "https://api.tomtom.com/search/2/geocode/{}.json?key={}"


def load_profile_env():
    """Load the active Hermes business profile .env without overwriting env vars."""
    candidates = [
        os.path.join(os.path.expanduser("~"), ".hermes", "profiles", "business", ".env"),
        r"C:\\Users\\gabem\\AppData\\Local\\hermes\\profiles\\business\\.env",
    ]
    for path in candidates:
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        name, value = line.split("=", 1)
                        os.environ.setdefault(name.strip(), value.strip().strip('\\\"'))
            return
        except OSError:
            continue


load_profile_env()


def geocode(address):
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


def make_quote(payload):
    pickup = payload["pickup"].strip()
    destination = payload["destination"].strip()
    vehicle = payload.get("vehicle", "sedan")
    pickup_time = payload.get("pickup_time") or None
    pickup_point = geocode(pickup)
    destination_point = geocode(destination)
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
        waypoints=[pickup_point, destination_point],
        depart_at=driver_departure,
    )
    one_way = calculate_route(
        origin=pickup_point,
        destination=destination_point,
        depart_at=pickup_time,
    )
    result = calculate_quote(
        total_driver_minutes=full["minutes"],
        one_way_miles=one_way["miles"],
        vehicle=vehicle,
    )
    result.update({
        "pickup": pickup,
        "destination": destination,
        "pickup_time": pickup_time,
        "pickup_point": [pickup_point[0], pickup_point[1]],
        "destination_point": [destination_point[0], destination_point[1]],
        "home_point": [HOME[0], HOME[1]],
        "full_cycle": full,
        "one_way": one_way,
        "home_base": "910 Anderson St., Charlottesville, VA",
    })
    return result


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body, content_type="application/json"):
        raw = body if isinstance(body, bytes) else body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open("index.html", "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
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
        except Exception as exc:
            self._send(400, json.dumps({"error": str(exc)}))

    def log_message(self, *_):
        pass


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    url = "http://127.0.0.1:8765"
    print(f"Charlottesville Transportation Quoter: {url}")
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
