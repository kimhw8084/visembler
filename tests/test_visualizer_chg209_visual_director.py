from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from company_ui.products.visualizer.domain import VisualizerContractError, canonical_model
from scripts.release_checks.run_chg209_visual_director_matrix import fixture_models, fresh_cold_chain

ROOT = Path(__file__).resolve().parents[1]
COMPOSITION = ROOT / "company_ui/products/visualizer/assets/authoring_composition.mjs"
EDITOR = ROOT / "company_ui/products/visualizer/assets/integrated_editor.mjs"


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


def test_direction_profiles_derive_from_semantic_inventory_and_preserve_recipe_authority() -> None:
    result = node_json(
        r'''
import {visualDirectorProfile,visualDirectorRuleInventory,compositionOrder,compositionProminence,sectionCompositionPlan} from './company_ui/products/visualizer/assets/authoring_composition.mjs';
const item=(id,role,engine,section,more={})=>({id,title:`renamed ${id}`,composition_role:role,engine,section_id:section,...more});
const executive=[item('a','report_headline','TextEngine','opening'),item('b','context','TextEngine','opening'),item('c','hero_metric','MetricEngine','performance'),item('d','hero_metric','MetricEngine','performance'),item('e','primary_analysis','CoreChartEngine','analysis'),item('f','detailed_evidence','TableEngine','evidence',{customTable:{rows:Array.from({length:12},(_,i)=>[i,i*2])}}),item('g','decision_risk','DecisionCompositeEngine','decision'),item('h','conclusion','TextEngine','delivery')];
const experiment=[item('a','report_headline','TextEngine','opening'),item('b','context','TextEngine','opening'),item('c','hero_metric','MetricEngine','performance'),item('d','hero_metric','ComparisonEngine','performance'),item('e','primary_analysis','CoreChartEngine','analysis'),item('f','supporting_analysis','CoreChartEngine','analysis'),item('g','narrative_interpretation','TextEngine','analysis'),item('h','detailed_evidence','TableEngine','evidence'),item('i','decision_risk','DecisionCompositeEngine','decision')];
const causal=[item('a','report_headline','TextEngine','opening'),item('b','hero_metric','MetricEngine','performance'),item('c','detailed_evidence','WaferFabEngine','analysis'),item('d','primary_analysis','EngineeringChartEngine','analysis'),item('e','detailed_evidence','TableEngine','evidence'),item('f','causal_evidence','DiagramEngine','evidence'),item('g','action_status','ProjectCompositeEngine','delivery')];
const dense=[item('a','report_headline','TextEngine','opening'),item('b','context','TextEngine','opening'),item('c','hero_metric','MetricEngine','performance'),item('d','hero_metric','MetricEngine','performance'),item('e','primary_analysis','CoreChartEngine','analysis'),item('f','primary_analysis','EngineeringChartEngine','analysis'),item('g','detailed_evidence','TableEngine','evidence',{rows:Array.from({length:22},(_,i)=>[i,i+1])}),item('h','detailed_evidence','EvidenceCompositeEngine','evidence'),item('i','causal_evidence','DiagramEngine','evidence'),item('j','decision_risk','DecisionCompositeEngine','decision'),item('k','action_status','ProjectCompositeEngine','delivery'),item('l','context','TextEngine','analysis',{text:'constraint and status '.repeat(30)})];
const allocation=[item('a','report_headline','TextEngine','opening'),item('b','hero_metric','ComparisonEngine','performance'),item('b2','hero_metric','MetricEngine','performance'),item('b3','hero_metric','MetricEngine','performance'),item('c','primary_analysis','CoreChartEngine','analysis'),item('c2','primary_analysis','EngineeringChartEngine','analysis'),item('d','detailed_evidence','TableEngine','evidence'),item('e','decision_risk','DecisionCompositeEngine','decision'),item('f','action_status','ProjectCompositeEngine','delivery')];
const sparse=[item('a','report_headline','TextEngine','opening'),item('b','context','TextEngine','opening'),item('c','decision_risk','DecisionCompositeEngine','decision'),item('d','conclusion','TextEngine','delivery')];
const inputs={executive,experiment,causal,dense,allocation,sparse};
const profiles=Object.fromEntries(Object.entries(inputs).map(([key,items])=>[key,visualDirectorProfile(items,{layoutPreset:key==='executive'?'executive':'editorial'})]));
const plans=Object.fromEntries(Object.entries(inputs).map(([key,items])=>[key,sectionCompositionPlan(items,key==='executive'?'executive':'editorial',1440,Object.fromEntries(items.map(x=>[x.id,{minW:260,minH:120}])),profiles[key]).map(section=>({id:section.id,pattern:section.pattern,featureRole:items.find(x=>x.id===section.featureId)?.composition_role||null,featureEngine:items.find(x=>x.id===section.featureId)?.engine||null,rows:section.rows.map(row=>row.ids.map(id=>items.find(x=>x.id===id)?.composition_role))}))]));
const explicit=visualDirectorProfile(executive,{layoutPreset:'technical',choice:'sparse-decision'});
const presetAuthority=visualDirectorProfile(executive,{layoutPreset:'technical'});
const recipeFallback=visualDirectorProfile([],{layoutPreset:'technical'});
const explicitHeroScale=compositionProminence(item('hero','hero_metric','MetricEngine','performance',{emphasis:'hero'}),'executive',profiles.executive);
console.log(JSON.stringify({rules:visualDirectorRuleInventory(),profiles:Object.fromEntries(Object.entries(profiles).map(([key,value])=>[key,{id:value.id,label:value.label,authority:value.authority,recipeId:value.recipeId,traits:value.traits,negativeIdentity:value.negativeIdentity,density:value.density.evidence,focus:value.focus.primaryRoles}])),plans,explicit:{id:explicit.id,authority:explicit.authority,recipeId:explicit.recipeId,directionExplicit:explicit.directionExplicit},presetAuthority:{id:presetAuthority.id,authority:presetAuthority.authority,recipeId:presetAuthority.recipeId},recipeFallback:{id:recipeFallback.id,authority:recipeFallback.authority,recipeId:recipeFallback.recipeId},explicitHeroScale,executiveDirectionOrder:compositionOrder(executive,'executive',profiles.executive).map(x=>x.section_id),legacyRecipeOrder:compositionOrder(executive,'executive').map(x=>x.section_id)}));
'''
    )
    profiles = result["profiles"]
    assert {key: value["id"] for key, value in profiles.items()} == {
        "executive": "decision-led",
        "experiment": "conditional-evidence",
        "causal": "causal-investigation",
        "dense": "dense-operations",
        "allocation": "allocation-comparison",
        "sparse": "sparse-decision",
    }
    assert profiles["executive"]["recipeId"] == "executive"
    assert profiles["executive"]["authority"] == "layout-preset"
    assert len(profiles["causal"]["traits"]) == 3
    assert profiles["causal"]["negativeIdentity"] == "generic chart gallery"
    assert profiles["dense"]["density"] == "dense"
    assert result["explicit"] == {
        "id": "sparse-decision",
        "authority": "user-direction",
        "recipeId": "technical",
        "directionExplicit": True,
    }
    assert result["presetAuthority"] == {
        "id": "decision-led",
        "authority": "semantic-auto",
        "recipeId": "technical",
    }
    assert result["recipeFallback"] == {
        "id": "dense-operations",
        "authority": "layout-preset",
        "recipeId": "technical",
    }
    assert result["explicitHeroScale"] == 1.18
    assert len(result["rules"]["profiles"]) == 8
    assert any("composition roles" in value for value in result["rules"]["classifierInputs"])
    assert "report title" in result["rules"]["forbiddenInputs"]
    assert list(dict.fromkeys(result["executiveDirectionOrder"]))[:3] == ["opening", "evidence", "analysis"]
    assert list(dict.fromkeys(result["legacyRecipeOrder"]))[:3] == ["opening", "performance", "analysis"]
    assert next(section for section in result["plans"]["experiment"] if section["id"] == "analysis")["pattern"] == "conditional-evidence-pair"
    assert next(section for section in result["plans"]["causal"] if section["id"] == "evidence")["pattern"] == "causal-flow-feature"
    dense_analysis = next(section for section in result["plans"]["dense"] if section["id"] == "analysis")
    assert dense_analysis["pattern"] == "dense-evidence-grid"
    assert dense_analysis["rows"][0] == ["primary_analysis", "primary_analysis"]
    assert next(section for section in result["plans"]["dense"] if section["id"] == "evidence")["pattern"] == "causal-flow-feature"
    allocation_plan = next(section for section in result["plans"]["allocation"] if section["id"] == "performance")
    assert allocation_plan["pattern"] == "allocation-comparison"
    assert allocation_plan["featureEngine"] == "ComparisonEngine"
    assert allocation_plan["rows"][0] == ["hero_metric", "hero_metric", "hero_metric"]
    allocation_evidence = next(section for section in result["plans"]["allocation"] if section["id"] == "analysis")
    assert allocation_evidence["pattern"] == "allocation-evidence-grid"
    assert allocation_evidence["rows"][0] == ["primary_analysis", "primary_analysis"]


