#!/usr/bin/env python3
"""Native browser gate for Report Hub/Manage thumbnail geometry and errors."""
from __future__ import annotations

import argparse
import hashlib
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
from company_ui.products.visualizer.templates import template_model
from editor_host import NativeHost
from native_common import BrowserEvents, browser_kwargs, ready, write_json


FROZEN_HASH = "d8ebd4378f01b7c52a7a4be57c578c22adf29b899cc08a370cf084881195343e"


def _item(index: int, *, engine: str = "TextEngine", element: str = "Body Narrative", **extra) -> dict:
    return {
        "id": f"c{index}",
        "type": "text",
        "engine": engine,
        "element": element,
        "title": element,
        "text": f"Thumbnail fixture {index}",
        "order": index - 1,
        "locked": False,
        "z": index,
        **extra,
    }


def _model(items: list[dict], *, width: float = 1600, height: float = 900) -> dict:
    return canonical_model({
        "schema_version": 1,
        "items": items,
        "groups": {},
        "datasets": [],
        "mode": "smart",
        "layoutPreset": "editorial",
        "crossFilter": None,
        "canvas": {"width": width, "height": height},
        "nextId": len(items) + 1,
    })


def _fixture_models() -> list[dict]:
    observed = _model([
        _item(1, x=40, y=973, w=520, h=24),
        _item(2, engine="CoreChartEngine", element="Line Chart", x=600, y=1106, w=840, h=260,
              data=[["A", 1], ["B", 3], ["C", 2]]),
        _item(3, engine="WaferFabEngine", element="Wafer Map", x=1500, y=1400, w=0, h=0,
              observations=[{"x": 0, "y": 0, "value": 91}]),
    ])
    dense = _model([_item(index) for index in range(1, 13)])
    narrow = _model([
        _item(1, engine="DiagramEngine", element="Process Flow", x=-300, y=-200, w=8, h=8,
              nodes=["Detect", "Verify"], edges=[{"from": 0, "to": 1, "label": "pass"}]),
        _item(2, engine="ImageMediaEngine", element="Screenshot Frame", x=1950, y=40, w=1, h=1),
    ])
    mixed = _model([
        _item(1, engine="MetricEngine", element="Hero KPI", value=84.2, unit="%"),
        _item(2, engine="CoreChartEngine", element="Line Chart", data=[["W1", 82], ["W2", 86]]),
        _item(3, engine="TableEngine", element="Clean Table"),
        _item(4, engine="DiagramEngine", element="Process Flow", nodes=["A", "B"], edges=[["A", "B"]]),
        _item(5, engine="WaferFabEngine", element="Wafer Map", observations=[{"x": 0, "y": 0, "value": 0}]),
    ])
    return [observed, dense, narrow, mixed, template_model("operations-review"), template_model("investigation-rca")]


def _invalid_svg_geometry(page) -> list[dict]:
    return page.evaluate("""()=>{
      const bad=[];
      for(const node of document.querySelectorAll('.cui-report-thumb svg *')){
        for(const name of ['x','y','width','height']){
          if(!node.hasAttribute(name))continue;
          const raw=node.getAttribute(name),value=Number(raw);
          if(!Number.isFinite(value)||value<0)bad.push({tag:node.tagName,attribute:name,value:raw});
        }
      }
      return bad;
    }""")


def _assert_no_page_overflow(page) -> None:
    overflow = page.evaluate("()=>document.documentElement.scrollWidth-window.innerWidth")
    assert overflow <= 1, f"page-level horizontal overflow: {overflow}px"


