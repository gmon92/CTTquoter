# Charlottesville Transportation Quoter (MVP)

Local browser-based quote calculator for manual entry. It uses TomTom Orbis routing when `TOMTOM_API_KEY` is available.

## Run on Windows PowerShell

```powershell
$env:TOMTOM_API_KEY = "your-key"
cd path\to\cville-quoter
python app.py
```

The app opens at http://127.0.0.1:8765.

The key is read from the environment and is never shown in the browser. Do not commit it or paste it into chat.

## Current behavior

- Geocodes pickup and destination with TomTom Search API.
- Calculates the full driver cycle: 910 Anderson → pickup → destination → 910 Anderson.
- Calculates the one-way customer route separately.
- Compares the $70/hour minimum calculation against sedan/SUV mileage pricing.
- Shows the city-proper base rate separately.
- Accepts pasted notes for reference, with manual address fields in this first MVP.

## Verification

```powershell
python -m unittest -v
```
