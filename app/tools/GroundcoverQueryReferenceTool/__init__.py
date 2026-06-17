"""groundcover query-language (gcQL) reference tool."""

from __future__ import annotations

from typing import Any, cast

from app.tools.tool_decorator import tool
from app.tools.utils.availability import groundcover_available_or_backend
from app.tools.utils.groundcover import groundcover_creds, make_client

_SOURCE = "groundcover_query_reference"


def _is_available(sources: dict[str, dict]) -> bool:
    return groundcover_available_or_backend(sources)


def _extract_params(sources: dict[str, dict]) -> dict[str, Any]:
    gc = sources["groundcover"]
    return {"groundcover_backend": gc.get("_backend"), **groundcover_creds(gc)}


@tool(
    name="get_groundcover_query_reference",
    display_name="groundcover query reference",
    source="groundcover",
    tags=("observability", "reference"),
    cost_tier="cheap",
    surfaces=("investigation", "chat"),
    description=(
        "Get the groundcover Query Language (gcQL) reference: operators, functions, pipes, and "
        "query patterns. Call this ONCE before writing gcQL for any query_groundcover_* tool. "
        "Reading it first prevents malformed and overly expensive queries."
    ),
    use_cases=[
        "Before composing any non-trivial gcQL query for groundcover logs/traces/metrics/apm",
        "When unsure about stats/sort/filter syntax or pipe operators",
        "To recall the performance and time-window guidance for efficient queries",
    ],
    requires=[],
    input_schema={"type": "object", "properties": {}},
    is_available=_is_available,
    extract_params=_extract_params,
)
def get_groundcover_query_reference(
    api_key: str | None = None,
    mcp_url: str = "",
    tenant_uuid: str = "",
    backend_id: str = "",
    timezone: str = "UTC",
    groundcover_backend: Any = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    """Return the cached gcQL reference skill content."""
    if groundcover_backend is not None and hasattr(groundcover_backend, "get_query_reference"):
        return cast("dict[str, Any]", groundcover_backend.get_query_reference())

    creds = {
        "api_key": api_key or "",
        "mcp_url": mcp_url,
        "tenant_uuid": tenant_uuid,
        "backend_id": backend_id,
        "timezone": timezone,
    }
    client = make_client(creds)
    if client is None:
        return {
            "source": _SOURCE,
            "available": False,
            "reference": "",
            "error": "groundcover integration not configured",
        }
    result = client.get_query_reference()
    if not result.get("success"):
        return {
            "source": _SOURCE,
            "available": False,
            "reference": "",
            "error": result.get("error", "could not fetch gcQL reference"),
        }
    return {
        "source": _SOURCE,
        "available": True,
        "reference": result.get("reference", ""),
        "cached": result.get("cached", False),
        "error": None,
    }
