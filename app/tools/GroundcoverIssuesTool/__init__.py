"""groundcover monitor-issue query tool (gcQL over query_issues)."""

from __future__ import annotations

from app.tools.utils.groundcover import DEFAULT_ISSUES_QUERY, GCQL_GUIDANCE, make_signal_tool

query_groundcover_issues = make_signal_tool(
    name="query_groundcover_issues",
    display_name="groundcover monitor issues",
    mcp_tool="query_issues",
    source="groundcover",
    envelope_source="groundcover_issues",
    tags=("monitors", "alerts", "observability"),
    description=(
        "Query groundcover monitor issue instances (active alerts and historical firings) with "
        "gcQL. Use query_groundcover_monitors first to discover monitor definitions/IDs, then "
        "drill into firings here. " + GCQL_GUIDANCE + " Use '* | field_names' to discover fields."
    ),
    use_cases=[
        "Listing currently firing or recently fired monitor issues",
        "Finding issues for a specific monitor by name or a namespace",
        "Counting issues grouped by monitor_name to see the noisiest monitors",
    ],
    query_description=(
        "gcQL query. Start with a filter or '*' and include '| limit N'. Examples: "
        "'* | filter env:production | limit 50'; "
        "'* | filter monitor_name:*cpu* | sort by (last_firing_start desc) | limit 20'; "
        "'* | filter silenced:false | stats by (monitor_name) count() | limit 20'."
    ),
    default_query=DEFAULT_ISSUES_QUERY,
)
query_groundcover_issues.__module__ = __name__
