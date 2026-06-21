# Agent guidance for Counta

> Project-specific handoff and operating rules for Counta.
> If you lost context, read this file first, then `README.md`, then run tests.
>
> Last updated: 2026-06-21 — after AI/LLM layer removal.

## 0. Quick recovery for a new agent

1. Read this file (`AGENTS.md`).
2. Skim `README.md` for the product pitch.
3. Run the deploy gate: `uv run python scripts/pre_flight.py`.
4. Only then open the specific code area you need to change.

For operator-level context (personal profile, family rules, cross-project conventions), see:
- `~/github-work/denis-root-continuity/skills/repo-bootstrap.md`
- `~/github-work/denis-root-continuity/skills/operator-profile.md`
- `~/github-work/denis-root-continuity/skills/agent-behavior.md`
- `~/github-work/denis-root-continuity/skills/project-avalone.md`

---

## 1. What Counta is

Counta is a personal/family double-entry bookkeeping PWA, currently live at `https://counta.avalone.online`.

- **No AI / LLM / STT / vision.** The app was recently stripped of all AI features. Everything is deterministic.
- **Own ledger.** It uses a private SQLite double-entry ledger, not ERPNext or any external accounting system.
- **Small scale.** Designed for one person, a couple, or a small family/group. One SQLite DB per instance.
- **i18n-first.** User-facing strings are stored in a central glossary with `ru`, `en`, `ko` translations.

---

## 2. Tech stack

| Layer | Tech | File(s) |
|---|---|---|
| Runtime | Python ≥3.13, managed with `uv` | `pyproject.toml`, `uv.lock` |
| Web framework | FastAPI + Uvicorn | `src/counta/web/app.py` |
| Frontend | Vanilla JS SPA inside one Jinja2 template | `src/counta/web/templates/app.html` |
| Database | SQLite (`~/.counta/counta.db`) | `src/counta/core/sqlledger.py`, `src/counta/core/*.py` |
| Auth | PBKDF2-HMAC-SHA256 passwords + signed `itsdangerous` session cookie | `src/counta/core/tenant.py`, `src/counta/core/security.py` |
| i18n | Central glossary table | `src/counta/core/glossary.py` |
| Currency | Live fiat + crypto conversion | `src/counta/core/currency.py` |
| Email | SMTP (Gmail App Password) | `src/counta/core/notify.py` |
| Tests | pytest + pytest-asyncio | `tests/` |

Key dependencies: `fastapi`, `uvicorn[standard]`, `jinja2`, `sqlalchemy[asyncio]`, `pydantic-settings`, `itsdangerous`, `httpx`, `qrcode`, `aiogram` (legacy, currently unused).

---

## 3. Directory layout

```
src/counta/
├── core/                  # Business logic + data access (no HTTP)
│   ├── sqlledger.py       # SQLite double-entry ledger (accounts, entries, lines, seq)
│   ├── engine.py          # Async facade over sqlledger
│   ├── tenant.py          # Users, passwords, tenant ContextVar, isolation
│   ├── money.py           # Money-account registry + currency per account
│   ├── catalog.py         # Canonical expense/income categories + i18n labels
│   ├── ledger_ops.py      # Account resolution helpers (used by forms)
│   ├── entry_meta.py      # Per-entry metadata: occurred_at, slept_entries
│   ├── lexicon.py         # User-learned phrase → account mappings
│   ├── glossary.py        # Central UI text glossary (ru/en/ko)
│   ├── ui_glossary.py     # Context descriptions for glossary entries
│   ├── tips.py            # Rule-based financial tips
│   ├── currency.py        # Currency list + live conversion
│   ├── notify.py          # Per-tenant settings + SMTP email
│   ├── global_settings.py # Instance-wide settings (registration mode, etc.)
│   ├── config.py          # Pydantic-Settings env config
│   ├── constants.py       # Tunable constants (rate limits, limits)
│   ├── security.py        # Rate limits, verification codes, reset tokens
│   └── db.py              # Single DB_PATH constant
├── web/                   # HTTP layer
│   ├── app.py             # FastAPI app, page routes, auth middleware
│   ├── api/               # API routers (domain-split)
│   │   ├── __init__.py    # Aggregates all routers under /api
│   │   ├── accounts.py    # Accounts, categories, incomes CRUD
│   │   ├── entries.py     # Journal entries, balances, report
│   │   ├── form.py        # Form dropdown data, glossary seed, currency convert
│   │   ├── analytics.py   # Summary, tips, trends, compare
│   │   ├── edit.py        # Category/income editor lists
│   │   ├── settings.py    # User settings
│   │   ├── admin.py       # Admin endpoints
│   │   ├── misc.py        # /me, email verification
│   │   ├── common.py      # Shared label helpers
│   │   └── dependencies.py # FastAPI tenant/admin dependencies
│   ├── templates/
│   │   └── app.html       # Main SPA template
│   └── static/            # icon.svg, sw.js, manifest.json
├── i18n/                  # (legacy; currently empty after strings.py removal)
tests/                     # pytest suite
scripts/
│   ├── pre_flight.py      # Deploy gate
│   └── check_i18n.py      # i18n linter
migrations/                # Legacy Alembic migrations (Postgres schema)
```

