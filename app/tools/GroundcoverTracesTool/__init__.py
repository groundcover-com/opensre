"""groundcover traces query tool (gcQL over query_traces)."""

from __future__ import annotations

from app.tools.utils.groundcover import DEFAULT_TRACES_QUERY, GCQL_GUIDANCE, make_signal_tool

query_groundcover_traces = make_signal_tool(
    name="query_groundcover_traces",
    display_name="groundcover traces",
    mcp_tool="query_traces",
    source="groundcover",
    envelope_source="groundcover_traces",
    tags=("traces", "observability"),
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
    query_description=(
        "gcQL query. Lead with the filter directly (not a '| filter' pipe) and include "
        "'| limit N'. Examples: "
        "'workload:checkout duration_seconds>0.5 | sort by (duration_seconds desc) | limit 50'; "
        "'status_code>=500 | stats by (workload) count() as errors | sort by (errors desc) "
        "| limit 20'; 'span_type:mysql status:error | limit 50'."
    ),
    default_query=DEFAULT_TRACES_QUERY,
)
query_groundcover_traces.__module__ = __name__
