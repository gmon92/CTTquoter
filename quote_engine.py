from __future__ import annotations

from typing import Optional

HOURLY_RATES = {"sedan": 70.0, "suv": 85.0}
MILEAGE_RATES = {"sedan": 3.0, "suv": 3.6}


def calculate_quote(*, total_driver_minutes: float, one_way_miles: float,
                    vehicle: str, hourly_rate: Optional[float] = None,
                    mileage_rate: Optional[float] = None, quote: Optional[float] = None,
                    edited: str = "hourly_rate", base_rate: Optional[float] = None) -> dict:
    vehicle = vehicle.lower().strip()
    if vehicle not in HOURLY_RATES:
        raise ValueError("vehicle must be sedan or suv")
    hours = total_driver_minutes / 60
    if hours <= 0 or one_way_miles <= 0:
        raise ValueError("route time and one-way mileage must be greater than zero")

    # Keep the original calculator interface working for existing callers.
    if base_rate is not None and hourly_rate is None and mileage_rate is None and quote is None:
        hourly_price = round(max(hours * HOURLY_RATES[vehicle], 70.0), 2)
        mileage_price = round(one_way_miles * MILEAGE_RATES[vehicle], 2)
        method = "mileage" if mileage_price > hourly_price else "hourly"
        return {
            "base_rate": round(float(base_rate), 2),
            "hourly_price": hourly_price,
            "mileage_price": mileage_price,
            "recommended_price": max(hourly_price, mileage_price),
            "recommended_method": method,
            "vehicle": vehicle,
            "hourly_rate": HOURLY_RATES[vehicle],
            "mileage_rate": MILEAGE_RATES[vehicle],
        }

    hourly_rate = HOURLY_RATES[vehicle] if hourly_rate is None else float(hourly_rate)
    mileage_rate = MILEAGE_RATES[vehicle] if mileage_rate is None else float(mileage_rate)
    if edited == "mileage_rate":
        final_quote = one_way_miles * mileage_rate
    elif edited == "quote":
        if quote is None:
            raise ValueError("quote is required when edited is quote")
        final_quote = float(quote)
    else:
        edited = "hourly_rate"
        final_quote = hours * hourly_rate

    if final_quote < 0:
        raise ValueError("quote cannot be negative")
    hourly_rate = final_quote / hours
    mileage_rate = final_quote / one_way_miles
    return {
        "quote": round(final_quote, 2),
        "hourly_rate": round(hourly_rate, 2),
        "mileage_rate": round(mileage_rate, 2),
        "total_driver_hours": round(hours, 2),
        "one_way_miles": round(one_way_miles, 2),
        "vehicle": vehicle,
        "edited": edited,
    }
