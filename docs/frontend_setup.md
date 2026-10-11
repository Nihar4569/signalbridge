# frontend_setup.md — Run & deploy the dashboard

The dashboard is a **React app built with Vite**. It compiles to plain static
files (`frontend/dist/`), so deployment is a single command and needs no server.

**Design:** Google Material 3 dark theme (the Gemini palette), a persistent
sidebar, and a Gemini-branded AI planning experience.

```
frontend/
├── package.json        scripts: dev / build / preview
├── vite.config.js
├── index.html          app shell + fonts + Leaflet CSS
├── public/favicon.svg  Gemini spark
└── src/
    ├── main.jsx        entry (HashRouter)
    ├── App.jsx         sidebar + routes
    ├── api.js          every backend call + money formatting
    ├── icons.jsx       inline SVG icons + the Gemini spark
    ├── theme.css       Material 3 design tokens & components
    ├── components/     Sidebar, Topbar, Kpi, MapView, IncidentCard, AiPlanModal
    └── pages/          Dashboard, Shipments, Incidents, Recoveries, Signals, Capabilities
```

---

## 1. First-time setup

```bash
cd signalbridge/frontend
npm install
```

(Node 18+ required.)

---

## 2. Run it locally

You need **two terminals**: the backend serves the data, the frontend serves the UI.

```bash
# Terminal 1 — backend API (port 8000)
cd signalbridge
uv run uvicorn backend.app.main:app --reload --port 8000

# Terminal 2 — frontend dev server (port 5173, hot reload)
cd signalbridge/frontend
npm run dev
```

Open **http://localhost:5173**.

### Or preview the real production build

```bash
cd signalbridge/frontend
npm run build      # outputs to dist/
npm run preview    # serves dist/ on http://localhost:5173
```

---

## 3. The build command (for deployment)

```bash
cd signalbridge/frontend
npm run build
```

Produces `frontend/dist/` (~349 kB JS → **108 kB gzipped**). That folder is the
entire website.

### Pointing the build at your deployed backend

By default the app calls `http://localhost:8000`. For a deployed site, set the
API base at build time:

```bash
VITE_API_BASE=https://signalbridge-api-xxxx.a.run.app npm run build
```

---

## 4. Deploy to Firebase Hosting

`firebase.json` is already configured (`public: frontend/dist` + SPA rewrites).

```bash
# one-time
npm install -g firebase-tools
firebase login
cd signalbridge
firebase use --add          # pick your Google Cloud project

# every deploy
cd frontend && VITE_API_BASE=https://YOUR-CLOUD-RUN-URL npm run build && cd ..
firebase deploy --only hosting
```

Firebase prints your live URL (`https://your-project.web.app`).

> Deploy the backend to Cloud Run first — see [manual_work.md](manual_work.md) —
> so you know the URL to bake in.

---

## 5. What's on each screen

| Sidebar item | What it does |
|---|---|
| **Dashboard** | KPI tiles, the live route map with alerts, and threatened orders |
| **Shipments** | Map + a table of every shipment (lane, carrier, ETA, progress, health) |
| **Threatened orders** | Every order with a real shortage, each with an **AI Plan** button |
| **Recoveries** | What was automated after each approval: timeline, actions, emails |
| **Live signals** | Pick a port/DC → live weather (Open-Meteo) + disruption news (GDELT) |
| **Capabilities** | 9 live features and 5 roadmap features |
| *Coming soon* | VIP allocation, Penalty & claims, Perishables rescue, Settings |

### The AI Plan experience (the centrepiece)

Click the **✨ AI Plan** button on any threatened order:

1. A Gemini-branded modal opens with an animated **"thinking"** sequence.
2. It then shows the full plan in 5 numbered steps — impact before/after,
   internal stock used, **supplier options including the rejected ones and why**,
   the margin verdict, surplus forecast and approval tier.
3. **Gemini's summary** explains it in plain English.
4. Press **Approve & execute** → the modal becomes a live fulfilment view:
   reservation receipt, automation timeline, the PO + transfer created, and the
   actual **emails** sent (expandable).

---

## 6. Map tiles

The map uses **free OpenStreetMap tiles with a dark filter — no API key**.
Want a premium dark basemap? See [map_setup.md](map_setup.md).

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Everything shows "—" / "API offline" | Backend isn't running, or `VITE_API_BASE` is wrong. |
| `npm run dev` fails | Run `npm install` first; needs Node 18+. |
| Map blank | Offline or a blocker is stopping the tile CDN. |
| Deployed site shows no data | You built without `VITE_API_BASE`, so it's calling localhost. Rebuild with the Cloud Run URL. |
| Blank page after deploy | Make sure `firebase.json` has `public: "frontend/dist"`. |

> The previous no-build static dashboard is kept in **`frontend-legacy/`** for
> reference. It is not used by the build and can be deleted once you're happy.
