# groundcover Provider Architecture (ADR)

## Status
Proposed - June 17, 2026. Covers DX-343.

This is a contributor design note for adding groundcover as a first-class
observability provider. The fork is public, so private groundcover source paths
and local-only audit details are intentionally omitted. Refresh the source
audit before implementation PRs if the public MCP surface changes.

## Context
OpenSRE already treats providers such as Grafana, Datadog, Honeycomb, and
Coralogix as first-class observability sources. A first-class provider is more
than a client: it has normalized configuration, verification, registered tools,
investigation routing, docs, tests, and stable failure behavior.

groundcover should provide the same shape for incidents whose evidence lives in
groundcover logs, traces, metrics, APM measurements, Kubernetes events,
entities, monitors, and monitor issues.

One motivation for this provider is that OpenSRE users can already point an
agent at the groundcover MCP server directly, but that leaves too much query
discipline to chance. Efficient groundcover investigations require provider
skills: narrow time windows, bounded row limits, metadata discovery before
guessing fields, aggregation over raw row pulls for wide ranges, and explicit
gcQL syntax guidance. OpenSRE must ship that skill out of the box instead of
depending on an external MCP resource that the model may not read.

## Source Audit Summary
OpenSRE integration work needs to touch these surfaces:

- `app/integrations/config_models.py` for strict normalized credentials.
- `app/integrations/_catalog_impl.py` and `app/integrations/registry.py` for
  local store/env resolution, aliases, setup order, and verification support.
- `app/integrations/verify.py` and verification adapters for
  `opensre integrations verify groundcover`.
- `app/services/groundcover/client.py` for transport, auth, routing, retries,
  JSON/SSE parsing, and response normalization.
- `app/tools/Groundcover*Tool/` packages for investigation and chat tools.
- `app/agent/extract.py`, `app/agent/investigation.py`, and
  `app/agent/prompt.py` for alert-source detection, first-round auto-calls,
  and "Where to start" guidance.
- `app/types/evidence.py` for the canonical evidence source literal.
- `.env.example`, `docs/configuration/environment-variables.mdx`,
  `docs/groundcover.mdx`, and `docs/docs.json` for user setup docs.
- `tests/integrations/`, `tests/tools/`, and at least one investigation
  scenario fixture for runtime usefulness.

Existing OpenSRE provider guidance is mostly carried through tool metadata, not
separate provider prompt files. `app/agent/prompt.py` renders each tool's
description, examples, anti-examples, evidence type, side-effect level, and
output keys into the investigation prompt. Grafana and Datadog tools use this
pattern today. groundcover should use the same mechanism, plus a dedicated
query-reference wrapper where useful.

The current groundcover public MCP contract is sufficient for v1 read-only
OpenSRE investigation:

- Endpoint: `https://mcp.groundcover.com/api/mcp`.
- Transport: streamable HTTP MCP with JSON-RPC responses and possible SSE
  framing.
- Required auth: `Authorization: Bearer <service-account-token>`.
- Request headers to support: `MCP-Protocol-Version: 2024-11-05`,
  `Accept: application/json, text/event-stream`, `Content-Type:
  application/json`, `X-Timezone`, and optional `X-Tenant-Uuid` /
  `X-Backend-Id`.
- Routing: `list_workspaces` discovers available `tenant_uuid` and
  `backend_id` values. Some public tools also accept routing fields in the tool
  arguments, but the client should still set routing headers when configured so
  every public tool, including metrics and monitors, has consistent context.
- Public read-only tools include `list_workspaces`, `get_gcql_reference`,
  `query_logs`, `query_traces`, `query_events`, `query_entities`,
  `query_issues`, `query_apm`, `query_metrics`, `query_monitors`,
  `search_logs_metadata`, `search_traces_metadata`,
  `search_events_metadata`, and `search_metrics_metadata`.

## Decision
Use an MCP-first provider architecture for v1.

Do not start with direct REST/router calls. Public MCP already exposes the
read-only evidence OpenSRE needs, carries read-only annotations, documents gcQL
query rules through `get_gcql_reference`, and keeps routing semantics owned by
groundcover. REST can be added later behind the same service client only if a
specific first-class workflow cannot be represented by the public MCP tools.

Do not implement write/remediation actions in v1. Monitor creation, monitor
updates, silencing, notification-route changes, and any other mutating action
are out of scope for this provider.

Treat groundcover query guidance as a product requirement, not documentation
nice-to-have. A correct implementation must make efficient query behavior
visible to the model before it writes expensive gcQL or PromQL.

## Query Guidance Contract
Every groundcover implementation PR should preserve these rules in code,
metadata, and tests:

