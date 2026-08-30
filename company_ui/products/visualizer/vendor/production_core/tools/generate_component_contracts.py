#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

HERE = Path(__file__).resolve()
PROD = HERE.parents[1]
ROOT = PROD.parent
REGISTRY = ROOT / '03_MASTER_ELEMENT_REGISTRY' / 'MASTER_ELEMENT_REGISTRY.json'
AUDIT = ROOT / '13_DEEP_AUDIT_248_ELEMENTS' / 'Visualizer_248_Element_Deep_Audit.json'
OUT = PROD / 'contracts' / 'component_contracts.json'
SCHEMA = PROD / 'contracts' / 'component_contract_schema.json'

ENGINE = {
    'SmartLayoutEngine': dict(geometry=(180,120,520,330,1200,675), variants=['smart','guided','free'], role='region', ppt='editable_grouped_shapes', data='composition constraints, semantic visual mass, output profile'),
    'MetricEngine': dict(geometry=(160,110,280,180,520,320), variants=['hero','strip','compact','comparison'], role='group', ppt='editable_text_and_shapes', data='typed numeric metric, unit, comparison baseline, status'),
    'TextEngine': dict(geometry=(180,100,360,180,900,520), variants=['title','body','callout','quote','caption'], role='group', ppt='editable_text_box', data='source-backed text, hierarchy level, provenance'),
    'ComparisonEngine': dict(geometry=(220,140,440,250,900,520), variants=['before_after','delta','side_by_side','ranked'], role='group', ppt='editable_grouped_shapes', data='typed comparable entities, dimensions, deltas, provenance'),
    'CoreChartEngine': dict(geometry=(260,180,520,320,1000,620), variants=['line','bar','area','scatter','distribution','hierarchy','flow'], role='img', ppt='native_chart_when_supported_else_editable_shapes', data='typed series, scales, encodings, eligibility result, provenance'),
    'TableEngine': dict(geometry=(260,180,620,360,1200,675), variants=['table','grouped','summary','virtualized'], role='grid', ppt='editable_table', data='typed columns, typed rows, sort/filter/aggregation state'),
    'MatrixEngine': dict(geometry=(260,200,620,420,1200,675), variants=['matrix','heatmap','pivot','quadrant'], role='grid', ppt='editable_table_and_shapes', data='typed row/column dimensions, values, aggregation, hierarchy'),
    'TimelineEngine': dict(geometry=(280,140,620,240,1200,520), variants=['milestone','gantt','sequence','dependency'], role='group', ppt='editable_timeline_shapes', data='explicit dates or sequence positions, duration, dependency type/lag, provenance'),
    'DiagramEngine': dict(geometry=(300,180,650,420,1200,675), variants=['flow','dag','network','sequence','fishbone','mindmap'], role='group', ppt='editable_shapes_and_connectors', data='semantic nodes, typed edges, graph grammar, labels, provenance'),
    'ImageMediaEngine': dict(geometry=(220,150,520,340,1000,650), variants=['image','crop','annotated','gallery','comparison'], role='img', ppt='native_image_plus_editable_annotations', data='asset identity, dimensions, crop transform, annotations, provenance'),
    'EvidenceCompositeEngine': dict(geometry=(260,160,560,340,1100,650), variants=['evidence_card','hypothesis','rca','source_panel'], role='group', ppt='editable_grouped_shapes', data='evidence ids, polarity, confidence, source provenance, state machine'),
    'DecisionCompositeEngine': dict(geometry=(240,150,520,320,1000,620), variants=['decision','risk','gate','recommendation'], role='group', ppt='editable_grouped_shapes', data='decision state, criteria, risks, confidence, provenance'),
    'ProjectCompositeEngine': dict(geometry=(260,160,580,340,1100,650), variants=['status','milestone','roadmap','plan'], role='group', ppt='editable_grouped_shapes', data='project state, milestones, ownership, explicit dates, dependencies'),
    'EngineeringChartEngine': dict(geometry=(280,190,560,360,1100,650), variants=['spc','doe','regression','distribution','capability'], role='img', ppt='native_chart_when_supported_else_editable_shapes', data='typed engineering measurements, method, assumptions, limits, reference computation'),
    'WaferFabEngine': dict(geometry=(280,220,560,500,1000,675), variants=['wafer_map','die_map','tool_chamber','route','spatial_compare'], role='img', ppt='editable_shapes_plus_native_image_boundary', data='registered wafer/die coordinates, orientation, population, tool/chamber/route keys'),
    'InteractionLayer': dict(geometry=(32,32,220,80,900,300), variants=['tooltip','filter','brush','drill','tabs','detail','hover'], role='control', ppt='flatten_selected_state_only', data='semantic interaction state referencing canonical component ids'),
    'EditorInfrastructure': dict(geometry=(32,32,320,180,1200,675), variants=['selection','resize','drag','group','layer','palette','inspector','preflight'], role='application', ppt='not_exported_editor_only', data='semantic editor commands, revision, selection ids, layout mode'),
}

required_fields = [
    'contract_version','element','category','canonical_engine','wave','status','relationship','maturity_tier',
    'golden_target','zero_error_acceptance','semantic_data','geometry','variants','typography','accessibility',
    'states','serialization','data_binding','ppt','security','qa'
]

