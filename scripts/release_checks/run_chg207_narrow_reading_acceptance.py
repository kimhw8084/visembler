#!/usr/bin/env python3
"""Native populated-report narrow reading acceptance for CHG-207 R1."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageStat
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from editor_host import NativeHost
from native_common import BrowserEvents, browser_kwargs, ready, write_json


SOURCE_SHA = "5dfdd5eba77a45b63aa2e5290cb7609a573e9efc"
SOURCE_TREE = "d932f22966508ba6fdb630b6f66e1a01818b7b03"
R2_SHA = "7224c0815142557e2362e2ca4e6201e67006126c"
R2_SCREENSHOT = "tests/fixtures/chg207/chg173-r2-supply-chain-reading-320-before.png"
FIXTURE = "tests/fixtures/chg206/whole_report_models.json"
FABRIC_JOB_ID = "CF-044dc968600667a197348544"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _supplemented_supply_model(original: dict) -> dict:
    model = copy.deepcopy(original)
    order = max(int(row.get("order", 0)) for row in model.get("items", [])) + 1
    additions = [
        {
            "id": "chg207-negative", "type": "metric", "engine": "MetricEngine", "element": "Hero KPI",
            "title": "Negative precision case", "value": -1234567.8, "unit": "units",
            "metric_format": {"kind": "number", "precision": 1}, "showTitle": True,
            "section_id": "weak-scenes", "section_title": "Narrow reading edge cases",
            "composition_role": "supporting_evidence", "order": order, "z": order + 1,
        },
        {
            "id": "chg207-zero", "type": "metric", "engine": "MetricEngine", "element": "Hero KPI",
            "title": "Explicit zero precision", "value": 0, "unit": "",
            "metric_format": {"kind": "number", "precision": 3}, "showTitle": True,
            "section_id": "weak-scenes", "section_title": "Narrow reading edge cases",
            "composition_role": "supporting_evidence", "order": order + 1, "z": order + 2,
        },
        {
            "id": "chg207-long-comparison", "type": "comparison", "engine": "ComparisonEngine",
            "element": "Before/After KPI", "title": "Long numeric comparison", "before": 9876543210,
            "after": 12345678901, "unit": "units", "showTitle": True,
            "section_id": "weak-scenes", "section_title": "Narrow reading edge cases",
            "composition_role": "supporting_evidence", "order": order + 2, "z": order + 3,
        },
        {
            "id": "chg207-nonoverflow-table", "type": "table", "engine": "TableEngine",
            "element": "Evidence Table", "title": "Compact evidence", "showTitle": True,
            "customTable": {"headers": ["Supplier", "Part"], "rows": [["Northstar", "A-1"]]},
            "rows": [["Northstar", "A-1"]], "section_id": "weak-scenes",
            "section_title": "Narrow reading edge cases", "composition_role": "detailed_evidence",
            "order": order + 3, "z": order + 4,
        },
    ]
    model["items"].extend(additions)
    model["nextId"] = max(int(model.get("nextId", 1)), order + len(additions) + 1)
    return model


def _supplemented_technical_model(original: dict) -> dict:
    model = copy.deepcopy(original)
    flow = next(row for row in model["items"] if row.get("element") == "Process Flow")
    flow["nodes"] = [
        "Detect chamber drift against the paired reference lot",
        "Contain the affected recipe and date-coded material",
        "Verify maintenance with the next production control run",
        "Release the process only after Quality confirms recovery",
    ]
    flow["edges"] = [[flow["nodes"][index], flow["nodes"][index + 1]] for index in range(len(flow["nodes"]) - 1)]
    order = max(int(row.get("order", 0)) for row in model.get("items", [])) + 1
    model["items"].extend([
        {
            "id": "chg207-tech-negative", "type": "metric", "engine": "MetricEngine", "element": "Hero KPI",
            "title": "Negative precision duration", "value": -1234567890.125, "unit": "seconds",
            "metric_format": {"kind": "number", "precision": 3}, "showTitle": True,
            "section_id": "weak-scenes", "section_title": "Narrow reading edge cases",
            "composition_role": "supporting_evidence", "order": order, "z": order + 1,
        },
        {
            "id": "chg207-tech-comparison", "type": "comparison", "engine": "ComparisonEngine",
            "element": "Before/After KPI", "title": "Long response capacity", "before": 9876543210,
            "after": 12345678901, "unit": "units", "showTitle": True,
            "section_id": "weak-scenes", "section_title": "Narrow reading edge cases",
            "composition_role": "supporting_evidence", "order": order + 1, "z": order + 2,
        },
    ])
    model["nextId"] = max(int(model.get("nextId", 1)), order + 3)
    return model


def _pixel_facts(path: Path) -> dict:
    with Image.open(path) as source:
        image = source.convert("RGB")
        stats = ImageStat.Stat(image)
        extrema = image.getextrema()
        return {
            "width": image.width,
            "height": image.height,
            "rgb_stddev": [round(value, 3) for value in stats.stddev],
            "rgb_extrema": extrema,
            "nonuniform_pixels": sum(1 for pixel in image.get_flattened_data() if pixel[0] != pixel[1] or pixel[1] != pixel[2]),
        }


def _crop_component(full_page: Path, rect: dict, destination: Path) -> None:
    with Image.open(full_page) as source:
        box = (max(0, round(rect["x"])), max(0, round(rect["y"])), round(rect["x"] + rect["width"]), round(rect["y"] + rect["height"]))
        crop = source.crop(box)
        crop.save(destination)


def _contact_sheet(before: Path, after: Path, destination: Path) -> None:
    font = ImageFont.load_default()
    panel_width = 460
    gutter = 20
    with Image.open(before) as first, Image.open(after) as second:
        images = [first.convert("RGB"), second.convert("RGB")]
    panels = []
    for label, image in zip(("CHG-173 R2 · AR-73 failure · 320px", "CHG-207 R1 · populated Preview · 320px"), images):
        scale = panel_width / image.width
        resized = image.resize((panel_width, max(1, round(image.height * scale))))
        panel = Image.new("RGB", (panel_width, resized.height + 42), "white")
        draw = ImageDraw.Draw(panel)
        draw.text((8, 8), label, fill="#132d49", font=font)
        panel.paste(resized, (0, 32))
        panels.append(panel)
    height = max(panel.height for panel in panels)
    sheet = Image.new("RGB", (panel_width * 2 + gutter, height), "#eef2f6")
    for index, panel in enumerate(panels):
        sheet.paste(panel, (index * (panel_width + gutter), 0))
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination)


def _preview(page, host: NativeHost, report_id: str, width: int, height: int) -> str:
    page.set_viewport_size({"width": width, "height": height})
    response = page.goto(f"{host.url}/visualizer?report={report_id}", wait_until="domcontentloaded")
    assert response and response.status == 200
    ready(page, require_settled=True)
    model_snapshot = page.evaluate("()=>JSON.stringify(window.CompanyUIVisualizerBridge.state().model)")
    page.locator("#previewBtn").click()
    page.wait_for_function("()=>document.querySelector('.cui-visualizer-root')?.classList.contains('preview-mode')")
    page.wait_for_timeout(160)
    return model_snapshot


def _page_facts(page, expected: dict, output: Path, stem: str) -> dict:
    viewport_path = output / f"{stem}-viewport.png"
    full_path = output / f"{stem}-full-page.png"
    page.evaluate("window.scrollTo(0,0)")
    page.screenshot(path=str(viewport_path))
    page.screenshot(path=str(full_path), full_page=True)
    browser = page.evaluate(
        """(expected)=>{
          const root=document.querySelector('.cui-visualizer-root');
          const model=window.CompanyUIVisualizerBridge.state().model;
          const components=[...root.querySelectorAll('.component[data-id]')];
          const tokens=[...root.querySelectorAll('.numeric-token')].map((el,index)=>{
            const rect=el.getBoundingClientRect(),cardRect=el.closest('.gallery-card')?.getBoundingClientRect();
            const range=document.createRange();range.selectNodeContents(el);
            const rects=[...range.getClientRects()].map(r=>({x:r.x,y:r.y,width:r.width,height:r.height}));
            const visualLines=[];for(const rect of rects){const line=visualLines.find(row=>Math.min(row.bottom,rect.y+rect.height)-Math.max(row.top,rect.y)>1);if(line){line.top=Math.min(line.top,rect.y);line.bottom=Math.max(line.bottom,rect.y+rect.height);line.left=Math.min(line.left,rect.x);line.right=Math.max(line.right,rect.x+rect.width);}else visualLines.push({top:rect.y,bottom:rect.y+rect.height,left:rect.x,right:rect.x+rect.width});}
            const clippedBy=[];for(let ancestor=el.parentElement;ancestor;ancestor=ancestor.parentElement){const ps=getComputedStyle(ancestor),pr=ancestor.getBoundingClientRect();if((/hidden|clip/.test(ps.overflowX)&&visualLines.some(line=>line.left<pr.left-1||line.right>pr.right+1))||(/hidden|clip/.test(ps.overflowY)&&visualLines.some(line=>line.top<pr.top-1||line.bottom>pr.bottom+1)))clippedBy.push({className:String(ancestor.className||''),overflowX:ps.overflowX,overflowY:ps.overflowY});}
            const component=el.closest('.component'),componentRect=component?.getBoundingClientRect();
            const cs=getComputedStyle(el);
            return {index,text:el.innerText.replace(/\\s+/g,' ').trim(),x:rect.x,y:rect.y,width:rect.width,height:rect.height,
              scrollWidth:el.scrollWidth,clientWidth:el.clientWidth,scrollHeight:el.scrollHeight,clientHeight:el.clientHeight,
              fontSize:cs.fontSize,whiteSpace:cs.whiteSpace,display:cs.display,rangeLines:visualLines,rangeRects:rects,clippedBy,
              insideCard:!cardRect||(rect.left>=cardRect.left-1&&rect.right<=cardRect.right+1&&rect.top>=cardRect.top-1&&rect.bottom<=cardRect.bottom+1),
              insideComponent:!componentRect||(rect.left>=componentRect.left-1&&rect.right<=componentRect.right+1&&rect.top>=componentRect.top-1&&rect.bottom<=componentRect.bottom+1)};
          });
          const flow=components.find(el=>el.dataset.id===expected.flowId);
          const readingSelector=innerWidth<=360?'.diagram-narrow-reading':'.diagram-medium-reading',narrow=flow?.querySelector(readingSelector),wide=flow?.querySelector('.diagram-wide-reading');
          const nodes=[...(narrow?.querySelectorAll('[data-diagram-node]')||[])].map(el=>{
            const r=el.getBoundingClientRect();return {id:el.dataset.diagramNode,order:Number(el.dataset.nodeOrder),label:el.querySelector('title')?.textContent.replace(/^Step \\d+: /,''),rect:{x:r.x,y:r.y,width:r.width,height:r.height}};
          });
          const edges=[...(narrow?.querySelectorAll('[data-diagram-edge]')||[])].map(el=>({id:el.dataset.diagramEdge,order:Number(el.dataset.edgeOrder),source:el.dataset.sourceId,target:el.dataset.targetId,path:el.querySelector('path')?.getAttribute('d')}));
          const shownNarrow=narrow&&getComputedStyle(narrow).display!=='none';
          const flowStyle=shownNarrow&&narrow.querySelector('.diagram-reading-label')?getComputedStyle(narrow.querySelector('.diagram-reading-label')).fontSize:null;
          const svgRect=shownNarrow?narrow.getBoundingClientRect():null,svgViewWidth=shownNarrow?Number(narrow.viewBox.baseVal.width)||1:1;
          const table=components.find(el=>el.dataset.id===expected.tableId)?.querySelector('.table-frame.table-scroll[role=region]');
          const tableShell=table?.closest('.table-scroll-shell'),tableShellRect=tableShell?.getBoundingClientRect();
          const small=components.find(el=>el.dataset.id===expected.smallTableId)?.querySelector('.table-frame.table-scroll[role=region]');
          const comparison=components.find(el=>el.dataset.id===expected.comparisonId)?.getBoundingClientRect();
          const tableAncestors=[];for(let el=table;el;el=el.parentElement){const r=el.getBoundingClientRect(),s=getComputedStyle(el);tableAncestors.push({tag:el.tagName,id:el.id,className:String(el.className||'').slice(0,90),y:r.y,height:r.height,overflowY:s.overflowY,position:s.position,scrollTop:el.scrollTop,scrollHeight:el.scrollHeight,clientHeight:el.clientHeight});}
          const decisionIndex=components.findIndex(el=>el.dataset.id===expected.decisionId),nextIndex=components.findIndex(el=>el.dataset.id===expected.nextId);
          const componentRects=components.map(el=>{const r=el.getBoundingClientRect();return {id:el.dataset.id,x:r.x,y:r.y,width:r.width,height:r.height,scrollWidth:el.scrollWidth,clientWidth:el.clientWidth,scrollHeight:el.scrollHeight,clientHeight:el.clientHeight};});
          const flowComponent=flow?.getBoundingClientRect();
          return {viewport:{width:innerWidth,height:innerHeight,devicePixelRatio,documentWidth:document.documentElement.scrollWidth,bodyWidth:document.body.scrollWidth,documentHeight:document.documentElement.scrollHeight,bodyHeight:document.body.scrollHeight,windowScrollY:scrollY},
            tokenFacts:tokens,componentOrder:components.map(el=>el.dataset.id),componentRects,decisionIndex,nextIndex,
            flow:{visibleNarrow:Boolean(shownNarrow),wideDisplay:wide?getComputedStyle(wide).display:null,fontSize:flowStyle,
              devicePixelRatio,svgRect:svgRect?svgRect.toJSON():null,effectiveLabelPixels:flowStyle&&svgRect?Number.parseFloat(flowStyle)*svgRect.width/svgViewWidth*devicePixelRatio:null,
              ariaLabel:narrow?.getAttribute('aria-label'),canonicalDirection:narrow?.dataset.canonicalDirection,readingDirection:narrow?.dataset.readingDirection,
              nodes,edges,rect:flowComponent?{x:flowComponent.x,y:flowComponent.y,width:flowComponent.width,height:flowComponent.height}:null,
              bounds:flowComponent?{scrollWidth:flow.scrollWidth,clientWidth:flow.clientWidth,scrollHeight:flow.scrollHeight,clientHeight:flow.clientHeight}:null},
            comparisonRect:comparison?{x:comparison.x,y:comparison.y,width:comparison.width,height:comparison.height}:null,
            table:table?{clientWidth:table.clientWidth,scrollWidth:table.scrollWidth,scrollLeft:table.scrollLeft,overflow:table.scrollWidth>table.clientWidth+1,
              overflowX:getComputedStyle(table).overflowX,touchAction:getComputedStyle(table).touchAction,tabIndex:table.tabIndex,
              ariaLabel:table.getAttribute('aria-label'),describedBy:table.getAttribute('aria-describedby'),hint:table.closest('.table-scroll-shell')?.querySelector('.table-scroll-hint')?.innerText,
              rect:table.getBoundingClientRect().toJSON(),ancestors:tableAncestors,windowScrollY:scrollY,documentScrollHeight:document.documentElement.scrollHeight,bodyScrollHeight:document.body.scrollHeight,
              pointerEvents:getComputedStyle(table).pointerEvents,shellRect:tableShellRect?.toJSON()||null}:null,
            smallTable:small?{clientWidth:small.clientWidth,scrollWidth:small.scrollWidth,overflow:small.scrollWidth>small.clientWidth+1,
              ariaLabel:small.getAttribute('aria-label'),describedBy:small.getAttribute('aria-describedby'),hintHidden:small.closest('.table-scroll-shell')?.querySelector('.table-scroll-hint')?.hidden,tabIndex:small.tabIndex}:null,
            visual:{flowPixelRect:narrow?.getBoundingClientRect().toJSON?.()||null,flowNodeSvgRects:nodes.map(row=>row.rect),componentCount:components.length},
            modelUnchanged:JSON.stringify(model)===expected.modelSnapshot};
        }""",
        expected,
    )
    return {
        "screenshots": {
            "viewport": {"path": str(viewport_path.name), "sha256": digest(viewport_path), "pixels": _pixel_facts(viewport_path)},
            "full_page": {"path": str(full_path.name), "sha256": digest(full_path), "pixels": _pixel_facts(full_path)},
        },
        "browser": browser,
    }


def _exercise_table(page, table_id: str) -> dict:
    table = page.locator(f'.component[data-id="{table_id}"] .table-frame.table-scroll[role="region"]')
    table.wait_for(state="visible")
    page.locator("#previewBtn").focus()
    tab_trace = []
    for _ in range(80):
        page.keyboard.press("Tab")
        active = page.evaluate("()=>{const el=document.activeElement;return {tag:el?.tagName,id:el?.id,role:el?.getAttribute('role'),label:el?.getAttribute('aria-label'),className:String(el?.className||'').slice(0,100)}}")
        tab_trace.append(active)
        if table.evaluate("el=>document.activeElement===el"):
            break
    assert table.evaluate("el=>document.activeElement===el"), f"keyboard tab order did not reach the focusable table region: {tab_trace}"
    page.wait_for_timeout(60)
    initial = table.evaluate("el=>({left:el.scrollLeft,max:el.scrollWidth-el.clientWidth,label:el.getAttribute('aria-label'),describedBy:el.getAttribute('aria-describedby'),hint:el.closest('.table-scroll-shell')?.querySelector('.table-scroll-hint')?.innerText,boxShadow:getComputedStyle(el).boxShadow,outline:getComputedStyle(el).outline,outlineStyle:getComputedStyle(el).outlineStyle})")
    assert initial["max"] > 1, f"expected table to overflow horizontally: {initial}"
    assert initial["describedBy"] and initial["hint"], f"overflow instructions are not exposed: {initial}"
    assert "more columns" in initial["hint"].lower() or "earlier columns" in initial["hint"].lower(), initial
    assert initial["boxShadow"] != "none" or initial["outlineStyle"] != "none", f"focus indicator is not visible: {initial}"
    assert initial["label"].startswith("Scrollable table:"), initial
    rows = [{"key": "focus", "left": initial["left"], "focused": table.evaluate("el=>document.activeElement===el")}]
    for key in ("ArrowRight", "End", "ArrowLeft", "Home"):
        before = table.evaluate("el=>el.scrollLeft")
        table.press(key)
        page.wait_for_timeout(80)
        after = table.evaluate("el=>el.scrollLeft")
        focused = table.evaluate("el=>document.activeElement===el")
        hint = table.evaluate("el=>el.closest('.table-scroll-shell')?.querySelector('.table-scroll-hint')?.innerText")
        rows.append({"key": key, "before": before, "after": after, "focused": focused, "hint": hint})
        assert focused, f"focus left table after {key}"
        assert after != before, f"{key} did not move scroll position ({before} -> {after})"
    assert rows[1]["after"] > rows[1]["before"], rows
    assert rows[2]["after"] == initial["max"], rows
    assert rows[3]["after"] < rows[3]["before"], rows
    assert rows[4]["after"] == 0, rows
    table.evaluate("el=>{el.scrollLeft=0;el.focus();el.scrollIntoView({block:'center',inline:'nearest'})}")
    page.wait_for_timeout(80)
    box = table.bounding_box()
    assert box and box["x"] >= 0 and box["y"] >= 0 and box["x"] + box["width"] <= page.viewport_size["width"] + 1 and box["y"] + box["height"] <= page.viewport_size["height"] + 1, f"overflow region could not be brought into the viewport for pointer scrolling: box={box}, viewport={page.viewport_size}"
    page.mouse.move(box["x"] + min(20, box["width"] / 2), box["y"] + min(24, box["height"] / 2))
    before_wheel = table.evaluate("el=>el.scrollLeft")
    page.mouse.wheel(140, 0)
    page.wait_for_timeout(120)
    after_wheel = table.evaluate("el=>el.scrollLeft")
    assert after_wheel > before_wheel, f"wheel did not scroll table: {before_wheel}->{after_wheel}"
    touch_receipt = {"attempted": False, "before": after_wheel, "after": after_wheel, "status": "not-run"}
    try:
        rect = table.bounding_box()
        cdp = page.context.new_cdp_session(page)
        x = rect["x"] + rect["width"] - 8
        y = rect["y"] + min(24, rect["height"] / 2)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x - 72, "y": y, "id": 1}]})
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        page.wait_for_timeout(100)
        touch_after = table.evaluate("el=>el.scrollLeft")
        touch_receipt = {"attempted": True, "before": after_wheel, "after": touch_after, "status": "scrolled" if touch_after > after_wheel else "touch-action-and-overflow-css-verified"}
    except Exception as exc:
        touch_receipt = {"attempted": True, "status": "touch-injection-unavailable", "detail": str(exc)}
    maximum = table.evaluate("el=>el.scrollWidth-el.clientWidth")
    table.evaluate("el=>el.scrollLeft=el.scrollWidth")
    page.wait_for_timeout(80)
    end_hint = table.evaluate("el=>el.closest('.table-scroll-shell')?.querySelector('.table-scroll-hint')?.innerText")
    end_left = table.evaluate("el=>el.scrollLeft")
    assert end_left == maximum, (end_left, maximum)
    assert "left" in end_hint.lower() or "earlier columns" in end_hint.lower(), end_hint
    return {"initial": initial, "tab_focus_trace": tab_trace, "keyboard": rows, "wheel": {"before": before_wheel, "after": after_wheel}, "touch": touch_receipt, "end": {"scrollLeft": end_left, "max": maximum, "hint": end_hint}, "focusRetained": all(row["focused"] for row in rows)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--candidate-tree", required=True)
    parser.add_argument("--fabric-job-id", default=FABRIC_JOB_ID)
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    if output == ROOT or ROOT in output.parents:
        parser.error("--output must be outside the checkout.")
    if output.exists() and any(output.iterdir()):
        parser.error("--output must be new or empty.")
    if git("rev-parse", "HEAD") != args.candidate_sha or git("rev-parse", "HEAD^{tree}") != args.candidate_tree:
        parser.error("Acceptance must start on the exact candidate SHA and tree.")
    if git("branch", "--show-current") != "fix/visembler-chg207-narrow-reading-r1":
        parser.error("Acceptance must run on fix/visembler-chg207-narrow-reading-r1.")
    if git("rev-parse", "HEAD^") != SOURCE_SHA:
        parser.error("The candidate parent must be the exact requested CHG-173 R2 main commit.")
    if git("status", "--porcelain"):
        parser.error("Candidate acceptance requires a clean worktree.")
    output.mkdir(parents=True, exist_ok=True)
    fixture_path = ROOT / FIXTURE
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    report_rows = {row["key"]: row for row in fixture["reports"]}
    supply_model = report_rows["supply-chain-capacity-holdout"]["model"]
    technical_model = _supplemented_technical_model(report_rows["technical-status-review"]["model"])
    stress_model = _supplemented_supply_model(supply_model)
    before_path = ROOT / R2_SCREENSHOT
    receipt = {
        "schema": "visembler-chg207-narrow-reading-acceptance.v1",
        "project": "visembler", "request": "CHG-207-r1", "operation": "FIX",
        "fabric_job_id": args.fabric_job_id, "candidate_sha": args.candidate_sha,
        "candidate_tree": args.candidate_tree, "source_sha": SOURCE_SHA, "source_tree": SOURCE_TREE,
        "r2_carrier_sha": R2_SHA, "r2_failure_screenshot": {"path": R2_SCREENSHOT, "sha256": digest(before_path), "pixels": _pixel_facts(before_path)},
        "populated_report_fixture": {"path": FIXTURE, "sha256": digest(fixture_path), "source": fixture.get("source"), "source_candidate": fixture.get("source_candidate"), "source_tree": fixture.get("source_tree")},
        "runtime": {}, "cases": {}, "focused_interactions": {}, "browser_errors": [],
        "status": "RUNNING",
    }
    events = BrowserEvents()
    flow_source = next(row for row in supply_model["items"] if row.get("element") == "Process Flow")
    wide_table_source = next(row for row in supply_model["items"] if row.get("engine") == "TableEngine")
    decision_source = next(row for row in supply_model["items"] if row.get("composition_role") == "decision_risk")
    next_source = next(row for row in supply_model["items"] if row.get("section_id") == "delivery" and row.get("id") != decision_source["id"])
    comparison_source = next(row for row in supply_model["items"] if row.get("engine") == "ComparisonEngine")
    metric_sources = [row for row in supply_model["items"] if row.get("engine") == "MetricEngine"]
    expected_supply = {
        "flowId": flow_source["id"], "tableId": wide_table_source["id"], "smallTableId": "chg207-nonoverflow-table",
        "decisionId": decision_source["id"], "nextId": next_source["id"],
    }
    try:
        with tempfile.TemporaryDirectory(prefix="visembler-chg207-native-") as temp_dir, sync_playwright() as playwright:
            with NativeHost(ROOT, Path(temp_dir) / "data") as host:
                supply_id = host.create(model=supply_model, name="chg207-supply-chain-capacity")
                technical_id = host.create(model=technical_model, name="chg207-technical-status")
                stress_id = host.create(model=stress_model, name="chg207-supply-chain-weak-scenes")
                browser = playwright.chromium.launch(**browser_kwargs())
                receipt["runtime"] = {"python": sys.version.split()[0], "nicegui": importlib.metadata.version("nicegui"), "playwright": importlib.metadata.version("playwright"), "browser": browser.version, "host_url": host.url, "ephemeral_port": host.port, "native_host": True}
                context = browser.new_context(viewport={"width": 320, "height": 800}, device_scale_factor=1, has_touch=True, is_mobile=False)
                page = context.new_page()
                page.set_default_timeout(10000)
                events.attach(page)

                for name, width, height in (("supply-320", 320, 800), ("supply-390", 390, 844), ("supply-desktop", 1440, 1000)):
                    model_snapshot = _preview(page, host, supply_id, width, height)
                    expected = {**expected_supply, "comparisonId": comparison_source["id"], "modelSnapshot": model_snapshot}
                    facts = _page_facts(page, expected, output, name)
                    receipt["cases"][name] = facts
                    if name == "supply-320":
                        full_page = output / facts["screenshots"]["full_page"]["path"]
                        comparison_path = output / "supply-320-comparison.png"
                        flow_path = output / "supply-320-process-flow.png"
                        table_path = output / "supply-320-wide-evidence-table.png"
                        _crop_component(full_page, facts["browser"]["comparisonRect"], comparison_path)
                        _crop_component(full_page, facts["browser"]["flow"]["rect"], flow_path)
                        _crop_component(full_page, facts["browser"]["table"]["shellRect"], table_path)
                        receipt["focused_interactions"]["table_keyboard_and_overflow"] = _exercise_table(page, wide_table_source["id"])
                        receipt["focused_interactions"]["table_keyboard_and_overflow"]["screenshots"] = {"table": {"path": table_path.name, "sha256": digest(table_path), "pixels": _pixel_facts(table_path)}}
                        reachability = {}
                        for item_id in (decision_source["id"], next_source["id"]):
                            item = page.locator(f'.component[data-id="{item_id}"]')
                            item.scroll_into_view_if_needed()
                            box = item.bounding_box()
                            content = " ".join(item.inner_text().split())
                            assert box and box["y"] >= 0 and box["y"] + box["height"] <= height + 1 and content, (item_id, box, content)
                            scroll_y = page.evaluate("()=>scrollY")
                            reachability[item_id] = {"rect": box, "window_scroll_y": scroll_y, "document_y": box["y"] + scroll_y, "visible_text": content}
                        assert reachability[decision_source["id"]]["document_y"] < reachability[next_source["id"]]["document_y"], reachability
                        receipt["focused_interactions"]["decision_next_reachability"] = reachability
                    page_model = supply_model
                    assert facts["browser"]["modelUnchanged"], f"{name}: narrow rendering changed saved composition"
                    if name in ("supply-320", "supply-390"):
                        browser_facts = facts["browser"]
                        assert browser_facts["viewport"]["documentWidth"] <= width, (name, browser_facts["viewport"])
                        tokens = browser_facts["tokenFacts"]
                        for value in ("120000 units", "142000 units", "2.7%", "116 days"):
                            found = [token for token in tokens if token["text"] == value]
                            assert found, f"{name}: missing expected formatted visible token {value!r}: {tokens}"
                            assert all(len(token["rangeLines"]) == 1 and token["scrollWidth"] <= token["clientWidth"] and token["insideComponent"] for token in found), (name, value, found)
                        flow = browser_facts["flow"]
                        expected_reading_direction = "down" if width <= 360 else "serpentine"
                        assert flow["visibleNarrow"] and flow["canonicalDirection"] == "right" and flow["readingDirection"] == expected_reading_direction, (name, flow)
                        assert [row["label"] for row in flow["nodes"]] == flow_source["nodes"], (name, flow)
                        assert [row["order"] for row in flow["nodes"]] == list(range(len(flow_source["nodes"]))), (name, flow)
                        assert len(flow["edges"]) == len(flow_source["edges"]), (name, flow)
                        assert [row["order"] for row in flow["edges"]] == list(range(len(flow_source["edges"]))), (name, flow)
                        node_labels = {row["id"]: row["label"] for row in flow["nodes"]}
                        actual_edges = [[node_labels[edge["source"]], node_labels[edge["target"]]] for edge in flow["edges"]]
                        assert actual_edges == flow_source["edges"], (name, actual_edges, flow_source["edges"])
                        assert flow["fontSize"] and float(flow["fontSize"].removesuffix("px")) >= 14, (name, flow)
                        assert flow["effectiveLabelPixels"] >= 12, (name, flow)
                        assert flow["bounds"]["scrollWidth"] <= flow["bounds"]["clientWidth"] + 1, (name, flow["bounds"])
                        assert all(row["rect"]["width"] > 0 and row["rect"]["height"] > 0 for row in flow["nodes"]), (name, flow)
                        if flow["readingDirection"] == "down":
                            assert all(flow["nodes"][i]["rect"]["y"] + flow["nodes"][i]["rect"]["height"] <= flow["nodes"][i + 1]["rect"]["y"] + 1 for i in range(len(flow["nodes"]) - 1)), (name, flow)
                        else:
                            boxes = [row["rect"] for row in flow["nodes"]]
                            assert all(not (a["x"] < b["x"] + b["width"] and a["x"] + a["width"] > b["x"] and a["y"] < b["y"] + b["height"] and a["y"] + a["height"] > b["y"]) for index, a in enumerate(boxes) for b in boxes[index + 1:]), (name, flow)
                            centers = [(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2) for box in boxes]
                            assert centers[0][0] < centers[1][0] and abs(boxes[0]["y"] - boxes[1]["y"]) <= 2, (name, flow)
                            assert abs(centers[1][0] - centers[2][0]) <= 2 and centers[2][1] > centers[1][1], (name, flow)
                            assert centers[2][0] > centers[3][0] and abs(boxes[2]["y"] - boxes[3]["y"]) <= 2, (name, flow)
                        flow_rect = flow["rect"]
                        flow_bottom = flow["nodes"][-1]["rect"]["y"] + flow["nodes"][-1]["rect"]["height"]
                        following = min((rect for rect in browser_facts["componentRects"] if rect["id"] != flow_source["id"] and rect["y"] >= flow_rect["y"] + flow_rect["height"] - 1), key=lambda rect: rect["y"], default=None)
                        if following:
                            assert flow_bottom <= following["y"] + 1, (name, flow, following)
                        assert browser_facts["decisionIndex"] >= 0 and browser_facts["nextIndex"] > browser_facts["decisionIndex"], (name, browser_facts["componentOrder"])
                        assert browser_facts["viewport"]["documentHeight"] >= browser_facts["componentRects"][browser_facts["nextIndex"]]["y"] + browser_facts["componentRects"][browser_facts["nextIndex"]]["height"], (name, browser_facts["viewport"], browser_facts["componentRects"][browser_facts["nextIndex"]])
                        assert browser_facts["table"] and browser_facts["table"]["overflow"], (name, browser_facts["table"])
                        assert browser_facts["table"]["describedBy"] and browser_facts["table"]["hint"], (name, browser_facts["table"])
                    else:
                        assert facts["browser"]["flow"]["wideDisplay"] != "none", facts["browser"]["flow"]
                    if name == "supply-320":
                        assert browser_facts["table"]["tabIndex"] == 0
                        receipt["cases"][name]["visual_pixel_facts"] = {"comparison": _pixel_facts(comparison_path), "flow": _pixel_facts(flow_path), "table": _pixel_facts(table_path)}

                for name, width, height, report_id, model in (("technical-320", 320, 800, technical_id, technical_model), ("weak-scenes-320", 320, 800, stress_id, stress_model)):
                    model_snapshot = _preview(page, host, report_id, width, height)
                    flow = next((entry for entry in model["items"] if entry.get("element") == "Process Flow"), None)
                    table = next((entry for entry in model["items"] if entry.get("engine") == "TableEngine"), None)
                    expected = {"flowId": flow["id"] if flow else "", "tableId": table["id"] if table else "", "smallTableId": "chg207-nonoverflow-table", "decisionId": decision_source["id"], "nextId": next_source["id"], "modelSnapshot": model_snapshot}
                    facts = _page_facts(page, expected, output, name)
                    receipt["cases"][name] = facts
                    assert facts["browser"]["modelUnchanged"], (name, "model changed")
                    assert facts["browser"]["viewport"]["documentWidth"] <= width, (name, facts["browser"]["viewport"])
                    if name == "technical-320":
                        assert facts["browser"]["flow"]["visibleNarrow"], facts["browser"]["flow"]
                        assert [row["label"] for row in facts["browser"]["flow"]["nodes"]] == flow["nodes"], facts["browser"]["flow"]
                        assert [row["order"] for row in facts["browser"]["flow"]["nodes"]] == list(range(len(flow["nodes"]))), facts["browser"]["flow"]
                        node_labels = {row["id"]: row["label"] for row in facts["browser"]["flow"]["nodes"]}
                        actual_edges = [[node_labels[edge["source"]], node_labels[edge["target"]]] for edge in facts["browser"]["flow"]["edges"]]
                        assert actual_edges == flow["edges"], (name, actual_edges, flow["edges"])
                        tokens = {token["text"]: token for token in facts["browser"]["tokenFacts"]}
                        for value in ("-1,234,567,890.125 seconds", "9876543210 units", "12345678901 units"):
                            token = tokens.get(value)
                            assert token and len(token["rangeLines"]) == 1 and token["scrollWidth"] <= token["clientWidth"] and token["insideComponent"], (name, value, token)
                    else:
                        by_id = {token["text"]: token for token in facts["browser"]["tokenFacts"]}
                        for value in ("-1,234,567.8 units", "0.000", "9876543210 units", "12345678901 units"):
                            token = by_id.get(value)
                            assert token, (name, value, facts["browser"]["tokenFacts"])
                            assert len(token["rangeLines"]) == 1 and token["scrollWidth"] <= token["clientWidth"] and token["insideComponent"], (name, token)
                        assert facts["browser"]["smallTable"] and not facts["browser"]["smallTable"]["overflow"], facts["browser"]["smallTable"]
                        assert facts["browser"]["smallTable"]["hintHidden"] and not facts["browser"]["smallTable"]["describedBy"], facts["browser"]["smallTable"]
                        assert facts["browser"]["smallTable"]["tabIndex"] == 0, facts["browser"]["smallTable"]
                        receipt["focused_interactions"]["nonoverflow_table"] = facts["browser"]["smallTable"]
                        assert facts["browser"]["flow"]["visibleNarrow"], facts["browser"]["flow"]
                        assert [row["label"] for row in facts["browser"]["flow"]["nodes"]] == flow["nodes"], facts["browser"]["flow"]
                        receipt["focused_interactions"]["weak_scene_comparison_labels"] = {
                            "before_label": page.locator('.component[data-id="chg207-long-comparison"] .before-after-kpi>div>small:not(.comparison-unit)').all_text_contents(),
                            "direction_marker": page.locator('.component[data-id="chg207-long-comparison"] .before-after-kpi em').inner_text(),
                            "token_text": [page.locator(f'.component[data-id="chg207-long-comparison"] .numeric-token').nth(index).inner_text() for index in range(2)],
                        }
                        assert receipt["focused_interactions"]["weak_scene_comparison_labels"]["before_label"] == ["Before", "After"]
                        assert receipt["focused_interactions"]["weak_scene_comparison_labels"]["direction_marker"] == "▲"
                context.close()

                zoom_context = browser.new_context(viewport={"width": 160, "height": 800}, device_scale_factor=2, has_touch=True, is_mobile=False)
                zoom_page = zoom_context.new_page()
                zoom_page.set_default_timeout(10000)
                events.attach(zoom_page)
                zoom_snapshot = _preview(zoom_page, host, supply_id, 160, 800)
                zoom_expected = {**expected_supply, "comparisonId": comparison_source["id"], "modelSnapshot": zoom_snapshot}
                zoom_facts = _page_facts(zoom_page, zoom_expected, output, "supply-zoom-equivalent-200")
                receipt["cases"]["supply-zoom-equivalent-200"] = zoom_facts
                zoom_browser = zoom_facts["browser"]
                assert zoom_browser["viewport"]["documentWidth"] <= 160, zoom_browser["viewport"]
                assert zoom_browser["viewport"]["devicePixelRatio"] == 2
                for value in ("120000 units", "142000 units", "2.7%", "116 days"):
                    found = [token for token in zoom_browser["tokenFacts"] if token["text"] == value]
                    assert found and all(len(token["rangeLines"]) == 1 and token["scrollWidth"] <= token["clientWidth"] and token["insideComponent"] for token in found), (value, found)
                assert zoom_browser["flow"]["visibleNarrow"] and zoom_browser["flow"]["effectiveLabelPixels"] >= 12, zoom_browser["flow"]
                assert [row["label"] for row in zoom_browser["flow"]["nodes"]] == flow_source["nodes"]
                receipt["focused_interactions"]["zoom_equivalent_200"] = {"method": "160 CSS-pixel viewport with deviceScaleFactor=2 (200% zoom-equivalent visible pixel width)", "viewport": zoom_browser["viewport"], "flow_effective_label_pixels": zoom_browser["flow"]["effectiveLabelPixels"], "critical_tokens": [token for token in zoom_browser["tokenFacts"] if token["text"] in {"120000 units", "142000 units", "2.7%", "116 days"}]}
                zoom_context.close()
                browser.close()

        before_path = ROOT / R2_SCREENSHOT
        after_path = output / "supply-320-full-page.png"
        contact = output / "AR-73-before-after-320-contact-sheet.png"
        _contact_sheet(before_path, after_path, contact)
        receipt["screenshots"] = {
            "before": {"path": R2_SCREENSHOT, "sha256": digest(before_path), "pixels": _pixel_facts(before_path)},
            "after_contact_sheet": {"path": contact.name, "sha256": digest(contact), "pixels": _pixel_facts(contact)},
        }
        receipt["browser_errors"] = events.unexpected
        assert not receipt["browser_errors"], receipt["browser_errors"]
        receipt["status"] = "PASS_PENDING_MANUAL_PIXEL_REVIEW"
    except Exception as exc:
        receipt["error"] = str(exc)
        receipt["traceback"] = traceback.format_exc()
        receipt["browser_errors"] = events.unexpected
        receipt["status"] = "FAIL"
    write_json(output / "acceptance-receipt.json", receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0 if receipt["status"] == "PASS_PENDING_MANUAL_PIXEL_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
