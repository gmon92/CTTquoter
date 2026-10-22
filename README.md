# Charlottesville Transportation Quoter (MVP)

Local browser-based taxi quote calculator for manual entry. TomTom Search, Orbis Routing, and map tiles use `TOMTOM_API_KEY`.

## Run on Windows PowerShell

```powershell
$env:TOMTOM_API_KEY = "your-key"
cd path\to\CTTquoter
python app.py
```

The app opens at http://127.0.0.1:8765.

The key is read from the environment and is never shown in the browser. Do not commit it or paste it into chat.

## Current behavior

- Geocodes pickup and destination with TomTom Search API.
- Calculates the full driver cycle: 910 Anderson → pickup → destination → 910 Anderson.
- Calculates the one-way customer route separately.
- Displays the routes and stops over TomTom street map tiles. Map tiles are proxied through the local server so the API key stays out of the browser.
- Accepts a customer pickup time for route estimates.
- Starts with the vehicle's default hourly rate ($70/hour sedan, $85/hour SUV) and calculates the quote from full driver-cycle time.
- Shows three linked values: final quote, hourly rate per full driver hour, and equivalent rate per customer one-way mile. Editing any one recalculates the other two.
- Accepts pasted notes for reference; notes are not parsed automatically.

## Verification

```powershell
python -m unittest -v
```

To run the linked quote control tests, use Node.js (only needed for these tests):

```powershell
node test_quote_ui.cjs
```
