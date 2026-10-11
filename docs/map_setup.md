# map_setup.md — The map tiles (and the "API KEY REQUIRED" message)

## Why you saw "API KEY REQUIRED"

The map background is made of **tiles** served by a map provider. The first
version used **CARTO** dark tiles, and CARTO now requires a free account + API
key — so without one, their tiles show a **"API KEY REQUIRED"** watermark.

## The fix (already applied): free, no key

The dashboard now uses **OpenStreetMap** tiles by default, with a dark CSS filter
so they match the theme. These need **no API key and no signup** — the watermark
is gone and it works out of the box, including when deployed.

So **you don't need to do anything.** The map just works.

> OpenStreetMap asks that you keep usage reasonable (it's donated infrastructure).
> For a prototype/demo this is fine. For a high-traffic production app, use one of
> the keyed providers below.

---

## Want a nicer / branded dark map? Get a free key

All of these have a **free tier**. Pick one, get a key, paste it into
`frontend/config.js`. **MapTiler is the easiest.**

### Option A — MapTiler (recommended, easiest)

1. Go to <https://www.maptiler.com/> and click **Sign up** (free).
2. Verify your email and log in.
3. Open **Account → API keys** (or the "Keys" tab).
4. Copy your **API key** (a short string).
5. Pick a dark style URL. A good one is `dataviz-dark`. Your tile URL is:
   ```
   https://api.maptiler.com/maps/dataviz-dark/{z}/{x}/{y}.png?key=YOUR_KEY
   ```
6. In `frontend/config.js`, uncomment the block and paste it:
   ```js
   window.SIGNALBRIDGE_TILES = {
     url: "https://api.maptiler.com/maps/dataviz-dark/{z}/{x}/{y}.png?key=YOUR_KEY",
     attribution: "© MapTiler © OpenStreetMap contributors"
   };
   ```
7. Refresh the page. Done — no dark filter needed (the style is already dark).

Free tier: ~100,000 tile loads/month, which is plenty for a demo.

### Option B — CARTO (the one that showed the watermark)

1. Go to <https://carto.com/> → **Sign up** (free trial / developer).
2. In the dashboard, create an **API Access Token / key**.
3. Use their basemap style URL with your token (see their "Basemaps" docs). It
   looks like:
   ```
   https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?...token...
   ```
4. Put it in `config.js` as in Option A.

### Option C — Stadia Maps (Alidade Smooth Dark)

1. Go to <https://stadiamaps.com/> → **Sign up** (free).
2. Create a **property** and an **API key**; add `localhost` and your deploy
   domain to the allowed domains.
3. Tile URL:
   ```
   https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}.png?api_key=YOUR_KEY
   ```
4. Put it in `config.js`.

### Option D — Google Maps (most setup, needs billing)

Google Maps tiles need a **Google Cloud project with billing enabled** and the
**Map Tiles API**, and Leaflet isn't the native fit (Google has its own JS SDK).
Only go here if you specifically want Google branding. Steps:
1. In [Google Cloud Console](https://console.cloud.google.com/), create/select a
   project and **enable billing**.
2. Enable the **Map Tiles API** (and/or Maps JavaScript API).
3. **APIs & Services → Credentials → Create credentials → API key**.
4. Restrict the key (HTTP referrers = your domains).
5. Integrate per Google's Map Tiles docs. (For this prototype, MapTiler is far
   simpler and looks just as good.)

---

## How to apply a key (summary)

1. Get a key from one provider above.
2. Open `frontend/config.js`.
3. Uncomment the `window.SIGNALBRIDGE_TILES = { ... }` block and paste your tile
   URL + attribution. Omit `className` (premium dark styles don't need the
   filter).
4. Refresh (local) or redeploy (Firebase Hosting).

To go back to the free default, just comment the block out again.

---

## Keep keys safe

- Map keys are **public** (they ship in the browser) — that's normal for map
  tiles. Protect them with **domain/referrer restrictions** in the provider's
  dashboard so others can't reuse them.
- Do **not** reuse your Gemini or Google Cloud keys for maps. Use a separate,
  restricted map key.
