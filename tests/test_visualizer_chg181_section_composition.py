from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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


def test_section_grammar_selects_patterns_and_deterministic_feature_support() -> None:
    result = node_json(
        r'''
import {sectionCompositionPlan} from './company_ui/products/visualizer/assets/authoring_composition.mjs';
const items=[
 {id:'title',element:'Hero Title',engine:'TextEngine',composition_role:'report_headline',section_id:'opening',section_title:'Decision brief',order:0},
 {id:'context',element:'Body Narrative',engine:'TextEngine',composition_role:'context',section_id:'opening',section_title:'Decision brief',order:1},
 {id:'m1',element:'Hero KPI',engine:'MetricEngine',composition_role:'hero_metric',section_id:'performance',order:2,emphasis:'standard'},
 {id:'m2',element:'Hero KPI',engine:'MetricEngine',composition_role:'hero_metric',section_id:'performance',order:3},
 {id:'m3',element:'Before/After KPI',engine:'ComparisonEngine',composition_role:'hero_metric',section_id:'performance',order:4},
 {id:'main',element:'Bar Chart',engine:'CoreChartEngine',composition_role:'primary_analysis',section_id:'analysis',order:5},
 {id:'support',element:'Bar Chart',engine:'CoreChartEngine',composition_role:'supporting_analysis',section_id:'analysis',order:6},
 {id:'risk',element:'Risk Callout',engine:'DecisionCompositeEngine',composition_role:'decision_risk',section_id:'decision',order:7},
 {id:'next',element:'Project Card',engine:'ProjectCompositeEngine',composition_role:'action_status',section_id:'delivery',order:8},
];
const first=sectionCompositionPlan(items,'executive',1440,{main:{minW:380},support:{minW:380}}),second=sectionCompositionPlan(items,'executive',1440,{main:{minW:380},support:{minW:380}});
console.log(JSON.stringify({patterns:first.map(value=>[value.id,value.pattern]),stable:JSON.stringify(first)===JSON.stringify(second),opening:first.find(value=>value.id==='opening'),performance:first.find(value=>value.id==='performance'),analysis:first.find(value=>value.id==='analysis'),ids:first.flatMap(value=>value.rows.flatMap(row=>row.ids))}));
'''
    )
    assert result["patterns"] == [
        ["opening", "hero-opening-band"],
        ["performance", "compact-kpi-strip"],
        ["analysis", "feature-support-analysis"],
        ["decision", "compact-decision-band"],
        ["delivery", "closing-next-step"],
    ]
    assert result["stable"] is True
    assert result["analysis"]["featureId"] == "main"
    assert result["analysis"]["supportIds"] == ["support"]
    assert result["analysis"]["rows"][0]["ids"] == ["main", "support"]
    assert result["patterns"][1] == ["performance", "compact-kpi-strip"]
    assert result["patterns"][0] == ["opening", "hero-opening-band"]
    assert result["opening"]["rows"][0]["ids"] == ["title", "context"]
    assert result["opening"]["rows"][0]["ratios"] == [0.68, 0.32]
    assert result["performance"]["featureId"] == "m2"
    assert result["performance"]["rows"][0]["ids"] == ["m2", "m1", "m3"]
    assert result["performance"]["rows"][0]["ratios"] == [0.42, 0.29, 0.29]
    assert sorted(result["ids"]) == sorted(["title", "context", "m1", "m2", "m3", "main", "support", "risk", "next"])


