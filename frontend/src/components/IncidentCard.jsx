import { day } from "../api.js";
import { SparkIcon } from "../icons.jsx";

export default function IncidentCard({ incident, onAskAi, recovered }) {
  return (
    <div className="incident">
      <div className="incident-top">
        <div>
          <div className="incident-sku">{incident.sku}</div>
          <div className="incident-meta">
            {incident.location_id} · due {day(incident.deadline)}
          </div>
        </div>
        {recovered ? (
          <span className="chip green">recovered</span>
        ) : (
          <span className="chip red">short {incident.shortage_qty}</span>
        )}
      </div>

      <div className="incident-actions">
        <span className="card-sub">
          supply {incident.supply_by_deadline} / demand {incident.demand_by_deadline}
        </span>
        <span className="spacer" />
        <button className="btn gemini small" onClick={() => onAskAi(incident)}>
          <SparkIcon size={14} />
          AI Plan
        </button>
      </div>
    </div>
  );
}
