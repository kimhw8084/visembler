#!/usr/bin/env python3
"""Capture the CHG-209 six-scene exact-base / candidate reading matrix."""
from __future__ import annotations

import argparse
import copy
import hashlib
from io import BytesIO
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from editor_host import NativeHost
from native_common import BrowserEvents, browser_kwargs, ready, write_json


FIXTURE = Path("tests/fixtures/chg206/whole_report_models.json")
VIEWPORTS = {"desktop-1440": 1440, "narrow-390": 390, "narrow-320": 320}
EXPECTED_DIRECTIONS = {
    "A-executive": "decision-led", "B-experiment": "conditional-evidence",
    "C-causal": "causal-investigation", "D-technical": "dense-operations",
    "E-holdout-mixed": "allocation-comparison", "F-holdout-sparse": "sparse-decision",
}
SCENES = {
    "A-executive": {
        "fixture": "executive-business-review", "title": "Executive cohort decision",
        "person": "CFO and regional commercial lead", "context": "Quarterly retention review before the next intervention window.",
        "task": "Decide whether the South cohort needs a targeted retention action.",
        "decision": "Direct the intervention using cohort evidence; aggregate revenue is context.",
        "current_truth": "North and West are on plan; South is below the retention target.",
        "tone": "Decisive and evidence led, with aggregate growth as context.",
        "misunderstanding": "A reader could mistake total growth for evidence that every cohort is healthy.",
    },
    "B-experiment": {
        "fixture": "experiment-decision", "title": "Conditional experiment readout",
        "person": "Product experimentation lead and quality owner", "context": "Four week randomized onboarding test with a quality guardrail.",
        "task": "Choose whether to expand treatment beyond a limited rollout.",
        "decision": "Continue only as a limited rollout while the quality and retention caveats remain open.",
        "current_truth": "Treatment conversion is higher in the observed sample; long term retention is unknown.",
        "tone": "Measured and conditional; sample limits stay adjacent to the treatment evidence.",
        "misunderstanding": "The trend may be read as proof of durable lift without its sample caveat.",
    },
    "C-causal": {
        "fixture": "semiconductor-rca", "title": "Causal yield investigation",
        "person": "Process engineer, equipment owner, and lot disposition lead", "context": "Affected lot compared with spatial and paired reference evidence.",
        "task": "Determine the containment needed before lot release.",
        "decision": "Contain the affected lot until chamber verification agrees with the paired reference run.",
        "current_truth": "The local yield loss aligns with chamber drift; causal certainty remains under verification.",
        "tone": "Investigative, traceable, and explicit about what is verified.",
        "misunderstanding": "A shared headline weight could imply the mechanism is already proven.",
    },
    "D-technical": {
        "fixture": "technical-status-review", "title": "Dense operating review",
        "person": "Shift operations lead and reliability engineering", "context": "Line 4 shift, control chart, evidence table, and open release actions.",
        "task": "Review operating evidence together and decide whether capacity can be released.",
        "decision": "Keep the recipe locked until the paired-lot check closes both open items.",
        "current_truth": "The overnight trend recovered; the next paired-lot result is still pending.",
        "tone": "Compact, technical, and scannable without hiding supporting evidence.",
        "misunderstanding": "Large gaps may separate the decision from the operating evidence that qualifies it.",
    },
    "E-holdout-mixed": {
        "fixture": "fresh-cold-chain", "title": "Fresh mixed evidence holdout",
        "person": "Regional cold-chain planner and depot operations", "context": "Fresh synthetic delivery-capacity review with trend, allocation, comparison, and lead-time evidence.",
        "task": "Allocate reserve capacity across three depots while one supplier date remains unconfirmed.",
        "decision": "Reserve qualified stock for the constrained route and keep the uncertain supplier allocation provisional.",
        "current_truth": "Demand exceeds the confirmed buffer in two weeks; one lead-time estimate is not yet committed.",
        "tone": "Operational and constraint led, with comparison and next action kept together.",
        "misunderstanding": "A point estimate could be mistaken for committed capacity while one date is provisional.",
    },
    "F-holdout-sparse": {
        "fixture": "fresh-release", "title": "Fresh sparse release decision",
        "person": "Quality approver and release manager", "context": "A small evidence packet for a batch release with one unresolved validation result.",
        "task": "Decide whether to release the batch or hold it for one more sample.",
        "decision": "Hold the batch until the missing validation sample is reviewed.",
        "current_truth": "Two checks pass; the third result is unavailable, so the evidence is incomplete.",
        "tone": "Direct and open, with uncertainty visible before the next step.",
        "misunderstanding": "The two passing checks could obscure the missing validation result.",
    },
}


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def fixture_models(root: Path) -> tuple[dict[str, dict], str]:
    path = root / FIXTURE
    raw = path.read_bytes()
    payload = json.loads(raw)
    models = {row["key"]: copy.deepcopy(row["model"]) for row in payload["reports"]}
    return models, hashlib.sha256(raw).hexdigest()


