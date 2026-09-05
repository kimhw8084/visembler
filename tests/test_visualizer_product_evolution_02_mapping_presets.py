from __future__ import annotations
import hashlib, json, subprocess
from pathlib import Path
from company_ui.products.visualizer.page import _normalize_mapping_presets, _decode_bridge_event

ROOT=Path(__file__).resolve().parents[1]

def node(source):
    return json.loads(subprocess.run(['node','--input-type=module','-e',source],cwd=ROOT,text=True,capture_output=True,check=True).stdout)

def test_mapping_preset_pure_matching_is_order_safe_and_production_safe():
    value=node(r'''
import {intakeText} from './company_ui/products/visualizer/assets/authoring_data.mjs';
import {normalizedFieldName,mappingSchemaSignature,mappingToFieldNames,mappingFromFieldNames,matchingMappingPresets,hasUniqueNormalizedFields} from './company_ui/products/visualizer/assets/authoring_mapping_presets.mjs';
const a=intakeText('LOT\tX_COORD\tY_COORD\tMEASURE\nL1\t1\t1\t98.2'), b=intakeText('MEASURE\tY_COORD\tLOT\tX_COORD\n98.2\t1\tL1\t1');
const mapping={lot_id:a.fields[0].id,die_x:a.fields[1].id,die_y:a.fields[2].id,value:a.fields[3].id};
const saved={id:'mapping-wafer',name:'Wafer',version:1,view:'wafer',schema:{signature:mappingSchemaSignature(a.fields)},mapping:mappingToFieldNames(mapping,a.fields)};
console.log(JSON.stringify({signature:[mappingSchemaSignature(a.fields),mappingSchemaSignature(b.fields)],names:mappingToFieldNames(mapping,a.fields),restored:mappingFromFieldNames(saved.mapping,b.fields),matches:matchingMappingPresets([saved],b),extra:matchingMappingPresets([saved],intakeText('MEASURE\tY_COORD\tLOT\tX_COORD\tTOOL\n98\t1\tL1\t1\tE')),duplicate:hasUniqueNormalizedFields([{name:'Lot'},{name:'LOT'}]),norm:normalizedFieldName(' Die X / Coord ')}));
''')
    assert value['signature'][0]==value['signature'][1]
    assert value['restored']['die_x'].startswith('x_coord') and len(value['matches'])==1
    assert value['extra']==[] and value['duplicate'] is False and value['norm']=='die_x_coord'

def test_mapping_preset_server_normalizer_and_bridge_are_bounded():
    raw=[{'version':1,'id':'mapping-1','name':' Wafer yield ','view':'wafer','schema':{'fields':['die_y','yield_pct','die_x','wafer_id']},'mapping':{'die_x':'die_x','die_y':'die_y','value':'yield_pct','wafer_id':'wafer_id'},'rows':[1]}]
    presets=_normalize_mapping_presets(raw)
    assert presets[0]['schema']['fields']==['die_x','die_y','wafer_id','yield_pct'] and 'rows' not in presets[0]
    assert _normalize_mapping_presets([{'id':'x','name':'bad','view':'scatter','schema':{'fields':['x','y']},'mapping':{'x':'x'}}])==[]
    assert _decode_bridge_event({'bridge_version':1,'type':'mapping.preferences_requested','payload':{}})['type']=='mapping.preferences_requested'

def test_mapping_preset_editor_and_connector_contracts():
    editor=(ROOT/'company_ui/products/visualizer/assets/integrated_editor.mjs').read_text()
    assert 'mapping.preferences_requested' in editor and 'Using saved mapping' in editor and 'Forget mapping' in editor
    connector=ROOT/'company_ui/products/visualizer/vendor/production_core/core/GOLDEN_CONNECTOR_ENGINE_V5_FROZEN.js'
    assert hashlib.sha256(connector.read_bytes()).hexdigest()=='d8ebd4378f01b7c52a7a4be57c578c22adf29b899cc08a370cf084881195343e'
