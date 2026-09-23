# CSW — Credit Scorecards Workbench

A tool for building, validating, and documenting credit risk scorecards
(Application and Behavioural, with ML models for benchmarking).

See [`.claude/plans`](../../.claude/plans) in this session, or ask Claude,
for the full development plan and roadmap.

## Structure

- `engine/` — pure Python statistical/modeling engine (no web/DB dependencies)
- `api/` — FastAPI backend, thin HTTP layer over `engine`, SQLite project storage
- `web/` — React + TypeScript frontend (wizard-style UI)
- `tests/` — pytest suite for `engine`

## Running locally

Backend:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ./engine -e ./api
uvicorn app.main:app --app-dir api --port 8000
```

Frontend:

```bash
cd web
npm install
npm run dev
```

Then open http://localhost:5173.

## Tests

```bash
source .venv/bin/activate
pip install -e ./engine[dev]
python -m pytest tests/
```

## Deploying

See [`DEPLOY.md`](DEPLOY.md) for running this on-prem with Docker, HTTPS
via your internal CA, and Azure AD SAML SSO.
