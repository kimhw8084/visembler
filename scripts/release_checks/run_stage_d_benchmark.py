"""Measure the five Stage D repeat-report workflows on fresh native hosts.

This is deliberately a measurement harness.  It counts visible primary
interactions and records the actual elapsed time; it does not write report
models behind the browser or compare against an unmeasured external tool.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from editor_host import NativeHost, load_editor  # noqa: E402
from run_p2_benchmark import (  # noqa: E402
    add_element,
    common_receipt,
    edit_field,
    entry,
    export_current,
    field_id,
    model,
    open_new_report,
    paste_data,
    P2_INSTRUMENTATION,
    primary_click,
    primary_locator_click,
    primary_select,
    ready,
    reload_and_assert,
    select_component,
    settled,
    task_c,
    task_d,
    task_e,
    viewport_probe,
)


def task_1(page, metrics, out, image_path):
    """New process-health report: paste, profile, create a full structure."""
    text = (
        "LOT\tTOOL\tCHAMBER\tTIMESTAMP\tMEASUREMENT\tTARGET\tSTATUS\n"
        "L001\tETCH-01\tC1\t2026-08-01\t98.2\t100\tRUN\n"
        "L002\tETCH-01\tC1\t2026-08-02\t97.8\t100\tRUN\n"
        "L003\tETCH-02\tC2\t2026-08-03\t101.1\t100\tHOLD\n"
        "L004\tETCH-02\tC2\t2026-08-04\t99.4\t100\tRUN"
    )
    open_new_report(page, metrics, "Blank canvas")
    primary_click(page, metrics, "#stageDIntakeBtn")
    page.locator("#stageDText").fill(text)
    page.locator('[data-stage-d-action="full-report"]').wait_for(timeout=10000)
    primary_click(page, metrics, '[data-stage-d-action="full-report"]')
    settled(page)
    current = model(page)
    assert len(current["datasets"]) == 1 and len(current["items"]) >= 3
    assert any(item.get("element") in {"Line Chart", "SPC Control Chart", "Vertical Bar"} for item in current["items"])
    export = export_current(page, metrics, out, "task-1-process-health")
    reload_and_assert(page, {}, None)
    return {"export": export, "profiled_and_structured": True, "raw_json_edits": 0}


def task_2(page, metrics, out, image_path):
    """Repeat weekly operations report using refresh and the dedicated hub."""
    open_new_report(page, metrics, "Operations Review")
    source = "LOT\tMEASURE\tSTATUS\nL001\t98\tRun\nL002\t97\tHold\nL003\t101\tRun"
    table_id = paste_data(page, metrics, source, "table")
    select_component(page, metrics, table_id)
    page.locator('[data-refresh-dataset]').wait_for(timeout=10000)
    primary_click(page, metrics, '[data-refresh-dataset]')
    page.locator("#refreshDataText").fill("LOT\tMEASURE\tSTATUS\nL001\t99\tRun\nL002\t98\tRun\nL003\t100\tRun")
    page.locator("#refreshLinked").wait_for(state="visible", timeout=15000)
    primary_click(page, metrics, "#refreshLinked")
    page.locator("#genericModal.show").wait_for(state="hidden", timeout=15000)
    settled(page)
    primary_locator_click(metrics, page.locator('.cui-visualizer-reportbar button').filter(has_text="Duplicate"))
    settled(page)
    title = page.get_by_label("Report title")
    title.fill("Operations Review Week 2")
    title.press("Tab")
    settled(page)
    metrics["primary_clicks"] += 1
    manage = page.locator('.cui-visualizer-reportbar button').filter(has_text="Manage")
    manage.wait_for(state="visible", timeout=10000)
    manage.evaluate("node => node.click()")
    page.locator(".cui-report-hub").wait_for(timeout=15000)
    primary_click(page, metrics, 'button:has-text("List")')
    page.locator(".cui-report-list").wait_for(timeout=10000)
    original = page.locator('.cui-report-card').filter(has=page.locator('input[value="Operations Review"]')).first
    original.wait_for(timeout=10000)
    primary_locator_click(metrics, original.locator('button').filter(has_text="Move to trash"))
    dialog = page.locator('.q-dialog:visible')
    dialog.get_by_text("Move to trash", exact=True).click()
    page.wait_for_timeout(180)
    toolbar_fields = page.locator('.cui-report-hub-toolbar .q-field')
    primary_locator_click(metrics, toolbar_fields.nth(2))
    page.locator('.q-menu:visible .q-item').get_by_text("Trash", exact=True).click()
    trash_card = page.locator('.cui-report-card').filter(has_text="Operations Review").first
    trash_card.wait_for(timeout=10000)
    primary_locator_click(metrics, trash_card.locator('button').filter(has_text="Restore"))
    page.wait_for_timeout(240)
    primary_locator_click(metrics, toolbar_fields.nth(2))
    page.locator('.q-menu:visible .q-item').get_by_text("Active + trash", exact=True).click()
    restored = page.locator('.cui-report-card').filter(has=page.locator('input[value="Operations Review"]')).first
    restored.wait_for(timeout=10000)
    primary_locator_click(metrics, restored.locator('button').filter(has_text="History"))
    page.locator('.cui-history-panel').wait_for(timeout=10000)
    checkpoint = page.locator('input[placeholder="Before review"]').first
    checkpoint.wait_for(state="visible", timeout=10000)
    if checkpoint.count():
        checkpoint.fill("Weekly review complete")
        checkpoint.press("Tab")
        checkpoint_button=page.locator('button:has-text("Save checkpoint")').first
        page.wait_for_function("button=>!button.disabled",arg=checkpoint_button.element_handle(),timeout=10000)
        primary_locator_click(metrics,checkpoint_button)
        page.locator('.cui-history-card').filter(has_text='checkpoint').first.wait_for(timeout=10000)
    return {"refreshed": True, "report_lifecycle": True, "hub_list_view": True, "history_inspected": True, "checkpoint_requested": True, "raw_json_edits": 0}


def task_3(page, metrics, out, image_path):
    """RCA report from process steps, evidence image, and events."""
    open_new_report(page, metrics, "Investigation / RCA")
    flow_id = "c3"
    select_component(page, metrics, flow_id)
    edit_field(page, "#iNodes", "Detect\nAnalyze\nContain\nVerify")
    edit_field(page, "#iEdges", "Detect -> Analyze\nAnalyze -> Contain\nContain -> Verify")
    primary_select(metrics, page.locator("#iDirection"), "right")
    edit_field(page, "#iEdgeLabel", "handoff")
    assert page.locator(f'.component[data-id="{flow_id}"] .diagram-edge-label').count() >= 1
    timeline_id = add_element(page, metrics, "Event Timeline")
    image_id = add_element(page, metrics, "Image + Caption")
    select_component(page, metrics, image_id)
    page.locator("#iImageFile").set_input_files(str(image_path))
    settled(page)
    edit_field(page, "#iAlt", "RCA evidence image")
    edit_field(page, "#iCaption", "Pressure signature capture")
    select_component(page, metrics, "c1")
    primary_click(page, metrics, '[data-mode="guided"]')
    settled(page)
    reload_and_assert(page, {"element": "Process Flow"}, flow_id)
    export = export_current(page, metrics, out, "task-3-rca")
    return {"export": export, "edge_label": "handoff", "evidence_image": True, "timeline_id": timeline_id, "raw_json_edits": 0}


def task_4(page, metrics, out, image_path):
    """Wafer investigation with mapped identity and reusable evidence."""
    return task_c(page, metrics, out, image_path)


def task_5(page, metrics, out, image_path):
    """Executive summary from text plus chart data, then one-click cleanup."""
    open_new_report(page, metrics, "Executive Brief")
    page.locator(".q-dialog:visible").wait_for(state="hidden", timeout=15000)
    page.locator("#stageDIntakeBtn").wait_for(state="visible", timeout=15000)
    primary_click(page, metrics, "#stageDIntakeBtn")
    page.locator("#stageDText").fill("Weekly process health improved after chamber containment.")
    primary_click(page, metrics, '[data-stage-d-action="create"]')
    settled(page)
    chart_text = "TIMESTAMP\tMEASUREMENT\n2026-08-01\t97.2\n2026-08-02\t98.5\n2026-08-03\t99.1\n2026-08-04\t99.4"
    chart_id = "c2"
    select_component(page,metrics,chart_id)
    primary_click(page,metrics,"#pasteDataBtn")
    page.locator("#dataFirstText").fill(chart_text)
    replace=page.locator("#dataFirstReplace")
    replace.wait_for(state="visible",timeout=15000)
    primary_locator_click(metrics,replace)
    page.locator("#genericModal.show").wait_for(state="hidden",timeout=15000)
    settled(page)
    select_component(page, metrics, chart_id)
    primary_click(page, metrics, "#stageDCleanBtn")
    settled(page)
    primary_click(page, metrics, "#stageDFitBtn")
    settled(page)
    export = export_current(page, metrics, out, "task-5-executive-summary")
    return {"export": export, "clean_layout": True, "text_and_metrics": True, "raw_json_edits": 0}


TASKS = {
    "1": ("process-health-from-data", task_1, [
        "The data-first flow still requires one explicit creation choice after profiling.",
        "Blueprint-level structure is automatic once the field profile is accepted.",
        "Export remains an explicit final action for reviewability.",
    ]),
    "2": ("repeat-weekly-operations", task_2, [
        "Report reuse still crosses the report lifecycle surface for duplicate and restore.",
        "Shared-data operations remain explicit to protect linked visuals.",
        "A checkpoint is a deliberate review action before export.",
    ]),
    "3": ("rca-evidence-report", task_3, [
        "Process, event, and evidence items are still selected in separate authoring contexts.",
        "Diagram refinement remains a focused inspector interaction.",
        "Evidence metadata is intentionally explicit for accessibility.",
    ]),
    "4": ("wafer-investigation", task_4, [
        "Wafer identity roles remain distributed across the data binding controls.",
        "Evidence grouping is a deliberate multi-selection action.",
        "Portable import/export is retained as a separate verification step.",
    ]),
    "5": ("executive-summary", task_5, [
        "Text and chart evidence are created through two content-first choices.",
        "Clean Layout and Fit Report remove manual geometry work.",
        "The final export remains explicit and observable.",
    ]),
}


def visual_quality(page):
    """Measure product-visible quality; wrappers alone do not count as content."""
    return page.evaluate(r"""()=>{
      const root=document.querySelector('.cui-visualizer-root');
      if(!root)return {surface:'report-hub',occupied_area_ratio:null,elements:[],empty_error_state_count:0,clipping_overflow_count:0,primary_evidence_area_share:null,context_toolbar:null};
      const hull=document.querySelector('#hull'),nodes=[...document.querySelectorAll('.component')],hullRect=hull?.getBoundingClientRect();
      const area=r=>Math.max(0,r.width)*Math.max(0,r.height),union=rects=>rects.reduce((a,r)=>a?({left:Math.min(a.left,r.left),top:Math.min(a.top,r.top),right:Math.max(a.right,r.right),bottom:Math.max(a.bottom,r.bottom),width:Math.max(a.right,r.right)-Math.min(a.left,r.left),height:Math.max(a.bottom,r.bottom)-Math.min(a.top,r.top)}):r,null);
      const selector=engine=>engine==='CoreChartEngine'||engine==='EngineeringChartEngine'?'.cs-chart-svg':engine==='WaferFabEngine'?'.cs-wafer-svg>circle,.cs-wafer-svg [data-wafer-die]':engine==='DiagramEngine'?'.diagram-studio-static [data-diagram-node],.diagram-studio-static [data-diagram-edge]':engine==='TimelineEngine'?'[data-timeline-event]':engine==='ImageMediaEngine'?'.image-stage,.captioned-image-live,.screenshot-frame-live':engine==='TableEngine'?'.table-frame,.table-wrap':engine==='MetricEngine'?'.metric-value,.hero-kpi,.status-hero,.metric-ring-live':'.card-body>*';
      const elements=nodes.map(node=>{const card=node.getBoundingClientRect(),contentRoot=node.querySelector('.c-content')||node,engine=node.querySelector('[data-engine]')?.dataset.engine||'',parts=[...node.querySelectorAll(selector(engine))].map(value=>value.getBoundingClientRect()).filter(value=>value.width>0&&value.height>0),inside=union(parts),role=window.CompanyUIVisualizerBridge.state().model.items.find(item=>item.id===node.dataset.id)?.message_role||'',box=value=>{const rect=value?.getBoundingClientRect();return rect?{width:rect.width,height:rect.height}:null;},offenders=[...contentRoot.querySelectorAll('*')].filter(value=>value.scrollWidth>value.clientWidth+1||value.scrollHeight>value.clientHeight+1).slice(0,6).map(value=>({tag:value.tagName,class:value.className?.baseVal??value.className,client_width:value.clientWidth,scroll_width:value.scrollWidth,client_height:value.clientHeight,scroll_height:value.scrollHeight})),dominant=inside?Math.max(inside.width/Math.max(1,card.width),inside.height/Math.max(1,card.height)):0;return {id:node.dataset.id,engine,role,card_area:area(card),visual_area:inside?area(inside):0,visual_utilization:inside?area(inside)/Math.max(1,area(card)):0,dominant_axis_share:dominant,overflow:contentRoot.scrollWidth>contentRoot.clientWidth+1||contentRoot.scrollHeight>contentRoot.clientHeight+1,overflow_metrics:{client_width:contentRoot.clientWidth,scroll_width:contentRoot.scrollWidth,client_height:contentRoot.clientHeight,scroll_height:contentRoot.scrollHeight},overflow_offenders:offenders,renderer_boxes:{content:box(node.querySelector('.integrated-element-content')),body:box(node.querySelector('.card-body')),plot:box(node.querySelector('.cs-static-chart')),svg:box(node.querySelector('.cs-chart-svg')),meaningful:inside?{width:inside.width,height:inside.height}:null}};});
      const occupied=elements.reduce((sum,value)=>sum+value.card_area,0)/Math.max(1,area(hullRect||{width:1,height:1}));
      const text=document.querySelector('#componentLayer')?.innerText||'',empty=(text.match(/Add chart data|Diagram data needs review|X unmapped|Y unmapped|No mapped dies/gi)||[]).length;
      const primary=elements.filter(value=>value.role==='Primary Evidence'),occupiedCards=elements.reduce((sum,value)=>sum+value.card_area,0),primaryShare=primary.length?primary.reduce((sum,value)=>sum+value.card_area,0)/Math.max(1,occupiedCards):null,primaryUtilization=primary.length?Math.min(...primary.map(value=>value.visual_utilization)):null;
      const context=document.querySelector('#context.show'),selected=document.querySelector('.component.selected');let contextToolbar=null;if(context&&selected){const a=context.getBoundingClientRect(),b=selected.getBoundingClientRect(),dx=Math.max(0,b.left-a.right,a.left-b.right),dy=Math.max(0,b.top-a.bottom,a.top-b.bottom);contextToolbar={distance:Math.hypot(dx,dy),visible:a.width>0&&a.height>0};}
      return {surface:'editor',occupied_area_ratio:occupied,element_count:elements.length,elements,empty_error_state_count:empty,clipping_overflow_count:elements.filter(value=>value.overflow).length,primary_evidence_area_share:primaryShare,primary_evidence_min_visual_utilization:primaryUtilization,plotted_marks:document.querySelectorAll('[data-chart-point]').length,wafer_dies:document.querySelectorAll('[data-wafer-die]').length,diagram_errors:(text.match(/Diagram data needs review/gi)||[]).length,context_toolbar:contextToolbar};
    }""")


def assert_quality(name, quality, checkpoint_exists):
    if quality['surface']=='report-hub':
        if name=='repeat-weekly-operations' and not checkpoint_exists: raise AssertionError('requested checkpoint was not created')
        return
    if quality['empty_error_state_count']:
        raise AssertionError(f"{quality['empty_error_state_count']} product empty/error states remain")
    required_occupied = .52 if quality.get('element_count', len(quality.get('elements', []))) >= 5 else .42 if quality.get('element_count', len(quality.get('elements', []))) >= 3 else .20
    if quality['occupied_area_ratio'] < required_occupied:
        raise AssertionError(f"excessive blank report area: occupied ratio {quality['occupied_area_ratio']:.3f} < {required_occupied:.2f}")
    if quality['clipping_overflow_count']:
        raise AssertionError(f"{quality['clipping_overflow_count']} clipping/overflow conditions")
    if quality['primary_evidence_min_visual_utilization'] is not None and quality['primary_evidence_min_visual_utilization'] < .28:
        raise AssertionError(f"primary evidence does not use its allocated card: {quality['primary_evidence_min_visual_utilization']:.3f} < 0.28")
    for element in quality.get('elements', []):
        if element['engine']=='WaferFabEngine' and element['visual_utilization'] < .24:
            raise AssertionError(f"wafer visual utilization {element['visual_utilization']:.3f} < 0.24")
        if element['engine']=='DiagramEngine' and element['visual_utilization'] < .22 and element['dominant_axis_share'] < .70:
            raise AssertionError(f"diagram meaningful use {element['visual_utilization']:.3f} / dominant {element['dominant_axis_share']:.3f} is too small")
        if element['engine']=='TimelineEngine' and element['dominant_axis_share'] < .70:
            raise AssertionError(f"timeline dominant-axis share {element['dominant_axis_share']:.3f} < 0.70")
    if name=='rca-evidence-report' and quality['diagram_errors']: raise AssertionError('RCA contains diagram error state')
    if name=='wafer-investigation' and quality['wafer_dies'] < 1: raise AssertionError('Wafer Investigation contains no observed dies')
    if name in {'process-health-from-data','executive-summary'} and quality['plotted_marks'] < 1: raise AssertionError('compatible chart data produced no plotted marks')
    if quality['context_toolbar'] and (not quality['context_toolbar']['visible'] or quality['context_toolbar']['distance'] > 20): raise AssertionError('selection context toolbar is detached')


def run_task(browser, name, fn, friction, root, image_path):
    task_out = root / name
    task_out.mkdir(parents=True, exist_ok=True)
    metrics = {"primary_clicks": 0}
    errors = []
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix=f"visembler-stage-d-{name}-") as task_tmp:
        host = NativeHost(ROOT, Path(task_tmp) / "report-data")
        host.create(name=f"stage-d-{name}")
        with host:
            context = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True, permissions=["clipboard-read", "clipboard-write"])
            page = context.new_page()
            page.add_init_script(P2_INSTRUMENTATION)
            page.on("pageerror", lambda error: errors.append(f"pageerror: {error}"))
            page.on("console", lambda message: errors.append(f"console: {message.text}") if message.type == "error" else None)
            page.on("requestfailed", lambda request: errors.append(f"request: {request.url} · {request.failure}"))
            receipt = {"task": name, "status": "FAIL", "checks": {}}
            try:
                load_editor(page, host, f"stage-d-{name}")
                ready(page)
                result = fn(page, metrics, task_out, image_path)
                result["viewport"] = viewport_probe(page, task_out, name)
                quality=visual_quality(page)
                checkpoint_exists=any(any(entry.get('checkpoint') for entry in host.repository.list_history(record.report_id)) for record in host.repository.list())
                quality['checkpoint_created']=checkpoint_exists
                assert_quality(name,quality,checkpoint_exists)
                result['visual_quality']=quality
                receipt.update(status="PASS", checks=result)
            except Exception as exc:
                receipt["error"] = f"{type(exc).__name__}: {exc}"
                try:
                    quality=visual_quality(page)
                    quality['checkpoint_created']=any(any(entry.get('checkpoint') for entry in host.repository.list_history(record.report_id)) for record in host.repository.list())
                    receipt['checks']['visual_quality']=quality
                except Exception:
                    pass
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--only", default="")
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    image_path = output / "benchmark-image.png"
    image = Image.new("RGB", (240, 150), "#145a86")
    ImageDraw.Draw(image).rectangle((35, 30, 180, 115), fill="#f2ca52")
    image.save(image_path)
    report = {
        "status": "FAIL",
        "scope": "finite Stage D time-saving benchmark; fresh native report directory per task",
        "method": "Primary interactions count visible click/select/double-click actions; typing is excluded. No model writes are used.",
        "source_sha256": hashlib.sha256((ROOT / "company_ui/products/visualizer/assets/integrated_editor.mjs").read_bytes()).hexdigest(),
        "tasks": [],
        "external_dependencies": {"powerpoint": False, "external_chart_authoring": False, "external_diagram_authoring": False},
    }
    with sync_playwright() as playwright:
        executable = os.environ.get("VISEMBLER_BROWSER") or shutil.which("chromium")
        launch = {"headless": True}
        if executable:
            launch.update(executable_path=executable, args=["--no-sandbox"])
        browser = playwright.chromium.launch(**launch)
        for key, (name, fn, friction) in TASKS.items():
            if args.only and args.only.casefold() not in {key.casefold(), name.casefold()}:
                continue
            receipt = run_task(browser, name, fn, friction, output, image_path)
            receipt["key"] = key
            report["tasks"].append(receipt)
            print(key, receipt["status"], receipt.get("error", "")[:180], flush=True)
        browser.close()
    report["passed"] = sum(item["status"] == "PASS" for item in report["tasks"])
    report["total"] = len(report["tasks"])
    report["status"] = "PASS" if report["total"] == 5 and report["passed"] == report["total"] else "FAIL"
    (output / "stage-d-benchmark.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "passed": report["passed"], "total": report["total"], "output": str(output)}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
