from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.release_checks.run_chg293_process_flow_acceptance import run_acceptance

ROOT = Path(__file__).resolve().parents[1]
MODULE = "./company_ui/products/visualizer/assets/authoring_diagram_studio.mjs"
SOURCE = ROOT / "company_ui/products/visualizer/assets/authoring_diagram_studio.mjs"
CSS_SOURCE = ROOT / "company_ui/products/visualizer/assets/integrated_editor.css"


def node_json(source: str) -> dict:
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", source],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode:
        raise AssertionError(f"Node fixture failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def test_clearance_policy_adapts_layout_and_preserves_graph_identity() -> None:
    result = node_json(
        f'''
import {{diagramFromEntry,diagramToEntry,renderDiagramReadingSvg,renderDiagramSvg}} from {json.dumps(MODULE)};
const labels=['Map wafer cluster','Compare matched lot','Check CF-4 pressure','Confirm containment'];
const entry={{id:'unrelated-flow',engine:'DiagramEngine',element:'Process Flow',direction:'right',nodes:labels,edges:labels.slice(1).map((label,index)=>[labels[index],label]),diagram:{{
 schema:'visembler.diagram.studio',version:1,groups:[],swimlanes:[],layers:[{{id:'base',visible:true}}],layout:{{direction:'right'}},
 nodes:labels.map((label,index)=>({{id:`node-${{index+1}}`,shape:'process',label,secondary:index===1?'Matched reference evidence':''}})),
 edges:labels.slice(1).map((label,index)=>({{id:`edge-${{index+1}}`,source:`node-${{index+1}}`,target:`node-${{index+2}}`,labels:index===1?[{{id:'label-2',text:'CF-4 excursion verified',position:'center',offset:0}}]:[]}})),
}}}};
const before=JSON.stringify(entry),canonical=diagramFromEntry(entry),roundTrip=diagramFromEntry(diagramToEntry(entry,canonical));
const compactEntry=structuredClone(entry);compactEntry.diagram.edges.forEach(edge=>edge.labels=[]);
const compact=renderDiagramReadingSvg(compactEntry,{{layout:'compact'}}),annotated=renderDiagramReadingSvg(entry,{{layout:'compact'}}),narrow=renderDiagramReadingSvg(entry),wide=renderDiagramSvg(entry,{{className:'diagram-wide-reading'}});
const holdout=(count)=>{{const names=Array.from({{length:count}},(_,index)=>`Review chamber pressure step ${{index+1}}`),value={{engine:'DiagramEngine',element:'Process Flow',direction:'right',nodes:names,edges:names.slice(1).map((label,index)=>[names[index],label])}};return renderDiagramReadingSvg(value,{{layout:'compact'}});}};
const lowWidth=renderDiagramReadingSvg(entry,{{layout:'compact',availableWidth:220}});
const sourceGraph=(value)=>({{nodes:value.nodes.map(node=>[node.id,node.label,node.secondary]),edges:value.edges.map(edge=>[edge.id,edge.source,edge.target,edge.sourcePort,edge.targetPort,edge.labels.map(label=>[label.id,label.text,label.position,label.offset])]),direction:value.layout.direction}});
const field=(svg,name)=>Number(svg.match(new RegExp(`data-${{name}}="([^"]+)"`))?.[1]||0);
const ids=svg=>({{nodes:[...svg.matchAll(/data-diagram-node="([^"]+)"/g)].map(row=>row[1]),edges:[...svg.matchAll(/data-diagram-edge="([^"]+)"/g)].map(row=>row[1]),direct:[...svg.matchAll(/data-direct="([^"]+)"/g)].map(row=>row[1])}});
console.log(JSON.stringify({{
 unchanged:before===JSON.stringify(entry),identity:JSON.stringify(sourceGraph(canonical))===JSON.stringify(sourceGraph(roundTrip)),
 compact:{{columns:field(compact,'reading-columns'),clearance:field(compact,'reading-clearance-px'),padding:field(compact,'reading-protected-padding'),paddingY:field(compact,'reading-protected-padding-y'),marker:field(compact,'reading-marker-envelope'),markerForward:field(compact,'reading-marker-forward-envelope'),minimumScale:field(compact,'reading-minimum-scale'),lineHeight:field(compact,'reading-line-height'),direction:compact.match(/data-reading-direction="([^"]+)/)?.[1],ids:ids(compact),containsAccessibleSequence:labels.every(label=>compact.includes(label)),connectorTitles:compact.includes('Compare matched lot → Check CF-4 pressure')}},
 annotatedColumns:field(annotated,'reading-columns'),annotatedTitle:annotated.includes('CF-4 excursion verified'),
 narrow:{{columns:field(narrow,'reading-columns'),direction:narrow.match(/data-reading-direction="([^"]+)/)?.[1]}},
 wide:{{clearance:field(wide,'reading-clearance-px'),padding:field(wide,'reading-protected-padding'),marker:field(wide,'reading-marker-envelope'),minimumScale:field(wide,'reading-minimum-scale'),direct:ids(wide).direct}},
 fiveColumns:field(holdout(5),'reading-columns'),sixColumns:field(holdout(6),'reading-columns'),lowWidthColumns:field(lowWidth,'reading-columns'),
 antiSpecialCase:!/CHG-293|CHG-173|Map wafer cluster|Compare matched lot/.test({json.dumps(SOURCE.read_text(encoding='utf-8'))}),
}}));
'''
    )
    assert result["unchanged"] is True
    assert result["identity"] is True
    assert result["compact"]["columns"] == 2
    assert result["compact"]["clearance"] == 4
    assert result["compact"]["padding"] == 16
    assert result["compact"]["paddingY"] == 8
    assert result["compact"]["marker"] == 10.8
    assert result["compact"]["markerForward"] == 1.8
    assert result["compact"]["minimumScale"] == 0.95
    assert result["compact"]["lineHeight"] == 14
    assert ".diagram-medium-reading .diagram-reading-label { fill:var(--viz-ink-soft);font-size:14px!important;" in CSS_SOURCE.read_text(encoding="utf-8")
    assert result["compact"]["direction"] == "serpentine"
    assert result["compact"]["ids"]["nodes"] == ["node-1", "node-2", "node-3", "node-4"]
    assert result["compact"]["ids"]["edges"] == ["edge-1", "edge-2", "edge-3"]
    assert result["compact"]["ids"]["direct"] == [f"diagram-node:{index}" for index in range(4)]
    assert result["compact"]["containsAccessibleSequence"] is True
    assert result["compact"]["connectorTitles"] is True
    assert result["annotatedColumns"] == 1
    assert result["annotatedTitle"] is True
    assert result["narrow"] == {"columns": 1, "direction": "down"}
    assert result["wide"]["clearance"] == 4
    assert result["wide"]["padding"] >= 26
    assert result["wide"]["marker"] == 12
    assert result["wide"]["minimumScale"] == 0.25
    assert result["fiveColumns"] == 1
    assert result["sixColumns"] == 1
    assert result["lowWidthColumns"] == 1
    assert result["antiSpecialCase"] is True


def test_native_browser_measures_connectors_markers_and_breakpoint_holdouts(tmp_path: Path) -> None:
    receipt = run_acceptance(tmp_path / "chg293-browser")

    assert receipt["status"] == "PASS"
    matrix = receipt["cases"]["r6-like"]["geometry"]
    assert set(matrix) == {"1440", "520", "390", "361", "360", "320"}
    assert matrix["1440"]["projection"] == "wide"
    assert matrix["390"]["projection"] == "medium-2-column"
    assert matrix["361"]["projection"] == "medium-2-column"
    assert matrix["360"]["projection"] == "narrow"
    assert matrix["320"]["projection"] == "narrow"
    for width, geometry in matrix.items():
        assert all(edge["text_intersections"] == 0 for edge in geometry["connectors"]), (width, geometry)
        clearances = [value for edge in geometry["connectors"] for value in (edge["shaft_clearance_px"], edge["arrowhead_clearance_px"]) if value is not None]
        assert min(clearances) >= 4, (width, geometry)
    for name in ("four-stage-holdout", "five-stage-holdout", "six-stage-holdout", "edge-secondary-labels"):
        geometry = receipt["cases"][name]["geometry"]["390"]
        assert all(edge["text_intersections"] == 0 for edge in geometry["connectors"]), (name, geometry)
        assert min(value for edge in geometry["connectors"] for value in (edge["shaft_clearance_px"], edge["arrowhead_clearance_px"]) if value is not None) >= 4
    edge_case = receipt["cases"]["edge-secondary-labels"]["geometry"]["390"]
    assert edge_case["edgeLabels"]
    assert edge_case["edgeLabelToNodeTextClearancePx"] > 0
