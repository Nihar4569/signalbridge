# External weather and news sources

External signals provide context for a shipment assessment, not carrier-confirmed delays. Normal news inputs are headlines/metadata. The application does not crawl complete articles.

## Weather: Open-Meteo

[weather.py](../backend/adapters/weather.py) calls `https://api.open-meteo.com/v1/forecast` with coordinates, UTC and a default three-day forecast. Requested hourly variables are precipitation, wind speed, gusts and weather code.

The adapter summarizes maximum precipitation/gusts and the maximum weather code, then applies configured thresholds:

| Condition | Adapter risk |
|---|---|
| Gusts at least 60 km/h, precipitation at least 20 mm, or code in {95, 96, 97, 99} | high |
| Gusts at least 40 km/h or precipitation at least 10 mm | medium |
| Otherwise | low |

Precipitation here is the maximum returned hourly value, not the whole forecast's accumulated total. Thresholds are application policy, not a prediction of transit delay.

Failures return unknown/error states. The module also supports a multi-location helper, but the current worker uses the single-location helper per place.

Open-Meteo's free endpoint is intended for non-commercial use and currently lists limits of 600 calls/minute, 5,000/hour, 10,000/day and 300,000/month, without an uptime guarantee. Commercial use requires an appropriate plan. Reviewed 18 October 2026: [official pricing/terms](https://open-meteo.com/en/pricing). Installation/reference replay and external-source usage are different things.

## News: GDELT with Google News RSS fallback

[news.py](../backend/adapters/news.py) searches a location phrase plus configured disruption keywords.

- Primary: `https://api.gdeltproject.org/api/v2/doc/doc`.
- Parameters include `mode=artlist`, JSON, newest-first sort, configured timespan (default 3d) and record limit (default 10).
- The adapter spaces GDELT attempts by 5.2 seconds and pauses that provider for 300 seconds after certain failures.
- On primary failure it tries Google News RSS search.
- Successful results are cached for 600 seconds within the process.
- Returned metadata identifies the provider. Error handling does not establish a provider SLA.

Discovery keywords include disruption and security-event terms. They are a search filter, not a semantic classifier: a cancelled-strike headline can still match, while some useful paraphrases may not be discovered.

Google News RSS is an external source, not a managed Google Cloud AI service or proof of web grounding inside Gemini. Availability and provider terms must be respected.

GDELT discovery time and RSS publication metadata do not prove the underlying event's occurrence time. Freshly fetched historical reporting may still concern an old event.

## Where the adapters are used

| Caller | Behavior |
|---|---|
| `GET /signals/{location_id}` | Live lookup for a selected place. Does not itself run full triage. |
| Scan worker | Reads selected locations, fetches sources, ingests signals and invokes Gemini interpretation. |
| Optional ADK agent | Registered weather/news tools call the adapters. |
| Assistant context helpers | Can enrich relevant questions with external context; inspect the actual returned source metadata. |

See [monitoring](scheduler.md) for triggers and persistence. The worker's discovery set includes all active ports/sea waypoints as well as in-transit destinations; it is not limited to exactly one lane.

## Evidence storage and interpretation

Weather readings replace the place's previous weather signal. News is keyed by article URL. Current ingestion leaves `ttl_at` null; it does not activate automatic deletion.

Gemini receives bounded current evidence and known route/record IDs. Python validates references and exact excerpts before applying assessments. A structurally valid result is not proof of factual truth or exact remaining-leg applicability. Unknown/unavailable interpretation must remain visible.

Real news/weather and synthetic retail records must be labelled separately. The [fixed walkthrough](decision_walkthrough.md) uses owned synthetic notices and a private clock rather than depending on today's headlines.

## Later integrations

Carrier tracking, supplier confirmations, licensed authority notices and production weather sources can improve reliability after their access/terms and contracts are established. Google Weather, Document AI or other Google services are options, not currently used integrations.

Do not run a manual scan or live assistant query as an offline benchmark. Use the [network-blocked benchmark](../tests/benchmark/README.md).