def test_section_patterns_cover_narrative_evidence_causal_and_detail_grid() -> None:
    result = node_json(
        r'''
import {sectionCompositionPlan} from './company_ui/products/visualizer/assets/authoring_composition.mjs';
const model=[
 {id:'n',element:'Body Narrative',engine:'TextEngine',text:'Short finding',composition_role:'narrative_interpretation',section_id:'analysis'},
 {id:'photo',element:'Image Evidence',engine:'ImageMediaEngine',composition_role:'detailed_evidence',section_id:'analysis'},
 {id:'story',element:'Body Narrative',engine:'TextEngine',text:'Long interpretation. '.repeat(24),composition_role:'narrative_interpretation',section_id:'multi-analysis'},
 {id:'main',element:'Line Chart',engine:'CoreChartEngine',composition_role:'primary_analysis',section_id:'multi-analysis'},
 {id:'support1',element:'SPC Control Chart',engine:'EngineeringChartEngine',composition_role:'supporting_analysis',section_id:'multi-analysis'},
 {id:'support2',element:'Box Plot',engine:'EngineeringChartEngine',composition_role:'supporting_analysis',section_id:'multi-analysis'},
 {id:'flow',element:'Process Flow',engine:'DiagramEngine',composition_role:'causal_evidence',section_id:'evidence'},
 {id:'ev1',element:'Evidence Table',engine:'TableEngine',composition_role:'detailed_evidence',section_id:'detail'},
 {id:'ev2',element:'Image Evidence',engine:'ImageMediaEngine',composition_role:'detailed_evidence',section_id:'detail'},
];
const plan=sectionCompositionPlan(model,'technical',1440,{n:{minW:260},photo:{minW:280},story:{minW:320},main:{minW:380},support1:{minW:380},support2:{minW:380},flow:{minW:380},ev1:{minW:340},ev2:{minW:280}});
console.log(JSON.stringify(plan.map(value=>({id:value.id,pattern:value.pattern,rows:value.rows.map(row=>row.ids)}))));
'''
    )
    assert result == [
        {"id": "multi-analysis", "pattern": "feature-support-analysis", "rows": [["main", "support1", "support2"], ["story"]]},
        {"id": "analysis", "pattern": "narrative-evidence-split", "rows": [["n", "photo"]]},
        {"id": "evidence", "pattern": "causal-flow-feature", "rows": [["flow"]]},
        {"id": "detail", "pattern": "evidence-detail-grid", "rows": [["ev1", "ev2"]]},
    ]


def test_long_narrative_content_gets_its_own_intrinsic_row() -> None:
    result = node_json(
        r'''
import {sectionCompositionPlan} from './company_ui/products/visualizer/assets/authoring_composition.mjs';
const items=[
 {id:'story',element:'Body Narrative',engine:'TextEngine',text:'A measured interpretation that needs room. '.repeat(24),composition_role:'narrative_interpretation',section_id:'analysis',order:0},
 {id:'plot',element:'Line Chart',engine:'CoreChartEngine',composition_role:'primary_analysis',section_id:'analysis',order:1},
];
const plan=sectionCompositionPlan(items,'technical',1440,{story:{minW:320,prefH:500},plot:{minW:380,prefH:380}});
console.log(JSON.stringify({pattern:plan[0].pattern,rows:plan[0].rows.map(row=>row.ids),contentFit:items[0].text.length>360&&plan[0].rows[0].ids.includes('story')&&plan[0].rows[0].ids.length===1}));
'''
    )
    assert result == {"pattern": "narrative-evidence-split", "rows": [["story"], ["plot"]], "contentFit": True}


def test_section_fallback_custom_metadata_emphasis_and_semantic_nonmutation() -> None:
    result = node_json(
        r'''
import {sectionCompositionPlan,compositionSpacing} from './company_ui/products/visualizer/assets/authoring_composition.mjs';
const custom=[
 {id:'a',element:'Line Chart',engine:'CoreChartEngine',view_type:'line',variant:'area',mapping:{x:'time',y:'value'},data:[['Mon',3]],transform_recipe:{id:'keep'},composition_role:'primary_analysis',section_id:'custom-intro',section_title:'Process context',section_order:4,order:2},
 {id:'b',element:'Line Chart',engine:'CoreChartEngine',composition_role:'supporting_analysis',section_id:'custom-intro',section_title:'Process context',section_order:4,order:3,emphasis:'hero'},
 {id:'legacy',element:'Clean Table',engine:'TableEngine',section_id:'appendix',section_title:'Appendix',section_order:8,order:4},
];
const before=JSON.stringify(custom),plan=sectionCompositionPlan(custom,'review',1100,{a:{minW:380,prefH:400},b:{minW:380,prefH:200}}),repeat=sectionCompositionPlan(custom,'review',1100,{a:{minW:380,prefH:400},b:{minW:380,prefH:200}}),gaps=['dense','compact','comfortable','unknown'].map(density=>compositionSpacing({density,itemCount:12}));
console.log(JSON.stringify({pattern:plan[0].pattern,feature:plan[0].featureId,custom:plan[0].title,customOrder:plan[0].order,legacy:plan[1].pattern,legacyTitle:plan[1].title,stable:JSON.stringify(plan)===JSON.stringify(repeat),unmutated:before===JSON.stringify(custom),ids:plan.flatMap(section=>section.rows.flatMap(row=>row.ids)),gaps}));
'''
    )
    assert result["pattern"] == "feature-support-analysis"
    assert result["feature"] == "b"  # Explicit hero emphasis remains authoritative.
    assert result["custom"] == "Process context"
    assert result["customOrder"] == 0
    assert result["legacy"] == "evidence-detail-grid"
    assert result["legacyTitle"] == "Appendix"
    assert result["stable"] is True
    assert result["unmutated"] is True
    assert result["ids"] == ["b", "a", "legacy"]
    assert all(12 <= gap["stackGap"] <= 20 and 20 <= gap["sectionGap"] <= 34 for gap in result["gaps"])


