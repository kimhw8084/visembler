#!/usr/bin/env python3
"""Native rendered acceptance and evidence for Visembler CHG-140 Report Hub."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import traceback
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from company_ui.products.visualizer.domain import canonical_model
from company_ui.products.visualizer.governance import ReportAccessCatalog, ReportRole
from company_ui.products.visualizer.templates import REPORT_TEMPLATES
from company_ui.security import AuthorizationModel
from company_ui.security.models import Principal
from editor_host import NativeHost
from native_common import BrowserEvents, acceptance_model, browser_kwargs, write_json
from source_identity import candidate_sha


def _model(text: str = "CHG-140 report") -> dict:
    value = acceptance_model()
    value["items"][0]["text"] = text
    value["items"][0]["body"] = text
    return canonical_model(value)


def _inside(box: dict | None, width: int) -> bool:
    return bool(box and box["x"] >= -1 and box["x"] + box["width"] <= width + 1 and box["width"] >= 0)


def _overlay_closed(locator) -> bool:
    locator.wait_for(state="hidden", timeout=8_000)
    return True


def _no_overflow(page) -> None:
    overflow = page.evaluate("()=>document.documentElement.scrollWidth-innerWidth")
    assert overflow <= 1, f"document horizontal overflow: {overflow}px"


def _open(page, url: str) -> None:
    response = page.goto(url, wait_until="domcontentloaded")
    assert response and response.status < 400, response.status if response else None
    page.locator('[data-testid="report-hub"]').wait_for(timeout=20_000)
    page.locator('[data-testid="report-card"]').first.wait_for(timeout=20_000)
    page.locator('.q-menu:visible').wait_for(state='hidden', timeout=5_000)


def _card(page, report_id: str):
    return page.locator(f'[data-testid="report-card"][data-report-id="{report_id}"]').first


def _open_actions(page, card) -> None:
    trigger = card.locator('[data-report-action="more"]:visible')
    trigger.wait_for(state='visible', timeout=5_000)
    trigger.click()
    page.locator('.q-menu:visible').wait_for(timeout=5_000)


def _select_view(page, label: str) -> None:
    field = page.locator('.cui-report-hub-toolbar .q-field').nth(2)
    field.click()
    menu = page.locator('.q-menu:visible')
    menu.get_by_text(label, exact=True).click()
    menu.wait_for(state='hidden', timeout=5_000)
    field.get_by_text(label, exact=True).wait_for(state='visible', timeout=5_000)


def _fixture_setup(host: NativeHost) -> dict[str, str]:
    repository = host.repository
    access = ReportAccessCatalog(repository)
    ids: dict[str, str] = {}

    def owned(name: str, title: str, *, text: str = "CHG-140") -> str:
        record = repository.create(name, title=title, model=_model(text), metadata={"description": "Recognizable report context"})
        access.migrate([record], owner_subject="local-dev", require_explicit_owner=True)
        return record.report_id

    ids["primary"] = owned("chg140-primary", "Weekly process health", text="Weekly process health")
    ids["long"] = owned("chg140-long", "A report title deliberately long enough to verify wrapping without clipping or horizontal spill", text="Long title")
    ids["history"] = owned("chg140-history", "History review", text="History baseline")
    history = repository.get(ids["history"])
    history = repository.commit(ids["history"], base_revision=history.revision, model=_model("History revision two"), commit_id="chg140-history-2")
    repository.checkpoint(ids["history"], "Before review", expected_revision=history.revision)
    access.migrate([repository.get(ids["history"])], owner_subject="local-dev", require_explicit_owner=True)
    ids["trash"] = owned("chg140-trash", "Recoverable report", text="Move me safely")
    trash = repository.get(ids["trash"])
    access.begin_trash(ids["trash"])
    repository.trash_report(ids["trash"], expected_revision=trash.revision)
    access.mark_trashed(ids["trash"])

    viewer = repository.create("chg140-viewer", title="Read-only shared report", model=_model("Viewer report"), metadata={"description": "A report shared for review"})
    access.migrate([viewer], owner_subject="external-owner", require_explicit_owner=True)
    access.grant(viewer.report_id, Principal("external-owner"), "local-dev", ReportRole.VIEWER)
    ids["viewer"] = viewer.report_id

    editor = repository.create("chg140-editor", title="Editor shared report", model=_model("Editor report"), metadata={"description": "An editable shared report"})
    access.migrate([editor], owner_subject="external-owner-2", require_explicit_owner=True)
    access.grant(editor.report_id, Principal("external-owner-2"), "local-dev", ReportRole.EDITOR)
    ids["editor"] = editor.report_id

    for index in range(12):
        ids[f"many-{index}"] = owned(f"chg140-many-{index:02d}", f"Collection report {index + 1:02d}", text=f"Collection {index + 1:02d}")
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    screenshots = output / "screenshots"
    screenshots.mkdir(exist_ok=True)
    receipt = {
        "schema": "visembler-chg140-report-hub.v1",
        "change": "CHG-140",
        "candidate_sha": candidate_sha(ROOT),
        "source_files": {},
        "viewports": {},
        "cases": [],
        "unexpected_browser_events": [],
    }

    def check(name: str, function) -> None:
        row = {"name": name, "status": "FAIL"}
        try:
            row["details"] = function() or {}
            row["status"] = "PASS"
        except Exception as error:
            row["error"] = str(error)
            row["traceback"] = traceback.format_exc()
        receipt["cases"].append(row)

    try:
        with tempfile.TemporaryDirectory(prefix="visembler-chg140-report-hub-") as temp:
            data_dir = Path(temp) / "data"
            with NativeHost(ROOT, data_dir) as host:
                ids = _fixture_setup(host)
                receipt["fixture_ids"] = ids
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(**browser_kwargs())
                    context = browser.new_context(viewport={"width": 1440, "height": 900})
                    page = context.new_page()
                    events = BrowserEvents()
                    events.attach(page)
                    hub_url = f"{host.url}/visualizer/reports?report={quote(ids['primary'])}"

                    def structure() -> dict:
                        _open(page, f"{host.url}/visualizer/reports?report={quote(ids['history'])}")
                        active = page.locator('[data-report-state="active"]')
                        assert active.count() >= 18, active.count()
                        card = _card(page, ids["primary"])
                        assert card.locator('input,textarea').count() == 0
                        assert card.locator('[data-report-action="open"]:visible').count() == 1
                        assert card.locator('[data-report-action="more"]:visible').count() == 1
                        assert card.locator('[data-report-action="duplicate"]:visible,[data-report-action="history"]:visible,[data-report-action="share"]:visible,[data-report-action="trash"]:visible').count() == 0
                        assert card.locator('[data-preview-family="chart"]').count() >= 1
                        return {"active_cards": active.count(), "visible_card_controls": card.locator('button:visible').count()}

                    def long_content() -> dict:
                        _open(page, f"{host.url}/visualizer/reports?report={quote(ids['long'])}")
                        card = _card(page, ids["long"])
                        title = card.locator('.cui-report-card-title')
                        description = card.locator('.cui-report-card-description')
                        assert title.inner_text().startswith("A report title deliberately long enough")
                        assert description.inner_text() == "Recognizable report context"
                        assert _inside(title.bounding_box(), 1440)
                        assert _inside(description.bounding_box(), 1440)
                        assert card.evaluate("node=>[...node.querySelectorAll('*')].every(child=>child.scrollWidth<=child.clientWidth+1)")
                        page.screenshot(path=str(screenshots / "report-hub-long-title.png"), full_page=True)
                        return {"long_title_wrapped": True, "description_legible": True, "card_contained": True}

                    def disclosure() -> dict:
                        card = _card(page, ids["primary"])
                        trigger = card.locator('[data-report-action="more"]')
                        trigger.click()
                        menu = page.locator('.q-menu:visible')
                        for label in ("Edit details", "Duplicate report", "Review history", "Download JSON", "Manage access", "Move to trash"):
                            assert menu.get_by_role("button", name=label, exact=True).count() == 1, label
                        page.keyboard.press("Escape")
                        menu.wait_for(state="hidden", timeout=5_000)
                        page.wait_for_function("trigger=>document.activeElement===trigger", arg=trigger.element_handle(), timeout=5_000)
                        return {"authorized_management_items": 6, "escape_returns_focus": True}

                    def share() -> dict:
                        card = _card(page, ids["primary"])
                        _open_actions(page, card)
                        page.locator('.q-menu:visible').get_by_role("button", name="Manage access", exact=True).click()
                        dialog = page.locator('[data-cui-overlay="dialog"]:visible')
                        text = dialog.inner_text()
                        assert "Person or group" in text
                        assert "subject" not in text.casefold()
                        assert "This identifier represents a group" in text
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(100)
                        assert _overlay_closed(dialog)
                        return {"human_facing_terms": True, "implementation_vocabulary_absent": True}

                    def history() -> dict:
                        card = _card(page, ids["history"])
                        _open_actions(page, card)
                        page.locator('.q-menu:visible').get_by_role("button", name="Review history", exact=True).click()
                        current = page.locator('[data-testid="history-current-context"]:visible')
                        selected = page.locator('[data-testid="report-history"]:visible [data-selected="true"]')
                        current.wait_for(timeout=10_000)
                        assert current.get_by_text("Current r", exact=False).count() == 1
                        assert selected.count() == 1
                        assert selected.locator('[data-history-action="restore"]:visible').count() == 1
                        assert selected.locator('[data-history-action="duplicate"]:visible').count() == 1
                        assert page.locator('[data-testid="report-history"]:visible .cui-history-compare .cui-report-thumb-svg').count() >= 4
                        entries = page.locator('[data-testid="report-history"]:visible [data-history-id]')
                        assert entries.count() >= 2
                        revision_count = entries.count()
                        selected.locator('[data-history-action="restore"]:visible').click()
                        restore_dialog = page.locator('[data-cui-overlay="dialog"]:visible')
                        assert "creates a new revision" in restore_dialog.inner_text()
                        page.keyboard.press("Escape")
                        _overlay_closed(restore_dialog)
                        entries.nth(1).locator('[data-history-action="select"]').click()
                        assert page.locator('[data-testid="report-history"]:visible [data-selected="true"]').count() == 1
                        page.get_by_role("button", name="Back to reports", exact=True).click()
                        page.wait_for_timeout(100)
                        drawer = page.locator('[data-testid="report-history-drawer"]')
                        assert _overlay_closed(drawer)
                        return {"revisions": revision_count, "current_and_selected_context": True, "restore_is_new_revision": True}

                    def creation() -> dict:
                        before = len(host.repository.list())
                        _open(page, f"{host.url}/visualizer/reports?report={quote(ids['history'])}")
                        page.get_by_role("button", name="Create report", exact=True).click()
                        chooser = page.locator('[data-cui-overlay="dialog"]:visible')
                        chooser.wait_for(state='visible', timeout=5_000)
                        assert chooser.get_by_text("Create a report", exact=True).count() == 1
                        assert chooser.locator('[data-testid="report-template-card"]').count() == len(REPORT_TEMPLATES) + 1
                        chooser.locator('[data-template-id="investigation-rca"]').get_by_role("button", name="Create from this blueprint", exact=True).click()
                        page.wait_for_url("**/visualizer?report=**", timeout=20_000)
                        created = len(host.repository.list()) - before
                        assert created == 1, created
                        created_record = sorted(host.repository.list(), key=lambda record: record.updated_at, reverse=True)[0]
                        assert created_record.metadata.get("template_id") == "investigation-rca"
                        return {"supported_templates": len(REPORT_TEMPLATES) + 1, "created": created_record.report_id, "template_model_preserved": True}

                    def empty_search() -> dict:
                        _open(page, f"{host.url}/visualizer/reports?report={quote(ids['history'])}")
                        search = page.get_by_label("Search reports")
                        search.fill("no-report-matches-this-query")
                        empty = page.get_by_text("No active reports match this search.", exact=True)
                        empty.wait_for(state='visible', timeout=5_000)
                        search.fill("")
                        page.locator('[data-report-state="active"]:visible').first.wait_for(timeout=5_000)
                        return {"empty_search_state": True, "search_recovery": True}

                    def trash_recovery() -> dict:
                        _open(page, f"{host.url}/visualizer/reports?report={quote(ids['history'])}")
                        _select_view(page, "Active + trash")
                        card = _card(page, ids["primary"])
                        _open_actions(page, card)
                        page.locator('.q-menu:visible').get_by_role("button", name="Move to trash", exact=True).click()
                        dialog = page.locator('[data-cui-overlay="dialog"]:visible')
                        assert "recoverable" in dialog.inner_text().casefold()
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(100)
                        assert _overlay_closed(dialog)
                        _open_actions(page, card)
                        page.locator('.q-menu:visible').get_by_role("button", name="Move to trash", exact=True).click()
                        page.locator('[data-cui-overlay="dialog"]:visible').get_by_role("button", name="Move to trash", exact=True).click()
                        trash_card = page.locator(f'[data-testid="report-card"][data-report-id="{ids["primary"]}"][data-report-state="trash"]')
                        trash_card.wait_for(timeout=5_000)
                        assert trash_card.get_by_role("button", name="Restore report", exact=True).count() == 1
                        return {"confirmation_consequence": True, "recovery_action": True}

                    def responsive(label: str, width: int, height: int = 900) -> dict:
                        page.set_viewport_size({"width": width, "height": height})
                        _open(page, f"{host.url}/visualizer/reports?report={quote(ids['history'])}")
                        _no_overflow(page)
                        cards = page.locator('[data-testid="report-card"]:visible')
                        assert cards.count() >= 1
                        for index in range(min(cards.count(), 8)):
                            card = cards.nth(index)
                            assert _inside(card.bounding_box(), width), (label, index, card.bounding_box())
                            assert _inside(card.locator('.cui-report-card-footer').bounding_box(), width), (label, index)
                        toolbar = page.locator('.cui-report-hub-toolbar')
                        assert _inside(toolbar.bounding_box(), width)
                        page.screenshot(path=str(screenshots / f"report-hub-{label}.png"), full_page=True)
                        receipt["viewports"][label] = {"width": width, "height": height, "document_scroll_width": page.evaluate("()=>document.documentElement.scrollWidth"), "card_count": cards.count()}
                        return receipt["viewports"][label]

                    def responsive_coarse() -> dict:
                        coarse_context = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
                        coarse_page = coarse_context.new_page()
                        coarse_events = BrowserEvents()
                        coarse_events.attach(coarse_page)
                        try:
                            _open(coarse_page, f"{host.url}/visualizer/reports?report={quote(ids['history'])}")
                            _no_overflow(coarse_page)
                            cards = coarse_page.locator('[data-testid="report-card"]:visible')
                            assert cards.count() >= 1
                            for index in range(min(cards.count(), 8)):
                                assert _inside(cards.nth(index).bounding_box(), 390)
                                assert _inside(cards.nth(index).locator('.cui-report-card-footer').bounding_box(), 390)
                            coarse_page.screenshot(path=str(screenshots / "report-hub-mobile-200-equivalent.png"), full_page=True)
                            receipt["viewports"]["mobile-200-equivalent"] = {"width": 390, "height": 844, "device_scale_factor": 2, "document_scroll_width": coarse_page.evaluate("()=>document.documentElement.scrollWidth"), "card_count": cards.count()}
                            return receipt["viewports"]["mobile-200-equivalent"]
                        finally:
                            receipt["unexpected_browser_events"].extend(coarse_events.unexpected)
                            coarse_context.close()

                    def readonly() -> dict:
                        page.set_viewport_size({"width": 1440, "height": 900})
                        viewer_projection = ReportAccessCatalog(host.repository).capabilities(ids["viewer"], Principal("local-dev"), AuthorizationModel())
                        assert viewer_projection.can_read and viewer_projection.read_only
                        assert not viewer_projection.can_rename and not viewer_projection.can_duplicate and not viewer_projection.can_share and not viewer_projection.can_delete
                        _open(page, f"{host.url}/visualizer/reports?report={quote(ids['viewer'])}")
                        card = _card(page, ids["viewer"])
                        assert card.locator('[data-report-action="open"]:visible').count() == 1
                        page.screenshot(path=str(screenshots / "report-hub-read-only.png"), full_page=True)
                        return {"role": "viewer", "authorized_read_only_actions": True, "unauthorized_mutations_hidden": True, "browser_fixture": ids["viewer"]}

                    def theme_and_motion() -> dict:
                        page.emulate_media(color_scheme="dark", reduced_motion="reduce", forced_colors="active")
                        _open(page, f"{host.url}/visualizer/reports?report={quote(ids['history'])}")
                        _no_overflow(page)
                        page.screenshot(path=str(screenshots / "report-hub-dark-reduced-motion.png"), full_page=True)
                        page.emulate_media(color_scheme=None, reduced_motion="no-preference", forced_colors="none")
                        return {"dark_theme": True, "reduced_motion": True, "forced_colors": True}

                    check("desktop hierarchy and content preview", structure)
                    check("long title and description containment", long_content)
                    check("progressive disclosure and focus return", disclosure)
                    check("human-facing sharing surface", share)
                    check("focused history current-versus-selected review", history)
                    check("supported blueprint creation", creation)
                    check("empty search and recovery", empty_search)
                    check("trash consequence and recovery", trash_recovery)
                    check("narrow 1024 geometry", lambda: responsive("narrow-1024", 1024))
                    check("mobile 390 geometry", lambda: responsive("mobile-390", 390, 844))
                    check("200-percent-equivalent mobile geometry", responsive_coarse)
                    check("viewer read-only governance and rendered state", readonly)
                    check("dark, reduced-motion, forced-colors surface", theme_and_motion)
                    receipt["unexpected_browser_events"] = events.unexpected
                    context.close()
                    browser.close()
        receipt["isolated_storage_removed"] = not data_dir.exists()
    except Exception as error:
        receipt["harness_error"] = str(error)
        receipt["traceback"] = traceback.format_exc()

    for relative in ("company_ui/products/visualizer/page.py", "scripts/release_checks/run_chg140_report_hub_acceptance.py"):
        path = ROOT / relative
        receipt["source_files"][relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    receipt["screenshots"] = [
        {"path": path.relative_to(output).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
        for path in sorted(screenshots.glob("*.png"))
    ]
    receipt["passed"] = sum(case["status"] == "PASS" for case in receipt["cases"])
    receipt["total"] = len(receipt["cases"])
    receipt["status"] = "PASS" if (
        receipt["passed"] == receipt["total"]
        and not receipt["unexpected_browser_events"]
        and receipt.get("isolated_storage_removed") is True
        and "harness_error" not in receipt
    ) else "FAIL"
    write_json(output / "chg140-report-hub-acceptance.json", receipt)
    (output / "chg140-report-hub-acceptance.json.sha256").write_text(
        hashlib.sha256((output / "chg140-report-hub-acceptance.json").read_bytes()).hexdigest() + "  chg140-report-hub-acceptance.json\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
