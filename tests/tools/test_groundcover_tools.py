"""Tests for the groundcover investigation tools (logs/traces/events/issues/apm/
entities/metrics/monitors + query reference)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.services.groundcover.client import GroundcoverToolResult
from app.tools.GroundcoverApmTool import query_groundcover_apm
from app.tools.GroundcoverEntitiesTool import query_groundcover_entities
from app.tools.GroundcoverEventsTool import query_groundcover_events
from app.tools.GroundcoverIssuesTool import query_groundcover_issues
from app.tools.GroundcoverLogsTool import query_groundcover_logs
from app.tools.GroundcoverMetricsTool import query_groundcover_metrics
from app.tools.GroundcoverMonitorsTool import query_groundcover_monitors
from app.tools.GroundcoverQueryReferenceTool import get_groundcover_query_reference
from app.tools.GroundcoverTracesTool import query_groundcover_traces
from tests.tools.conftest import BaseToolContract, mock_agent_state

_CREDS = {"api_key": "tok", "mcp_url": "https://mcp.example.com/api/mcp"}


def _ok(data: Any, notes: list[str] | None = None) -> GroundcoverToolResult:
    return GroundcoverToolResult(
        success=True, tool="t", data=data, text="", notes=notes or [], error=None
    )


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------


class TestLogsContract(BaseToolContract):
    def get_tool_under_test(self) -> Any:
        return query_groundcover_logs.__opensre_registered_tool__


class TestTracesContract(BaseToolContract):
    def get_tool_under_test(self) -> Any:
        return query_groundcover_traces.__opensre_registered_tool__


class TestMetricsContract(BaseToolContract):
    def get_tool_under_test(self) -> Any:
        return query_groundcover_metrics.__opensre_registered_tool__


class TestMonitorsContract(BaseToolContract):
    def get_tool_under_test(self) -> Any:
        return query_groundcover_monitors.__opensre_registered_tool__


class TestReferenceContract(BaseToolContract):
    def get_tool_under_test(self) -> Any:
        return get_groundcover_query_reference.__opensre_registered_tool__


# ---------------------------------------------------------------------------
# Availability + param extraction
# ---------------------------------------------------------------------------


def test_is_available_requires_connection_and_key() -> None:
    rt = query_groundcover_logs.__opensre_registered_tool__
    assert rt.is_available({"groundcover": {"connection_verified": True, "api_key": "k"}}) is True
    assert rt.is_available({"groundcover": {"connection_verified": True}}) is False
    assert rt.is_available({"groundcover": {"_backend": object()}}) is True
    assert rt.is_available({}) is False


def test_extract_params_seeds_default_query() -> None:
    rt = query_groundcover_logs.__opensre_registered_tool__
    params = rt.extract_params(mock_agent_state())
    assert params["api_key"] == "gc_test_token"
    assert "limit" in params["query"]


def test_traces_not_seeded_without_query() -> None:
    rt = query_groundcover_traces.__opensre_registered_tool__
    params = rt.extract_params(mock_agent_state())
    assert "query" not in params  # traces has no blind default seed query


# ---------------------------------------------------------------------------
# Runtime behavior
# ---------------------------------------------------------------------------


def test_logs_unavailable_without_credentials() -> None:
    result = query_groundcover_logs(query="* | limit 10", api_key=None)
    assert result["available"] is False
    assert "not configured" in result["error"]


def test_logs_empty_query_returns_needs_query() -> None:
    result = query_groundcover_logs(query="", **_CREDS)
    assert result["available"] is True
    assert result["data"] == []
    assert result["notes"]


def test_logs_happy_path_envelope() -> None:
    client = MagicMock()
    client.call_tool.return_value = _ok([{"level": "error", "content": "boom"}])
    with patch("app.tools.utils.groundcover.make_client", return_value=client):
        result = query_groundcover_logs(query="* | filter level:error | limit 10", **_CREDS)
    assert result["available"] is True
    assert result["source"] == "groundcover_logs"
    assert result["data"] == [{"level": "error", "content": "boom"}]
    assert result["summary"]["returned"] == 1
    assert result["time_range"]["period"] == "PT1H"
    # the tool passed the gcQL query straight through
    assert client.call_tool.call_args.args[0] == "query_logs"


def test_logs_truncation_note_sets_truncated() -> None:
    client = MagicMock()
    client.call_tool.return_value = _ok([{"a": 1}], notes=["Results truncated at 1 rows."])
    with patch("app.tools.utils.groundcover.make_client", return_value=client):
        result = query_groundcover_logs(query="* | limit 1", **_CREDS)
    assert result["truncated"] is True


def test_logs_upstream_error_envelope() -> None:
    client = MagicMock()
    client.call_tool.return_value = GroundcoverToolResult(
        success=False, tool="query_logs", error="logs query timed out — narrow the time range"
    )
    with patch("app.tools.utils.groundcover.make_client", return_value=client):
        result = query_groundcover_logs(query="* | limit 10", **_CREDS)
    assert result["available"] is False
    assert "narrow the time range" in result["error"]


def test_logs_uses_backend_when_injected() -> None:
    backend = MagicMock()
    backend.query_logs.return_value = {"source": "groundcover_logs", "available": True, "data": []}
    result = query_groundcover_logs(query="* | limit 10", groundcover_backend=backend)
    assert result["available"] is True
    backend.query_logs.assert_called_once()


def test_metrics_requires_mode() -> None:
    result = query_groundcover_metrics(mode="", **_CREDS)
    assert result["available"] is True
    assert "mode" in result["notes"][0].lower()


def test_metrics_get_labels_requires_metric_name() -> None:
    result = query_groundcover_metrics(mode="get_labels", **_CREDS)
    assert "metric_name" in result["notes"][0]


def test_metrics_query_range_requires_promql() -> None:
    result = query_groundcover_metrics(mode="query_range", **_CREDS)
    assert "promql" in result["notes"][0]


def test_metrics_get_names_calls_client() -> None:
    client = MagicMock()
    client.call_tool.return_value = _ok([{"name": "groundcover_cpu"}])
    with patch("app.tools.GroundcoverMetricsTool.make_client", return_value=client):
        result = query_groundcover_metrics(mode="get_names", filter="cpu", **_CREDS)
    assert result["available"] is True
    assert client.call_tool.call_args.args[0] == "query_metrics"
    assert client.call_tool.call_args.args[1]["mode"] == "get_names"


def test_monitors_lists_without_query() -> None:
    client = MagicMock()
    client.call_tool.return_value = _ok([{"name": "cpu-monitor", "state": "ok"}])
    with patch("app.tools.GroundcoverMonitorsTool.make_client", return_value=client):
        result = query_groundcover_monitors(query="", **_CREDS)
    assert result["available"] is True
    assert client.call_tool.call_args.args[1] == {}  # no gcQL filter -> empty args


def test_entities_happy_path() -> None:
    client = MagicMock()
    client.call_tool.return_value = _ok([{"kind": "Pod", "status_phase": "Running"}])
    with patch("app.tools.GroundcoverEntitiesTool.make_client", return_value=client):
        result = query_groundcover_entities(query="kind:Pod | limit 10", **_CREDS)
    assert result["available"] is True
    assert result["time_range"] == {"live": "true"}


def test_apm_happy_path() -> None:
    client = MagicMock()
    client.call_tool.return_value = _ok([{"workload": "api", "requests": 100}])
    with patch("app.tools.utils.groundcover.make_client", return_value=client):
        result = query_groundcover_apm(
            query="resource_type:http is_inbound:true | filter source:ebpf "
            "| stats by (workload) sum(total_counter) as requests | limit 10",
            **_CREDS,
        )
    assert result["available"] is True
    assert client.call_tool.call_args.args[0] == "query_apm"


def test_reference_returns_text() -> None:
    client = MagicMock()
    client.get_query_reference.return_value = {
        "success": True,
        "reference": "# gcQL",
        "cached": False,
    }
    with patch("app.tools.GroundcoverQueryReferenceTool.make_client", return_value=client):
        result = get_groundcover_query_reference(**_CREDS)
    assert result["available"] is True
    assert result["reference"] == "# gcQL"


# ---------------------------------------------------------------------------
# Query-guidance contract (PLAN.md): guidance must be visible in metadata
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tool_func",
    [
        query_groundcover_logs,
        query_groundcover_traces,
        query_groundcover_events,
        query_groundcover_issues,
        query_groundcover_apm,
    ],
)
def test_signal_tool_descriptions_carry_query_guidance(tool_func: Any) -> None:
    rt = tool_func.__opensre_registered_tool__
    desc = rt.description.lower()
    assert "limit n" in desc
    assert "narrow" in desc
    assert "get_groundcover_query_reference" in desc
    # every signal tool requires a query and exposes a time window
    assert "query" in rt.input_schema["properties"]
