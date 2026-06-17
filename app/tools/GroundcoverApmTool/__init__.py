"""groundcover APM measurements query tool (gcQL over query_apm)."""

from __future__ import annotations

from app.tools.utils.groundcover import GCQL_GUIDANCE, make_signal_tool

query_groundcover_apm = make_signal_tool(
    name="query_groundcover_apm",
    display_name="groundcover APM",
    mcp_tool="query_apm",
    source="groundcover",
    envelope_source="groundcover_apm",
    tags=("apm", "metrics", "observability"),
    description=(
        "Query groundcover APM measurements (aggregated request rate, error rate, and latency for "
        "operations observed on the wire: HTTP, gRPC, DB/cache/queue, LLM). Use for golden-signal "
        "aggregates; use query_groundcover_traces for individual spans. "
        "EVERY query MUST include two top-level filters before any pipe: resource_type:<type> "
        "(http, grpc, dns, mysql, postgresql, kafka, redis, mongodb, graphql, s3, sqs, openai, "
        "anthropic, bedrock, gen_ai) AND is_inbound:true OR is_outbound:true. Disambiguate source "
        "with '| filter source:ebpf' or by grouping 'stats by (source, ...)'. Measurement columns "
        "(use inside stats): total_counter, success_counter, error_counter, total_latency_seconds, "
        "latency_seconds_quantiles. " + GCQL_GUIDANCE
    ),
    use_cases=[
        "Golden signals per inbound service (requests, errors, p50/p95, error rate)",
        "Error rate of a workload's outbound calls grouped by the called server",
        "Latency regression triage across HTTP/gRPC/DB operations",
    ],
    query_description=(
        "gcQL query. MUST start with resource_type:<type> and is_inbound:true (or "
        "is_outbound:true), and include '| limit N'. Example: "
        "'resource_type:http is_inbound:true | filter source:ebpf | stats by (workload) "
        "sum(total_counter) as requests, sum(error_counter) as errors, "
        "quantile(0.95, latency_seconds_quantiles) as p95_seconds "
        "| math errors / requests * 100 as error_rate keep_existing | sort by (requests desc) "
        "| limit 20'."
    ),
    default_query=None,
)
query_groundcover_apm.__module__ = __name__
