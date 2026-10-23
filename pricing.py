"""Server-side adjustments for the three linked quote controls.

The original route calculator and default rates stay in quote_engine.py. These
are the same adjustment, minimum-charge and tip rules previously used by the UI.
"""
from __future__ import annotations

import math

from quote_engine import HOURLY_RATES


def amount(value, name):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a non-negative number")
    try:
        value = float(value)
    except (ValueError, TypeError):
        raise ValueError(f"{name} must be a non-negative number") from None
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a non-negative number")
    return value


def cents(value):
    # Preserve Math.round(value * 100) from the existing adjustment controls.
    if not math.isfinite(value * 100):
        raise ValueError("Price is too large")
    return math.floor(value * 100 + 0.5) / 100


def reprice_quote(payload):
    minutes = amount(payload.get("total_driver_minutes"), "Driver time")
    miles = amount(payload.get("one_way_miles"), "Customer mileage")
    if minutes <= 0 or miles <= 0:
        raise ValueError("Route time and customer mileage must be greater than zero")
    hours = minutes / 60
    if hours <= 0:
        raise ValueError("Route time must be greater than zero")
    vehicle = payload.get("vehicle", "sedan")
    if vehicle not in HOURLY_RATES:
        raise ValueError("vehicle must be sedan or suv")
    charge = cents(amount(payload.get("additional_charge", 0), "Additional charge"))
    include_tip = payload.get("include_tip", False)
    if not isinstance(include_tip, bool):
        raise ValueError("Include tip must be true or false")
    source = payload.get("edited")
    if source == "additional_charge":
        total = amount(payload.get("trip_price"), "Trip price") + charge
    elif source in ("hourly_rate", "mileage_rate", "quote", "quote_slider"):
        value = amount(payload.get("value"), "Edited value")
        total = value * hours if source == "hourly_rate" else value * miles if source == "mileage_rate" else value
    else:
        raise ValueError("Unknown pricing control")
    clamped = total < charge
    total = cents(max(total, charge))
    # The old browser calculation rounded the price to cents before its 20% tip.
    tip = math.floor(math.floor(total * 100 + 0.5) / 5 + 0.5) / 100 if include_tip else 0.0
    return {
        "quote": total,
        "trip_price": cents(total - charge),
        "additional_charge": charge,
        "hourly_rate": cents(total / hours),
        "mileage_rate": cents(total / miles),
        "include_tip": include_tip,
        "tip_amount": tip,
        "all_inclusive_price": cents(total + tip),
        "clamped": clamped,
    }
