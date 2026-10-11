import { useEffect, useState } from "react";
import Topbar from "../components/Topbar.jsx";
import MapView from "../components/MapView.jsx";
import { api, day } from "../api.js";

const CHIP = { on_time: "green", at_risk: "yellow", delayed: "red" };

export default function Shipments({ onToggleSidebar }) {
  const [data, setData] = useState(null);

  useEffect(() => { api.map().then(setData).catch(() => {}); }, []);
  const routes = data?.routes || [];

  return (
    <>
      <Topbar title="Shipments" subtitle="Every shipment currently in transit" onToggleSidebar={onToggleSidebar} />
      <div className="content">
        <section className="card" style={{ marginBottom: 16 }}>
          <MapView data={data} height={360} />
        </section>

        <section className="card">
          <div className="card-head"><h3>In transit</h3><span className="chip grey">{routes.length}</span></div>
          <table className="table">
            <thead>
              <tr>
                <th>Shipment</th><th>Lane</th><th>Product</th><th>Qty</th>
                <th>Carrier</th><th>ETA</th><th>Progress</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {routes.map((r) => (
                <tr key={r.shipment_id}>
                  <td className="mono">{r.shipment_id}</td>
                  <td>{r.lane_name}</td>
                  <td>{r.sku}</td>
                  <td>{r.quantity}</td>
                  <td className="mono">{r.carrier_id}</td>
                  <td>{day(r.eta)}</td>
                  <td>{Math.round((r.progress || 0) * 100)}%</td>
                  <td><span className={"chip " + (CHIP[r.health] || "grey")}>{r.health.replace("_", " ")}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          {!routes.length && <p className="empty">No shipments loaded.</p>}
        </section>
      </div>
    </>
  );
}
