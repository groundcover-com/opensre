"""groundcover Kubernetes events query tool (gcQL over query_events)."""

from __future__ import annotations

from app.tools.utils.groundcover import DEFAULT_EVENTS_QUERY, GCQL_GUIDANCE, make_signal_tool

query_groundcover_events = make_signal_tool(
    name="query_groundcover_events",
    display_name="groundcover Kubernetes events",
    mcp_tool="query_events",
    source="groundcover",
    envelope_source="groundcover_events",
    tags=("events", "kubernetes", "observability"),
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
    query_description=(
        "gcQL query. Start with a filter or '*' and include '| limit N'. Examples: "
        "'* | filter type:Warning | limit 50'; '* | filter reason:OOMKilled | limit 50'; "
        "'* | filter k8s.namespace.name:production type:Warning | stats by (reason) count() "
        "| limit 20'."
    ),
    default_query=DEFAULT_EVENTS_QUERY,
)
query_groundcover_events.__module__ = __name__