def test_direction_is_stable_when_report_and_item_names_change_and_profiles_are_not_title_classifiers() -> None:
    result = node_json(
        r'''
import {visualDirectorProfile,sectionCompositionPlan} from './company_ui/products/visualizer/assets/authoring_composition.mjs';
const base=[
 {id:'a',title:'Executive business review',composition_role:'report_headline',engine:'TextEngine',section_id:'opening'},
 {id:'b',title:'Quarterly context',composition_role:'context',engine:'TextEngine',section_id:'opening'},
 {id:'c',title:'Metric 1',composition_role:'hero_metric',engine:'MetricEngine',section_id:'performance'},
 {id:'d',title:'Metric 2',composition_role:'hero_metric',engine:'MetricEngine',section_id:'performance'},
 {id:'e',title:'Cohort evidence',composition_role:'detailed_evidence',engine:'TableEngine',section_id:'evidence',rows:[[1,2],[3,4]]},
 {id:'f',title:'Decision',composition_role:'decision_risk',engine:'DecisionCompositeEngine',section_id:'decision'},
];
const renamed=base.map((item,index)=>({...item,id:`new-${index}`,title:`unrelated label ${index}`}));
const a=visualDirectorProfile(base,{layoutPreset:'editorial'}),b=visualDirectorProfile(renamed,{layoutPreset:'editorial'});
const plan=items=>sectionCompositionPlan(items,'editorial',1440,Object.fromEntries(items.map(item=>[item.id,{minW:260,minH:120}]))).map(section=>({id:section.id,pattern:section.pattern,featureRole:items.find(item=>item.id===section.featureId)?.composition_role}));
console.log(JSON.stringify({sameDirection:a.id===b.id,sameTraits:JSON.stringify(a.traits)===JSON.stringify(b.traits),sameSections:JSON.stringify(plan(base).map(x=>[x.id,x.pattern,x.featureRole]))===JSON.stringify(plan(renamed).map(x=>[x.id,x.pattern,x.featureRole])),profile:a}));
'''
    )
    assert result["sameDirection"] is True
    assert result["sameTraits"] is True
    assert result["sameSections"] is True
    assert result["profile"]["id"] == "decision-led"
    assert result["profile"]["inventory"]["roleCounts"]["hero_metric"] == 2

    source = COMPOSITION.read_text(encoding="utf-8")
    classifier = source[source.index("function inferredDirection"):source.index("function densityHint")]
    forbidden = (
        "executive-business-review", "experiment-decision", "semiconductor-rca",
        "technical-status-review", "supply-chain-capacity-holdout", "report_id",
        "benchmark", "screenshot", "fixture_name",
    )
    assert not any(value in classifier.lower() for value in forbidden)
    assert "\"x\":" not in classifier and "\"y\":" not in classifier
    assert not re.search(r"\b(?:entry|item)\.(?:x|y|left|top)\b", classifier)
    production = "\n".join(path.read_text(encoding="utf-8") for path in (
        COMPOSITION, EDITOR, ROOT / "company_ui/products/visualizer/assets/integrated_editor.css",
        ROOT / "company_ui/products/visualizer/assets/authoring_stage_d.mjs",
    )).lower()
    assert not any(value in production for value in (
        "executive-business-review", "experiment-decision", "semiconductor-rca",
        "technical-status-review", "supply-chain-capacity-holdout",
        "executive cohort decision", "causal yield investigation", "dense operating review",
    ))


