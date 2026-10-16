from __future__ import annotations

HOURLY_RATES = {"sedan": 70.0, "suv": 85.0}
MILEAGE_RATES = {"sedan": 3.0, "suv": 3.6}


def calculate_quote(*, base_rate: float, total_driver_minutes: float,
                    one_way_miles: float, vehicle: str) -> dict:
    vehicle = vehicle.lower().strip()
    if vehicle not in HOURLY_RATES:
        raise ValueError("vehicle must be sedan or suv")
    hourly = round(max(total_driver_minutes / 60 * HOURLY_RATES[vehicle], 70.0), 2)
    mileage = round(one_way_miles * MILEAGE_RATES[vehicle], 2)
    recommended_method = "mileage" if mileage > hourly else "hourly"
    return {
        "base_rate": round(float(base_rate), 2),
        "hourly_price": hourly,
        "mileage_price": mileage,
        "recommended_price": max(hourly, mileage),
        "recommended_method": recommended_method,
        "vehicle": vehicle,
        "hourly_rate": HOURLY_RATES[vehicle],
        "mileage_rate": MILEAGE_RATES[vehicle],
    }
