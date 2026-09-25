# CSW — Credit Scorecards Workbench

Formerly "ScoreX"; the GitHub repo is still named `ScoreX`. Full scorecard
lifecycle tool: ingestion → target/sampling → WOE binning → selection →
logistic scorecard → ML benchmark + final model selection → scaling →
validation (KS/AUC/PSI/CSI) → reason codes → reporting/export. Also a
Decision Tree (strategy/policy) project type, multi-user auth with role
labels + audit trail, and champion/challenger versioning.

- `engine/credittool_engine/` — pure Python modeling logic, no web/DB deps
- `api/app/` — FastAPI routers over the engine, SQLite storage
- `web/` — React + TypeScript, one sidebar step/page per pipeline stage
- `tests/` — pytest for the engine

## Working with the user

- Credit-risk practitioner: use WOE/IV, PDO, PSI/CSI, reason codes,
  champion/challenger directly; no tutorials. Give concise trade-offs.
- Ask (AskUserQuestion, with a recommended option) before changes that
  reshape the pipeline, the DB schema, or add a new step/page. For
  open-ended "what should we add / X vs Y" questions, give a short direct
  recommendation and wait for a go-ahead before building.
- A new decision point in the workflow gets its own sidebar step/page,
  not a control bolted onto an existing panel.

## Conventions

- Routers that depend on the deployed model branch on
  `project.artifacts.final_model_selection.source` (logistic vs ML).
- `API_BASE` in `web/src/api.ts` is build-time configurable
  (`VITE_API_BASE`); production default is same-origin `/api`. Never
  hardcode `localhost`.
- Model Building keeps every fit as a candidate (`api/app/candidates.py`);
  one candidate per model type is active (logistic = the `modeling`
  artifact, each ML algorithm = its `ml_benchmark` result). New fits don't
  activate themselves once one is active. `POST /rebuild` re-runs Final
  Model Selection → Scaling → Validation with the remembered
  `downstream_settings`.
- Auth: local accounts plus Azure AD SAML (`api/app/saml_config.py`,
  `routers/saml_auth.py`). SAML role comes from Azure AD group claims on
  each login; `UserRecord.auth_source` is "local" or "saml".

## Testing

- Engine: pytest unit tests on small synthetic datasets
  (`python -m pytest tests/`).
- API: verify with curl or the browser against running dev servers. Do
  not use FastAPI TestClient — it fails here (needs `httpx2`). For a full
  traceback, import the router and call the endpoint function directly in
  `python -c` with an `AuthUser`.
- Any code generator (scoring code, SQL, exported scripts) needs a
  round-trip test: exec the generated code and compare its output (values
  and types) to the direct engine computation — not just substring checks.
- Docker isn't available in the Claude sandbox: validate deployment
  changes with `docker compose config` and by exercising the Python
  settings logic directly. See `DEPLOY.md`.
