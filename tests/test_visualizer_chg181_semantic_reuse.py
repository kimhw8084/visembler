from __future__ import annotations

import json
import subprocess
from pathlib import Path

from company_ui.products.visualizer.page import _normalize_presets
from company_ui.products.visualizer.templates import REPORT_TEMPLATES

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "company_ui" / "products" / "visualizer" / "assets"


def node_json(source: str) -> dict:
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", source],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode:
        raise AssertionError(f"Node fixture failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def source_model() -> dict:
    dataset = {
        "id": "private-source-dataset",
        "name": "Quarterly Sales",
        "revision": 7,
        "fields": [
            {"id": "region-field", "name": "Region", "type": "categorical", "semantic_tags": ["category"]},
            {"id": "sales-field", "name": "Sales", "type": "number", "semantic_tags": ["measurement"]},
        ],
        "rows": [["East", 80], ["West", 95]],
    }
    common = {
        "dataset_id": dataset["id"],
        "message_role": "Primary Evidence",
        "transform_recipe": {
            "id": "rolling-sales-recipe",
            "source_dataset_id": dataset["id"],
            "steps": [{"type": "rolling_mean", "source_field": "sales-field", "window": 3}],
        },
        "transform_pipeline": [{"type": "filter", "field": "sales-field", "operator": "greater_than", "value": 0}],
        "analysis_recipe": {
            "id": "sales-analysis-v4",
            "version": 4,
            "source_dataset_id": dataset["id"],
            "mappings": {"value": "sales-field"},
            "semantic_contract": "value-level derived analysis",
        },
        "statistical_recipe": {
            "id": "summary-statistics-v2",
            "version": 2,
            "source_dataset_id": dataset["id"],
            "value_field": "sales-field",
        },
        "chart_studio": {
            "dataset_id": dataset["id"],
            "dataset": dataset,
            "mapping": {"x": "region-field", "y": "sales-field"},
            "transforms": {"steps": [{"type": "rolling_mean", "source_field": "sales-field"}]},
            "visual": {"palette": "report", "lineWidth": 3},
        },
        "data": [["East", 80], ["West", 95]],
        "rows": [["East", 80], ["West", 95]],
    }
    return {
        "mode": "smart",
        "layoutPreset": "review",
        "canvas": {"width": 1440, "height": 1200},
        "datasets": [dataset],
        "items": [
            {"id": "chart-1", "engine": "CoreChartEngine", "type": "chart", "element": "Line Chart", "view_type": "line", "mapping": {"x": "region-field", "y": "sales-field"}, **common},
            {"id": "table-1", "engine": "TableEngine", "type": "table", "element": "Clean Table", "view_type": "table", "mapping": {"category": "region-field", "value": "sales-field"}, "customTable": {"headers": ["Region", "Sales"], "rows": [["East", 80]]}, **common},
        ],
    }


def test_chg181_composition_roles_and_named_recipes_are_deterministic_and_legacy_safe() -> None:
    result = node_json(
        r'''
import {compositionRole,composeReportModel,compositionRecipe} from './company_ui/products/visualizer/assets/authoring_composition.mjs';
const legacy={mode:'guided',layoutPreset:'editorial',canvas:{width:1200,height:900},items:[
 {id:'risk',element:'Risk Callout',engine:'DecisionCompositeEngine',order:0,message_role:'Risk'},
 {id:'metric',element:'Hero KPI',engine:'MetricEngine',type:'metric',order:1},
 {id:'comparison',element:'Before/After KPI',engine:'ComparisonEngine',type:'comparison',order:1.5},
 {id:'headline',element:'Hero Title',engine:'TextEngine',type:'text',order:2},
 {id:'chart',element:'Line Chart',engine:'CoreChartEngine',type:'chart',order:3},
 {id:'narrative',element:'Body Narrative',engine:'TextEngine',type:'text',order:4},
 {id:'table',element:'Clean Table',engine:'TableEngine',type:'table',order:5},
 {id:'diagram',element:'Process Flow',engine:'DiagramEngine',type:'diagram',order:6},
 {id:'takeaway',element:'Key Takeaway',engine:'TextEngine',type:'text',order:7},
]};
const executive=composeReportModel(legacy,'executive'),technical=composeReportModel(legacy,'technical');
console.log(JSON.stringify({roles:legacy.items.map(compositionRole),executive:executive.items.map(x=>[x.id,x.composition_role,x.section_id,x.order]),technical:technical.items.map(x=>[x.id,x.order]),smart:executive.mode,legacyUntouched:legacy.items.every(x=>!x.composition_role),recipe:compositionRecipe('investigation').roles.slice(0,4)}));
'''
    )
    assert result["roles"] == ["decision_risk", "hero_metric", "hero_metric", "report_headline", "primary_analysis", "narrative_interpretation", "detailed_evidence", "causal_evidence", "conclusion"]
    executive_order = [entry[0] for entry in sorted(result["executive"], key=lambda entry: entry[3])]
    assert executive_order[:4] == ["headline", "metric", "comparison", "chart"]
    assert executive_order.index("risk") > executive_order.index("chart")
    assert result["smart"] == "smart"
    assert result["legacyUntouched"] is True
    technical_order = [entry[0] for entry in sorted(result["technical"], key=lambda entry: entry[1])]
    assert executive_order.index("table") < executive_order.index("diagram")
    assert technical_order.index("diagram") < technical_order.index("table")
    assert result["recipe"] == ["report_headline", "context", "hero_metric", "primary_analysis"]


def test_chg181_smart_composition_has_stable_non_overlapping_bounded_rectangles() -> None:
    result = node_json(
        r'''
import {layoutOperations,contentFitSummary} from './company_ui/products/visualizer/assets/authoring_stage_d.mjs';
import {composeReportModel} from './company_ui/products/visualizer/assets/authoring_composition.mjs';
const model=composeReportModel({mode:'smart',layoutPreset:'executive',canvas:{width:1440,height:4800},items:[
 {id:'c',element:'Line Chart',engine:'CoreChartEngine',type:'chart',order:5,composition_role:'primary_analysis'},
 {id:'m2',element:'Hero KPI',engine:'MetricEngine',type:'metric',order:4,composition_role:'hero_metric'},
 {id:'h',element:'Hero Title',engine:'TextEngine',type:'text',order:3,composition_role:'report_headline'},
 {id:'m1',element:'Hero KPI',engine:'MetricEngine',type:'metric',order:2,composition_role:'hero_metric'},
 {id:'t',element:'Clean Table',engine:'TableEngine',type:'table',order:1,composition_role:'detailed_evidence'},
 {id:'n',element:'Body Narrative',engine:'TextEngine',type:'text',order:0,text:'A long interpretation '.repeat(60),composition_role:'narrative_interpretation'},
]},'executive');
const a=layoutOperations(model,{action:'clean'}),b=layoutOperations(model,{action:'clean'}),rects=a.map(op=>({id:op.id,...op.patch}));
const overlap=(left,right)=>left.x<right.x+right.w&&left.x+left.w>right.x&&left.y<right.y+right.h&&left.y+left.h>right.y;
console.log(JSON.stringify({stable:JSON.stringify(a)===JSON.stringify(b),roles:contentFitSummary(model).items.map(x=>x.role),rects,overlaps:rects.some((left,index)=>rects.slice(index+1).some(right=>overlap(left,right))),bounded:rects.every(rect=>rect.x>=0&&rect.y>=0&&rect.x+rect.w<=1440&&rect.y+rect.h<=4800),free:layoutOperations({...model,mode:'free'}).length}));
'''
    )
    assert result["stable"] is True
    assert result["overlaps"] is False
    assert result["bounded"] is True
    assert result["free"] == 0
    narrative = next(rect for rect in result["rects"] if rect["id"] == "n")
    assert narrative["w"] > 1200


def test_chg181_builtin_templates_include_canonical_semantic_intent() -> None:
    assert set(REPORT_TEMPLATES) >= {"executive-brief", "investigation-rca", "operations-review", "wafer-fab-analysis", "executive-business-review", "semiconductor-rca", "experiment-decision", "technical-status-review"}
    for template in REPORT_TEMPLATES.values():
        assert all(item.get("composition_role") for item in template["model"]["items"])
        assert all(item.get("section_id") and item.get("section_title") for item in template["model"]["items"])
    executive = REPORT_TEMPLATES["executive-business-review"]["model"]["items"]
    assert {item["composition_role"] for item in executive} >= {"report_headline", "context", "hero_metric", "primary_analysis", "detailed_evidence", "decision_risk", "conclusion"}
    semiconductor = REPORT_TEMPLATES["semiconductor-rca"]["model"]["items"]
    assert {item["composition_role"] for item in semiconductor} >= {"report_headline", "hero_metric", "primary_analysis", "detailed_evidence", "causal_evidence", "narrative_interpretation", "action_status"}
    experiment = REPORT_TEMPLATES["experiment-decision"]["model"]["items"]
    assert {item["composition_role"] for item in experiment} >= {"context", "hero_metric", "supporting_analysis", "narrative_interpretation", "decision_risk"}
    assert next(item for item in experiment if item["element"] == "Line Chart")["composition_role"] == "primary_analysis"
    assert next(item for item in experiment if item["element"] == "Box Plot")["composition_role"] == "supporting_analysis"
    assert next(item for item in experiment if item["element"] == "Before/After KPI")["composition_role"] == "hero_metric"


def test_chg181_binding_contract_groups_shared_data_and_reuses_new_data_atomically() -> None:
    model = source_model()
    result = node_json(
        """
import {buildReusableBindingContract,reusableStructure,planReusableRemap,applyReusableRemap,normalizedBindingContract} from './company_ui/products/visualizer/assets/authoring_reuse_contract.mjs';
import {pasteCompositionPlan} from './company_ui/products/visualizer/assets/authoring_clipboard.mjs';
const source=JSON.parse(process.env.CHG181_SOURCE),before=structuredClone(source),contract=buildReusableBindingContract(source),structure=reusableStructure(source,contract);
const destination={id:'new-dataset',name:'Follow-up sales',revision:2,fields:[{id:'new-region',name:'Region',type:'categorical',semantic_tags:['category']},{id:'new-sales',name:'Sales',type:'number',semantic_tags:['measurement']}],rows:[['North',170],['South',155]]};
const plan=planReusableRemap(contract,[destination]),applied=applyReusableRemap(structure,plan,[destination]);
const section=applyReusableRemap(reusableStructure({kind:'composition',items:source.items,groups:[],datasets:source.datasets},contract),plan,[destination]),paste=pasteCompositionPlan({mode:'smart',nextId:20,items:[],groups:{},datasets:[destination]},section,{preserveExistingDatasets:true}),pastedItems=paste.ops.filter(op=>op.op==='item.add').map(op=>op.item);
console.log(JSON.stringify({version:normalizedBindingContract(contract)?.version,slots:contract.slots.length,shared:contract.slots[0]?.bindings.length,leaked:JSON.stringify(contract).includes('private-source-dataset'),sourceUnchanged:JSON.stringify(source)===JSON.stringify(before),structureEmpty:structure.datasets.length===0&&structure.items.every(item=>!item.dataset_id&&!item.mapping&&!item.chart_studio?.dataset)&&structure.items[0].transform_pipeline[0].field==='Sales'&&structure.items[1].customTable.rows.length===0,ok:plan.ok,bound:applied.items.map(item=>item.dataset_id),mappings:applied.items.map(item=>item.mapping),transform:applied.items[0].transform_recipe.steps[0].source_field,transformSource:applied.items[0].transform_recipe.source_dataset_id,pipelineField:applied.items[0].transform_pipeline[0].field,analysisField:applied.items[0].analysis_recipe.mappings.value,stats:applied.items[0].statistical_recipe.value_field,chartData:applied.items[0].chart_studio.dataset.id,sourceRows:source.datasets[0].rows,sectionRetainsSelectedDataset:pastedItems.length===2&&pastedItems.every(item=>item.dataset_id==='new-dataset')&&!paste.ops.some(op=>op.op==='model.patch'&&op.patch.datasets)}));
""".replace("process.env.CHG181_SOURCE", json.dumps(json.dumps(model)))
    )
    assert result["version"] == 1
    assert result["slots"] == 1
    assert result["shared"] == 2
    assert result["leaked"] is False
    assert result["sourceUnchanged"] is True
    assert result["structureEmpty"] is True
    assert result["ok"] is True
    assert result["bound"] == ["new-dataset", "new-dataset"]
    assert result["mappings"][0] == {"x": "new-region", "y": "new-sales"}
    assert result["transform"] == "new-sales"
    assert result["transformSource"] == "new-dataset"
    assert result["pipelineField"] == "new-sales"
    assert result["analysisField"] == "new-sales"
    assert result["stats"] == "new-sales"
    assert result["chartData"] == "new-dataset"
    assert result["sourceRows"] == [["East", 80], ["West", 95]]
    assert result["sectionRetainsSelectedDataset"] is True


def test_chg181_remap_fails_closed_for_ambiguous_and_incompatible_fields() -> None:
    model = source_model()
    result = node_json(
        """
import {buildReusableBindingContract,planReusableRemap} from './company_ui/products/visualizer/assets/authoring_reuse_contract.mjs';
const source=JSON.parse(process.env.CHG181_SOURCE),slot=buildReusableBindingContract(source).slots[0];
const ambiguous={id:'ambiguous',name:'Two Region columns',fields:[{id:'region-a',name:'Region',type:'categorical',semantic_tags:['category']},{id:'region-b',name:'REGION',type:'categorical',semantic_tags:['category']},{id:'sales',name:'Sales',type:'number',semantic_tags:['measurement']}],rows:[]};
const incompatible={id:'incompatible',name:'Text sales',fields:[{id:'region',name:'Region',type:'categorical',semantic_tags:['category']},{id:'sales',name:'Sales',type:'string',semantic_tags:['measurement']}],rows:[]};
const selected={ [slot.identity]:{dataset_id:ambiguous.id} },a=planReusableRemap({version:1,kind:'analytical-bindings',slots:[slot]},[ambiguous],selected),partial=planReusableRemap({version:1,kind:'analytical-bindings',slots:[slot]},[ambiguous]),b=planReusableRemap({version:1,kind:'analytical-bindings',slots:[slot]},[incompatible],{[slot.identity]:{dataset_id:incompatible.id}});
console.log(JSON.stringify({ambiguous:a.ok,ambiguity:a.slots[0].unresolved.some(value=>value.reason==='ambiguous'),autoSelected:partial.slots[0].dataset_id===ambiguous.id,partialBlocked:!partial.ok,incompatible:b.ok,typeProblem:b.slots[0].problems.some(value=>value.reason==='incompatible type'),badVersion:planReusableRemap({...buildReusableBindingContract(source),version:2},[ambiguous]).ok}));
""".replace("process.env.CHG181_SOURCE", json.dumps(json.dumps(model)))
    )
    assert result == {"ambiguous": False, "ambiguity": True, "autoSelected": True, "partialBlocked": True, "incompatible": False, "typeProblem": True, "badVersion": False}


def test_chg181_remap_blocks_a_schema_match_that_cannot_run_its_saved_analysis_recipe() -> None:
    result = node_json(
        r'''
import {buildReusableBindingContract,planReusableRemap} from './company_ui/products/visualizer/assets/authoring_reuse_contract.mjs';
const source={datasets:[{id:'source-capability',name:'Capability cohort',fields:[{id:'measurement',name:'Measurement',type:'number'},{id:'lsl',name:'LSL',type:'number'},{id:'usl',name:'USL',type:'number'}],rows:[[10,0,20],[11,0,20],[12,0,20]]}],items:[{id:'capability',engine:'EngineeringChartEngine',type:'chart',element:'Process Capability',view_type:'engineering',dataset_id:'source-capability',mapping:{value:'measurement'},analysis_recipe:{id:'process-capability',version:'statistical-v1',mapping:{value:'measurement',specification_low:'lsl',specification_high:'usl'}}}]};
const contract=buildReusableBindingContract(source),destination={id:'bad-values',name:'Text measurements',fields:[{id:'new-measurement',name:'Measurement',type:'number'},{id:'new-lsl',name:'LSL',type:'number'},{id:'new-usl',name:'USL',type:'number'}],rows:[['unmeasured',0,20],['unknown',0,20]]};
const plan=planReusableRemap(contract,[destination]);
console.log(JSON.stringify({ready:plan.ok,selected:plan.slots[0].dataset_id,message:plan.slots[0].problems[0]?.message||''}));
'''
    )
    assert result["ready"] is False
    assert result["selected"] == "bad-values"
    assert "Process Capability cannot use this data" in result["message"]
    assert "finite" in result["message"].lower()


def test_chg181_reused_bar_summary_keeps_category_and_value_roles_visible() -> None:
    result = node_json(
        r'''
import {chartSummary} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
const model={chart_type:'Vertical Bar',dataset:{fields:[{id:'region',name:'Region',type:'categorical'},{id:'revenue',name:'Revenue',type:'number'}],rows:[['East',180],['West',205]]},mapping:{category:'region',value:'revenue',x:'revenue',y:'revenue'}};
console.log(JSON.stringify({summary:chartSummary(model)}));
'''
    )
    assert "Category Region" in result["summary"]
    assert "Value Revenue" in result["summary"]
    assert "X Revenue" not in result["summary"]


def test_chg181_short_bar_scale_avoids_near_duplicate_endpoint_ticks() -> None:
    result = node_json(
        r'''
import {buildCanonicalChartPlan} from './company_ui/products/visualizer/assets/canonical_chart_renderer.mjs';
const model={chart_type:'Vertical Bar',dataset:{fields:[{id:'region',name:'Region',type:'categorical'},{id:'revenue',name:'Revenue',type:'number'}],rows:[['East',180],['West',205]]},mapping:{category:'region',value:'revenue'},axes:{x:{},y:{tickCount:5,zeroBaseline:true}},legend:{show:true,position:'bottom'},visual:{barMode:'grouped',barWidth:.62},series:[]};
const plan=buildCanonicalChartPlan(model,{width:760,height:400});
console.log(JSON.stringify({ticks:plan.yTicks}));
'''
    )
    assert 200 in result["ticks"]
    assert 205 not in result["ticks"]


def test_chg181_spatial_reports_clip_wafer_cells_to_company_geometry() -> None:
    result = node_json(
        r'''
import {renderChartSvg} from './company_ui/products/visualizer/assets/authoring_chart_studio.mjs';
const dataset={id:'wafer-data',fields:[{id:'x',name:'Die X',type:'integer'},{id:'y',name:'Die Y',type:'integer'},{id:'value',name:'Yield',type:'number'},{id:'reference',name:'Reference',type:'number'},{id:'affected',name:'Affected',type:'number'}],rows:[[5,0,88,98,88],[3,4,97,99,97],[0,0,98,98,98]]};
const wafer=renderChartSvg({chart_type:'Wafer Map',dataset,mapping:{die_x:'x',die_y:'y',value:'value'}},{width:520,height:520});
const difference=renderChartSvg({chart_type:'Wafer Difference Map',dataset,mapping:{die_x:'x',die_y:'y',reference_value:'reference',affected_value:'affected'}},{width:760,height:440});
console.log(JSON.stringify({waferClipped:wafer.includes('clip-path="url(#cui-spatial-clip-520-520)"')&&wafer.includes('id="cui-spatial-clip-520-520"'),differenceClipped:difference.includes('clip-path="url(#cui-spatial-clip-760-440)"')&&difference.includes('id="cui-spatial-clip-760-440"'),dies:(wafer.match(/data-wafer-die=/g)||[]).length,deltaDies:(difference.match(/data-wafer-die=/g)||[]).length}));
'''
    )
    assert result["waferClipped"] is True
    assert result["differenceClipped"] is True
    assert result["dies"] == 3
    assert result["deltaDies"] == 3


def test_chg181_structure_remap_does_not_create_empty_dataset_recipe_identity() -> None:
    result = node_json(
        r'''
import {buildReusableBindingContract,reusableStructure,planReusableRemap,applyReusableRemap} from './company_ui/products/visualizer/assets/authoring_reuse_contract.mjs';
const source={datasets:[{id:'source',name:'Sales',fields:[{id:'category',name:'Region',type:'categorical'},{id:'value',name:'Revenue',type:'number'}],rows:[['East',20],['West',30]]}],items:[{id:'chart',element:'Vertical Bar',engine:'CoreChartEngine',type:'chart',view_type:'bar',dataset_id:'source',mapping:{category:'category',value:'value'},transform_recipe:{steps:[]},transform_pipeline:[]}]};
const contract=buildReusableBindingContract(source),structure=reusableStructure(source,contract),destination={id:'destination',name:'New sales',fields:[{id:'new-category',name:'Region',type:'categorical'},{id:'new-value',name:'Revenue',type:'number'}],rows:[['North',100],['South',90]]},plan=planReusableRemap(contract,[destination]),applied=applyReusableRemap(structure,plan,[destination]),item=applied.items[0];
console.log(JSON.stringify({ready:plan.ok,dataset_id:item.dataset_id,transform:item.transform_recipe||null,pipeline:item.transform_pipeline||null,analysis:item.analysis_recipe||null,statistical:item.statistical_recipe||null,engineering:item.engineering_recipe||null,staleRows:item.data||null}));
'''
    )
    assert result == {
        "ready": True,
        "dataset_id": "destination",
        "transform": None,
        "pipeline": None,
        "analysis": None,
        "statistical": None,
        "engineering": None,
        "staleRows": None,
    }


def test_chg181_normalization_and_visible_reuse_choice_preserve_legacy_and_copy_modes() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert 'value.reuse_mode===\'structure\'?' in editor
    assert 'value="structure" checked> Reuse structure with new data' in editor
    assert 'value="copy"> Keep source data with this preset' in editor
    assert 'data-remap-source-copy' in editor
    assert 'data-remap-add-source>Add a data source' in editor
    assert 'Need another source? Add it through Data First' in editor
    assert "data-reusepreset" in editor
    assert "Apply with source data" in editor
    assert "Reuse with new data" in editor
    legacy = {
        "id": "legacy",
        "name": "Old report",
        "model": {"mode": "smart", "layoutPreset": "editorial", "items": [], "datasets": [], "groups": {}},
    }
    copy_record = {"id": "copy", "name": "Copy", "kind": "report", "reuse_mode": "copy", "model": legacy["model"]}
    normalized = _normalize_presets([legacy, copy_record])
    assert len(normalized) == 2
    assert "kind" not in normalized[0]
    assert normalized[1]["reuse_mode"] == "copy"


def test_chg181_structure_only_preferences_reject_cross_report_dataset_identity() -> None:
    report = {
        "id": "reuse",
        "name": "Reusable report",
        "kind": "report",
        "reuse_mode": "structure",
        "binding_contract": {"version": 1, "kind": "analytical-bindings", "slots": []},
        "model": {"mode": "smart", "layoutPreset": "executive", "items": [], "datasets": [], "groups": {}},
    }
    accepted = _normalize_presets([report])
    assert len(accepted) == 1
    assert accepted[0]["reuse_mode"] == "structure"
    bad = json.loads(json.dumps(report))
    bad["binding_contract"]["slots"] = [{"identity": "slot", "name": "Sales", "source_schema_signature": "", "source_fields": [], "bindings": [{"item_id": "c1", "dataset_id": "private"}]}]
    assert _normalize_presets([bad]) == []


def test_chg181_corrupt_and_oversized_binding_records_do_not_poison_legacy_presets() -> None:
    legacy = {
        "id": "legacy",
        "name": "Legacy report",
        "model": {"mode": "smart", "layoutPreset": "editorial", "items": [], "datasets": [], "groups": {}},
    }
    corrupt = {
        "id": "corrupt",
        "name": "Unsupported contract",
        "reuse_mode": "structure",
        "binding_contract": {"version": 8, "kind": "analytical-bindings", "slots": []},
        "model": legacy["model"],
    }
    oversized = {
        "id": "oversized",
        "name": "Oversized contract",
        "reuse_mode": "structure",
        "binding_contract": {
            "version": 1,
            "kind": "analytical-bindings",
            "slots": [{"identity": "large", "name": "Sales", "source_fields": [{"name": "x" * 1_500_001}], "bindings": []}],
        },
        "model": legacy["model"],
    }
    normalized = _normalize_presets([corrupt, oversized, legacy])
    assert [record["id"] for record in normalized] == ["legacy"]
    assert "binding_contract" not in normalized[0]


def test_chg181_structure_reuse_clears_unbound_values_and_names_manual_review() -> None:
    result = node_json(
        r'''
import {buildReusableBindingContract,reusableStructure} from './company_ui/products/visualizer/assets/authoring_reuse_contract.mjs';
import {renderIntegratedElement} from './company_ui/products/visualizer/assets/element_renderer.mjs';
const source={items:[
 {id:'metric',engine:'MetricEngine',element:'Hero KPI',value:95,delta:3,series:[['W1',92],['W2',95]]},
 {id:'strip',engine:'MetricEngine',element:'Metric Strip',target:100,metrics:[['East',80],{label:'West',value:95,target:100,share:52}]},
 {id:'compare',engine:'ComparisonEngine',element:'Before/After KPI',before:62,after:91,unit:'%'},
 {id:'table',engine:'TableEngine',element:'Clean Table',customTable:{headers:['Region','Revenue'],rows:[['East',80]]},rows:[['East',80]]},
]};
const contract=buildReusableBindingContract(source),structure=reusableStructure(source,contract);
console.log(JSON.stringify({manual:contract.manual_value_items,items:structure.items,comparison:renderIntegratedElement({engine:'ComparisonEngine',element:'Before/After KPI',before:null,after:null,unit:'%'})}));
'''
    )
    assert [item["kind"] for item in result["manual"]] == ["key_metric", "key_metric", "comparison", "evidence_table"]
    metric, strip, comparison, table = result["items"]
    assert "value" not in metric and "series" not in metric
    assert "target" not in strip and strip["metrics"] == [["East", None], {"label": "West"}]
    assert "before" not in comparison and "after" not in comparison
    assert table["customTable"]["rows"] == [] and table["rows"] == []
    assert "62" not in result["comparison"] and "91" not in result["comparison"]
