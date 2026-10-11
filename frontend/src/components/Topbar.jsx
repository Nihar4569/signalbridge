import { useEffect, useState } from "react";
import { api } from "../api.js";
import { IconMenu, IconSun, IconMoon } from "../icons.jsx";
import { useTheme } from "../ThemeContext.jsx";

export default function Topbar({ title, subtitle, onToggleSidebar, actions }) {
  const [online, setOnline] = useState(null);
  const [clock, setClock] = useState("");
  const { theme, toggle } = useTheme();

  useEffect(() => {
    api.health().then(() => setOnline(true)).catch(() => setOnline(false));
    const t = setInterval(() => setClock(new Date().toLocaleTimeString()), 1000);
    setClock(new Date().toLocaleTimeString());
    return () => clearInterval(t);
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
      <span className={"pill " + (online ? "live" : "off")}>
        <span className="dot blink" />
        {online === null ? "connecting" : online ? "LIVE" : "API offline"}
      </span>
    </header>
  );
}
