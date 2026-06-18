"""Synthetic RCA scenario using groundcover as the evidence source.

Validates that a groundcover alert seeds the right tools and that a fixture
backend yields realistic logs/traces/metrics/apm/events/entities/monitors/issues
evidence through the normal OpenSRE tool envelope — without any network access.
"""

from __future__ import annotations

from typing import Any

from app.agent.investigation import _ALERT_SOURCE_TO_TOOL_SOURCES
from app.tools.GroundcoverApmTool import query_groundcover_apm
from app.tools.GroundcoverEntitiesTool import query_groundcover_entities
from app.tools.GroundcoverEventsTool import query_groundcover_events
from app.tools.GroundcoverIssuesTool import query_groundcover_issues
from app.tools.GroundcoverLogsTool import query_groundcover_logs
from app.tools.GroundcoverMetricsTool import query_groundcover_metrics
from app.tools.GroundcoverMonitorsTool import query_groundcover_monitors
from app.tools.GroundcoverQueryReferenceTool import get_groundcover_query_reference
from app.tools.GroundcoverTracesTool import query_groundcover_traces


def _envelope(source: str, data: list[dict[str, Any]], query: str) -> dict[str, Any]:
    return {
        "source": source,
        "available": True,
        "query": query,
        "time_range": {"period": "PT1H"},
        "data": data,
        "summary": {"returned": len(data)},
        "truncated": False,
        "error": None,
    }


class _FixtureGroundcoverBackend:
    """Realistic, network-free groundcover backend for synthetic scenarios.

    Each method mirrors a groundcover MCP tool and returns a ready OpenSRE
    envelope (the tools short-circuit to the backend when injected).
    """

    def get_query_reference(self) -> dict[str, Any]:
        return {
            "source": "groundcover_query_reference",
            "available": True,
            "reference": "# groundcover gcQL Reference\n<filter> | pipe1 | pipe2 ...",
            "cached": False,
            "error": None,
        }

    def query_logs(self, **kwargs: Any) -> dict[str, Any]:
        return _envelope(
            "groundcover_logs",
            [
                {
                    "_time": "2026-06-17T10:00:00Z",
                    "level": "error",
                    "workload": "checkout",
                    "namespace": "production",
                    "content": "DB connection timeout calling orders-db after 5s",
                },
                {
                    "_time": "2026-06-17T10:00:02Z",
                    "level": "error",
                    "workload": "checkout",
                    "namespace": "production",
                    "content": "upstream 503 from payments-gateway",
                },
            ],
            kwargs.get("query", ""),
        )

    def query_traces(self, **kwargs: Any) -> dict[str, Any]:
        return _envelope(
            "groundcover_traces",
            [
                {
                    "_time": "2026-06-17T10:00:00Z",
                    "trace_id": "abc123",
                    "workload": "checkout",
                    "span_name": "POST /checkout",
                    "duration_seconds": 5.2,
                    "http.status_code": 503,
                    "status": "error",
                }
            ],
            kwargs.get("query", ""),
        )

    def query_metrics(self, **kwargs: Any) -> dict[str, Any]:
        return _envelope(
            "groundcover_metrics",
            [{"metric": "groundcover_container_cpu_usage", "workload": "checkout", "value": 0.94}],
            kwargs.get("promql") or kwargs.get("mode", ""),
        )

    def query_apm(self, **kwargs: Any) -> dict[str, Any]:
        return _envelope(
            "groundcover_apm",
            [
                {
                    "workload": "checkout",
                    "requests": 1200,
                    "errors": 180,
                    "error_rate": 15.0,
                    "p95_seconds": 4.8,
                }
            ],
            kwargs.get("query", ""),
        )

    def query_events(self, **kwargs: Any) -> dict[str, Any]:
        return _envelope(
            "groundcover_events",
            [
                {
                    "_time": "2026-06-17T09:59:00Z",
                    "type": "Warning",
                    "reason": "OOMKilled",
                    "involved_object.name": "checkout-7d9f",
                    "k8s.namespace.name": "production",
                }
            ],
            kwargs.get("query", ""),
        )

    def query_entities(self, **kwargs: Any) -> dict[str, Any]:
        return _envelope(
            "groundcover_entities",
            [{"kind": "Pod", "name": "checkout-7d9f", "status_phase": "Running", "restarts": 4}],
            kwargs.get("query", ""),
        )

    def query_monitors(self, **kwargs: Any) -> dict[str, Any]:
        return _envelope(
            "groundcover_monitors",
            [
                {
                    "name": "checkout-error-rate",
                    "type": "prometheus",
                    "state": "alerting",
                    "monitor_id": "mon-1",
                }
            ],
            kwargs.get("query", ""),
        )

    def query_issues(self, **kwargs: Any) -> dict[str, Any]:
        return _envelope(
            "groundcover_issues",
            [
                {
                    "monitor_name": "checkout-error-rate",
                    "last_firing_start": "2026-06-17T10:00:00Z",
                    "silenced": False,
                    "namespace": "production",
                }
            ],
            kwargs.get("query", ""),
        )


def test_groundcover_alert_source_maps_to_tools() -> None:
    assert _ALERT_SOURCE_TO_TOOL_SOURCES["groundcover"] == ["groundcover"]


def test_logs_scenario() -> None:
    backend = _FixtureGroundcoverBackend()
    result = query_groundcover_logs(
        query="* | filter workload:checkout level:error | limit 50", groundcover_backend=backend
    )
    assert result["available"] is True
    assert result["summary"]["returned"] == 2
    assert "timeout" in result["data"][0]["content"].lower()


def test_traces_scenario() -> None:
    backend = _FixtureGroundcoverBackend()
    result = query_groundcover_traces(query="* | limit 50", groundcover_backend=backend)
    assert result["available"] is True
    assert result["data"][0]["duration_seconds"] == 5.2
    assert result["data"][0]["http.status_code"] == 503


def test_apm_scenario() -> None:
    backend = _FixtureGroundcoverBackend()
    result = query_groundcover_apm(
        query="resource_type:http is_inbound:true | filter source:ebpf "
        "| stats by (workload) sum(total_counter) as requests | limit 20",
        groundcover_backend=backend,
    )
    assert result["available"] is True
    assert result["data"][0]["error_rate"] == 15.0


def test_metrics_scenario() -> None:
    backend = _FixtureGroundcoverBackend()
    result = query_groundcover_metrics(
        mode="query_instant",
        promql="groundcover_container_cpu_usage{workload='checkout'}",
        groundcover_backend=backend,
    )
    assert result["available"] is True
    assert result["data"][0]["value"] == 0.94


def test_events_entities_monitors_issues_scenario() -> None:
    backend = _FixtureGroundcoverBackend()
    events = query_groundcover_events(
        query="* | filter type:Warning | limit 50", groundcover_backend=backend
    )
    entities = query_groundcover_entities(query="kind:Pod | limit 50", groundcover_backend=backend)
    monitors = query_groundcover_monitors(query="", groundcover_backend=backend)
    issues = query_groundcover_issues(query="* | limit 50", groundcover_backend=backend)
    assert events["data"][0]["reason"] == "OOMKilled"
    assert entities["data"][0]["restarts"] == 4
    assert monitors["data"][0]["state"] == "alerting"
    assert issues["data"][0]["monitor_name"] == "checkout-error-rate"


def test_query_reference_scenario() -> None:
    backend = _FixtureGroundcoverBackend()
    result = get_groundcover_query_reference(groundcover_backend=backend)
    assert result["available"] is True
    assert "gcQL" in result["reference"]
