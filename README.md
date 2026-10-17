# SignalBridge

**Turn a supply-chain disruption into a traceable inventory recovery plan.**

When a port delay, strike, or storm threatens a shipment, SignalBridge spots the
orders that will actually fall short, finds the cheapest safe way to cover them
(own stock first, then a supplier), checks it's worth the cost, and routes it to
the right person to approve — with evidence at every step.

Built for the **Google Cloud AI Builder Cup** (Retail & Commerce) using
**Google ADK + Gemini**, deployable on **Cloud Run + Firebase**.

---

## See it work in 2 minutes (no cloud, no key)

```bash
# Terminal 1 — backend API
cd signalbridge
uv sync --extra dev
uv run uvicorn backend.app.main:app --reload --port 8000

# Terminal 2 — React dashboard
cd signalbridge/frontend
npm install
npm run dev          # http://localhost:5173
```

Open **http://localhost:5173**, then choose **Decision walkthrough** to compare
the two reference cases without a key. On a threatened operational order,
**✨ AI Plan** shows the calculated proposal and its saved evidence. Gemini
interprets and explains; Python calculates; execution requires human approval.

Production build (one command, deploys anywhere):

```bash
cd frontend && npm run build     # -> frontend/dist/
```

Prefer the terminal? `uv run python -m scripts.demo` runs the whole recovery
engine with no UI. Tests: `uv run python -m pytest -q`.

Full setup → **[docs/start.md](docs/start.md)** and **[docs/frontend_setup.md](docs/frontend_setup.md)**.

## Follow an evidence-backed decision

Open **Decision walkthrough** in the dashboard sidebar. Compare an active channel
closure with a cancelled strike using the same synthetic retail case. Reference
replay works without a key. **Assess with Gemini** runs a real interpretation
with exact source excerpts, route relevance, calculated shortage and recovery
cost. Each run uses an isolated snapshot and performs no operational writes.

The recovery modal also shows an evidence-backed brief from the latest saved
shipment assessment. See **[the walkthrough guide](docs/decision_walkthrough.md)**
for the data assumptions, AI boundaries and test instructions.

---

## What it does (5 capabilities)

| Capability | Plain meaning |
|---|---|
| **Impact Triage** | Keep only the shipments that will really cause a stockout |
| **Margin Optimization** | Don't spend ₹100 to save ₹60 |
| **Internal Balancing** | Use our own DC / dark-store stock before buying outside |
| **Multi-Tier Governance** | Small fix → local planner; big spend → executive (plain rules, a default approver per tier) |
| **Predictive Surplus** | Warn when the late shipment will cause future overstock |

---

## How it's built

```text
backend/domain/   the math & decisions — pure python, fully tested  <- start here
backend/agent/    Google ADK agent (optional chat: checks live weather and news)
backend/app/      FastAPI web API
backend/worker/   background monitor
fixtures/         synthetic demo data (JSON)
docs/             start here ↓
```

The design rule: **the agent reasons and explains; `domain/` code does the math
and the writes; a human approves anything that costs money.**

---

## Docs

| Doc | What's in it |
|---|---|
| [docs/start.md](docs/start.md) | Set up and run (uv **and** pip) |
| [docs/frontend_setup.md](docs/frontend_setup.md) | Run & deploy the dashboard (Firebase Hosting) |
| [docs/map_setup.md](docs/map_setup.md) | Map tiles & how to get a map API key (optional) |
| [docs/simple.md](docs/simple.md) | How the code is wired, traced click-by-click |
| [docs/calculation.md](docs/calculation.md) | The math, with worked examples |
| [docs/architecture.md](docs/architecture.md) | The big picture + diagrams |
| [docs/agents.md](docs/agents.md) | What each AI agent does, in plain words |
| [docs/schema.md](docs/schema.md) | The database model |
| [docs/after_plan_approval.md](docs/after_plan_approval.md) | What auto-happens after approval (PO + emails) |
| [docs/external_api.md](docs/external_api.md) | The real free APIs (weather + news) |
| [docs/scheduler.md](docs/scheduler.md) | How to run the monitor on a timer |
| [docs/manual_work.md](docs/manual_work.md) | Human-only steps (Firebase, keys, deploy) |
| [docs/blueprint.md](docs/blueprint.md) | The full original design |
| [docs/decision_walkthrough.md](docs/decision_walkthrough.md) | Evidence-backed decisions and an isolated active/cancelled notice demo |
| [AGENTS.md](AGENTS.md) | Rules for editing this repo (read before coding) |
| [todo.md](todo.md) | Our shared plan (Vibe_work + manual_work) |

---

## Status

Early base version. The **core recovery engine runs and is tested** on local
fixtures. Cloud storage (Firestore), login, and deployment are set up manually —
see [docs/manual_work.md](docs/manual_work.md). This prototype does **not** make
real purchases or move real goods.
