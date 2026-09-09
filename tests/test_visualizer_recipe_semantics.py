from __future__ import annotations

import json
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


def test_recipe_semantics_are_value_level_and_adversarial():
    payload = node_json(
        r'''
import {executeRecipeSemantics, recipeRoleContract} from './company_ui/products/visualizer/assets/analysis_semantics.mjs';

const result=(recipe,fields,rows,mapping,options={})=>executeRecipeSemantics(recipe,{id:`${recipe}-source`,revision:4,fields,rows},mapping,options);
const numeric=(id,name,tag)=>({id,name,type:'number',semantic_tags:tag?[tag]:[]});
const categorical=(id,name,tag)=>({id,name,type:'categorical',semantic_tags:tag?[tag]:[]});
const text=(id,name,tag)=>({id,name,type:'string',semantic_tags:tag?[tag]:[]});

const pareto=result('yield-pareto',[categorical('cause','Cause','category'),numeric('loss','Loss','weight')],
  [['Particle',10],['Scratch',8],['Particle',7],['Void',5]],{category:'cause',value:'loss'});
const spc=result('spc-excursion',[text('time','Timestamp','time'),numeric('measure','Measurement','value')],
  [['2026-01-03',9],['2026-01-01',10],['2026-01-01',11],['2026-01-02',12]],{time:'time',value:'measure'});
const spcLimits=result('spc-excursion',[text('time','Timestamp','time'),numeric('measure','Measurement','value'),numeric('lsl','LSL'),numeric('usl','USL')],
  [['2026-01-02',11,8,14],['2026-01-01',10,8,14]],{time:'time',value:'measure',specification_low:'lsl',specification_high:'usl'});
const matrix=result('tool-chamber-matching',[categorical('tool','Tool','tool'),categorical('chamber','Chamber','chamber'),numeric('measure','Measurement','value')],
  [['ETCH-01','A',10],['ETCH-01','A',14],['ETCH-01','B',20],['ETCH-02','A',8]],{tool:'tool',chamber:'chamber',value:'measure'});
const golden=result('golden-affected',[numeric('position','Position','x'),numeric('reference','Reference','reference_value'),numeric('affected','Affected','affected_value')],
  [[1,10,11],[2,10,15],[3,12,9]],{x:'position',reference_value:'reference',affected_value:'affected'});
const wafer=result('wafer-difference',[numeric('x','Die X','die_x'),numeric('y','Die Y','die_y'),numeric('reference','Reference','reference_value'),numeric('affected','Affected','affected_value')],
  [[1,1,10,11],[2,1,10,15],[3,1,10,9]],{die_x:'x',die_y:'y',reference_value:'reference',affected_value:'affected'});
const prepost=result('pre-post-change',[categorical('cohort','Status','cohort'),numeric('measure','Measurement','value')],
  [['Pre',10],['Post',12],['Pre',14],['Post',16],['Post',20]],{cohort:'cohort',value:'measure'});
const distribution=result('distribution-comparison',[categorical('cohort','Cohort','cohort'),numeric('measure','Measurement','value')],
  [['Control',10],['Control',11],['Affected',30],['Affected',31]],{cohort:'cohort',value:'measure'});
const review=result('distribution-review',[numeric('measure','Measurement','value')],[[10],[12],[11]],{value:'measure'});
const invalidComparison=result('distribution-comparison',[numeric('measure','Measurement','value')],[[10],[12]],{value:'measure'});
const contracts=['yield-pareto','spc-excursion','tool-chamber-matching','golden-affected','wafer-difference','pre-post-change','distribution-comparison','distribution-review'].map(recipeRoleContract);
console.log(JSON.stringify({
  pareto:{ok:pareto.ok,rows:pareto.rows,summary:pareto.summary,provenance:pareto.provenance},
  spc:{ok:spc.ok,rows:spc.rows},
  spcLimits:{ok:spcLimits.ok,summary:spcLimits.summary},
  matrix:{ok:matrix.ok,rows:matrix.rows,summary:matrix.summary},
  golden:{ok:golden.ok,rows:golden.rows,summary:golden.summary},
  wafer:{ok:wafer.ok,rows:wafer.rows,summary:wafer.summary},
  prepost:{ok:prepost.ok,summary:prepost.summary,rows:prepost.rows},
  distribution:{ok:distribution.ok,summary:distribution.summary},
  review:{ok:review.ok,summary:review.summary},
  invalidComparison:{ok:invalidComparison.ok,errors:invalidComparison.errors},
  contracts,
}));
'''
    )

    pareto = payload["pareto"]
    assert pareto["ok"] is True
    assert [(row["category"], row["contribution"]) for row in pareto["rows"]] == [
        ("Particle", 17),
        ("Scratch", 8),
        ("Void", 5),
    ]
    assert [round(row["cumulative_percent"], 6) for row in pareto["rows"]] == [
        56.666667,
        83.333333,
        100,
    ]
    assert pareto["summary"]["total"] == 30
    assert pareto["summary"]["top_contributor"]["category"] == "Particle"
    assert pareto["summary"]["top_contributor"]["value"] == 17
    assert pareto["summary"]["top_contributor"]["share_percent"] == pytest.approx(56.66666666666667)
    assert "group category" in pareto["provenance"]

    assert payload["spc"]["ok"] is True
    assert [(row["time"], row["value"]) for row in payload["spc"]["rows"]] == [
        ("2026-01-01", 10),
        ("2026-01-01", 11),
        ("2026-01-02", 12),
        ("2026-01-03", 9),
    ]
    assert payload["spcLimits"]["summary"]["specification_low"] == 8
    assert payload["spcLimits"]["summary"]["specification_high"] == 14

    assert payload["matrix"]["ok"] is True
    assert {(row["tool"], row["chamber"]): row["value"] for row in payload["matrix"]["rows"]} == {
        ("ETCH-01", "A"): 12,
        ("ETCH-01", "B"): 20,
        ("ETCH-02", "A"): 8,
    }
    assert all("·" in row["label"] for row in payload["matrix"]["rows"])

    assert payload["golden"]["ok"] is True
    assert [(row["x"], row["cohort"], row["value"]) for row in payload["golden"]["rows"]] == [
        (1, "Golden", 10), (1, "Affected", 11),
        (2, "Golden", 10), (2, "Affected", 15),
        (3, "Golden", 12), (3, "Affected", 9),
    ]
    assert payload["golden"]["summary"]["cohorts"] == ["Affected", "Golden"]

    assert payload["wafer"]["ok"] is True
    assert [row["delta"] for row in payload["wafer"]["rows"]] == [1, 5, -1]
    assert payload["wafer"]["summary"]["max_abs_delta"] == 5

    assert payload["prepost"]["ok"] is True
    assert payload["prepost"]["summary"] == {
        "aggregation": "mean",
        "before": 12,
        "after": 16,
        "delta": 4,
        "counts": {"Pre": 2, "Post": 3},
    }

    assert payload["distribution"]["ok"] is True
    assert payload["distribution"]["summary"]["cohort_counts"] == {"Affected": 2, "Control": 2}
    assert payload["review"]["ok"] is True
    assert payload["invalidComparison"]["ok"] is False
    assert any(error["code"] == "MISSING_COHORT" for error in payload["invalidComparison"]["errors"])

    for contract in payload["contracts"]:
        assert contract["required_roles"] == contract["consumed_roles"]


