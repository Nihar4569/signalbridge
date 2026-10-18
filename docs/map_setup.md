# Map configuration and meaning

The current frontend uses Leaflet with OpenStreetMap raster tiles. It does not use Google Maps and needs no map API key for its default provider.

## What the map represents

Routes, locations and alerts come from `GET /map`. Shipment progress is derived from stored departure/arrival dates and animated along a schematic polyline. It is not live GPS, AIS or carrier telemetry. A displayed arrival can be a stored scenario assumption, not a verified carrier prediction.

Colors reflect the application's shipment-health policy. A recovery/covered indication is not independent proof that stock was purchased or delivered.

## Current tile configuration

[MapView.jsx](../frontend/src/components/MapView.jsx) reads `window.SIGNALBRIDGE_TILES`, falling back to:

```javascript
{
  url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
  attribution: "© OpenStreetMap contributors",
  className: "sb-dark-tiles"
}
```

This documents the checked-in URL, not a recommendation that its subdomain pattern is the latest provider preference. OpenStreetMap currently recommends the canonical `https://tile.openstreetmap.org/{z}/{x}/{y}.png` URL. A future source/configuration update can adopt it deliberately.

## Overriding tiles

There is no `frontend/config.js`.

To intentionally configure another provider, define the global before the module script in `frontend/index.html`, or implement a deliberate configuration mechanism. Example shape:

```html
<script>
  window.SIGNALBRIDGE_TILES = {
    url: "https://YOUR-PROVIDER/{z}/{x}/{y}.png?key=YOUR-PUBLIC-MAP-KEY",
    attribution: "YOUR-PROVIDER-ATTRIBUTION"
  };
</script>
```

Omitting `className` avoids applying the default tile filter to an already-styled basemap. Rebuild/redeploy after changing the source. The sample is an integration instruction, not a provider already enabled.

Browser map tokens are public and must be restricted appropriately. Never reuse a private Gemini or service-account credential in frontend configuration.

## Provider policy

OpenStreetMap public tiles are donated infrastructure with usage conditions, attribution and caching requirements, not a guaranteed production SLA. Do not bulk-download or prefetch them indiscriminately. Review the [official tile policy](https://operations.osmfoundation.org/policies/tiles/) before scaling usage.

Other providers have their own licences, quotas and key restrictions. No provider-specific free-tier allowance is guaranteed here.

## Troubleshooting

- Confirm that `GET /map` succeeds and contains route points.
- Inspect tile requests and provider policy/errors separately from API errors.
- Keep attribution visible.
- Missing coordinates or route points can omit a marker/route.
- A moving marker does not validate a real shipment's location.

Google Maps or carrier-based positions remain optional future integrations, not current project usage.
