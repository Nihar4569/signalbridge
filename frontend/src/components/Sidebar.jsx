import { NavLink } from "react-router-dom";
import {
  GeminiIcon, SparkIcon, IconDashboard, IconShip, IconWarning, IconCheck,
  IconSignal, IconGrid, IconStar, IconReceipt, IconLeaf, IconSettings,
} from "../icons.jsx";

// Live pages (routable) and roadmap items (shown but disabled, with a SOON chip).
const LIVE = [
  { to: "/", label: "Dashboard", Icon: IconDashboard, end: true },
  { to: "/shipments", label: "Shipments", Icon: IconShip },
  { to: "/incidents", label: "Threatened orders", Icon: IconWarning },
  { to: "/recoveries", label: "Recoveries", Icon: IconCheck },
  { to: "/signals", label: "Live signals", Icon: IconSignal },
  { to: "/decision-demo", label: "Decision walkthrough", Icon: SparkIcon },
  { to: "/capabilities", label: "Capabilities", Icon: IconGrid },
];

const SOON = [
  { label: "VIP allocation", Icon: IconStar },
  { label: "Penalty & claims", Icon: IconReceipt },
  { label: "Perishables rescue", Icon: IconLeaf },
  { label: "Settings", Icon: IconSettings },
];

export default function Sidebar({ onAskGemini }) {
  return (
    <aside className="sidebar">
      <div className="sb-brand">
        <GeminiIcon size={26} id="brand-gem" />
        <div className="sb-brand-text">
          <h1>SignalBridge</h1>
          <p>Control Tower</p>
        </div>
      </div>

      <div className="sb-section">Operations</div>
      <nav className="sb-nav">
        {LIVE.map(({ to, label, Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) => "sb-item" + (isActive ? " active" : "")}
            title={label}
          >
            <span className="sb-ico"><Icon size={20} /></span>
            <span className="sb-label">{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sb-section">Coming soon</div>
      <nav className="sb-nav">
        {SOON.map(({ label, Icon }) => (
          <div key={label} className="sb-item disabled" title={`${label} — coming soon`}>
            <span className="sb-ico"><Icon size={20} /></span>
            <span className="sb-label">{label}</span>
            <span className="chip-soon">SOON</span>
          </div>
        ))}
      </nav>

      <div className="sb-foot">
        <button
          className="btn gemini sb-ask"
          onClick={onAskGemini}
          title="Ask Gemini about shipments, weather, ports, stock and more"
        >
          <SparkIcon size={16} />
          <span className="sb-label">Ask Gemini</span>
        </button>
        <div className="sb-powered">
          <GeminiIcon size={12} id="powered-gem" />
          Powered by Google Gemini
        </div>
      </div>
    </aside>
  );
}