def test_recipe_semantics_fail_closed_for_invalid_values_and_zero_totals():
    payload = node_json(
        r'''
import {executeRecipeSemantics} from './company_ui/products/visualizer/assets/analysis_semantics.mjs';
const fields=[{id:'category',name:'Category',type:'categorical',semantic_tags:['category']},{id:'value',name:'Value',type:'number',semantic_tags:['value']}];
const run=(rows)=>executeRecipeSemantics('yield-pareto',{fields,rows},{category:'category',value:'value'});
const negative=run([['A',-1],['B',2]]);
const zero=run([['A',0],['B',0],['C',null],['D','bad']]);
const prepost=executeRecipeSemantics('pre-post-change',{fields:[{id:'cohort',name:'Cohort',type:'categorical',semantic_tags:['cohort']},{id:'measure',name:'Measurement',type:'number',semantic_tags:['value']}],rows:[['Pre',10],['Post',12],['Hold',11]]},{cohort:'cohort',value:'measure'});
console.log(JSON.stringify({negative:{ok:negative.ok,errors:negative.errors},zero:{ok:zero.ok,rows:zero.rows,summary:zero.summary},prepost:{ok:prepost.ok,errors:prepost.errors}}));
'''
    )
    assert payload["negative"]["ok"] is False
    assert any(error["code"] == "NEGATIVE_CONTRIBUTION" for error in payload["negative"]["errors"])
    assert payload["zero"]["ok"] is True
    assert all(row["cumulative_percent"] == 0 for row in payload["zero"]["rows"])
    assert payload["zero"]["summary"]["total"] == 0
    assert payload["prepost"]["ok"] is False
    assert any(error["code"] == "UNSUPPORTED_COMPARISON_COHORT" for error in payload["prepost"]["errors"])


