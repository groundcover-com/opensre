"""groundcover live Kubernetes entities query tool (gcQL over query_entities)."""

from __future__ import annotations

from typing import Any, cast

from app.tools.tool_decorator import tool
from app.tools.utils.availability import groundcover_available_or_backend
from app.tools.utils.groundcover import (
    GCQL_GUIDANCE,
    build_envelope,
    groundcover_creds,
    make_client,
    needs_query,
    unavailable,
)

_SOURCE = "groundcover_entities"


def _is_available(sources: dict[str, dict]) -> bool:
    return groundcover_available_or_backend(sources)


def _extract_params(sources: dict[str, dict]) -> dict[str, Any]:
    gc = sources["groundcover"]
    return {"groundcover_backend": gc.get("_backend"), **groundcover_creds(gc)}


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
    },
    is_available=_is_available,
    extract_params=_extract_params,
)
def query_groundcover_entities(
    query: str = "",
    api_key: str | None = None,
    mcp_url: str = "",
    tenant_uuid: str = "",
    backend_id: str = "",
    timezone: str = "UTC",
    groundcover_backend: Any = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Query live Kubernetes entities; entities have no time window."""
    if groundcover_backend is not None and hasattr(groundcover_backend, "query_entities"):
        return cast("dict[str, Any]", groundcover_backend.query_entities(query=query))

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
    if not query.strip():
        return needs_query(_SOURCE)

    result = client.call_tool("query_entities", {"query": query})
    envelope = build_envelope(_SOURCE, query, result, tr={"live": "true"})
    return envelope
