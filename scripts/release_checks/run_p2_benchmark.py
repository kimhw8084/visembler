"""Measure the five finite P2 authoring tasks against isolated native hosts.

This is an interaction benchmark, not a product acceptance shortcut.  Every
task uses the visible editor controls and a fresh temporary report directory;
model reads are used only for assertions and receipts.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from editor_host import NativeHost, load_editor  # noqa: E402
from native_upload import import_native_report  # noqa: E402

MOD = "Meta" if sys.platform == "darwin" else "Control"

P2_INSTRUMENTATION = """
(() => {
  const m = window.__P2_BENCHMARK__ = {
    modal_opens: 0, destructive_confirmations: 0, context_exits: 0,
    correction_actions: 0, raw_json_edits: 0, no_op_controls: []
  };
  const seen = new WeakSet();
  const inspect = () => document.querySelectorAll('.q-dialog, .modal').forEach(node => {
    const visible = !!(node.offsetWidth || node.offsetHeight || node.getClientRects().length) &&
      getComputedStyle(node).display !== 'none' && getComputedStyle(node).visibility !== 'hidden';
    if (visible && !seen.has(node)) {
      seen.add(node); m.modal_opens += 1;
      if (/trash|delete|restore revision|destructive/i.test(node.innerText || '')) m.destructive_confirmations += 1;
    }
  });
  const observer = new MutationObserver(inspect);
  const attach = () => { if (document.documentElement) { observer.observe(document.documentElement, {subtree:true, childList:true, attributes:true, attributeFilter:['class','style']}); inspect(); } };
  if (document.documentElement) attach(); else document.addEventListener('DOMContentLoaded', attach, {once:true});
  window.addEventListener('click', event => {
    const node = event.target.closest?.('#libraryToggle,#inspectorToggle,#historyBtn,#debugBtn,#exportBtn,#pasteDataBtn,#dataFirstManageMappings,#mappingManagerBack');
    if (node) m.context_exits += 1;
    if (event.target.closest?.('#undo,#redo,[data-close],[data-transform-action="cancel"]')) m.correction_actions += 1;
  }, true);
})();
"""


def state(page):
    return page.evaluate("window.CompanyUIVisualizerBridge.state()")


def model(page):
    return state(page)["model"]


def settled(page):
    page.wait_for_function(
        "() => { const s=window.CompanyUIVisualizerBridge.state(); return s.pending===0&&!s.inflight; }",
        timeout=15000,
    )


def ready(page):
    page.locator('.cui-visualizer-root[data-editor-ready="true"]').wait_for(timeout=20000)
    settled(page)


def primary_click(page, metrics, selector, *, modifiers=None):
    metrics["primary_clicks"] += 1
    page.locator(selector).click(modifiers=modifiers or [])


def primary_locator_click(metrics, locator, *, modifiers=None):
    metrics["primary_clicks"] += 1
    locator.click(modifiers=modifiers or [])


def primary_select(metrics, locator, value):
    metrics["primary_clicks"] += 1
    locator.select_option(value)


def primary_dblclick(metrics, locator):
    metrics["primary_clicks"] += 1
    locator.dblclick()


def ensure_panels(page, metrics):
    for selector in ("#libraryToggle", "#inspectorToggle"):
        if page.locator(selector).get_attribute("aria-pressed") != "true":
            primary_click(page, metrics, selector)


def select_component(page, metrics, item_id, *, modifiers=None):
    primary_locator_click(metrics, page.locator(f'.component[data-id="{item_id}"]'), modifiers=modifiers)
    page.wait_for_function(
        "id => document.querySelector(`.component[data-id=\"${id}\"]`)?.getAttribute('aria-selected')==='true'",
        arg=item_id,
    )


def add_element(page, metrics, name):
    ensure_panels(page, metrics)
    page.locator("#componentSearch").fill(name)
    entry = page.locator(f'.library-item[data-element="{name}"]')
    entry.wait_for(timeout=10000)
    primary_locator_click(metrics, entry.locator(".library-insert"))
    settled(page)
    page.locator("#componentSearch").fill("")
    return model(page)["items"][-1]["id"]


def field_id(page_model, field_name):
    wanted = field_name.casefold()
    for dataset in page_model.get("datasets", []):
        for field in dataset.get("fields", []):
            if str(field.get("name", "")).casefold() == wanted:
                return field["id"]
    raise AssertionError(f"No dataset field named {field_name!r}")


def entry(page_model, item_id):
    return next(item for item in page_model["items"] if item["id"] == item_id)


def edit_field(page, selector, value):
    control = page.locator(selector)
    control.wait_for(state="visible", timeout=10000)
    control.fill(str(value))
    control.press("Tab")
    settled(page)


def open_new_report(page, metrics, template):
    primary_click(page, metrics, 'button:has-text("New report")')
    card = page.locator(".q-dialog:visible .cui-report-template").filter(has_text=template).first
    card.wait_for(state="visible", timeout=10000)
    primary_locator_click(metrics, card)
    page.wait_for_function(
        "template => document.querySelector('.q-dialog[aria-hidden=\"true\"]') || document.querySelector('.q-dialog:not(.q-dialog--open)')",
        arg=template,
        timeout=10000,
    )
    settled(page)


def paste_data(page, metrics, text, view, *, mapping_name=None):
    primary_click(page, metrics, "#pasteDataBtn")
    page.locator("#dataFirstText").fill(text)
    page.locator(f'[data-data-first-view="{view}"]').wait_for(timeout=15000)
    primary_click(page, metrics, f'[data-data-first-view="{view}"]')
    if mapping_name:
        save = page.locator("#dataFirstSaveMapping")
        save.wait_for(state="visible", timeout=10000)
        primary_locator_click(metrics, save)
        page.locator("#mappingPresetName").fill(mapping_name)
        primary_click(page, metrics, "#mappingSaveConfirm")
        page.locator("#dataFirstCreate").wait_for(state="visible", timeout=10000)
    primary_click(page, metrics, "#dataFirstCreate")
    page.locator("#genericModal.show").wait_for(state="hidden", timeout=15000)
    settled(page)
    return model(page)["items"][-1]["id"]


def export_current(page, metrics, out, stem):
    primary_click(page, metrics, "#exportBtn")
    with page.expect_download(timeout=15000) as download:
        primary_click(page, metrics, "#exportJsonAction")
    json_path = out / f"{stem}.json"
    download.value.save_as(str(json_path))
    primary_click(page, metrics, "#exportBtn")
    with page.expect_download(timeout=15000) as download:
        primary_click(page, metrics, "#exportSvgAction")
    svg_path = out / f"{stem}.svg"
    download.value.save_as(str(svg_path))
    svg_text = svg_path.read_text(encoding="utf-8")
    assert "<svg" in svg_text and "NaN" not in svg_text and "undefined" not in svg_text
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert isinstance(payload.get("model", payload).get("items"), list)
    return {"json": str(json_path), "svg": str(svg_path), "svg_readable": True}


def reload_and_assert(page, expected, item_id=None):
    page.reload(wait_until="domcontentloaded")
    ready(page)
    current = model(page)
    if item_id:
        actual = entry(current, item_id)
        for key, value in expected.items():
            assert actual.get(key) == value, (key, actual.get(key), value)
    return current


def viewport_probe(page, out, task_name):
    result = {}
    for width in (390, 768, 1440):
        page.set_viewport_size({"width": width, "height": 900})
        page.wait_for_timeout(100)
        name = f"{task_name}-{width}.png"
        page.screenshot(path=str(out / name), full_page=False)
        result[str(width)] = page.evaluate(
            """() => ({
              viewport: innerWidth,
              document_scroll_width: document.documentElement.scrollWidth,
              visible_control_overflows: [...document.querySelectorAll('button,input,select,textarea')]
                .filter(n => { const s=getComputedStyle(n), r=n.getBoundingClientRect(); return s.display!=='none' && s.visibility!=='hidden' && r.width>0 && r.height>0 && r.right>innerWidth+2; })
                .slice(0, 12).map(n => n.getAttribute('aria-label') || n.textContent.trim().slice(0, 40))
            })""",
        )
    page.set_viewport_size({"width": 1440, "height": 1000})
    return result


def common_receipt(page, metrics, started, errors, out, task_name, friction):
    browser_metrics = page.evaluate("window.__P2_BENCHMARK__ || {}")
    return {
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "primary_clicks": metrics["primary_clicks"],
        "modal_opens": browser_metrics.get("modal_opens", 0),
        "context_exits": browser_metrics.get("context_exits", 0),
        "destructive_confirmations": browser_metrics.get("destructive_confirmations", 0),
        "corrective_recovery_actions": browser_metrics.get("correction_actions", 0),
        "raw_json_edits": browser_metrics.get("raw_json_edits", 0),
        "unexpected_noop_controls": browser_metrics.get("no_op_controls", []),
        "browser_errors": errors,
        "top_three_friction": friction,
        "evidence_directory": str(out),
    }


def task_a(page, metrics, out, image_path):
    text = (
        "LOT\tTOOL\tCHAMBER\tTIMESTAMP\tMEASUREMENT\tTARGET\tSTATUS\n"
        "L001\tETCH-01\tC1\t2026-08-01\t98.2\t100\tRUN\n"
        "L002\tETCH-01\tC1\t2026-08-02\t97.8\t100\tRUN\n"
        "L003\tETCH-02\tC2\t2026-08-03\t101.1\t100\tHOLD\n"
        "L004\tETCH-02\tC2\t2026-08-04\t99.4\t100\tRUN\n"
        "L005\tETCH-03\tC1\t2026-08-05\t96.9\t100\tRUN"
    )
    open_new_report(page, metrics, "Blank canvas")
    chart_id = paste_data(page, metrics, text, "line", mapping_name="Trend investigation mapping")
    select_component(page, metrics, chart_id)
    current = model(page)
    timestamp = field_id(current, "TIMESTAMP")
    measurement = field_id(current, "MEASUREMENT")
    status = field_id(current, "STATUS")
    primary_select(metrics, page.locator('[data-dataset-role="x"]'), timestamp)
    settled(page)
    primary_select(metrics, page.locator('[data-dataset-role="y"]'), measurement)
    settled(page)
    panel = page.locator(".data-transform-panel")
    primary_select(metrics, panel.locator('[data-transform-type]'), "filter")
    primary_select(metrics, panel.locator('[data-transform-field]'), status)
    edit_field(page, '[data-transform-value]', "RUN")
    primary_click(page, metrics, '[data-transform-action="save"]')
    settled(page)
    primary_select(metrics, panel.locator('[data-transform-type]'), "sort")
    primary_select(metrics, panel.locator('[data-transform-field]'), measurement)
    primary_click(page, metrics, '[data-transform-action="save"]')
    settled(page)
    primary_select(metrics, panel.locator('[data-transform-type]'), "top_n")
    edit_field(page, '[data-transform-n]', "3")
    primary_select(metrics, panel.locator('[data-transform-ranking-field]'), measurement)
    primary_click(page, metrics, '[data-transform-action="save"]')
    settled(page)
    primary_click(page, metrics, '[data-transform-step-action="down"][data-transform-index="0"]')
    settled(page)
    before_switch = entry(model(page), chart_id)
    primary_select(metrics, page.locator("#iVisualType"), "CoreChartEngine::Area Chart")
    page.wait_for_function("id => document.querySelector(`[data-id=\"${id}\"] [data-element=\"Area Chart\"]`)", arg=chart_id)
    primary_click(page, metrics, "#undo")
    settled(page)
    assert entry(model(page), chart_id)["element"] == "Line Chart"
    primary_click(page, metrics, "#redo")
    settled(page)
    assert entry(model(page), chart_id)["element"] == "Area Chart"
    value_index = model(page)["datasets"][0]["fields"].index(next(f for f in model(page)["datasets"][0]["fields"] if f["id"] == measurement))
    edit_field(page, f'#dataDockGrid [data-dataset-cell="0:{value_index}"]', "102.4")
    after = entry(model(page), chart_id)
    assert after["element"] == "Area Chart"
    assert [step["type"] for step in after["transform_recipe"]["steps"]] == ["sort", "filter", "top_n"]
    current = reload_and_assert(page, {"element": "Area Chart", "dataset_id": after["dataset_id"]}, chart_id)
    assert entry(current, chart_id)["transform_recipe"]["steps"][0]["type"] == "sort"
    export = export_current(page, metrics, out, "task-a-trend")
    return {"export": export, "state_preserved": True, "transform_order": ["sort", "filter", "top_n"], "before_switch": before_switch["element"]}


def set_engineering_field(page, selector, value):
    edit_field(page, selector, value)


def task_b(page, metrics, out, image_path):
    text = (
        "SUBGROUP\tTIMESTAMP\tMEASUREMENT\tLSL\tUSL\n"
        "G1\t2026-08-01\t98.2\t95\t105\nG1\t2026-08-02\t99.1\t95\t105\n"
        "G2\t2026-08-03\t101.2\t95\t105\nG2\t2026-08-04\t100.4\t95\t105\n"
        "G3\t2026-08-05\t99.7\t95\t105\nG3\t2026-08-06\t100.1\t95\t105\n"
        "G4\t2026-08-07\t98.8\t95\t105\nG4\t2026-08-08\t101.0\t95\t105"
    )
    open_new_report(page, metrics, "Blank canvas")
    chart_id = paste_data(page, metrics, text, "engineering")
    select_component(page, metrics, chart_id)
    set_engineering_field(page, "#iLsl", "95")
    set_engineering_field(page, "#iUsl", "105")
    assert entry(model(page), chart_id).get("specification_low") == 95
    spc_html = page.locator(f'.component[data-id="{chart_id}"] .card-body').inner_html()
    primary_select(metrics, page.locator("#iVisualType"), "EngineeringChartEngine::CUSUM Chart")
    settled(page)
    for selector, value in (("#iTarget", "100"), ("#iSigma", "2"), ("#iK", "0.5"), ("#iDecisionH", "4")):
        set_engineering_field(page, selector, value)
    cusum = entry(model(page), chart_id)
    assert (cusum.get("target"), cusum.get("sigma"), cusum.get("k"), cusum.get("decision_h")) == (100, 2, 0.5, 4)
    cusum_html = page.locator(f'.component[data-id="{chart_id}"] .card-body').inner_html()
    assert cusum_html != spc_html
    primary_select(metrics, page.locator("#iVisualType"), "EngineeringChartEngine::EWMA Chart")
    settled(page)
    for selector, value in (("#iTarget", "100"), ("#iSigma", "2"), ("#iLambda", "0.25"), ("#iControlL", "2.7")):
        set_engineering_field(page, selector, value)
    ewma = entry(model(page), chart_id)
    assert (ewma.get("target"), ewma.get("sigma"), ewma.get("lambda"), ewma.get("L")) == (100, 2, 0.25, 2.7)
    ewma_html = page.locator(f'.component[data-id="{chart_id}"] .card-body').inner_html()
    assert ewma_html != cusum_html
    primary_select(metrics, page.locator("#iVisualType"), "EngineeringChartEngine::SPC Control Chart")
    settled(page)
    kpi_id = add_element(page, metrics, "Hero KPI")
    takeaway_id = add_element(page, metrics, "Key Takeaway")
    assert kpi_id != takeaway_id
    expected = {"element": "SPC Control Chart", "specification_low": 95, "specification_high": 105}
    reload_and_assert(page, expected, chart_id)
    export = export_current(page, metrics, out, "task-b-engineering")
    return {"export": export, "variant_parameters_reached_renderer": True, "supporting_items": [kpi_id, takeaway_id]}


def task_c(page, metrics, out, image_path):
    text = (
        "X_COORD\tY_COORD\tMEASUREMENT\tLOT\tTOOL\tCHAMBER\tROUTE\n"
        "-2\t0\t98.1\tLOT-77\tETCH-04\tC2\tR1\n-1\t1\t99.0\tLOT-77\tETCH-04\tC2\tR1\n"
        "0\t0\t101.2\tLOT-77\tETCH-04\tC2\tR1\n1\t1\t100.4\tLOT-77\tETCH-04\tC2\tR1\n"
        "2\t0\t97.8\tLOT-77\tETCH-04\tC2\tR1"
    )
    open_new_report(page, metrics, "Blank canvas")
    wafer_id = paste_data(page, metrics, text, "wafer")
    select_component(page, metrics, wafer_id)
    current = model(page)
    for role, field_name in (("lot_id", "LOT"), ("tool", "TOOL"), ("chamber", "CHAMBER")):
        role_control = page.locator(f'[data-dataset-role="{role}"]')
        role_control.wait_for(state="visible", timeout=10000)
        primary_select(metrics, role_control, field_id(current, field_name))
        settled(page)
    route_control = page.locator('[data-dataset-role="route"]')
    if route_control.count() == 0:
        raise AssertionError("Wafer Map has no route identity mapping control")
    primary_select(metrics, route_control, field_id(current, "ROUTE"))
    settled(page)
    image_id = add_element(page, metrics, "Image + Caption")
    page.locator("#iImageFile").set_input_files(str(image_path))
    settled(page)
    edit_field(page, "#iAlt", "Wafer map showing center measurement excursion")
    edit_field(page, "#iCaption", "LOT-77 center excursion review")
    evidence_id = add_element(page, metrics, "Evidence Card")
    select_component(page, metrics, image_id)
    select_component(page, metrics, evidence_id, modifiers=[MOD])
    primary_click(page, metrics, "#group")
    settled(page)
    primary_click(page, metrics, "#lock")
    settled(page)
    current = model(page)
    wafer_entry = entry(current, wafer_id)
    assert wafer_entry["mapping"]["lot_id"] == field_id(current, "LOT")
    assert wafer_entry["mapping"]["tool"] == field_id(current, "TOOL")
    assert wafer_entry["mapping"]["chamber"] == field_id(current, "CHAMBER")
    assert wafer_entry["mapping"]["route"] == field_id(current, "ROUTE")
    assert "R1" in page.locator(f'.component[data-id="{wafer_id}"] .card-body').inner_text()
    assert entry(current, image_id).get("alt") == "Wafer map showing center measurement excursion"
    assert entry(current, image_id).get("groupId") is not None
    reload_and_assert(page, {"alt": "Wafer map showing center measurement excursion"}, image_id)
    export = export_current(page, metrics, out, "task-c-wafer")
    import_receipt = import_native_report(page, Path(export["json"]), out / "import-receipt")
    metrics["primary_clicks"] += 4
    imported = model(page)
    assert any(item.get("element") == "Image + Caption" for item in imported["items"])
    return {"export": export, "import": import_receipt, "group_locked": True, "alt_semantics": True}


def choose_report(page, metrics, title):
    select = page.locator(".cui-visualizer-report-select")
    primary_locator_click(metrics, select)
    option = page.locator('.q-menu:visible .q-item').filter(has_text=re.compile(rf'^{re.escape(title)}$')).first
    option.wait_for(state="visible", timeout=10000)
    primary_locator_click(metrics, option)
    page.wait_for_function("title => document.querySelector('[aria-label=\"Report title\"]')?.value === title", arg=title, timeout=15000)
    settled(page)


def task_d(page, metrics, out, image_path):
    open_new_report(page, metrics, "Operations Review")
    original_title = "Operations Review"
    hero_id = "c1"
    select_component(page, metrics, hero_id)
    edit_field(page, "#iValue", "94.2")
    edit_field(page, "#iUnit", "%")
    status_id = add_element(page, metrics, "Status Metric")
    edit_field(page, "#iStatus", "Watch")
    edit_field(page, "#iValue", "2")
    select_component(page, metrics, "c5")
    edit_field(page, "#iDetail", "Owner: Process Engineering · milestone: containment")
    edit_field(page, "#iStatus", "Active")
    headers = ["LOT", "TOOL", "CHAMBER", "SHIFT", "DATE", "MEASURE", "TARGET", "STATUS", "ROUTE", "OWNER", "NOTE"]
    rows = [
        ["L001", "E1", "C1", "A", "2026-08-01", "98", "100", "Run", "R1", "Kim", "ok"],
        ["L002", "E1", "C1", "B", "2026-08-02", "97", "100", "Hold", "R1", "Lee", "review"],
        ["L003", "E2", "C2", "A", "2026-08-03", "101", "100", "Run", "R2", "Park", "ok"],
    ]
    table_text = "\n".join("\t".join(map(str, row)) for row in [headers, *rows])
    table_id = paste_data(page, metrics, table_text, "table", mapping_name="Operations table mapping")
    select_component(page, metrics, table_id)
    table_entry = entry(model(page), table_id)
    dataset_id = table_entry["dataset_id"]
    initial_dataset = next(dataset for dataset in model(page)["datasets"] if dataset["id"] == dataset_id)
    page.locator('[data-dataset-cell="1:5"]').focus()
    primary_click(page, metrics, '[data-dataset-action="insert-row-above"]')
    settled(page)
    changed_dataset = next(dataset for dataset in model(page)["datasets"] if dataset["id"] == dataset_id)
    assert len(changed_dataset["rows"]) == len(initial_dataset["rows"]) + 1
    page.locator('[data-dataset-cell="1:5"]').focus()
    primary_click(page, metrics, '[data-dataset-action="delete-rows"]')
    settled(page)
    changed_dataset = next(dataset for dataset in model(page)["datasets"] if dataset["id"] == dataset_id)
    assert changed_dataset["rows"] == initial_dataset["rows"]
    page.locator('[data-dataset-cell="1:5"]').focus()
    primary_click(page, metrics, '[data-dataset-action="insert-column-left"]')
    settled(page)
    changed_dataset = next(dataset for dataset in model(page)["datasets"] if dataset["id"] == dataset_id)
    assert len(changed_dataset["fields"]) == len(initial_dataset["fields"]) + 1
    page.locator('[data-dataset-cell="1:5"]').focus()
    primary_click(page, metrics, '[data-dataset-action="delete-columns"]')
    settled(page)
    changed_dataset = next(dataset for dataset in model(page)["datasets"] if dataset["id"] == dataset_id)
    assert changed_dataset["fields"] == initial_dataset["fields"] and changed_dataset["rows"] == initial_dataset["rows"]
    primary_click(page, metrics, "#pasteDataBtn")
    page.locator("#dataFirstText").fill(table_text)
    page.locator('[data-data-first-view="table"]').wait_for(timeout=15000)
    primary_click(page, metrics, '[data-data-first-view="table"]')
    primary_click(page, metrics, "#dataFirstManageMappings")
    compatible = page.locator('.mapping-manager-row .mapping-compatibility.compatible').first
    compatible.wait_for(state="visible", timeout=10000)
    primary_click(page, metrics, '[data-mapping-action="apply"]')
    page.locator("#dataFirstCreate").wait_for(state="visible", timeout=10000)
    primary_click(page, metrics, '#genericModal .dialog-head [data-close]')
    page.locator("#genericModal.show").wait_for(state="hidden", timeout=10000)
    primary_locator_click(metrics, page.locator('.cui-visualizer-reportbar button').filter(has_text="Duplicate"))
    settled(page)
    duplicate_title = page.get_by_label("Report title")
    duplicate_title.fill("Operations Review Copy")
    duplicate_title.press("Tab")
    settled(page)
    choose_report(page, metrics, original_title)
    primary_locator_click(metrics, page.locator('.cui-visualizer-reportbar button').filter(has_text="Manage"))
    primary_click(page, metrics, 'button:has-text("Move current to trash…")')
    primary_click(page, metrics, 'button:has-text("Move to trash")')
    settled(page)
    primary_locator_click(metrics, page.locator('.cui-visualizer-reportbar button').filter(has_text="Manage"))
    primary_click(page, metrics, 'button:has-text("Restore trashed report…")')
    primary_click(page, metrics, 'button:has-text("Restore report")')
    page.wait_for_function("title => document.querySelector('[aria-label=\"Report title\"]')?.value === title", arg=original_title, timeout=15000)
    settled(page)
    primary_locator_click(metrics, page.locator('.cui-visualizer-reportbar button').filter(has_text="Manage"))
    primary_click(page, metrics, 'button:has-text("Report history")')
    page.locator('.q-dialog:visible').get_by_text("Report history", exact=True).wait_for(timeout=10000)
    primary_click(page, metrics, 'button:has-text("Restore revision")')
    settled(page)
    export = export_current(page, metrics, out, "task-d-operations")
    return {"export": export, "table_columns": len(headers), "mapping_applied": True, "report_lifecycle": True, "history_restore": True, "status_id": status_id}


def task_e(page, metrics, out, image_path):
    open_new_report(page, metrics, "Investigation / RCA")
    flow_id = "c3"
    select_component(page, metrics, flow_id)
    edit_field(page, "#iNodes", "Detect\nAnalyze\nContain\nVerify")
    edit_field(page, "#iEdges", "Detect -> Analyze\nAnalyze -> Contain\nContain -> Verify")
    primary_select(metrics, page.locator("#iDirection"), "right")
    settled(page)
    edit_field(page, "#iEdgeLabel", "handoff")
    right_svg = page.locator(f'.component[data-id="{flow_id}"] svg')
    right_path = right_svg.locator("path").first.get_attribute("d")
    assert page.locator(f'.component[data-id="{flow_id}"] .diagram-edge-label').count() >= 1
    primary_select(metrics, page.locator("#iVisualType"), "DiagramEngine::Data Flow")
    settled(page)
    primary_click(page, metrics, "#undo")
    settled(page)
    assert entry(model(page), flow_id)["element"] == "Process Flow"
    primary_click(page, metrics, "#redo")
    settled(page)
    assert entry(model(page), flow_id)["element"] == "Data Flow"
    select_component(page, metrics, "c1")
    primary_dblclick(metrics, page.locator('.component[data-id="c1"] .statement-render'))
    edit_field(page, ".component[data-id='c1'] .direct-editor-control", "Observed chamber excursion")
    timeline_id = add_element(page, metrics, "Event Timeline")
    image_id = add_element(page, metrics, "Image + Caption")
    primary_dblclick(metrics, page.locator(f'.component[data-id="{image_id}"] figcaption'))
    edit_field(page, f'.component[data-id="{image_id}"] .direct-editor-control', "Pressure signature capture")
    primary_click(page, metrics, '[data-mode="guided"]')
    settled(page)
    assert model(page)["mode"] == "guided"
    primary_click(page, metrics, '[data-mode="free"]')
    settled(page)
    assert model(page)["mode"] == "free"
    reload_and_assert(page, {"element": "Data Flow"}, flow_id)
    current = model(page)
    assert entry(current, timeline_id)["element"] == "Event Timeline"
    assert entry(current, image_id).get("caption") == "Pressure signature capture"
    export = export_current(page, metrics, out, "task-e-rca")
    down_path = page.locator(f'.component[data-id="{flow_id}"] svg').locator("path").first.get_attribute("d")
    return {"export": export, "edge_label": "handoff", "direction_path_present": bool(right_path), "direction_changed_across_contract": down_path != right_path, "direct_text_caption": True}


TASKS = {
    "A": ("trend-investigation", task_a, [
        "Three ordered transforms require three separate inspector saves and one reorder.",
        "Mapping is selected in the data-intake context before the chart exists.",
        "Export is a separate menu step after persistence verification.",
    ]),
    "B": ("spc-process-control", task_b, [
        "Engineering variant changes move the author through a shared inspector context.",
        "Each statistical parameter is a separate commit-and-rerender interaction.",
        "Supporting KPI and narrative elements still require library context changes.",
    ]),
    "C": ("wafer-yield-evidence", task_c, [
        "Wafer identity fields are distributed across multiple inspector inputs.",
        "Multi-selection is required before grouping and locking the evidence pair.",
        "JSON import is a report-manager round trip after export.",
    ]),
    "D": ("operations-review", task_d, [
        "Template content edits are distributed across element selection and inspector context.",
        "Table selection must precede each row/column operation to preserve the middle target.",
        "Duplicate, trash, restore, and revision restore cross several report dialogs.",
    ]),
    "E": ("rca-process-flow", task_e, [
        "Diagram semantics are edited through several inspector fields before the canvas is readable.",
        "A compatible diagram switch still requires explicit undo/redo verification.",
        "Direct text and caption editing requires canvas double-click targeting.",
    ]),
}


def run_task(browser, name, fn, friction, root, image_path):
    task_out = root / name
    task_out.mkdir(parents=True, exist_ok=True)
    metrics = {"primary_clicks": 0}
    errors = []
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix=f"visembler-p2-{name}-") as task_tmp:
        host = NativeHost(ROOT, Path(task_tmp) / "report-data")
        host.create(name=f"p2-{name}")
        with host:
            context = browser.new_context(
                viewport={"width": 1440, "height": 1000},
                accept_downloads=True,
                permissions=["clipboard-read", "clipboard-write"],
            )
            page = context.new_page()
            page.add_init_script(P2_INSTRUMENTATION)
            page.on("pageerror", lambda error: errors.append(f"pageerror: {error}"))
            page.on("console", lambda message: errors.append(f"console: {message.text}") if message.type == "error" else None)
            page.on("requestfailed", lambda request: errors.append(f"request: {request.url} · {request.failure}"))
            receipt = {"task": name, "status": "FAIL", "checks": {}}
            try:
                load_editor(page, host, f"p2-{name}")
                ready(page)
                details = fn(page, metrics, task_out, image_path)
                details["viewport"] = viewport_probe(page, task_out, name)
                receipt.update(status="PASS", checks=details)
            except Exception as exc:
                receipt.update(error=f"{type(exc).__name__}: {exc}")
                try:
                    page.screenshot(path=str(task_out / "failure.png"), full_page=False)
                except Exception:
                    pass
            finally:
                receipt["metrics"] = common_receipt(page, metrics, started, errors, task_out, name, friction)
                receipt["browser_version"] = browser.version
                (task_out / "receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                context.close()
            return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--only", default="", help="Run one task key or task name")
    args = parser.parse_args()
    out = args.output.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    image_path = out / "benchmark-image.png"
    image = Image.new("RGB", (240, 150), "#145a86")
    ImageDraw.Draw(image).rectangle((35, 30, 180, 115), fill="#f2ca52")
    image.save(image_path)
    report = {
        "status": "FAIL",
        "scope": "finite P2 real-work usability benchmark; native NiceGUI; fresh isolated report directory per task",
        "method": "Primary interactions count visible click/select/double-click actions; typing is excluded. No model writes are used.",
        "source_sha256": hashlib.sha256((ROOT / "company_ui/products/visualizer/assets/integrated_editor.mjs").read_bytes()).hexdigest(),
        "tasks": [],
        "browser_surface": "Native Playwright harness; in-app browser connection unavailable in this session.",
    }
    with sync_playwright() as playwright:
        executable = os.environ.get("VISEMBLER_BROWSER") or shutil.which("chromium")
        launch = {"headless": True}
        if executable:
            launch.update(executable_path=executable, args=["--no-sandbox"])
        browser = playwright.chromium.launch(**launch)
        selected = []
        for key, (name, fn, friction) in TASKS.items():
            if not args.only or args.only.casefold() in {key.casefold(), name.casefold()}:
                selected.append((key, name, fn, friction))
        if not selected:
            parser.error("--only matched no task")
        for key, name, fn, friction in selected:
            receipt = run_task(browser, name, fn, friction, out, image_path)
            receipt["key"] = key
            report["tasks"].append(receipt)
            print(key, receipt["status"], receipt.get("error", "")[:180], flush=True)
        browser.close()
    report["passed"] = sum(task["status"] == "PASS" for task in report["tasks"])
    report["total"] = len(report["tasks"])
    report["status"] = "PASS" if report["passed"] == report["total"] else "FAIL"
    (out / "p2-benchmark.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "passed": report["passed"], "total": report["total"], "output": str(out)}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
