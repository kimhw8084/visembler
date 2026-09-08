from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "company_ui" / "products" / "visualizer" / "assets"


def node_json(source: str):
    result = subprocess.run(["node", "--input-type=module", "-e", source], cwd=ROOT, check=True, text=True, capture_output=True)
    return json.loads(result.stdout)


def test_data_first_recommendations_resolve_only_to_curated_production_targets() -> None:
    audit = node_json(r"""
import {intakeText, productionRecommendations, productionTargetForView, planDataFirstCreation} from './company_ui/products/visualizer/assets/authoring_data.mjs';
import {isProductionElement, PRODUCTION_LIBRARY_COUNT} from './company_ui/products/visualizer/assets/production_library.mjs';
const cases={
 wafer:'wafer_id\tdie_x\tdie_y\tyield_pct\nW01\t1\t1\t98.2\nW01\t2\t1\t97.8\nW01\t1\t2\t98.6',
 trend:'timestamp\tyield_pct\n2026-09-01\t98.1\n2026-09-02\t98.4\n2026-09-03\t98.7',
 category:'tool\tyield_pct\nETCH-01\t98.1\nETCH-02\t97.2\nETCH-03\t99.0',
 flow:'source\ttarget\tcount\nInspect\tReview\t42\nReview\tDisposition\t38',
 engineering:'subgroup\tmeasurement\tlsl\tusl\nA\t10.1\t9.5\t10.5\nA\t10.2\t9.5\t10.5\nB\t9.9\t9.5\t10.5',
 timeline:'date\tevent\n2026-09-01\tDiscovery\n2026-09-03\tValidation\n2026-09-05\tRelease',
 scatter:'x\ty\n1\t5\n2\t8\n3\t13',
};
const output=Object.fromEntries(Object.entries(cases).map(([name,text])=>{const intake=intakeText(text), recommendations=productionRecommendations(intake); const first=recommendations[0]; return [name,{recommendations,first:first?.production_target?.element,plan:planDataFirstCreation({intake,view:first?.view,mapping:first?.mapping,datasetId:'test'})}]}));
console.log(JSON.stringify({count:PRODUCTION_LIBRARY_COUNT,output,targets:Object.values(output).flatMap(value=>value.recommendations).map(r=>isProductionElement(r.production_target.engine,r.production_target.element)),scatterTarget:productionTargetForView('scatter')}));
""")
    assert audit["count"] == 39
    assert all(audit["targets"])
    assert audit["output"]["wafer"]["first"] == "Wafer Map"
    assert audit["output"]["trend"]["first"] == "Line Chart"
    assert audit["output"]["category"]["first"] == "Vertical Bar"
    assert audit["output"]["flow"]["first"] == "Data Flow"
    assert audit["output"]["engineering"]["first"] == "SPC Control Chart"
    assert audit["output"]["timeline"]["first"] == "Event Timeline"
    assert audit["output"]["scatter"]["first"] == "Clean Table"
    assert audit["scatterTarget"] is None
    assert all("Bar Chart" not in str(value) for value in audit["output"].values())


def test_data_first_planner_preserves_typed_scalars_and_rejects_invalid_manual_mapping() -> None:
    audit = node_json(r"""
import {intakeText, productionRecommendations, planDataFirstCreation} from './company_ui/products/visualizer/assets/authoring_data.mjs';
const intake=intakeText('tool\tyield_pct\tlot_id\nETCH-01\t0\t00123\nETCH-02\t"0"\t00124\nETCH-03\t""\t');
const rec=productionRecommendations(intake)[0];
const valid=planDataFirstCreation({intake,view:rec.view,mapping:rec.mapping,datasetId:'typed'});
const invalid=planDataFirstCreation({intake,view:'bar',mapping:{category:rec.mapping.category,value:rec.mapping.category},datasetId:'invalid'});
console.log(JSON.stringify({rec,valid,invalid,rows:intake.rows}));
""")
    assert audit["valid"]["valid"] is True
    assert audit["invalid"]["valid"] is False
    assert audit["rows"] == [["ETCH-01", 0, "00123"], ["ETCH-02", "0", "00124"], ["ETCH-03", "", None]]


def test_data_first_editor_entry_points_share_the_planner_and_keep_accessible_dialog_hooks() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    html = (ASSETS / "integrated_editor.html").read_text(encoding="utf-8")
    assert 'id="pasteDataBtn"' in html and "Excel, CSV, or TSV" in html
    assert "Paste data and create visual" in editor
    assert "function openDataFirstDialog" in editor
    assert "function createDataFirstVisual" in editor
    assert "planDataFirstCreation" in editor
    assert "productionRecommendations(result)[0]" in editor  # blank canvas path uses the shared production filter
    assert "Replace selected data" in editor and "dataFirstReplace" in editor
    assert "dataFirstText" in editor and "openModal(modal,$('#dataFirstText'))" in editor


def test_data_first_keeps_the_frozen_connector_byte_identical() -> None:
    connector = ROOT / "company_ui" / "products" / "visualizer" / "vendor" / "production_core" / "core" / "GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js"
    assert hashlib.sha256(connector.read_bytes()).hexdigest() == "d8ebd4378f01b7c52a7a4be57c578c22adf29b899cc08a370cf084881195343e"
