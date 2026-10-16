import { useEffect, useState } from "react";
import Topbar from "../components/Topbar.jsx";
import Kpi from "../components/Kpi.jsx";
import MapView from "../components/MapView.jsx";
import IncidentCard from "../components/IncidentCard.jsx";
import AiPlanModal from "../components/AiPlanModal.jsx";
import { api, rupeesShort } from "../api.js";
import { IconRefresh, IconShip, IconCheck, IconWarning, IconMoney, IconSignal } from "../icons.jsx";

export default function Dashboard({ onToggleSidebar }) {
  const [ov, setOv] = useState(null);
  const [mapData, setMapData] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [active, setActive] = useState(null);
  const [done, setDone] = useState({});
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const [o, m, i] = await Promise.allSettled([api.overview(), api.map(), api.incidents()]);
    if (o.status === "fulfilled") setOv(o.value);
    if (m.status === "fulfilled") setMapData(m.value);
    if (i.status === "fulfilled") setIncidents(i.value.incidents || []);
    setLoading(false);
  }
  useEffect(() => { load(); }, []);

  // Refresh also pulls fresh live weather + news (runs in the background).
  function refresh() {
    api.triggerScan().catch(() => {});
    load();
  }

  const alerts = mapData?.alerts || [];

  return (
    <>
      <Topbar
        title="Dashboard"
        subtitle="Live supply-chain overview"
        onToggleSidebar={onToggleSidebar}
        onScanComplete={load}
        actions={
          <button className="btn tonal small" onClick={refresh}>
            <IconRefresh size={16} /> Refresh
          </button>
        }
      />

      <div className="content">
        <div className="kpi-row">
          <Kpi label="Shipments tracked" value={ov?.shipments_tracked} icon={<IconShip size={14} />} />
          <Kpi label="On time" value={ov?.on_time} accent="var(--good)" icon={<IconCheck size={14} />} />
          <Kpi label="At risk" value={ov?.at_risk} accent="var(--warn)" icon={<IconWarning size={14} />} />
          <Kpi label="Orders threatened" value={ov?.orders_at_risk} accent="var(--bad)" icon={<IconWarning size={14} />} />
          <Kpi label="Revenue at risk" value={ov?.revenue_at_risk_minor} format={rupeesShort} accent="var(--violet)" icon={<IconMoney size={14} />} />
          <Kpi label="Active alerts" value={ov?.active_alerts} accent="var(--primary)" icon={<IconSignal size={14} />} />
        </div>

        <div className="grid cols-2">
          <section className="card">
            <div className="card-head">
              <div>
                <h3>Live route map</h3>
                <div className="card-sub">Shipments move in real time · alerts marked on the lane</div>
              </div>
              <div className="legend">
                <span><i style={{ background: "#34a853" }} />On time</span>
                <span><i style={{ background: "#fbbc04" }} />At risk</span>
                <span><i style={{ background: "#ea4335" }} />Delayed</span>
              </div>
            </div>
            <MapView data={mapData} />
            <div className="ticker">
              <span className="ticker-label">ALERTS</span>
              <span className="ticker-text">
                {alerts.length
                  ? alerts.map((a) => `${a.type === "weather" ? "⛈️" : "⛔"} ${a.title}`).join("     •     ")
                  : "No active alerts"}
              </span>
            </div>
          </section>

          <section className="card">
            <div className="card-head">
              <div>
                <h3>Threatened orders</h3>
                <div className="card-sub">Ask Gemini for a recovery plan</div>
              </div>
              <span className="chip red">{incidents.length}</span>
            </div>

            {loading && <div className="shimmer" style={{ height: 96 }} />}

            {!loading && incidents.length === 0 && (
              <p className="empty">Nothing at risk. Every order is covered.</p>
            )}

            <div className="stack">
              {incidents.map((inc) => (
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
      </div>

      {active && (
        <AiPlanModal
          incident={active}
          onClose={() => setActive(null)}
          onApproved={() => {
            setDone((d) => ({ ...d, [active.sku + active.location_id]: true }));
            api.overview().then(setOv).catch(() => {});
          }}
        />
      )}
    </>
  );
}
