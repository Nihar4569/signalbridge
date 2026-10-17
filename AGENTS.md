# AGENTS.md — How to work in this repo (for humans and AI assistants)

This file tells any coding assistant (and any new teammate) how to make changes
here **without breaking things**. If you are "vibe coding" with an AI, point it at
this file first. Keep changes small, simple, and explained.

---

## The golden rule of this codebase

> **Gemini/agents reason and explain. `backend/domain/` does the math and the
> writes. A human approves anything that costs money.**

If a change makes the AI do arithmetic or write to the database directly, it is
wrong. Put the logic in `backend/domain/` and have the agent *call* it.

---

## Project shape (know this before editing)

```text
backend/core/      config, local/snapshot/Firestore stores, logging
backend/domain/    deterministic calculations and state logic (no model calls)
backend/adapters/  live weather/news, simulated supplier, optional SMTP
backend/ai/        main Gemini REST interpretation, explanations and Q&A
backend/agent/     optional single ADK weather/news agent
backend/app/       FastAPI routes and built-frontend serving
backend/worker/    guarded scan worker, optional timer (off by default)
frontend/          React/Vite dashboard (dev 3000, preview 5173)
fixtures/          synthetic business records and isolated decision cases
scripts/           demo.py, seed_firestore.py
tests/             unit tests (must stay green)
docs/              README.md index, architecture, schema, setup and roadmap
```

---

## Rules for every change

1. **Keep it beginner-readable.** Prefer clear, boring code over clever code.
   A new teammate should understand a function without a diagram.
2. **Small steps.** One change at a time. Don't refactor unrelated code.
3. **Pure logic goes in `backend/domain/`.** No network, no cloud, no AI there.
   That folder must stay testable with plain numbers.
4. **Never store a number you can calculate.** `free_to_use = on_hand - reserved`
   is derived, never saved. (See [docs/schema.md](docs/schema.md) representation rules.)
5. **Money is integer minor units (paise) + a currency code.** Never a float.
6. **Quantities are whole integers.** Timestamps are UTC ISO-8601 strings.
7. **Add a test for any new domain logic.** Tests must pass: `pytest -q`.
8. **Comments explain *why*, not *what*.** One line is usually enough.
9. **Secrets never touch the repo.** No keys in code, logs, or fixtures. Use `.env`.
10. **Match the data contract.** If you change a field name, change it in the
    fixtures, the domain code, and [docs/schema.md](docs/schema.md) together.

---

## How to add a new feature (the pattern)

Say you want a new rule, e.g. "prefer the greener supplier".

1. Write a **pure function** in `backend/domain/` (e.g. `sustainability.py`) that
   takes plain data and returns a plain result. No cloud.
2. Write a **test** for it in `tests/`.
3. Expose it through the relevant application route or a thin typed wrapper.
   If an agent needs the capability, its tool docstring must describe the contract.
4. Register an ADK tool only if the optional agent should actually use it. The
   main web workflow uses `backend/ai/gemini.py`, not an ADK multi-agent pipeline.
5. If the API needs it, add a route in `backend/app/routers/`.
6. Update the relevant doc in `docs/`.

Do **not** jump straight to step 3. The logic lives in `domain/` first.

---

## Before you say "done"

Run these and make sure they pass:

```bash
python -m scripts.demo     # the demo still tells the recovery story
pytest -q                  # all tests green
ruff check .               # style is clean
```

If you touched data shapes, also check the API still starts:

```bash
uvicorn backend.app.main:app --reload --port 8000   # then open http://localhost:8000/docs
```

---

## What NOT to do

- ❌ Don't let the agent compute money or quantities — call `domain/`.
- ❌ Don't add a second copy of a number that can drift (stock, totals).
- ❌ Don't add big new libraries or cloud services "just in case."
- ❌ Don't hardcode secrets, project IDs, or keys.
- ❌ Don't delete the fixtures or make the demo need the internet.
- ❌ Don't break `DATA_BACKEND=local` — it must always work with no cloud.
- ❌ Don't describe planned authentication, transactions, scheduled jobs or
  physical supplier execution as already implemented. See [docs/roadmap.md](docs/roadmap.md).

---

## Good first tasks

- Add a new SKU + shipment to `fixtures/` and watch the demo react.
- Add a test for a tricky deadline edge case in `tests/test_exposure.py`.
- Add a regression for a current execution boundary before changing it; `FirestoreStore` already exists.
- Add a `/incidents` filter by severity in `backend/app/routers/incidents.py`.

When in doubt, read [docs/README.md](docs/README.md), [docs/architecture.md](docs/architecture.md)
and [docs/roadmap.md](docs/roadmap.md) first. Preserve the golden rule above.