def test_recipe_refresh_recomputes_derived_values_and_keeps_versioned_contract():
    payload = node_json(
        r'''
import {executeRecipeSemantics} from './company_ui/products/visualizer/assets/analysis_semantics.mjs';
import {recipeExecutionPlan} from './company_ui/products/visualizer/assets/engineering_recipes.mjs';
const fields=[
  {id:'category',name:'Cause',type:'categorical',semantic_tags:['category']},
  {id:'value',name:'Loss',type:'number',semantic_tags:['weight']},
];
const mapping={category:'category',value:'value'};
const first=executeRecipeSemantics('yield-pareto',{id:'bound',revision:4,fields,rows:[['A',10],['B',5]]},mapping);
const refreshed=executeRecipeSemantics('yield-pareto',{id:'bound',revision:5,fields,rows:[['A',2],['B',20]]},mapping);
const plan=recipeExecutionPlan('yield-pareto',fields);
console.log(JSON.stringify({first:first.summary,refreshed:refreshed.summary,revision:refreshed.dataset.revision,version:plan.recipe_version,provenance:plan.provenance.transform_summary}));
'''
    )
    assert payload["first"]["top_contributor"]["category"] == "A"
    assert payload["refreshed"]["top_contributor"]["category"] == "B"
    assert payload["refreshed"]["top_contributor"]["value"] == 20
    assert payload["refreshed"]["top_contributor"]["share_percent"] == pytest.approx(90.9090909090909)
    assert payload["revision"] == 5
    assert payload["version"] == "v2"
    assert "group category" in payload["provenance"]


def test_wafer_and_comparison_invalid_rows_are_explicitly_recoverable():
    payload = node_json(
        r'''
import {executeRecipeSemantics} from './company_ui/products/visualizer/assets/analysis_semantics.mjs';
const fields=[
  {id:'x',name:'Die X',type:'number',semantic_tags:['die_x']},
  {id:'y',name:'Die Y',type:'number',semantic_tags:['die_y']},
  {id:'reference',name:'Reference',type:'number',semantic_tags:['reference_value']},
  {id:'affected',name:'Affected',type:'number',semantic_tags:['affected_value']},
];
const wafer=executeRecipeSemantics('wafer-difference',{fields,rows:[[1,1,10,12],[1,1,14,16],[2,1,10,null]]},{die_x:'x',die_y:'y',reference_value:'reference',affected_value:'affected'});
const golden=executeRecipeSemantics('golden-affected',{fields:[{id:'x',name:'Position',type:'number',semantic_tags:['x']},{id:'reference',name:'Reference',type:'number',semantic_tags:['reference_value']},{id:'affected',name:'Affected',type:'number',semantic_tags:['affected_value']}],rows:[[1,10,null],[2,11,null]]},{x:'x',reference_value:'reference',affected_value:'affected'});
console.log(JSON.stringify({wafer:{rows:wafer.rows,warnings:wafer.warnings},golden:{ok:golden.ok,warnings:golden.warnings,errors:golden.errors}}));
'''
    )
    assert payload["wafer"]["rows"] == [{
        "x": 1, "y": 1, "reference": 12, "affected": 14, "delta": 2, "duplicate_count": 2,
    }]
    assert any(warning["code"] == "DUPLICATE_DIE_COORDINATE" for warning in payload["wafer"]["warnings"])
    assert any(warning["code"] == "INVALID_DIE_ROW" for warning in payload["wafer"]["warnings"])
    assert payload["golden"]["ok"] is False
    assert any(error["code"] == "MISSING_COHORT" for error in payload["golden"]["errors"])