def test_section_width_fit_is_bounded_and_mobile_order_uses_composed_order() -> None:
    result = node_json(
        r'''
import {sectionCompositionPlan} from './company_ui/products/visualizer/assets/authoring_composition.mjs';
const items=[{id:'a',element:'Line Chart',engine:'CoreChartEngine',composition_role:'primary_analysis',section_id:'analysis',order:8},{id:'b',element:'Box Plot',engine:'EngineeringChartEngine',composition_role:'supporting_analysis',section_id:'analysis',order:2}];
const plan=sectionCompositionPlan(items,'technical',720,{a:{minW:380},b:{minW:380}}),flat=plan.flatMap(section=>section.rows.flatMap(row=>row.ids)),path='company_ui/products/visualizer/assets/integrated_editor.mjs';
console.log(JSON.stringify({rows:plan[0].rows.map(row=>row.ids),ratios:plan[0].rows.map(row=>row.ratios),allPlaced:flat.length===items.length&&new Set(flat).size===items.length,source:await (await import('node:fs/promises')).readFile(path,'utf8')}));
'''
    )
    assert result["allPlaced"] is True
    assert result["rows"] == [["a"], ["b"]]
    # Smart mobile Preview follows the derived composition order, while other modes keep user order.
    assert "model().mode==='smart'&&Number.isFinite(Number(r.order))?Number(r.order)*2+1" in result["source"]
    assert "sectionCompositionPlan(ordered,preset,CANVAS.w,profiles)" in result["source"]
    assert "Math.min(MAX_CANVAS_H,Math.max(360,Math.ceil(baseNeeded)))" in result["source"]


def test_shared_remap_requirements_deduplicate_roles_and_summarize_incompatibility() -> None:
    result = node_json(
        r'''
import {groupedRemapRequirements,summarizedRemapIssues,remapStatusSummary} from './company_ui/products/visualizer/assets/authoring_reuse_presentation.mjs';
const source={bindings:[
 {item_id:'chart',element:'Line Chart',view:'line',required_roles:['x','y'],field_roles:[{role:'x',field_name:'Region',field_type:'categorical',semantic_tags:['category'],required:true},{role:'y',field_name:'Sales',field_type:'number',semantic_tags:['measurement'],required:true}],references:[]},
 {item_id:'table',element:'Evidence Table',view:'table',required_roles:['category','value'],field_roles:[{role:'category',field_name:'Region',field_type:'categorical',semantic_tags:['category'],required:true},{role:'value',field_name:'Sales',field_type:'number',semantic_tags:['measurement'],required:true}],references:[]},
]};
const slot={mapping:{chart:{x:'region',y:'sales'},table:{category:'region',value:'sales'}},unresolved:[],problems:[
 {item_id:'chart',role:'x',source_field:'Region',reason:'incompatible type'},
 {item_id:'table',role:'category',source_field:'Region',reason:'incompatible type'},
]};
const requirements=groupedRemapRequirements(source,slot),issues=summarizedRemapIssues(source,slot);
console.log(JSON.stringify({roles:requirements.map(value=>[value.label,value.itemIds,value.value,value.assignments]),issues:issues.map(value=>value.message),summary:remapStatusSummary({ok:false})}));
'''
    )
    assert len(result["roles"]) == 2
    assert [value[0] for value in result["roles"]] == ["Category", "Measurement"]
    assert all(value[2] for value in result["roles"])
    assert all(len(value[1]) == 2 for value in result["roles"])
    assert result["issues"] == ["Region needs a compatible field for category. · Affects 2 visuals."]
    assert result["summary"] == "Resolve the highlighted data source and field requirements before applying."


def test_remap_focus_accessibility_and_fail_closed_apply_contract_remain_present() -> None:
    source = (ROOT / "company_ui/products/visualizer/assets/integrated_editor.mjs").read_text()
    css = (ROOT / "company_ui/products/visualizer/assets/integrated_editor.css").read_text()
    assert "data-remap-assignments=\"${assignments}\"" in source
    assert "aria-label=\"${esc(label)} for ${esc(scope)}: ${esc(requirement.consumersLabel)}\"" in source
    assert "node?.focus({preventScroll:true})" in source
    assert "data-remap-role" in source and "data-remap-dataset" in source
    assert '<button type="submit" class="tb accent" ${plan.ok?' in source
    assert "data-remap-assignments" in source and "selection.mappings[target.itemId]" in source
    assert ".reuse-remap-consumers" in css
