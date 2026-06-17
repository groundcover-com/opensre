"""groundcover metrics query tool (query_metrics with discovery + PromQL modes)."""

from __future__ import annotations

from typing import Any, cast

from app.tools.tool_decorator import tool
from app.tools.utils.availability import groundcover_available_or_backend
from app.tools.utils.groundcover import (
    build_envelope,
    groundcover_creds,
    make_client,
    unavailable,
)

_SOURCE = "groundcover_metrics"
_MODES = ("get_names", "get_labels", "query_range", "query_instant")


def _is_available(sources: dict[str, dict]) -> bool:
    return groundcover_available_or_backend(sources)


def _extract_params(sources: dict[str, dict]) -> dict[str, Any]:
    gc = sources["groundcover"]
    return {"groundcover_backend": gc.get("_backend"), **groundcover_creds(gc)}


def _guidance(message: str) -> dict[str, Any]:
    return {
        "source": _SOURCE,
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
                "enum": list(_MODES),
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
        "required": ["mode"],
    },
    is_available=_is_available,
    extract_params=_extract_params,
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
    api_key: str | None = None,
    mcp_url: str = "",
    tenant_uuid: str = "",
    backend_id: str = "",
    timezone: str = "UTC",
    groundcover_backend: Any = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Query groundcover metrics across discovery and PromQL modes."""
    if groundcover_backend is not None and hasattr(groundcover_backend, "query_metrics"):
        return cast("dict[str, Any]", groundcover_backend.query_metrics(mode=mode, promql=promql))

    if mode not in _MODES:
        return _guidance(
            "Specify a mode: get_names (discover metrics) → get_labels → query_range/query_instant "
            "(PromQL). Start with get_names to find exact metric names."
        )
    if mode == "get_labels" and not metric_name:
        return _guidance("get_labels requires metric_name. Use get_names first to find it.")
    if mode in ("query_range", "query_instant") and not promql:
        return _guidance(f"{mode} requires a promql query using a verified metric name.")

    creds = {
        "api_key": api_key or "",
        "mcp_url": mcp_url,
        "tenant_uuid": tenant_uuid,
        "backend_id": backend_id,
        "timezone": timezone,
    }
    client = make_client(creds)
    if client is None:
        return unavailable(_SOURCE, "groundcover integration not configured")

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

    result = client.call_tool("query_metrics", args)
    envelope = build_envelope(_SOURCE, promql or filter or mode, result, tr={"mode": mode})
    return envelope