def fresh_cold_chain(source: dict) -> dict:
    """Create a new task and values from an existing renderer structure after the rule exists."""
    model = copy.deepcopy(source)
    model["layoutPreset"] = "comparison"
    model.pop("visualDirectionChoice", None)
    datasets = model.get("datasets", [])
    if datasets:
        dataset = datasets[0]
        dataset["id"] = "holdout-cold-chain-dataset"
        dataset["name"] = "Harbor cold-chain plan"
        labels = {
            "Week": "Delivery week", "Demand units": "Dose kits required",
            "Confirmed capacity": "Confirmed cold slots", "Actuator lead days": "Supplier lead days",
        }
        field_ids = {
            "week_1": "delivery_week", "demand_units_2": "dose_kits_required",
            "confirmed_capacity_3": "confirmed_cold_slots", "actuator_lead_days_4": "supplier_lead_days",
        }
        for field in dataset.get("fields", []):
            field["id"] = field_ids.get(field.get("id"), field.get("id"))
            field["name"] = labels.get(field.get("name"), field.get("name"))
        dataset["rows"] = [
            ["W11", 106000, 116000, 61], ["W12", 111000, 118000, 66],
            ["W13", 119000, 120000, 72], ["W14", 124000, 121000, 76],
            ["W15", 128000, 126000, 81], ["W16", 132000, 127000, 84],
            ["W17", 136000, 132000, 89], ["W18", 140000, 134000, 93],
        ]
        dataset["revision"] = 1
        for item in model.get("items", []):
            if item.get("dataset_id"):
                item["dataset_id"] = dataset["id"]
            for target in (item.get("mapping", {}), item.get("chart_studio", {}).get("mapping", {})):
                for role, field_id in list(target.items()):
                    if field_id in field_ids:
                        target[role] = field_ids[field_id]
        model["items"][0]["data"] = [[f"W{n}", value] for n, value in enumerate([106,111,119,124,128,132,136,140], 11)]
        model["items"][1]["data"] = [[f"W{n}", value] for n, value in enumerate([116,118,120,121,126,127,132,134], 11)]
    metrics = [item for item in model.get("items", []) if item.get("engine") == "MetricEngine"]
    if len(metrics) >= 2:
        metrics[0].update({"value": 2, "unit": "weeks", "title": "Capacity constrained"})
        metrics[0]["metric_format"] = {**metrics[0].get("metric_format", {}), "suffix": "weeks"}
        metrics[1].update({"value": 93, "unit": "days", "title": "Longest provisional lead"})
        metrics[1]["metric_format"] = {**metrics[1].get("metric_format", {}), "suffix": "days"}
    for item in model.get("items", []):
        role, engine, ident = item.get("composition_role"), item.get("engine"), str(item.get("id"))
        if engine == "TextEngine":
            if role == "report_headline":
                item["text"] = item["body"] = "Two depot weeks exceed the confirmed cold-chain buffer."
            elif role == "context":
                item["text"] = item["body"] = "Harbor network · W11–W18 · three depots · supplier confirmation pending for the constrained route."
                item["composition_role"] = "context"
            elif role == "narrative_interpretation":
                item["text"] = item["body"] = "Demand reaches 140,000 dose kits by W18 while confirmed cold slots reach 134,000. The supplier estimate is 93 days and remains provisional until the carrier appointment is confirmed. Reserve qualified stock against the two constrained weeks and review the mix again after the appointment."
                item["composition_role"] = "context"
            elif role == "conclusion":
                item["text"] = item["body"] = "Next step: reserve Bay 4 for W13–W14 and hold the unconfirmed supplier allocation as provisional."
        elif engine == "MetricEngine":
            # Values and units were set above from the two metric slots.
            pass
        elif engine == "ComparisonEngine":
            item.update({"title": "Demand versus confirmed cold slots · W13", "before": 120000, "after": 134000, "beforeLabel": "Demand at W13", "afterLabel": "Confirmed slots at W13", "unit": "kits"})
            item["metric_format"] = {**item.get("metric_format", {}), "suffix": "kits"}
        elif engine == "TableEngine":
            table = item.setdefault("customTable", {})
            table["headers"] = ["Depot / supplier", "Confirmed", "Provisional", "Lead time", "Current truth"]
            table["rows"] = [
                ["Bay 2 / Harbor North", 54000, 0, "24 days", "Confirmed through W15"],
                ["Bay 4 / Meridian Cold", 42000, 14000, "93 days", "Carrier appointment pending"],
                ["Bay 7 / East Quay", 38000, 0, "31 days", "Two constrained weeks"],
            ]
        elif engine == "DecisionCompositeEngine":
            item["statement"] = "Reserve qualified cold slots for W13–W14."
            item["detail"] = "Demand exceeds confirmed capacity by 3,000 kits in W13 and 3,000 in W14; supplier timing remains provisional."
            item["status"] = "Conditional · supplier appointment pending"
        elif engine == "ProjectCompositeEngine":
            item["title"] = "Reserve and verify"
            item["summary"] = "Reserve Bay 4 capacity for the two constrained weeks."
            item["status"] = "Owner: Depot operations · Due: W12"
        elif engine == "DiagramEngine":
            item["title"] = "Reserve / confirm / release"
            item["nodes"] = ["Compare weekly demand", "Reserve qualified cold slots", "Confirm carrier appointment", "Release provisional allocation"]
            item["edges"] = [[item["nodes"][index], item["nodes"][index + 1]] for index in range(len(item["nodes"]) - 1)]
    model["schema_version"] = 1
    model["mode"] = "smart"
    return model


