# start.md — Set up SignalBridge

This gets the project running on your machine. The **core demo and tests need no
cloud, no API key, and no internet** — so you can see it work in two minutes.

There are two ways to set up. Pick one. **`uv` is recommended** (faster, simpler);
`pip` is the familiar fallback.

> You need **Python 3.10 or newer**. Check with `python3 --version`.
> If yours is older, `uv` can install a newer Python for you automatically (see below).

---

## Option A — with `uv` (recommended)

[`uv`](https://docs.astral.sh/uv/) is a fast Python package manager.

```bash
# 0. Install uv once (skip if you already have it)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 1. Go into the project
cd signalbridge

# 2. Install everything (uv reads pyproject.toml and even fetches Python 3.11)
uv sync --extra dev

# 3. See it work — the core recovery demo (no cloud needed)
uv run python -m scripts.demo

# 4. Run the tests
uv run python -m pytest -q
```

Everyday commands with uv:

| What | Command |
|---|---|
| Run the demo | `uv run python -m scripts.demo` |
| Run tests | `uv run python -m pytest -q` |
| Start the API | `uv run uvicorn backend.app.main:app --reload --port 8000` |
| Run the monitor once | `uv run python -m backend.worker.main` |
| Run the ADK agent | `uv run adk run backend/agent` *(needs a key — see below)* |

---

## Option B — with `pip` + venv

```bash
# 1. Go into the project
cd signalbridge

# 2. Create and activate a virtual environment (use a 3.10+ python)
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install runtime + dev tools
pip install -r requirements-dev.txt

# 4. See it work
python -m scripts.demo

# 5. Run the tests
python -m pytest -q
```

Everyday commands with pip (venv activated):

| What | Command |
|---|---|
| Run the demo | `python -m scripts.demo` |
| Run tests | `python -m pytest -q` |
| Start the API | `uvicorn backend.app.main:app --reload --port 8000` |
| Run the monitor once | `python -m backend.worker.main` |
| Run the ADK agent | `adk run backend/agent` *(needs a key — see below)* |

> Prefer shortcuts? There's a `Makefile`: `make setup-uv`, `make demo`, `make test`, `make api`.

---

## Run the full app (backend + frontend)

This is the end-to-end prototype: a dashboard that talks to the API. Use **two
terminals**.

```bash
# Terminal 1 — the backend API (port 8000)
cd signalbridge
uv run uvicorn backend.app.main:app --reload --port 8000
#   (pip users, venv active:  uvicorn backend.app.main:app --reload --port 8000)

# Terminal 2 — the frontend (port 5173)
cd signalbridge/frontend
python3 -m http.server 5173
```

Then open **http://localhost:5173** and click **Scan for risk**.
You'll see the incident → open it → review the plan → **Explain with AI** →
**Approve & reserve**.

The frontend is plain HTML/JS (no npm, no build). How it's wired is explained in
[simple.md](simple.md).

---

## What you should see

`python -m scripts.demo` prints the jacket scenario: a port delay turns a healthy
order into an **80-unit shortage**, then SignalBridge uses 20 units of internal
stock, buys 60 from a supplier, confirms it's worth it, and routes it for
approval. That is the whole product in one screen.

`pytest` should say **11 passed** (domain + models/store).

---

## Set up the config file

```bash
cp .env.example .env
```

For the **core demo and the API read-paths you don't need to change anything** —
`DATA_BACKEND=local` reads the JSON files in `fixtures/`.

You only edit `.env` when you want to:
- run the **AI agent** → add `GOOGLE_API_KEY` (free key from <https://aistudio.google.com/apikey>)
- use **Firestore** or **deploy** → see below and [manual_work.md](manual_work.md)

---

## Use Firestore instead of fixtures (optional)

The app already has a real `FirestoreStore` (`backend/core/store.py`). Fixtures stay
the seed source; runtime reads go to Cloud Firestore when you flip the switch.

```bash
# 1. Copy env and point at your Firebase/GCP project (see .firebaserc)
cp .env.example .env
#    DATA_BACKEND=firestore
#    GOOGLE_CLOUD_PROJECT=signalbridge-8b80a   # or your project id
#    TENANT_ID=buildx-demo

# 2. Login (once)
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID

# 3. Create Firestore Native DB in console if needed (asia-south1 matches firebase.json)

# 4. Validate mapping, then seed
python -m scripts.seed_firestore --dry-run
python -m scripts.seed_firestore

# 5. Deploy rules + indexes
firebase deploy --only firestore

# 6. Run API — GET /health should show data_backend: firestore
uvicorn backend.app.main:app --reload --port 8000
```

Data path: `tenants/{TENANT_ID}/{collection}/{doc_id}`  
Models: `backend/models/` · IDs: `backend/models/ids.py`

---

## Run the AI agent (optional)

The agent uses Gemini, so it needs a key.

```bash
# 1. Put your key in .env
echo "GOOGLE_API_KEY=your_key_here" >> .env

# 2. Run the agent in your terminal
uv run adk run backend/agent      # or: adk run backend/agent

# Or open the ADK web UI to chat with it
uv run adk web
```

Try asking it: *"Is JACKET-BLUE-M at WH-MUM at risk, and what should we do?"*

---

## Project layout (where things live)

```text
signalbridge/
├── backend/
│   ├── core/       config, data store, logging
│   ├── domain/     the math & decisions (pure python, tested)  <- start here
│   ├── adapters/   supplier simulator, news
│   ├── agent/      the Google ADK agent (triage -> recovery -> governance)
│   ├── app/        the FastAPI web API
│   └── worker/     the background monitor
├── fixtures/       synthetic demo data (JSON)
├── scripts/        demo.py and the Firestore seeder
├── tests/          unit tests (no cloud needed)
└── docs/           you are here
```

New to the codebase? Read the files in this order:
1. [architecture.md](architecture.md) — the big picture
2. [agents.md](agents.md) — what each agent does, in plain words
3. [schema.md](schema.md) — the data model
4. `backend/domain/exposure.py` — the one function everything depends on

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `No module named backend` | Run commands from the `signalbridge/` folder, not inside `backend/`. |
| `python: command not found` | Use `python3`, or let `uv` manage Python via `uv run`. |
| ADK agent errors about a key | Add `GOOGLE_API_KEY` to `.env` (see above). |
| `NotImplementedError: FirestoreStore` | You set `DATA_BACKEND=firestore` before setting it up. Set it back to `local`. |
