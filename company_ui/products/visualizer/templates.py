from __future__ import annotations

from copy import deepcopy
from typing import Any

from .domain import canonical_model

_ENGINE_TYPE = {
    'SmartLayoutEngine':'layout','TextEngine':'text','MetricEngine':'metric','ComparisonEngine':'comparison',
    'CoreChartEngine':'chart','TableEngine':'table','MatrixEngine':'matrix','TimelineEngine':'timeline',
    'DiagramEngine':'diagram','ImageMediaEngine':'image','EvidenceCompositeEngine':'evidence',
    'DecisionCompositeEngine':'decision','ProjectCompositeEngine':'project','EngineeringChartEngine':'engineering',
    'WaferFabEngine':'wafer','InteractionLayer':'interaction','EditorInfrastructure':'editor',
}

def _item(id_: str, element: str, engine: str, order: int, **extra: Any) -> dict[str, Any]:
    return {'id':id_,'type':_ENGINE_TYPE[engine],'element':element,'engine':engine,'title':element,'order':order,'weight':1.0,'locked':False,'groupId':None,'z':order+1,**extra}

BLANK_REPORT = canonical_model({'items':[],'groups':{},'mode':'guided','layoutPreset':'editorial','crossFilter':None,'nextId':1})

REPORT_TEMPLATES = {
    'executive-brief': {
        'name':'Executive Brief','description':'Leadership-ready KPI, trend, takeaway, comparison and decision starting point.',
        'model': canonical_model({'mode':'smart','layoutPreset':'executive','nextId':6,'items':[
            _item('c1','Hero KPI','MetricEngine',0,value=None,unit='',delta=None,target=None),
            _item('c2','Line Chart','CoreChartEngine',1,data=[['Period 1',None],['Period 2',None],['Period 3',None]],brush=[0,2],revealed=True),
            _item('c3','Key Takeaway','TextEngine',2,text='Summarize what changed, why it matters, and what happens next.'),
            _item('c4','Before/After KPI','ComparisonEngine',3,before=None,after=None,unit=''),
            _item('c5','Decision Needed','DecisionCompositeEngine',4,statement='Decision required',detail='Describe the recommendation and trade-offs.',status='Open'),
        ]}),
    },
    'investigation-rca': {
        'name':'Investigation / RCA','description':'Problem statement, evidence, causal analysis, timeline and corrective action.',
        'model': canonical_model({'mode':'smart','layoutPreset':'technical','nextId':6,'items':[
            _item('c1','Executive Statement','TextEngine',0,text='Define the observed issue, affected scope, and impact.'),
            _item('c2','Evidence Card','EvidenceCompositeEngine',1,statement='Evidence item',detail='Record source, observation, and implication.',status='Observed'),
            _item('c3','Fishbone','DiagramEngine',2,nodes=['Problem','Method','Machine','Material','Measurement','Environment'],edges=[]),
            _item('c4','Event Timeline','TimelineEngine',3,milestones=[{'label':'Observed','date':None},{'label':'Verified','date':None}]),
            _item('c5','Corrective Action Component','EvidenceCompositeEngine',4,statement='Corrective action',detail='Owner · due date · verification',status='Planned'),
        ]}),
    },
    'operations-review': {
        'name':'Operations Review','description':'Operational scorecard, trend, action table, risk and project status.',
        'model': canonical_model({'mode':'smart','layoutPreset':'editorial','nextId':6,'items':[
            _item('c1','Metric Strip','MetricEngine',0,metrics=[{'label':'Output','value':None},{'label':'Quality','value':None},{'label':'Cycle','value':None}]),
            _item('c2','Multi-Line','CoreChartEngine',1,data=[['W1',None],['W2',None],['W3',None],['W4',None]],brush=[0,3],revealed=True),
            _item('c3','Action Tracker','TableEngine',2,customTable={'headers':['Action','Owner','Due','Status'],'rows':[['','','','']]}),
            _item('c4','Risk Callout','DecisionCompositeEngine',3,statement='Top risk',detail='Describe exposure and mitigation.',status='Monitor'),
            _item('c5','Project Card','ProjectCompositeEngine',4,statement='Priority workstream',detail='Owner · milestone · current risk',status='Active'),
        ]}),
    },
    'wafer-fab-analysis': {
        'name':'Wafer / Fab Analysis','description':'Semiconductor spatial/process analysis with wafer, SPC, tool/chamber and evidence context.',
        'model': canonical_model({'mode':'smart','layoutPreset':'technical','nextId':6,'items':[
            _item('c1','Wafer Map','WaferFabEngine',0,observations=[],tool='',chamber='',lot='',route=''),
            _item('c2','SPC Control Chart','EngineeringChartEngine',1,observations=[],role='measurement',lower_limit=None,upper_limit=None),
            _item('c3','Tool × Chamber Matrix','WaferFabEngine',2,observations=[],tool='',chamber='',lot='',route=''),
            _item('c4','Box Plot','CoreChartEngine',3,data=[['Group A',None],['Group B',None]],brush=[0,1],revealed=True),
            _item('c5','Evidence Card','EvidenceCompositeEngine',4,statement='Engineering evidence',detail='Record provenance and interpretation.',status='Observed'),
        ]}),
    },
}

def template_model(template_id: str) -> dict[str, Any]:
    if template_id == 'blank': return deepcopy(BLANK_REPORT)
    try: return deepcopy(REPORT_TEMPLATES[template_id]['model'])
    except KeyError as exc: raise KeyError(f'unknown Visualizer template: {template_id}') from exc
