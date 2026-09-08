"""Focused Stage D product-layer contracts."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def node_json(source: str) -> dict:
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", source],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return json.loads(result.stdout)


def test_stage_d_content_first_intake_is_deterministic() -> None:
    observed = node_json(
        r'''
import {contentIntakePlan} from './company_ui/products/visualizer/assets/authoring_stage_d.mjs';
const text=contentIntakePlan('Pressure excursion investigation\nThe chamber trend moved outside the expected band.');
const data=contentIntakePlan('source\ttarget\tlabel\nDetect\tAnalyze\tstep\nAnalyze\tVerify\tstep');
const wafer=contentIntakePlan('X_COORD\tY_COORD\tMEASUREMENT\tLOT\n0\t1\t98.2\tL1\n1\t1\t99.1\tL1');
const image=contentIntakePlan('',{imageMime:'image/png'});
console.log(JSON.stringify({
  text:[text.kind,text.defaultRole,text.recommendations.map(x=>x.element)],
  diagram:[data.kind,data.recommendations[0].element],
  wafer:[wafer.kind,wafer.recommendations[0].element],
  image:[image.kind,image.recommendations.length,image.requires],
}));
'''
    )
    assert observed == {
        "text": ["text", "Context", ["Body Narrative", "Executive Statement", "Key Takeaway"]],
        "diagram": ["table", "Data Flow"],
        "wafer": ["table", "Wafer Map"],
        "image": ["image", 3, ["alt text"]],
    }


def test_stage_d_roles_layout_and_free_mode_contract() -> None:
    observed = node_json(
        r'''
import {applyMessageRole,layoutOperations,withSuggestedRoles,contentFitSummary,revisionDiff} from './company_ui/products/visualizer/assets/authoring_stage_d.mjs';
const base={mode:'smart',canvas:{width:1200,height:900},items:[
 {id:'a',element:'Hero KPI',engine:'MetricEngine',type:'metric',order:0,w:260,h:140,locked:false},
 {id:'b',element:'Line Chart',engine:'CoreChartEngine',type:'chart',order:1,w:420,h:240,locked:false},
 {id:'c',element:'Risk Callout',engine:'DecisionCompositeEngine',type:'decision',order:2,w:260,h:150,locked:true,x:800,y:400},
]};
const roles=withSuggestedRoles(base);const ops=layoutOperations(roles,{action:'clean'});const free=layoutOperations({...roles,mode:'free'},{action:'clean'});const roleOps=applyMessageRole(roles,['b'],'Primary Evidence');const diff=revisionDiff(base,{...base,items:[...base.items,{id:'d'}]});
console.log(JSON.stringify({roles:roles.items.map(x=>x.message_role),ops:ops.map(x=>[x.id,x.patch.x,x.patch.y]),free:free.length,role:roleOps.ops[0].patch.message_role,diff:diff.added,fit:contentFitSummary(roles).items.length}));
'''
    )
    assert observed["roles"] == ["Headline", "Primary Evidence", "Risk"]
    assert observed["free"] == 0
    assert observed["role"] == "Primary Evidence"
    assert observed["diff"] == ["d"]
    assert observed["fit"] == 3
    assert len(observed["ops"]) == 2


def test_stage_d_delivery_findings_and_command_catalog() -> None:
    observed = node_json(
        r'''
import {deliveryFindings,STAGE_D_COMMANDS,BLUEPRINTS,createReusableAsset,assetCompatibility} from './company_ui/products/visualizer/assets/authoring_stage_d.mjs';
const model={items:[{id:'chart',element:'Line Chart',engine:'CoreChartEngine',series:[{id:'a'},{id:'b'}],legend:{show:false}},{id:'image',element:'Image',engine:'ImageMediaEngine',alt:''}]};
const findings=deliveryFindings(model);const asset=createReusableAsset({name:'Trend',type:'chart recipe',payload:{chart_type:'Line Chart'},compatibility:{schema_signature:'a|b'}});
console.log(JSON.stringify({findings:findings.map(x=>x.id),commands:STAGE_D_COMMANDS.length,blueprints:BLUEPRINTS.length,compat:assetCompatibility(asset,{schema_signature:'other'}).kind,name:asset.name}));
'''
    )
    assert observed["findings"] == ["missing-headline", "axis-title", "missing-legend", "missing-alt"]
    assert observed["commands"] >= 16
    assert observed["blueprints"] >= 6
    assert observed["compat"] == "incompatible"
    assert observed["name"] == "Trend"