def fresh_sparse_release() -> dict:
    items = [
            {"id": "f-head", "type": "text", "engine": "TextEngine", "element": "Executive Statement", "title": "Batch disposition", "composition_role": "report_headline", "section_id": "opening", "showTitle": True, "text": "Hold batch R17 until the missing validation sample is reviewed.", "body": "Hold batch R17 until the missing validation sample is reviewed."},
            {"id": "f-context", "type": "text", "engine": "TextEngine", "element": "Body Narrative", "title": "Current evidence", "composition_role": "context", "section_id": "opening", "showTitle": True, "text": "Two of three release checks passed. The final sample result has not arrived, and no substitute measurement is available.", "body": "Two of three release checks passed. The final sample result has not arrived, and no substitute measurement is available."},
            {"id": "f-table", "type": "table", "engine": "TableEngine", "element": "Clean Table", "title": "Validation checks", "composition_role": "detailed_evidence", "section_id": "evidence", "customTable": {"headers": ["Check", "Observed", "Required", "Status"], "rows": [["Seal integrity", "Pass", "Pass", "Complete"], ["Temperature excursion", "0.4°C", "≤ 1.0°C", "Complete"], ["Retention sample", "Unavailable", "Measured", "Open"]]}},
            {"id": "f-risk", "type": "decision", "engine": "DecisionCompositeEngine", "element": "Risk Callout", "title": "Disposition", "composition_role": "decision_risk", "section_id": "decision", "statement": "Do not release R17 yet.", "detail": "The missing sample is a required validation result; passing checks do not close that requirement.", "status": "Hold · evidence incomplete"},
            {"id": "f-next", "type": "text", "engine": "TextEngine", "element": "Key Takeaway", "title": "Next step", "composition_role": "conclusion", "section_id": "delivery", "showTitle": True, "text": "Review the sample as soon as it posts, then repeat disposition.", "body": "Review the sample as soon as it posts, then repeat disposition."},
        ]
    for order, item in enumerate(items):
        item["order"] = order
    return {
        "schema_version": 1, "authoring_schema": "authoring-p0-v1",
        "canvas": {"width": 1600, "height": 900}, "mode": "smart", "crossFilter": None,
        "layoutPreset": "editorial", "items": items, "groups": {}, "datasets": [], "nextId": 6,
    }


def scene_models(root: Path) -> tuple[dict[str, dict], str]:
    source, fixture_hash = fixture_models(root)
    required = {meta["fixture"] for key, meta in SCENES.items() if key.startswith(("A-", "B-", "C-", "D-"))}
    result = {key: copy.deepcopy(source[key]) for key in required}
    result["fresh-cold-chain"] = fresh_cold_chain(source["supply-chain-capacity-holdout"])
    result["fresh-release"] = fresh_sparse_release()
    return result, fixture_hash


def settle(page, timeout=20000):
    page.wait_for_function("()=>{const s=window.CompanyUIVisualizerBridge?.state?.();return s&&s.pending===0&&!s.inflight}", timeout=timeout)


def open_report(page, host: NativeHost, report_id: str, width: int = 1440):
    page.set_viewport_size({"width": width, "height": 1000 if width > 500 else 844})
    response = page.goto(f"{host.url}/visualizer?report={report_id}", wait_until="domcontentloaded")
    assert response and response.status == 200
    ready(page, require_settled=True)
    if page.locator("#libraryToggle").get_attribute("aria-pressed") == "true":
        page.locator("#libraryToggle").click()
    if page.locator("#inspectorToggle").get_attribute("aria-pressed") == "true":
        page.locator("#inspectorToggle").click()


def semantic_snapshot(model: dict) -> dict:
    return {
        "datasets": model.get("datasets", []),
        "items": [
            {key: value for key, value in item.items() if key not in {"x", "y", "w", "h", "order"}}
            for item in model.get("items", [])
        ],
    }


