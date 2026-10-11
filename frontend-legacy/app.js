// SignalBridge frontend — plain JavaScript, no framework, no build step.
// It calls the backend API and draws the control tower. Read top to bottom.

const q = (id) => document.getElementById(id);

// Backend URL comes from config.js (window.SIGNALBRIDGE_API). See frontend_setup.md.
const API_BASE = window.SIGNALBRIDGE_API || "http://localhost:8000";

// ---- tiny helpers -----------------------------------------------------------

// Format integer paise (minor units) as full rupees, e.g. 11300000 -> "₹1,13,000".
function rupees(minor) {
  if (minor == null) return "—";
  return "₹" + (minor / 100).toLocaleString("en-IN");
}

// Short rupees for KPI tiles, e.g. 62492000 -> "₹6.25 L".
function rupeesShort(minor) {
  const r = minor / 100;
  if (r >= 1e7) return "₹" + (r / 1e7).toFixed(2) + " Cr";
  if (r >= 1e5) return "₹" + (r / 1e5).toFixed(2) + " L";
  return "₹" + Math.round(r).toLocaleString("en-IN");
}

async function api(path) {
  const res = await fetch(API_BASE + path);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function apiPost(path) {
  const res = await fetch(API_BASE + path, { method: "POST" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// Animate a number tile from 0 to its value.
function animateNumber(el, to, fmt) {
  const dur = 700, start = performance.now();
  function step(now) {
    const p = Math.min(1, (now - start) / dur);
    const v = to * (0.5 - Math.cos(Math.PI * p) / 2); // ease in-out
    el.textContent = fmt ? fmt(v) : Math.round(v);
    if (p < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// ---- top bar: clock + health ------------------------------------------------

function startClock() {
  const el = q("clock");
  const tick = () => (el.textContent = new Date().toLocaleTimeString());
  tick();
  setInterval(tick, 1000);
}

async function checkHealth() {
  const el = q("api-status");
  try {
    await api("/health");
    el.textContent = "● API connected";
    el.style.color = "var(--good)";
  } catch {
    el.textContent = "● API offline";
    el.style.color = "var(--bad)";
  }
}

// ---- KPI row ----------------------------------------------------------------

async function loadOverview() {
  try {
    const o = await api("/overview");
    animateNumber(q("kpi-shipments"), o.shipments_tracked);
    animateNumber(q("kpi-ontime"), o.on_time);
    animateNumber(q("kpi-atrisk"), o.at_risk);
    animateNumber(q("kpi-orders"), o.orders_at_risk);
    animateNumber(q("kpi-revenue"), o.revenue_at_risk_minor, rupeesShort);
    animateNumber(q("kpi-alerts"), o.active_alerts);
  } catch {
    /* KPIs stay as — if the API is down */
  }
}

// ---- the live map -----------------------------------------------------------

const COLORS = { green: "#2fd69b", amber: "#f2b84b", red: "#ef5b5b" };
let MAP = null;
const FLEET = []; // moving shipment markers

function initMap() {
  MAP = L.map("map", { worldCopyJump: true, zoomControl: true }).setView([20, 55], 3);
  // Default: free OpenStreetMap tiles (no API key) with a dark CSS filter.
  // To use a premium provider, set window.SIGNALBRIDGE_TILES — see docs/map_setup.md.
  const tiles = window.SIGNALBRIDGE_TILES || {
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution: "© OpenStreetMap contributors",
    className: "sb-dark-tiles",
  };
  L.tileLayer(tiles.url, {
    attribution: tiles.attribution,
    maxZoom: 19,
    className: tiles.className || "",
  }).addTo(MAP);
}

// Returns a function t->[lat,lon] that walks the route by distance.
function makeSampler(points) {
  const segs = [];
  let total = 0;
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i], b = points[i + 1];
    const d = Math.hypot(b[0] - a[0], b[1] - a[1]);
    segs.push({ a, b, d });
    total += d;
  }
  return (t) => {
    if (total === 0) return points[0];
    let dist = Math.max(0, Math.min(1, t)) * total;
    for (const s of segs) {
      if (dist <= s.d) {
        const f = s.d ? dist / s.d : 0;
        return [s.a[0] + (s.b[0] - s.a[0]) * f, s.a[1] + (s.b[1] - s.a[1]) * f];
      }
      dist -= s.d;
    }
    return points[points.length - 1];
  };
}

function routePopup(r) {
  return `<div class="pop-title">${r.shipment_id} · ${r.sku}</div>
    <div class="pop-meta">${r.quantity} units · ${r.carrier_id}<br>
    ETA ${(r.eta || "").slice(0, 10)} · status: <b>${r.health}</b></div>`;
}

async function loadMap() {
  const d = await api("/map");
  const allPts = [];

  d.routes.forEach((r) => {
    allPts.push(...r.points);
    const poly = L.polyline(r.points, {
      color: COLORS[r.color] || COLORS.green,
      weight: 3,
      opacity: 0.85,
      dashArray: r.health === "delayed" ? "6 8" : null,
    }).addTo(MAP).bindPopup(routePopup(r));

    const samp = makeSampler(r.points);
    const icon = L.divIcon({
      className: "",
      html: `<div class="ship-dot ${r.color}"></div>`,
      iconSize: [16, 16],
      iconAnchor: [8, 8],
    });
    const marker = L.marker(samp(r.progress), { icon }).addTo(MAP).bindPopup(routePopup(r));
    // Realistic slow speeds (fraction of the route per second). A whole ocean
    // route takes minutes on screen; a delayed ship barely crawls.
    const speed = r.health === "delayed" ? 0.0005 : r.health === "at_risk" ? 0.0018 : 0.004;
    FLEET.push({ marker, poly, samp, t: r.progress, speed, sku: r.sku, dest: r.destination_location_id });
  });

  d.locations.forEach((l) => {
    const icon = L.divIcon({
      className: "",
      html: `<div class="loc-dot ${l.type}"></div>`,
      iconSize: [10, 10],
      iconAnchor: [5, 5],
    });
    L.marker([l.lat, l.lon], { icon }).addTo(MAP)
      .bindPopup(`<div class="pop-title">${l.name}</div><div class="pop-meta">${l.type}</div>`);
  });

  d.alerts.forEach((a) => {
    const emoji = a.type === "weather" ? "⛈️" : "⛔";
    const icon = L.divIcon({
      className: "",
      html: `<div class="alert-pin">${emoji}</div>`,
      iconSize: [26, 26],
      iconAnchor: [13, 13],
    });
    L.marker([a.lat, a.lon], { icon }).addTo(MAP)
      .bindPopup(`<div class="pop-title">${a.title}</div><div class="pop-meta">${a.detail}</div>`);
  });

  if (allPts.length) MAP.fitBounds(allPts, { padding: [30, 30] });

  q("ticker-text").textContent =
    d.alerts.map((a) => `${a.type === "weather" ? "⛈️" : "⛔"} ${a.title}`).join("      •      ")
    || "No active alerts";

  requestAnimationFrame(tickFleet);
}

let _lastFrame = 0;
function tickFleet(now) {
  const dt = _lastFrame ? (now - _lastFrame) / 1000 : 0;
  _lastFrame = now;
  FLEET.forEach((f) => {
    // Move forward slowly and stop at the destination (no teleport loop).
    if (f.t < 1) {
      f.t = Math.min(1, f.t + f.speed * dt);
      f.marker.setLatLng(f.samp(f.t));
    }
  });
  requestAnimationFrame(tickFleet);
}

// ---- features grid ----------------------------------------------------------

const FEATURES = [
  ["Impact Triage", "Filters thousands of signals down to the orders that truly break.", true],
  ["Margin Optimization", "Never spend more to recover than the order is worth.", true],
  ["Internal Balancing", "Uses our own DC / dark-store stock before buying outside.", true],
  ["Multi-Tier Governance", "Routes approval by value: planner → manager → exec.", true],
  ["Predictive Surplus", "Flags future overstock from late shipments arriving.", true],
  ["Live Route Map", "Real-time route tracking with weather & disruption alerts.", true],
  ["Live Weather + News", "Open-Meteo + GDELT, filtered by location.", true],
  ["AI Explanation", "Gemini explains every recovery plan in plain English.", true],
  ["Customer Priority (VIP)", "Allocate scarce stock to VIP / SLA accounts first.", false],
  ["Penalty & Insurance", "Auto-bundle proof and draft penalty / insurance claims.", false],
  ["Perishables Rescue", "Reroute near-expiry stock before it spoils.", false],
  ["Firestore + Login", "Cloud storage, user roles and a full audit trail.", false],
];

function renderFeatures() {
  q("feature-grid").innerHTML = FEATURES.map(
    ([t, d, live]) => `
    <div class="feature ${live ? "" : "soon"}">
      <span class="tag ${live ? "live" : "soon"}">${live ? "LIVE" : "SOON"}</span>
      <h4>${t}</h4><p>${d}</p>
    </div>`
  ).join("");
}

// ---- incidents (threatened orders) -----------------------------------------

async function scanIncidents() {
  const list = document.getElementById("incidents-list");
  const hint = document.getElementById("incidents-hint");
  hint.textContent = "Scanning…";
  list.innerHTML = "";

  try {
    const data = await api("/incidents");
    if (data.count === 0) {
      hint.textContent = "No incidents. Every order is covered.";
      return;
    }
    hint.textContent = `${data.count} order(s) at risk:`;
    data.incidents.forEach((inc) => list.appendChild(incidentCard(inc)));
  } catch (err) {
    hint.textContent = "Could not load incidents: " + err.message;
  }
}

function incidentCard(inc) {
  const li = document.createElement("li");
  li.className = "incident";
  li.innerHTML = `
    <div class="sku">${inc.sku}</div>
    <div class="meta">${inc.location_id} · due ${inc.deadline.slice(0, 10)}</div>
    <div style="margin-top:6px"><span class="badge short">short ${inc.shortage_qty} units</span></div>
  `;
  li.onclick = () => {
    document.querySelectorAll(".incident").forEach((n) => n.classList.remove("active"));
    li.classList.add("active");
    loadPlan(inc.sku, inc.location_id);
  };
  return li;
}

// ---- 3. load + draw the recovery plan (right panel) -------------------------

async function loadPlan(sku, locationId) {
  const hint = document.getElementById("plan-hint");
  const body = document.getElementById("plan-body");
  hint.classList.add("hidden");
  body.classList.remove("hidden");
  body.innerHTML = `<p class="spinner">Building plan…</p>`;

  try {
    const plan = await api(`/plans/${sku}/${locationId}`);
    body.innerHTML = renderPlan(plan);
    wirePlanButtons(plan);
  } catch (err) {
    body.innerHTML = `<p class="no">Failed: ${err.message}</p>`;
  }
}

function renderPlan(plan) {
  if (plan.status === "no_action_needed") {
    return `<p class="ok">No action needed — this order is already covered.</p>`;
  }

  const base = plan.baseline_exposure || {};
  const dis = plan.exposure || {};
  const margin = plan.margin_check || {};
  const surplus = plan.surplus_forecast || {};
  const approval = plan.approval || {};

  const optionRows = (plan.supplier_options || [])
    .map(
      (o) => `
      <tr>
        <td>${o.offer_id}</td>
        <td>${o.qty || "—"}</td>
        <td>${o.cost_minor ? rupees(o.cost_minor) : "—"}</td>
        <td>${o.arrives_at.slice(0, 10)}</td>
        <td class="${o.feasible ? "ok" : "no"}">${o.feasible ? "✓ chosen-able" : "✗ " + o.reason}</td>
      </tr>`
    )
    .join("");

  return `
    <!-- before vs after -->
    <div class="block">
      <h3>Impact (before vs after the disruption)</h3>
      <div class="compare">
        <div class="card">
          <h4>Normal</h4>
          <div class="big good">${base.shortage_qty ?? 0}</div>
          <div class="meta">units short · supply ${base.supply_by_deadline ?? "—"} / demand ${base.demand_by_deadline ?? "—"}</div>
        </div>
        <div class="card">
          <h4>After disruption</h4>
          <div class="big bad">${dis.shortage_qty}</div>
          <div class="meta">units short · supply ${dis.supply_by_deadline} / demand ${dis.demand_by_deadline}</div>
        </div>
      </div>
    </div>

    <!-- internal first -->
    <div class="block">
      <h3>Step 1 · Our own stock first</h3>
      <div class="kv">
        <span class="k">Used from internal stores</span><span>${plan.internal_used_qty} units</span>
      </div>
    </div>

    <!-- supplier options -->
    <div class="block">
      <h3>Step 2 · Supplier options for the rest</h3>
      <table>
        <thead><tr><th>Offer</th><th>Qty</th><th>Cost</th><th>Arrives</th><th>Status</th></tr></thead>
        <tbody>${optionRows}</tbody>
      </table>
      <p class="meta" style="margin-top:8px">Chosen: <strong>${plan.selected_offer_id || "none"}</strong> · recovered ${plan.recovered_qty}/${dis.shortage_qty} units</p>
    </div>

    <!-- margin -->
    <div class="block">
      <h3>Step 3 · Is it worth it?</h3>
      <div class="kv">
        <span class="k">Recovery cost</span><span>${rupees(margin.recovery_cost_minor)}</span>
        <span class="k">Revenue protected</span><span>${rupees(margin.protected_revenue_minor)}</span>
        <span class="k">Penalty avoided</span><span>${rupees(margin.penalty_avoided_minor)}</span>
        <span class="k">Net benefit</span><span>${rupees(margin.net_benefit_minor)}</span>
        <span class="k">Verdict</span><span class="verdict ${margin.verdict}">${(margin.verdict || "").replace("_", " ")}</span>
      </div>
    </div>

    <!-- surplus -->
    <div class="block">
      <h3>Step 4 · Future surplus warning</h3>
      <div class="kv">
        <span class="k">Expected overstock later</span><span>${surplus.expected_surplus_qty} units</span>
        <span class="k">Suggested action</span><span>${surplus.suggested_action || "none"}</span>
      </div>
    </div>

    <!-- governance + narrative + actions -->
    <div class="block">
      <h3>Step 5 · Approval</h3>
      <div class="kv">
        <span class="k">Needs sign-off from</span><span><strong>${approval.tier}</strong></span>
      </div>
      <div class="narrative" id="narrative">${plan.narrative}</div>
      <div class="source-tag" id="narrative-source"></div>
      <div class="actions">
        <button class="btn secondary" id="explain-btn">Explain with AI</button>
        <button class="btn" id="approve-btn">Approve &amp; reserve</button>
      </div>
      <div id="receipt"></div>
    </div>

    <!-- live external signals (real free APIs) -->
    <div class="block">
      <h3>Live external signals (real APIs)</h3>
      <p class="meta">Pulls live weather (Open-Meteo) + news (GDELT) for this destination.</p>
      <button class="btn secondary" id="signals-btn">Check live weather + news</button>
      <div id="signals-out"></div>
    </div>
  `;
}

// Turn a recovered shipment's route green on the map.
function markRouteRecovered(sku, dest) {
  const f = FLEET.find((x) => x.sku === sku && x.dest === dest);
  if (!f) return;
  f.poly.setStyle({ color: COLORS.green, dashArray: null });
  f.marker.setIcon(L.divIcon({
    className: "", html: `<div class="ship-dot green"></div>`, iconSize: [16, 16], iconAnchor: [8, 8],
  }));
  f.speed = 0.006; // recovered shipment moves a little faster (expedited)
  f.poly.bindPopup(`<div class="pop-title">${sku}</div><div class="pop-meta">✅ Recovery plan approved</div>`);
}

// Render everything that happens automatically after approval.
function renderFulfillment(out) {
  const f = out.fulfillment || {};
  const r = out.receipt || {};
  const steps = (f.steps || [])
    .map((s) => `<li class="${s.done ? "done" : "pending"}">${s.done ? "✅" : "⏳"} ${s.label}</li>`)
    .join("");
  const actions = (f.actions || [])
    .map((a) =>
      a.type === "internal_transfer"
        ? `<li>🔁 <b>Internal transfer</b> — ${a.qty}× ${a.sku} · ${a.from_location_id} → ${a.to_location_id}</li>`
        : `<li>🧾 <b>Purchase order</b> — ${a.qty}× ${a.sku} → ${a.supplier_name} (deliver ${a.deliver_to_location_id})</li>`
    )
    .join("");
  const emails = (f.emails || [])
    .map((e, i) => {
      const res = (f.email_results || [])[i] || {};
      return `<details class="email">
        <summary>📧 ${e.kind.replace("_", " ")} → ${e.to} <span class="meta">(${res.mode || "sent"})</span></summary>
        <div class="email-sub"><b>${e.subject}</b></div>
        <pre class="email-body">${e.body}</pre>
      </details>`;
    })
    .join("");
  const sentCount = (f.email_results || []).filter((x) => x.sent).length;
  return `<div class="fulfil">
    <div class="receipt">✅ Approved &amp; reserved <b>${r.qty}</b> units · ref <b>${r.supplier_ref}</b></div>
    <h3 style="margin-top:12px">Automated after approval</h3>
    <ul class="timeline">${steps}</ul>
    <h3>Actions created</h3>
    <ul class="actions-list">${actions}</ul>
    <h3>Emails sent (${sentCount})</h3>
    ${emails}
    <p class="meta" style="margin-top:8px">Emails are <b>simulated</b> in the prototype. Turn on real SMTP — see docs/after_plan_approval.md.</p>
  </div>`;
}

// ---- 4. buttons on the plan (explain + approve) -----------------------------

function wirePlanButtons(plan) {
  const explainBtn = document.getElementById("explain-btn");
  const approveBtn = document.getElementById("approve-btn");

  explainBtn.onclick = async () => {
    explainBtn.disabled = true;
    explainBtn.textContent = "Thinking…";
    try {
      const out = await api(`/plans/${plan.sku}/${plan.location_id}/explain`);
      document.getElementById("narrative").textContent = out.text;
      document.getElementById("narrative-source").textContent = "source: " + out.source;
    } catch (err) {
      document.getElementById("narrative-source").textContent = "AI failed: " + err.message;
    } finally {
      explainBtn.disabled = false;
      explainBtn.textContent = "Explain with AI";
    }
  };

  approveBtn.onclick = async () => {
    approveBtn.disabled = true;
    approveBtn.textContent = "Automating…";
    const receipt = document.getElementById("receipt");
    try {
      const out = await apiPost(`/plans/${plan.sku}/${plan.location_id}/approve`);
      if (out.status === "approved") {
        receipt.innerHTML = renderFulfillment(out);
        approveBtn.textContent = "Approved ✓";
        markRouteRecovered(plan.sku, plan.location_id);
        const active = document.querySelector(".incident.active");
        if (active && !active.querySelector(".badge.vip")) {
          active.querySelector(".meta").insertAdjacentHTML(
            "beforeend", ' · <span class="badge" style="background:rgba(47,214,155,.15);color:var(--good)">recovered</span>'
          );
        }
      } else {
        receipt.innerHTML = `<div class="receipt" style="border-color:var(--warn)">Status: ${out.status}</div>`;
        approveBtn.disabled = false;
        approveBtn.textContent = "Approve & reserve";
      }
    } catch (err) {
      receipt.innerHTML = `<p class="no">Approve failed: ${err.message}</p>`;
      approveBtn.disabled = false;
      approveBtn.textContent = "Approve & reserve";
    }
  };

  // "Check live signals" — calls the real weather + news APIs for the port.
  const signalsBtn = document.getElementById("signals-btn");
  signalsBtn.onclick = async () => {
    signalsBtn.disabled = true;
    signalsBtn.textContent = "Checking live APIs…";
    const out = document.getElementById("signals-out");
    try {
      const s = await api(`/signals/${plan.location_id}`);
      const w = s.weather || {};
      const n = s.news || {};
      let html = `<div class="kv">
        <span class="k">Location</span><span>${s.name || plan.location_id}</span>
        <span class="k">Weather risk</span><span><strong>${w.risk}</strong> · gust ${w.max_wind_gust_kmh ?? "—"} km/h · rain ${w.max_precip_mm ?? "—"} mm</span>
        <span class="k">News</span><span>${n.ok ? n.count + " article(s)" : (n.error || "none")}</span>
      </div>`;
      if (n.articles && n.articles.length) {
        html += "<ul>" + n.articles.slice(0, 3).map(
          (a) => `<li><a href="${a.url}" target="_blank" rel="noopener">${a.title || a.url}</a> <span class="meta">· ${a.domain || ""}</span></li>`
        ).join("") + "</ul>";
      }
      out.innerHTML = html;
    } catch (err) {
      out.innerHTML = `<p class="no">Signals failed: ${err.message}</p>`;
    } finally {
      signalsBtn.disabled = false;
      signalsBtn.textContent = "Check live weather + news";
    }
  };
}

// ---- start ------------------------------------------------------------------

async function init() {
  startClock();
  checkHealth();
  renderFeatures();
  loadOverview();
  scanIncidents();

  if (window.L) {
    initMap();
    loadMap().catch((e) => {
      q("ticker-text").textContent = "Map data failed: " + e.message;
    });
  } else {
    q("map").innerHTML = '<p class="hint" style="padding:16px">Map library did not load (offline?).</p>';
  }

  q("refresh-btn").onclick = () => {
    loadOverview();
    scanIncidents();
  };
}

init();
