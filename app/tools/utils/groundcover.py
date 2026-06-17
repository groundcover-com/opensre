"""Shared helpers for groundcover investigation tools.

All groundcover tools share one client factory, one normalized output envelope,
and one signal-query runner so logs/traces/events/issues/apm stay consistent.
The OpenSRE output envelope is provider-agnostic and never exposes raw MCP
protocol frames to the investigator.

This module lives under ``app/tools/utils`` (skipped by the tool registry) so it
is shared infrastructure, not a registered tool.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from app.services.groundcover import GroundcoverClient, GroundcoverConfig, GroundcoverToolResult

# Default row cap embedded in seed/example queries. The model can override it,
# but every gcQL example must carry an explicit ``| limit N``.
DEFAULT_ROW_LIMIT = 50
# Safety cap applied to rows we put into the prompt envelope, independent of the
# gcQL ``| limit`` the server enforced. Keeps noisy results bounded.
_ENVELOPE_ROW_CAP = 100
_MAX_FIELD_CHARS = 1000

# Default seed queries: cheap, recent, bounded. Used when the alert payload does
# not carry an explicit query. Every one starts with a filter/`*` and limits rows.
DEFAULT_LOGS_QUERY = "* | filter level:error | sort by (_time desc) | limit 50"
DEFAULT_EVENTS_QUERY = "* | filter type:Warning | sort by (_time desc) | limit 50"
DEFAULT_ISSUES_QUERY = "* | sort by (_time desc) | limit 50"


# Reusable query-guidance preamble embedded in every gcQL tool description.
# This is deliberately redundant with the upstream gcQL reference so OpenSRE
# ships efficient query behavior even when the model never calls the reference.
GCQL_GUIDANCE = (
    "Time range is controlled by start/end/period parameters, NOT in the query. "
    "Keep the window as narrow as the question allows: start with the last 1h (default) and "
    "widen only after an empty/inconclusive result. Wide multi-day scans with selective filters "
    "can time out — '| limit N' caps rows RETURNED, not data SCANNED, so for wide ranges prefer "
    "stats/aggregations over raw row pulls. Queries must start with a filter or '*' (never a bare "
    "'|') and must include '| limit N'. Discover fields before guessing. "
    "Call get_groundcover_query_reference once per session before composing non-trivial gcQL."
)


def groundcover_creds(gc: dict[str, Any]) -> dict[str, Any]:
    """Extract the credential subset a GroundcoverClient needs from a source entry."""
    return {
        "api_key": gc.get("api_key", ""),
        "mcp_url": gc.get("mcp_url", ""),
        "tenant_uuid": gc.get("tenant_uuid", ""),
        "backend_id": gc.get("backend_id", ""),
        "timezone": gc.get("timezone", "UTC"),
    }


def make_client(creds: dict[str, Any]) -> GroundcoverClient | None:
    """Build a GroundcoverClient, or None when credentials are missing/invalid."""
    if not creds.get("api_key"):
        return None
    try:
        config = GroundcoverConfig.model_validate(creds)
    except Exception:
        return None
    if not config.is_configured:
        return None
    return GroundcoverClient(config)


def unavailable(source: str, error: str, **extra: Any) -> dict[str, Any]:
    """Standard unavailable envelope (no MCP call was made or it failed)."""
    return {
        "source": source,
        "available": False,
        "data": [],
        "summary": {},
        "truncated": False,
        "error": error,
        **extra,
    }


def needs_query(source: str) -> dict[str, Any]:
    """Cheap envelope returned when a signal tool is invoked without a gcQL query.

    Used so blind first-round seeding of query tools costs nothing: instead of
    issuing an invalid empty query, the tool tells the model how to call it.
    """
    return {
        "source": source,
        "available": True,
        "query": "",
        "data": [],
        "summary": {},
        "truncated": False,
        "error": None,
        "notes": [
            "Provide a gcQL query to run. Call get_groundcover_query_reference first "
            "for syntax, keep the time window narrow (default 1h), and include | limit N."
        ],
    }


def _truncate_value(value: Any) -> Any:
    if isinstance(value, str) and len(value) > _MAX_FIELD_CHARS:
        return value[: _MAX_FIELD_CHARS - 3] + "..."
    return value


def compact_rows(rows: list[Any], limit: int = _ENVELOPE_ROW_CAP) -> tuple[list[Any], bool]:
    """Cap row count and truncate long string fields. Returns (rows, capped)."""
    capped = len(rows) > limit
    out: list[Any] = []
    for row in rows[:limit]:
        if isinstance(row, dict):
            out.append({k: _truncate_value(v) for k, v in row.items()})
        else:
            out.append(_truncate_value(row))
    return out, capped


def time_range(start: str, end: str, period: str) -> dict[str, str]:
    """Echo the requested time window; period defaults to the server default (1h)."""
    return {
        "start": start or "",
        "end": end or "",
        "period": period or ("" if (start and end) else "PT1H"),
    }


def build_envelope(
    source: str,
    query: str,
    result: GroundcoverToolResult,
    *,
    tr: dict[str, str],
) -> dict[str, Any]:
    """Turn a GroundcoverToolResult into the normalized OpenSRE envelope."""
    if not result.success:
        return {
            "source": source,
            "available": False,
            "query": query,
            "time_range": tr,
            "data": [],
            "summary": {},
            "truncated": False,
            "error": result.error or "groundcover query failed",
        }

    data = result.data
    truncated = any("truncat" in note.lower() for note in result.notes)
    summary: dict[str, Any] = {}
    if isinstance(data, list):
        rows, capped = compact_rows(data)
        summary = {"returned": len(rows), "total_in_response": len(data)}
        truncated = truncated or capped
        data_out: Any = rows
    else:
        data_out = data if data is not None else []

    envelope: dict[str, Any] = {
        "source": source,
        "available": True,
        "query": query,
        "time_range": tr,
        "data": data_out,
        "summary": summary,
        "truncated": truncated,
        "error": None,
    }
    if result.notes:
        envelope["notes"] = result.notes
    return envelope


def run_signal_query(
    *,
    source: str,
    mcp_tool: str,
    creds: dict[str, Any],
    query: str,
    start: str = "",
    end: str = "",
    period: str = "",
    backend: Any = None,
    extra_args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Shared runner for gcQL signal tools (logs/traces/events/issues/apm).

    When ``backend`` is provided (synthetic harness), the call short-circuits to
    the fixture backend. Otherwise it runs the MCP tool through the client and
    returns the normalized envelope. An empty query yields a cheap ``needs_query``
    envelope without any MCP round trip.
    """
    if backend is not None:
        method = getattr(backend, mcp_tool, None)
        if callable(method):
            return cast("dict[str, Any]", method(query=query))
        return unavailable(source, f"groundcover backend does not implement {mcp_tool}")

    client = make_client(creds)
    if client is None:
        return unavailable(source, "groundcover integration not configured")
    if not query.strip():
        return needs_query(source)

    args: dict[str, Any] = {"query": query}
    if start:
        args["start"] = start
    if end:
        args["end"] = end
    if period:
        args["period"] = period
    if extra_args:
        args.update(extra_args)

    result = client.call_tool(mcp_tool, args)
    return build_envelope(source, query, result, tr=time_range(start, end, period))


