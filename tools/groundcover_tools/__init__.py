# ======== from tools/groundcover_logs_tool/ ========

"""groundcover logs query tool (gcQL over query_logs)."""

from __future__ import annotations

from typing import Any

from integrations.groundcover.client import GroundcoverClient
from tools.tool_decorator import tool
from tools.utils.availability import groundcover_available_or_backend
from tools.utils.groundcover import (
    DEFAULT_LOGS_QUERY,
    GCQL_GUIDANCE,
    base_extract_params,
    run_signal_query,
)

_LOGS_SOURCE = "groundcover_logs"
_LOGS_MCP_TOOL = "query_logs"

_LOGS_QUERY_DESCRIPTION = (
    "gcQL query. Lead with the filter directly (not a '| filter' pipe) and include "
    "'| limit N'. Project raw rows with '| fields ...' rather than a bare select-all. "
    "Examples: 'level:error | fields _time, workload, instance, content | limit 50'; "
    "'workload:checkout level:error | fields _time, instance, content | limit 50'; "
    "'* | stats by (workload) count() if (level:error) as errors | sort by (errors desc) "
    "| limit 20'."
)


def _logs_is_available(sources: dict[str, dict]) -> bool:
    """Available when groundcover credentials are present or a fixture backend is injected."""
    return groundcover_available_or_backend(sources)


def _logs_extract_params(sources: dict[str, dict]) -> dict[str, Any]:
    """Inject a pre-built client + seed query, never raw credentials."""
    return base_extract_params(sources.get("groundcover", {}), default_query=DEFAULT_LOGS_QUERY)


