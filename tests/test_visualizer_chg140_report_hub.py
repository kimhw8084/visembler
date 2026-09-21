from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "company_ui/products/visualizer/page.py"
ACCEPTANCE = ROOT / "scripts/release_checks/run_chg140_report_hub_acceptance.py"


def test_report_hub_cards_keep_identity_preview_and_resume_primary() -> None:
    source = PAGE.read_text(encoding="utf-8")
    card = source.split("def render_report_card", 1)[1].split("@ui.refreshable\n        def render_cards", 1)[0]
    assert "_report_thumbnail_markup" in card
    assert "StatusBadge" in card
    assert "cui-report-card-primary" in card
    assert "data-report-action=\"open\"" in card
    assert "data-report-action=\"more\"" in card
    assert "ui.input" not in card and "ui.textarea" not in card
    assert 'data-report-action="duplicate"' not in card
    assert 'data-report-action="share"' not in card
    assert 'data-report-action="trash"' not in card


def test_report_hub_uses_governed_progressive_disclosure_and_contextual_history() -> None:
    source = PAGE.read_text(encoding="utf-8")
    assert "ActionMenu" in source
    assert "DetailDrawer('Report history'" in source
    assert "Restore as new revision" in source
    assert "Current r" in source and "data-selected=" in source
    assert "Manage report access" in source
    assert "Person or group" in source
    assert "User or group subject" not in source
    assert "group subject" not in source
    assert "This identifier represents a group" in source
    assert "template_model(template_id)" in source
    assert "REPORT_TEMPLATES.items()" in source


def test_report_hub_responsive_contract_does_not_reintroduce_toolbar_wall() -> None:
    source = PAGE.read_text(encoding="utf-8")
    assert "cui-report-hub-toolbar>*{flex:1 1 100%" not in source
    hub_rule = source.split(".cui-report-hub{", 1)[1].split("}", 1)[0]
    assert "max-width" not in hub_rule and "margin:0 auto" not in hub_rule
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in source
    assert "@media(max-width:420px)" in source


def test_chg140_browser_receipt_exercises_negative_defect_controls() -> None:
    source = ACCEPTANCE.read_text(encoding="utf-8")
    for label in (
        "desktop hierarchy and content preview",
        "long title and description containment",
        "progressive disclosure and focus return",
        "human-facing sharing surface",
        "focused history current-versus-selected review",
        "supported blueprint creation",
        "empty search and recovery",
        "trash consequence and recovery",
        "viewer read-only governance and rendered state",
        "200-percent-equivalent mobile geometry",
    ):
        assert label in source
    assert "card.locator('input,textarea').count() == 0" in source
    assert "document.documentElement.scrollWidth" in source
    assert "Manage access" in source and "Move to trash" in source
    assert "Current r" in source and "data-selected" in source
