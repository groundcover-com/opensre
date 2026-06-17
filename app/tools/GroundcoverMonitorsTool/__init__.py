"""groundcover monitor-definition query tool (query_monitors)."""

from __future__ import annotations

from typing import Any, cast

from app.services.groundcover import GroundcoverClient
from app.tools.tool_decorator import tool
from app.tools.utils.availability import groundcover_available_or_backend
from app.tools.utils.groundcover import base_extract_params, build_envelope, unavailable

_SOURCE = "groundcover_monitors"


def _is_available(sources: dict[str, dict]) -> bool:
    return groundcover_available_or_backend(sources)


def _extract_params(sources: dict[str, dict]) -> dict[str, Any]:
    # query is optional for monitors; seed lists all monitors. No time window.
    return base_extract_params(sources["groundcover"], include_period=False)


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
    is_available=_is_available,
    extract_params=_extract_params,
)
def query_groundcover_monitors(
    query: str = "",
    _groundcover_client: GroundcoverClient | None = None,
    groundcover_backend: Any = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """List groundcover monitor definitions and current health."""
    if groundcover_backend is not None and hasattr(groundcover_backend, "query_monitors"):
        return cast("dict[str, Any]", groundcover_backend.query_monitors(query=query))

    if _groundcover_client is None:
        return unavailable(_SOURCE, "groundcover integration not configured")

    # query_monitors accepts an optional gcQL filter and no time window.
    args = {"query": query} if query.strip() else {}
    result = _groundcover_client.call_tool("query_monitors", args)
    return build_envelope(_SOURCE, query, result, tr={})
