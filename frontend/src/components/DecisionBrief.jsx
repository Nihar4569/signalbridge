import { day, rupees } from "../api.js";
import { GeminiIcon } from "../icons.jsx";

const STATUS = { affected: "Potential disruption", unaffected: "Notice does not require action", unknown: "Review required", unverified: "Assessment not linked" };
const when = (value) => value ? new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "Not recorded";

export default function DecisionBrief({ brief, compact = false }) {
  if (!brief) return null;
  const impact = brief.impact || {};
  const proposal = brief.proposal || {};
  const review = brief.review_notes || [];
  const needsReview = review.length > 0 || brief.interpretations.some((item) => ["unknown", "unverified"].includes(item.status));

  return (
    <section className="decision-brief" aria-label="Evidence-backed decision brief">
      <div className="decision-heading">
        <div>
          <div className="decision-eyebrow"><GeminiIcon size={16} id={"brief-" + brief.location_id} /> Evidence to decision</div>
          <h3>Evidence-backed decision brief</h3>
        </div>
        <span className={"chip " + (needsReview ? "grey" : impact.shortage_qty > 0 ? "red" : "green")}>
          {needsReview ? "Review evidence" : impact.shortage_qty > 0 ? "Recovery proposed" : "No new purchase"}
        </span>
      </div>

      <div className="decision-assessments">
        {brief.interpretations.map((item) => (
          <div className="decision-interpretation" key={item.shipment_id}>
            <div className="decision-line">
              <strong>{STATUS[item.status] || "Review required"}</strong>
              <span className="mono card-sub">{item.shipment_id}</span>
            </div>
            <p>{item.reason}</p>
            {item.matched_places?.length > 0 && <p className="card-sub">Route evidence: {[...new Set(item.matched_places)].join(", ")}</p>}
            <div className="decision-meta">{item.source} · assessed {when(item.assessed_at)} · event {item.event_status}</div>
            {item.policy_override && <p className="decision-warning">Route safety rule: {item.policy_override}</p>}
          </div>
        ))}
      </div>

      <div className="decision-metrics">
        <div><span>Shortage by {day(impact.deadline)}</span><strong>{impact.shortage_qty ?? "—"}<small> units</small></strong></div>
        <div><span>Own stock / supplier</span><strong>{proposal.internal_qty ?? 0}<small> / </small>{proposal.supplier_qty ?? 0}<small> units</small></strong></div>
        <div><span>Proposed recovery cost</span><strong>{proposal.recovery_cost_minor == null ? "No purchase proposed" : rupees(proposal.recovery_cost_minor)}</strong></div>
      </div>
      {!compact && proposal.selected_offer_id && (
        <p className="decision-proposal">Proposed offer <b className="mono">{proposal.selected_offer_id}</b>. Human approval: <b>{proposal.approver}</b>.</p>
      )}

      <details className="decision-sources" open={!compact}>
        <summary>Inspect source evidence ({brief.evidence.length})</summary>
        <div className="decision-source-list">
          {brief.evidence.map((source) => (
            <article className="decision-source" key={source.signal_id}>
              <div className="decision-line">
                <strong>{source.source_url && /^https?:\/\//i.test(source.source_url)
                  ? <a href={source.source_url} target="_blank" rel="noreferrer">{source.title} ↗</a>
                  : source.title}</strong>
                <span className={"chip " + (source.current ? "blue" : "grey")}>{source.current ? "Within evidence window" : "Stale / time unknown"}</span>
              </div>
              <div className="decision-meta">{source.source} · {source.place} · <span className="mono">{source.signal_id}</span></div>
              {source.citations.length > 0 ? source.citations.map((citation, index) => (
                <blockquote key={index}>{citation.quote}<footer>Exact source excerpt · {citation.shipment_id}</footer></blockquote>
              )) : <p className="card-sub">{source.policy_evidence ? "Used by the deterministic route safety rule." : "Context source. No validated model citation is saved."}</p>}
              <p className="decision-meta">Published {when(source.published_at)} · fetched {when(source.fetched_at)}</p>
            </article>
          ))}
          {!brief.evidence.length && <p className="card-sub">No source records are available for this case.</p>}
        </div>
      </details>

      {review.length > 0 && <div className="decision-warning"><strong>Before acting</strong><ul>{review.map((note) => <li key={note}>{note}</li>)}</ul></div>}
      <details className="decision-assumptions" open={!compact}>
        <summary>Calculation assumptions</summary>
        <ul>{brief.assumptions.map((note) => <li key={note}>{note}</li>)}</ul>
      </details>
    </section>
  );
}