---

## 4. Core architecture patterns

### 4.1 Double-entry ledger

Every financial event is a balanced journal entry.

- `led_entries` — header: tenant, voucher name, posting_date, user_remark, total_debit, docstatus, creation.
- `led_lines` — lines: tenant, entry, account, debit, credit (CHECK ensures only one side is non-zero).
- `led_seq` — per-tenant voucher numbering per year.
- `sqlledger.assert_balanced()` enforces that `SUM(debit) == SUM(credit)` globally and per-entry.

Sign convention: `account_balance = SUM(debit) - SUM(credit)`. Positive = money you have; negative = debt.

### 4.2 Tenant isolation

- `core/tenant.py` holds a `ContextVar[int]` (`_current`) for the current tenant id.
- `web/app.py::auth_gate` reads the signed `counta_session` cookie and calls `tenant.set_current(tid)`.
- Almost every data-access function calls `tenant.require_current()` or embeds `tenant=?` in SQL.
- Glossary and global settings are the only shared/instance-wide tables.

### 4.3 Accounts

Account PKs follow the legacy ERPNext shape `{account_name} - {ABBR}` (ABBR = `DP`), but canonical categories now use stable slugs like `cat_groceries`.

Account `root_type` values:
- `Asset` — cash, bank, other money accounts.
- `Liability` — credit cards, loans.
- `Income` — salary, side income, etc.
- `Expense` — spending categories.

`account_type` is a finer-grained ERPNext-like tag. `ledger_ops._EXCLUDED_ACCOUNT_TYPES = {"Receivable", "Payable"}` keeps party accounts out of simple personal finance flows.

### 4.4 Money registry

`core/money.py` maintains an explicit registry (`money_accounts`) of which Asset/Liability accounts are "money". Each money account has its own currency. This avoids guessing from account names.

When a new money account is created, it is registered with a currency. Transfers between accounts with different currencies are rejected by `engine.post_journal_entry`.

### 4.5 Catalog & labels

- `core/catalog.py` defines canonical categories and their roles (`need`, `want`, `goal`, `income`).
- `core/catalog.py::CANON` maps stable slugs to metadata.
- `catalog_i18n` stores per-tenant per-account labels in `ru/en/ko`.
- `core/glossary.py` is the source of truth for generic UI text, currency names, and canonical category names.

Rule: every user-visible string has a neutral alphanumeric key; languages are translations.

### 4.6 Entry metadata

`core/entry_meta.py` stores:
- `occurred_at` — the actual transaction date/time (separate from posting_date).
- `slept_entries` — snapshots used when a money account is disabled (entries are canceled and can be restored later).

### 4.7 Deterministic tips

`core/tips.py` selects a financial-literacy tip by evaluating rule conditions against normalized report data. It is **not** AI. Priority order is defined in `_ROLE_PRIORITY`.