def _wait_hub(page, expected_cards: int) -> None:
    page.locator('[data-testid="report-hub"]').wait_for(timeout=20_000)
    page.wait_for_function("count=>document.querySelectorAll('[data-testid=report-card]').length>=count", arg=expected_cards)
    page.wait_for_timeout(180)
    invalid = _invalid_svg_geometry(page)
    assert not invalid, invalid


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    screenshots = output / "screenshots"
    screenshots.mkdir(exist_ok=True)
    receipt = {"scope": "native Report Hub browser-error release gate", "workflows": [], "unexpected_errors": []}

    try:
        with tempfile.TemporaryDirectory(prefix="visembler-report-hub-gate-") as temp:
            data_dir = Path(temp) / "data"
            with NativeHost(ROOT, data_dir) as host, sync_playwright() as playwright:
                report_ids = []
                fixtures = _fixture_models()
                for index in range(12):
                    report_ids.append(host.create(model=fixtures[index % len(fixtures)], name=f"hub-gate-{index + 1:02d}"))
                pathological_id = report_ids[0]
                browser = playwright.chromium.launch(**browser_kwargs())
                context = browser.new_context()

                def run_case(name: str, width: int, action) -> None:
                    page = context.new_page()
                    page.set_viewport_size({"width": width, "height": 900 if width != 390 else 844})
                    events = BrowserEvents()
                    events.attach(page)
                    row = {"name": name, "viewport": width, "status": "FAIL"}
                    try:
                        action(page)
                        page.wait_for_timeout(180)
                        assert not events.unexpected, events.unexpected
                        row["status"] = "PASS"
                        row["thumbnail_count"] = page.locator(".cui-report-thumb-svg").count()
                        row["invalid_svg_geometry"] = _invalid_svg_geometry(page)
                        page.screenshot(path=str(screenshots / f"{name}-{width}.png"), full_page=False)
                    except Exception as error:
                        row["error"] = str(error)
                        row["traceback"] = traceback.format_exc()
                    finally:
                        row["browser_events"] = list(events.unexpected)
                        receipt["unexpected_errors"].extend({"workflow": name, "viewport": width, **event} for event in events.unexpected)
                        receipt["workflows"].append(row)
                        page.close()

                def hub_views(page) -> None:
                    page.goto(f"{host.url}/visualizer/reports?report={quote(pathological_id)}", wait_until="domcontentloaded")
                    _wait_hub(page, 12)
                    page.locator('[data-testid="report-list-view"]').click()
                    page.locator(".cui-report-list").wait_for()
                    page.locator('[data-testid="report-grid-view"]').click()
                    page.locator(".cui-report-grid:not(.cui-report-list)").first.wait_for()
                    assert page.locator('[data-preview-family="chart"]').count() >= 1
                    assert page.locator('[data-preview-family="wafer"]').count() >= 1
                    assert page.locator('[data-preview-family="diagram"]').count() >= 1
                    assert not _invalid_svg_geometry(page)
                    _assert_no_page_overflow(page)

                def manage(page, selected: bool) -> None:
                    page.goto(f"{host.url}/visualizer?report={quote(pathological_id)}", wait_until="domcontentloaded")
                    ready(page, require_settled=True)
                    if selected:
                        page.locator(".component").first.evaluate("element=>element.click()")
                    page.locator('[data-testid="manage-reports"]').click()
                    _wait_hub(page, 12)
                    _assert_no_page_overflow(page)
                    page.get_by_role("button", name="Open editor", exact=True).click()
                    ready(page, require_settled=False)

                for width in (1440, 768, 390):
                    run_case("report-hub-grid-list-thumbnails", width, hub_views)
                    run_case("editor-manage-unselected" if width == 1440 else "editor-manage-selected", width,
                             lambda page, selected=width != 1440: manage(page, selected))

                # Exercise creation/open/trash against the isolated repository.
                def lifecycle(page) -> None:
                    before = {record.report_id for record in host.repository.list()}
                    page.goto(f"{host.url}/visualizer/reports?report={quote(pathological_id)}", wait_until="domcontentloaded")
                    _wait_hub(page, 12)
                    page.get_by_role("button", name="Create report", exact=True).click()
                    ready(page, require_settled=False)
                    created = {record.report_id for record in host.repository.list()} - before
                    assert len(created) == 1, created
                    created_id = created.pop()
                    page.locator('[data-testid="manage-reports"]').click()
                    _wait_hub(page, 13)
                    card = page.locator(f'[data-report-id="{created_id}"][data-report-state="active"]')
                    card.locator('[data-report-action="open"]').click()
                    ready(page, require_settled=False)
                    page.locator('[data-testid="manage-reports"]').click()
                    _wait_hub(page, 13)
                    card = page.locator(f'[data-report-id="{created_id}"][data-report-state="active"]')
                    card.locator('[data-report-action="trash"]').click()
                    page.locator('.q-dialog').get_by_role("button", name="Move to trash", exact=True).click()
                    page.wait_for_function("rid=>!document.querySelector(`[data-report-id=\"${rid}\"][data-report-state=active]`)", arg=created_id)
                    assert any(record.report_id == created_id for record in host.repository.list_trash())
                    assert not _invalid_svg_geometry(page)

                run_case("report-hub-create-open-trash", 1440, lifecycle)
                receipt["fixture_reports_created"] = 13
                receipt["fixture_reports_peak_active"] = 13
                context.close()
                browser.close()
        receipt["isolated_storage_removed"] = not data_dir.exists()
    except Exception as error:
        receipt["harness_error"] = str(error)
        receipt["traceback"] = traceback.format_exc()

    frozen = ROOT / "company_ui/products/visualizer/vendor/production_core/core/GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js"
    receipt["frozen_connector_sha256"] = hashlib.sha256(frozen.read_bytes()).hexdigest()
    receipt["passed"] = sum(row.get("status") == "PASS" for row in receipt["workflows"])
    receipt["total"] = len(receipt["workflows"])
    receipt["status"] = "PASS" if (
        receipt["passed"] == receipt["total"] == 7
        and not receipt["unexpected_errors"]
        and receipt.get("isolated_storage_removed") is True
        and receipt["frozen_connector_sha256"] == FROZEN_HASH
        and "harness_error" not in receipt
    ) else "FAIL"
    write_json(output / "report-hub-browser-error-gate.json", receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
