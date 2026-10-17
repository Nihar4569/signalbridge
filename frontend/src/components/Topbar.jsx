import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { IconMenu, IconSun, IconMoon } from "../icons.jsx";
import { useTheme } from "../ThemeContext.jsx";

function agoLabel(seconds) {
  if (seconds == null) return null;
  if (seconds < 60) return "live · updated just now";
  const mins = Math.floor(seconds / 60);
  return `live · updated ${mins}m ago`;
}

export default function Topbar({ title, subtitle, onToggleSidebar, actions, onScanComplete }) {
  const [online, setOnline] = useState(null);
  const [clock, setClock] = useState("");
  const [scan, setScan] = useState(null);
  const { theme, toggle } = useTheme();
  const cbRef = useRef(onScanComplete);
  const wasRunning = useRef(false);
  cbRef.current = onScanComplete;

  useEffect(() => {
    api.health().then(() => setOnline(true)).catch(() => setOnline(false));
    const t = setInterval(() => setClock(new Date().toLocaleTimeString()), 1000);
    setClock(new Date().toLocaleTimeString());

    let active = true;
    async function poll() {
      try {
        const s = await api.scanStatus();
        if (!active) return;
        setScan(s);
        // When a background scan finishes, pull the fresh data into the page.
        if (wasRunning.current && !s.running) cbRef.current?.();
        wasRunning.current = s.running;
      } catch {
        /* status is best-effort; ignore errors */
      }
    }
    poll();
    const p = setInterval(poll, 8000);
    return () => { active = false; clearInterval(t); clearInterval(p); };
  }, []);

  return (
    <header className="topbar">
      <button className="icon-btn" onClick={onToggleSidebar} aria-label="Toggle navigation">
        <IconMenu size={22} />
      </button>
      <div>
        <div className="page-title">{title}</div>
        {subtitle && <div className="page-sub">{subtitle}</div>}
      </div>
      <div className="top-spacer" />
      {actions}
      <button
        className="icon-btn theme-toggle"
        onClick={toggle}
        aria-label="Toggle theme"
        title={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      >
        <IconSun size={20} className="t-sun" />
        <IconMoon size={20} className="t-moon" />
      </button>
      <span className="pill clock">{clock}</span>
      {scan?.running ? (
        <span className="pill" style={{ color: "var(--info)" }} title="Fetching live weather & news">
          <span className="dot blink" /> fetching live data…
        </span>
      ) : (
        <span className={"pill " + (online ? "live" : "off")} title={scan?.last_finished_at || ""}>
          <span className="dot blink" />
          {online === null
            ? "connecting"
            : !online
            ? "API offline"
            : agoLabel(scan?.seconds_since_last_scan) || "LIVE"}
        </span>
      )}
    </header>
  );
}
