#!/usr/bin/env python3
"""Explicit receipt for the final, narrow visual cleanup (FV001-FV041)."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from editor_host import NativeHost  # noqa: E402
from native_common import BrowserEvents, browser_kwargs, ready, write_json  # noqa: E402
from run_final_visual_remediation_acceptance import fixture, report_model  # noqa: E402

FROZEN = "d8ebd4378f01b7c52a7a4be57c578c22adf29b899cc08a370cf084881195343e"
NAMES = {
    "FV001": "Preview removes selected chrome",
    "FV002": "Preview hides resize handles",
    "FV003": "Preview hides context toolbar",
    "FV004": "Preview hides editor-only controls",
    "FV005": "Preview contains no chart or diagram edit action",
    "FV006": "Preview report content is not manipulable",
    "FV007": "Exit Preview restores editor behavior",
    "FV008": "Preview contract covers six representative compositions",
    "FV009": "Event Timeline renders five of five events",
    "FV010": "Event Timeline spans its dominant axis",
    "FV011": "Event Timeline has no clipping at 1024",
    "FV012": "Event Timeline has no clipping at 768",
    "FV013": "Milestone Rail has no silent event loss",
    "FV014": "Sequence Strip has no silent event loss",
    "FV015": "Wafer Investigation occupies at least 42 percent",
    "FV016": "Wafer visual uses at least 24 percent of its card",
    "FV017": "RCA report occupies at least 52 percent",
    "FV018": "Process Flow uses its card meaningfully",
    "FV019": "RCA timelines span their dominant axis",
    "FV020": "Process Health occupies at least 42 percent",
    "FV021": "Executive Summary occupies at least 52 percent",
    "FV022": "Smart to Guided retains professional geometry",
    "FV023": "Free geometry remains unchanged",
    "FV024": "Final reports contain no empty or error placeholders",
    "FV025": "Shapes control is initially visible at 768",
    "FV026": "Inspector control is initially visible at 768",
    "FV027": "Tablet panel controls need no horizontal toolbar scroll",
    "FV028": "Shapes opens the palette drawer",
    "FV029": "Inspector opens the inspector drawer",
    "FV030": "Diagram drawers provide backdrop, close, and Escape",
    "FV031": "Diagram panel controls are accessible at 390",
    "FV032": "Stage A regression",
    "FV033": "Stage B regression",
    "FV034": "Stage C regression",
    "FV035": "Stage D regression",
    "FV036": "Prior final visual remediation regression",
    "FV037": "All 49 production element workflows",
    "FV038": "Data workflows",
    "FV039": "Product contract audit",
    "FV040": "No unexpected browser errors",
    "FV041": "Frozen connector unchanged",
}


def visible_count(page, selector: str) -> int:
    return page.locator(selector).evaluate_all(
        "nodes => nodes.filter(node => { const s=getComputedStyle(node),r=node.getBoundingClientRect(); return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0; }).length"
    )


def inside_viewport(page, selector: str) -> tuple[bool, dict]:
    box = page.locator(selector).first.bounding_box()
    viewport = page.viewport_size
    return bool(box and box["x"] >= 0 and box["y"] >= 0 and box["x"] + box["width"] <= viewport["width"] and box["y"] + box["height"] <= viewport["height"]), box or {}


def timeline_probe(page) -> dict:
    return page.evaluate("""()=>{
      const group=document.querySelector('[data-timeline-events]'),events=[...document.querySelectorAll('[data-timeline-event]')],card=document.querySelector('.component');
      if(!group||!card||!events.length)return {count:events.length,dominant:0,clipped:true};
      const box=card.getBoundingClientRect(),rects=events.map(node=>node.getBoundingClientRect()),centers=rects.map(r=>({x:r.left+r.width/2,y:r.top+r.height/2}));
      const x=(Math.max(...centers.map(p=>p.x))-Math.min(...centers.map(p=>p.x)))/Math.max(1,box.width),y=(Math.max(...centers.map(p=>p.y))-Math.min(...centers.map(p=>p.y)))/Math.max(1,box.height);
      return {count:events.length,dominant:Math.max(x,y),x,y,clipped:rects.some(r=>r.left<box.left-2||r.right>box.right+2||r.top<box.top-2||r.bottom>box.bottom+2)};
    }""")


def benchmark_quality(receipt: dict, name: str) -> dict:
    task = next((value for value in receipt.get("tasks", []) if value.get("task") == name), {})
    return task.get("checks", {}).get("visual_quality", {})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--skip-regressions", action="store_true")
    parser.add_argument("--skip-benchmark", action="store_true")
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    rows = {key: {"id": key, "name": name, "status": "FAIL", "error": "not executed"} for key, name in NAMES.items()}
    receipt = {"scope": "final narrow visual cleanup", "checks": [], "unexpected_errors": [], "preview": [], "timelines": [], "diagram_tablet": []}

    def record(key: str, passed: bool, detail=""):
        rows[key] = {"id": key, "name": NAMES[key], "status": "PASS" if passed else "FAIL"}
        if detail:
            rows[key]["detail" if passed else "error"] = str(detail)[:1000]

    def attempt(key: str, check):
        try:
            detail = check()
            record(key, True, detail or "")
        except Exception as error:
            record(key, False, error)

    try:
        milestones = [{"label": label, "date": f"Sep {index}"} for index, label in enumerate(("Detect", "Analyze", "Contain", "Verify", "Release"), 1)]
        preview_entries = [
            fixture("CoreChartEngine", "Line Chart", 1),
            fixture("DiagramEngine", "Process Flow", 1),
            fixture("TimelineEngine", "Event Timeline", 1),
            fixture("WaferFabEngine", "Wafer Map", 1),
            fixture("TextEngine", "Body Narrative", 1),
        ]
        preview_entries[2]["milestones"] = milestones
        mixed = []
        for index, source in enumerate(preview_entries, 1):
            value = {**source, "id": f"mixed-{index}", "order": index - 1, "z": index}
            mixed.append(value)
        with tempfile.TemporaryDirectory(prefix="visembler-final-visual-cleanup-") as temp:
            host = NativeHost(ROOT, Path(temp) / "data")
            preview_reports = [(entry["element"], host.create(model=report_model(entry), name=f"preview-{index}")) for index, entry in enumerate(preview_entries)]
            preview_reports.append(("mixed", host.create(model=report_model(mixed[0], items=mixed), name="preview-mixed")))
            timeline_ids = {}
            for element in ("Event Timeline", "Milestone Rail", "Sequence Strip"):
                value = fixture("TimelineEngine", element, 1)
                value["milestones"] = milestones
                timeline_ids[element] = host.create(model=report_model(value), name=element.lower().replace(" ", "-"))
            free = fixture("TextEngine", "Body Narrative", 1)
            free.update(x=77, y=91, w=438, h=233)
            free_id = host.create(model=report_model(free, mode="free"), name="free-geometry")
            smart_items = [fixture("WaferFabEngine", "Wafer Map", 1), fixture("ImageMediaEngine", "Image + Caption", 2), fixture("EvidenceCompositeEngine", "Evidence Card", 3)]
            smart_id = host.create(model=report_model(smart_items[0], items=smart_items), name="smart-guided")
            diagram_id = host.create(model=report_model(fixture("DiagramEngine", "Process Flow", 1)), name="diagram-tablet")

            with host, sync_playwright() as playwright:
                browser = playwright.chromium.launch(**browser_kwargs())
                context = browser.new_context(viewport={"width": 1440, "height": 900})
                page = context.new_page()
                events = BrowserEvents()
                events.attach(page)

                preview_passes = []
                for label, report_id in preview_reports:
                    page.goto(f"{host.url}/visualizer?report={quote(report_id)}", wait_until="domcontentloaded")
                    ready(page, require_settled=True)
                    component = page.locator(".component").first
                    component.click()
                    before = page.evaluate("()=>JSON.stringify(CompanyUIVisualizerBridge.state().model)")
                    page.locator("#previewBtn").click()
                    page.locator(".cui-visualizer-root.preview-mode").wait_for()
                    page.wait_for_timeout(80)
                    chrome = page.evaluate("""()=>{const node=document.querySelector('.component.selected'),s=node&&getComputedStyle(node);return {outline:s?.outlineStyle,outlineWidth:s?.outlineWidth,boxShadow:s?.boxShadow,border:s?.borderColor};}""")
                    no_selection = chrome.get("outline") in {"none", ""} or chrome.get("outlineWidth") == "0px"
                    no_resize = visible_count(page, ".resize-h") == 0
                    no_context = visible_count(page, ".context") == 0
                    no_editor = visible_count(page, "[data-editor-only]") == 0
                    clean_text = "Edit chart" not in page.locator("#componentLayer").inner_text() and "Edit Diagram" not in page.locator("#componentLayer").inner_text()
                    box = component.bounding_box()
                    if box:
                        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                        page.mouse.down()
                        page.mouse.move(box["x"] + box["width"] / 2 + 60, box["y"] + box["height"] / 2 + 40)
                        page.mouse.up()
                    after_drag = page.evaluate("()=>JSON.stringify(CompanyUIVisualizerBridge.state().model)")
                    page.locator("#previewFitWidth").click()
                    page.locator("#previewFitPage").click()
                    page.locator("#previewExit").click()
                    page.wait_for_function("()=>!document.querySelector('.cui-visualizer-root').classList.contains('preview-mode')")
                    after_exit = page.evaluate("()=>JSON.stringify(CompanyUIVisualizerBridge.state().model)")
                    restored = page.locator(".component.selected").count() == 1 and visible_count(page, ".resize-h") > 0
                    result = {"composition": label, "selection": no_selection, "resize": no_resize, "context": no_context, "editor_only": no_editor, "edit_text": clean_text, "immutable": before == after_drag == after_exit, "restored": restored}
                    receipt["preview"].append(result)
                    preview_passes.append(result)
                attempt("FV001", lambda: (_ for _ in ()).throw(AssertionError(receipt["preview"])) if not all(value["selection"] for value in preview_passes) else None)
                attempt("FV002", lambda: (_ for _ in ()).throw(AssertionError(receipt["preview"])) if not all(value["resize"] for value in preview_passes) else None)
                attempt("FV003", lambda: (_ for _ in ()).throw(AssertionError(receipt["preview"])) if not all(value["context"] for value in preview_passes) else None)
                attempt("FV004", lambda: (_ for _ in ()).throw(AssertionError(receipt["preview"])) if not all(value["editor_only"] for value in preview_passes) else None)
                attempt("FV005", lambda: (_ for _ in ()).throw(AssertionError(receipt["preview"])) if not all(value["edit_text"] for value in preview_passes) else None)
                attempt("FV006", lambda: (_ for _ in ()).throw(AssertionError(receipt["preview"])) if not all(value["immutable"] for value in preview_passes) else None)
                attempt("FV007", lambda: (_ for _ in ()).throw(AssertionError(receipt["preview"])) if not all(value["restored"] for value in preview_passes) else None)
                record("FV008", len(preview_passes) == 6 and all(all(value[key] for key in ("selection", "resize", "context", "editor_only", "edit_text", "immutable", "restored")) for value in preview_passes), receipt["preview"])

                timeline_results = {}
                for element, report_id in timeline_ids.items():
                    page.set_viewport_size({"width": 1440, "height": 900})
                    page.goto(f"{host.url}/visualizer?report={quote(report_id)}", wait_until="domcontentloaded")
                    ready(page, require_settled=True)
                    probes = {1440: timeline_probe(page)}
                    if element == "Event Timeline":
                        for width in (1024, 768):
                            page.set_viewport_size({"width": width, "height": 820})
                            page.wait_for_timeout(120)
                            probes[width] = timeline_probe(page)
                    timeline_results[element] = probes
                receipt["timelines"] = timeline_results
                event = timeline_results["Event Timeline"]
                record("FV009", event[1440]["count"] == 5, event)
                record("FV010", min(value["dominant"] for value in event.values()) >= .70, event)
                record("FV011", not event[1024]["clipped"], event[1024])
                record("FV012", not event[768]["clipped"], event[768])
                record("FV013", timeline_results["Milestone Rail"][1440]["count"] == 5, timeline_results["Milestone Rail"])
                record("FV014", timeline_results["Sequence Strip"][1440]["count"] == 5, timeline_results["Sequence Strip"])

                page.set_viewport_size({"width": 1440, "height": 900})
                page.goto(f"{host.url}/visualizer?report={quote(smart_id)}", wait_until="domcontentloaded")
                ready(page, require_settled=True)
                smart = page.evaluate("()=>window.__VIZ_PROD__.layoutRects().map(({id,x,y,w,h})=>({id,x,y,w,h}))")
                page.locator('[data-mode="guided"]').click()
                page.wait_for_timeout(120)
                guided = page.evaluate("()=>CompanyUIVisualizerBridge.state().model.items.map(({id,x,y,w,h})=>({id,x,y,w,h}))")
                record("FV022", smart == guided and sum(value["w"] * value["h"] for value in guided) / (1200 * 900) >= .42, {"smart": smart, "guided": guided})

                page.goto(f"{host.url}/visualizer?report={quote(free_id)}", wait_until="domcontentloaded")
                ready(page, require_settled=True)
                free_before = page.evaluate("()=>CompanyUIVisualizerBridge.state().model.items.map(({id,x,y,w,h})=>({id,x,y,w,h}))")
                page.set_viewport_size({"width": 768, "height": 820})
                page.wait_for_timeout(100)
                free_after = page.evaluate("()=>CompanyUIVisualizerBridge.state().model.items.map(({id,x,y,w,h})=>({id,x,y,w,h}))")
                record("FV023", free_before == free_after, {"before": free_before, "after": free_after})

                element_id = host.repository.get(diagram_id).model["items"][0]["id"]
                tablet = {}
                for width in (768, 390):
                    page.set_viewport_size({"width": width, "height": 820})
                    page.goto(f"{host.url}/visualizer/diagram-studio?report={quote(diagram_id)}&element={quote(str(element_id))}", wait_until="domcontentloaded")
                    page.locator('#diagram-studio[data-studio-ready="true"]').wait_for(timeout=20000)
                    page.wait_for_timeout(120)
                    shapes_ok, shapes_box = inside_viewport(page, '[data-action="toggle-palette"]')
                    inspector_ok, inspector_box = inside_viewport(page, '[data-action="toggle-inspector"]')
                    toolbar_layout = page.evaluate("""()=>{const toolbar=document.querySelector('.ds-toolbar'),shell=document.querySelector('.ds-shell'),buttons=[document.querySelector('[data-action="toggle-palette"]'),document.querySelector('[data-action="toggle-inspector"]')],t=toolbar.getBoundingClientRect(),s=shell.getBoundingClientRect(),rects=buttons.map(node=>node.getBoundingClientRect());return {toolbar_overflow:toolbar.scrollWidth>toolbar.clientWidth+1,document_overflow:document.documentElement.scrollWidth>innerWidth+1,controls_in_toolbar:rects.every(rect=>rect.left>=t.left-1&&rect.right<=t.right+1&&rect.top>=t.top-1&&rect.bottom<=t.bottom+1),shell_below_toolbar:s.top>=t.bottom-1,toolbar:{left:t.left,top:t.top,right:t.right,bottom:t.bottom},shell:{top:s.top},buttons:rects.map(rect=>({left:rect.left,top:rect.top,right:rect.right,bottom:rect.bottom}))};}""")
                    page.locator('[data-action="toggle-palette"]').click()
                    page.wait_for_timeout(220)
                    shapes_open = page.locator(".ds-palette.is-open").is_visible() and page.locator("#ds-panel-backdrop").is_visible()
                    close_visible = page.locator('.ds-palette.is-open [data-action="close-panels"]').is_visible()
                    page.keyboard.press("Escape")
                    shapes_closed = not page.locator(".ds-palette.is-open").is_visible()
                    page.locator('[data-action="toggle-inspector"]').click()
                    page.wait_for_timeout(220)
                    inspector_open = page.locator(".ds-inspector.is-open").is_visible() and page.locator("#ds-panel-backdrop").is_visible()
                    page.locator('.ds-inspector.is-open [data-action="close-panels"]').click()
                    inspector_closed = not page.locator(".ds-inspector.is-open").is_visible()
                    tablet[width] = {"shapes_visible": shapes_ok, "shapes_box": shapes_box, "inspector_visible": inspector_ok, "inspector_box": inspector_box, **toolbar_layout, "shapes_open": shapes_open, "inspector_open": inspector_open, "close_visible": close_visible, "escape": shapes_closed, "close": inspector_closed}
                    page.screenshot(path=str(output / f"diagram-studio-{width}.png"), full_page=False)
                receipt["diagram_tablet"] = tablet
                record("FV025", tablet[768]["shapes_visible"], tablet[768])
                record("FV026", tablet[768]["inspector_visible"], tablet[768])
                record("FV027", not tablet[768]["toolbar_overflow"] and not tablet[768]["document_overflow"] and tablet[768]["controls_in_toolbar"] and tablet[768]["shell_below_toolbar"], tablet[768])
                record("FV028", tablet[768]["shapes_open"], tablet[768])
                record("FV029", tablet[768]["inspector_open"], tablet[768])
                record("FV030", tablet[768]["close_visible"] and tablet[768]["escape"] and tablet[768]["close"], tablet[768])
                record("FV031", tablet[390]["shapes_visible"] and tablet[390]["inspector_visible"] and not tablet[390]["toolbar_overflow"] and not tablet[390]["document_overflow"] and tablet[390]["controls_in_toolbar"] and tablet[390]["shell_below_toolbar"] and tablet[390]["shapes_open"] and tablet[390]["inspector_open"], tablet[390])
                receipt["unexpected_errors"] = events.unexpected
                record("FV040", not events.unexpected, events.unexpected[:8])
                context.close()
                browser.close()

        if args.skip_benchmark:
            for key in ("FV015", "FV016", "FV017", "FV018", "FV019", "FV020", "FV021", "FV024"):
                rows[key] = {"id": key, "name": NAMES[key], "status": "NOT_APPLICABLE", "reason": "benchmark intentionally skipped for focused development"}
        else:
            benchmark_dir = output / "benchmark"
            code = subprocess.run([sys.executable, str(ROOT / "scripts/release_checks/run_stage_d_benchmark.py"), "--output", str(benchmark_dir)], cwd=ROOT, timeout=720).returncode
            benchmark = json.loads((benchmark_dir / "stage-d-benchmark.json").read_text())
            receipt["benchmark"] = benchmark
            wafer = benchmark_quality(benchmark, "wafer-investigation")
            rca = benchmark_quality(benchmark, "rca-evidence-report")
            process = benchmark_quality(benchmark, "process-health-from-data")
            executive = benchmark_quality(benchmark, "executive-summary")
            record("FV015", code == 0 and (wafer.get("occupied_area_ratio") or 0) >= .42, wafer)
            wafer_element = next((value for value in wafer.get("elements", []) if value.get("engine") == "WaferFabEngine"), {})
            record("FV016", (wafer_element.get("visual_utilization") or 0) >= .24, wafer_element)
            record("FV017", (rca.get("occupied_area_ratio") or 0) >= .52, rca)
            diagram = next((value for value in rca.get("elements", []) if value.get("engine") == "DiagramEngine"), {})
            record("FV018", (diagram.get("visual_utilization") or 0) >= .22 or (diagram.get("dominant_axis_share") or 0) >= .70, diagram)
            timelines = [value for value in rca.get("elements", []) if value.get("engine") == "TimelineEngine"]
            record("FV019", bool(timelines) and min(value.get("dominant_axis_share") or 0 for value in timelines) >= .70, timelines)
            record("FV020", (process.get("occupied_area_ratio") or 0) >= .42, process)
            record("FV021", (executive.get("occupied_area_ratio") or 0) >= .52, executive)
            qualities = [benchmark_quality(benchmark, name) for name in ("process-health-from-data", "wafer-investigation", "rca-evidence-report", "executive-summary")]
            record("FV024", code == 0 and all(value.get("empty_error_state_count") == 0 for value in qualities), qualities)

        regressions = [
            ("FV032", "run_stage_a_acceptance.py", []),
            ("FV033", "run_diagram_studio_acceptance.py", []),
            ("FV034", "run_chart_studio_acceptance.py", ["--skip-regressions"]),
            ("FV035", "run_stage_d_acceptance.py", ["--skip-regressions"]),
            ("FV036", "run_final_visual_remediation_acceptance.py", ["--skip-regressions", "--skip-benchmark"]),
        ]
        if args.skip_regressions:
            for key, script, _ in regressions:
                rows[key] = {"id": key, "name": NAMES[key], "status": "NOT_APPLICABLE", "reason": f"{script} intentionally deferred"}
            for key in ("FV037", "FV038", "FV039"):
                rows[key] = {"id": key, "name": NAMES[key], "status": "NOT_APPLICABLE", "reason": "release regression intentionally deferred"}
        else:
            for key, script, extra in regressions:
                target = output / script.replace(".py", "")
                command = [sys.executable, str(ROOT / "scripts/release_checks" / script), "--output", str(target), *extra]
                code = subprocess.run(command, cwd=ROOT, timeout=480).returncode
                record(key, code == 0, f"{script} exit {code}")
            element_code = subprocess.run([sys.executable, "scripts/release_checks/run_editor_workflows.py", "--output", str(output / "elements"), "--native"], cwd=ROOT, timeout=480).returncode
            data_code = subprocess.run([sys.executable, "scripts/release_checks/run_data_workflows.py", "--output", str(output / "data"), "--native"], cwd=ROOT, timeout=300).returncode
            contract_code = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_visualizer_product_completion_p0.py", "tests/test_visualizer_final_visual_remediation.py"], cwd=ROOT, timeout=180).returncode
            record("FV037", element_code == 0, f"element workflow exit {element_code}")
            record("FV038", data_code == 0, f"data workflow exit {data_code}")
            record("FV039", contract_code == 0, f"product contract exit {contract_code}")

        frozen = hashlib.sha256((ROOT / "company_ui/products/visualizer/vendor/production_core/core/GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js").read_bytes()).hexdigest()
        record("FV041", frozen == FROZEN, frozen)
    except Exception as error:
        receipt["harness_error"] = str(error)
        receipt["traceback"] = traceback.format_exc()

    receipt["checks"] = [rows[key] for key in NAMES]
    receipt["pass"] = sum(value["status"] == "PASS" for value in receipt["checks"])
    receipt["applicable"] = sum(value["status"] != "NOT_APPLICABLE" for value in receipt["checks"])
    receipt["not_applicable"] = sum(value["status"] == "NOT_APPLICABLE" for value in receipt["checks"])
    receipt["status"] = "PASS" if receipt["pass"] == receipt["applicable"] and not receipt.get("harness_error") else "FAIL"
    path = output / "final-visual-cleanup-acceptance.json"
    write_json(path, receipt)
    print(json.dumps({"status": receipt["status"], "pass": receipt["pass"], "applicable": receipt["applicable"], "not_applicable": receipt["not_applicable"], "path": str(path)}))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