def capture_state(page) -> dict:
    return page.evaluate(
        """()=>{
          const root=document.querySelector('.cui-visualizer-root'),prod=window.__VIZ_PROD__,bridge=window.CompanyUIVisualizerBridge,hull=document.querySelector('#hull');
          const model=bridge?.state?.()?.model||null,rect=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return{id:e.dataset.id||'',role:e.dataset.compositionRole||'',section:e.dataset.section||'',pattern:e.dataset.sectionPattern||'',level:e.dataset.compositionLevel||'',x:r.x,y:r.y,w:r.width,h:r.height,fontPx:parseFloat(getComputedStyle(e.querySelector('.c-content')||e).fontSize)||0,scrollWidth:e.scrollWidth,clientWidth:e.clientWidth,scrollHeight:e.scrollHeight,clientHeight:e.clientHeight,order:s.order,text:(e.innerText||'').trim().slice(0,180)}};
          const items=[...document.querySelectorAll('#componentLayer>.component')].map(rect),heads=[...document.querySelectorAll('#componentLayer .composition-section-heading')].map(e=>({text:e.innerText.trim(),section:e.dataset.section,pattern:e.dataset.sectionPattern,direction:e.dataset.direction,role:e.getAttribute('role'),level:e.getAttribute('aria-level'),rect:{x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y,w:e.getBoundingClientRect().width,h:e.getBoundingClientRect().height}}));
          const surfaces=[...document.querySelectorAll('#compositionSectionSurfaceLayer .composition-section-surface')].map(e=>({section:e.dataset.section,pattern:e.dataset.pattern,direction:e.dataset.direction,containment:e.dataset.containment}));
          const geometry=prod?.layoutGeometry?.()||null,layoutItems=geometry?.items||[],viewport=document.querySelector('.viewport');
          const directionControl=document.querySelector('#visualDirectionSelect'),directionLabel=directionControl&&document.querySelector(`label[for="${directionControl.id}"]`),directionDescription=directionControl?.getAttribute('aria-describedby');
          const accessibility={canvasHeadingCount:heads.length,headingsNamedAndLevelled:heads.every(h=>Boolean(h.text)&&h.role==='heading'&&h.level==='2'),directionControl:{present:Boolean(directionControl),labelled:Boolean(directionLabel?.textContent.trim()),described:Boolean(directionDescription&&document.getElementById(directionDescription)),focused:Boolean(directionControl&&document.activeElement===directionControl),focusIndicator:directionControl?{outline:getComputedStyle(directionControl).outlineStyle,outlineWidth:getComputedStyle(directionControl).outlineWidth}:null},skipToMain:Boolean(document.querySelector('a[href*="#main"]')||document.querySelector('[data-skip-to-main]'))};
          const canvasElement=hull?{rect:{x:hull.getBoundingClientRect().x,y:hull.getBoundingClientRect().y,w:hull.getBoundingClientRect().width,h:hull.getBoundingClientRect().height},clientWidth:hull.clientWidth,clientHeight:hull.clientHeight,scrollWidth:hull.scrollWidth,scrollHeight:hull.scrollHeight}:null;
          const viewportElement=viewport?{rect:{x:viewport.getBoundingClientRect().x,y:viewport.getBoundingClientRect().y,w:viewport.getBoundingClientRect().width,h:viewport.getBoundingClientRect().height},scrollTop:viewport.scrollTop,scrollHeight:viewport.scrollHeight,clientHeight:viewport.clientHeight,overflow:getComputedStyle(viewport).overflow}:null;
          return {viewport:{width:innerWidth,height:innerHeight,documentWidth:document.documentElement.scrollWidth,bodyWidth:document.body.scrollWidth,documentHeight:document.documentElement.scrollHeight},canvasElement,viewportElement,mode:model?.mode||'',layoutPreset:model?.layoutPreset||'',visualDirection:prod?.visualDirection?.()||null,rootDirection:root?.dataset.visualDirection||'',items,headings:heads,surfaces,geometry,geometryViolations:layoutItems.filter(item=>!Number.isFinite(item.x)||!Number.isFinite(item.y)||item.x<0||item.y<0||item.w<=0||item.h<=0||item.x+item.w>geometry.canvas.width+1||item.y+item.h>geometry.canvas.height+1),accessibility};
        }"""
    )


