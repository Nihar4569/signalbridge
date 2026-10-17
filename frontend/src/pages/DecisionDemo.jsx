import { useEffect, useRef, useState } from "react";
import { api, day, rupees } from "../api.js";
import Topbar from "../components/Topbar.jsx";
import DecisionBrief from "../components/DecisionBrief.jsx";
import { SparkIcon } from "../icons.jsx";

export default function DecisionDemo({ onToggleSidebar }) {
  const [catalog, setCatalog] = useState(null);
  const [selected, setSelected] = useState("active-closure");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const request = useRef(0);

  useEffect(() => {
    let alive = true;
    api.decisionCases().then((data) => alive && setCatalog(data)).catch((err) => alive && setError(err.message));
    return () => { alive = false; };
  }, []);

  async function run(caseId, mode) {
    const id = ++request.current;
    setBusy(true);
    setResult(null);
    setError("");
    try {
      const data = await api.runDecisionCase(caseId, mode);
      if (request.current === id) setResult(data);
    } catch (err) {
      if (request.current === id) setError(err.message);
    } finally {
      if (request.current === id) setBusy(false);
    }
  }

  useEffect(() => {
    run(selected, "reference");
    return () => { request.current += 1; };
  }, [selected]);

  const current = catalog?.cases.find((item) => item.case_id === selected);
  const plan = result?.plan;
  const hasAssessment = result?.assessment_state === "complete";

  return (
    <>
      <Topbar title="Decision walkthrough" subtitle="Follow the evidence from a notice to a recovery decision" onToggleSidebar={onToggleSidebar} isolated />
      <main className="content decision-page">
        <section className="decision-intro">
          <span className="decision-eyebrow">SYNTHETIC RETAIL CASE</span>
          <h2>Does this notice actually threaten an order?</h2>
          <p>A retail DC needs 100 coffee packs by 19 October. It has 20 in stock and expects 80 inbound. Compare an active closure with a cancelled strike, using the same inventory and supplier options.</p>
          <div className="decision-meta">Fixed scenario clock: {catalog?.assessment_at ? `${day(catalog.assessment_at)} at 09:00 UTC` : "17 October 2026 at 09:00 UTC"}. Each run uses a private snapshot. No reservations, purchases or emails occur.</div>
        </section>

        <div className="decision-case-picker" role="group" aria-label="Choose an operational notice">
          {(catalog?.cases || []).map((item, index) => (
            <button key={item.case_id} className={"decision-case" + (selected === item.case_id ? " selected" : "")} onClick={() => setSelected(item.case_id)} aria-pressed={selected === item.case_id}>
              <span className="decision-case-number">0{index + 1}</span>
              <span><strong>{item.title}</strong><small>{item.description}</small></span>
            </button>
          ))}
        </div>

        <div className="decision-runbar">
          <div>
            <strong>{current?.title || "Operational notice"}</strong>
            <p className="card-sub">Reference results are authored examples. “Assess with Gemini” runs the model on the supplied notice.</p>
          </div>
          <div className="row">
            <button className="btn outline" disabled={busy} onClick={() => run(selected, "reference")}>Reference replay</button>
            <button className="btn gemini" disabled={busy || !catalog?.gemini_configured} onClick={() => run(selected, "gemini")} title={!catalog?.gemini_configured ? "A Gemini API key is not configured on this server" : "Run a new evidence interpretation"}>
              <SparkIcon size={16} /> Assess with Gemini
            </button>
          </div>
        </div>
        {catalog && !catalog.gemini_configured && <p className="decision-warning">Live Gemini is unavailable on this server. Reference replay still exercises evidence validation, triage and recovery calculations.</p>}
        {error && <p className="decision-warning" role="alert">Could not load this run: {error}</p>}
        {busy && <div className="decision-loading" role="status"><span className="spin" /> Reading the notice and calculating this case…</div>}

        {result && (
          <>
            <div className="decision-result-bar" aria-live="polite">
              <span className={"chip " + (hasAssessment ? result.mode === "gemini" ? "blue" : "grey" : "red")}>
                {result.mode === "reference" ? "Reference interpretation · no model call" : result.assessment_state === "unavailable" ? "Gemini unavailable" : hasAssessment ? "Live Gemini interpretation" : "Live Gemini · review required"}
              </span>
              <span className="decision-meta">{result.duration_ms.toLocaleString()} ms · executed {new Date(result.executed_at).toLocaleTimeString()}</span>
            </div>
            {!hasAssessment && <p className="decision-warning">{result.assessment_state === "unavailable" ? "The model did not produce a complete validated decision. No reference answer was substituted and no action is authorized." : "Gemini identified missing or uncertain evidence. Review the notes before drawing an operational conclusion."}</p>}
            <div className="card">
              <DecisionBrief brief={result.brief} />
            </div>
            <section className="card">
              <div className="card-head"><h3>{hasAssessment ? "Calculated outcome" : "Snapshot calculations · assessment incomplete"}</h3><span className="chip grey">Python domain engine</span></div>
              {hasAssessment && plan.status === "no_action_needed" ? (
                <p>The expected inbound shipment covers the 100-unit order. This notice creates no additional shortage and no purchase proposal.</p>
              ) : (
                <div className="decision-table-scroll"><table className="table">
                  <thead><tr><th>Offer</th><th>Available / proposed</th><th>Illustrative cost</th><th>Decision</th></tr></thead>
                  <tbody>{(plan.supplier_options || []).map((offer) => (
                    <tr key={offer.offer_id}><td className="mono">{offer.offer_id}</td><td>{offer.available_qty} / {offer.qty}</td><td>{rupees(offer.cost_minor)}</td><td>{offer.reason}</td></tr>
                  ))}</tbody>
                </table></div>
              )}
              <p className="card-sub mt">No execution occurs in this walkthrough. Return to Threatened orders to review an operational recovery proposal.</p>
            </section>
            <section className="card">
              <div className="card-head"><h3>Route relevance</h3></div>
              {result.shipments.map((shipment) => (
                <div className="decision-route-row" key={shipment.shipment_id}>
                  <strong className="mono">{shipment.shipment_id}</strong>
                  <span>{shipment.assessment?.reason || "No validated interpretation"}</span>
                  <span className={"chip " + (shipment.assessment?.status === "unknown" ? "grey" : shipment.risk_zone === "risk" ? "red" : "green")}>
                    {shipment.assessment?.status === "unknown" ? "Review" : shipment.risk_zone === "risk" ? "Potential impact" : "Notice excluded"}
                  </span>
                </div>
              ))}
            </section>
          </>
        )}
      </main>
    </>
  );
}
