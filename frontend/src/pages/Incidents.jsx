import { useEffect, useState } from "react";
import Topbar from "../components/Topbar.jsx";
import IncidentCard from "../components/IncidentCard.jsx";
import AiPlanModal from "../components/AiPlanModal.jsx";
import { api } from "../api.js";
import { IconRefresh } from "../icons.jsx";

export default function Incidents({ onToggleSidebar }) {
  const [list, setList] = useState([]);
  const [active, setActive] = useState(null);
  const [done, setDone] = useState({});
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const d = await api.incidents();
      setList(d.incidents || []);
    } catch { /* API offline — show empty state */ }
    setLoading(false);
  }
  useEffect(() => { load(); }, []);

  return (
    <>
      <Topbar
        title="Threatened orders"
        subtitle="Orders that will fall short unless we act"
        onToggleSidebar={onToggleSidebar}
        actions={<button className="btn tonal small" onClick={load}><IconRefresh size={16} /> Scan</button>}
      />
      <div className="content">
        <section className="card">
          <div className="card-head">
            <div>
              <h3>Impact triage result</h3>
              <div className="card-sub">Only orders with a real shortage are listed</div>
            </div>
            <span className="chip red">{list.length}</span>
          </div>

          {loading && <div className="shimmer" style={{ height: 110 }} />}
          {!loading && !list.length && <p className="empty">Nothing at risk right now.</p>}

          <div className="stack">
            {list.map((inc) => (
              <IncidentCard
                key={inc.sku + inc.location_id}
                incident={inc}
                recovered={done[inc.sku + inc.location_id]}
                onAskAi={setActive}
              />
            ))}
          </div>
        </section>
      </div>

      {active && (
        <AiPlanModal
          incident={active}
          onClose={() => setActive(null)}
          onApproved={() => setDone((d) => ({ ...d, [active.sku + active.location_id]: true }))}
        />
      )}
    </>
  );
}
