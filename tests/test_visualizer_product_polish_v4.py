from pathlib import Path
import hashlib
from company_ui.design.contrast import contrast_ratio
ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'company_ui/products/visualizer/assets'
def test_v4_polish_contracts():
 css=(ASSETS/'integrated_editor.css').read_text(); js=(ASSETS/'integrated_editor.mjs').read_text(); html=(ASSETS/'integrated_editor.html').read_text()
 assert 'max-width:1500px' in css and '.seg button{flex:0 0 auto;white-space:nowrap}' in css
 assert '@media (max-width:480px)' in css and '#previewBtn' in css and '#exportBtn' in css and '#saveBtn{display:inline-flex!important}' in css
 assert 'function mobileShell()' in js and 'if(mobileShell()){setInspector(false);setLibrary(false);}' in js
 assert 'if(ui.libraryOpen&&mobileShell())ui.inspectorOpen=false' in js and 'if(ui.inspectorOpen&&mobileShell())ui.libraryOpen=false' in js
 assert 'Caption: describe the image' in js and 'Add screenshot or mockup' in js and 'screenshot-empty' in js
 assert "(model().items.length%6)*24" in js
 assert html.count('id="previewBtn"')==1 and html.count('id="exportBtn"')==1
 assert '[data-theme="dark"] .cui-visualizer-reportbar' in css and '[data-theme="dark"] .cui-dialog-card' in css
 assert 'width:16px;height:14px;border:1.5px solid currentColor' in css
 assert '[data-library="open"] .bottom .statusline,.cui-visualizer-root[data-inspector="open"] .bottom .statusline{visibility:hidden}' in css
 connector=ROOT/'company_ui/products/visualizer/vendor/production_core/core/GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js'
 assert hashlib.sha256(connector.read_bytes()).hexdigest()=='d8ebd4378f01b7c52a7a4be57c578c22adf29b899cc08a370cf084881195343e'


def test_chg70_r1_contrast_authorities_have_aa_margin_in_both_themes():
 tokens=(ASSETS/'tokens.css').read_text()
 css=(ASSETS/'integrated_editor.css').read_text()
 assert '--viz-accent: #0064c8;' in tokens
 assert '--viz-accent: #0064c8;' not in css
 assert '--viz-r-control: 10px;' in tokens and '--viz-r-surface: 14px;' in tokens and '--viz-r-overlay: 18px;' in tokens
 assert '.cui-visualizer-reportbar { --q-primary:var(--cui-accent); }' in css
 assert '.cui-visualizer-reportbar .q-btn.bg-primary .q-btn__content' in css
 assert contrast_ratio('#0071E3','#FFFFFF') >= 4.5
 assert contrast_ratio('#0064C8','#F2F2F4') >= 4.5
 assert contrast_ratio('#5EA6FF','#18181B') >= 4.5