---

## 5. API surface

All API routers are mounted under `/api` in `src/counta/web/api/__init__.py`.

| Router | Key endpoints | Purpose |
|---|---|---|
| `form.py` | `GET /form-data`, `/glossary`, `/currencies`, `/convert` | Form dropdowns, glossary seed, currency conversion |
| `accounts.py` | `GET /account/me`, `/accounts`; `POST /account`, `/account/{pk}/disable`, `/account/{pk}/purge`, `/category`, `/income` | Accounts, categories, incomes |
| `entries.py` | `POST /entry`; `GET /balances`, `/entries`, `/report`; cancel/restore/purge | Journal operations and reports |
| `settings.py` | `GET /settings`, `POST /settings` | Per-tenant settings |
| `analytics.py` | `GET /analytics/summary`, `/analytics/tip`, `/analytics/tips`, `/analytics/trend`, `/analytics/compare` | Rule-based analytics |
| `edit.py` | `GET /edit/categories`, `/edit/incomes` | Editor lists |
| `admin.py` | `GET /admin/config`, `/admin/users`, `/admin/stats`; `POST /admin/config`, `/admin/constants` | Instance admin |
| `misc.py` | `GET /me`; `POST /send-verify-code`, `/verify-email` | Profile & email verification |

Page routes (login, register, recover, admin dashboard) live in `src/counta/web/app.py`.

---

## 6. Frontend patterns

The frontend is in `src/counta/web/templates/app.html` (~2.3k lines, no framework).

- **SPA pages:** `div#page-entry`, `#page-balances`, `#page-ai`, `#page-more`. Bottom tab bar switches visibility.
- **State:** global JS variables (`FD`, `LANG`, `LAYOUT`, `jFilter`, `pending`, `modalStack`).
- **Modals/sheets:** operation form, filter panel, wizard are overlays integrated with `history.pushState` so the Android back button closes them.
- **i18n:** static strings via `data-i`, `data-i-ph`, `data-i-title`; dynamic via `T('key')`.
- **Theming:** CSS variables + `data-theme` on `<html>`; theme is applied before first paint to avoid flash.
- **PWA:** `manifest.json`, `sw.js`, 30-second `/api/version` polling to force reload after deploy.
- **Journal:** infinite scroll via `IntersectionObserver`.
- **Entry form:** three-step flow (input → review → posted); resets to defaults on every open.

---

## 7. Configuration & deployment

### 7.1 Environment config

`core/config.py` reads `COUNTA_*` env vars (and optional `.env`):

- `COUNTA_FERNET_KEY` — required; signs session cookies.
- `COUNTA_WEB_BASE_URL`, `COUNTA_WEB_HOST`, `COUNTA_WEB_PORT`.
- `COUNTA_REGISTRATION_MODE` — `open` / `invite` / `closed`.
- `COUNTA_REGISTRATION_INVITE_CODE`.
- `COUNTA_STRICT_PASSWORD_POLICY`.
- `COUNTA_SMTP_USER`, `COUNTA_SMTP_PASSWORD`, `COUNTA_SMTP_FROM` — optional email.
- `COUNTA_DB_PATH` — optional; override the SQLite database path. Defaults to `~/.counta/counta.db`. Useful when running inside containers (e.g. PRoot) where the runtime `$HOME` differs from the persistent data directory.

### 7.2 Runtime startup

`app.on_event("startup")` (`src/counta/web/app.py::_ensure_catalog`):
1. Ensures owner tenant exists.
2. Seeds default categories for the owner.
3. Seeds money registry from existing accounts.
4. Seeds glossary.
5. Ensures at least one admin exists.

### 7.3 Production runtime

Current prod runs on a Samsung Galaxy A30 (Termux + PRoot Ubuntu):
- Counta web: tmux session `counta`, uvicorn on `127.0.0.1:8810`.
- `COUNTA_DB_PATH=/data/data/com.termux/files/home/.counta/counta.db` so the database lives in persistent Termux home, not inside the ephemeral PRoot container rootfs.
- Public access: Cloudflare Tunnel session `cf`.
- MacBook launchd agents (`online.avalone.counta-web`, `online.avalone.counta-tunnel`) are retired.

