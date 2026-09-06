from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "company_ui" / "products" / "visualizer" / "assets"


def test_wafer_route_is_a_supported_bound_identity_role() -> None:
    command = r'''
import { intakeText } from './company_ui/products/visualizer/assets/authoring_data.mjs';
import { MAPPING_PRESET_ROLES, mappingFromFieldNames, mappingToFieldNames } from './company_ui/products/visualizer/assets/authoring_mapping_presets.mjs';
import { renderIntegratedElement } from './company_ui/products/visualizer/assets/element_renderer.mjs';
const intake = intakeText('X_COORD\tY_COORD\tMEASUREMENT\tLOT\tTOOL\tCHAMBER\tROUTE\n-1\t0\t98.1\tLOT-77\tETCH-04\tC2\tR1\n0\t0\t101.2\tLOT-77\tETCH-04\tC2\tR1');
const wafer = intake.recommendations.find(candidate => candidate.view === 'wafer');
const route = intake.fields.find(field => field.name === 'ROUTE');
if (!route || !wafer || wafer.mapping.route !== route.id) throw new Error('wafer intake did not infer route identity');
if (!MAPPING_PRESET_ROLES.includes('route')) throw new Error('route is not portable as a mapping role');
const roundTrip = mappingFromFieldNames(mappingToFieldNames(wafer.mapping, intake.fields), intake.fields);
if (roundTrip.route !== route.id) throw new Error('route mapping was lost during preset conversion');
const html = renderIntegratedElement({
  engine:'WaferFabEngine', element:'Wafer Map', dataset_id:'d1',
  observations:[{x:-1,y:0,value:98.1},{x:0,y:0,value:101.2}],
  fab_rows:[{'ROUTE':'R1'}], fab_fields:[{id:'route',name:'ROUTE',type:'categorical'}], fab_mapping:{route:'route'}
});
if (!html.includes('Route') || !html.includes('R1')) throw new Error('route identity was not rendered');
'''
    subprocess.run(["node", "--input-type=module", "-e", command], cwd=ROOT, check=True, capture_output=True, text=True)


def test_bound_wafer_data_dock_exposes_route_without_changing_catalog() -> None:
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    data = (ASSETS / "authoring_data.mjs").read_text(encoding="utf-8")
    assert "'route'" in editor
    assert "route:['route','routing','flow']" in data
    assert "const routeField=fieldName('route')" in (ASSETS / "element_renderer.mjs").read_text(encoding="utf-8")
    library = (ASSETS / "production_library.mjs").read_text(encoding="utf-8")
    assert library.count("'WaferFabEngine::Wafer Map'") == 1