def test_free_manual_rectangles_direction_choice_reuse_and_data_contract_are_preserved() -> None:
    result = node_json(
        r'''
import {composeReportModel,visualDirectorProfile} from './company_ui/products/visualizer/assets/authoring_composition.mjs';
import {layoutOperations} from './company_ui/products/visualizer/assets/authoring_stage_d.mjs';
import {buildReusableBindingContract,reusableStructure} from './company_ui/products/visualizer/assets/authoring_reuse_contract.mjs';
const dataset={id:'source-id',name:'Source',revision:4,fields:[{id:'cat-id',name:'Cohort',type:'categorical'},{id:'value-id',name:'Yield',type:'number'}],rows:[['A',91],['B',88]]};
const entry={id:'table',engine:'TableEngine',type:'table',element:'Detailed evidence',composition_role:'detailed_evidence',section_id:'evidence',dataset_id:'source-id',mapping:{category:'cat-id',value:'value-id'},rows:[['A',91],['B',88]],customTable:{headers:['Cohort','Yield'],rows:[['A',91],['B',88]]},x:171,y:283,w:511,h:249};
const free={mode:'free',layoutPreset:'editorial',items:[entry],datasets:[dataset],groups:{},visualDirectionChoice:'auto'},before=structuredClone(free);
const changed={...structuredClone(free),visualDirectionChoice:'causal-investigation'};
const manualRects=value=>value.items.map(({id,x,y,w,h})=>({id,x,y,w,h}));
const composed=composeReportModel({...free,items:[entry,{id:'head',engine:'TextEngine',type:'text',element:'Report headline',composition_role:'report_headline',x:10,y:15,w:320,h:90}]},'editorial');
const contract=buildReusableBindingContract(free),changedContract=buildReusableBindingContract(changed),structure=reusableStructure({...free,items:[entry]},contract);
console.log(JSON.stringify({manualUnchanged:JSON.stringify(manualRects(free))===JSON.stringify(manualRects(changed)),freeLayoutOps:layoutOperations(changed).length,sourceUnchanged:JSON.stringify(free)===JSON.stringify(before),composedPreservesSource:JSON.stringify(composed.datasets)===JSON.stringify(free.datasets)&&JSON.stringify(composed.items.find(item=>item.id==='table').rows)===JSON.stringify(entry.rows)&&JSON.stringify(composed.items.find(item=>item.id==='table').mapping)===JSON.stringify(entry.mapping)&&composed.visualDirectionChoice==='auto',reuseChoice:structure.visualDirectionChoice,roles:structure.items.map(item=>item.composition_role||null),bindingCount:contract.slots[0].bindings.length,reuseBindingsStable:JSON.stringify(contract)===JSON.stringify(changedContract),directionAfterDataReplacement:visualDirectorProfile([{...entry,engine:'TimelineEngine',composition_role:'primary_analysis',dataset_id:'other',mapping:{}}],{layoutPreset:'editorial'}).id}));
'''
    )
    assert result["manualUnchanged"] is True
    assert result["freeLayoutOps"] == 0
    assert result["sourceUnchanged"] is True
    assert result["composedPreservesSource"] is True
    assert result["reuseChoice"] == "auto"
    assert result["bindingCount"] == 1
    assert result["reuseBindingsStable"] is True
    assert result["directionAfterDataReplacement"] == "editorial"

    editor = EDITOR.read_text(encoding="utf-8")
    setter = editor[editor.index("function setVisualDirection"):editor.index("function autoLayout")]
    assert "model.patch" in setter and "visualDirectionChoice" in setter
    assert "composeReportModel" not in setter
    assert "visualDirection:()=>currentVisualDirection()" in editor


