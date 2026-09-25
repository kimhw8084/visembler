from __future__ import annotations

import hashlib
import json
import subprocess
from types import SimpleNamespace
from pathlib import Path

import pytest
from playwright.sync_api import Error as PlaywrightError

from company_ui.products.visualizer.page import _history_diff_summary, _report_thumbnail_markup
from company_ui.products.visualizer.repository import ReportRepository
from scripts.release_checks.run_final_visual_remediation_acceptance import fixture, goto_local_route
from scripts.release_checks.waferfab_visual_contracts import LEGACY_WAFERFAB_SELECTOR, WAFERFAB_RENDERER_CONTRACTS


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "company_ui/products/visualizer/assets"
FROZEN = ROOT / "company_ui/products/visualizer/vendor/production_core/core/GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js"


class _NavigationPage:
    def __init__(self, failures: list[str], events=None) -> None:
        self.failures = list(failures)
        self.events = events
        self.calls = 0
        self.waits: list[int] = []

    def goto(self, url: str, *, wait_until: str):
        self.calls += 1
        if self.failures:
            detail = self.failures.pop(0)
            if self.events is not None:
                self.events.unexpected.append(
                    {"kind": "requestfailed", "detail": f"{url} :: {detail}"}
                )
            raise PlaywrightError(f"Page.goto: net::{detail} at {url}")
        return "loaded"

    def wait_for_timeout(self, milliseconds: int) -> None:
        self.waits.append(milliseconds)


def test_visual_acceptance_retries_only_transient_local_navigation_faults() -> None:
    events = SimpleNamespace(unexpected=[], expected_fault=[])
    retries: list[dict] = []
    page = _NavigationPage(["ERR_ABORTED"], events)
    assert goto_local_route(page, "http://127.0.0.1:9000/visualizer", events=events, retry_log=retries) == "loaded"
    assert page.calls == 2 and page.waits == [100]
    assert events.unexpected == []
    assert events.expected_fault[0]["kind"] == "requestfailed"
    assert retries == [{"url": "http://127.0.0.1:9000/visualizer", "attempt": 1, "reason": "ERR_ABORTED"}]

    deterministic = _NavigationPage(["ERR_CONNECTION_REFUSED"])
    with pytest.raises(PlaywrightError):
        goto_local_route(deterministic, "http://127.0.0.1:9000/broken")
    assert deterministic.calls == 1 and deterministic.waits == []


def node_json(source: str) -> dict:
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", source],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_diagram_adapter_accepts_every_supported_edge_shape() -> None:
    result = node_json(
        r"""
import {diagramFromEntry,renderDiagramSvg} from './company_ui/products/visualizer/assets/authoring_diagram_studio.mjs';
const variants=[
  [['A','B']],
  [{from:'A',to:'B',label:'handoff'}],
  [{source:'A',target:'B',labels:['verified']}],
  [{source:0,target:1,label:'indexed'}],
];
const rendered=variants.map(edges=>{const model=diagramFromEntry({engine:'DiagramEngine',element:'Process Flow',nodes:['A','B'],edges,direction:'down'});return {nodes:model.nodes.length,edges:model.edges.length,svg:renderDiagramSvg(model)};});
const canonical=diagramFromEntry({diagram:{nodes:[{id:'a',label:'Start',x:10,y:10},{id:'b',label:'End',x:260,y:10}],edges:[{id:'e',source:'a',target:'b',labels:[{id:'l',text:'release',position:'center'}]}]}});
console.log(JSON.stringify({rendered,canonical:renderDiagramSvg(canonical)}));
"""
    )
    assert all(row["nodes"] == 2 and row["edges"] == 1 for row in result["rendered"])
    assert all("Diagram data needs review" not in row["svg"] for row in result["rendered"])
    assert "handoff" in result["rendered"][1]["svg"]
    assert "verified" in result["rendered"][2]["svg"]
    assert "indexed" in result["rendered"][3]["svg"]
    assert "release" in result["canonical"]


