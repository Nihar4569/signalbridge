import { useEffect, useState } from "react";
import Topbar from "../components/Topbar.jsx";
import { api } from "../api.js";
import { IconRefresh, IconCheck } from "../icons.jsx";

export default function Recoveries({ onToggleSidebar }) {
  const [list, setList] = useState([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const d = await api.fulfillments();
      setList(d.fulfillments || []);
    } catch { /* API offline */ }
    setLoading(false);
  }
  useEffect(() => { load(); }, []);

  return (
    <>
      <Topbar
        title="Recoveries"
        subtitle="What was automated after each approval"
        onToggleSidebar={onToggleSidebar}
        actions={<button className="btn tonal small" onClick={load}><IconRefresh size={16} /> Refresh</button>}
      />
      <div className="content">
        {loading && <div className="shimmer" style={{ height: 140 }} />}

        {!loading && !list.length && (
          <section className="card">
            <p className="empty">
              No approved recoveries yet.<br />
              Open a threatened order, press <b>AI Plan</b>, then <b>Approve &amp; execute</b>.
            </p>
          </section>
        )}

        <div className="stack">
          {list.map((f) => (
            <section className="card" key={f.operation_id}>
              <div className="card-head">
                <div>
                  <h3>{f.sku} → {f.location_id}</h3>
                  <div className="card-sub mono">{f.operation_id}</div>
                </div>
                <span className="chip green">{f.recovered_qty} units recovered</span>
              </div>

              <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 18 }}>
                <div>
                  <div className="sect-label">Status</div>
                  <ul className="timeline">
                    {(f.steps || []).map((s) => (
                      <li key={s.label} className={s.done ? "" : "pending"}>
                        {s.done ? <IconCheck size={16} /> : "⏳"} {s.label}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <div className="sect-label">Actions</div>
                  <div className="stack">
                    {(f.actions || []).map((a, i) => (
                      <div className="action-row" key={i}>
                        {a.type === "internal_transfer"
                          ? <>🔁 {a.qty}× {a.sku} · {a.from_location_id} → {a.to_location_id}</>
                          : <>🧾 {a.qty}× {a.sku} → {a.supplier_name}</>}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="mt">
                <div className="sect-label">Emails</div>
                {(f.emails || []).map((e, i) => (
                  <details className="email-card" key={i}>
                    <summary>📧 {e.kind.replace("_", " ")} → <b>{e.to}</b></summary>
                    <div className="mt"><b>{e.subject}</b></div>
                    <pre className="email-body">{e.body}</pre>
                  </details>
                ))}
              </div>
            </section>
          ))}
        </div>
      </div>
    </>
  );
}
