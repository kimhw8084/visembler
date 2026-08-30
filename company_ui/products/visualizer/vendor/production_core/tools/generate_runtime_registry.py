#!/usr/bin/env python3
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT.parent/'Visualizer_ZERO_LOSS_MASTER_HANDOFF_2026-08-26_v2'/'13_DEEP_AUDIT_248_ELEMENTS'/'Visualizer_248_Element_Deep_Audit.json'
rows=json.load(open(AUDIT))
by={}
for r in rows: by.setdefault(r['canonical_engine'],[]).append(r['element'])
if len(rows)!=248 or len({r['element'] for r in rows})!=248: raise SystemExit('registry authority not 248 unique')
js='// generated from authoritative 248-element deep audit\n'
js+='export const ELEMENTS_BY_ENGINE = Object.freeze('+json.dumps(by,indent=2)+');\n'
js+='export const ALL_ELEMENTS = Object.freeze('+json.dumps([r['element'] for r in rows],indent=2)+');\n'
js+='const ELEMENT_ENGINE = new Map(Object.entries(ELEMENTS_BY_ENGINE).flatMap(([engine,names])=>names.map(name=>[name,engine])));\n'
js+='export function engineForElement(name){const e=ELEMENT_ENGINE.get(name); if(!e) throw new Error(`Unknown Visualizer element: ${name}`); return e;}\n'
js+='export function hasElement(name){return ELEMENT_ENGINE.has(name);}\n'
js+='export const REGISTRY_COUNTS = Object.freeze({elements:ALL_ELEMENTS.length,engines:Object.keys(ELEMENTS_BY_ENGINE).length});\n'
(ROOT/'core/runtime_registry.mjs').write_text(js)
(ROOT/'contracts/runtime_registry.json').write_text(json.dumps({'elements':len(rows),'engines':len(by),'byEngine':by},indent=2)+'\n')
print(json.dumps({'pass':True,'elements':len(rows),'engines':len(by),'counts':{k:len(v) for k,v in by.items()}},indent=2))