- Tool descriptions must state the default query strategy: start with the
  narrowest relevant window, default to one hour, widen only after an empty or
  inconclusive result, and avoid multi-day raw scans unless the user explicitly
  asks for that range.
- Logs, traces, events, and issues tools must require or inject a row cap. gcQL
  examples must include `| limit N`.
- Wide-window examples must use `stats` or other aggregation patterns instead
  of raw row pulls.
- Tools should guide the model to discover fields before guessing. Logs,
  traces, events, and metrics should mention metadata search. Entities and
  issues should mention `* | field_names` where applicable.
- Custom gcQL tools must tell the model to fetch or rely on the groundcover
  reference before composing non-trivial queries. The implementation can expose
  this as `get_groundcover_query_reference`, as an automatic cached
  `get_gcql_reference` call inside the service client, or both.
- Error responses for parse errors, empty results, timeouts, and row-cap issues
  must include concise corrective hints: narrow the time range, add filters,
  add or lower `| limit N`, use metadata discovery, or aggregate.
- Tests must assert that prompt/tool metadata includes the query guidance, not
  only that the transport call succeeds.

This is deliberately redundant with the upstream MCP reference. OpenSRE's
first-class provider should work even when the underlying MCP resource or
reference tool is not automatically surfaced by the user's LLM client.

## Configuration Contract
Add a strict `GroundcoverIntegrationConfig` with these fields:

| Field | Env var | Default | Notes |
| --- | --- | --- | --- |
| `api_key` | `GROUNDCOVER_API_KEY` | required | Bearer service-account token. Support `GROUNDCOVER_MCP_TOKEN` as a compatibility alias only if needed. |
| `mcp_url` | `GROUNDCOVER_MCP_URL` | `https://mcp.groundcover.com/api/mcp` | Must be HTTPS, except loopback for tests/dev. |
| `tenant_uuid` | `GROUNDCOVER_TENANT_UUID` | empty | Optional for single-workspace accounts; required when verification detects ambiguity. |
| `backend_id` | `GROUNDCOVER_BACKEND_ID` | empty | Optional for single-backend tenants; required when verification detects ambiguity. |
| `timezone` | `GROUNDCOVER_TIMEZONE` | `UTC` | Sent as `X-Timezone`; affects returned timestamps. |
| `integration_id` | store metadata | empty | Matches existing integration model patterns. |

Support `GROUNDCOVER_INSTANCES` as the multi-instance JSON override after the
single-instance path works. Multi-instance support should match the existing
Grafana/Datadog instance shape: `{name, tags, credentials}`.

Verification should be low impact:

1. Connect to MCP with the configured token and headers.
2. Call `list_workspaces`.
3. If no tenant/backend is configured and the account has multiple choices,
   return an actionable verification failure that names the missing field.
4. Call `get_gcql_reference` or `tools/list` to prove the expected public tool
   surface exists without querying customer telemetry.

## Service Client Contract
Create `app/services/groundcover/client.py` as the only module that knows MCP
wire details. Tool modules should call typed methods on this client, not build
JSON-RPC payloads directly.

The client should:

- Use the existing `mcp` dependency's streamable HTTP client when practical.
  If direct HTTP is needed for testability, keep the JSON-RPC/SSE parser
  private to this service package.
- Redact bearer tokens and service-account token shapes from exceptions,
  traces, debug output, and returned tool payloads.
- Normalize JSON-RPC errors, 401/403, 429, 5xx, timeout, malformed SSE, and
  empty results into stable investigation-friendly dictionaries.
- Keep timeouts short by default and expose per-call overrides only where
  tools need them.
- Set routing headers from config on every request.
- Cache the groundcover query reference per client/session once fetched, so
  tools can include concise hints without repeatedly spending tokens.
- Provide a small method surface: `list_workspaces`, `list_tools`,
  `get_query_reference`, `call_tool`, and convenience methods for each
  first-class OpenSRE tool.

## Tool Shape
Use `source="groundcover"` for every tool and set
`side_effect_level="read_only"` where the decorator supports it. Prefer one
tool per evidence family so the planner sees clear capabilities:

- `get_groundcover_query_reference`: wraps `get_gcql_reference` and returns
  the concise groundcover query skill. This tool should be cheap, read-only,
  visible on investigation/chat surfaces, and referenced by custom query tool
  descriptions.
- `query_groundcover_logs`: wraps `query_logs`; takes gcQL, time range, limit,
  optional tenant/backend override, and returns compacted logs plus an error
  taxonomy where useful.
- `query_groundcover_traces`: wraps `query_traces`; takes gcQL, time range,
  limit, and returns spans/traces with high-latency and error summaries.
- `query_groundcover_metrics`: wraps `query_metrics`; supports `get_names`,
  `get_labels`, `query_range`, and `query_instant` modes. It should encourage
  metric discovery before PromQL execution.
