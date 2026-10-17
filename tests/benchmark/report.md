# SignalBridge measured offline benchmark

Measured at 2026-10-17T18:18:46.225592+00:00. Fixed scenario clock: 2026-10-17T09:00:00+00:00.

## Scope

Actual local execution measurements on bundled sample records, with a separate controlled disruption scenario. These are not live customer outcomes, cloud API latencies, AI accuracy scores or production capacity measurements.

Outbound network connections are blocked by default. No Firestore writes, reservations, purchases or emails occur. Fallbacks use mocked HTTP responses.

## Dataset

| Record type | Count |
|---|---:|
| locations | 27 |
| lanes | 9 |
| products | 10 |
| partners | 31 |
| shipments | 15 |
| order_lines | 20 |
| stock_balances | 29 |
| supplier_offers | 36 |
| signals | 5 |

## Independent validation

The reference calculator reads raw orders, stock, routes, signals and offers. It does not call the application calculator or trust its feasibility flags. It validates the current documented sample-data policy, not all operational risks.

| Scenario | Plans matched | Shortage / covered | Field comparisons |
|---|---:|---:|---:|
| stored_snapshot | 11/11 | 4 / 7 | 341/341 |
| controlled_disruption | 11/11 | 11 / 0 | 593/593 |

Comparisons include demand, incoming supply, shortage, internal free stock, offer coverage, capacity, delivery deadline, expiry, blocked routes, supplier selection, cost, revenue exposure, penalties, surplus and approval tier. Equal-cost optimal offers are accepted. Reason text is checked for presence only.

## Local latency

Warm in-process calls, sequential execution. Each operation excludes 25 warm-ups. Recovery plans rotate across independently identified shortage cases. p95 uses the nearest-rank method. These numbers exclude network and model latency.

| Operation | Samples | Mean ms | Median ms | p95 ms |
|---|---:|---:|---:|---:|
| assess_exposure | 5000 | 0.0051 | 0.0050 | 0.0053 |
| build_recovery_plan | 5000 | 0.3445 | 0.3355 | 0.4060 |
| dashboard_overview_assembly | 250 | 4.0434 | 3.9992 | 4.2637 |

## Simulated resilience

5/5 mocked failure scenarios passed.

- news_429_to_rss: PASS
- model_503: PASS
- key_429: PASS
- no_keys: PASS
- all_models_unavailable: PASS

## Benchmark negative controls

16/16 deliberately injected faults detected. This measures sensitivity to these selected faults, not AI accuracy.

Control case: CHOC-GIFT-500 at WH-MUM. Faults target this selected recovery case, not every plan.
- altered_exposure.shortage_qty: DETECTED
- altered_exposure.supply_by_deadline: DETECTED
- altered_internal_used_qty: DETECTED
- altered_supplier_qty: DETECTED
- altered_recovered_qty: DETECTED
- altered_margin_check.recovery_cost_minor: DETECTED
- altered_margin_check.protected_revenue_minor: DETECTED
- altered_margin_check.penalty_avoided_minor: DETECTED
- altered_margin_check.net_benefit_minor: DETECTED
- altered_surplus_forecast.expected_surplus_qty: DETECTED
- missing_supplier_choice_and_options: DETECTED
- wrong_approval_tier: DETECTED
- ignored_quote_expiry: DETECTED
- ignored_supplier_capacity: DETECTED
- ignored_delivery_deadline: DETECTED
- ignored_blocked_route: DETECTED

## Limitations

- Business records are bundled sample data. Injected disruption notices are synthetic.
- Arrival delays are scenario assumptions, not Gemini-predicted ETAs.
- Individual plans do not prove simultaneous recovery feasibility across shared stock.
- Internal availability excludes reservations but not donor demand or transit time.
- Margin figures are decision estimates, not realized savings or profit.
- Offline results do not measure live Gemini, cold starts, concurrent load or uptime.

Overall benchmark status: PASS.

Full comparisons, violations, fixture/code hashes and environment are in results.json.
