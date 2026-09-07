from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from company_ui.products.visualizer.page import _history_diff_summary, _report_thumbnail_markup
from company_ui.products.visualizer.repository import ReportRepository


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "company_ui/products/visualizer/assets"
FROZEN = ROOT / "company_ui/products/visualizer/vendor/production_core/core/GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js"


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


def test_layout_selection_and_tablet_contracts_are_explicit() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    css = (ASSETS / "integrated_editor.css").read_text(encoding="utf-8")
    diagram_html = (ASSETS / "diagram_studio.html").read_text(encoding="utf-8")
    diagram_js = (ASSETS / "diagram_studio.mjs").read_text(encoding="utf-8")
    assert "soloSize" in editor and "growthScore" in editor and "let y=g" in editor
    assert "position:fixed;z-index:190" in css and "scored.x}px" in editor
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
