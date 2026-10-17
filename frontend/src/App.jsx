import { useCallback, useEffect, useState } from "react";
import { Routes, Route, useLocation } from "react-router-dom";
import Sidebar from "./components/Sidebar.jsx";
import GeminiPanel from "./components/GeminiPanel.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Shipments from "./pages/Shipments.jsx";
import Incidents from "./pages/Incidents.jsx";
import Recoveries from "./pages/Recoveries.jsx";
import Signals from "./pages/Signals.jsx";
import Capabilities from "./pages/Capabilities.jsx";
import DecisionDemo from "./pages/DecisionDemo.jsx";
import { api } from "./api.js";

export default function App() {
  const [collapsed, setCollapsed] = useState(false);
  const [geminiOpen, setGeminiOpen] = useState(false);
  const toggle = () => setCollapsed((c) => !c);
  const closeGemini = useCallback(() => setGeminiOpen(false), []);
  const isWalkthrough = useLocation().pathname === "/decision-demo";

  // Fetch fresh live weather + news whenever the app loads. As of now this
  // page-load trigger stands in for Google Cloud Scheduler (keeps us on the
  // free tier); later a Cloud Scheduler cron will call the same /scan endpoint.
  useEffect(() => { if (!isWalkthrough) api.triggerScan().catch(() => {}); }, [isWalkthrough]);

  return (
    <div className={"app" + (collapsed ? " collapsed" : "")}>
      <Sidebar onAskGemini={() => setGeminiOpen(true)} />
      <div className="main-area">
        <Routes>
          <Route path="/" element={<Dashboard onToggleSidebar={toggle} />} />
          <Route path="/shipments" element={<Shipments onToggleSidebar={toggle} />} />
          <Route path="/incidents" element={<Incidents onToggleSidebar={toggle} />} />
          <Route path="/recoveries" element={<Recoveries onToggleSidebar={toggle} />} />
          <Route path="/signals" element={<Signals onToggleSidebar={toggle} />} />
          <Route path="/capabilities" element={<Capabilities onToggleSidebar={toggle} />} />
          <Route path="/decision-demo" element={<DecisionDemo onToggleSidebar={toggle} />} />
        </Routes>
      </div>
      {/* Always mounted so the conversation survives closing and page changes. */}
      <GeminiPanel open={geminiOpen} onClose={closeGemini} />
    </div>
  );
}
