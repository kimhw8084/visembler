from __future__ import annotations

import json
import subprocess
from pathlib import Path

from company_ui.products.visualizer.domain import canonical_model
from company_ui.products.visualizer.repository import ReportRepository

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "company_ui/products/visualizer/assets"


def node_json(source: str):
    result = subprocess.run(
        ["node", "--input-type=module", "-e", source],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_p1_transform_recipe_is_typed_operation_specific_and_ordered():
    value = node_json(
        r'''
import {applyRecipe} from './company_ui/products/visualizer/assets/authoring_transforms.mjs';
const dataset={fields:[{id:'name',name:'Name',type:'string'},{id:'score',name:'Score',type:'number'}],rows:[['keep',2],['keep',9],['drop',10],['keep',4]]};
const recipe={steps:[{type:'filter',field:'name',operator:'equals',value:'keep'},{type:'sort',field:'score',direction:'desc'},{type:'top_n',ranking_field:'score',n:2},{type:'rename',field:'score',name:'Rank score'}]};
const output=applyRecipe(dataset,recipe);
console.log(JSON.stringify({rows:output.rows,fields:output.fields.map(field=>field.name),typed:applyRecipe({...dataset,rows:[["0",'0'],['1',0]]},{steps:[{type:'top_n',ranking_field:'score',n:1}]}).rows}));
'''
    )
    assert value["rows"] == [["keep", 9], ["keep", 4]]
    assert value["fields"] == ["Name", "Rank score"]
    assert value["typed"] == [["1", 0]]


def test_p1_renderers_preserve_comparison_units_captions_and_wide_columns():
    value = node_json(
        r'''
import {renderIntegratedElement} from './company_ui/products/visualizer/assets/element_renderer.mjs';
const wide={engine:'TableEngine',element:'Clean Table',id:'t1',customTable:{headers:['A','B','C','D','E'],rows:[[1,2,3,4,5]]}};
const comparison=renderIntegratedElement({engine:'ComparisonEngine',element:'Before/After KPI',before:10,after:20,unit:'min'});
const image=renderIntegratedElement({engine:'ImageMediaEngine',element:'Image + Caption',id:'i1',alt:'A real image description',caption:'Review caption'});
console.log(JSON.stringify({wide:(renderIntegratedElement(wide).match(/<th(?:\s|>)/g)||[]).length,unit:comparison.includes('comparison-unit')&&comparison.includes('min'),caption:image.includes('data-direct="caption"')&&image.includes('Review caption'),alt:image.includes('A real image description')}));
'''
    )
    assert value == {"wide": 5, "unit": True, "caption": True, "alt": True}


def test_p1_report_description_is_revisioned_metadata_and_manager_contract_is_visible(tmp_path: Path):
    repo = ReportRepository(tmp_path)
    first = repo.create("p1", title="Pilot", model=canonical_model({"items": []}))
    updated = repo.update_description("p1", "Internal review report", expected_revision=first.revision)
    assert updated.revision == first.revision + 1
    assert updated.metadata["description"] == "Internal review report"
    assert repo.list_history("p1")[0]["revision"] == updated.revision

    page = (ROOT / "company_ui/products/visualizer/page.py").read_text(encoding="utf-8")
    assert "Export current JSON" in page and "Search active reports" in page and "Recently modified" in page
    assert "update_description" in page


def test_p1_transform_mapping_mobile_chrome_and_wide_table_contracts_are_wired():
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    html = (ASSETS / "integrated_editor.html").read_text(encoding="utf-8")
    css = (ASSETS / "integrated_editor.css").read_text(encoding="utf-8")
    assert "top_n" in editor and "data-transform-step-action" in editor and "Reorder" in editor
    assert "Manage saved mappings" in editor and "mapping-compatibility" in editor
    assert 'id="libraryClose"' in html and 'id="panelBackdrop"' in html
    assert 'id="saveBtn">Autosaved' in html
    assert '.debug-badge[data-level="idle"]{display:none}' in css
    assert ".data-dock-header" in css and ".table-scroll" in css
