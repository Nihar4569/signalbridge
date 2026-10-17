import { useEffect, useRef } from "react";
import L from "leaflet";

const COLORS = { green: "#34a853", amber: "#fbbc04", red: "#ea4335" };

// Walk a polyline by distance: t (0..1) -> [lat, lon]
function makeSampler(points) {
  const segs = [];
  let total = 0;
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i], b = points[i + 1];
    const d = Math.hypot(b[0] - a[0], b[1] - a[1]);
    segs.push({ a, b, d });
    total += d;
  }
  return (t) => {
    if (!total) return points[0];
    let dist = Math.max(0, Math.min(1, t)) * total;
    for (const s of segs) {
      if (dist <= s.d) {
        const f = s.d ? dist / s.d : 0;
        return [s.a[0] + (s.b[0] - s.a[0]) * f, s.a[1] + (s.b[1] - s.a[1]) * f];
      }
      dist -= s.d;
    }
    return points[points.length - 1];
  };
}

// Ships are drawn at their TRUE position, derived from the real departure date
// and ETA (backend: domain/network.shipment_progress). A real voyage takes
// weeks, so the dot advances at that same real pace — it must not race across
// the ocean, or the map would contradict the shipment's own ETA.
const DAY_SECONDS = 86400;

export default function MapView({ data, height = 460 }) {
  const el = useRef(null);
  const map = useRef(null);
  const fleet = useRef([]);
  const raf = useRef(null);

  useEffect(() => {
    if (!el.current || map.current) return;
    map.current = L.map(el.current, { zoomControl: true, worldCopyJump: true }).setView([20, 55], 3);
    // Free OpenStreetMap tiles, darkened with CSS. No API key. See docs/map_setup.md.
    const tiles = window.SIGNALBRIDGE_TILES || {
      url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      attribution: "© OpenStreetMap contributors",
      className: "sb-dark-tiles",
    };
    L.tileLayer(tiles.url, {
      attribution: tiles.attribution,
      maxZoom: 19,
      className: tiles.className || "",
    }).addTo(map.current);

    return () => {
      cancelAnimationFrame(raf.current);
      map.current?.remove();
      map.current = null;
    };
  }, []);

  useEffect(() => {
    if (!map.current || !data) return;
    const m = map.current;
    // Everything we draw goes in one group, removed on cleanup, so a data
    // refresh replaces the layers instead of stacking duplicates on top.
    const group = L.layerGroup().addTo(m);
    fleet.current = [];
    const all = [];

    data.routes.forEach((r) => {
      all.push(...r.points);
      const color = COLORS[r.color] || COLORS.green;
      const poly = L.polyline(r.points, {
        color,
        weight: 3,
        opacity: 0.9,
        dashArray: r.health === "delayed" ? "6 8" : null,
      }).addTo(group);

      const popup = `<b>${r.shipment_id}</b> · ${r.sku}<br>${r.quantity} units · ${r.carrier_id}<br>ETA ${String(r.eta || "").slice(0, 10)} · ${r.health}`;
      poly.bindPopup(popup);

      const samp = makeSampler(r.points);
      const marker = L.marker(samp(r.progress), {
        icon: L.divIcon({ className: "", html: `<div class="ship-dot ${r.color}"></div>`, iconSize: [14, 14], iconAnchor: [7, 7] }),
      }).addTo(group).bindPopup(popup);

      // Fraction of the route covered per second on this voyage.
      const voyageDays = Math.max(1, (new Date(r.eta) - new Date(r.departed_at || r.eta)) / 86400000);
      fleet.current.push({ marker, samp, t: r.progress, speed: 1 / (voyageDays * DAY_SECONDS) });
    });

    data.locations.forEach((l) => {
      L.marker([l.lat, l.lon], {
        icon: L.divIcon({ className: "", html: `<div class="loc-dot ${l.type}"></div>`, iconSize: [8, 8], iconAnchor: [4, 4] }),
      }).addTo(group).bindPopup(`<b>${l.name}</b><br>${l.type}`);
    });

    data.alerts.forEach((a) => {
      L.marker([a.lat, a.lon], {
        icon: L.divIcon({ className: "", html: `<div class="alert-pin">${a.type === "weather" ? "⛈️" : "⛔"}</div>`, iconSize: [24, 24], iconAnchor: [12, 12] }),
      }).addTo(group).bindPopup(`<b>${a.title}</b><br>${a.detail}`);
    });

    if (all.length) m.fitBounds(all, { padding: [30, 30] });

    let last = 0;
    const tick = (now) => {
      const dt = last ? (now - last) / 1000 : 0;
      last = now;
      fleet.current.forEach((f) => {
        if (f.t < 1) {
          f.t = Math.min(1, f.t + f.speed * dt); // stop at destination
          f.marker.setLatLng(f.samp(f.t));
        }
      });
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf.current);
      group.remove();
    };
  }, [data]);

  return <div ref={el} className="map-box" style={{ height }} />;
}
