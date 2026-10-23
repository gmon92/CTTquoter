# Charlottesville Transportation Quoter (MVP)

Local browser-based taxi quote calculator for manual entry. TomTom Search, Orbis Routing, and map tiles use `TOMTOM_API_KEY`.

## Run on macOS

From the project folder, create your local settings file once:

```bash
cp .env.example .env
nano .env
```

Replace the placeholder in `.env` with your actual TomTom API key:

```dotenv
TOMTOM_API_KEY=your-tomtom-api-key-here
```

Save with Control+O, press Return, then exit with Control+X. Start the app:

```bash
python3 app.py
```

For everyday use, double-click **Start Quoter.command** in Finder. It starts the app from its own folder and opens your browser. Keep the Terminal window open while using the app; press Control+C in that window to stop it.

Git preserves the launcher's executable permission. If macOS reports a permission error (for example, after downloading a ZIP), run this once in the project folder:

```bash
chmod +x "Start Quoter.command"
```

The app reads `.env` from the same folder as `app.py`. You only need to save the key once.
If you previously exported a different key in Terminal, run `unset TOMTOM_API_KEY` before starting the app to use the key from `.env`. An exported environment value takes precedence over the file. Restart the app after changing the key.

## Run on Windows PowerShell

For first-time setup, create your local settings file from the project folder:

```powershell
Copy-Item .env.example .env
notepad .env
```

Replace the placeholder with your actual TomTom API key and save the file. Then double-click **Start Quoter.bat** in File Explorer. It finds Python 3, starts the app from the project folder, and opens your browser. Keep the command window open while using the app; press Control+C in it to stop the app.

You can also run `py -3 app.py` from the project folder. An existing `TOMTOM_API_KEY` environment variable takes precedence over `.env`.

The app opens at http://127.0.0.1:8765.

The key is read from `.env` or the environment and is never shown in the browser. `.env` is excluded from Git; `.env.example` contains only a placeholder. Do not commit your key or paste it into chat.

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