See `denis-root-continuity/skills/infrastructure.md` for A30 access and service commands.

### 7.4 Deploy gate

**Every change must pass `uv run python scripts/pre_flight.py` before deploy or merge.**

The script checks:
1. Python syntax for all `src/counta/*.py`.
2. `pytest -q` all green.
3. `scripts/check_i18n.py` green (ru/en/ko coverage, no untranslated strings).
4. Inline JS in `app.html` parses without syntax errors (bun/node).
5. Local server `/healthz` responds if running.

---

## 8. Testing

- Run: `uv run pytest -q`
- Fixtures create a temp SQLite DB, reload core modules, create an owner user, and sign a session cookie.
- Key test files:
  - `tests/test_sqlledger.py` — ledger invariants.
  - `tests/test_tenant_isolation.py` — users cannot see each other's data.
  - `tests/test_api_refactor_smoke.py` — API smoke tests.
  - `tests/test_currency.py` — cross-currency transfer guard.

---

## 9. Extending Counta / the Avalone ecosystem

The operator wants other Avalone apps to share users: register once at `avalone.online` and be logged into all apps (including Counta).

### 9.1 Recommended pattern: central identity portal

Build a small central auth service at `avalone.online`:

- **OAuth2 / OpenID Connect provider** (or a lightweight cookie+JWT service).
- Users register/login at `https://avalone.online/auth`.
- Each app (Counta, future apps) becomes an OAuth2 client.
- On first visit, Counta redirects to the portal; portal redirects back with a token/code.
- Counta maps the portal user id to a local `tenant_id`. Existing Counta users can be linked by email or by a one-time migration.

### 9.2 What the portal needs at minimum

No marketing site is required. The portal can be just:
- `/login` and `/register` pages.
- A tiny logged-in dashboard listing connected apps (Counta + future ones).
- Logout / session management.

Later, a public landing page can be added without changing the auth flow.

### 9.3 Alternative patterns

| Approach | Pros | Cons |
|---|---|---|
| Central OAuth2 portal (recommended) | Single source of truth; apps stay independent; standard libraries exist | Need to build/maintain the portal |
| Shared user DB + JWT | Simpler if all apps are on the same infrastructure | Tight coupling; schema changes hurt everyone |
| Per-app DB with user sync events | Apps stay autonomous | Eventual consistency; conflict resolution needed |

### 9.4 Counta changes needed

1. Replace local password login with OAuth2 callback handler.
2. Keep `tenant_id` internally, but add `portal_user_id` column to `users`.
3. Keep session cookie signed by Counta, but seed it from the portal token instead of local password check.
4. Keep tenant isolation logic unchanged — it already scopes all data by user id.

---

## 10. Decisions to respect

- **ERPNext is gone forever.** Do not suggest bringing it back or running Docker/Frappe commands.
- **AI/LLM is gone forever.** Do not re-add `litellm`, OpenAI, Groq, vision, or STT.
- **Glossary-first:** every user-facing string has a neutral alphanumeric key; `ru/en/ko` are translations.
- **Buttons before free text:** new flows should start as structured button flows.
- **No money is silently lost:** any ledger change must keep `assert_balanced()` true.
- **Hard-delete is allowed** now that we own the ledger; implement with explicit friction.

---

## 11. Checks before reporting done

- Run `uv run python scripts/pre_flight.py` and confirm PASS.
- Runtime check on the real UI (local or prod) for the full lifecycle of the feature.
- All three languages (ru/en/ko) covered for any new UI string.

---

## 12. Safety

- Do not put secrets in code or logs; use `~/infrastructure-secrets.env` / `~/counta-secrets.env`.
- Do not modify or delete `~/.counta/counta.db` without a backup.
- Do not run Docker commands for ERPNext — it is gone.
- Any ledger change must keep `assert_balanced()` true.
