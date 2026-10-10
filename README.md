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
cd signalbridge
uv sync --extra dev            # or: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt
uv run python -m scripts.demo  # or: python -m scripts.demo
```

You'll see a port delay turn a healthy order into an **80-unit shortage**, then
SignalBridge build a governed recovery plan. Run the tests with
`uv run python -m pytest -q` (7 should pass).

Full setup (both `uv` and `pip`) → **[docs/start.md](docs/start.md)**.

---

## What it does (5 capabilities)

| Capability | Plain meaning |
|---|---|
| **Impact Triage** | Keep only the shipments that will really cause a stockout |
| **Margin Optimization** | Don't spend ₹100 to save ₹60 |
| **Internal Balancing** | Use our own DC / dark-store stock before buying outside |
| **Multi-Tier Governance** | Small fix → local planner; big spend → executive |
| **Predictive Surplus** | Warn when the late shipment will cause future overstock |

---

## How it's built

```text
backend/domain/   the math & decisions — pure python, fully tested  <- start here
backend/agent/    Google ADK agent: triage -> recovery -> governance
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
| [docs/simple.md](docs/simple.md) | How the code is wired, traced click-by-click |
| [docs/calculation.md](docs/calculation.md) | The math, with worked examples |
| [docs/architecture.md](docs/architecture.md) | The big picture + diagrams |
| [docs/agents.md](docs/agents.md) | What each AI agent does, in plain words |
| [docs/schema.md](docs/schema.md) | The database model |
| [docs/external_api.md](docs/external_api.md) | The real free APIs (weather + news) |
| [docs/scheduler.md](docs/scheduler.md) | How to run the monitor on a timer |
| [docs/manual_work.md](docs/manual_work.md) | Human-only steps (Firebase, keys, deploy) |
| [docs/blueprint.md](docs/blueprint.md) | The full original design |
| [AGENTS.md](AGENTS.md) | Rules for editing this repo (read before coding) |
| [todo.md](todo.md) | Our shared plan (Vibe_work + manual_work) |

---

## Status

Early base version. The **core recovery engine runs and is tested** on local
fixtures. Cloud storage (Firestore), login, and deployment are set up manually —
see [docs/manual_work.md](docs/manual_work.md). This prototype does **not** make
real purchases or move real goods.
