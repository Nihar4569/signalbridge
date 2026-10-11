// All backend calls live here.
// The API base can be overridden at deploy time (see docs/frontend_setup.md):
//   VITE_API_BASE=https://your-cloud-run-url  npm run build
export const API_BASE =
  import.meta.env.VITE_API_BASE || window.SIGNALBRIDGE_API || "http://localhost:8000";

async function get(path) {
  const res = await fetch(API_BASE + path);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function post(path, body) {
  const res = await fetch(API_BASE + path, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  health: () => get("/health"),
  overview: () => get("/overview"),
  map: () => get("/map"),
  incidents: () => get("/incidents"),
  plan: (sku, loc) => get(`/plans/${sku}/${loc}`),
  explain: (sku, loc) => get(`/plans/${sku}/${loc}/explain`),
  ask: (sku, loc, question) => post(`/plans/${sku}/${loc}/ask`, { question }),
  askAll: (question, history) => post("/assistant/ask", { question, history }),
  approve: (sku, loc) => post(`/plans/${sku}/${loc}/approve`),
  signals: (loc) => get(`/signals/${loc}`),
  fulfillments: () => get("/fulfillments"),
};

// ---- formatting helpers -----------------------------------------------------

/** Integer paise -> "₹1,13,000" */
export function rupees(minor) {
  if (minor == null) return "—";
  return "₹" + Math.round(minor / 100).toLocaleString("en-IN");
}

/** Integer paise -> "₹6.25 L" (compact, for KPI tiles) */
export function rupeesShort(minor) {
  if (minor == null) return "—";
  const r = minor / 100;
  if (r >= 1e7) return "₹" + (r / 1e7).toFixed(2) + " Cr";
  if (r >= 1e5) return "₹" + (r / 1e5).toFixed(2) + " L";
  return "₹" + Math.round(r).toLocaleString("en-IN");
}

export const day = (ts) => (ts ? String(ts).slice(0, 10) : "—");
