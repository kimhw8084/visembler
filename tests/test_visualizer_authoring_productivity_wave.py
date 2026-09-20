from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "company_ui" / "products" / "visualizer" / "assets"


def node_json(source: str):
    result = subprocess.run(
        ["node", "--input-type=module", "-e", source],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


def test_productivity_matrix_covers_exactly_the_production_library() -> None:
    result = node_json(
        r"""
import {productionEntries,PRODUCTION_LIBRARY_COUNT} from './company_ui/products/visualizer/assets/production_library.mjs';
console.log(JSON.stringify({count:PRODUCTION_LIBRARY_COUNT,entries:productionEntries().map(item=>item.element)}));
"""
    )
    matrix = (ROOT / "docs" / "VISSEMBLER_AUTHORING_PRODUCTIVITY_MATRIX.md").read_text()
    assert result["count"] == len(result["entries"]) == 52
    assert len(set(result["entries"])) == 52
    assert all(f"| {element} |" in matrix for element in result["entries"])


def test_content_first_clipboard_contract_uses_one_shared_path() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "on($('#pasteDataBtn'),'click',()=>openDataFirstDialog())" in editor
    assert "if(action==='paste')openDataFirstDialog()" in editor
    assert "async function handleClipboardText(text)" in editor
    assert "on(window,'paste',async(e)=>{if(ui.preview||hasAuthoringTextFocus())return;" in editor
    assert "active?.isContentEditable" in editor


def test_dataset_inline_edit_is_field_aware() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    values = (ASSETS / "authoring_values.mjs").read_text(encoding="utf-8")
    assert "export function parseAuthoringFieldValue" in values
    assert "parseAuthoringFieldValue(raw,field||{},{quoted})" in editor
    assert "parseCellForField(value,directDataset.fields?.[directColumn])" in editor

    result = node_json(
        r"""
import {parseAuthoringFieldValue} from './company_ui/products/visualizer/assets/authoring_values.mjs';
console.log(JSON.stringify([
  parseAuthoringFieldValue('0',{type:'identifier'}),
  parseAuthoringFieldValue('0',{type:'categorical'}),
  parseAuthoringFieldValue('0',{type:'number'}),
  parseAuthoringFieldValue('',{type:'number'}),
  parseAuthoringFieldValue('""',{type:'string'}),
]));
"""
    )
    assert result == ["0", "0", 0, None, ""]


def test_focused_browser_controls_are_not_intercepted_by_canvas_paste() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert "hasAuthoringTextFocus()" in editor
    assert "input,textarea,select,[role=\"textbox\"],[contenteditable=\"true\"]" in editor
    assert "if(ui.preview||hasAuthoringTextFocus())return" in editor


def test_chg138_shared_human_authoring_authority_handles_dense_fields_and_pipeline_preview() -> None:
    result = node_json(
        r"""
import {intakeText} from './company_ui/products/visualizer/assets/authoring_data.mjs';
import {humanRoleLabel,humanFieldBrowserMarkup,humanEncodingShelvesMarkup,transformOutcomeSummary,previewTransformPipeline,datasetConsequenceSummary} from './company_ui/products/visualizer/assets/authoring_human.mjs';
const header=['Tool','Affected','Reference','Lot Code',...Array.from({length:32},(_,i)=>`Very long field name ${i+1}`)].join('\t');
const intake=intakeText(`${header}\nETCH-B\t10\t8\t0012\t0\t"0"\t\tbad-date\t${Array(28).fill('1').join('\t')}\nETCH-C\t11\t9\t0007\t1\t2\t\t2026-01-01\t${Array(28).fill('2').join('\t')}`);
const fields=intake.fields,rows=intake.rows;
const calc={type:'calculated',source_fields:[fields[1].id,fields[2].id],operation:'subtract',name:'Delta'};
const preview=previewTransformPipeline({fields,rows},{steps:[calc]});
const consumers=[{id:'a',element:'Chart A'},{id:'b',element:'Chart B',locked:true}];
console.log(JSON.stringify({
  fieldCount:fields.length,
  fieldSearch:humanFieldBrowserMarkup({fields,rows,query:'long field name 31'}).includes('Very long field name 31'),
  labels:[humanRoleLabel('category'),humanRoleLabel('reference_value'),humanRoleLabel('specification_low')],
  shelves:humanEncodingShelvesMarkup({fields,mapping:{category:fields[0].id,value:fields[1].id},view:'bar'}).includes('Category')&&humanEncodingShelvesMarkup({fields,mapping:{category:fields[0].id,value:fields[1].id},view:'bar'}).includes('Measurement'),
  summary:transformOutcomeSummary(calc,fields),
  preview:{ok:preview.ok,added:preview.columnsAdded,rows:preview.rowCountAfter},
  consequence:datasetConsequenceSummary({id:'d',resource_id:'r'},consumers,'a'),
}));
"""
    )
    assert result["fieldCount"] >= 36
    assert result["fieldSearch"] is True
    assert result["labels"] == ["Category", "Reference / Golden", "Lower specification"]
    assert result["shelves"] is True
    assert result["summary"] == "Create Delta from Affected − Reference"
    assert result["preview"]["ok"] is True
    assert result["preview"]["added"] == ["Delta"]
    assert result["preview"]["rows"] == 2
    assert result["consequence"]["shared"] is True
    assert result["consequence"]["lockedNames"] == ["Chart B"]


def test_chg138_surfaces_use_shared_task_hierarchy_and_no_json_transform_summary() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    studio = (ASSETS / "chart_studio.mjs").read_text(encoding="utf-8")
    for label in ("Fields", "Encodings", "Data grid", "Transforms", "Source"):
        assert label in editor
    for label in ("Data understanding", "Spreadsheet data grid", "Transform pipeline"):
        assert label in studio
    assert "JSON.stringify(step)" not in studio
    assert "Field names separated by commas" not in editor


def test_chg138_r2_preview_uses_the_governed_renderer_for_each_production_family() -> None:
    result = node_json(
        r"""
import {intakeText,productionTargetForView} from './company_ui/products/visualizer/assets/authoring_data.mjs';
import {renderDataFirstPreview,transientProductionEntry} from './company_ui/products/visualizer/assets/authoring_preview.mjs';
import {renderIntegratedElement} from './company_ui/products/visualizer/assets/element_renderer.mjs';
const cases=[
  ['table','category\tvalue\nA\t1\nB\t2',{category:'category_1',value:'value_2'},html=>html.includes('<table')],
  ['timeline','date\tevent\n2024-01-01\tstart\n2024-01-02\tstop',{time:'date_1',category:'event_2'},html=>html.includes('timeline-rail')],
  ['diagram','source\ttarget\nA\tB\nB\tC',{source:'source_1',target:'target_2'},html=>html.includes('diagram-svg')],
  ['line','category\tvalue\nA\t1\nB\t2',{x:'category_1',y:'value_2'},html=>html.includes('chart-studio-render')],
  ['engineering','date\tmeasurement\n2024-01-01\t1\n2024-01-02\t2',{time:'date_1',value:'measurement_2'},html=>html.includes('chart-studio-spc-control-chart')],
  ['wafer','die_x\tdie_y\tvalue\n1\t2\t98\n2\t3\t97',{die_x:'die_x_1',die_y:'die_y_2',value:'value_3'},html=>html.includes('cs-wafer-svg')],
];
const output={};
for(const [view,text,mapping,assertion] of cases){
  const dataset={...intakeText(text),id:'preview-dataset'};
  const target=productionTargetForView(view);
  const preview=renderDataFirstPreview({target,view,mapping,dataset});
  const entry=transientProductionEntry({target,view,mapping,dataset});
  const postCreate=renderIntegratedElement(entry);
  output[view]={actual:assertion(preview),parity:preview===postCreate,transientId:entry.id,engine:entry.engine};
}
console.log(JSON.stringify(output));
"""
    )
    assert all(item["actual"] and item["parity"] for item in result.values())
    assert all(item["transientId"] == "__data-first-preview__" for item in result.values())
    assert {item["engine"] for item in result.values()} == {
        "TableEngine", "TimelineEngine", "DiagramEngine", "CoreChartEngine", "EngineeringChartEngine", "WaferFabEngine"
    }


def test_chg138_r2_shared_mapping_and_transform_drafts_are_safe_and_prospective() -> None:
    result = node_json(
        r"""
import {intakeText} from './company_ui/products/visualizer/assets/authoring_data.mjs';
import {humanMappingAssignment,transformRecipeWithDraft,previewTransformPipeline} from './company_ui/products/visualizer/assets/authoring_human.mjs';
const dataset=intakeText('label\tfirst\tsecond\nA\t10\t3\nB\t9\t2');
const fields=dataset.fields,recipe={steps:[]},before=JSON.stringify({dataset,recipe});
const calculated={type:'calculated',source_fields:[fields[1].id,fields[2].id],operation:'subtract',name:'delta'};
const unpivot={type:'unpivot',keep_fields:[fields[0].id]};
const calculatedDraft=transformRecipeWithDraft(recipe,calculated,null);
const calculatedPreview=previewTransformPipeline(dataset,calculatedDraft);
const unpivotPreview=previewTransformPipeline(dataset,transformRecipeWithDraft(recipe,unpivot,null));
const afterDraft=JSON.stringify({dataset,recipe});
const invalid=humanMappingAssignment({value:fields[1].id},'value',fields[0],fields,'bar');
const valid=humanMappingAssignment({},'value',fields[1],fields,'bar');
const saved=transformRecipeWithDraft(recipe,calculated,null);
console.log(JSON.stringify({unchanged:before===afterDraft,calculated:{ok:calculatedPreview.ok,rows:calculatedPreview.rowCountAfter,added:calculatedPreview.columnsAdded,sample:calculatedPreview.after.rows[0]},unpivot:{ok:unpivotPreview.ok,rows:unpivotPreview.rowCountAfter},invalid,valid,saved}));
"""
    )
    assert result["unchanged"] is True
    assert result["calculated"]["ok"] is True
    assert result["calculated"]["added"] == ["delta"]
    assert result["calculated"]["sample"][-1] == 7
    assert result["unpivot"] == {"ok": True, "rows": 4}
    assert result["invalid"]["ok"] is False
    assert "needs a number" in result["invalid"]["error"]
    assert result["valid"]["ok"] is True
    assert result["saved"]["steps"][0]["type"] == "calculated"


def test_chg138_r2_shared_search_mapping_and_draft_hooks_are_present_in_both_surfaces() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    studio = (ASSETS / "chart_studio.mjs").read_text(encoding="utf-8")
    human = (ASSETS / "authoring_human.mjs").read_text(encoding="utf-8")
    assert "state.fieldQuery=event.target.value" in editor
    assert "state.fieldQuery=node.value" in studio
    assert "setSelectionRange(start,end)" in editor
    assert "setSelectionRange(start,end)" in studio
    assert "humanMappingAssignment(state.mapping" in editor
    assert "humanMappingAssignment(state.model.mapping" in studio
    assert "transformRecipeWithDraft(recipe,draft,index)" in editor
    assert "transformRecipeWithDraft({steps},draft,index)" in studio
    assert "export function humanMappingAssignment" in human
    assert "export function transformRecipeWithDraft" in human
    assert "export function readHumanTransformStep" in human
