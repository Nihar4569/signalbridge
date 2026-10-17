import { useEffect, useState } from "react";
import { api, rupees, day } from "../api.js";
import { GeminiIcon, IconClose, IconCheck } from "../icons.jsx";
import AskGemini from "./AskGemini.jsx";
import DecisionBrief from "./DecisionBrief.jsx";

export default function AiPlanModal({ incident, onClose, onApproved }) {
  const { sku, location_id: loc } = incident;
  const [plan, setPlan] = useState(null);
  const [brief, setBrief] = useState(null);
  const [briefError, setBriefError] = useState("");
  const [ai, setAi] = useState(null);
  const [error, setError] = useState(null);
  const [fulfil, setFulfil] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    api.brief(sku, loc)
      .then((data) => { if (alive) { setBrief(data); setPlan(data.plan); } })
      .catch(() => {
        if (!alive) return;
        setBriefError("Source evidence could not be loaded. Review the plan before approval.");
        api.plan(sku, loc).then((data) => alive && setPlan(data)).catch((err) => alive && setError(err.message));
      });
    api
      .explain(sku, loc)
      .then((a) => alive && setAi(a))
      .catch(() => {});
    return () => { alive = false; };
  }, [sku, loc]);

  const ready = Boolean(plan);
  const canApprove = plan?.status === "awaiting_approval" && plan?.selected_offer_id && plan?.margin_check?.verdict === "worth_it";

  async function approve() {
    setBusy(true);
    try {
      const out = await api.approve(sku, loc);
      if (out.status !== "approved") throw new Error("This plan is no longer ready for approval. Close it and review the current proposal.");
      setFulfil(out);
      onApproved?.(out);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="scrim" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <GeminiIcon size={26} id="modal-gem" />
          <div style={{ flex: 1 }}>
            <div className="modal-title">AI Recovery Plan</div>
            <div className="card-sub">
              {sku} · {loc} · calculated proposal with source evidence
            </div>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close">
            <IconClose size={20} />
          </button>
        </div>

        <div className="modal-body">
          {error && <p style={{ color: "var(--bad)" }}>Failed: {error}</p>}

          {!ready && !error && <div className="decision-loading" role="status"><span className="spin" /> Loading the calculated recovery plan…</div>}

          {ready && !fulfil && <DecisionBrief brief={brief} compact />}
          {briefError && !fulfil && <p className="decision-warning">{briefError}</p>}

          {ready && !fulfil && <PlanView plan={plan} ai={ai} sku={sku} loc={loc} />}

          {fulfil && <Fulfilment out={fulfil} />}
        </div>

        <div className="modal-foot">
          <span className="card-sub">
            {fulfil
              ? "All follow-up actions were automated."
              : "Gemini explains · deterministic code calculates · you approve."}
          </span>
          <div className="row">
            <button className="btn tonal" onClick={onClose}>
              {fulfil ? "Done" : "Cancel"}
            </button>
            {ready && !fulfil && (
              <button className="btn filled" onClick={approve} disabled={busy || !canApprove}>
                {busy ? "Automating…" : "Approve & execute"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function PlanView({ plan, ai, sku, loc }) {
  if (plan.status === "no_action_needed") {
    return <p className="empty">This order is already covered — no action needed.</p>;
  }
  const base = plan.baseline_exposure || {};
  const dis = plan.exposure || {};
  const m = plan.margin_check || {};
  const s = plan.surplus_forecast || {};
  const ap = plan.approval || {};

  return (
    <>
      <Section n="1" label="Impact of the disruption">
        <div className="compare">
          <div className="cmp">
            <h4>Normally</h4>
            <div className="num good">{base.shortage_qty ?? 0}</div>
            <small>units short</small>
          </div>
          <div className="arrow">→</div>
          <div className="cmp">
            <h4>After disruption</h4>
            <div className="num bad">{dis.shortage_qty}</div>
            <small>
              supply {dis.supply_by_deadline} / demand {dis.demand_by_deadline} by {day(dis.deadline)}
            </small>
          </div>
        </div>
      </Section>

      <Section n="2" label="Internal stock used first">
        <div className="kv">
          <span className="k">Units pulled from our own DCs / dark stores</span>
          <span className="v">{plan.internal_used_qty}</span>
        </div>
      </Section>

      <Section n="3" label="Supplier options considered">
        <table className="table">
          <thead>
            <tr><th>Offer</th><th>Qty</th><th>Cost</th><th>Arrives</th><th>Decision</th></tr>
          </thead>
          <tbody>
            {(plan.supplier_options || []).map((o) => (
              <tr key={o.offer_id} className={o.feasible ? "" : "row-muted"}>
                <td className="mono">{o.offer_id}</td>
                <td>{o.qty ? o.qty.toLocaleString("en-IN") : "—"}</td>
                <td>{o.cost_minor != null ? rupees(o.cost_minor) : "—"}</td>
                <td>{day(o.arrives_at)}</td>
                <td>
                  {o.feasible ? (
                    <span className="chip green">feasible</span>
                  ) : (
                    <span className="chip grey" title={o.reason}>rejected · {o.reason}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="card-sub mt">
          Selected <b className="mono">{plan.selected_offer_id || "none"}</b> · recovering{" "}
          {plan.recovered_qty}/{dis.shortage_qty} units
        </p>
      </Section>

      <Section n="4" label="Is the recovery worth it?">
        <div className="kv">
          <span className="k">Recovery cost</span><span className="v">{rupees(m.recovery_cost_minor)}</span>
          <span className="k">Revenue exposed under the delay scenario</span><span className="v">{rupees(m.protected_revenue_minor)}</span>
          <span className="k">Potential late penalty</span><span className="v">{rupees(m.penalty_avoided_minor)}</span>
          <span className="k">Estimated recovery benefit</span>
          <span className="v" style={{ color: m.net_benefit_minor > 0 ? "var(--good)" : "var(--bad)" }}>
            {rupees(m.net_benefit_minor)}
          </span>
        </div>
        <p className="card-sub mt">Revenue plus potential penalty less external recovery cost. This is a decision estimate, not realized profit.</p>
        <div className="mt">
          <span className={"chip " + (m.verdict === "worth_it" ? "green" : "red")}>
            {m.verdict === "worth_it" ? "Worth it" : "Not worth it"}
          </span>
        </div>
      </Section>

      <Section n="5" label="Predicted surplus & approval">
        <div className="kv">
          <span className="k">Future overstock when the late shipment lands</span>
          <span className="v">{s.expected_surplus_qty} units ({s.suggested_action || "none"})</span>
          <span className="k">Approval required from</span>
          <span className="v">
            {ap.approver_title || ap.tier} <span className="chip blue">{(ap.tier || "").replace("_", " ")}</span>
          </span>
        </div>
      </Section>

      <Section label="Gemini's summary" gem>
        <div className="ai-note">{ai ? ai.text : plan.narrative}</div>
        <div className="ai-src">
          <GeminiIcon size={12} id="src-gem" />
          {ai ? `source: ${ai.source}` : "generating…"}
        </div>
      </Section>

      <Section label="Ask Gemini" gem>
        <AskGemini sku={sku} loc={loc} />
      </Section>
    </>
  );
}

function Fulfilment({ out }) {
  const f = out.fulfillment || {};
  const r = out.receipt || {};
  return (
    <>
      <div className="ai-note" style={{ borderColor: "color-mix(in srgb, var(--good) 45%, var(--border))" }}>
        ✅ Approved. Supplier hold for <b>{r.qty}</b> units, plus <b>{r.internal_qty ?? 0}</b> internal units · ref <b className="mono">{r.supplier_ref}</b>
      </div>

      <Section label="Automated after approval">
        <ul className="timeline">
          {(f.steps || []).map((s) => (
            <li key={s.label} className={s.done ? "" : "pending"}>
              {s.done ? <IconCheck size={16} /> : "⏳"} {s.label}
            </li>
          ))}
        </ul>
      </Section>

      <Section label="Actions created">
        <div className="stack">
          {(f.actions || []).map((a, i) => (
            <div className="action-row" key={i}>
              {a.type === "internal_transfer" ? (
                <>🔁 <b>Internal transfer</b> — {a.qty}× {a.sku} · {a.from_location_id} → {a.to_location_id}</>
              ) : (
                <>🧾 <b>Purchase order</b> — {a.qty}× {a.sku} → {a.supplier_name} (deliver {a.deliver_to_location_id})</>
              )}
            </div>
          ))}
        </div>
      </Section>

      <Section label={`Emails sent (${(f.email_results || []).filter((e) => e.sent).length})`}>
        {(f.emails || []).map((e, i) => (
          <details className="email-card" key={i}>
            <summary>
              📧 {e.kind.replace("_", " ")} → <b>{e.to}</b>{" "}
              <span className="muted">({(f.email_results || [])[i]?.mode || "sent"})</span>
            </summary>
            <div className="mt"><b>{e.subject}</b></div>
            <pre className="email-body">{e.body}</pre>
          </details>
        ))}
        <p className="card-sub">Emails are simulated in the prototype — see docs/after_plan_approval.md.</p>
      </Section>
    </>
  );
}

function Section({ n, label, gem, children }) {
  return (
    <div className="sect">
      <div className="sect-label">
        {n && <span className="step-no">{n}</span>}
        {gem && <GeminiIcon size={13} id={"s-" + label} />}
        {label}
      </div>
      {children}
    </div>
  );
}