def capture_reading_canvas(page, target: Path) -> dict:
    """Save the complete report canvas, scrolling the real desktop viewport when needed."""
    page.evaluate("""()=>{window.scrollTo(0,0);const v=document.querySelector('.viewport');if(v)v.scrollTop=0;const fit=document.getElementById('previewFitWidth'),targets=[fit?.parentElement,document.getElementById('previewExit')].filter(Boolean);window.__chg209ScreenshotChrome=targets.map(e=>({e,value:e.style.visibility}));targets.forEach(e=>e.style.visibility='hidden')}""")
    def restore_chrome():
        page.evaluate("""()=>{for(const row of window.__chg209ScreenshotChrome||[])row.e.style.visibility=row.value;delete window.__chg209ScreenshotChrome}""")
    dpr = page.evaluate("()=>window.devicePixelRatio")
    initial = page.evaluate("""()=>{const h=document.querySelector('#hull'),v=document.querySelector('.viewport'),hr=h.getBoundingClientRect(),vr=v.getBoundingClientRect();return {hull:{x:hr.x,y:hr.y,w:hr.width,h:hr.height},viewport:{x:vr.x,y:vr.y,w:vr.width,h:vr.height,scrollHeight:v.scrollHeight,clientHeight:v.clientHeight,scrollTop:v.scrollTop},width:innerWidth,height:innerHeight}}""")
    target.parent.mkdir(parents=True, exist_ok=True)
    if initial["width"] <= 800:
        page_bytes = page.screenshot(full_page=True, animations="disabled")
        with Image.open(BytesIO(page_bytes)) as image:
            source = image.convert("RGB")
            x0, y0 = round(initial["hull"]["x"] * dpr), round(initial["hull"]["y"] * dpr)
            width = round(initial["hull"]["w"] * dpr)
            height = round(max(initial["hull"]["h"], page.evaluate("()=>document.querySelector('#hull').scrollHeight")) * dpr)
            x1, y1 = min(source.width, x0 + width), min(source.height, y0 + height)
            source.crop((x0, y0, x1, y1)).save(target)
            restore_chrome()
            return {"method": "full-page screenshot cropped to complete responsive report canvas", "crop": {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0}, "clipped_right_px": max(0, width - (x1 - x0)), "clipped_bottom_px": max(0, height - (y1 - y0))}

    width, height = round(initial["hull"]["w"] * dpr), round(initial["hull"]["h"] * dpr)
    canvas = Image.new("RGB", (width, height), "white")
    viewport_height = initial["viewport"]["clientHeight"]
    max_scroll = max(0, initial["viewport"]["scrollHeight"] - viewport_height)
    step = max(1, int(viewport_height * .72))
    offsets = list(range(0, int(max_scroll) + 1, step))
    if not offsets or offsets[-1] != int(max_scroll):
        offsets.append(int(max_scroll))
    crops = []
    for offset in offsets:
        page.evaluate("offset=>{const v=document.querySelector('.viewport');v.scrollTop=offset;window.scrollTo(0,0)}", offset)
        page.wait_for_timeout(90)
        location = page.evaluate("""()=>{const h=document.querySelector('#hull').getBoundingClientRect(),v=document.querySelector('.viewport').getBoundingClientRect();return {h:{x:h.x,y:h.y,w:h.width,h:h.height},v:{x:v.x,y:v.y,w:v.width,h:v.height},scrollTop:document.querySelector('.viewport').scrollTop}}""")
        screenshot = page.screenshot(animations="disabled")
        with Image.open(BytesIO(screenshot)) as shot:
            frame = shot.convert("RGB")
            screen_top = max(location["h"]["y"], location["v"]["y"], 0)
            screen_bottom = min(location["h"]["y"] + location["h"]["h"], location["v"]["y"] + location["v"]["h"], initial["height"])
            sx0, sy0 = round(location["h"]["x"] * dpr), round(screen_top * dpr)
            sx1, sy1 = min(frame.width, sx0 + width), min(frame.height, round(screen_bottom * dpr))
            dx0, dy0 = 0, round((screen_top - location["h"]["y"]) * dpr)
            dx1, dy1 = dx0 + (sx1 - sx0), dy0 + (sy1 - sy0)
            if sx1 > sx0 and sy1 > sy0 and dx1 <= width and dy1 <= height:
                canvas.paste(frame.crop((sx0, sy0, sx1, sy1)), (dx0, dy0))
            crops.append({"scrollTop": location["scrollTop"], "source": [sx0, sy0, sx1, sy1], "destination": [dx0, dy0, dx1, dy1]})
    canvas.save(target)
    page.evaluate("()=>{const v=document.querySelector('.viewport');if(v)v.scrollTop=0}")
    restore_chrome()
    return {"method": "overlapping native viewport captures stitched to full report canvas", "scroll_offsets": offsets, "crops": crops, "clipped_right_px": 0, "clipped_bottom_px": 0}