def test_chart_adapter_hydrates_legacy_line_wafer_and_engineering() -> None:
    result = node_json(
        r"""
import {chartModelFromEntry,chartToEntry,renderChartSvg,chartSummary} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
const line=chartModelFromEntry({engine:'CoreChartEngine',element:'Line Chart',data:[['A',0],['B','0'],['C',2]]});
const wafer=chartModelFromEntry({engine:'WaferFabEngine',element:'Wafer Map',observations:[{x:0,y:0,value:91,lot:'L1',tool:'ETCH-1'},{x:1,y:0,value:95,lot:'L1',tool:'ETCH-1'}]});
const engineering=chartModelFromEntry({engine:'EngineeringChartEngine',element:'SPC Control Chart',observations:[{label:'1',value:10},{label:'2',value:11}]});
const saved=chartToEntry({id:'w'},wafer),reopened=chartModelFromEntry(saved);
console.log(JSON.stringify({
  line:{rows:line.dataset.rows,mapping:line.mapping,summary:chartSummary(line),marks:(renderChartSvg(line).match(/data-chart-point/g)||[]).length},
  wafer:{rows:wafer.dataset.rows.length,mapping:wafer.mapping,marks:(renderChartSvg(wafer).match(/data-wafer-die/g)||[]).length,svg:renderChartSvg(wafer)},
  engineering:{rows:engineering.dataset.rows.length,marks:(renderChartSvg(engineering).match(/data-chart-point/g)||[]).length},
  reopened:{rows:reopened.dataset.rows.length,marks:(renderChartSvg(reopened).match(/data-wafer-die/g)||[]).length},
}));
"""
    )
    assert result["line"]["rows"][0][1] == 0
    assert result["line"]["rows"][1][1] == "0"
    assert result["line"]["mapping"]["x"] and result["line"]["mapping"]["y"]
    assert "unmapped" not in result["line"]["summary"].lower()
    assert result["line"]["marks"] == 2  # string "0" is preserved but does not drive geometry
    assert result["wafer"]["rows"] == result["wafer"]["marks"] == 2
    assert "91 → 95" in result["wafer"]["svg"]
    assert result["engineering"]["rows"] == result["engineering"]["marks"] == 2
    assert result["reopened"]["rows"] == result["reopened"]["marks"] == 2


def test_final_visual_verifier_fixtures_match_each_waferfab_renderer_contract() -> None:
    elements = [
        "Wafer Map",
        "Wafer Difference Map",
        "Tool × Chamber Matrix",
        "Golden vs Affected Profile",
        "Control vs Affected Distribution",
    ]
    entries = [fixture("WaferFabEngine", element, index) for index, element in enumerate(elements, 1)]
    source = f"""
import {{chartModelFromEntry,renderChartSvg}} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
const entries={json.dumps(entries, ensure_ascii=False)};
const rendered=entries.map(entry=>{{
  const model=chartModelFromEntry(entry),svg=renderChartSvg(model,{{width:680,height:330}});
  return {{element:entry.element,rows:model.dataset.rows.length,mapping:model.mapping,svg,
    waferDies:(svg.match(/data-wafer-die=/g)||[]).length,
    chartPoints:(svg.match(/data-chart-point=/g)||[]).length}};
}});
console.log(JSON.stringify(rendered));
"""
    rendered = node_json(source)
    by_element = {item["element"]: item for item in rendered}
    assert by_element["Wafer Map"]["rows"] == by_element["Wafer Map"]["waferDies"] == 4
    assert by_element["Wafer Difference Map"]["rows"] == by_element["Wafer Difference Map"]["waferDies"] == 3
    assert by_element["Wafer Difference Map"]["mapping"]["value"] == "__delta"
    assert by_element["Tool × Chamber Matrix"]["rows"] == 4
    assert by_element["Tool × Chamber Matrix"]["chartPoints"] == 4
    assert "ETCH-01 · A · mean measurement 12" in by_element["Tool × Chamber Matrix"]["svg"]
    assert "cs-fab-profile" in by_element["Golden vs Affected Profile"]["svg"]
    assert all(token in by_element["Golden vs Affected Profile"]["svg"] for token in ("10", "15", "9"))
    assert all(token in by_element["Control vs Affected Distribution"]["svg"] for token in ("Control", "Affected", "n=2"))


def test_final_visual_verifier_keeps_old_probe_evidence_and_element_contracts() -> None:
    source = (ROOT / "scripts/release_checks/run_final_visual_remediation_acceptance.py").read_text(encoding="utf-8")
    benchmark = (ROOT / "scripts/release_checks/run_stage_d_benchmark.py").read_text(encoding="utf-8")
    assert set(WAFERFAB_RENDERER_CONTRACTS) == {
        "Wafer Map",
        "Wafer Difference Map",
        "Tool × Chamber Matrix",
        "Golden vs Affected Profile",
        "Control vs Affected Distribution",
    }
    contracts_source = (ROOT / "scripts/release_checks/waferfab_visual_contracts.py").read_text(encoding="utf-8")
    assert LEGACY_WAFERFAB_SELECTOR in contracts_source
    assert "WAFERFAB_RENDERER_CONTRACTS" in source
    assert "WAFERFAB_RENDERER_CONTRACTS" in benchmark
    assert "legacy_assumption_marks" in source
    assert "value['renderer_contract'] is None or value['marks']<1" in source


