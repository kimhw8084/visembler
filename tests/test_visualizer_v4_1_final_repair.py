from pathlib import Path
import hashlib
ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'company_ui/products/visualizer/assets'
def test_v41_data_first_and_responsive_repairs():
 js=(ASSETS/'integrated_editor.mjs').read_text();css=(ASSETS/'integrated_editor.css').read_text()
 assert 'Array.isArray(validation.unresolved)' in js and 'Cannot bind this data to the selected visual.' in js
 assert 'sourceText' in js and 'textarea id="dataFirstText"' in js
 assert 'state.savedPresetId&&mappingPresets.find' in js and 'saved?`<div class="data-first-saved"' in js
 assert 'data-forget-mapping' in js and 'mappingPresets=mappingPresets.filter' in js
 assert '.data-first-recommendation>*{min-width:0;white-space:normal;overflow-wrap:anywhere}' in css
 assert '@media (min-width:481px) and (max-width:800px)' in css and '#saveBtn{display:inline-flex!important}' in css
 connector=ROOT/'company_ui/products/visualizer/vendor/production_core/core/GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js'
 assert hashlib.sha256(connector.read_bytes()).hexdigest()=='d8ebd4378f01b7c52a7a4be57c578c22adf29b899cc08a370cf084881195343e'
