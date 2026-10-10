# todo.md — our shared plan

This is where we (you + the AI assistant) stay in sync. Two lists:
**Vibe_work** = things the AI can build in code. **Manual_work** = things only
you can do (accounts, consoles, secrets).

Last updated: 2026-10-10 · Status: **prototype runs end-to-end on dummy data**.

---

## ✅ Done

- [x] Core recovery engine (`backend/domain/`) — exposure, internal balancing,
      margin, surplus, governance, reservations. Pure Python, unit-tested.
- [x] FastAPI backend with 4 endpoints (`/incidents`, `/plans`, `/explain`, `/approve`).
- [x] Gemini wired via REST for the "Explain with AI" button (key in `.env`). **Tested, working.**
- [x] Frontend dashboard (`frontend/`) — scan → plan → explain → approve. No build step.
- [x] **Live external APIs (free, no key): Open-Meteo weather + GDELT news**, with location
      filtering. Exposed via `GET /signals/{location}`, the `signal_agent` (ADK), and the worker.
- [x] Dummy data in `fixtures/`. 7 unit tests pass.
- [x] Docs: start, simple, calculation, architecture, agents, schema, external_api, scheduler, manual_work.

---

## 🟦 Vibe_work (the AI can do these in code, no accounts needed)

Pick any; they don't need cloud access.

- [ ] **More demo data** — add 2–3 more SKUs / shipments / an order that is fine
      (shows triage filtering out noise). Pure fixtures + a test.
- [ ] **Customer priority (VIP first)** — when stock is scarce, allocate to VIP
      orders first. New `domain/allocation.py` + a tool + a column in the UI.
- [ ] **"What-if" slider** — let the UI change the assumed delay date and re-run
      exposure live. Frontend + a query param on `/plans`.
- [ ] **Severity sorting** — rank incidents by revenue-at-risk on the dashboard.
- [ ] **Rejected-options clarity** — show *why* each supplier was rejected (already
      in the data; just surface it nicer in the UI).
- [x] **`FirestoreStore` class** — `backend/core/store.py` + models + seed script
      ready. Still needs you to create the DB / auth — see manual_work.
- [ ] **Full ADK agent run endpoint** — expose the 3-agent pipeline
      (`backend/agent/`) over an endpoint instead of the single REST call.
- [ ] **Tests for the API** — add endpoint tests with FastAPI's TestClient.
- [ ] **Dockerfile** — containerize the backend so it's ready for Cloud Run.
- [ ] **Perishables rescue (future scope)** — reroute near-expiry stock. New
      `domain/perishable.py`; fields already reserved in the schema.

> Tell me which ones you want and I'll build them.

---

## 🟥 Manual_work (only you can do these)

Full steps are in [docs/manual_work.md](docs/manual_work.md). Short list:

- [ ] Nothing is required to keep testing the prototype — it already runs on dummy data.
- [ ] **When ready for a real DB:** create a Google Cloud project + enable billing,
      create a **Firestore** database (Native mode), run `scripts/seed_firestore.py`.
- [ ] **For login/roles:** set up **Firebase Authentication**.
- [ ] **For a live URL:** deploy the backend to **Cloud Run**, host the frontend on
      **Firebase Hosting**.
- [ ] **Before the repo is public:** confirm `.env` is not committed, add Firestore
      security rules, set a billing budget alert.

---

## 🔑 What I can unlock if you give me a credential / access

If you set up one of these and give me the key (or connect its MCP), here's the
**extra** work I could then do for you:

| You give me… | …and I can then build |
|---|---|
| **Gemini API key** *(already done ✅)* | AI explanations, and the full ADK triage→recovery→governance agent |
| **Google Cloud project + billing** | Real Firestore storage, Cloud Run deploy configs, Secret Manager for keys |
| **Firebase project** | Login (Auth), hosting the dashboard on a public URL, push notifications (FCM) |
| **Google Maps Platform key** | A live map of ports / warehouses / suppliers, and road-route ETAs for inland transfers |
| **Google Weather API access** | Weather risk on a shipment's route (storm near a port = early warning) |
| **Document AI processor** | Read a scanned shipment manifest/PDF and pull out SKUs + quantities automatically |
| **BigQuery access** | Match storm/flood map areas to warehouse locations (geographic risk) |
| **A Firestore / GCP MCP server** | Let me inspect and seed your cloud data directly, and verify deploys |

> **For the hackathon prototype you only need the Gemini key** (which is already
> working). Everything else is for scaling up *after* the demo — exactly the plan
> you set: test first, add Firebase/cloud later.

---

## Notes between us

- Keep `DATA_BACKEND=local` until Firestore is set up. Everything runs offline.
- The `.env` holds the Gemini key and is **gitignored** — never commit it.
- Design rule we follow: **AI explains, Python calculates, a human approves.**