def test_layout_selection_and_tablet_contracts_are_explicit() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    composition = (ASSETS / "authoring_composition.mjs").read_text(encoding="utf-8")
    css = (ASSETS / "integrated_editor.css").read_text(encoding="utf-8")
    diagram_html = (ASSETS / "diagram_studio.html").read_text(encoding="utf-8")
    diagram_js = (ASSETS / "diagram_studio.mjs").read_text(encoding="utf-8")
    assert "const fitToHull=" in editor and "function semanticSmartLayout(items=viewItems())" in editor
    assert "function allocateRowWidths(row, innerW, gap, ratios = null)" in editor
    assert "sectionCompositionPlan(ordered,preset,CANVAS.w,profiles)" in editor
    assert "const spacing=compositionSpacing({density:model().density||direction.density.spacing,itemCount:ordered.length,direction:direction.id})" in editor
    assert "let y=g;" in editor and "sectionHeadingOrder" in editor
    assert "compositionOrder(items,model().layoutPreset||'editorial',direction)" in editor
    assert "COMPOSITION_ROLES" in composition and "ROLE_SECTIONS" in composition
    assert "innerW=Math.max(1,CANVAS.w-2*g)" in editor
    assert "editor-chrome-layer" in editor and "renderEditorChrome(rm)" in editor
    assert "--viz-layer-editor-chrome" in css and "pointer-events:none" in css
    assert "data-responsive-priority=\"secondary\"" in editor or "data-responsive-priority=\"secondary\"" in (ASSETS / "integrated_editor.html").read_text(encoding="utf-8")
    assert "toolbar .tb:nth-of-type(n+7)" not in css
    assert "max-height:none" in css and "90cqw" in css
    assert "toggle-palette" in diagram_html and "toggle-inspector" in diagram_html
    assert "fitViewport('fit-page',false)" in diagram_js and "viewportTouched" in diagram_js


def test_report_thumbnails_and_history_are_semantic() -> None:
    chart={"items":[{"id":"c","engine":"CoreChartEngine","element":"Line Chart","data":[["A",1],["B",3]]}]}
    wafer={"items":[{"id":"w","engine":"WaferFabEngine","element":"Wafer Map","observations":[{"x":0,"y":0,"value":1}]}]}
    diagram={"items":[{"id":"d","engine":"DiagramEngine","element":"Process Flow","nodes":["A","B"],"edges":[["A","B"]]}]}
    text={"items":[{"id":"t","engine":"TextEngine","element":"Hero Title","text":"Result"}]}
    previews=[_report_thumbnail_markup(model) for model in (chart,wafer,diagram,text)]
    assert all("cui-report-thumb-svg" in preview for preview in previews)
    assert len(set(previews)) == 4
    assert 'data-preview-family="chart"' in previews[0]
    assert 'data-preview-family="wafer"' in previews[1]
    assert 'data-preview-family="diagram"' in previews[2]
    assert 'data-preview-family="text"' in previews[3]
    before={"items":[{"id":"c","title":"Old","x":10,"y":10,"mapping":{"x":"a"},"chart_studio":{"axes":{}}}]}
    after={"items":[{"id":"c","title":"New","x":50,"y":10,"mapping":{"x":"b"},"chart_studio":{"axes":{"x":{"title":"Time"}}}}]}
    summary=_history_diff_summary(before,after)
    assert all(label in summary for label in ("content/text","geometry","mapping","chart config"))


def test_checkpoint_requires_name_and_frozen_connector_is_unchanged(tmp_path: Path) -> None:
    repository=ReportRepository(tmp_path)
    record=repository.create("report",title="Report",model={"items":[],"groups":{},"datasets":[],"mode":"smart","layoutPreset":"editorial","canvas":{"width":1200,"height":900},"nextId":1})
    try:
        repository.checkpoint(record.report_id,"",expected_revision=record.revision)
    except Exception as error:
        assert "checkpoint name is required" in str(error)
    else:
        raise AssertionError("empty checkpoint was accepted")
    saved=repository.checkpoint(record.report_id,"Review ready",expected_revision=record.revision)
    assert saved["checkpoint"] is True and saved["label"] == "Review ready"
    assert hashlib.sha256(FROZEN.read_bytes()).hexdigest() == "d8ebd4378f01b7c52a7a4be57c578c22adf29b899cc08a370cf084881195343e"
