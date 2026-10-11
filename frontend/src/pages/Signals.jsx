import { useEffect, useState } from "react";
import Topbar from "../components/Topbar.jsx";
import { api } from "../api.js";

const RISK = { low: "green", medium: "yellow", high: "red", unknown: "grey" };

export default function Signals({ onToggleSidebar }) {
  const [locations, setLocations] = useState([]);
  const [sel, setSel] = useState("");
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.map().then((d) => {
      const locs = (d.locations || []).filter((l) => l.type === "port" || l.type === "dc");
      setLocations(locs);
      if (locs.length) setSel(locs[0].location_id);
    }).catch(() => {});
  }, []);

  async function check(id) {
    setBusy(true);
    setData(null);
    try {
      setData(await api.signals(id));
    } catch (e) {
      setData({ error: e.message });
    }
    setBusy(false);
  }

  const w = data?.weather || {};
  const n = data?.news || {};

  return (
    <>
      <Topbar title="Live signals" subtitle="Real weather & news from free public APIs" onToggleSidebar={onToggleSidebar} />
      <div className="content">
        <section className="card">
          <div className="card-head">
            <div>
              <h3>Check a location</h3>
              <div className="card-sub">Open-Meteo (weather) + GDELT (news), filtered by location</div>
            </div>
          </div>

          <div className="row">
            <select
              className="select"
              value={sel}
              onChange={(e) => setSel(e.target.value)}
            >
              {locations.map((l) => (
                <option key={l.location_id} value={l.location_id}>{l.name}</option>
              ))}
            </select>
            <button className="btn filled" onClick={() => check(sel)} disabled={busy || !sel}>
              {busy ? "Checking…" : "Check live signals"}
            </button>
          </div>

          {data?.error && <p className="mt" style={{ color: "var(--bad)" }}>{data.error}</p>}

          {data && !data.error && (
            <div className="grid mt" style={{ gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div className="card well" style={{ boxShadow: "none" }}>
                <div className="card-head"><h3>Weather</h3><span className={"chip " + (RISK[w.risk] || "grey")}>{w.risk}</span></div>
                <div className="kv">
                  <span className="k">Max wind gust</span><span className="v">{w.max_wind_gust_kmh ?? "—"} km/h</span>
                  <span className="k">Max precipitation</span><span className="v">{w.max_precip_mm ?? "—"} mm</span>
                  <span className="k">Source</span><span className="v">{w.source || "—"}</span>
                </div>
              </div>

              <div className="card well" style={{ boxShadow: "none" }}>
                <div className="card-head">
                  <h3>Disruption news</h3>
                  <span className="chip grey">{n.ok ? `${n.count} found` : n.error || "none"}</span>
                </div>
                {n.ok && n.articles?.length ? (
                  <div className="stack">
                    {n.articles.slice(0, 4).map((a, i) => (
                      <a key={i} href={a.url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 13 }}>
                        {a.title || a.url}
                        <span className="muted"> · {a.domain}</span>
                      </a>
                    ))}
                  </div>
                ) : (
                  <p className="card-sub">
                    {n.note || "No recent disruption articles for this location."}
                  </p>
                )}
              </div>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
