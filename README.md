# Charlottesville Transportation Quoter (MVP)

Local browser-based taxi quote calculator for manual entry. TomTom Search, Orbis Routing, and map tiles use `TOMTOM_API_KEY`.

For iPhone Home Screen installation, offline behavior, optional employee sign-in, and PWA regression tests, see [the PWA guide](PWA.md). HTTPS hosting and access settings must be approved before production changes.

Use **Save quote** after calculating to retain a named historical quote. Browse, search, view, reuse or delete records under **Saved quotes**. See [accounts and storage](ACCOUNTS_AND_STORAGE.md) for persistence, backups, profile ownership, and future App Store client boundaries. The existing login currently uses one shared team profile.

For an unlisted website hosted independently of your Mac, use [the Render hosting guide](HOSTING.md). Your existing GoDaddy website can stay in place. The repository includes a ready-to-deploy `render.yaml` blueprint.

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

## Run with Docker

Docker Desktop can run the quoter in a container on Windows, macOS, or Linux. Create a `.env` file in the project folder and add your TomTom API key as described above. Start Docker Desktop, open PowerShell in the project folder, and run:

```powershell
docker compose up --build -d
```

Open http://127.0.0.1:8765 on the computer. To use an iPhone on the same Wi-Fi, open `http://PC-IP-ADDRESS:8765` in Safari, replacing `PC-IP-ADDRESS` with the computer's Wi-Fi IPv4 address. The container listens on the local network; Windows Firewall may ask you to allow Docker Desktop on private networks.

Stop the quoter with:

```powershell
docker compose down
```

The default port is `8765`, so stop any other local copy of the quoter before starting Docker. After changing project files, run `docker compose up --build -d` again to rebuild and start the updated app. Docker Compose reads `.env` for the API key; the key is passed into the container at runtime and is not copied into the image.

## Current behavior

For private access from phones using a Cloudflare Tunnel and approved email logins, follow [the Cloudflare setup guide](CLOUDFLARE_SETUP.md). The host computer must stay awake and run both the app and connector.

- Expands airport shorthand **CHO, IAD, RIC, DCA, BWI, ROA, and LYH** into airport names and street addresses before routing. Codes ignore case and surrounding spaces; `CHO airport` also works. Supported in pickup, destination, and extra stops. Resolved addresses appear in quote results and comparisons.
- Local shorthand: **BHI** → Boar’s Head Resort (200 Ednam Drive); **Keswick** → Keswick Hall (701 Club Drive); **Farmington** → Farmington Country Club (1625 Country Club Circle). These ignore case and surrounding spaces and work in pickup, destination, and extra stops.
- Geocodes pickup and destination with TomTom Search API.
- Calculates the full driver cycle: 910 Anderson → pickup → destination → 910 Anderson.
- Calculates the one-way customer route separately.
- Optional **Add more customer stops** checkbox reveals extra address fields. Stops are visited in the order entered between pickup and the final destination, and are included in both customer mileage and the full driver cycle. Unchecking the option ignores those stops. Recalculate after editing the route.
- Optional **Add a dollar amount to the quote** checkbox reveals an additional charge. The quote shows a trip-price-plus-charge breakdown, and the hourly/mileage rates remain equivalent to the final total. Adjusting the charge updates the total live; editing the final quote or either rate adjusts the trip price while keeping the charge fixed. Unchecking the option removes the charge.
- Optional **Add 20% tip (all-inclusive price)** checkbox shows a separate tip and all-inclusive total. The tip is calculated after the trip price and any additional charge, rounded to cents, and updates live as pricing changes. The three linked pricing controls show the quote before tip.
- Displays the routes and stops over TomTom street map tiles. Map tiles are proxied through the local server so the API key stays out of the browser.
- Accepts a customer pickup time for route estimates.
- Starts with the vehicle's default hourly rate ($70/hour sedan, $85/hour SUV) and calculates the quote from full driver-cycle time.
- Shows three linked values: final quote, hourly rate per full driver hour, and equivalent rate per customer one-way mile. Editing any one recalculates the other two.
- **Add to comparison** saves the current quote as a named option in a side-by-side table, including route, vehicle, pickup time, rates, additional charge, tip, and total. Adjust the current pricing or calculate another trip, then add another option. Rename options directly in the table, remove them individually, or use **Clear comparison** to keep working on the current quote. **New quote / clear all** clears the form, results, and comparison. Saved options last until cleared or the page is reloaded.
- Shows matching base-rate references from `Taxi Pricing.xlsx`, grouped by the spreadsheet's rate schedules, plus relevant airport pickup notes. Listed point-to-point routes match in either direction. Airport names/codes and addresses within 1.5 km of an airport reference point can match; nearby matches are labeled for confirmation. These references do not change the calculated quote.
- Reads the workbook from the app folder each time a quote is calculated, so saving a pricing update in Excel updates future references. Keep its existing table layout and keep the workbook in the app folder; no Excel installation or extra Python packages are required to read it.
- Accepts pasted notes for reference; notes are not parsed automatically.

## Verification

```powershell
python -m unittest -v
```

To run the linked quote control tests, use Node.js (only needed for these tests):

```powershell
node test_quote_ui.cjs
```