def save_scene(page, output: Path, scene_id: str, include_320: bool) -> dict:
    details = {"viewports": {}, "screenshots": {}}
    page.set_viewport_size({"width": 1440, "height": 1000})
    if not page.locator(".cui-visualizer-root.preview-mode").count():
        page.locator("#previewBtn").click()
        page.locator(".cui-visualizer-root.preview-mode").wait_for(timeout=10000)
    for viewport_id in (["desktop-1440", "narrow-390", "narrow-320"] if include_320 else ["desktop-1440", "narrow-390"]):
        width = VIEWPORTS[viewport_id]
        page.set_viewport_size({"width": width, "height": 1000 if width > 500 else 844})
        if page.locator("#previewFitWidth").count() and page.locator("#previewFitWidth").is_visible():
            page.locator("#previewFitWidth").click()
        else:
            page.evaluate("window.__VIZ_PROD__?.fitZoom?.('width')")
        page.wait_for_timeout(180)
        state = capture_state(page)
        target = output / "screenshots" / f"{viewport_id}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        capture = capture_reading_canvas(page, target)
        details["viewports"][viewport_id] = state
        with Image.open(target) as image:
            details["screenshots"][viewport_id] = {"path": target.relative_to(output).as_posix(), "sha256": digest(target), "width": image.width, "height": image.height, "capture": capture}
    return details


def exercise_user_control(page, host: NativeHost, report_id: str) -> dict:
    if not page.evaluate("Boolean(window.__VIZ_PROD__?.visualDirection)"):
        return {"available": False, "reason": "Exact base predates the Visual Director control."}
    page.set_viewport_size({"width": 1440, "height": 1000})
    if page.locator(".cui-visualizer-root.preview-mode").count():
        page.evaluate("()=>{const e=document.getElementById('previewExit');if(e)e.style.visibility=''}")
        page.locator("#previewExit").click()
    if page.locator("#libraryToggle").get_attribute("aria-pressed") != "true":
        page.locator("#libraryToggle").click()
    page.locator("#presetsTab").click()
    select = page.locator("#visualDirectionSelect")
    select.wait_for(state="visible")
    select.focus()
    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")
    control_accessibility = page.evaluate("""()=>{const e=document.querySelector('#visualDirectionSelect'),label=document.querySelector('label[for="visualDirectionSelect"]'),described=e?.getAttribute('aria-describedby'),r=e?.getBoundingClientRect(),s=e&&getComputedStyle(e);return {label:label?.textContent.trim()||'',description:described?document.getElementById(described)?.textContent.trim()||'':'',focused:document.activeElement===e,focusVisible:Boolean(e?.matches(':focus-visible')),outline:s?.outlineStyle||'',outlineWidth:s?.outlineWidth||'',boxShadow:s?.boxShadow||'',withinViewport:Boolean(r&&r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight)}}""")
    assert control_accessibility["label"] and control_accessibility["description"] and control_accessibility["focused"] and control_accessibility["withinViewport"], control_accessibility
    before_model = page.evaluate("()=>CompanyUIVisualizerBridge.state().model")
    before_profile = page.evaluate("()=>__VIZ_PROD__.visualDirection()")
    before_semantics = canonical_hash(semantic_snapshot(before_model))

    select.select_option("editorial")
    page.wait_for_function("()=>CompanyUIVisualizerBridge.state().model.visualDirectionChoice==='editorial'")
    settle(page)
    override_profile = page.evaluate("()=>__VIZ_PROD__.visualDirection()")
    override_semantics = canonical_hash(semantic_snapshot(page.evaluate("()=>CompanyUIVisualizerBridge.state().model")))
    assert override_profile["id"] == "editorial" and override_profile["authority"] == "user-direction", override_profile
    assert override_semantics == before_semantics, "Changing direction must not change report values, mappings, bindings, or content."

    page.locator("#undo").click()
    page.wait_for_function("()=>CompanyUIVisualizerBridge.state().model.visualDirectionChoice===undefined")
    assert page.evaluate("()=>__VIZ_PROD__.visualDirection().id") == before_profile["id"]
    page.locator("#redo").click()
    page.wait_for_function("()=>CompanyUIVisualizerBridge.state().model.visualDirectionChoice==='editorial'")
    settle(page)
    persisted = host.repository.get(report_id).model.get("visualDirectionChoice")
    assert persisted == "editorial", persisted
    page.reload(wait_until="domcontentloaded")
    ready(page, require_settled=True)
    assert page.evaluate("()=>CompanyUIVisualizerBridge.state().model.visualDirectionChoice") == "editorial"
    assert page.evaluate("()=>__VIZ_PROD__.visualDirection().authority") == "user-direction"

    if page.locator("#libraryToggle").get_attribute("aria-pressed") != "true":
        page.locator("#libraryToggle").click()
    page.locator("#presetsTab").click()
    select = page.locator("#visualDirectionSelect")
    select.select_option("auto")
    page.wait_for_function("()=>CompanyUIVisualizerBridge.state().model.visualDirectionChoice==='auto'")
    settle(page)
    assert page.evaluate("()=>__VIZ_PROD__.visualDirection().id") == before_profile["id"]
    auto_profile = page.evaluate("()=>__VIZ_PROD__.visualDirection()")

    page.locator('[data-mode="free"]').click()
    page.wait_for_function("()=>CompanyUIVisualizerBridge.state().model.mode==='free'")
    manual_before = page.evaluate("()=>CompanyUIVisualizerBridge.state().model.items.map(({id,x,y,w,h})=>({id,x,y,w,h}))")
    select = page.locator("#visualDirectionSelect")
    select.select_option("causal-investigation")
    page.wait_for_function("()=>CompanyUIVisualizerBridge.state().model.visualDirectionChoice==='causal-investigation'")
    settle(page)
    manual_after = page.evaluate("()=>CompanyUIVisualizerBridge.state().model.items.map(({id,x,y,w,h})=>({id,x,y,w,h}))")
    assert manual_after == manual_before, "Free mode must not recompose saved manual geometry when direction changes."
    manual_choice_profile = page.evaluate("()=>__VIZ_PROD__.visualDirection()")
    select.select_option("auto")
    page.wait_for_function("()=>CompanyUIVisualizerBridge.state().model.visualDirectionChoice==='auto'")
    settle(page)
    manual_restored = page.evaluate("()=>CompanyUIVisualizerBridge.state().model.items.map(({id,x,y,w,h})=>({id,x,y,w,h}))")
    assert manual_restored == manual_before
    return {
        "available": True,
        "auto_before": before_profile,
        "explicit_override": override_profile,
        "undo_redo": {"undo_restored_auto": True, "redo_restored_user_choice": True},
        "save_reload": {"stored_choice": persisted, "restored_choice": "editorial"},
        "auto_reversal": auto_profile,
        "manual_free": {"before": manual_before, "after_choice": manual_after, "restored": manual_restored, "profile_while_manual": manual_choice_profile},
        "source_semantics_sha256_before": before_semantics,
        "source_semantics_sha256_after_override": override_semantics,
        "source_and_dataset_immutability": override_semantics == before_semantics,
        "accessible_user_control": control_accessibility,
    }


