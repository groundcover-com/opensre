"""Alert-source routing + evidence wiring tests for the groundcover provider."""

from __future__ import annotations

from app.agent.investigation import _ALERT_SOURCE_TO_TOOL_SOURCES as INVESTIGATION_MAP
from app.agent.investigation import _build_seed_calls
from app.agent.prompt import _ALERT_SOURCE_TO_TOOL_SOURCES as PROMPT_MAP
from app.agent.prompt import _build_start_guidance, _group_tools_by_source
from app.cli.investigation.alert_templates import build_alert_template
from app.tools.registry import clear_tool_registry_cache, get_registered_tools
from app.types.evidence import EvidenceSource


def test_groundcover_is_evidence_source() -> None:
    assert "groundcover" in EvidenceSource.__args__  # type: ignore[attr-defined]


def test_groundcover_in_both_routing_maps() -> None:
    assert INVESTIGATION_MAP["groundcover"] == ["groundcover"]
    assert PROMPT_MAP["groundcover"] == ["groundcover"]


def test_alert_template_groundcover() -> None:
    template = build_alert_template("groundcover")
    assert template["alert_source"] == "groundcover"
    assert "groundcover" in template["message"].lower()


def _groundcover_state() -> dict:
    return {
        "alert_source": "groundcover",
        "alert_name": "groundcover monitor: checkout error rate high",
        "resolved_integrations": {
            "groundcover": {
                "connection_verified": True,
                "api_key": "tok",
                "mcp_url": "https://mcp.groundcover.com/api/mcp",
            }
        },
    }


def test_seed_calls_prioritize_groundcover_tools() -> None:
    clear_tool_registry_cache()
    tools = get_registered_tools("investigation")
    seed = _build_seed_calls(_groundcover_state(), tools, llm=object())
    seeded_names = {c.name for c in seed}
    assert seeded_names, "expected groundcover tools to be seeded"
    assert all(name.startswith(("query_groundcover", "get_groundcover")) for name in seeded_names)
    # all groundcover tools should seed (logs/traces/events/issues/apm/entities/
    # metrics/monitors + reference)
    assert "query_groundcover_logs" in seeded_names
    assert "get_groundcover_query_reference" in seeded_names


def test_start_guidance_names_groundcover_primary() -> None:
    clear_tool_registry_cache()
    tools = [t for t in get_registered_tools("investigation") if str(t.source) == "groundcover"]
    grouped = _group_tools_by_source(tools)
    guidance = _build_start_guidance("groundcover", "checkout error rate high", grouped)
    assert "**groundcover** alert" in guidance
    assert "query_groundcover_logs" in guidance
