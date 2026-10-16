from __future__ import annotations

import json
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse
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


def make_quote(payload):
    pickup = payload["pickup"].strip()
    destination = payload["destination"].strip()
    vehicle = payload.get("vehicle", "sedan")
    base_rate = float(payload.get("base_rate") or 0)
    depart_at = payload.get("depart_at") or None
    pickup_point = geocode(pickup)
    destination_point = geocode(destination)
    full = calculate_route(
        origin=HOME,
        destination=HOME,
        waypoints=[pickup_point, destination_point],
        depart_at=depart_at,
    )
    one_way = calculate_route(
        origin=pickup_point,
        destination=destination_point,
        depart_at=depart_at,
    )
    result = calculate_quote(
        base_rate=base_rate,
        total_driver_minutes=full["minutes"],
        one_way_miles=one_way["miles"],
        vehicle=vehicle,
    )
    result.update({
        "pickup": pickup,
        "destination": destination,
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
    server = ThreadingHTTPServer(("0.0.0.0", 8765), Handler)
    url = "http://127.0.0.1:8765"
    print(f"Charlottesville Transportation Quoter: {url}")
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
