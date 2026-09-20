from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

from company_ui.products.visualizer.domain import canonical_model


ROOT = Path(__file__).resolve().parents[1]


def _source(headers: list[str], rows: list[list[object]]) -> str:
    return "\n".join(["\t".join(headers), *["\t".join(str(value) for value in row) for row in rows]])


def _helpers():
    scripts = str(ROOT / "scripts" / "release_checks")
    sys.path.insert(0, scripts)
    try:
        from editor_host import NativeHost, load_editor
        from run_editor_workflows import model, panels, ready, settled
    finally:
        sys.path.remove(scripts)
    return NativeHost, load_editor, model, panels, ready, settled


@pytest.mark.parametrize("viewport", [(1440, 900), (1024, 900), (390, 844)])
def test_chg138_r2_native_search_and_keyboard_mapping(viewport: tuple[int, int], tmp_path: Path) -> None:
    playwright = pytest.importorskip("playwright.sync_api")
    NativeHost, load_editor, model, panels, ready, settled = _helpers()
    headers = ["category", "value", "first", "second", *[f"Very long field name {index}" for index in range(1, 33)]]
    rows = []
    for index in range(1, 4):
        long_values = [("A" if index % 2 else "B") if field_index == 31 else index * 100 + field_index for field_index in range(1, 33)]
        rows.append(["A" if index % 2 else "B", index, index + 10, index + 20, *long_values])
    source = _source(headers, rows)

    with NativeHost(ROOT, tmp_path / "native-data") as host:
        with playwright.sync_playwright() as instance:
            executable = os.environ.get("VISEMBLER_BROWSER") or shutil.which("chromium")
            options = {"headless": True}
            if executable:
                options.update(executable_path=executable, args=["--no-sandbox"])
            browser = instance.chromium.launch(**options)
            page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
            errors: list[str] = []
            failed_requests: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.on("requestfailed", lambda request: failed_requests.append(str(request.failure)))
            try:
                report_id = host.create()
                load_editor(page, host, report_id)
                ready(page)
                panels(page, library=True, inspector=False)
                page.locator("#pasteDataBtn").click()
                page.locator("#dataFirstText").fill(source)
                page.locator(".data-first-summary").wait_for(state="visible", timeout=20_000)

                search = page.locator("[data-human-field-search]").first
                search.fill("Very long field name 31")
                search.wait_for(state="visible")
                assert page.locator(".human-field-card").count() == 1
                assert "Very long field name 31" in page.locator(".human-field-card").inner_text()
                assert search.evaluate("node => document.activeElement === node")
                assert search.input_value() == "Very long field name 31"

                # Move through the staged flow and choose a real chart result.
                page.locator('[data-data-first-stage="choose"]').last.click()
                page.locator('[data-data-first-view="bar"]').click()
                page.locator('[data-data-first-stage="map"]').last.click()
                assert page.locator("[data-human-field-search]").input_value() == "Very long field name 31"
                category = page.locator('[data-data-first-role="category"]')
                category.focus()
                card = page.locator(".human-field-card").first
                card.focus()
                card.press("Enter")
                assert category.input_value() == card.get_attribute("data-human-field")
                assert page.locator("[data-human-field-search]").input_value() == "Very long field name 31"

                # An incompatible direct assignment is rejected before mapping state changes.
                value_shelf = page.locator('[data-data-first-role="value"]')
                before_mapping = value_shelf.input_value()
                value_shelf.focus()
                card.focus()
                card.press("Enter")
                assert value_shelf.input_value() == before_mapping
                assert "needs a number" in page.locator("#dataFirstValidation").inner_text()

                # Drag remains supported, but the keyboard path above is the primary path.
                page.locator("#dataFirstReset").click()
                page.locator('[data-data-first-role="category"]').focus()
                page.locator('[data-human-field-search]').fill("Very long field name 30")
                drag_card = page.locator(".human-field-card").first
                drag_card.drag_to(page.locator('[data-role-drop="category"]'))
                assert page.locator('[data-data-first-role="category"]').input_value() == drag_card.get_attribute("data-human-field")
                assert page.locator("#dataFirstValidation").count() == 0
                assert page.locator(".human-encoding-shelf").filter(has_text="Required").count() >= 1
                assert page.locator(".human-encoding-shelf").filter(has_text="Optional").count() >= 1

                # Create the selected result and inspect the same field-browser contract in Data Dock.
                page.locator('[data-data-first-stage="commit"]').last.click()
                page.locator("#dataFirstCreate").click()
                page.wait_for_function(
                    "(count) => window.CompanyUIVisualizerBridge.state().model.items.length > count",
                    arg=0,
                    timeout=30_000,
                )
                settled(page)
                created = next(item for item in model(page)["items"] if item["element"] == "Vertical Bar")
                component = page.locator(f'.component[data-id="{created["id"]}"]')
                component.focus()
                component.press("Enter")
                panels(page, library=False, inspector=True)
                page.locator('[data-data-dock-tab="fields"]').click()
                dock_search = page.locator("[data-human-field-search]").first
                before_search_model = model(page)
                dock_search.fill("Very long field name 31")
                assert page.locator(".human-field-card").count() == 1
                assert dock_search.evaluate("node => document.activeElement === node")
                assert model(page) == before_search_model
                assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1")
                assert not errors, errors
                assert not failed_requests, failed_requests
            finally:
                page.context.close()
                browser.close()