def full_profile_receipt(scene: dict, runtime: dict) -> dict:
    profile = runtime["visualDirection"] or {}
    return {
        **{key: scene[key] for key in ("title", "person", "context", "task", "decision", "current_truth", "tone", "misunderstanding")},
        "character": profile.get("traits", []),
        "negative_identity": profile.get("negativeIdentity"),
        "density": profile.get("density", {}).get("evidence"),
        "hierarchy": {"strongest_salience": profile.get("focus", {}).get("primaryRoles", []), "recipe": profile.get("recipeId"), "authority": profile.get("authority")},
        "spacing_grouping": {"spacing": profile.get("spacing"), "sections": runtime.get("section_plan", [])},
        "surfaces": profile.get("sectionTreatment"),
        "data_density_treatment": profile.get("density"),
        "typography": profile.get("typography"),
        "semantic_emphasis": profile.get("emphasis"),
        "responsive_recomposition": profile.get("responsive"),
        "observed_viewports": {key: {"width": value["viewport"]["width"], "document_width": value["viewport"]["documentWidth"], "component_count": len(value["items"]), "reading_order": [item["id"] for item in sorted(value["items"], key=lambda item: (float(item["y"]), float(item["x"])))], "headings": value["headings"]} for key, value in runtime["viewports"].items()},
    }