schema = {
    '$schema':'https://json-schema.org/draft/2020-12/schema',
    '$id':'visualizer.component-contract.schema.json',
    'title':'Visualizer Golden Component Contract',
    'type':'object',
    'required': required_fields,
    'properties': {
        'contract_version': {'const':1},
        'element': {'type':'string','minLength':1}, 'category': {'type':'string','minLength':1},
        'canonical_engine': {'type':'string','enum':sorted(ENGINE)}, 'wave': {'type':'integer','minimum':1,'maximum':11},
        'status': {'type':'string','minLength':1}, 'relationship': {'type':'string','minLength':1}, 'maturity_tier': {'type':'integer','minimum':1,'maximum':4},
        'golden_target': {'type':'string','minLength':20}, 'zero_error_acceptance': {'type':'string','minLength':20},
        'semantic_data': {'type':'object','required':['required_domain_data','truth_policy','eligibility_policy']},
        'geometry': {'type':'object','required':['min','preferred','max','responsive_policy']},
        'variants': {'type':'array','minItems':1,'items':{'type':'string'}},
        'typography': {'type':'object','required':['chrome_min_px','data_min_px','body_min_px','explanatory_min_px','scale_test']},
        'accessibility': {'type':'object','required':['role','keyboard_path_required','visible_focus_required','accessible_name_required','target_policy','reduced_motion_required']},
        'states': {'type':'object','required':['empty','loading','error','stale','unauthorized']},
        'serialization': {'type':'object','required':['semantic_id_required','deterministic','browser_geometry_leakage','revision_safe_mutations']},
        'data_binding': {'type':'object','required':['typed','raw_values_preserved','provenance_required','invalid_state_preflight']},
        'ppt': {'type':'object','required':['mapping','editable_preference','smallest_boundary_flattening','safe_area_required']},
        'security': {'type':'object','required':['escape_untrusted_text','sanitize_svg_html','ai_injection_forbidden']},
        'qa': {'type':'object','required':['golden_target','zero_error_acceptance','visual_regression','property_fuzz','serialization_roundtrip']},
    },
    'additionalProperties': True,
}


def geom(profile):
    mnw,mnh,pw,ph,mxw,mxh = profile['geometry']
    return {
        'min': {'w':mnw,'h':mnh},
        'preferred': {'w':pw,'h':ph},
        'max': {'w':mxw,'h':mxh},
        'responsive_policy': 'Clamp to declared min/max; semantic representation may change before typography crosses floor; Smart mode recomposes instead of overflow.',
    }


def main():
    registry = json.loads(REGISTRY.read_text())
    audit = json.loads(AUDIT.read_text())
    audit_by_name = {r['element']:r for r in audit}
    contracts=[]
    for row in registry:
        a=audit_by_name[row['element']]
        p=ENGINE[row['canonical_engine']]
        c={
            'contract_version':1,
            'element':row['element'],'category':row['category'],'canonical_engine':row['canonical_engine'],'wave':row['wave'],
            'status':row['status'],'relationship':row['relationship'],'maturity_tier':a['maturity_tier'],
            'reference_anchors':a.get('reference_anchors',''),'known_blockers':a.get('known_blockers',''),
            'golden_target':a['golden_target'],'zero_error_acceptance':a['zero_error_acceptance'],
            'semantic_data': {
                'required_domain_data':p['data'],
                'truth_policy':'Renderer and AI may not invent raw values, dates, certainty, relationships, coordinates, or provenance.',
                'eligibility_policy':'Typed deterministic eligibility/grammar checks run before render; invalid semantics block or explicitly warn.',
            },
            'geometry':geom(p), 'variants':p['variants'],
            'typography': {'chrome_min_px':11,'data_min_px':12,'body_min_px':13,'explanatory_min_px':13,'scale_test':'80%–200% text scale with zero clipping, overlap, or hidden required content'},
            'accessibility': {'role':p['role'],'keyboard_path_required':True,'visible_focus_required':True,'accessible_name_required':True,'target_policy':{'desktop_min_px':32,'touch_min_px':44},'reduced_motion_required':True},
            'states': {
                'empty':'Named empty state preserving component identity and recovery action.',
                'loading':'Non-blocking labelled loading state; no fake data.',
                'error':'Explicit computation/data error with cause and recovery; never NaN/undefined blank UI.',
                'stale':'Staleness label preserves last known value and timestamp/provenance where available.',
                'unauthorized':'Source access state reveals no protected data and provides safe recovery guidance.',
            },
            'serialization': {'semantic_id_required':True,'deterministic':True,'browser_geometry_leakage':'Transient browser coordinates prohibited unless geometry is canonical manual-mode intent. Connector endpoint coordinates are never canonical.','revision_safe_mutations':True},
            'data_binding': {'typed':True,'raw_values_preserved':True,'provenance_required':True,'invalid_state_preflight':True},
            'ppt': {'mapping':p['ppt'],'editable_preference':True,'smallest_boundary_flattening':True,'safe_area_required':True,'exact_corporate_profile_status':'pending user-supplied sanitized corporate profile only'},
            'security': {'escape_untrusted_text':True,'sanitize_svg_html':True,'ai_injection_forbidden':True},
            'qa': {'golden_target':a['golden_target'],'zero_error_acceptance':a['zero_error_acceptance'],'visual_regression':True,'property_fuzz':True,'serialization_roundtrip':True,'audit_confidence':a.get('audit_confidence')},
        }
        contracts.append(c)
    OUT.write_text(json.dumps({'schema_version':1,'count':len(contracts),'contracts':contracts},indent=2,ensure_ascii=False)+'\n')
    SCHEMA.write_text(json.dumps(schema,indent=2)+'\n')
    print(f'wrote {len(contracts)} contracts -> {OUT}')

if __name__=='__main__': main()
