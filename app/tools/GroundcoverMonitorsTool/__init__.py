"""groundcover monitor-definition query tool (query_monitors)."""

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

_SOURCE = "groundcover_monitors"


def _is_available(sources: dict[str, dict]) -> bool:
    return groundcover_available_or_backend(sources)


def _extract_params(sources: dict[str, dict]) -> dict[str, Any]:
    gc = sources["groundcover"]
    return {"query": "", "groundcover_backend": gc.get("_backend"), **groundcover_creds(gc)}


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
    },
    is_available=_is_available,
    extract_params=_extract_params,
)
def query_groundcover_monitors(
    query: str = "",
    api_key: str | None = None,
    mcp_url: str = "",
    tenant_uuid: str = "",
    backend_id: str = "",
    timezone: str = "UTC",
    groundcover_backend: Any = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """List groundcover monitor definitions and current health."""
    if groundcover_backend is not None and hasattr(groundcover_backend, "query_monitors"):
        return cast("dict[str, Any]", groundcover_backend.query_monitors(query=query))

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

    # query_monitors accepts an optional gcQL filter and no time window.
    args = {"query": query} if query.strip() else {}
    result = client.call_tool("query_monitors", args)
    return build_envelope(_SOURCE, query, result, tr={})
