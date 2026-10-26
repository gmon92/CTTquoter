"""Persistent historical quotes, separate from the live pricing calculator."""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from pricing import amount, price_for_saved_snapshot
from accounts import AccountContext


def storage_path():
    configured = os.environ.get("QUOTER_DATA_DIR")
    directory = Path(configured).expanduser() if configured else Path(__file__).resolve().parent / "data"
    return directory / "quotes.sqlite3"


def text(value, label, limit, required=False):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError(f"{label} must be {'nonempty text' if required else 'text'} of at most {limit} characters")
    return value.strip() if label != "Notes" else value


def snapshot(payload):
    """Whitelist historical fields; compute all money fields with Python rules."""
    name = text(payload.get("name"), "Quote name", 120, True)
    trip = payload.get("trip")
    price = payload.get("pricing")
    if not isinstance(trip, dict) or not isinstance(price, dict):
        raise ValueError("A calculated trip and pricing are required")
    full, customer = trip.get("full_cycle"), trip.get("one_way")
    if not isinstance(full, dict) or not isinstance(customer, dict):
        raise ValueError("Calculated route details are required")
    stops = trip.get("stops", [])
    if not isinstance(stops, list) or len(stops) > 148:
        raise ValueError("Invalid saved trip stops")
    stops = [text(stop.get("address") if isinstance(stop, dict) else stop, "Stop address", 1000, True) for stop in stops]
    pickup_time = trip.get("pickup_time") or None
    if pickup_time is not None:
        text(pickup_time, "Pickup time", 64, True)
        parsed = datetime.fromisoformat(pickup_time.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Pickup time must include a timezone")
        pickup_time = parsed.astimezone(timezone.utc).isoformat()
    route = {"full_cycle": {"minutes": amount(full.get("minutes"), "Driver time"),
                            "miles": amount(full.get("miles"), "Driver mileage")},
             "one_way": {"minutes": amount(customer.get("minutes"), "Customer time"),
                         "miles": amount(customer.get("miles"), "Customer mileage")}}
    total = amount(price.get("quote"), "Quote")
    charge = amount(price.get("additional_charge", 0), "Additional charge")
    if total < charge:
        raise ValueError("Quote cannot be less than the additional charge")
    pricing = price_for_saved_snapshot({"total_driver_minutes": route["full_cycle"]["minutes"],
                            "one_way_miles": route["one_way"]["miles"],
                            "vehicle": trip.get("vehicle"), "edited": "quote", "value": total,
                            "additional_charge": charge, "include_tip": price.get("include_tip", False)},
                                      origin=price.get('pricing_origin', 'adjustment'))
    return {"name": name, "notes": text(payload.get("notes", ""), "Notes", 10000),
            "pickup": text(trip.get("pickup"), "Pickup address", 1000, True),
            "destination": text(trip.get("destination"), "Destination", 1000, True),
            "stops": stops, "vehicle": trip.get("vehicle"), "pickup_time": pickup_time,
            **route, "pricing": pricing}


class QuoteStore:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else storage_path()

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        existed = self.path.exists()
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            if not existed:
                self.path.chmod(0o600)
            version = connection.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1):
                raise sqlite3.DatabaseError('Unsupported quote storage version')
            connection.execute("CREATE TABLE IF NOT EXISTS quotes (id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, profile_id TEXT NOT NULL, created_by TEXT NOT NULL, name TEXT NOT NULL, created_at TEXT NOT NULL, snapshot TEXT NOT NULL, search_text TEXT NOT NULL)")
            connection.execute("CREATE INDEX IF NOT EXISTS quotes_profile_date ON quotes(workspace_id, profile_id, created_at DESC)")
            connection.execute('PRAGMA user_version = 1')
            connection.commit()
            return connection
        except Exception:
            connection.close()
            raise

    @staticmethod
    def scope(account):
        if not isinstance(account, AccountContext) or not all((account.account_id, account.profile_id, account.workspace_id)):
            raise ValueError("An authenticated account context is required")
        return account.workspace_id, account.profile_id

    def save(self, account, payload):
        workspace, profile = self.scope(account)
        data = snapshot(payload)
        record = {"id": uuid.uuid4().hex, "created_at": datetime.now(timezone.utc).isoformat(), **data}
        searchable = '\n'.join([data['name'], data['pickup'], data['destination'], *data['stops'], data['notes']]).casefold()
        with closing(self.connect()) as connection, connection:
            connection.execute("INSERT INTO quotes VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                               (record['id'], workspace, profile, account.account_id, record['name'], record['created_at'], json.dumps(data, allow_nan=False, ensure_ascii=False), searchable))
        return record

    def list(self, account, search="", limit=50, offset=0):
        workspace, profile = self.scope(account)
        # instr treats %, _, quotes and SQL syntax as literal search text.
        with closing(self.connect()) as connection:
            rows = connection.execute("SELECT id, created_at, snapshot FROM quotes WHERE workspace_id = ? AND profile_id = ? AND instr(search_text, ?) > 0 ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                                      (workspace, profile, search.casefold(), limit + 1, offset)).fetchall()
        return {"quotes": [{"id": row['id'], "created_at": row['created_at'], **json.loads(row['snapshot'])} for row in rows[:limit]],
                "has_more": len(rows) > limit}

    def get(self, account, quote_id):
        workspace, profile = self.scope(account)
        with closing(self.connect()) as connection:
            row = connection.execute("SELECT id, created_at, snapshot FROM quotes WHERE id = ? AND workspace_id = ? AND profile_id = ?", (quote_id, workspace, profile)).fetchone()
        return {"id": row['id'], "created_at": row['created_at'], **json.loads(row['snapshot'])} if row else None

    def delete(self, account, quote_id):
        workspace, profile = self.scope(account)
        with closing(self.connect()) as connection, connection:
            return connection.execute("DELETE FROM quotes WHERE id = ? AND workspace_id = ? AND profile_id = ?", (quote_id, workspace, profile)).rowcount == 1
