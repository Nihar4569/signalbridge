import Topbar from "../components/Topbar.jsx";

const FEATURES = [
  ["🎯", "Impact Triage", "Filters thousands of transit exceptions down to the orders that will actually cause a stockout or OTIF penalty.", true],
  ["💰", "Margin Optimization", "Weighs recovery cost against the protected margin, so we never spend more than the order is worth.", true],
  ["🔁", "Internal Balancing", "Scans our own DCs and dark stores for free stock before authorising any external spot buy.", true],
  ["🏛️", "Multi-Tier Governance", "Routes approvals by value — local planner, regional manager, or executive sign-off.", true],
  ["📦", "Predictive Surplus", "Flags the overstock created when a delayed shipment finally lands after replacements arrive.", true],
  ["🗺️", "Live Route Map", "Real-time lane tracking with colour-coded health plus weather and disruption alerts.", true],
  ["🌦️", "Live Weather & News", "Open-Meteo and GDELT, filtered by location, feeding the agent real-world signals.", true],
  ["✨", "Gemini Recovery Plans", "Gemini explains every plan in plain English, grounded in deterministic calculations.", true],
  ["📧", "Automated Fulfilment", "On approval: reserves stock, raises the PO and transfer, and emails every party.", true],
  ["⭐", "Customer Priority (VIP)", "Allocate scarce replacement stock to VIP accounts and strict-SLA contracts first.", false],
  ["🧾", "Penalty & Insurance", "Bundle GPS logs, delay notices and costs, then auto-draft the penalty or insurance claim.", false],
  ["🥬", "Perishables Rescue", "Reroute at-risk fresh food or medicine to a nearby discounter or charity before it spoils.", false],
  ["🔥", "Firestore & Auth", "Cloud persistence, user roles and a complete, queryable audit trail.", false],
  ["📱", "Mobile Alerts", "Push notifications so planners can approve a recovery from their phone.", false],
];

export default function Capabilities({ onToggleSidebar }) {
  const live = FEATURES.filter((f) => f[3]).length;
  return (
    <>
      <Topbar
        title="Capabilities"
        subtitle={`${live} live in this prototype · ${FEATURES.length - live} on the roadmap`}
        onToggleSidebar={onToggleSidebar}
      />
      <div className="content">
        <div className="feat-grid">
          {FEATURES.map(([icon, title, desc, isLive]) => (
            <div className={"feat" + (isLive ? "" : " soon")} key={title}>
              <span className={"chip " + (isLive ? "green" : "yellow")}>{isLive ? "LIVE" : "SOON"}</span>
              <div className="feat-ico">{icon}</div>
              <h4>{title}</h4>
              <p>{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