def capture_side(app_root: Path, output: Path, side: str, run_controls: bool) -> dict:
    models, fixture_hash = scene_models(app_root)
    output.mkdir(parents=True, exist_ok=True)
    receipt = {"side": side, "app_root": str(app_root), "commit": git(app_root, "rev-parse", "HEAD"), "tree": git(app_root, "rev-parse", "HEAD^{tree}"), "fixture": {"path": FIXTURE.as_posix(), "sha256": fixture_hash}, "scenes": {}, "browser_errors": [], "status": "RUNNING"}
    events = BrowserEvents()
    with tempfile.TemporaryDirectory(prefix=f"chg209-{side}-") as temporary:
        with NativeHost(app_root, Path(temporary) / "data") as host:
            report_ids = {}
            for scene_id, metadata in SCENES.items():
                model = models[metadata["fixture"]]
                report_id = host.create(model=copy.deepcopy(model), name=f"chg209-{side}-{scene_id.lower()}")
                report_ids[scene_id] = report_id
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(**browser_kwargs())
                context = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
                page = context.new_page()
                page.set_default_timeout(12000)
                events.attach(page)
                for scene_id, metadata in SCENES.items():
                    report_id = report_ids[scene_id]
                    open_report(page, host, report_id)
                    initial_model = page.evaluate("()=>CompanyUIVisualizerBridge.state().model")
                    input_hash = canonical_hash(semantic_snapshot(initial_model))
                    runtime = save_scene(page, output / "scenes" / scene_id, scene_id, scene_id in {"D-technical", "E-holdout-mixed"})
                    runtime["visualDirection"] = runtime["viewports"]["desktop-1440"]["visualDirection"]
                    if runtime["viewports"]["desktop-1440"]["viewport"]["documentWidth"] > 1440:
                        raise AssertionError(f"{scene_id}: desktop report overflows horizontally.")
                    for viewport, state in runtime["viewports"].items():
                        width = VIEWPORTS[viewport]
                        if state["viewport"]["documentWidth"] > width:
                            raise AssertionError(f"{scene_id} {viewport}: report has horizontal page overflow.")
                    if side == "candidate":
                        profile = runtime["visualDirection"]
                        assert profile and len(profile.get("traits", [])) == 3, (scene_id, profile)
                        assert profile["id"] == EXPECTED_DIRECTIONS[scene_id], (scene_id, profile["id"], EXPECTED_DIRECTIONS[scene_id])
                        expected_sections = page.evaluate("()=>__VIZ_PROD__.layoutRects().map(item=>({section:item.section,pattern:item.sectionPattern,role:item.role,level:item.compositionLevel}))")
                        runtime["section_plan"] = expected_sections
                        assert canonical_hash(semantic_snapshot(page.evaluate("()=>CompanyUIVisualizerBridge.state().model"))) == input_hash, f"{scene_id}: capture changed source values, mappings, or content."
                        for viewport, state in runtime["viewports"].items():
                            assert not state["geometryViolations"], f"{scene_id} {viewport}: component outside report canvas: {state['geometryViolations']}"
                            assert state["accessibility"]["headingsNamedAndLevelled"], f"{scene_id} {viewport}: malformed section headings."
                    else:
                        runtime["section_plan"] = runtime["viewports"]["desktop-1440"]["headings"]
                    receipt["scenes"][scene_id] = {
                        "report_id": report_id,
                        "input_model_sha256": input_hash,
                        "direction_review": full_profile_receipt(metadata, runtime),
                        "runtime": runtime,
                    }
                    if side == "candidate" and scene_id == "A-executive" and run_controls:
                        receipt["user_control_reversibility"] = exercise_user_control(page, host, report_id)
                    page.goto("about:blank")
                receipt["browser_errors"] = events.unexpected
                receipt["native_runtime"] = {"nicegui": "3.15.0", "browser": browser.version, "host": "real NiceGUI application with isolated synthetic report repository"}
                context.close()
                browser.close()
    assert not receipt["browser_errors"], receipt["browser_errors"]
    receipt["status"] = "PASS"
    write_json(output / "matrix-receipt.json", receipt)
    return receipt


def contact_sheet(base_dir: Path, candidate_dir: Path, output: Path, viewport: str, scene_ids: list[str]):
    font = ImageFont.load_default()
    cell_w, cell_h, label_h, margin = 600, 550, 34, 14
    sheet = Image.new("RGB", (margin + 2 * (cell_w + margin), margin + len(scene_ids) * (cell_h + label_h + margin)), "#e8ebef")
    draw = ImageDraw.Draw(sheet)
    for row, scene_id in enumerate(scene_ids):
        y = margin + row * (cell_h + label_h + margin)
        for col, (label, root) in enumerate((("Exact base", base_dir), ("Candidate", candidate_dir))):
            x = margin + col * (cell_w + margin)
            draw.text((x + 6, y + 4), f"{scene_id} · {label} · {viewport}", fill="#1b2733", font=font)
            path = root / "scenes" / scene_id / "screenshots" / f"{viewport}.png"
            with Image.open(path) as original:
                image = original.convert("RGB")
                image.thumbnail((cell_w - 12, cell_h - 12), Image.Resampling.LANCZOS)
                sheet.paste(image, (x + (cell_w - image.width) // 2, y + label_h + (cell_h - image.height) // 2))
            draw.rectangle((x, y + label_h, x + cell_w, y + label_h + cell_h), outline="#9aa5b1", width=1)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--side", choices=("base", "candidate"), required=True)
    parser.add_argument("--exercise-user-control", action="store_true")
    args = parser.parse_args()
    root, output = args.app_root.expanduser().resolve(), args.output.expanduser().resolve()
    if args.side == "candidate" and root != ROOT.resolve():
        print(f"runner ROOT {ROOT.resolve()} differs from candidate app root {root}", file=sys.stderr)
        return 2
    try:
        result = capture_side(root, output, args.side, args.exercise_user_control)
        print(json.dumps({"status": result["status"], "side": result["side"], "commit": result["commit"], "scene_count": len(result["scenes"]), "output": str(output)}, indent=2))
        return 0
    except Exception as exc:
        write_json(output / "matrix-receipt.json", {"status": "FAIL", "side": args.side, "error": str(exc)})
        raise


if __name__ == "__main__":
    raise SystemExit(main())
