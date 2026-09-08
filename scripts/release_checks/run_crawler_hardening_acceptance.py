#!/usr/bin/env python3
"""Targeted native proof for exhaustive-crawler lifecycle and interactions."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import traceback
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from playwright.sync_api import sync_playwright

from company_ui.products.visualizer.domain import canonical_model
from crawler_runtime import CrawlerReportManager
from editor_host import NativeHost
from native_common import BrowserEvents, acceptance_model, browser_kwargs, ready, text_model, write_json


def diagram_model() -> dict:
    return canonical_model({
        "schema_version": 1,
        "items": [{
            "id": "c1", "type": "diagram", "engine": "DiagramEngine", "element": "Process Flow",
            "title": "Process Flow", "nodes": ["Detect", "Analyze", "Release"],
            "edges": [{"from": 0, "to": 1, "label": "inspect"}, {"from": 1, "to": 2, "label": "pass"}],
            "direction": "right", "order": 0, "locked": False, "z": 1,
        }],
        "groups": {}, "datasets": [], "mode": "smart", "layoutPreset": "editorial",
        "crossFilter": None, "canvas": {"width": 1600, "height": 900}, "nextId": 2,
    })


def chart_model() -> dict:
    return canonical_model({
        "schema_version": 1,
        "items": [{
            "id": "c1", "type": "chart", "engine": "CoreChartEngine", "element": "Line Chart",
            "title": "Line Chart", "data": [["W1", 82], ["W2", 86], ["W3", 84]],
            "order": 0, "locked": False, "z": 1,
        }],
        "groups": {}, "datasets": [], "mode": "smart", "layoutPreset": "editorial",
        "crossFilter": None, "canvas": {"width": 1600, "height": 900}, "nextId": 2,
    })


def _inside_viewport(locator, width: int) -> bool:
    box = locator.bounding_box()
    return bool(box and box["x"] >= 0 and box["x"] + box["width"] <= width and box["y"] >= 0)


def _no_page_overflow(page) -> None:
    overflow = page.evaluate("()=>document.documentElement.scrollWidth-innerWidth")
    assert overflow <= 1, overflow


def _open(page, url: str, ready_selector: str) -> None:
    response = page.goto(url, wait_until="domcontentloaded")
    assert response and response.status < 400, response.status if response else None
    page.locator(ready_selector).wait_for(timeout=20_000)
    page.wait_for_timeout(120)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    shots = output / "screenshots"
    shots.mkdir(exist_ok=True)
    receipt = {"scope": "crawler hardening targeted acceptance", "cases": [], "unexpected_errors": []}

    def check(name: str, function) -> None:
        row = {"name": name, "status": "FAIL"}
        try:
            function()
            row["status"] = "PASS"
        except Exception as error:
            row["error"] = str(error)
            row["traceback"] = traceback.format_exc()
        receipt["cases"].append(row)

    try:
        with tempfile.TemporaryDirectory(prefix="visembler-crawler-hardening-") as temp:
            data_dir = Path(temp) / "data"
            with NativeHost(ROOT, data_dir) as host:
                with CrawlerReportManager(host, run_id="targeted", max_existing=12) as fixtures:
                    hub_ids = [fixtures.reset(acceptance_model(), f"hub-{index:02d}") for index in range(8)]
                    mutable = fixtures.reset(text_model("initial"), "mutable")
                    for index in range(40):
                        fixtures.reset(text_model(f"reset-{index % 2}"), "mutable")
                    check("bounded reset reuses one report", lambda: (
                        (_ for _ in ()).throw(AssertionError(fixtures.metrics()))
                        if fixtures.metrics()["active"] != 9 or fixtures.created_total != 9 else None
                    ))

                    with sync_playwright() as playwright:
                        browser = playwright.chromium.launch(**browser_kwargs())
                        context = browser.new_context()
                        context.set_default_timeout(8_000)
                        context.set_default_navigation_timeout(30_000)
                        page = context.new_page()
                        events = BrowserEvents()
                        events.attach(page)

                        def skip_link() -> None:
                            _open(page, f"{host.url}/visualizer/reports?report={quote(hub_ids[0])}", '[data-testid="report-hub"]')
                            page.evaluate("()=>document.activeElement?.blur?.()")
                            link = page.get_by_role("link", name="Skip to main content", exact=True)
                            for _ in range(12):
                                page.keyboard.press("Tab")
                                if link.evaluate("node=>document.activeElement===node"):
                                    break
                            assert link.evaluate("node=>document.activeElement===node")
                            assert _inside_viewport(link, 1440)
                            page.keyboard.press("Enter")
                            page.wait_for_function("()=>location.hash==='#cui-main-content'||document.activeElement?.id==='cui-main-content'")

                        check("skip link uses keyboard accessibility semantics", skip_link)

                        def stable_hub_action() -> None:
                            _open(page, f"{host.url}/visualizer/reports?report={quote(hub_ids[0])}", '[data-testid="report-hub"]')
                            card = page.locator(f'[data-report-id="{hub_ids[0]}"]')
                            before = fixtures.snapshot_ids()
                            assert card.locator('[data-report-action="duplicate"]').get_attribute("data-report-action") == "duplicate"
                            card.locator('[data-report-action="duplicate"]').click()
                            page.wait_for_function("n=>document.querySelectorAll('[data-testid=report-card]').length>n", arg=8)
                            created = fixtures.adopt_new(before, "targeted duplicate")
                            assert len(created) == 1
                            fixtures.cleanup_extras(set(fixtures.scenarios.values()))
                            assert fixtures.metrics()["active"] == 9

                        check("semantic Report Hub selector survives refresh", stable_hub_action)

                        def diagram_drawers(width: int) -> None:
                            report_id = fixtures.reset(diagram_model(), "mutable")
                            page.set_viewport_size({"width": width, "height": 844 if width == 390 else 900})
                            _open(page, f"{host.url}/visualizer/diagram-studio?report={quote(report_id)}&element=c1", '#diagram-studio[data-studio-ready="true"]')
                            shapes = page.locator('[data-action="toggle-palette"]')
                            inspector = page.locator('[data-action="toggle-inspector"]')
                            assert _inside_viewport(shapes, width) and _inside_viewport(inspector, width)
                            shapes.click()
                            page.locator("#ds-shape-panel.is-open").wait_for()
                            assert page.locator("#ds-panel-backdrop").is_visible()
                            assert shapes.get_attribute("aria-expanded") == "true"
                            page.locator('#ds-shape-panel [data-action="close-panels"]').click()
                            page.wait_for_function("()=>!document.querySelector('#ds-shape-panel').classList.contains('is-open')")
                            page.locator("[data-node-id]").first.evaluate("node=>node.dispatchEvent(new MouseEvent('click',{bubbles:true}))")
                            inspector.click()
                            page.locator("#ds-inspector-panel.is-open").wait_for()
                            assert inspector.get_attribute("aria-expanded") == "true"
                            page.locator('#ds-inspector-panel [data-action="add-layer"]').click()
                            page.keyboard.press("Escape")
                            page.wait_for_function("()=>!document.querySelector('#ds-inspector-panel').classList.contains('is-open')")
                            assert inspector.get_attribute("aria-expanded") == "false"
                            _no_page_overflow(page)
                            page.screenshot(path=str(shots / f"diagram-drawers-{width}.png"))

                        check("Diagram Studio 768 drawers expose and restore controls", lambda: diagram_drawers(768))
                        check("Diagram Studio 390 drawers expose and restore controls", lambda: diagram_drawers(390))

                        def responsive_editor() -> None:
                            report_id = fixtures.reset(acceptance_model(), "mutable")
                            page.set_viewport_size({"width": 768, "height": 900})
                            _open(page, f"{host.url}/visualizer?report={quote(report_id)}", '.cui-visualizer-root[data-editor-ready="true"]')
                            backdrop = page.locator("#panelBackdrop:visible")
                            if backdrop.count(): backdrop.click()
                            page.locator(".component").first.click()
                            page.locator("#libraryToggle").click()
                            assert page.locator("#panelBackdrop").is_visible()
                            page.keyboard.press("Escape")
                            page.wait_for_function("()=>document.querySelector('#libraryToggle').getAttribute('aria-pressed')==='false'")
                            assert page.locator(".component.selected").count() == 1
                            _no_page_overflow(page)

                        check("responsive overlay ordering selects before modality", responsive_editor)

                        def mobile_routes() -> None:
                            report_id = fixtures.reset(acceptance_model(), "mutable")
                            diagram_id = fixtures.reset(diagram_model(), "diagram-mobile")
                            chart_id = fixtures.reset(chart_model(), "chart-mobile")
                            page.set_viewport_size({"width": 390, "height": 844})
                            _open(page, f"{host.url}/visualizer?report={quote(report_id)}", '.cui-visualizer-root[data-editor-ready="true"]')
                            page.locator("#previewBtn").click()
                            page.locator("#previewExit:visible").wait_for()
                            _no_page_overflow(page)
                            page.locator("#previewExit").click()
                            _open(page, f"{host.url}/visualizer/reports?report={quote(report_id)}", '[data-testid="report-hub"]')
                            _no_page_overflow(page)
                            _open(page, f"{host.url}/visualizer/diagram-studio?report={quote(diagram_id)}&element=c1", '#diagram-studio[data-studio-ready="true"]')
                            _no_page_overflow(page)
                            _open(page, f"{host.url}/visualizer/chart-studio?report={quote(chart_id)}&element=c1", '#chart-studio[data-studio-ready="true"]')
                            _no_page_overflow(page)
                            page.screenshot(path=str(shots / "mobile-chart-studio-390.png"))

                        check("mobile 390 editor hub studios preview navigation", mobile_routes)
                        receipt["unexpected_errors"] = events.unexpected
                        check("zero unexpected console page network errors", lambda: (
                            (_ for _ in ()).throw(AssertionError(events.unexpected)) if events.unexpected else None
                        ))
                        context.close()
                        browser.close()
                receipt["fixture_lifecycle"] = fixtures.final_metrics
        receipt["isolated_storage_removed"] = not data_dir.exists()
    except Exception as error:
        receipt["harness_error"] = str(error)
        receipt["traceback"] = traceback.format_exc()

    lifecycle = receipt.get("fixture_lifecycle") or {}
    check("final crawler-owned report count is zero", lambda: (
        (_ for _ in ()).throw(AssertionError(lifecycle))
        if lifecycle.get("active") != 0 or lifecycle.get("created_total") != lifecycle.get("cleaned") else None
    ))
    receipt["passed"] = sum(row["status"] == "PASS" for row in receipt["cases"])
    receipt["total"] = len(receipt["cases"])
    receipt["status"] = "PASS" if (
        receipt["passed"] == receipt["total"]
        and not receipt["unexpected_errors"]
        and receipt.get("isolated_storage_removed") is True
        and "harness_error" not in receipt
    ) else "FAIL"
    write_json(output / "crawler-hardening-acceptance.json", receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
