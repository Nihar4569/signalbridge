// SignalBridge frontend — plain JavaScript, no framework, no build step.
// It calls the backend API and draws the screens. Read top to bottom.

// Where the backend lives. Change this if your API runs on another port.
const API_BASE = "http://localhost:8000";

// ---- tiny helpers -----------------------------------------------------------

// Format integer paise (minor units) as rupees, e.g. 11300000 -> "₹1,13,000".
function rupees(minor) {
  if (minor == null) return "—";
  return "₹" + (minor / 100).toLocaleString("en-IN");
}

// Shortcut to call the API and get JSON back.
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

// ---- 1. health check (footer) ----------------------------------------------

async function checkHealth() {
  const el = document.getElementById("api-status");
  try {
    await api("/health");
    el.textContent = "API: connected ✓";
  } catch {
    el.textContent = "API: not reachable ✗ (is the backend running?)";
  }
}

// ---- 2. scan for incidents (left panel) -------------------------------------

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
          <h4>After port delay</h4>
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
  `;
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
    approveBtn.textContent = "Reserving…";
    try {
      const out = await apiPost(`/plans/${plan.sku}/${plan.location_id}/approve`);
      const receipt = document.getElementById("receipt");
      if (out.status === "reserved") {
        receipt.innerHTML = `<div class="receipt">
          ✅ Reserved <strong>${out.receipt.qty}</strong> units ·
          ref <strong>${out.receipt.supplier_ref}</strong> ·
          expires ${out.receipt.expires_at.slice(0, 16).replace("T", " ")}
        </div>`;
        approveBtn.textContent = "Approved ✓";
      } else {
        receipt.innerHTML = `<div class="receipt" style="border-color:var(--warn)">Status: ${out.status}</div>`;
        approveBtn.disabled = false;
        approveBtn.textContent = "Approve & reserve";
      }
    } catch (err) {
      document.getElementById("receipt").innerHTML = `<p class="no">Approve failed: ${err.message}</p>`;
      approveBtn.disabled = false;
      approveBtn.textContent = "Approve & reserve";
    }
  };
}

// ---- start ------------------------------------------------------------------

document.getElementById("scan-btn").onclick = scanIncidents;
checkHealth();