def test_visual_direction_choice_round_trips_through_shared_model_and_history() -> None:
    result = node_json(
        r'''
import {EditorStore,parseCanonical,serializeCanonical} from './company_ui/products/visualizer/vendor/production_core/core/editor_store.mjs';
const base={schema_version:1,authoring_schema:'authoring-p0-v1',datasets:[],items:[],groups:{},mode:'smart',layoutPreset:'editorial',crossFilter:null,canvas:{width:1600,height:900},nextId:20};
const store=new EditorStore(base,{revision:1});
const command=store.command([{op:'model.patch',patch:{visualDirectionChoice:'causal-investigation'}}],'Set direction');
store.commit(command);const saved=serializeCanonical(parseCanonical(store.serialize()));
store.undo(store.revision);const undone=JSON.parse(store.serialize());
store.redo(store.revision);const redone=JSON.parse(store.serialize());
console.log(JSON.stringify({saved:JSON.parse(saved),undoneHasChoice:Object.hasOwn(undone,'visualDirectionChoice'),redone:redone.visualDirectionChoice,stable:serializeCanonical(parseCanonical(store.serialize()))===store.serialize()}));
'''
    )
    assert result["saved"]["visualDirectionChoice"] == "causal-investigation"
    assert result["undoneHasChoice"] is False
    assert result["redone"] == "causal-investigation"
    assert result["stable"] is True

    persisted = canonical_model({"items": [], "visualDirectionChoice": "causal-investigation"})
    assert canonical_model(persisted)["visualDirectionChoice"] == "causal-investigation"
    with pytest.raises(VisualizerContractError):
        canonical_model({"items": [], "visualDirectionChoice": 7})