def _creds_from_kwargs(
    api_key: str | None,
    mcp_url: str,
    tenant_uuid: str,
    backend_id: str,
    timezone: str,
) -> dict[str, Any]:
    return {
        "api_key": api_key or "",
        "mcp_url": mcp_url,
        "tenant_uuid": tenant_uuid,
        "backend_id": backend_id,
        "timezone": timezone,
    }


def make_signal_tool(
    *,
    name: str,
    display_name: str,
    mcp_tool: str,
    source: str,
    envelope_source: str,
    description: str,
    use_cases: list[str],
    query_description: str,
    tags: tuple[str, ...],
    default_query: str | None = None,
    cost_tier: str = "moderate",
) -> Callable[..., dict[str, Any]]:
    """Build a registered gcQL signal tool (logs/traces/events/issues).

    These tools all share one shape: a gcQL ``query`` plus start/end/period time
    window, run through one MCP tool, returning the normalized envelope. Tools
    that need bespoke arguments (entities, apm, metrics, monitors) are defined
    explicitly instead.
    """
    # Imported here to avoid importing the tool decorator at module import time
    # for callers that only use the runner/envelope helpers.
    from app.tools.tool_decorator import tool
    from app.tools.utils.availability import groundcover_available_or_backend

    def _is_available(sources: dict[str, dict]) -> bool:
        return groundcover_available_or_backend(sources)

    def _extract_params(sources: dict[str, dict]) -> dict[str, Any]:
        gc = sources["groundcover"]
        params: dict[str, Any] = {
            "period": gc.get("period", "PT1H"),
            "groundcover_backend": gc.get("_backend"),
            **groundcover_creds(gc),
        }
        if default_query is not None:
            params["query"] = gc.get("default_query") or default_query
        return params

    def _run(
        query: str = "",
        start: str = "",
        end: str = "",
        period: str = "",
        api_key: str | None = None,
        mcp_url: str = "",
        tenant_uuid: str = "",
        backend_id: str = "",
        timezone: str = "UTC",
        groundcover_backend: Any = None,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        return run_signal_query(
            source=envelope_source,
            mcp_tool=mcp_tool,
            creds=_creds_from_kwargs(api_key, mcp_url, tenant_uuid, backend_id, timezone),
            query=query,
            start=start,
            end=end,
            period=period,
            backend=groundcover_backend,
        )

    decorated = tool(
        name=name,
        display_name=display_name,
        source=cast("Any", source),
        tags=tags,
        cost_tier=cast("Any", cost_tier),
        description=description,
        use_cases=use_cases,
        requires=[],
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": query_description},
                "start": {"type": "string", "description": "RFC3339 start time (optional)"},
                "end": {"type": "string", "description": "RFC3339 end time (optional)"},
                "period": {
                    "type": "string",
                    "description": "ISO-8601 duration window, e.g. PT1H (default).",
                    "default": "PT1H",
                },
            },
            "required": ["query"],
        },
        is_available=_is_available,
        extract_params=_extract_params,
    )(_run)
    return cast("Callable[..., dict[str, Any]]", decorated)
