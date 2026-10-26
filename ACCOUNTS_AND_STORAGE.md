# Accounts, saved quotes, and future iPhone clients

## Current behavior

After calculating and adjusting a quote, enter a name and press **Save quote**. Open **Saved quotes** to search by name, address or notes, view the historical amounts, reuse the trip, or delete a record after confirmation. Saved records include pickup/destination/stops, pickup time, vehicle, route miles and hours, notes, both equivalent rates, extra charge, tip and total.

Saved prices remain fixed. Viewing a record makes no TomTom request and does not rerun routing or current default rates. The server also preserves the existing initial-route versus adjusted-rate cent rounding. **Use trip for a new quote** fills the form; pressing **Calculate trip** then creates a fresh estimate. Clearing the current quote/comparisons does not erase history.

Unsaved quotes and comparisons remain temporary. Saved history is server-side, persists across page reloads and ordinary server restarts when the storage directory is retained, and is available to the same profile from iPhone and desktop using the same server. Separate local installations have separate databases. An internet connection is required; customer records are not cached for offline access.

## Identity and ownership

This release preserves the existing shared team-password option (and password-free local development). These map to **one Shared team profile**. It does **not** implement individual registration, individual employee passwords, or a profile picker yet.

Saved quotes already carry:

- `workspace_id`: company/team boundary;
- `profile_id`: profile that owns the record;
- `created_by`: account that saved it.

Every list, search, view and delete query enforces workspace and profile ownership in SQL. Ownership comes only from the authenticated server context. Payload/query fields cannot select another profile or change the recorded creator. A quote ID from another profile returns 404. Database methods require an explicit account context; there is no implicit fallback to unrestricted storage.

## Code boundaries

| Component | Responsibility |
| --- | --- |
| `accounts.py` | Immutable account/profile/workspace context, stable IDs, public profile metadata. |
| `employee_access.py` | Authentication and `current_account()` identity resolution. Currently resolves the Shared team profile. |
| `quote_store.py` | Profile-scoped storage repository, snapshot validation, schema version and persistence. No HTTP or browser code. |
| `pricing.py`, `quote_engine.py` | Server pricing rules, independent of browser UI and account provider. |
| `app.py` | HTTP access checks and API wiring. Passes the trusted account context to storage. |
| `static/saved-quotes.js` | Save/history interface. Displays server amounts, never chooses ownership or calculates prices. |

An account provider can replace `EmployeeAccess.current_account()` with session/token-to-account resolution. It must return stable account/profile/workspace IDs only after authenticating the user and checking profile membership. Shared profiles can be authorized explicitly; matching a display name is not permission. Signing in or changing profiles should reload client state so records from the previous profile are cleared from memory.

An eventual native/App Store client can use the same APIs and pricing services. Packaging for the App Store, individual account provisioning, and the choice of account provider remain separate future work. No account service, native wrapper or App Store deployment has been enabled.

The repository accepts an injected `server.quote_store`, allowing another database implementation behind the same `save/list/get/delete` interface without changing browser pricing or ownership rules. Schema version 1 is recorded in SQLite's `user_version`; future schema changes should use explicit migrations and preserve stable ownership IDs.

## API

All routes below use the existing authentication and same-origin write checks. Responses are `no-store`; the service worker never caches these APIs.

- `GET /api/account` — current profile metadata.
- `POST /api/saved-quotes` — save a named snapshot; returns 201 and a server-generated ID. Inputs: `name`, `notes`, calculated `trip` route details, and `pricing` (`quote`, `additional_charge`, `include_tip`, and `pricing_origin` from the quote/reprice response). Monetary fields are validated/rebuilt by the Python pricing service; client-supplied tip/total/rates are not trusted.
- `GET /api/saved-quotes?q=...&offset=...` — search current profile, newest first, 50 per page, with `has_more` and profile metadata.
- `GET /api/saved-quotes/{id}` — historical snapshot for the current profile.
- `DELETE /api/saved-quotes/{id}` — delete only a record owned by the current profile.

The initial quote, repricing, routing and workbook calculations are unchanged. Saving does not perform a new live route lookup.

## Storage, hosting and backups

Local default: `data/quotes.sqlite3` beside `app.py`. The database and its directory are excluded from Git. No extra Python packages are required. Keep the data folder when updating or moving the local app. To back up, stop the app and copy `quotes.sqlite3` to private backup storage; restore it to the same data directory with the server stopped.

For a hosted installation, configure **persistent storage** after approval and set an absolute server directory, for example:

```dotenv
QUOTER_DATA_DIR=/var/data/ctt-quoter
```

That directory must actually be on a retained writable disk/volume. Setting the variable alone does not make storage persistent. The current Render free service filesystem is ephemeral and is **not suitable for long-term quote history**: files can be lost during idle shutdowns, restarts or deployments. An approved service with a persistent disk or a future managed database is needed for durable hosted records. No hosting plan, disk, credentials, production environment, DNS, or deployment was changed for this feature.

Before sharing hosted quote history, enable the employee sign-in described in [PWA.md](PWA.md), or configure the approved identity gateway. The current shared login shares one history. If authentication is unset, history is accessible to anyone with the app address, just like its other APIs. Keep customer notes and database backups out of Git.