def test_fresh_mixed_holdout_has_new_task_fields_and_consistent_decision_evidence() -> None:
    fixtures, _ = fixture_models(ROOT)
    holdout = fresh_cold_chain(fixtures["supply-chain-capacity-holdout"])
    dataset = holdout["datasets"][0]
    assert dataset["id"] == "holdout-cold-chain-dataset"
    assert {field["id"] for field in dataset["fields"]} == {
        "delivery_week", "dose_kits_required", "confirmed_cold_slots", "supplier_lead_days"
    }
    assert {field["name"] for field in dataset["fields"]} == {
        "Delivery week", "Dose kits required", "Confirmed cold slots", "Supplier lead days"
    }
    for item in holdout["items"]:
        if item.get("dataset_id"):
            assert item["dataset_id"] == dataset["id"]
            assert set(item.get("mapping", {}).values()) <= {field["id"] for field in dataset["fields"]}
    comparison = next(item for item in holdout["items"] if item.get("engine") == "ComparisonEngine")
    assert comparison["title"] == "Demand versus confirmed cold slots · W13"
    assert (comparison["before"], comparison["after"]) == (120000, 134000)
    flow = next(item for item in holdout["items"] if item.get("engine") == "DiagramEngine")
    assert "carrier appointment" in " ".join(flow["nodes"]).lower()
    assert "p70" not in json.dumps(holdout).lower()
    assert "w38" not in json.dumps(holdout).lower()


def test_export_plan_rounds_fractional_element_dimensions_to_nearest_emu() -> None:
    from company_ui.products.visualizer.ppt_service import _plan

    target_width = 12_192_000
    target_height = 9_144_000
    geometry = {
        "canvas": {"width": 1600, "height": 1200},
        "items": [
            {"id": "fractional", "x": 1, "y": 2, "w": 1467.1823, "h": 241.5107}
        ],
    }
    plan = _plan(
        {"items": [{"id": "fractional", "engine": "TextEngine", "x": 1, "y": 2, "w": 1467.1823, "h": 241.5107}]},
        geometry,
        target_width=target_width,
        target_height=target_height,
    )
    scale = min(target_width / 1600, target_height / 1200)
    item = plan["items"][0]

    # The adapter's Inches conversion truncates normalized EMU dimensions.
    # Exported bounds should match the report canvas's nearest-EMU projection.
    assert int(item["nw"] * target_width) == round(1467.1823 * scale)
    assert int(item["nh"] * target_height) == round(241.5107 * scale)