- `query_groundcover_apm`: wraps `query_apm`; use for request, error-rate, and
  latency aggregates. Surface version-gate errors directly and clearly.
- `query_groundcover_events`: wraps `query_events` for Kubernetes warning and
  lifecycle evidence.
- `query_groundcover_entities`: wraps `query_entities` for live Kubernetes
  object state.
- `query_groundcover_monitors`: wraps `query_monitors` for monitor definitions
  and current health.
- `query_groundcover_issues`: wraps `query_issues` for monitor issue
  instances, active alerts, and historical firings.
- Optional metadata helpers can wrap `search_*_metadata` if discovery through
  the main tools is too cumbersome for the planner.

The output envelope should be consistent across tools:

```json
{
  "source": "groundcover_logs",
  "available": true,
  "query": "* | filter level:error | limit 50",
  "time_range": {"start": "...", "end": "..."},
  "data": [],
  "summary": {},
  "truncated": false,
  "error": null
}
```

Do not return raw MCP protocol envelopes to the investigator. Preserve enough
metadata for evidence, but keep protocol details inside the service client.

## Investigation Wiring
Add `groundcover` as a canonical alert source and evidence source.

Required wiring:

- `app/types/evidence.py`: add `"groundcover"`.
- `app/agent/extract.py`: classify groundcover alerts when alert payloads,
  URLs, monitor issue links, or source labels mention groundcover.
- `app/agent/investigation.py`: map `alert_source == "groundcover"` to the
  groundcover tool source so the first tool round starts there.
- `app/agent/prompt.py`: map `alert_source == "groundcover"` to
  `["groundcover"]` for prompt guidance.
- Alert fixtures should cover at least one monitor issue or workload alert with
  `alert_source: groundcover` and prove the first investigation round calls
  groundcover tools before secondary sources.

## Docs and Tests
Implementation PRs must follow `TOOL_INTEGRATION_CHECKLIST.md` and `CI.md`.
For this provider, the minimum useful test plan is:

- Config model and env-loader tests, including URL normalization, token
  presence, timezone default, and multi-instance parsing.
- Verification tests with a fake MCP server for success, missing token,
  ambiguous routing, unauthorized, and missing expected tools.
- Service-client tests for JSON responses, SSE `data:` framing, JSON-RPC
  errors, timeout, 429/5xx, malformed payloads, secret redaction, and cached
  query-reference behavior.
- Tool contract tests for metadata, schemas, `is_available`, `extract_params`,
  success payloads, empty results, upstream errors, and groundcover query
  guidance in descriptions/examples.
- Prompt/agent context tests proving the rendered investigation prompt includes
  the groundcover query guidance when the provider is connected.
- Registry/discovery tests proving groundcover tools appear on the expected
  investigation and chat surfaces only when configured.
- Prompt/agent routing tests proving groundcover alert sources are primary.
- At least one realistic synthetic/investigation fixture showing logs, traces,
  metrics/APM, monitors, and issues can contribute RCA evidence without an
  unbounded query.

User-facing docs should be added with the first runtime feature PR, not only at
the end. `docs/groundcover.mdx` should cover service-account token creation,
env vars, `opensre integrations setup groundcover`, verification, sample
queries, default query limits, time-window guidance, and common failures such
as ambiguous tenant/backend selection.

## Security and Reliability Guardrails
- Never commit tokens or tenant-specific defaults.
- Prefer read-only service-account tokens and read-only MCP tools.
- Redact `Authorization`, `GROUNDCOVER_API_KEY`, `GROUNDCOVER_MCP_TOKEN`, and
  token-like values in all returned errors.
- Keep default query windows narrow. Wide logs/traces/issues ranges should
  require explicit user intent.
- Do not expose private/internal MCP tools through OpenSRE.
- Fail closed: if the configured token cannot list tools or verify routing, the
  groundcover tools must not be planner-visible.
- Keep gcQL guidance close to the tools. The first tool call in a session should
  be able to fetch `get_gcql_reference` when the model needs query syntax.

## Open Questions for Implementation
- Should `opensre integrations setup groundcover` ask for tenant/backend
  eagerly, or verify first and ask only when the account is ambiguous?
- Should metadata search be separate planner-visible tools, or should the main
  logs/traces/events/metrics tools perform discovery as a mode?
- Should APM live as a dedicated `query_groundcover_apm` tool or be grouped
  under metrics in the prompt copy? The transport surface is separate, so a
  dedicated tool is clearer unless planner noise becomes an issue.
- Which groundcover alert payload fields are stable enough for extraction tests
  beyond explicit `alert_source: groundcover`?
