# Run SignalBridge locally

The application has a Python API and a React/Vite frontend. Local records and reference replay need no cloud credentials or model calls. Dependency installation, map tiles/fonts, live weather/news and live Gemini require network access.

## Requirements

- Python 3.10 or newer.
- Node.js 18 or newer and npm.
- [uv](https://docs.astral.sh/uv/) or a Python virtual environment.

Run commands from the repository root unless a frontend directory is specified.

## 1. Install Python dependencies

### With uv

```bash
uv sync --extra dev
```

### With pip

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Windows activation uses `.venv\Scripts\activate`. Pip users can omit `uv run` from subsequent commands while the environment is active.

Copy `.env.example` to an untracked local `.env` if needed. Do not overwrite an existing file containing your configuration. Leave `DATA_BACKEND=local` and `SIGNAL_SCAN_INTERVAL_SECONDS=0` for local development. See [config.py](../backend/core/config.py) for authoritative defaults.

## 2. Start the API and frontend

Terminal 1, repository root:

```bash
DATA_BACKEND=local GOOGLE_API_KEY='' GOOGLE_API_KEY_2='' \
  SIGNAL_SCAN_INTERVAL_SECONDS=0 \
  uv run uvicorn backend.app.main:app --reload --port 8000
```

This command intentionally disables live Gemini keys for the session. To use live Gemini later, configure a valid key and omit those empty overrides.

Terminal 2:

```bash
cd frontend
npm ci
npm run dev
```

Vite development uses **http://localhost:3000**, unless that port is occupied and Vite selects another. Read its terminal output. API documentation is **http://localhost:8000/docs**.

For an isolated first run, open **http://localhost:3000/#/decision-demo** directly and select **Reference replay**. This avoids the operational frontend scan trigger and makes no model call.

Opening operational pages can request weather/news through `POST /scan`, even without a Gemini key. The optional timer being disabled does not disable that page-load trigger.

## 3. Understand the walkthrough

The fixed coffee example has two notices:

- Active closure: 80 units short, 20 internal units, 60 supplier units, ₹3,700 external recovery cost.
- Cancelled strike: no shortage and no new purchase proposal.

All records/notices are synthetic and use a fixed scenario clock. See [decision walkthrough](decision_walkthrough.md). Reference replay is not a successful live-model response.

For **Assess with Gemini**, configure `GOOGLE_API_KEY` in local/deployment secrets and restart the backend without the empty key overrides. `GOOGLE_API_KEY_2` is an optional alternate key. Available quota and model access are required. Both assistants also use this REST integration.

## 4. Demo, regression and build

Run from the repository root:

```bash
DATA_BACKEND=local GOOGLE_API_KEY='' GOOGLE_API_KEY_2='' \
  uv run python -m scripts.demo

DATA_BACKEND=local GOOGLE_API_KEY=offline-test-key GOOGLE_API_KEY_2='' \
  SIGNAL_SCAN_INTERVAL_SECONDS=0 uv run python -m pytest -q

uv run ruff check .
```

The dummy key is non-secret and enables mocked model paths in legacy tests. The current suite was checked on 18 October 2026 with outbound connections blocked: **132 passed**, one deprecation warning. This is a dated local regression result, not live AI accuracy. Use the [benchmark guide](../tests/benchmark/README.md) for its default network-blocked harness.

The terminal jacket demo reads changing operational fixtures. It can correctly print no action needed. It is not guaranteed to reproduce an older 80-jacket recovery example.

Ruff currently has existing findings outside this documentation change; a successful test run does not imply a clean lint run.

Build/preview the frontend:

```bash
cd frontend
npm run build
npm run preview
```

Production preview uses **http://localhost:5173**. The preview is not the Vite development server. Do not serve the React source directory with `python -m http.server`.

## 5. Optional ADK agent

```bash
uv run adk run backend/agent
```

This runs one weather/news tool-using agent, separately from the web application. It needs a valid Gemini key and network quota. See [agents.md](agents.md).

## 6. Optional Firestore

Set up credentials, database and tenant deliberately using [cloud setup](manual_work.md). `DATA_BACKEND=firestore` switches stores; it does not seed data automatically.

`uv run python -m scripts.seed_firestore --dry-run` validates fixtures and prints intended paths without cloud writes. Running the seeder without `--dry-run` writes/overwrites seed documents, so do it only against the intended project/tenant.

## Troubleshooting

| Symptom | Check |
|---|---|
| `No module named backend` | Run from the repository root with the selected Python environment. |
| Frontend missing at 5173 during development | Development uses port 3000; 5173 is preview. |
| API offline / empty views | Verify backend startup, API base, health response body and successful data reads. Empty results are not proof of safety. |
| Live Gemini unavailable | Key configuration, model access and quota. Reference replay remains separate. |
| Firestore initialization failure | Project ID, application credentials/emulator and intended tenant. |
| No recovery in terminal demo | Current fixture state may be covered; use the fixed walkthrough to reproduce recovery. |
| Map unavailable | Tile-provider/network policy. The map is not required for the reference calculations. |

Continue with [architecture](architecture.md), [data contract](schema.md) and [roadmap](roadmap.md).
