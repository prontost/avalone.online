# Counta

Personal/family double-entry bookkeeping PWA at `https://counta.avalone.online`.

- **Own SQLite ledger** — no external accounting system, no ERPNext, no AI.
- **Multi-tenant** — one DB instance can host a few users (family/small group).
- **i18n-first** — `ru` / `en` / `ko` from a central glossary.
- **Deterministic analytics** — reports, trends, and financial tips are rule-based.
- **Live currency conversion** — fiat via open.er-api.com, crypto via CoinGecko.

## Stack

- Python ≥3.13, managed with `uv`
- FastAPI + Uvicorn
- SQLite (`~/.counta/counta.db`; override with `COUNTA_DB_PATH`)
- Jinja2 + vanilla JS SPA
- `itsdangerous` signed session cookies
- pytest for tests

## Dev

```bash
uv sync
# Create .env from example and fill COUNTA_FERNET_KEY at minimum:
cp .env.example .env
# Optional: override SQLite path (default is ~/.counta/counta.db)
# export COUNTA_DB_PATH=/path/to/counta.db
uv run python scripts/pre_flight.py   # deploy gate
uv run uvicorn counta.web.app:app --host 127.0.0.1 --port 8810 --reload
```

Open `http://127.0.0.1:8810`.

## Tests

```bash
uv run pytest -q
```

## Deploy gate

Every change must pass:

```bash
uv run python scripts/pre_flight.py
```

This checks Python syntax, tests, i18n coverage, and inline JS syntax.

## Docs for agents

See `AGENTS.md` for architecture, patterns, and operating rules.
