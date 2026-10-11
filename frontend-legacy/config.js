// Backend API location. For local dev this is the FastAPI server on port 8000.
// When you deploy, either edit this value to your Cloud Run URL, or define
// window.SIGNALBRIDGE_API before this script loads. See docs/frontend_setup.md.
window.SIGNALBRIDGE_API = window.SIGNALBRIDGE_API || "http://localhost:8000";

// OPTIONAL: nicer map tiles.
// By default the map uses FREE OpenStreetMap tiles with a dark filter — no API
// key, nothing to set up. If you want a premium dark basemap (CARTO, MapTiler,
// Stadia, ...), get a key by following docs/map_setup.md, then uncomment and
// fill this in (drop the "className" so the dark filter is NOT applied):
//
// window.SIGNALBRIDGE_TILES = {
//   url: "https://api.maptiler.com/maps/dataviz-dark/{z}/{x}/{y}.png?key=YOUR_KEY",
//   attribution: "© MapTiler © OpenStreetMap contributors"
// };
