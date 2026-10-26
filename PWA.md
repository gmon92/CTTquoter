# CTT Quoter on iPhone

## Install after the HTTPS version is approved and deployed

1. Open the quoter's **HTTPS** address in **Safari** on your iPhone. If you opened a link inside Mail or another app, choose **Open in Safari** first.
2. Tap **Share** (the square with an upward arrow; on some Safari versions it is inside the menu).
3. Choose **Add to Home Screen**. Scroll down the share menu if necessary.
4. Keep **Open as Web App** enabled if your iOS version shows that option. Name it **CTT Quoter**, then tap **Add**.
5. Open the new taxi icon from your Home Screen. It launches in standalone mode without Safari's address bar and tabs. Sign in with the team password if prompted.

Safari and an installed web app can have separate sign-in sessions. Sign in again from the Home Screen icon if needed. Sessions last up to 8 hours; **Sign out** ends the current session. If an older bookmark still opens in Safari, remove that icon and add it again using these steps.

This is an installed website; there is no App Store submission, developer account, or Apple subscription. Internet access is required for quotes, rate edits, maps and sign-in. A local `127.0.0.1` link on your Mac does not point to your Mac when opened on an iPhone. Use an approved HTTPS test or production address for phone installation.

## What changed

- The repository actually uses Python's standard-library HTTP server, not FastAPI. That server, its launchers, original `/api/quote`, `/api/tiles/...`, `/health`, route calculations, default rates and Excel references are preserved.
- The linked controls now call **POST `/api/reprice`**. Python applies the existing hourly/customer-mile equivalence, fixed extra charge, minimum equal to that charge, cent rounding and optional 20% tip. No routing request is needed when prices change.
- The initial `/api/quote` calculations and `quote_engine.py` are unchanged. Adjustment rounding preserves the former browser `Math.round` rules, including rounding the tip after rounding the quote to cents.
- JavaScript validates inputs, schedules requests and displays returned amounts. It does not calculate fares, equivalent rates, additional-charge totals or tips. Comparisons copy the server's returned pricing fields.
- Inputs use decimal keyboards, at least 16px text, and 48px touch controls. The phone layout stacks fields; desktop keeps multiple columns. iPhone safe areas and text zoom are supported.
- Matching Excel references stay available in an expandable panel with a match count. It starts collapsed on phones to keep price controls close to the result, and open on desktop. Reference tables scroll horizontally rather than splitting dollar amounts across lines.
- `/manifest.webmanifest`, `/sw.js`, `/pwa.js`, `/offline.html` and `/icons/...` are explicit public routes. The PNG icons are opaque: 180px Apple icon, 192px and 512px regular icons, and a 512px maskable icon.

## Offline behavior and updates

The service worker caches only public installation assets and the generic offline notice. It **never caches the app page, sign-in pages, route tiles, customer addresses, quote API responses or comparisons**. All app/API responses use `Cache-Control: no-store`. An offline launch shows a reconnect notice; a failed price update shows an error and blocks saving an outdated price. Reconnect and use **Retry price update**.

Unsaved quotes, notes and comparisons remain in memory and clear on reload. Use **Save quote** to retain a named historical quote on the server, then find it under **Saved quotes**. See [accounts and storage](ACCOUNTS_AND_STORAGE.md) for profile ownership and persistent hosted storage requirements. Switching apps briefly does not intentionally clear unsaved work, but iOS can discard web apps to reclaim memory.

New service workers activate after existing app windows close, so an update does not reload an active quote. For future changes to cached installation assets, increment `CACHE` in `static/sw.js`; reopening online fetches current assets. Leaflet still loads from its existing HTTPS CDN; maps need a connection too.

## Prepare employee access (approval required before production changes)

No deployment, DNS, hosting configuration or production credentials are changed by this branch. `render.yaml` still deploys `main`; keep this branch separate until approved. Local development remains password-free by default.

For a small group, this branch includes **optional shared team-password sign-in**. To enable it after approval, set these **server environment settings**, then restart:

```dotenv
QUOTER_ACCESS_PASSWORD=<a unique randomly generated password of at least 16 characters>
QUOTER_PUBLIC_ORIGIN=https://quotes.example.com
```

Replace the address with the exact real HTTPS origin (scheme and host, plus port if nonstandard; no path). Generate a password with a password manager and share it privately. Do not commit it or put it in browser JavaScript. Keep `TOMTOM_API_KEY` in the server environment as before. The service fails to start if password protection is enabled on a public bind without an HTTPS origin, or the password is too short.

The existing Render HTTPS endpoint or a correctly configured TLS reverse proxy can terminate HTTPS; the Python process remains behind it. Redirect HTTP to HTTPS at the hosting layer. Do not expose the Python development port directly to the internet. HTTPS is needed for service workers and secure session cookies. The app uses the explicitly configured origin rather than trusting arbitrary `X-Forwarded-*` headers, validates browser POST origins, sets security headers and marks HTTPS sessions `Secure`, `HttpOnly`, and `SameSite=Strict`.

Protected routes include the app, quotes, repricing and map tiles. Public routes contain only install assets, the login form and `/health`. Five failed sign-ins per client in a minute trigger a temporary limit. Sessions are stored in this single Python process and expire after 8 hours; restarting or changing the password signs everyone out. Use **Sign out** before handing an unlocked device to someone else.

A shared password does not identify individual employees. For individual email logins, revocation and MFA, use an identity gateway such as [Cloudflare Access](CLOUDFLARE_SETUP.md), with the origin protected against bypass. That requires separate approval and configuration. Noindex and an unlisted URL alone do not authorize employees. **If `QUOTER_ACCESS_PASSWORD` is unset, access remains unlisted and open as before.**

For local sign-in testing, put only `QUOTER_ACCESS_PASSWORD` in your ignored `.env` and keep the default loopback bind; leave `QUOTER_PUBLIC_ORIGIN` unset for HTTP localhost. Never use those HTTP-only settings for a public deployment.

## Verify before approving release

Run the standard regression suites:

```bash
python3 -m unittest -v
node test_quote_ui.cjs
node test_pwa_worker.cjs
```

The UI suite calls the real Python repricer using `python3` (override with the `PYTHON` environment variable if needed). No live TomTom key or API calls are needed for these tests.

Optional real-browser tests use development-only dependencies:

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m playwright install chromium
python3 browser_tests.py
```

Set `CTT_TEST_BROWSER=webkit` after `python3 -m playwright install webkit` to check the WebKit engine too. Browser tests run an ephemeral loopback server with mocked TomTom responses. They cover iPhone-size and desktop layouts, quoting, stops, charge/tip ordering, linked controls, failed updates, comparison snapshots, worker registration, offline fallback and optional sign-in. They do not deploy anything.

Before an approved release, also install on a physical iPhone from the approved HTTPS origin and check the icon, standalone launch, Safari sharing flow, sign-in, safe areas with the keyboard open, and reconnect behavior. Browser emulation cannot reproduce the iOS Home Screen installation UI.

### Implementation verification

- 81 Python regression tests, including the unchanged initial quote rules, route options, workbook references, repricing, asset routes, employee access, saved snapshots and profile/workspace isolation.
- 18 linked-control/comparison tests calling the real Python repricer, plus 6 service-worker tests.
- 11 browser scenarios passed in both Chromium and WebKit (22 browser runs), including phone widths from 320px, the desktop layout, saved quote reload/search/reuse/delete and storage failures.
- Physical iPhone installation and an HTTPS deployment have not been performed. They remain approval-dependent release checks.