def test_chg138_r2_native_preview_parity_and_chart_studio_shared_search(tmp_path: Path) -> None:
    playwright = pytest.importorskip("playwright.sync_api")
    NativeHost, load_editor, model, panels, ready, settled = _helpers()
    cases = [
        ("table", "category\tvalue\nA\t1\nB\t2", "TableEngine", "table-frame"),
        ("timeline", "date\tevent\n2026-01-01\tstart\n2026-01-02\tstop", "TimelineEngine", "timeline-rail"),
        ("diagram", "source\ttarget\nA\tB\nB\tC", "DiagramEngine", "diagram-svg"),
        ("line", "date\tvalue\tfirst\tsecond\n2026-01-01\t1\t10\t3\n2026-01-02\t2\t9\t2", "CoreChartEngine", "chart-studio-render"),
        ("engineering", "subgroup\tmeasurement\nA\t1\nA\t2\nB\t3\nB\t4", "EngineeringChartEngine", "chart-studio-spc-control-chart"),
        ("wafer", "wafer_id\tdie_x\tdie_y\tvalue\nW01\t1\t1\t98\nW01\t2\t1\t99", "WaferFabEngine", "cs-wafer-svg"),
    ]

    with NativeHost(ROOT, tmp_path / "native-data") as host:
        with playwright.sync_playwright() as instance:
            executable = os.environ.get("VISEMBLER_BROWSER") or shutil.which("chromium")
            options = {"headless": True}
            if executable:
                options.update(executable_path=executable, args=["--no-sandbox"])
            browser = instance.chromium.launch(**options)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors: list[str] = []
            failed_requests: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.on("requestfailed", lambda request: failed_requests.append(str(request.failure)))
            try:
                report_id = host.create()
                load_editor(page, host, report_id)
                ready(page)
                panels(page, library=True, inspector=False)

                created_chart_id = None
                for view, source, engine, marker in cases:
                    before_count = len(model(page)["items"])
                    if before_count:
                        page.keyboard.press("Escape")
                    page.locator("#pasteDataBtn").click()
                    page.locator("#dataFirstText").fill(source)
                    page.locator(".data-first-summary").wait_for(state="visible", timeout=20_000)
                    page.locator('[data-data-first-stage="choose"]').last.click()
                    card = page.locator(f'[data-data-first-view="{view}"]')
                    assert card.count() == 1, (view, page.locator(".data-first-recommendations").inner_text())
                    card.click()
                    preview = page.locator(".data-first-live-preview")
                    preview.locator(f'[data-engine="{engine}"]').wait_for(state="visible")
                    assert marker in preview.inner_html()
                    preview_html = preview.locator(f'[data-engine="{engine}"]').inner_html()
                    page.locator('[data-data-first-stage="map"]').last.click()
                    page.locator('[data-data-first-stage="commit"]').last.click()
                    create_button = page.locator("#dataFirstCreate")
                    assert create_button.count() == 1 and create_button.is_visible() and create_button.is_enabled(), (view, page.locator("#modalBody").inner_text()[-1200:])
                    create_button.click()
                    page.wait_for_function(
                        "(count) => window.CompanyUIVisualizerBridge.state().model.items.length > count",
                        arg=before_count,
                        timeout=30_000,
                    )
                    settled(page)
                    item = model(page)["items"][-1]
                    assert item["engine"] == engine
                    rendered = page.locator(f'.component[data-id="{item["id"]}"] .integrated-element-content')
                    assert marker in rendered.inner_html()
                    assert preview_html == rendered.locator(f'[data-engine="{engine}"]').inner_html()
                    if engine == "CoreChartEngine":
                        created_chart_id = item["id"]

                assert created_chart_id
                page.goto(f"{host.url}/visualizer/chart-studio?report={report_id}&element={created_chart_id}", wait_until="domcontentloaded")
                page.locator('#chart-studio[data-studio-ready="true"]').wait_for(timeout=20_000)
                page.locator('[data-cs-tab="fields"]').click()
                chart_search = page.locator("[data-human-field-search]").first
                chart_search.fill("value")
                assert page.locator(".human-field-card").count() == 1
                assert chart_search.evaluate("node => document.activeElement === node")
                chart_search.fill("date")
                assert page.locator(".human-field-card").count() == 1

                # Chart Studio uses the same transient draft authority for a multi-field calculation.
                page.locator('[data-cs-tab="data"]').click()
                before_hash = page.evaluate("window.CompanyUIChartStudio.hash()")
                page.locator("#cs-transform-kind").select_option("calculated")
                page.locator('[data-multi-field="source_fields"]').select_option(["first_3", "second_4"])
                page.locator("#cs-transform-value").fill("delta")
                assert page.locator(".human-transform-preview").inner_text().lower().find("before / after") >= 0
                assert page.evaluate("window.CompanyUIChartStudio.hash()") == before_hash
                assert page.locator(".human-transform-preview").inner_text().find("delta") >= 0
                assert not errors, errors
                assert not failed_requests, failed_requests
            finally:
                page.context.close()
                browser.close()


