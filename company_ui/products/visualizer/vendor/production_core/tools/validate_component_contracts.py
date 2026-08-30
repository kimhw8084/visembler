#!/usr/bin/env python3
from __future__ import annotations
import json,sys
from pathlib import Path
PROD=Path(__file__).resolve().parents[1]
contracts=json.loads((PROD/'contracts/component_contracts.json').read_text())['contracts']
registry=json.loads((PROD/'contracts/runtime_registry.json').read_text())['byEngine']
required=['contract_version','element','category','canonical_engine','wave','status','relationship','maturity_tier','golden_target','zero_error_acceptance','semantic_data','geometry','variants','typography','accessibility','states','serialization','data_binding','ppt','security','qa']
errors=[];names=[c.get('element') for c in contracts];reg_names=[n for vals in registry.values() for n in vals]
if len(contracts)!=248:errors.append(f'contract count={len(contracts)} expected=248')
if len(names)!=len(set(names)):errors.append('duplicate contract element names')
if len(reg_names)!=248 or len(reg_names)!=len(set(reg_names)):errors.append('runtime registry must contain 248 unique names')
if set(names)!=set(reg_names):errors.append(f'contract/runtime mismatch missing={sorted(set(reg_names)-set(names))} extra={sorted(set(names)-set(reg_names))}')
for c in contracts:
    miss=[k for k in required if k not in c]
    if miss:errors.append(f"{c.get('element')}: missing {miss}")
    if c.get('canonical_engine') not in registry or c.get('element') not in registry.get(c.get('canonical_engine'),[]):errors.append(f"{c.get('element')}: engine mismatch")
    g=c.get('geometry',{});mn=g.get('min',{});pr=g.get('preferred',{});mx=g.get('max',{})
    for axis in ('w','h'):
        vals=[mn.get(axis),pr.get(axis),mx.get(axis)]
        if any(not isinstance(v,(int,float)) or v<=0 for v in vals) or not (vals[0]<=vals[1]<=vals[2]):errors.append(f"{c.get('element')}: invalid {axis} geometry {vals}")
    ty=c.get('typography',{})
    if ty.get('chrome_min_px',0)<11 or ty.get('data_min_px',0)<12 or ty.get('body_min_px',0)<13:errors.append(f"{c.get('element')}: typography floor")
    ac=c.get('accessibility',{});tp=ac.get('target_policy',{})
    if not ac.get('accessible_name_required') or not ac.get('visible_focus_required') or tp.get('desktop_min_px',0)<32 or tp.get('touch_min_px',0)<44:errors.append(f"{c.get('element')}: accessibility contract")
    db=c.get('data_binding',{});sec=c.get('security',{});ser=c.get('serialization',{})
    if not db.get('typed') or not db.get('raw_values_preserved') or not db.get('provenance_required') or not db.get('invalid_state_preflight'):errors.append(f"{c.get('element')}: data-binding contract")
    if not sec.get('escape_untrusted_text') or not sec.get('sanitize_svg_html') or not sec.get('ai_injection_forbidden'):errors.append(f"{c.get('element')}: security contract")
    if not ser.get('deterministic') or not ser.get('semantic_id_required') or not ser.get('revision_safe_mutations'):errors.append(f"{c.get('element')}: serialization contract")
    if not c.get('ppt',{}).get('mapping'):errors.append(f"{c.get('element')}: PPT mapping missing")
report={'pass':not errors,'contracts':len(contracts),'runtimeRegistry':len(reg_names),'engines':len(registry),'errors':errors[:100]}
(PROD/'qa/component_contract_validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));sys.exit(0 if report['pass'] else 1)
