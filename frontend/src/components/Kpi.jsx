import { useEffect, useRef, useState } from "react";

/** A KPI tile whose number counts up on mount. */
export default function Kpi({ label, value, format, foot, accent = "var(--primary)", icon }) {
  const [n, setN] = useState(0);
  const raf = useRef(null);

  useEffect(() => {
    if (value == null) return;
    const start = performance.now();
    const step = (now) => {
      const p = Math.min(1, (now - start) / 700);
      setN(value * (0.5 - Math.cos(Math.PI * p) / 2)); // ease in-out
      if (p < 1) raf.current = requestAnimationFrame(step);
    };
    raf.current = requestAnimationFrame(step);
    // rAF is paused in background tabs, so guarantee the final value regardless.
    const settle = setTimeout(() => setN(value), 800);
    return () => {
      cancelAnimationFrame(raf.current);
      clearTimeout(settle);
    };
  }, [value]);

  return (
    <div className="kpi" style={{ "--accent-line": accent }}>
      <div className="kpi-top">
        {icon}
        {label}
      </div>
      <div className="kpi-val">
        {value == null ? "—" : format ? format(n) : Math.round(n)}
      </div>
      {foot && <div className="kpi-foot">{foot}</div>}
    </div>
  );
}
