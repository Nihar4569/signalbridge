# Offline benchmark

Run from the repository root:

```bash
python tests/benchmark/benchmark.py --runs 5000 --output-dir ../output/benchmark
```

The default run blocks outbound socket connections. It uses a private in-memory
copy of `fixtures/`, not Firestore. It never approves plans or sends messages.
Do not add `--gemini` unless you intend to spend model quota: that option permits
network access and makes live assessment requests.

## What the measurements mean

- `stored_snapshot` checks every open SKU/location pair, including covered orders.
- `controlled_disruption` injects synthetic notices and risk flags into another
  private copy of the same sample records.
- The scenario clock defaults to **17 October 2026, 09:00 UTC**. `--as-of` accepts
  another timezone-qualified timestamp. This is separate from measurement time.
- `reference.py` independently calculates the declared policy from raw inputs.
  It imports no application logic and does not trust planner feasibility flags.
- `results.json` records every comparison and violation, input/code hashes,
  execution environment, actual iteration counts, and whether networking was blocked.
- `report.md` distinguishes measured execution time, policy checks, mocked
  resilience scenarios and negative controls. It never claims real-world AI accuracy.
- Recovery timing rotates across independently identified shortage cases. The
  reported 25 warm-ups are excluded, p95 uses nearest rank, and dashboard assembly
  has a separately reported maximum of 250 measured samples.
- Negative controls deliberately corrupt one valid supplier-recovery case. They
  test that the checker detects these selected faults, not every possible bug.
- Field-comparison counts are not independent business scenarios. Do not present
  a passing fraction as general accuracy, production reliability or realized savings.

The current reference policy includes stored disruption flags, internal on-hand
minus reservations, quote expiry/capacity/deadline/route safety, lowest feasible
external cost, configured approval limits and illustrative surplus. It does not
establish donor-demand safety, transfer transit times, coordinated stock allocation
across simultaneous plans or correctness of the original risk assessment.

## Regression results

Run the full pytest suite with outbound connections blocked and dummy API keys.
The dummy key allows legacy tests to exercise mocked model code without a real
credential. Pass that run's JUnit XML using `--regression-junit /path/to/regression.xml`
to include its actual counts. Without this option the benchmark makes no regression
test-count claim. Use XML generated from the same source revision as the benchmark.

The benchmark exits non-zero if validation, resilience, negative controls, supplied
regression results or explicitly requested live checks fail. `tests/test_benchmark.py`
covers hand-calculated expectations, deliberate faults, the network guard, current
Gemini response fields and failure exit behavior.

`verify_calculations.py` and `e2e_check.py` are separate legacy tools, not part of
this benchmark. In particular, the end-to-end tool can scan, call live models and
approve operations. Do not use it as an offline or zero-credit test.
