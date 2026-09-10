from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def node_json(source: str):
    result = subprocess.run(
        ["node", "--input-type=module", "-e", source],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


def test_xbar_r_constants_and_independent_reference_fixtures_are_exact():
    payload = node_json(
        r'''
import {XR_CONSTANTS, xbarR} from './company_ui/products/visualizer/vendor/production_core/core/statistics_engine.mjs';
const fixtures={
  2:[[1,3],[2,6],[4,5]],
  5:[[1,2,4,7,9],[2,3,5,8,10]],
  10:[[1,2,3,4,5,6,7,8,9,11],[2,3,4,5,6,7,8,9,10,12]],
};
const output=Object.fromEntries(Object.entries(fixtures).map(([n,groups])=>{const result=xbarR(groups);return [n,{constants:result.constants,means:result.means,ranges:result.ranges,xbarbar:result.xbarbar,rbar:result.rbar,sigma:result.sigma,xbarLimits:result.xbarLimits,rLimits:result.rLimits}]}));
console.log(JSON.stringify({constants:{2:XR_CONSTANTS[2],5:XR_CONSTANTS[5],10:XR_CONSTANTS[10]},output}));
'''
    )
    assert payload["constants"] == {
        "2": {"A2": 1.88, "D3": 0, "D4": 3.267, "d2": 1.128},
        "5": {"A2": 0.577, "D3": 0, "D4": 2.114, "d2": 2.326},
        "10": {"A2": 0.308, "D3": 0.223, "D4": 1.777, "d2": 3.078},
    }
    assert payload["output"]["2"]["means"] == [2, 4, 4.5]
    assert payload["output"]["2"]["ranges"] == [2, 4, 1]
    assert payload["output"]["2"]["xbarbar"] == pytest.approx(3.5)
    assert payload["output"]["2"]["rbar"] == pytest.approx(7 / 3)
    assert payload["output"]["2"]["xbarLimits"] == {
        "center": pytest.approx(3.5),
        "lcl": pytest.approx(3.5 - 1.88 * (7 / 3)),
        "ucl": pytest.approx(3.5 + 1.88 * (7 / 3)),
    }
    assert payload["output"]["5"]["means"] == [4.6, 5.6]
    assert payload["output"]["5"]["ranges"] == [8, 8]
    assert payload["output"]["5"]["xbarbar"] == pytest.approx(5.1)
    assert payload["output"]["5"]["rbar"] == pytest.approx(8)
    assert payload["output"]["10"]["means"] == [5.6, 6.6]
    assert payload["output"]["10"]["ranges"] == [10, 10]
    assert payload["output"]["10"]["xbarbar"] == pytest.approx(6.1)
    assert payload["output"]["10"]["rbar"] == pytest.approx(10)


def test_xbar_r_fails_closed_for_invalid_statistical_structure():
    payload = node_json(
        r'''
import {xbarR} from './company_ui/products/visualizer/vendor/production_core/core/statistics_engine.mjs';
const cases={
  fewer: [[1,2]],
  size_one: [[1],[2]],
  mixed: [[1,2],[3,4,5]],
  unsupported: [Array.from({length:11},(_,i)=>i),Array.from({length:11},(_,i)=>i+1)],
  nonfinite: [[1,2],[3,Number.NaN]],
  zero_range: [[2,2],[2,2]],
};
const output=Object.fromEntries(Object.entries(cases).map(([name,groups])=>{try{xbarR(groups);return [name,null]}catch(error){return [name,{code:error.code,message:error.message}]}}));
console.log(JSON.stringify(output));
'''
    )
    assert payload["fewer"]["code"] == "SUBGROUPS"
    assert "at least two subgroups" in payload["fewer"]["message"]
    assert payload["size_one"]["code"] == "SUBGROUP_SIZE"
    assert payload["mixed"]["code"] == "SUBGROUP_SIZE"
    assert payload["unsupported"]["code"] == "SUBGROUP_SIZE"
    assert payload["nonfinite"]["code"] == "NON_FINITE"
    assert payload["zero_range"]["code"] == "SPC_SIGMA"
    assert "average range is zero" in payload["zero_range"]["message"]


def test_process_capability_metrics_and_edge_contract_are_authoritative():
    payload = node_json(
        r'''
import {processCapability} from './company_ui/products/visualizer/vendor/production_core/core/statistics_engine.mjs';
const values=[9.8,10,10.2,10.1,9.9];
const full=processCapability(values,{lsl:9.5,usl:10.5,target:10});
const low=processCapability(values,{lsl:9.5});
const high=processCapability(values,{usl:10.5});
const cases={
  invalid_order:()=>processCapability(values,{lsl:10.5,usl:9.5}),
  no_specs:()=>processCapability(values,{}),
  zero_variation:()=>processCapability([10,10],{lsl:9,usl:11}),
  invalid_target:()=>processCapability(values,{lsl:9.5,usl:10.5,target:Number.NaN}),
};
const errors={};for(const [name,run] of Object.entries(cases)){try{run()}catch(error){errors[name]={code:error.code,message:error.message}}}
console.log(JSON.stringify({full,low,high,errors}));
'''
    )
    assert payload["full"]["n"] == 5
    assert payload["full"]["mean"] == pytest.approx(10)
    assert payload["full"]["sigma"] == pytest.approx(math.sqrt(0.025))
    assert payload["full"]["sigmaEstimator"] == "sample_standard_deviation"
    assert payload["full"]["cp"] == pytest.approx(1 / (6 * math.sqrt(0.025)))
    assert payload["full"]["cpu"] == pytest.approx(payload["full"]["cp"])
    assert payload["full"]["cpl"] == pytest.approx(payload["full"]["cp"])
    assert payload["full"]["cpk"] == pytest.approx(payload["full"]["cp"])
    assert payload["low"]["cp"] is None and payload["low"]["cpl"] == pytest.approx(payload["full"]["cp"])
    assert payload["high"]["cp"] is None and payload["high"]["cpu"] == pytest.approx(payload["full"]["cp"])
    assert payload["errors"]["invalid_order"]["code"] == "SPEC_LIMITS"
    assert payload["errors"]["no_specs"]["code"] == "SPEC_LIMITS"
    assert payload["errors"]["zero_variation"]["code"] == "SPC_SIGMA"
    assert payload["errors"]["invalid_target"]["code"] == "SPEC_LIMITS"


def test_statistical_recipe_semantics_preserve_values_mappings_and_provenance():
    payload = node_json(
        r'''
import {executeRecipeSemantics, recipeRoleContract, semanticDatasetForEntry} from './company_ui/products/visualizer/assets/analysis_semantics.mjs';
import {recommendEngineeringRecipes, recipeExecutionPlan} from './company_ui/products/visualizer/assets/engineering_recipes.mjs';
const n=(id,name,tags=[])=>({id,name,type:'number',semantic_tags:tags});
const c=(id,name,tags=[])=>({id,name,type:'categorical',semantic_tags:tags});
const xr={id:'xr',revision:3,fields:[c('group','Subgroup',['subgroup']),n('order','Order',['time']),n('m','Measurement',['value'])],rows:[['G2',2,10],['G1',1,8],['G2',2,14],['G1',1,12],['G3',3,11],['G3',3,17]]};
const cap={id:'cap',revision:2,fields:[n('m','Measurement',['value']),n('low','LSL',['specification_low']),n('high','USL',['specification_high'])],rows:[[9.8,9.5,10.5],[10,9.5,10.5],[10.2,9.5,10.5],[10.1,9.5,10.5],[9.9,9.5,10.5]]};
const capWithTarget={...cap,fields:[...cap.fields,n('target','Target',['target'])],rows:cap.rows.map(row=>[...row,10])};
const doe={id:'doe',revision:1,fields:[c('a','Factor A',['factor_a']),c('b','Factor B',['factor_b']),n('y','Response',['response'])],rows:[['A','L',10],['A','L',12],['A','H',14],['A','H',16],['B','L',20],['B','L',22],['B','H',28],['B','H',30]]};
const x=executeRecipeSemantics('xbar-r-process-review',xr,{subgroup:'group',order:'order',value:'m'});
const ca=executeRecipeSemantics('process-capability',cap,{value:'m',specification_low:'low',specification_high:'high'},{target:10});
const mappedTarget=executeRecipeSemantics('process-capability',capWithTarget,{value:'m',specification_low:'low',specification_high:'high',target:'target'});
const explicit=executeRecipeSemantics('process-capability',{...cap,rows:cap.rows.map(row=>[row[0]])},{value:'m'},{lsl:9.5,usl:10.5,target:10});
const d=executeRecipeSemantics('doe-response-review',doe,{factor_a:'a',factor_b:'b',response:'y'});
const conflict=executeRecipeSemantics('process-capability',{...cap,rows:cap.rows.map((row,index)=>index===2?[row[0],9.7,row[2]]:row)},{value:'m',specification_low:'low',specification_high:'high'});
const entry={analysis_recipe:{id:'xbar-r-process-review',version:'statistical-v1',mapping:{subgroup:'group',order:'order',value:'m'}}};
const refreshed=semanticDatasetForEntry(entry,{...xr,revision:4,rows:xr.rows.map((row,index)=>index===4?[row[0],row[1],20]:row)});
const recFields=[...xr.fields,...cap.fields,...doe.fields];
const invalidXbarRows=[['G1',1],['G1',2],['G2',3]];
console.log(JSON.stringify({x:{ok:x.ok,means:x.primary?.stats.means,ranges:x.primary?.stats.ranges,labels:x.primary?.subgroup_labels,revision:x.dataset?.metadata.semantic_version,provenance:x.provenance,metadata:x.dataset?.metadata.analysis_provenance},cap:{ok:ca.ok,stats:ca.primary?.stats,fields:ca.dataset?.fields.map(field=>field.id),provenance:ca.provenance},mappedTarget:{ok:mappedTarget.ok,target:mappedTarget.primary?.stats.target,targetSource:mappedTarget.summary?.specification_sources?.target},explicit:{ok:explicit.ok,cpk:explicit.primary?.stats.cpk},doe:{ok:d.ok,effects:d.primary?.effects,interaction:d.primary?.interaction,provenance:d.provenance},conflict:{ok:conflict.ok,code:conflict.errors?.[0]?.code},refresh:{ok:refreshed?.ok,means:refreshed?.primary?.stats.means,revision:refreshed?.dataset?.revision},contracts:{xr:recipeRoleContract('xbar-r-process-review'),cap:recipeRoleContract('process-capability'),doe:recipeRoleContract('doe-response-review')},plans:{xr:recipeExecutionPlan('xbar-r-process-review',xr.fields).visuals.map(item=>item.element),cap:recipeExecutionPlan('process-capability',cap.fields).valid,doe:recipeExecutionPlan('doe-response-review',doe.fields).visuals.map(item=>item.element)},recommendations:recommendEngineeringRecipes([...xr.fields,...cap.fields,...doe.fields]).map(item=>item.id),invalidRecommendations:recommendEngineeringRecipes([{id:'g',name:'Subgroup',type:'categorical',semantic_tags:['subgroup']},{id:'m',name:'Measurement',type:'number',semantic_tags:['value']}],invalidXbarRows).map(item=>item.id)}));
'''
    )
    assert payload["x"]["ok"] is True
    assert payload["x"]["means"] == [10, 12, 14]
    assert payload["x"]["ranges"] == [4, 4, 6]
    assert payload["x"]["labels"] == ["G1", "G2", "G3"]
    assert payload["x"]["revision"] == "statistical-v1"
    assert "X̄/R" in payload["x"]["provenance"]
    assert payload["x"]["metadata"] == payload["x"]["provenance"]
    assert payload["cap"]["ok"] is True
    assert payload["cap"]["stats"]["target"] == 10
    assert payload["cap"]["stats"]["sigmaEstimator"] == "sample_standard_deviation"
    assert payload["cap"]["fields"][-1] == "__cpk"
    assert "sample standard deviation" in payload["cap"]["provenance"]
    assert payload["mappedTarget"] == {"ok": True, "target": 10, "targetSource": "dataset-column"}
    assert payload["explicit"]["ok"] is True
    assert payload["explicit"]["cpk"] == pytest.approx(1.0540925533894636)
    effects = {effect["factor"]: {level["level"]: level["mean"] for level in effect["levels"]} for effect in payload["doe"]["effects"]}
    assert effects["factor_a"] == {"A": 13, "B": 25}
    assert effects["factor_b"] == {"H": 22, "L": 16}
    assert payload["doe"]["interaction"]["interactionEffect"] == pytest.approx(-2)
    assert "descriptive" in payload["doe"]["provenance"]
    assert payload["conflict"] == {"ok": False, "code": "CONFLICTING_SPECIFICATION"}
    assert payload["refresh"] == {"ok": True, "means": [10, 12, 18.5], "revision": 4}
    assert payload["contracts"]["xr"]["required_roles"] == ["subgroup", "value"]
    assert payload["contracts"]["cap"]["required_roles"] == ["specification_high", "specification_low", "value"]
    assert payload["contracts"]["doe"]["required_roles"] == ["factor_a", "factor_b", "response"]
    assert payload["plans"]["xr"] == ["Xbar-R Chart", "Clean Table", "Hero KPI"]
    assert payload["plans"]["cap"] is True
    assert payload["plans"]["doe"] == ["DOE Main Effects", "DOE Interaction Plot", "Clean Table"]
    assert {"xbar-r-process-review", "process-capability", "doe-response-review"}.issubset(payload["recommendations"])
    assert "xbar-r-process-review" not in payload["invalidRecommendations"]


def test_statistical_visuals_are_data_backed_and_export_safe():
    payload = node_json(
        r'''
import {chartModelFromEntry, renderChartSvg} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
const field=(id,name,type,tags=[])=>({id,name,type,semantic_tags:tags});
const xrDataset={id:'xr',revision:1,fields:[field('s','Subgroup','categorical',['subgroup']),field('m','Mean','number',['value'])],rows:[['G1',10],['G2',12],['G3',14]]};
const xrStats={n:2,means:[10,12,14],ranges:[2,4,6],xbarLimits:{center:12,lcl:3.2266666667,ucl:20.7733333333},rLimits:{center:4,lcl:0,ucl:8.456},rules:{signals:[]}};
const xrSvg=renderChartSvg(chartModelFromEntry({engine:'EngineeringChartEngine',element:'Xbar-R Chart',mapping:{subgroup:'s',value:'m'},statistical_result:xrStats},xrDataset),{width:760,height:520});
const doeDataset={id:'doe',revision:1,fields:[field('a','Factor A','categorical',['factor_a']),field('b','Factor B','categorical',['factor_b']),field('y','Response','number',['response'])],rows:[['A','L',10],['A','H',14],['B','L',20],['B','H',28]]};
const effects=[{factor:'factor_a',levels:[{level:'A',n:2,mean:12},{level:'B',n:2,mean:24}]},{factor:'factor_b',levels:[{level:'H',n:2,mean:21},{level:'L',n:2,mean:15}]}];
const interaction={factorA:'factor_a',factorB:'factor_b',levelsA:['A','B'],levelsB:['H','L'],cells:[[{mean:14,n:1},{mean:10,n:1}],[{mean:28,n:1},{mean:20,n:1}]],interactionEffect:-1};
const mainSvg=renderChartSvg(chartModelFromEntry({engine:'EngineeringChartEngine',element:'DOE Main Effects',mapping:{factor_a:'a',factor_b:'b',response:'y'},statistical_result:{effects}},doeDataset));
const interactionSvg=renderChartSvg(chartModelFromEntry({engine:'EngineeringChartEngine',element:'DOE Interaction Plot',mapping:{factor_a:'a',factor_b:'b',response:'y'},statistical_result:{interaction}},doeDataset));
const capDataset={id:'cap',revision:1,fields:[field('m','Measurement','number',['value'])],rows:[[9.8],[10],[10.2],[10.1],[9.9]]};
const capSvg=renderChartSvg(chartModelFromEntry({engine:'CoreChartEngine',element:'Histogram',analysis_recipe:{id:'process-capability'},mapping:{value:'m'},specification_low:9.5,specification_high:10.5,target:10},capDataset));
console.log(JSON.stringify({xr:xrSvg,main:mainSvg,interaction:interactionSvg,cap:capSvg}));
'''
    )
    for key in ("xr", "main", "interaction", "cap"):
        assert payload[key].startswith("<svg")
        assert "NaN" not in payload[key]
        assert "Infinity" not in payload[key]
    assert all(token in payload["xr"] for token in ("X̄", "R", "UCL", "Center", "LCL", "statistical"))
    assert "descriptive means" in payload["main"]
    assert "descriptive interaction" in payload["interaction"]
    assert all(token in payload["cap"] for token in ("LSL", "USL", "Target", "Specification markers are requirements"))


def test_statistical_recommendations_and_public_registry_are_coherent():
    payload = node_json(
        r'''
import {recommendEngineeringRecipes} from './company_ui/products/visualizer/assets/engineering_recipes.mjs';
import {PRODUCTION_LIBRARY_COUNT,isProductionElement} from './company_ui/products/visualizer/assets/production_library.mjs';
const fields=[
  {id:'subgroup',name:'Subgroup ID',type:'categorical',semantic_tags:['subgroup']},
  {id:'measurement',name:'Measurement',type:'number',semantic_tags:['value']},
  {id:'lsl',name:'LSL',type:'number',semantic_tags:['specification_low']},
  {id:'usl',name:'USL',type:'number',semantic_tags:['specification_high']},
  {id:'factor_a',name:'Factor A',type:'categorical',semantic_tags:['factor_a']},
  {id:'factor_b',name:'Factor B',type:'categorical',semantic_tags:['factor_b']},
  {id:'response',name:'Response',type:'number',semantic_tags:['response']},
];
const recipes=recommendEngineeringRecipes(fields).map(item=>({id:item.id,reason:item.reason,targets:item.visuals.map(visual=>visual.element)}));
console.log(JSON.stringify({count:PRODUCTION_LIBRARY_COUNT,recipes,production:[['EngineeringChartEngine','Xbar-R Chart'],['EngineeringChartEngine','DOE Main Effects'],['EngineeringChartEngine','DOE Interaction Plot']].map(([engine,element])=>isProductionElement(engine,element))}));
'''
    )
    assert payload["count"] == 52
    ids = {item["id"] for item in payload["recipes"]}
    assert {"xbar-r-process-review", "process-capability", "doe-response-review"}.issubset(ids)
    assert all(item["reason"] for item in payload["recipes"])
    assert payload["production"] == [True, True, True]
