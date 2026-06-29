"""Routing and evidence-wiring tests for the groundcover native alert source.

Mirrors the provider routing tests (SigNoz/Datadog/Jenkins/Dagster) but focuses
on the wiring added when ``alert_source: groundcover`` became a first-class
native source:

- groundcover appears in both alert-source → tool-source maps,
- the starter alert template builds and is registered in the CLI choices,
- a ``groundcover`` alert seeds the groundcover tools and the seed inputs pass
  public-schema validation,
- the investigation start-guidance names groundcover,
- the extraction prompt classifies groundcover payloads.

These checks are deterministic (no live planner decisions are stubbed): seeding
is a pure alert-source → tool mapping, so it runs in the default ``make
test-cov`` suite.
"""

from __future__ import annotations

from cli.constants import ALERT_TEMPLATE_CHOICES, SAMPLE_ALERT_OPTIONS
from cli.investigation.alert_templates import build_alert_template
from core.domain.alerts.alert_source import (
    ALERT_SOURCE_TO_SEED_TOOL_SOURCES,
    ALERT_SOURCE_TO_TOOL_SOURCES,
)
from tools.investigation.stages.gather_evidence.prompt import _build_start_guidance
from tools.investigation.stages.gather_evidence.tools import build_seed_calls
from tools.investigation.stages.intake.node import _EXTRACT_PROMPT
from tools.registry import get_registered_tools


def _groundcover_tools() -> list:
    return [t for t in get_registered_tools("investigation") if str(t.source) == "groundcover"]


# ── alert-source maps ────────────────────────────────────────────────────────


def test_groundcover_in_seed_map() -> None:
    """A groundcover alert pre-seeds the groundcover tools before the ReAct loop."""
    assert ALERT_SOURCE_TO_SEED_TOOL_SOURCES.get("groundcover") == ("groundcover",)


def test_groundcover_in_prompt_priority_map() -> None:
    """A groundcover alert treats groundcover as the primary tool source in the prompt."""
    assert ALERT_SOURCE_TO_TOOL_SOURCES.get("groundcover") == ("groundcover",)


# ── starter alert template ───────────────────────────────────────────────────


def test_groundcover_alert_template_builds() -> None:
    template = build_alert_template("groundcover")
    assert template["alert_source"] == "groundcover"
    # The embedded query annotation uses the corrected gcQL idioms: a leading
    # filter (no '| filter' pipe), an explicit projection, and '| limit N'.
    query = template["commonAnnotations"]["query"]
    assert not query.lstrip().startswith("|")
    assert "| filter" not in query
    assert "| fields" in query
    assert "| limit" in query
    assert "status:error" in query


def test_groundcover_registered_in_template_choices() -> None:
    assert "groundcover" in ALERT_TEMPLATE_CHOICES
    assert any(key == "groundcover" for key, _label in SAMPLE_ALERT_OPTIONS)


# ── seeding + public-schema validation ───────────────────────────────────────


def test_groundcover_alert_seeds_groundcover_tools() -> None:
    """``alert_source: groundcover`` seeds exactly the groundcover tools."""
    tools = _groundcover_tools()
    assert tools, "expected groundcover tools to be registered (branch 1)"

    state = {"alert_source": "groundcover"}
    calls = build_seed_calls(state, tools, llm=None)

    seeded_names = {call.name for call in calls}
    assert seeded_names == {t.name for t in tools}


def test_groundcover_seed_inputs_pass_public_schema() -> None:
    """Seed inputs the runtime would submit validate against each tool's public schema."""
    tools = _groundcover_tools()
    by_name = {t.name: t for t in tools}

    calls = build_seed_calls({"alert_source": "groundcover"}, tools, llm=None)
    assert calls

    for call in calls:
        tool = by_name[call.name]
        error = tool.validate_public_input(call.input)
        assert error is None, f"{call.name} seed input rejected: {error}"


# ── start-guidance ───────────────────────────────────────────────────────────


def test_start_guidance_names_groundcover() -> None:
    """The investigation start-guidance points the agent at groundcover first."""
    tools = _groundcover_tools()
    tools_by_source = {"groundcover": tools}

    guidance = _build_start_guidance(
        {"alert_source": "groundcover"},
        "groundcover",
        "groundcover monitor: checkout error rate high",
        tools_by_source,
    )

    assert "groundcover" in guidance
    assert "query_groundcover_logs" in guidance


# ── extraction prompt ────────────────────────────────────────────────────────


def test_extract_prompt_classifies_groundcover() -> None:
    """The extraction prompt resolves groundcover payloads to alert_source groundcover."""
    assert "groundcover" in _EXTRACT_PROMPT
    assert "gcQL" in _EXTRACT_PROMPT
    assert "app.groundcover.com" in _EXTRACT_PROMPT


# ── findings / evidence rendering + brand casing ─────────────────────────────


def test_brand_casing_keeps_groundcover_lowercase() -> None:
    from platform.common.branding import apply_brand_casing

    # A generic humanizer would render "Groundcover"; brand casing restores it.
    assert apply_brand_casing("groundcover".title()) == "groundcover"
    assert apply_brand_casing("Groundcover Logs") == "groundcover Logs"


def test_tool_source_label_renders_groundcover_lowercase() -> None:
    from cli.ui.renderer.tools import _tool_source_label

    assert _tool_source_label("query_groundcover_logs") == "groundcover"


def test_provenance_lines_render_groundcover_lowercase() -> None:
    from tools.investigation.reporting.formatters.report import _format_provenance_lines

    lines = _format_provenance_lines(
        {"source_provenance": {"groundcover": {"summary": "queried checkout logs"}}}
    )
    assert lines == ["• groundcover: queried checkout logs"]


def test_evidence_tool_calls_line_labels_and_links_groundcover() -> None:
    from tools.investigation.reporting.formatters.evidence import _format_tool_calls_line

    line = _format_tool_calls_line(
        {
            "executed_hypotheses": [{"actions": ["query_groundcover_logs"]}],
            "evidence": {},
        }
    )
    assert "groundcover Logs" in line
    assert "https://app.groundcover.com/logs" in line
