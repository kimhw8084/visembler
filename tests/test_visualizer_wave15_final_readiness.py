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


def test_wave15_production_registry_is_unique_and_every_entry_renders_meaningful_content() -> None:
    audit = node_json(r"""
import {PRODUCTION_LIBRARY_COUNT, productionEntries, isProductionElement} from './company_ui/products/visualizer/assets/production_library.mjs';
import {renderIntegratedElement} from './company_ui/products/visualizer/assets/element_renderer.mjs';
const base={id:'wave15',title:'Readiness sample',showTitle:true,text:'Readiness content',value:0,target:100,
  data:[['Baseline',0],['Current',12],['Target',24]],
  observations:[{label:'One',value:0},{label:'Two',value:1},{label:'Three',value:2}],
  rows:[['Measure',0],['String zero','0'],['Intentional blank','']],
  milestones:[{label:'Start',date:'2026-01-01'},{label:'Release',date:'2026-02-01'}],
  nodes:[{id:'a',label:'Source'},{id:'b',label:'Outcome'}],
  caption:'Explain the image',alt:'Readiness image',src:'',status:'On track',showTitle:false};
const entries=productionEntries();
const rendered=entries.map(spec=>({key:`${spec.engine}::${spec.element}`, markup:renderIntegratedElement({...base,...spec})}));
console.log(JSON.stringify({count:PRODUCTION_LIBRARY_COUNT, entries, rendered,
  hidden:isProductionElement('CoreChartEngine','Bubble Plot'), legacy:renderIntegratedElement({...base,engine:'CoreChartEngine',element:'Bubble Plot'})}));
""")
    assert audit["count"] == len(audit["entries"]) == 39
    keys = [f"{entry['engine']}::{entry['element']}" for entry in audit["entries"]]
    assert len(keys) == len(set(keys)) == 39
    assert audit["hidden"] is False
    assert "<article" in audit["legacy"]  # hidden reports remain renderer-compatible
    for rendered in audit["rendered"]:
        markup = rendered["markup"]
        assert "<article" in markup and len(markup) > 120, rendered["key"]
        assert all(token not in markup for token in ("undefined", "NaN", "Infinity")), rendered["key"]


def test_wave15_engineering_and_image_outputs_are_safe_and_semantically_distinct() -> None:
    audit = node_json(r"""
import {renderIntegratedElement} from './company_ui/products/visualizer/assets/element_renderer.mjs';
const engineering=element=>renderIntegratedElement({id:element,engine:'EngineeringChartEngine',element,title:element,showTitle:false,
 observations:[{label:'1',value:0},{label:'2',value:1},{label:'3',value:2}],data:[['1',0],['2',1],['3',2]]});
const image=element=>renderIntegratedElement({id:element,engine:'ImageMediaEngine',element,title:element,showTitle:false,src:'',caption:'',alt:''});
console.log(JSON.stringify({spc:engineering('SPC Control Chart'),imr:engineering('I-MR Chart'),cusum:engineering('CUSUM Chart'),ewma:engineering('EWMA Chart'),
 image:image('Image'),caption:image('Image + Caption'),screenshot:image('Screenshot Frame')}));
""")
    for name in ("spc", "imr", "cusum", "ewma"):
        markup = audit[name]
        assert "<svg" in markup and ("<path" in markup or "<polyline" in markup), name
        assert "<polygon" not in markup and "NaN" not in markup and "Infinity" not in markup, name
    assert "Add image" in audit["image"]
    assert "Caption: describe the image" in audit["caption"]
    assert "Add screenshot or mockup" in audit["screenshot"]


def test_wave15_scalar_round_trip_and_shared_lock_eligibility_remain_exact() -> None:
    audit = node_json(r"""
import {parseCanonical,serializeCanonical} from './company_ui/products/visualizer/vendor/production_core/core/editor_store.mjs';
import {selectionActionEligibility} from './company_ui/products/visualizer/assets/authoring_selection.mjs';
const values=[0,'0','',null];
const source={schema_version:1,items:[{id:'scalar',type:'table',title:'Scalar safety',order:0,data:values}],groups:{},mode:'guided',layoutPreset:'editorial',crossFilter:null,nextId:2};
const restored=parseCanonical(serializeCanonical(source));
const model={mode:'guided',groups:{g:{items:['locked','open']}},items:[{id:'locked',locked:true,groupId:'g'},{id:'open',locked:false,groupId:'g'}]};
console.log(JSON.stringify({values:restored.items[0].data,hasMissing:Object.hasOwn(restored.items[0],'missing'),eligibility:selectionActionEligibility(model,['locked','open'])}));
""")
    assert audit["values"] == [0, "0", "", None]
    assert audit["hasMissing"] is False
    assert audit["eligibility"]["delete"] == {"enabled": True, "reason": "", "partial": True}
    assert audit["eligibility"]["group"]["reason"] == "Locked members prevent an atomic structural action"


def test_wave15_authoring_contract_keeps_accessible_exchange_and_responsive_paths() -> None:
    html = (ASSETS / "integrated_editor.html").read_text(encoding="utf-8")
    css = (ASSETS / "integrated_editor.css").read_text(encoding="utf-8")
    editor = (ASSETS / "integrated_editor.mjs").read_text(encoding="utf-8")
    assert 'role="dialog" aria-modal="true"' in html
    assert 'role="combobox"' in html and 'role="listbox"' in html
    assert 'id="zoomFit"' in html and 'aria-label="Zoom out"' in html
    assert "min-height:44px!important;" in css
    assert css.count('.cui-visualizer-root[data-library="closed"][data-inspector="closed"] .shell') == 1
    assert "exportSvgMarkup" in editor and "image/svg+xml" in editor
    assert "PowerPoint" not in html
