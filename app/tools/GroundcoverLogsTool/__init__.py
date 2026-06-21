"""groundcover logs query tool (gcQL over query_logs)."""

from __future__ import annotations

from app.tools.utils.groundcover import DEFAULT_LOGS_QUERY, GCQL_GUIDANCE, make_signal_tool

query_groundcover_logs = make_signal_tool(
    name="query_groundcover_logs",
    display_name="groundcover logs",
    mcp_tool="query_logs",
    source="groundcover",
    envelope_source="groundcover_logs",
    tags=("logs", "observability"),
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
    query_description=(
        "gcQL query. Lead with the filter directly (not a '| filter' pipe) and include "
        "'| limit N'. Examples: 'level:error | limit 50'; "
        "'workload:checkout level:error | sort by (_time desc) | limit 50'; "
        "'* | stats by (workload) count() if (level:error) as errors | sort by (errors desc) "
        "| limit 20'."
    ),
    default_query=DEFAULT_LOGS_QUERY,
)
# The registry only registers callables whose __module__ matches the scanned
# module; the factory defines the function in utils, so re-home it here.
query_groundcover_logs.__module__ = __name__
