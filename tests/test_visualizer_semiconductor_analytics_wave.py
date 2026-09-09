from __future__ import annotations

import json
import subprocess
from pathlib import Path


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


def test_promoted_analytics_keep_the_legacy_library_and_have_real_renderer_contracts():
    payload = node_json(r'''
import {PRODUCTION_LIBRARY_COUNT, productionEntries, isProductionElement} from './company_ui/products/visualizer/assets/production_library.mjs';
import {CHART_TYPES, chartModelFromEntry, chartToEntry, renderChartSvg, switchChartType} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
const dataset={id:'fab',revision:4,fields:[
  {id:'x',name:'Position',type:'number',semantic_tags:[]},
  {id:'y',name:'Measurement',type:'number',semantic_tags:['value']},
  {id:'cause',name:'Defect Cause',type:'categorical',semantic_tags:['category']},
  {id:'count',name:'Count',type:'number',semantic_tags:['weight']},
  {id:'run',name:'Run',type:'categorical',semantic_tags:['identifier']}
],rows:[[1,5,'Particle',10,'A'],[2,8,'Scratch',7,'A'],[3,13,'Particle',3,'B'],[4,11,'Void',1,'B']]};
const promoted=['Multi-Line','Scatter Plot','Regression Scatter','Histogram','Box Plot','Pareto'];
const rendered=promoted.map(type=>{const model=chartModelFromEntry({engine:'CoreChartEngine',element:type,title:type},dataset);const svg=renderChartSvg(model);return {type,svg:svg.slice(0,30),hasSvg:svg.includes('<svg'),safe:!/[Nn]aN|Infinity/.test(svg)};});
const base=chartModelFromEntry({engine:'CoreChartEngine',element:'Line Chart',title:'Yield trend',mapping:{x:'x',y:'y'}},dataset);
const switched=switchChartType(base,'Regression Scatter'),switchedEntry=chartToEntry({engine:'CoreChartEngine',element:'Line Chart',title:'Yield trend'},switched);
console.log(JSON.stringify({count:PRODUCTION_LIBRARY_COUNT,entries:productionEntries().length,promoted,promotedProduction:promoted.map(element=>isProductionElement('CoreChartEngine',element)),chartTypes:promoted.map(element=>CHART_TYPES.includes(element)),rendered,switch:{type:switched.chart_type,dataset:switched.dataset.id,revision:switched.dataset.revision,title:switchedEntry.title,mapping:switched.mapping}}));
''')
    assert payload["count"] == payload["entries"] == 45
    assert all(payload["promotedProduction"])
    assert all(payload["chartTypes"])
    assert all(item["hasSvg"] and item["safe"] for item in payload["rendered"])
    assert payload["switch"] == {
        "type": "Regression Scatter",
        "dataset": "fab",
        "revision": 4,
        "title": "Yield trend",
        "mapping": {"x": "x", "y": "y"},
    }


def test_data_first_recommendations_are_explainable_and_resolve_to_promoted_targets():
    payload = node_json(r'''
import {intakeText, productionRecommendations} from './company_ui/products/visualizer/assets/authoring_data.mjs';
const cases={
  scatter:'x\ty\n1\t5\n2\t8\n3\t13',
  distribution:'measurement\n10\n12\n11\n13',
  pareto:'defect_cause\tcount\nParticle\t42\nScratch\t18\nVoid\t7',
  spc:'timestamp\tmeasurement\n2026-01-01\t10\n2026-01-02\t11\n2026-01-03\t9',
};
const output=Object.fromEntries(Object.entries(cases).map(([name,text])=>{const result=intakeText(text);return [name,productionRecommendations(result).slice(0,3).map(item=>({view:item.view,target:item.production_target,reason:item.reason}))]}));
console.log(JSON.stringify(output));
''')
    assert payload["scatter"][0]["target"]["element"] == "Scatter Plot"
    assert payload["distribution"][0]["target"]["element"] == "Histogram"
    assert payload["pareto"][0]["target"]["element"] == "Pareto"
    assert payload["spc"][0]["target"]["element"] == "Line Chart"
    assert all(item["reason"] for values in payload.values() for item in values)


def test_governed_engineering_transforms_are_deterministic_and_typed():
    payload = node_json(r'''
import {applyRecipe} from './company_ui/products/visualizer/assets/authoring_transforms.mjs';
const dataset={fields:[{id:'time',name:'Time',type:'integer'},{id:'a',name:'A',type:'number'},{id:'b',name:'B',type:'number'}],rows:[[1,10,2],[2,14,4],[3,13,5],[4,19,7]]};
const recipe={steps:[
  {type:'calculated',source_fields:['a','b'],operation:'subtract',name:'Delta'},
  {type:'difference',source_field:'a',name:'A change'},
  {type:'percent_change',source_field:'a',name:'A % change'},
  {type:'rolling_mean',source_field:'a',window:2,name:'A rolling mean'},
  {type:'z_score',source_field:'a',name:'A z'},
  {type:'cumulative_percent',source_field:'b',name:'B cumulative %'}
]};
const first=applyRecipe(dataset,recipe),second=applyRecipe(dataset,recipe);
console.log(JSON.stringify({fields:first.fields.map(field=>field.name),rows:first.rows,stable:JSON.stringify(first)===JSON.stringify(second),sourceUnchanged:dataset.fields.length===3&&dataset.rows.length===4}));
''')
    assert payload["stable"] is True
    assert payload["sourceUnchanged"] is True
    assert payload["fields"][-6:] == ["Delta", "A change", "A % change", "A rolling mean", "A z", "B cumulative %"]
    assert payload["rows"][0][-5:] == [None, None, 10, -1.0690449676496976, 11.11111111111111]
    assert payload["rows"][3][-1] == 100


def test_engineering_recipe_catalog_is_bounded_to_supported_production_visuals():
    payload = node_json(r'''
import {recommendEngineeringRecipes} from './company_ui/products/visualizer/assets/engineering_recipes.mjs';
const fields=[
  {id:'tool',name:'Tool',type:'categorical',semantic_tags:['tool']},
  {id:'chamber',name:'Chamber',type:'categorical',semantic_tags:['chamber']},
  {id:'measurement',name:'Measurement',type:'number',semantic_tags:['value']},
  {id:'time',name:'Timestamp',type:'datetime',semantic_tags:['time']},
];
const recipes=recommendEngineeringRecipes(fields);
console.log(JSON.stringify({ids:recipes.map(recipe=>recipe.id),ready:recipes.every(recipe=>recipe.ready),visuals:recipes.flatMap(recipe=>recipe.visuals)}));
''')
    assert "tool-chamber-matching" in payload["ids"]
    assert "spc-excursion" in payload["ids"]
    assert all(item in {"Hero KPI", "Key Takeaway", "Line Chart", "Clean Table", "SPC Control Chart", "Horizontal Bar", "Executive Statement", "Before/After KPI", "Box Plot", "Histogram", "Wafer Map"} for item in payload["visuals"])
