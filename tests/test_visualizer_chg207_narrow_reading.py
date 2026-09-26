from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


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


def test_metric_and_comparison_values_use_atomic_formatted_tokens() -> None:
    result = node_json(
        r'''
import {renderIntegratedElement} from './company_ui/products/visualizer/assets/element_renderer.mjs';
const metric=(id,value,unit,metric_format)=>renderIntegratedElement({id,engine:'MetricEngine',element:'Hero KPI',title:id,showTitle:true,value,unit,metric_format});
const comparison=renderIntegratedElement({id:'comparison',engine:'ComparisonEngine',element:'Before/After KPI',title:'Capacity',showTitle:true,before:120000,after:142000,unit:'units'});
console.log(JSON.stringify({
  supplyBefore:comparison.includes('<span class="numeric-token">120000 <small class="comparison-unit">units</small></span>'),
  supplyAfter:comparison.includes('<span class="numeric-token">142000 <small class="comparison-unit">units</small></span>'),
  hasComparisonLabels:comparison.includes('Before')&&comparison.includes('After')&&comparison.includes('▲'),
  negativeCurrency:metric('negative',-1234567.8,'USD',{kind:'currency',prefix:'$',precision:2}),
  negativeUnit:metric('negative-unit',-1234567.8,'units',{kind:'number',precision:1}),
  percent:metric('percent',2.7,'%',{kind:'number',precision:1,suffix:'%'}),
  zeroPrecision:metric('zero',0,'',{kind:'number',precision:3}),
  compact:metric('compact',120000,'units',{kind:'number',precision:0}),
}));
'''
    )
    assert result["supplyBefore"] is True
    assert result["supplyAfter"] is True
    assert result["hasComparisonLabels"] is True
    assert '<span class="numeric-token">-$1,234,567.80</span>' in result["negativeCurrency"]
    assert '<span class="numeric-token">-1,234,567.8 units</span>' in result["negativeUnit"]
    assert '<span class="numeric-token">2.7%</span>' in result["percent"]
    assert '<span class="numeric-token">0.000</span>' in result["zeroPrecision"]
    assert '<span class="numeric-token">120,000 units</span>' in result["compact"]


def test_narrow_flow_is_a_reading_projection_of_the_canonical_graph() -> None:
    result = node_json(
        r'''
import {renderDiagramReadingSvg,normalizeDiagram} from './company_ui/products/visualizer/assets/authoring_diagram_studio.mjs';
const entry={id:'flow',engine:'DiagramEngine',element:'Process Flow',direction:'right',nodes:[
 {id:'demand',label:'Reconcile extremely long P70 demand forecast'},
 {id:'reserve',label:'Reserve qualified date-coded actuators'},
 {id:'confirm',label:'Confirm supplier allocation window'},
 {id:'release',label:'Release remaining production build'},
],edges:[
 {id:'e1',source:'demand',target:'reserve'},
 {id:'e2',source:'reserve',target:'confirm'},
 {id:'e3',source:'confirm',target:'release'},
]};
const original=JSON.stringify(entry),canonical=normalizeDiagram(entry),svg=renderDiagramReadingSvg(entry,{label:'Allocation path'}),compact=renderDiagramReadingSvg(entry,{label:'Allocation path',layout:'compact'});
console.log(JSON.stringify({
 unmutated:original===JSON.stringify(entry),canonicalDirection:canonical.layout.direction,
 readingDirection:svg.match(/data-reading-direction="([^"]+)/)?.[1],
 nodeIds:[...svg.matchAll(/data-diagram-node="([^"]+)"/g)].map(x=>x[1]),
 edgeIds:[...svg.matchAll(/data-diagram-edge="([^"]+)"/g)].map(x=>x[1]),
 edgeOrder:[...svg.matchAll(/data-edge-order="(\d+)"/g)].map(x=>Number(x[1])),
 sourceTarget:[...svg.matchAll(/data-source-id="([^"]+)" data-target-id="([^"]+)"/g)].map(x=>[x[1],x[2]]),
 labels:['Reconcile extremely long P70 demand forecast','Reserve qualified date-coded actuators','Confirm supplier allocation window','Release remaining production build'].every(x=>svg.includes(x)),
 wordWrap:svg.includes('<tspan x="160" dy="22">P70 demand forecast</tspan>'),
 accessible:svg.includes('role="img"')&&svg.includes('Step 4: Release remaining production build'),
 stacked:svg.includes('data-reading-layout="stacked"')&&svg.includes('data-canonical-direction="right"'),
 compactLayout:compact.includes('data-reading-layout="stacked" data-reading-columns="2"')&&compact.includes('data-reading-direction="serpentine"'),
 compactNodeIds:[...compact.matchAll(/data-diagram-node="([^"]+)"/g)].map(x=>x[1]),
 compactEdgeIds:[...compact.matchAll(/data-diagram-edge="([^"]+)"/g)].map(x=>x[1]),
 compactEdgeOrder:[...compact.matchAll(/data-edge-order="(\d+)"/g)].map(x=>Number(x[1])),
 compactSourceTarget:[...compact.matchAll(/data-source-id="([^"]+)" data-target-id="([^"]+)"/g)].map(x=>[x[1],x[2]]),
 compactAccessible:compact.includes('role="img"')&&compact.includes('Step 4: Release remaining production build'),
}));
'''
    )
    assert result["unmutated"] is True
    assert result["canonicalDirection"] == "right"
    assert result["readingDirection"] == "down"
    assert result["nodeIds"] == ["demand", "reserve", "confirm", "release"]
    assert result["edgeIds"] == ["e1", "e2", "e3"]
    assert result["edgeOrder"] == [0, 1, 2]
    assert result["sourceTarget"] == [["demand", "reserve"], ["reserve", "confirm"], ["confirm", "release"]]
    assert result["labels"] is True
    assert result["wordWrap"] is True
    assert result["accessible"] is True
    assert result["stacked"] is True
    assert result["compactLayout"] is True
    assert result["compactNodeIds"] == ["demand", "reserve", "confirm", "release"]
    assert result["compactEdgeIds"] == ["e1", "e2", "e3"]
    assert result["compactEdgeOrder"] == [0, 1, 2]
    assert result["compactSourceTarget"] == [["demand", "reserve"], ["reserve", "confirm"], ["confirm", "release"]]
    assert result["compactAccessible"] is True


