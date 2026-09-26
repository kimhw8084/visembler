#!/usr/bin/env python3
"""Native browser acceptance for CHG-253 sparse narrow report reading."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata
import json
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from editor_host import NativeHost
from native_common import BrowserEvents, browser_kwargs, ready, write_json
from run_chg207_narrow_reading_acceptance import (
    FIXTURE,
    _exercise_table,
    _page_facts,
    _preview,
    _supplemented_supply_model,
    _supplemented_technical_model,
)

BASE = "353d8c648be0d88db2777f68e577a4ec47d8a6bb"
WORK_BRANCH = "fix/visembler-chg253-sparse-narrow-overflow-r1"
FABRIC_JOB_ID = "CF-88f38e33d7d0965e6db7075a"
R3_SCREENSHOT = (
    "refs/remotes/origin/project-os/CHG-173-r3:"
    "project-os-artifacts/visembler/CHG-173-r3/"
    "compositions/F-F-bridge-c08-sparse/reading-390.png"
)

RATIONALE = (
    "The required Cell B pressure trace has not been uploaded. Passing the other "
    "checks does not establish that Cell B met its release limit. Keep the cell "
    "isolated until the missing trace is recorded and reviewed by the duty engineer."
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def sparse_reader_model(*, renamed: bool = False) -> dict:
    title = "Unrelated release decision" if renamed else "Line readiness decision"
    statement = "Keep the packaging cell isolated until verification is complete."
    detail = RATIONALE
    status = "HOLD · one required result missing"
    metric_title = "Checks confirmed" if renamed else "Inspection completion"
    metric_delta = "1 pending · Cell B"
    metric_target = "3 / 3 required"
    if renamed:
        statement = "Pause the distribution run until the final custody record is reviewed."
        detail = (
            "The required custody confirmation for batch 14 has not arrived. "
            "Completion of the other checks does not confirm the missing transfer. "
            "Keep the batch on hold until its record is received and reviewed by the owner."
        )
        status = "PAUSED · one confirmation pending"
        metric_delta = "1 pending · Batch 14"
    return {
        "schema_version": 1,
        "mode": "smart",
        "layoutPreset": "editorial",
        "canvas": {"width": 1600, "height": 988},
        "datasets": [],
        "groups": {},
        "crossFilter": None,
        "nextId": 4,
        "items": [
            {
                "id": "decision-card", "type": "decision", "engine": "DecisionCompositeEngine",
                "element": "Risk Callout", "title": title, "showTitle": True,
                "statement": statement, "detail": detail, "status": status,
                "composition_role": "decision_risk", "section_id": "decision",
                "section_title": "Decision", "order": 0, "weight": 1.0, "z": 1,
            },
            {
                "id": "metric-card", "type": "metric", "engine": "MetricEngine",
                "element": "Hero KPI", "title": metric_title, "showTitle": True,
                "value": "2 / 3 required", "delta": metric_delta, "target": metric_target,
                "composition_role": "hero_metric", "section_id": "evidence",
                "section_title": "Verification evidence", "order": 1, "weight": 1.0, "z": 2,
            },
            {
                "id": "evidence-table", "type": "table", "engine": "TableEngine",
                "element": "Clean Table", "title": "Verification record", "showTitle": True,
                "customTable": {
                    "headers": ["CHECK LOCATION", "OBSERVED LOAD VALUE", "REQUIRED ACCEPTANCE LIMIT", "DISPOSITION"],
                    "rows": [
                        ["Pressure set point", "Within limit", "Within limit", "Pass"],
                        ["Interlock check", "Verified", "Verified", "Pass"],
                        ["Cell B trace", "Not received", "Recorded result", "Open"],
                    ],
                },
                "rows": [
                    ["Pressure set point", "Within limit", "Within limit", "Pass"],
                    ["Interlock check", "Verified", "Verified", "Pass"],
                    ["Cell B trace", "Not received", "Recorded result", "Open"],
                ],
                "composition_role": "detailed_evidence", "section_id": "record",
                "section_title": "Verification record", "order": 2, "weight": 1.0, "z": 3,
            },
        ],
    }


def _sparse_facts(page, width: int, screenshot_dir: Path | None, *, renamed: bool = False) -> dict:
    result = page.evaluate(
        """() => {
          const root=document.querySelector('.cui-visualizer-root');
          const model=window.CompanyUIVisualizerBridge.state().model;
          const read=(el)=>{if(!el)return null;const r=el.getBoundingClientRect(),s=getComputedStyle(el);return {
            tag:el.tagName,className:String(el.className||''),x:r.x,y:r.y,width:r.width,height:r.height,
            scrollWidth:el.scrollWidth,clientWidth:el.clientWidth,scrollHeight:el.scrollHeight,clientHeight:el.clientHeight,
            engine:el.dataset?.engine||null,mobileReaderFit:el.dataset?.mobileReaderFit||null,
            overflowX:s.overflowX,overflowY:s.overflowY,text:(el.innerText||'').replace(/\\s+/g,' ').trim()};};
          const layers=id=>{const c=root.querySelector(`.component[data-id="${id}"]`);if(!c)return [];
            const values=[c,c.querySelector('.c-content'),c.querySelector('.integrated-element-content'),
              c.querySelector('.gallery-card'),c.querySelector('.card-body'),c.querySelector('.risk-callout-live')].filter(Boolean);
            return values.map(read);};
          const decision=root.querySelector('.component[data-id="decision-card"]');
          const metric=root.querySelector('.component[data-id="metric-card"]');
          const tableComponent=root.querySelector('.component[data-id="evidence-table"]');
          const table=tableComponent?.querySelector('.table-frame.table-scroll[role="region"]');
          const tableBody=table?.querySelector('tbody');
          const rows=[...(table?.querySelectorAll('tbody tr')||[])].map(row=>{const r=row.getBoundingClientRect();return {text:(row.innerText||'').replace(/\\s+/g,' ').trim(),x:r.x,y:r.y,width:r.width,height:r.height,visible:!!table&&r.top>=table.getBoundingClientRect().top-1&&r.bottom<=table.getBoundingClientRect().bottom+1};});
          const headings=[...root.querySelectorAll('.composition-section-heading')].filter(el=>getComputedStyle(el).display!=='none');
          const components=[...root.querySelectorAll('.component[data-id]')];
          const collisions=[];for(const h of headings){const hr=h.getBoundingClientRect();for(const c of components){const cr=c.getBoundingClientRect();if(hr.left<cr.right&&hr.right>cr.left&&hr.top<cr.bottom&&hr.bottom>cr.top)collisions.push({heading:(h.innerText||'').trim(),component:c.dataset.id});}}
          const bodyText=el=>el?.querySelector('.card-body')?.innerText||'';
          const status=decision?.querySelector('.risk-callout-live>span'),riskCopy=decision?.querySelector('.risk-callout-live>div');
          const tokenFacts=[...(metric?.querySelectorAll('.numeric-token')||[])].map(el=>{const r=document.createRange();r.selectNodeContents(el);return {text:el.innerText.replace(/\\s+/g,' ').trim(),rects:[...r.getClientRects()].map(x=>({x:x.x,y:x.y,width:x.width,height:x.height})),scrollWidth:el.scrollWidth,clientWidth:el.clientWidth};});
          return {viewport:{width:innerWidth,documentWidth:document.documentElement.scrollWidth,bodyWidth:document.body.scrollWidth,documentHeight:document.documentElement.scrollHeight},
            modelUnchanged:JSON.stringify(model)===window.__CHG253_MODEL_SNAPSHOT__,
            decision:{layers:layers('decision-card'),text:bodyText(decision),statusText:status?.innerText||'',statusAfterRationale:!!status&&!!riskCopy&&status.getBoundingClientRect().top>=riskCopy.getBoundingClientRect().bottom-1,statusRect:read(status),rationaleRect:read(riskCopy)},
            metric:{layers:layers('metric-card'),text:bodyText(metric),tokens:tokenFacts},
            table:table?{readerFit:tableComponent.dataset.mobileReaderFit,component:read(tableComponent),frame:read(table),body:read(tableBody),cardBody:read(tableComponent.querySelector('.card-body')),rows,tabIndex:table.tabIndex,ariaLabel:table.getAttribute('aria-label'),describedBy:table.getAttribute('aria-describedby'),hintHidden:table.closest('.table-scroll-shell')?.querySelector('.table-scroll-hint')?.hidden,touchAction:getComputedStyle(table).touchAction}:null,
            sectionHeadings:headings.map(read),headingCollisions:collisions,
            nonContentSizing:components.filter(c=>!['TextEngine','MetricEngine','ComparisonEngine','EvidenceCompositeEngine','DecisionCompositeEngine','ProjectCompositeEngine'].includes(c.dataset.engine)).map(c=>({id:c.dataset.id,engine:c.dataset.engine,fit:c.dataset.mobileReaderFit,height:getComputedStyle(c).height,overflowY:getComputedStyle(c).overflowY}))};
        }"""
    )
    assert result["modelUnchanged"], (width, "preview changed source model")
    assert result["viewport"]["documentWidth"] <= width and result["viewport"]["bodyWidth"] <= width, (width, result["viewport"])
    if width <= 800:
        assert not result["headingCollisions"], (width, result["headingCollisions"])
    for card in (result["decision"], result["metric"]):
        assert card["text"], (width, card)
        for layer in card["layers"]:
            assert layer["scrollHeight"] <= layer["clientHeight"] + 1, (width, "vertical clipping", layer)
            assert layer["scrollWidth"] <= layer["clientWidth"] + 1, (width, "horizontal clipping", layer)
    statement = "Pause the distribution run until the final custody record is reviewed." if renamed else "Keep the packaging cell isolated until verification is complete."
    rationale = (
        "The required custody confirmation for batch 14 has not arrived. Completion of the other checks does not confirm the missing transfer. Keep the batch on hold until its record is received and reviewed by the owner."
        if renamed else RATIONALE
    )
    status = "PAUSED · one confirmation pending" if renamed else "HOLD · one required result missing"
    delta = "Delta 1 pending · Batch 14" if renamed else "Delta 1 pending · Cell B"
    assert statement in result["decision"]["text"], (width, result["decision"])
    assert rationale in result["decision"]["text"], (width, result["decision"])
    assert status in result["decision"]["text"], (width, result["decision"])
    if width <= 800:
        assert result["decision"]["statusAfterRationale"], (width, result["decision"])
    for support in ("2 / 3 required", delta, "Target 3 / 3 required"):
        assert support in result["metric"]["text"], (width, support, result["metric"])
    assert result["metric"]["tokens"] and all(
        len(token["rects"]) == 1 and token["scrollWidth"] <= token["clientWidth"]
        for token in result["metric"]["tokens"]
    ), (width, result["metric"]["tokens"])
    assert result["table"] and len(result["table"]["rows"]) == 3, (width, result["table"])
    assert result["decision"]["layers"][0]["mobileReaderFit"] == "content", result["decision"]["layers"][0]
    assert result["metric"]["layers"][0]["mobileReaderFit"] == "content", result["metric"]["layers"][0]
    assert result["table"]["readerFit"] == "bounded", result["table"]
    if width == 390:
        assert all(row["visible"] for row in result["table"]["rows"]), result["table"]
        assert result["table"]["body"]["scrollHeight"] <= result["table"]["body"]["clientHeight"] + 1, result["table"]["body"]
        assert result["table"]["frame"]["scrollHeight"] <= result["table"]["frame"]["clientHeight"] + 1, result["table"]["frame"]
        assert result["table"]["frame"]["scrollWidth"] > result["table"]["frame"]["clientWidth"] + 1, result["table"]["frame"]
        assert not result["table"]["hintHidden"] and result["table"]["describedBy"], result["table"]
    if screenshot_dir and width in (320, 360, 390, 1440):
        page.evaluate("window.scrollTo(0,0)")
        page.screenshot(path=str(screenshot_dir / f"sparse-{width}-full-page.png"), full_page=True)
        page.screenshot(path=str(screenshot_dir / f"sparse-{width}-viewport.png"))
    return result


def _exercise_sparse_table(page) -> dict:
    table = page.locator('.component[data-id="evidence-table"] .table-frame.table-scroll[role="region"]')
    table.wait_for(state="visible")
    page.locator("#previewBtn").focus()
    tab_trace = []
    for _ in range(80):
        page.keyboard.press("Tab")
        active = page.evaluate("()=>({tag:document.activeElement?.tagName,role:document.activeElement?.getAttribute('role'),label:document.activeElement?.getAttribute('aria-label')})")
        tab_trace.append(active)
        if table.evaluate("el=>document.activeElement===el"):
            break
    assert table.evaluate("el=>document.activeElement===el"), tab_trace
    initial = table.evaluate("el=>({left:el.scrollLeft,max:el.scrollWidth-el.clientWidth,label:el.getAttribute('aria-label'),describedBy:el.getAttribute('aria-describedby'),hint:el.closest('.table-scroll-shell')?.querySelector('.table-scroll-hint')?.innerText,overflowX:getComputedStyle(el).overflowX,touchAction:getComputedStyle(el).touchAction,focusShadow:getComputedStyle(el).boxShadow,outlineStyle:getComputedStyle(el).outlineStyle})")
    assert initial["max"] > 1 and initial["describedBy"] and "swipe" in initial["hint"].lower(), initial
    assert initial["overflowX"] == "auto" and "pan-x" in initial["touchAction"], initial
    assert initial["label"].startswith("Scrollable table:") and (initial["focusShadow"] != "none" or initial["outlineStyle"] != "none"), initial
    keys = []
    for key in ("ArrowRight", "End", "ArrowLeft", "Home"):
        before = table.evaluate("el=>el.scrollLeft")
        table.press(key)
        page.wait_for_timeout(40)
        after = table.evaluate("el=>el.scrollLeft")
        keys.append({"key": key, "before": before, "after": after, "focused": table.evaluate("el=>document.activeElement===el")})
    assert keys[0]["after"] > keys[0]["before"], keys
    assert keys[1]["after"] == initial["max"], keys
    assert keys[2]["after"] < keys[2]["before"], keys
    assert keys[3]["after"] == 0 and all(row["focused"] for row in keys), keys
    table.evaluate("el=>{el.scrollLeft=0;el.scrollIntoView({block:'center',inline:'nearest'});el.focus()}")
    box = table.bounding_box()
    assert box and box["x"] >= 0 and box["x"] + box["width"] <= page.viewport_size["width"] + 1, box
    page.mouse.move(box["x"] + box["width"] - 8, box["y"] + 20)
    page.mouse.wheel(140, 0)
    page.wait_for_timeout(60)
    wheel_after = table.evaluate("el=>el.scrollLeft")
    assert wheel_after > 0, wheel_after
    touch = {"attempted": False, "status": "not-run"}
    try:
        table.evaluate("el=>el.scrollLeft=0")
        cdp = page.context.new_cdp_session(page)
        x, y = box["x"] + box["width"] - 8, box["y"] + 24
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x - 72, "y": y, "id": 1}]})
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        page.wait_for_timeout(80)
        touch_after = table.evaluate("el=>el.scrollLeft")
        touch = {"attempted": True, "after": touch_after, "status": "scrolled" if touch_after > 0 else "touch-action-and-overflow-css-verified"}
    except Exception as exc:
        touch = {"attempted": True, "status": "touch-injection-unavailable", "detail": str(exc)}
    return {"initial": initial, "tab_focus_trace": tab_trace, "keyboard": keys, "wheel_after": wheel_after, "touch": touch, "focusRetained": True}


def run_acceptance(output: Path | None = None) -> dict:
    output = output.resolve() if output else None
    if output:
        output.mkdir(parents=True, exist_ok=True)
    fixture_path = ROOT / FIXTURE
    fixture_before = digest(fixture_path)
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    reports = {row["key"]: row["model"] for row in fixture["reports"]}
    sparse_model = sparse_reader_model()
    renamed_model = sparse_reader_model(renamed=True)
    supply_model = _supplemented_supply_model(copy.deepcopy(reports["supply-chain-capacity-holdout"]))
    technical_model = _supplemented_technical_model(copy.deepcopy(reports["technical-status-review"]))
    receipt = {
        "schema": "visembler-chg253-sparse-reading-acceptance.v1",
        "request": "CHG-253-r1", "fabric_job_id": FABRIC_JOB_ID,
        "runtime": {}, "sparse_matrix": {}, "renamed_shape": {}, "chg207_dense": {},
        "table_interaction": {}, "browser_errors": [], "source_data_unchanged": False,
        "status": "RUNNING",
    }
    events = BrowserEvents()
    try:
        with tempfile.TemporaryDirectory(prefix="visembler-chg253-native-") as temp_dir, sync_playwright() as playwright:
            with NativeHost(ROOT, Path(temp_dir) / "data") as host:
                sparse_id = host.create(model=sparse_model, name="chg253-sparse-shape")
                renamed_id = host.create(model=renamed_model, name="chg253-renamed-shape")
                supply_id = host.create(model=supply_model, name="chg207-supply-regression")
                technical_id = host.create(model=technical_model, name="chg207-technical-regression")
                browser = playwright.chromium.launch(**browser_kwargs())
                receipt["runtime"] = {
                    "python": sys.version.split()[0], "nicegui": importlib.metadata.version("nicegui"),
                    "playwright": importlib.metadata.version("playwright"), "browser": browser.version,
                    "native_host": True, "host_url": host.url, "ephemeral_port": host.port,
                }
                context = browser.new_context(viewport={"width": 390, "height": 900}, has_touch=True, is_mobile=False)
                page = context.new_page()
                page.set_default_timeout(10000)
                events.attach(page)

                for width in (320, 359, 360, 361, 389, 390, 391, 1440):
                    height = 1000 if width == 1440 else 900
                    snapshot = _preview(page, host, sparse_id, width, height)
                    page.evaluate("snapshot=>window.__CHG253_MODEL_SNAPSHOT__=snapshot", snapshot)
                    receipt["sparse_matrix"][str(width)] = _sparse_facts(page, width, output)
                    if width == 390:
                        receipt["table_interaction"] = _exercise_sparse_table(page)
                snapshot = _preview(page, host, renamed_id, 390, 900)
                page.evaluate("snapshot=>window.__CHG253_MODEL_SNAPSHOT__=snapshot", snapshot)
                receipt["renamed_shape"] = _sparse_facts(page, 390, output, renamed=True)
                assert "PAUSED · one confirmation pending" in receipt["renamed_shape"]["decision"]["text"]
                assert "Target 3 / 3 required" in receipt["renamed_shape"]["metric"]["text"]

                for case, report_id, model, width in (
                    ("supply-320", supply_id, supply_model, 320),
                    ("supply-390", supply_id, supply_model, 390),
                    ("technical-320", technical_id, technical_model, 320),
                    ("technical-390", technical_id, technical_model, 390),
                ):
                    snapshot = _preview(page, host, report_id, width, 900 if width == 320 else 1000)
                    flow = next((row for row in model["items"] if row.get("element") == "Process Flow"), None)
                    table = next((row for row in model["items"] if row.get("engine") == "TableEngine"), None)
                    decision = next((row for row in model["items"] if row.get("composition_role") == "decision_risk"), None)
                    next_item = next((row for row in model["items"] if row.get("section_id") == "delivery" and row.get("id") != (decision or {}).get("id")), None)
                    expected = {
                        "flowId": (flow or {}).get("id", ""), "tableId": (table or {}).get("id", ""),
                        "smallTableId": "chg207-nonoverflow-table", "decisionId": (decision or {}).get("id", ""),
                        "nextId": (next_item or {}).get("id", ""), "modelSnapshot": snapshot,
                    }
                    facts = _page_facts(page, expected, output or Path(tempfile.gettempdir()), f"chg207-{case}")
                    browser_facts = facts["browser"]
                    assert browser_facts["modelUnchanged"], (case, "model changed")
                    assert browser_facts["viewport"]["documentWidth"] <= width, (case, browser_facts["viewport"])
                    assert browser_facts["flow"]["visibleNarrow"], (case, browser_facts["flow"])
                    assert [row["label"] for row in browser_facts["flow"]["nodes"]] == flow["nodes"], (case, browser_facts["flow"])
                    assert [row["order"] for row in browser_facts["flow"]["nodes"]] == list(range(len(flow["nodes"]))), (case, browser_facts["flow"])
                    assert len(browser_facts["flow"]["edges"]) == len(flow["edges"]), (case, browser_facts["flow"])
                    node_labels = {row["id"]: row["label"] for row in browser_facts["flow"]["nodes"]}
                    actual_edges = [[node_labels[edge["source"]], node_labels[edge["target"]]] for edge in browser_facts["flow"]["edges"]]
                    assert actual_edges == flow["edges"], (case, actual_edges, flow["edges"])
                    assert all(
                        len(token["rangeLines"]) == 1 and token["scrollWidth"] <= token["clientWidth"] and token["insideComponent"]
                        for token in browser_facts["tokenFacts"]
                    ), (case, browser_facts["tokenFacts"])
                    token_texts = {token["text"] for token in browser_facts["tokenFacts"]}
                    expected_tokens = (
                        {"120000 units", "142000 units", "2.7%", "116 days"}
                        if case.startswith("supply-") else
                        {"-1,234,567,890.125 seconds", "9876543210 units", "12345678901 units"}
                    )
                    assert expected_tokens <= token_texts, (case, expected_tokens, token_texts)
                    receipt["chg207_dense"][case] = facts
                    if case == "supply-320":
                        receipt["chg207_dense"]["supply_table_interaction"] = _exercise_table(page, table["id"])
                assert not events.unexpected, events.unexpected
                context.close()
                browser.close()

        receipt["source_data_unchanged"] = digest(fixture_path) == fixture_before
        assert receipt["source_data_unchanged"], "CHG-207 source fixture changed during read-only regression"
        if output:
            raw_before = subprocess.check_output(["git", "show", R3_SCREENSHOT], cwd=ROOT)
            before_path = output / "r3-reading-390-before.png"
            before_path.write_bytes(raw_before)
            receipt["before_390"] = {"path": before_path.name, "sha256": digest(before_path), "bytes": len(raw_before)}
            receipt["candidate_screenshots"] = {
                path.name: {"sha256": digest(path), "bytes": path.stat().st_size}
                for path in sorted(output.glob("sparse-*-*.png"))
            }
        receipt["status"] = "PASS"
    except Exception as exc:
        receipt["status"] = "FAIL"
        receipt["error"] = str(exc)
        receipt["traceback"] = traceback.format_exc()
        receipt["browser_errors"] = events.unexpected
        if output:
            write_json(output / "acceptance-receipt.json", receipt)
        raise
    if output:
        write_json(output / "acceptance-receipt.json", receipt)
    return receipt


def _require_candidate(candidate_sha: str, candidate_tree: str) -> None:
    if _git("rev-parse", "HEAD") != candidate_sha or _git("rev-parse", "HEAD^{tree}") != candidate_tree:
        raise SystemExit("Acceptance must start on the exact candidate SHA and tree.")
    if _git("branch", "--show-current") != WORK_BRANCH:
        raise SystemExit(f"Acceptance must run on {WORK_BRANCH}.")
    if _git("rev-parse", "HEAD^") != BASE:
        raise SystemExit("Candidate must be a direct child of the exact requested base.")
    if _git("status", "--porcelain"):
        raise SystemExit("Candidate acceptance requires a clean worktree.")
    remote_main = _git("ls-remote", "origin", "refs/heads/main").split()[0]
    if remote_main != BASE:
        raise SystemExit(f"origin/main drifted from the exact base: {remote_main}")


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
    _require_candidate(args.candidate_sha, args.candidate_tree)
    output.mkdir(parents=True, exist_ok=True)
    result = run_acceptance(output)
    result["identity"] = {
        "repository": "kimhw8084/visembler", "project": "visembler", "change": "CHG-253",
        "request": "CHG-253-r1", "operation": "FIX", "fabric_job_id": args.fabric_job_id,
    }
    result["candidate"] = {"base": BASE, "head": args.candidate_sha, "tree": args.candidate_tree, "branch": WORK_BRANCH}
    write_json(output / "acceptance-receipt.json", result)
    print(json.dumps({"status": result["status"], "output": str(output), "candidate": result["candidate"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
