# Gemini and the optional ADK agent

## Where AI contributes

A notice saying a strike was cancelled can contain the same words as an active disruption. Gemini interprets the supplied meaning and explains its relevance to known shipment routes. Python then calculates the order impact and recovery proposal.

| Path | AI responsibility | Code responsibility |
|---|---|---|
| Signal scan | One interpretation for every supplied active shipment. | Validate the batch, apply policy, save assessments and calculate exposures. |
| Plan explanation | Explain the already-calculated proposal. | Calculate shortage, suppliers, money, surplus and approval tier. |
| Per-plan questions | Answer from assembled plan/business context. | Supply authoritative records and computed financial context. |
| Global assistant | Explain the network and answer questions from supplied context. | Assemble business records and any external context used by that request. |
| Decision walkthrough | Interpret a supplied synthetic notice in live mode. | Isolate the snapshot, validate the result and calculate the outcome. |

The main application uses [direct Gemini REST calls](../backend/ai/gemini.py). There are no sequential triage/recovery/governance ADK agents in that workflow.

## Structured shipment interpretation

The [strict output models](../backend/models/decision.py) define:

- `shipment_id`
- `status`: affected, unaffected or unknown
- `event_status`: active, planned, cancelled, none or uncertain
- `reason`
- `evidence[]`: supplied signal IDs and exact excerpts
- `unresolved_fields[]`

The request sends a portable JSON schema subset through `generationConfig.responseFormat.text`. Full Python validation still checks types, constraints and fields. The parser rejects missing, duplicate or unknown shipment IDs, unsupported references, non-exact excerpts, stale cited evidence and affected decisions without route-linked support. Unknown decisions require unresolved information.

These checks validate structure and references, not universal factual correctness. The model can still misunderstand a valid excerpt.

## Applying assessments safely

A valid affected interpretation can flag a shipment at risk. Unknown output does not silently clear a previous risk flag. An unavailable batch records a failed latest attempt while preserving the earlier assessment.

A deterministic severe-route policy can retain risk despite an unaffected interpretation. A validated cancellation can exclude its cited notice, but does not suppress an independent attack or other severe source. This is a bounded policy, not a complete event-revision system. The UI distinguishes policy overrides from the model's interpretation.

Current evidence windows are three hours for weather and 72 hours for news/notices, with a five-minute future-time tolerance. Gemini receives up to six current evidence records per location. Full remaining-leg timing is not modeled.

## Resilience and quota use

The REST helper tries configured models and keys within a shared nominal timeout budget. Unavailable, quota-limited or retired paths can fall through to another configured path. Successful responses identify the actual model. Cooldowns are process-local.

Explanations/chat can return labelled local fallback text. Shipment interpretation returns unavailable rather than inventing an assessment. Live decision walkthrough mode never substitutes its authored reference answer after a model failure.

A fallback is not successful AI inference, and loading animations are not execution traces. Live accuracy requires a labelled semantic evaluation; mocked tests do not establish it.

## The optional ADK path

[agent.py](../backend/agent/agent.py) creates one `LlmAgent`, `signal_agent`, also exported as `root_agent`. Only these tools are registered:

- `weather_risk_tool(location_id)`
- `news_scan_tool(location_id)`

Other wrappers exist in [tools.py](../backend/agent/tools.py), but their existence does not mean the agent invokes them. The web assistant and monitor do not call this ADK object.

To run it separately after [setup](start.md):

```bash
uv run adk run backend/agent
```

It needs `GOOGLE_API_KEY` and network/model quota. Ask about weather or disruption news near a known location. It is not an approval or financial execution agent.

## Rules for future AI integrations

Keep domain calculations in Python. Validate supplied IDs and treat external text as untrusted data. Add read-only tools only when a real use case needs them. Keep approval separate from model output, and test missing/conflicting evidence and unavailable-model behavior.

See [roadmap](roadmap.md) for live evaluation and optional assistant-tool integration.