def test_renderer_preserves_focusable_table_contract_and_preview_breakpoints() -> None:
    result = node_json(
        r'''
import {renderIntegratedElement} from './company_ui/products/visualizer/assets/element_renderer.mjs';
import {readFileSync} from 'node:fs';
const css=readFileSync('./company_ui/products/visualizer/assets/integrated_editor.css','utf8');
const wide=renderIntegratedElement({id:'wide',engine:'TableEngine',element:'Evidence Table',title:'Wide',customTable:{headers:['Supplier','Part','Lead time','Allocation','Risk'],rows:[['Northstar','A-1',116,'142000 units','Watch']]}});
const narrow=renderIntegratedElement({id:'narrow',engine:'TableEngine',element:'Evidence Table',title:'Narrow',customTable:{headers:['Supplier','Part'],rows:[['Northstar','A-1']]}});
console.log(JSON.stringify({
 focusable:/class="table-frame table-scroll" role="region" tabindex="0" aria-keyshortcuts="ArrowLeft ArrowRight Home End"/.test(wide),
 instructionStatus:/class="table-scroll-hint"[^>]*role="status" aria-live="polite" hidden/.test(wide),
 nativeOverflowInput:css.includes('.table-scroll-shell.has-overflow .table-frame.table-scroll { pointer-events:auto!important;touch-action:pan-x pan-y;'),
 sharedShell:wide.includes('table-scroll-shell')&&narrow.includes('table-scroll-shell'),
 atomicNoWrap:css.includes('.numeric-token { display:inline-block;max-width:100%;white-space:nowrap;'),
 responsiveFlow:css.includes('@media (max-width: 520px)')&&css.includes('.diagram-narrow-reading { display:block!important;'),
 mediumFlow:css.includes('.diagram-medium-reading .diagram-reading-label { fill:var(--viz-ink-soft);font-size:14px!important;')&&css.includes('.diagram-medium-reading { display:none!important;'),
 flowIntrinsicGrowth:css.includes('.component:has(.diagram-responsive-reading[data-reading-flow="true"]) .c-content { container-type:normal!important;'),
 mobileDocumentFlow:css.includes('@media(max-width:800px)')&&css.includes('.cui-visualizer-root.preview-mode { position:relative!important;inset:auto!important;height:auto!important;')&&css.includes('.cui-visualizer-workspace:has(.cui-visualizer-root.preview-mode)'),
 narrowComparison:css.includes('@media (max-width: 360px)')&&css.includes('.before-after-kpi { grid-template-columns:minmax(0,1fr);'),
 comparisonIntrinsicGrowth:css.includes('data-mobile-reader-fit="content"')&&css.includes('.component[data-mobile-reader-fit="content"] { height:auto!important;min-height:var(--viz-mobile-reader-height)!important;overflow:visible!important;')&&css.includes('.comparison>.compare-arrow { justify-self:center;transform:rotate(90deg);'),
}));
'''
    )
    assert result == {
        "focusable": True,
        "instructionStatus": True,
        "nativeOverflowInput": True,
        "sharedShell": True,
        "atomicNoWrap": True,
        "responsiveFlow": True,
        "mediumFlow": True,
        "flowIntrinsicGrowth": True,
        "mobileDocumentFlow": True,
        "narrowComparison": True,
        "comparisonIntrinsicGrowth": True,
    }