@tool(
    name="query_groundcover_logs",
    display_name="groundcover logs",
    source="groundcover",
    tags=("logs", "observability"),
    cost_tier="moderate",
    description=(
        "Search groundcover logs with gcQL. Use for application errors, exceptions, and service "
        "log events. " + GCQL_GUIDANCE + " Discover fields with '* | field_names' or by calling "
        "get_groundcover_query_reference."
    ),
    use_cases=[
        "Finding error/exception logs for a workload or namespace",
        "Correlating log spikes with a groundcover monitor issue",
        "Counting errors per workload with a single stats query over a narrow window",
    ],
    requires=[],
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": _LOGS_QUERY_DESCRIPTION},
            "start": {"type": "string", "description": "RFC3339 start time (optional)"},
            "end": {"type": "string", "description": "RFC3339 end time (optional)"},
            "period": {
                "type": "string",
                "description": "ISO-8601 duration window, e.g. PT1H (default).",
                "default": "PT1H",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    is_available=_logs_is_available,
    extract_params=_logs_extract_params,
)
def query_groundcover_logs(
    query: str = "",
    start: str = "",
    end: str = "",
    period: str = "",
    _groundcover_client: GroundcoverClient | None = None,
    groundcover_backend: Any = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Search groundcover logs with gcQL and return the normalized OpenSRE envelope.

    Credentials never travel through the model-facing arguments: ``extract_params``
    binds a pre-built :class:`GroundcoverClient` into ``_groundcover_client`` (and an
    optional synthetic ``groundcover_backend``), both stripped from seed input by the
    redactor. An empty query yields a cheap guidance envelope with no MCP round trip.
    """
    return run_signal_query(
        source=_LOGS_SOURCE,
        mcp_tool=_LOGS_MCP_TOOL,
        client=_groundcover_client,
        query=query,
        start=start,
        end=end,
        period=period,
        backend=groundcover_backend,
    )


# ======== from tools/groundcover_query_reference_tool/ ========

"""groundcover query-language (gcQL) reference tool."""


from typing import cast

from tools.tool_decorator import tool

_QUERY_REF_SOURCE = "groundcover_query_reference"


def _query_ref_is_available(sources: dict[str, dict]) -> bool:
    """Available when groundcover credentials are present or a fixture backend is injected."""
    return groundcover_available_or_backend(sources)


def _query_ref_extract_params(sources: dict[str, dict]) -> dict[str, Any]:
    """Inject a pre-built client (no time window), never raw credentials."""
    return base_extract_params(sources.get("groundcover", {}), include_period=False)


@tool(
    name="get_groundcover_query_reference",
    display_name="groundcover query reference",
    source="groundcover",
    tags=("observability", "reference"),
    cost_tier="cheap",
    surfaces=("investigation", "chat"),
    description=(
        "Get the groundcover Query Language (gcQL) reference: operators, functions, pipes, and "
        "query patterns. Call this ONCE before writing gcQL for any query_groundcover_* tool. "
        "Reading it first prevents malformed and overly expensive queries."
    ),
    use_cases=[
        "Before composing any non-trivial gcQL query for groundcover logs/traces/metrics/apm",
        "When unsure about stats/sort/filter syntax or pipe operators",
        "To recall the performance and time-window guidance for efficient queries",
    ],
    requires=[],
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
    is_available=_query_ref_is_available,
    extract_params=_query_ref_extract_params,
)
def get_groundcover_query_reference(
    _groundcover_client: GroundcoverClient | None = None,
    groundcover_backend: Any = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Return the cached gcQL reference skill content."""
    if groundcover_backend is not None and hasattr(groundcover_backend, "get_query_reference"):
        return cast("dict[str, Any]", groundcover_backend.get_query_reference())

    if _groundcover_client is None:
        return {
            "source": _QUERY_REF_SOURCE,
            "available": False,
            "reference": "",
            "error": "groundcover integration not configured",
        }
    result = _groundcover_client.get_query_reference()
    if not result.get("success"):
        return {
            "source": _QUERY_REF_SOURCE,
            "available": False,
            "reference": "",
            "error": result.get("error", "could not fetch gcQL reference"),
        }
    return {
        "source": _QUERY_REF_SOURCE,
        "available": True,
        "reference": result.get("reference", ""),
        "cached": result.get("cached", False),
        "error": None,
    }


# ======== from tools/groundcover_traces_tool/ ========

"""groundcover traces query tool (gcQL over query_traces)."""


from tools.tool_decorator import tool
from tools.utils.groundcover import (
    DEFAULT_TRACES_QUERY,
    GCQL_GUIDANCE,
)

_TRACES_SOURCE = "groundcover_traces"
_TRACES_MCP_TOOL = "query_traces"

_TRACES_QUERY_DESCRIPTION = (
    "gcQL query. Lead with the filter directly (not a '| filter' pipe) and include "
    "'| limit N'. Project raw spans with '| fields ...' (a bare select-all '| limit N' is "
    "rejected for traces); otherwise aggregate with '| stats ...'. Examples: "
    "'workload:checkout duration_seconds>0.5 | fields _time, span_name, duration_seconds "
    "| sort by (duration_seconds desc) | limit 50'; "
    "'status_code>=500 | stats by (workload) count() as errors | sort by (errors desc) "
    "| limit 20'; "
    "'span_type:mysql status:error | fields _time, span_name, status_code | limit 50'."
)


def _traces_is_available(sources: dict[str, dict]) -> bool:
    """Available when groundcover credentials are present or a fixture backend is injected."""
    return groundcover_available_or_backend(sources)


def _traces_extract_params(sources: dict[str, dict]) -> dict[str, Any]:
    """Inject a pre-built client + seed query, never raw credentials."""
    return base_extract_params(sources.get("groundcover", {}), default_query=DEFAULT_TRACES_QUERY)


@tool(
    name="query_groundcover_traces",
    display_name="groundcover traces",
    source="groundcover",
    tags=("traces", "observability"),
    cost_tier="moderate",
    description=(
        "Query groundcover traces/spans with gcQL. Use to find slow spans, failing spans, and "
        "request correlations across services. " + GCQL_GUIDANCE + " Discover fields with "
        "'* | field_names'. For traces, free text needs '*:*term*' or 'field:*term*' (no bare "
        "keywords). Error filtering by span type: HTTP spans use 'status_code>=500' (or "
        "'status_code>399'); databases/gRPC/messaging and any span type use 'status:error' "
        "(universal). Never use 'status_code>399' on non-HTTP spans — their codes differ. Key "
        "fields: span_name (endpoint), workload (caller), server (callee), duration_seconds, status."
    ),
    use_cases=[
        "Finding the slowest spans for a workload (sort by duration_seconds desc)",
        "Locating 5xx/erroring spans for a service or endpoint",
        "Aggregating error rate and p95 latency per workload with one stats query",
    ],
    requires=[],
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": _TRACES_QUERY_DESCRIPTION},
            "start": {"type": "string", "description": "RFC3339 start time (optional)"},
            "end": {"type": "string", "description": "RFC3339 end time (optional)"},
            "period": {
                "type": "string",
                "description": "ISO-8601 duration window, e.g. PT1H (default).",
                "default": "PT1H",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    is_available=_traces_is_available,
    extract_params=_traces_extract_params,
)
def query_groundcover_traces(
    query: str = "",
    start: str = "",
    end: str = "",
    period: str = "",
    _groundcover_client: GroundcoverClient | None = None,
    groundcover_backend: Any = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Query groundcover traces/spans with gcQL and return the normalized OpenSRE envelope.

    Credentials never travel through the model-facing arguments: ``extract_params``
    binds a pre-built :class:`GroundcoverClient` into ``_groundcover_client`` (and an
    optional synthetic ``groundcover_backend``), both stripped from seed input by the
    redactor. An empty query yields a cheap guidance envelope with no MCP round trip.
    """
    return run_signal_query(
        source=_TRACES_SOURCE,
        mcp_tool=_TRACES_MCP_TOOL,
        client=_groundcover_client,
        query=query,
        start=start,
        end=end,
        period=period,
        backend=groundcover_backend,
    )


# ======== from tools/groundcover_events_tool/ ========

"""groundcover Kubernetes events query tool (gcQL over query_events)."""


from tools.utils.groundcover import DEFAULT_EVENTS_QUERY

_EVENTS_SOURCE = "groundcover_events"
_EVENTS_MCP_TOOL = "query_events"

_EVENTS_QUERY_DESCRIPTION = (
    "gcQL query. Lead with the filter directly (not a '| filter' pipe) and include "
    "'| limit N'. Project raw rows with '| fields ...' rather than a bare select-all. "
    "Examples: 'type:Warning | fields _time, reason, namespace, message | limit 50'; "
    "'reason:OOMKilled | fields _time, namespace, name, message | limit 50'; "
    "'namespace:production type:Warning | stats by (reason) count() as events "
    "| sort by (events desc) | limit 20'."
)


def _events_is_available(sources: dict[str, dict]) -> bool:
    """Available when groundcover credentials are present or a fixture backend is injected."""
    return groundcover_available_or_backend(sources)


def _events_extract_params(sources: dict[str, dict]) -> dict[str, Any]:
    """Inject a pre-built client + seed query, never raw credentials."""
    return base_extract_params(sources.get("groundcover", {}), default_query=DEFAULT_EVENTS_QUERY)


@tool(
    name="query_groundcover_events",
    display_name="groundcover Kubernetes events",
    source="groundcover",
    tags=("events", "kubernetes", "observability"),
    cost_tier="moderate",
    description=(
        "Query groundcover Kubernetes events with gcQL. Use for warning/lifecycle evidence such "
        "as OOMKilled, CrashLoopBackOff, FailedScheduling, and image pull errors. "
        + GCQL_GUIDANCE
        + " Discover fields with '* | field_names'."
    ),
    use_cases=[
        "Finding Warning events (OOMKilled, FailedScheduling) for a namespace or workload",
        "Confirming pod restarts/evictions around an incident window",
        "Counting events by reason to spot the dominant failure mode",
    ],
    requires=[],
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": _EVENTS_QUERY_DESCRIPTION},
            "start": {"type": "string", "description": "RFC3339 start time (optional)"},
            "end": {"type": "string", "description": "RFC3339 end time (optional)"},
            "period": {
                "type": "string",
                "description": "ISO-8601 duration window, e.g. PT1H (default).",
                "default": "PT1H",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    is_available=_events_is_available,
    extract_params=_events_extract_params,
)
def query_groundcover_events(
    query: str = "",
    start: str = "",
    end: str = "",
    period: str = "",
    _groundcover_client: GroundcoverClient | None = None,
    groundcover_backend: Any = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Query groundcover Kubernetes events with gcQL and return the normalized OpenSRE envelope.

    Credentials never travel through the model-facing arguments: ``extract_params``
    binds a pre-built :class:`GroundcoverClient` into ``_groundcover_client`` (and an
    optional synthetic ``groundcover_backend``), both stripped from seed input by the
    redactor. An empty query yields a cheap guidance envelope with no MCP round trip.
    """
    return run_signal_query(
        source=_EVENTS_SOURCE,
        mcp_tool=_EVENTS_MCP_TOOL,
        client=_groundcover_client,
        query=query,
        start=start,
        end=end,
        period=period,
        backend=groundcover_backend,
    )


# ======== from tools/groundcover_issues_tool/ ========

"""groundcover monitor-issue query tool (gcQL over query_issues)."""


from tools.utils.groundcover import DEFAULT_ISSUES_QUERY

_ISSUES_SOURCE = "groundcover_issues"
_ISSUES_MCP_TOOL = "query_issues"

_ISSUES_QUERY_DESCRIPTION = (
    "gcQL query. Lead with the filter directly (not a '| filter' pipe) and include "
    "'| limit N'. Project raw rows with '| fields ...' rather than a bare select-all. "
    "Examples: 'env:production | fields monitor_name, last_firing_start, severity | limit 50'; "
    "'monitor_name:*cpu* | fields monitor_name, last_firing_start, env | limit 20'; "
    "'silenced:false | stats by (monitor_name) count() as firings | sort by (firings desc) "
    "| limit 20'."
)


def _issues_is_available(sources: dict[str, dict]) -> bool:
    """Available when groundcover credentials are present or a fixture backend is injected."""
    return groundcover_available_or_backend(sources)


def _issues_extract_params(sources: dict[str, dict]) -> dict[str, Any]:
    """Inject a pre-built client + seed query, never raw credentials."""
    return base_extract_params(sources.get("groundcover", {}), default_query=DEFAULT_ISSUES_QUERY)


@tool(
    name="query_groundcover_issues",
    display_name="groundcover monitor issues",
    source="groundcover",
    tags=("monitors", "alerts", "observability"),
    cost_tier="moderate",
    description=(
        "Query groundcover monitor issue instances (active alerts and historical firings) with "
        "gcQL. Use query_groundcover_monitors first to discover monitor definitions/IDs, then "
        "drill into firings here. " + GCQL_GUIDANCE + " Discover fields with '* | field_names'."
    ),
    use_cases=[
        "Listing currently firing or recently fired monitor issues",
        "Finding issues for a specific monitor by name or a namespace",
        "Counting issues grouped by monitor_name to see the noisiest monitors",
    ],
    requires=[],
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": _ISSUES_QUERY_DESCRIPTION},
            "start": {"type": "string", "description": "RFC3339 start time (optional)"},
            "end": {"type": "string", "description": "RFC3339 end time (optional)"},
            "period": {
                "type": "string",
                "description": "ISO-8601 duration window, e.g. PT1H (default).",
                "default": "PT1H",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    is_available=_issues_is_available,
    extract_params=_issues_extract_params,
)
def query_groundcover_issues(
    query: str = "",
    start: str = "",
    end: str = "",
    period: str = "",
    _groundcover_client: GroundcoverClient | None = None,
    groundcover_backend: Any = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Query groundcover monitor issues with gcQL and return the normalized OpenSRE envelope.

    Credentials never travel through the model-facing arguments: ``extract_params``
    binds a pre-built :class:`GroundcoverClient` into ``_groundcover_client`` (and an
    optional synthetic ``groundcover_backend``), both stripped from seed input by the
    redactor. An empty query yields a cheap guidance envelope with no MCP round trip.
    """
    return run_signal_query(
        source=_ISSUES_SOURCE,
        mcp_tool=_ISSUES_MCP_TOOL,
        client=_groundcover_client,
        query=query,
        start=start,
        end=end,
        period=period,
        backend=groundcover_backend,
    )


# ======== from tools/groundcover_apm_tool/ ========

"""groundcover APM measurements query tool (gcQL over query_apm)."""


_APM_SOURCE = "groundcover_apm"
_APM_MCP_TOOL = "query_apm"

_APM_QUERY_DESCRIPTION = (
    "gcQL query. MUST start with 'resource_type:<type>' AND 'is_inbound:true' (or "
    "'is_outbound:true') before any pipe, and include '| limit N'. Disambiguate the data "
    "source with 'source:ebpf' (lead filter) or group by it in stats. Measurement columns "
    "(use inside stats): total_counter, success_counter, error_counter, total_latency_seconds, "
    "latency_seconds_quantiles. Example: "
    "'resource_type:http is_inbound:true source:ebpf | stats by (workload) "
    "sum(total_counter) as requests, sum(error_counter) as errors, "
    "quantile(0.95, latency_seconds_quantiles) as p95_seconds "
    "| math errors / requests * 100 as error_rate keep_existing | sort by (requests desc) "
    "| limit 20'."
)


def _apm_is_available(sources: dict[str, dict]) -> bool:
    """Available when groundcover credentials are present or a fixture backend is injected."""
    return groundcover_available_or_backend(sources)


def _apm_extract_params(sources: dict[str, dict]) -> dict[str, Any]:
    """Inject a pre-built client but no seed query.

    APM requires mandatory ``resource_type:`` + ``is_inbound:``/``is_outbound:`` filters,
    so it cannot be blindly seeded; first-round invocation returns a cheap guidance
    envelope instead of an invalid query.
    """
    return base_extract_params(sources.get("groundcover", {}))


@tool(
    name="query_groundcover_apm",
    display_name="groundcover APM",
    source="groundcover",
    tags=("apm", "metrics", "observability"),
    cost_tier="moderate",
    description=(
        "Query groundcover APM measurements (aggregated request rate, error rate, and latency for "
        "operations observed on the wire: HTTP, gRPC, DB/cache/queue, LLM). Use for golden-signal "
        "aggregates; use query_groundcover_traces for individual spans. EVERY query MUST include "
        "two top-level filters before any pipe: 'resource_type:<type>' (http, grpc, dns, mysql, "
        "postgresql, kafka, redis, mongodb, graphql, s3, sqs, openai, anthropic, bedrock, gen_ai) "
        "AND 'is_inbound:true' OR 'is_outbound:true'. Disambiguate the data source with "
        "'source:ebpf' or by grouping 'stats by (source, ...)'. Measurement columns (use inside "
        "stats): total_counter, success_counter, error_counter, total_latency_seconds, "
        "latency_seconds_quantiles. " + GCQL_GUIDANCE
    ),
    use_cases=[
        "Golden signals per inbound service (requests, errors, p50/p95, error rate)",
        "Error rate of a workload's outbound calls grouped by the called server",
        "Latency regression triage across HTTP/gRPC/DB operations",
    ],
    requires=[],
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": _APM_QUERY_DESCRIPTION},
            "start": {"type": "string", "description": "RFC3339 start time (optional)"},
            "end": {"type": "string", "description": "RFC3339 end time (optional)"},
            "period": {
                "type": "string",
                "description": "ISO-8601 duration window, e.g. PT1H (default).",
                "default": "PT1H",
            },
        },
        "required": [],
        "additionalProperties": False,
    },
    is_available=_apm_is_available,
    extract_params=_apm_extract_params,
)
def query_groundcover_apm(
    query: str = "",
    start: str = "",
    end: str = "",
    period: str = "",
    _groundcover_client: GroundcoverClient | None = None,
    groundcover_backend: Any = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Query groundcover APM measurements with gcQL and return the normalized OpenSRE envelope.

    Credentials never travel through the model-facing arguments: ``extract_params``
    binds a pre-built :class:`GroundcoverClient` into ``_groundcover_client`` (and an
    optional synthetic ``groundcover_backend``), both stripped from seed input by the
    redactor. APM is never blindly seeded — an empty query yields a cheap guidance
    envelope with no MCP round trip.
    """
    return run_signal_query(
        source=_APM_SOURCE,
        mcp_tool=_APM_MCP_TOOL,
        client=_groundcover_client,
        query=query,
        start=start,
        end=end,
        period=period,
        backend=groundcover_backend,
    )


# ======== from tools/groundcover_entities_tool/ ========

"""groundcover live Kubernetes entities query tool (gcQL over query_entities)."""


from tools.utils.groundcover import (
    DEFAULT_ENTITIES_QUERY,
    build_envelope,
    needs_query,
    unavailable,
)

_ENTITIES_SOURCE = "groundcover_entities"

_ENTITIES_QUERY_DESCRIPTION = (
    "gcQL query over live entities (current state, no time window). Lead with the filter "
    "directly and include '| limit N'; project raw rows with '| fields ...' rather than a "
    "bare select-all. Examples: "
    "'kind:Pod status_phase:Running | fields name, namespace, status_phase | limit 100'; "
    "'kind:Deployment | fields name, namespace, ready_replicas | limit 50'; "
    "'kind:Node | stats by (status) count() as nodes | limit 10'."
)


def _entities_is_available(sources: dict[str, dict]) -> bool:
    """Available when groundcover credentials are present or a fixture backend is injected."""
    return groundcover_available_or_backend(sources)


def _entities_extract_params(sources: dict[str, dict]) -> dict[str, Any]:
    """Inject a pre-built client + seed query (no time window), never raw credentials."""
    return base_extract_params(
        sources.get("groundcover", {}),
        default_query=DEFAULT_ENTITIES_QUERY,
        include_period=False,
    )


@tool(
    name="query_groundcover_entities",
    display_name="groundcover Kubernetes entities",
    source="groundcover",
    tags=("kubernetes", "entities", "observability"),
    cost_tier="moderate",
    description=(
        "Query live Kubernetes entity state from groundcover with gcQL (current state, no time "
        "window). Use to inspect Pods, Deployments, Nodes, and their status. Queries operate on "
        "the live state — time parameters do not apply. Discover fields with "
        "'kind:Pod | field_names'. " + GCQL_GUIDANCE
    ),
    use_cases=[
        "Listing running/pending/failed pods in a namespace",
        "Checking Deployment replica readiness",
        "Counting pods/nodes grouped by status",
    ],
    requires=[],
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": _ENTITIES_QUERY_DESCRIPTION},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    is_available=_entities_is_available,
    extract_params=_entities_extract_params,
)
def query_groundcover_entities(
    query: str = "",
    _groundcover_client: GroundcoverClient | None = None,
    groundcover_backend: Any = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Query live groundcover Kubernetes entities with gcQL; entities have no time window.

    Credentials never travel through the model-facing arguments: ``extract_params``
    binds a pre-built :class:`GroundcoverClient` into ``_groundcover_client`` (and an
    optional synthetic ``groundcover_backend``), both stripped from seed input by the
    redactor. An empty query yields a cheap guidance envelope with no MCP round trip.
    """
    if groundcover_backend is not None and hasattr(groundcover_backend, "query_entities"):
        return cast("dict[str, Any]", groundcover_backend.query_entities(query=query))

    if _groundcover_client is None:
        return unavailable(_ENTITIES_SOURCE, "groundcover integration not configured")
    if not query.strip():
        return needs_query(_ENTITIES_SOURCE)

    result = _groundcover_client.call_tool("query_entities", {"query": query})
    return build_envelope(_ENTITIES_SOURCE, query, result, tr={"live": "true"})


# ======== from tools/groundcover_monitors_tool/ ========

"""groundcover monitor-definition query tool (query_monitors)."""


_MONITORS_SOURCE = "groundcover_monitors"


def _monitors_is_available(sources: dict[str, dict]) -> bool:
    """Available when groundcover credentials are present or a fixture backend is injected."""
    return groundcover_available_or_backend(sources)


def _monitors_extract_params(sources: dict[str, dict]) -> dict[str, Any]:
    """Inject a pre-built client (no time window, no seed query), never raw credentials.

    The query is optional for monitors; an empty filter lists all monitor definitions.
    """
    return base_extract_params(sources.get("groundcover", {}), include_period=False)


@tool(
    name="query_groundcover_monitors",
    display_name="groundcover monitors",
    source="groundcover",
    tags=("monitors", "alerts", "observability"),
    cost_tier="cheap",
    description=(
        "List groundcover monitor definitions with their current health status. Use to discover "
        "which monitors exist, check status, or find a monitor by name BEFORE drilling into "
        "active firings with query_groundcover_issues. Filter with a gcQL string; supported "
        "fields: monitor_name, type. Leave the query empty to list all monitors. Do not use this "
        "to retrieve alert instances — use query_groundcover_issues for that."
    ),
    use_cases=[
        "Discovering which monitor fired for an alert and its configured query",
        "Finding a monitor by name before querying its issues",
        "Checking the current health/state of configured monitors",
    ],
    requires=[],
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Optional gcQL filter. Supported fields: monitor_name, type. "
                    "Examples: 'monitor_name:*checkout*'; 'type:prometheus'. Empty lists all."
                ),
            },
        },
        "additionalProperties": False,
    },
    is_available=_monitors_is_available,
    extract_params=_monitors_extract_params,
)
def query_groundcover_monitors(
    query: str = "",
    _groundcover_client: GroundcoverClient | None = None,
    groundcover_backend: Any = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """List groundcover monitor definitions and current health (optional gcQL filter).

    Credentials never travel through the model-facing arguments: ``extract_params``
    binds a pre-built :class:`GroundcoverClient` into ``_groundcover_client`` (and an
    optional synthetic ``groundcover_backend``), both stripped from seed input by the
    redactor. An empty query lists all monitors rather than erroring.
    """
    if groundcover_backend is not None and hasattr(groundcover_backend, "query_monitors"):
        return cast("dict[str, Any]", groundcover_backend.query_monitors(query=query))

    if _groundcover_client is None:
        return unavailable(_MONITORS_SOURCE, "groundcover integration not configured")

    args = {"query": query} if query.strip() else {}
    result = _groundcover_client.call_tool("query_monitors", args)
    return build_envelope(_MONITORS_SOURCE, query, result, tr={})


# ======== from tools/groundcover_metrics_tool/ ========

"""groundcover metrics query tool (query_metrics with discovery + PromQL modes)."""


_METRICS_SOURCE = "groundcover_metrics"
_METRICS_MODES = ("get_names", "get_labels", "query_range", "query_instant")


def _metrics_is_available(sources: dict[str, dict]) -> bool:
    """Available when groundcover credentials are present or a fixture backend is injected."""
    return groundcover_available_or_backend(sources)


def _metrics_extract_params(sources: dict[str, dict]) -> dict[str, Any]:
    """Inject a pre-built client + default period, never raw credentials."""
    return base_extract_params(sources.get("groundcover", {}))


def _metrics_guidance(message: str) -> dict[str, Any]:
    """Cheap guidance envelope returned for an invalid/incomplete mode (no MCP round trip)."""
    return {
        "source": _METRICS_SOURCE,
        "available": True,
        "data": [],
        "summary": {},
        "truncated": False,
        "error": None,
        "notes": [message],
    }


@tool(
    name="query_groundcover_metrics",
    display_name="groundcover metrics",
    source="groundcover",
    tags=("metrics", "promql", "observability"),
    cost_tier="moderate",
    description=(
        "Query groundcover metrics. Discover metrics before running PromQL. Modes: "
        "'get_names' (list metric names, optional filter); 'get_labels' (label keys for a metric, "
        "requires metric_name); 'query_range' (PromQL range query, requires promql + step); "
        "'query_instant' (PromQL at a point, requires promql, uses end only). "
        "Native groundcover metrics use the 'groundcover_' prefix (includes kube-state-metrics) "
        "and carry descriptions/units. Always retrieve metric names first and use exact names. "
        "Keep ranges narrow (<= 24h). Returned timestamps are UTC."
    ),
    use_cases=[
        "Discovering relevant metric names before writing PromQL",
        "Inspecting label keys for a metric to build a selector",
        "Running a PromQL range/instant query for CPU, memory, or request metrics",
    ],
    requires=[],
    input_schema={
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": list(_METRICS_MODES),
                "description": "One of get_names, get_labels, query_range, query_instant.",
            },
            "filter": {"type": "string", "description": "Filter for get_names/get_labels search."},
            "metric_name": {"type": "string", "description": "Metric name (get_labels mode)."},
            "promql": {"type": "string", "description": "PromQL (query_range/query_instant)."},
            "step": {
                "type": "string",
                "description": "Step for query_range, e.g. 1m.",
                "default": "1m",
            },
            "start": {"type": "string", "description": "RFC3339 start (query_range)."},
            "end": {"type": "string", "description": "RFC3339 end / instant timestamp."},
            "period": {
                "type": "string",
                "description": "ISO-8601 window, e.g. PT1H.",
                "default": "PT1H",
            },
            "envs": {"type": "array", "items": {"type": "string"}},
            "clusters": {"type": "array", "items": {"type": "string"}},
            "limit": {"type": "integer", "default": 100},
        },
        "required": [],
        "additionalProperties": False,
    },
    is_available=_metrics_is_available,
    extract_params=_metrics_extract_params,
)
def query_groundcover_metrics(
    mode: str = "",
    filter: str = "",  # noqa: A002 - mirrors the groundcover MCP argument name
    metric_name: str = "",
    promql: str = "",
    step: str = "1m",
    start: str = "",
    end: str = "",
    period: str = "",
    envs: list[str] | None = None,
    clusters: list[str] | None = None,
    limit: int = 100,
    _groundcover_client: GroundcoverClient | None = None,
    groundcover_backend: Any = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Query groundcover metrics across discovery (get_names/get_labels) and PromQL modes.

    Credentials never travel through the model-facing arguments: ``extract_params``
    binds a pre-built :class:`GroundcoverClient` into ``_groundcover_client`` (and an
    optional synthetic ``groundcover_backend``), both stripped from seed input by the
    redactor. Invalid/incomplete modes yield a cheap guidance envelope with no MCP
    round trip.
    """
    if groundcover_backend is not None and hasattr(groundcover_backend, "query_metrics"):
        return cast(
            "dict[str, Any]",
            groundcover_backend.query_metrics(
                mode=mode,
                filter=filter,
                metric_name=metric_name,
                promql=promql,
                step=step,
                start=start,
                end=end,
                period=period,
                envs=envs,
                clusters=clusters,
                limit=limit,
            ),
        )

    if mode not in _METRICS_MODES:
        return _metrics_guidance(
            "Specify a mode: get_names (discover metrics) → get_labels → query_range/query_instant "
            "(PromQL). Start with get_names to find exact metric names."
        )
    if mode == "get_labels" and not metric_name:
        return _metrics_guidance("get_labels requires metric_name. Use get_names first to find it.")
    if mode in ("query_range", "query_instant") and not promql:
        return _metrics_guidance(f"{mode} requires a promql query using a verified metric name.")

    if _groundcover_client is None:
        return unavailable(_METRICS_SOURCE, "groundcover integration not configured")

    args: dict[str, Any] = {"mode": mode, "limit": limit}
    if filter:
        args["filter"] = filter
    if metric_name:
        args["metricName"] = metric_name
    if promql:
        args["promql"] = promql
    if mode == "query_range" and step:
        args["step"] = step
    if start:
        args["start"] = start
    if end:
        args["end"] = end
    if period:
        args["period"] = period
    if envs:
        args["envs"] = envs
    if clusters:
        args["clusters"] = clusters

    result = _groundcover_client.call_tool("query_metrics", args)
    return build_envelope(_METRICS_SOURCE, promql or filter or mode, result, tr={"mode": mode})