def test_chg138_r2_native_datadock_transform_draft_is_non_mutating_until_save(tmp_path: Path) -> None:
    playwright = pytest.importorskip("playwright.sync_api")
    NativeHost, load_editor, model, panels, ready, settled = _helpers()
    source = "date\tvalue\tfirst\tsecond\n2026-01-01\t1\t10\t3\n2026-01-02\t2\t9\t2"

    with NativeHost(ROOT, tmp_path / "native-data") as host:
        with playwright.sync_playwright() as instance:
            executable = os.environ.get("VISEMBLER_BROWSER") or shutil.which("chromium")
            options = {"headless": True}
            if executable:
                options.update(executable_path=executable, args=["--no-sandbox"])
            browser = instance.chromium.launch(**options)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors: list[str] = []
            failed_requests: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.on("requestfailed", lambda request: failed_requests.append(str(request.failure)))
            try:
                report_id = host.create()
                load_editor(page, host, report_id)
                ready(page)
                panels(page, library=True, inspector=False)
                page.locator("#pasteDataBtn").click()
                page.locator("#dataFirstText").fill(source)
                page.locator(".data-first-summary").wait_for(state="visible", timeout=20_000)
                page.locator('[data-data-first-stage="choose"]').last.click()
                page.locator('[data-data-first-view="line"]').click()
                page.locator('[data-data-first-stage="map"]').last.click()
                page.locator('[data-data-first-stage="commit"]').last.click()
                page.locator("#dataFirstCreate").click()
                page.wait_for_function(
                    "() => window.CompanyUIVisualizerBridge.state().model.items.length === 1",
                    timeout=30_000,
                )
                settled(page)
                entry = model(page)["items"][0]
                component = page.locator(f'.component[data-id="{entry["id"]}"]')
                component.focus()
                component.press("Enter")
                panels(page, library=False, inspector=True)
                page.locator('[data-data-dock-tab="transforms"]').click()

                before_draft = model(page)
                page.locator('[data-transform-type]').select_option("calculated")
                page.locator('[data-multi-field="source_fields"]').select_option(["first_3", "second_4"])
                page.locator('[data-transform-operation]').select_option("subtract")
                page.locator('[data-transform-name]').fill("delta")
                draft_preview = page.locator(".human-transform-preview").inner_text()
                assert "2 → 2 rows" in draft_preview
                assert "added delta" in draft_preview
                assert model(page) == before_draft

                page.locator('[data-transform-action="save"]').click()
                page.wait_for_function(
                    "() => window.CompanyUIVisualizerBridge.state().model.items[0].transform_recipe?.steps?.[0]?.type === 'calculated'",
                    timeout=30_000,
                )
                settled(page)
                after_calculated = model(page)
                assert after_calculated != before_draft

                page.locator('[data-transform-type]').select_option("unpivot")
                page.locator('[data-multi-field="keep_fields"]').select_option("date_1")
                unpivot_preview = page.locator(".human-transform-preview").inner_text()
                assert "rows" in unpivot_preview and "2 → 8 rows" in unpivot_preview
                assert model(page) == after_calculated
                page.locator('[data-transform-action="save"]').click()
                page.wait_for_function(
                    "() => window.CompanyUIVisualizerBridge.state().model.items[0].transform_recipe.steps.length === 2",
                    timeout=30_000,
                )
                assert model(page)["items"][0]["transform_recipe"]["steps"][1]["type"] == "unpivot"
                assert not errors, errors
                assert not failed_requests, failed_requests
            finally:
                page.context.close()
                browser.close()


