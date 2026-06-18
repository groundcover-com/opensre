"""Tests for brand-casing of user-facing strings."""

from __future__ import annotations

from app.utils.branding import apply_brand_casing


def test_apply_brand_casing_lowercases_groundcover() -> None:
    assert apply_brand_casing("Groundcover") == "groundcover"
    assert apply_brand_casing("Groundcover Logs") == "groundcover Logs"
    assert apply_brand_casing("Query Groundcover Metrics") == "Query groundcover Metrics"


def test_apply_brand_casing_is_noop_for_others() -> None:
    assert apply_brand_casing("Datadog") == "Datadog"
    assert apply_brand_casing("") == ""


def test_tool_source_label_renders_groundcover_lowercase() -> None:
    from app.cli.support.output import _tool_source_label

    assert _tool_source_label("query_groundcover_logs") == "groundcover"


def test_banner_uses_lowercase_groundcover() -> None:
    from app.cli.interactive_shell.ui.banner import _SERVICE_DISPLAY_NAMES

    assert _SERVICE_DISPLAY_NAMES["groundcover"] == "groundcover"
