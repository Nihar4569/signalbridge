# SignalBridge — Prototype Performance Report

_Generated 2026-10-17T07:11:14+00:00 · macOS-27.0.1-arm64-arm-64bit · Python 3.11.14_

## Executive summary

- **Full AI recovery plan** (shortage → internal stock → supplier choice → margin → approval): **0.09 ms** average (11,523 plans/sec).
- **Dashboard assembly** (`/overview`): **0.84 ms**.
- **Correctness:** **100% — all invariants held** across 6 recovery plans (money, feasibility, chokepoint rule). Money is never produced by the AI.
- **Resilience:** **all fallbacks passed** (news GDELT→Google News, Gemini model chain, no-key graceful).
- **Scale:** 6 shipments on 6 real trade lanes, 20 supplier offers, 12 live signals.

## 1. Scale (bundled real-data snapshot)

| Entity | Count |
|---|---|
| locations | 24 |
| lanes | 6 |
| products | 6 |
| partners | 23 |
| shipments | 6 |
| order lines | 10 |
| stock balances | 17 |
| supplier offers | 20 |
| signals | 12 |
| at risk order pairs | 6 |
| supplier options evaluated | 20 |

## 2. Latency

Measured in-process on local fixtures (a snapshot of the Firestore tenant), to isolate engine speed from network. Each row is many iterations.

| Operation | avg | p50 | p95 | min | max | ops/sec |
|---|---|---|---|---|---|---|
| `assess_exposure` | 0.003 ms | 0.003 ms | 0.003 ms | 0.003 ms | 0.025 ms | 356,423 |
| `route_approval` | 0.000 ms | 0.000 ms | 0.000 ms | 0.000 ms | 0.010 ms | 3,989,516 |
| `build_recovery_plan` | 0.087 ms | 0.084 ms | 0.105 ms | 0.075 ms | 0.161 ms | 11,523 |
| `dashboard_overview` | 0.837 ms | 0.759 ms | 1.328 ms | 0.733 ms | 1.659 ms | 1,195 |
| `dashboard_map` | 0.291 ms | 0.284 ms | 0.347 ms | 0.275 ms | 0.429 ms | 3,432 |
| `incidents` | 0.042 ms | 0.041 ms | 0.049 ms | 0.040 ms | 0.052 ms | 23,956 |

## 3. Correctness — invariants re-checked on every plan

Each recovery plan is independently recomputed and verified. The AI explains; deterministic Python computes every number, so these are exact.

| Invariant | Result |
|---|---|
| Recovery cost = qty × unit price + shipping (recomputed) | 6/6 |
| Chosen supplier is the cheapest feasible option | 6/6 |
| Every option carries a human-readable reason | 6/6 |
| No feasible offer routes through a disrupted chokepoint | 6/6 |

**No violations found.**

## 4. Resilience (failure injection)

| Scenario | Fallback behaviour | Result |
|---|---|---|
| GDELT news API returns HTTP 429 | switches to Google News RSS | PASS |
| Primary Gemini model over quota (429) | next model in the chain answers | PASS |
| No Gemini API key configured | returns a safe local summary, never crashes | PASS |

---

_Reproduce: `python tests/benchmark/benchmark.py` (add `--gemini` for section 5)._