def test_chg138_r2_native_shared_refresh_and_selected_detach_match_consequence_labels(tmp_path: Path) -> None:
    playwright = pytest.importorskip("playwright.sync_api")
    NativeHost, load_editor, model, panels, ready, settled = _helpers()
    fields = [
        {"id": "category", "name": "Category", "type": "categorical"},
        {"id": "value", "name": "Value", "type": "number"},
    ]
    dataset = {"id": "d1", "name": "Shared source", "revision": 1, "fields": fields, "rows": [["A", 1], ["B", 2]]}
    def item(item_id: str, locked: bool = False, order: int = 0) -> dict:
        return {
            "id": item_id,
            "type": "chart",
            "engine": "CoreChartEngine",
            "element": "Vertical Bar",
            "title": item_id,
            "dataset_id": "d1",
            "view_type": "bar",
            "mapping": {"category": "category", "value": "value"},
            "locked": locked,
            "showTitle": False,
            "order": order,
            "x": 14 + order * 500,
            "y": 14,
            "w": 440,
            "h": 320,
        }
    initial_model = canonical_model({"datasets": [dataset], "items": [item("c1", order=0), item("c2", order=1)]})

    with NativeHost(ROOT, tmp_path / "native-data") as host:
        with playwright.sync_playwright() as instance:
            executable = os.environ.get("VISEMBLER_BROWSER") or shutil.which("chromium")
            options = {"headless": True}
            if executable:
                options.update(executable_path=executable, args=["--no-sandbox"])
            browser = instance.chromium.launch(**options)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors: list[str] = []
            failed_requests: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.on("requestfailed", lambda request: failed_requests.append(str(request.failure)))
            try:
                report_id = host.create(model=initial_model)
                load_editor(page, host, report_id)
                ready(page)
                c1 = page.locator('.component[data-id="c1"]')
                c1.focus()
                c1.press("Enter")
                panels(page, library=False, inspector=True)
                page.locator('[data-data-dock-tab="source"]').last.click()
                source_text = page.locator('[data-data-dock-content="source"]').inner_text()
                assert "2 visuals use this dataset" in source_text
                assert "Refresh shared dataset · update 2 linked visuals" in source_text
                assert "Replace this visual only · detach its data" in source_text

                page.locator('[data-data-dock-content="source"] [data-refresh-dataset]').click()
                page.locator("#refreshDataText").fill("Category\tValue\nA\t10\nB\t20")
                page.locator("#refreshLinked:not([disabled])").wait_for(state="visible")
                page.locator("#refreshLinked").click()
                page.wait_for_function(
                    "() => window.CompanyUIVisualizerBridge.state().model.datasets[0].revision === 2",
                    timeout=30_000,
                )
                settled(page)
                refreshed = model(page)
                assert all(item_value["dataset_id"] == "d1" for item_value in refreshed["items"])
                assert refreshed["datasets"][0]["rows"] == [["A", 10], ["B", 20]]

                # Lock the second consumer, then verify the shared action is
                # blocked while selected-only detach remains available.
                c2 = page.locator('.component[data-id="c2"]')
                c2.focus()
                c2.press("Enter")
                panels(page, library=False, inspector=True)
                page.locator('[data-inspector="lock"]').click()
                settled(page)
                c1.focus()
                c1.press("Enter")
                panels(page, library=False, inspector=True)
                page.locator('[data-data-dock-tab="source"]').last.click()
                assert "Locked linked visual" in page.locator('[data-data-dock-content="source"]').inner_text()
                page.locator('[data-data-dock-content="source"] [data-refresh-dataset]').click()
                page.locator("#refreshDataText").fill("Category\tValue\nA\t100\nB\t200")
                page.locator("#refreshLinked[disabled]").wait_for(state="visible")
                assert "Unlock every linked visual" in page.locator("#modalBody").inner_text()
                page.locator("#refreshOnly:not([disabled])").wait_for(state="visible")
                page.locator("#refreshOnly").click()
                page.wait_for_function(
                    "() => window.CompanyUIVisualizerBridge.state().model.items.find(item => item.id === 'c1').dataset_id !== 'd1'",
                    timeout=30_000,
                )
                settled(page)
                final_model = model(page)
                c1_final = next(item_value for item_value in final_model["items"] if item_value["id"] == "c1")
                c2_final = next(item_value for item_value in final_model["items"] if item_value["id"] == "c2")
                assert c1_final["dataset_id"] != "d1"
                assert c2_final["dataset_id"] == "d1"
                assert len(final_model["datasets"]) == 2
                assert not errors, errors
                assert not failed_requests, failed_requests
            finally:
                page.context.close()
                browser.close()
