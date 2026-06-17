"""groundcover live Kubernetes entities query tool (gcQL over query_entities)."""

from __future__ import annotations

from typing import Any, cast

from app.services.groundcover import GroundcoverClient
from app.tools.tool_decorator import tool
from app.tools.utils.availability import groundcover_available_or_backend
from app.tools.utils.groundcover import (
    DEFAULT_ENTITIES_QUERY,
    GCQL_GUIDANCE,
    base_extract_params,
    build_envelope,
    needs_query,
    unavailable,
)

_SOURCE = "groundcover_entities"


def _is_available(sources: dict[str, dict]) -> bool:
    return groundcover_available_or_backend(sources)


def _extract_params(sources: dict[str, dict]) -> dict[str, Any]:
    return base_extract_params(
        sources["groundcover"], default_query=DEFAULT_ENTITIES_QUERY, include_period=False
    )


@tool(
    name="query_groundcover_entities",
    display_name="groundcover Kubernetes entities",
    source="groundcover",
    tags=("kubernetes", "entities", "observability"),
    cost_tier="moderate",
    description=(
        "Query live Kubernetes entity state from groundcover with gcQL (current state, no time "
        "window). Use to inspect Pods, Deployments, Nodes, and their status. "
        "Queries operate on the live state — time parameters do not apply. "
        "Discover fields with 'kind:Pod | field_names'. " + GCQL_GUIDANCE
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
            "query": {
                "type": "string",
                "description": (
                    "gcQL query over live entities. Examples: "
                    "'kind:Pod status_phase:Running | limit 100'; "
                    "'kind:Deployment | fields name, namespace, ready_replicas | limit 50'; "
                    "'kind:Node | stats by (status) count() | limit 10'."
                ),
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    is_available=_is_available,
    extract_params=_extract_params,
)
def query_groundcover_entities(
    query: str = "",
    _groundcover_client: GroundcoverClient | None = None,
    groundcover_backend: Any = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Query live Kubernetes entities; entities have no time window."""
    if groundcover_backend is not None and hasattr(groundcover_backend, "query_entities"):
        return cast("dict[str, Any]", groundcover_backend.query_entities(query=query))

    if _groundcover_client is None:
        return unavailable(_SOURCE, "groundcover integration not configured")
    if not query.strip():
        return needs_query(_SOURCE)

    result = _groundcover_client.call_tool("query_entities", {"query": query})
    return build_envelope(_SOURCE, query, result, tr={"live": "true"})
