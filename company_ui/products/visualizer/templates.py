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
    name=element.lower()
    if engine=='TextEngine':
        role='report_headline' if any(token in name for token in ('executive statement','hero title','report headline')) else 'conclusion' if any(token in name for token in ('key takeaway','conclusion','next step','recommendation')) else 'narrative_interpretation' if any(token in name for token in ('narrative','interpretation')) else 'context'
    elif engine=='MetricEngine': role='hero_metric'
    elif engine=='ComparisonEngine': role='hero_metric'
    elif engine in {'CoreChartEngine','EngineeringChartEngine','WaferFabEngine'}: role='primary_analysis'
    elif engine=='TableEngine' or engine=='EvidenceCompositeEngine' or engine=='ImageMediaEngine': role='detailed_evidence'
    elif engine=='DiagramEngine': role='causal_evidence'
    elif engine=='DecisionCompositeEngine': role='decision_risk'
    elif engine in {'ProjectCompositeEngine','TimelineEngine'}: role='action_status'
    else: role='supporting_analysis'
    sections={'report_headline':('opening','Overview'),'context':('opening','Overview'),'hero_metric':('performance','Performance'),'primary_analysis':('analysis','Analysis'),'supporting_analysis':('analysis','Analysis'),'narrative_interpretation':('analysis','Analysis'),'detailed_evidence':('evidence','Evidence'),'causal_evidence':('evidence','Evidence'),'decision_risk':('decision','Decision'),'action_status':('delivery','Next steps'),'conclusion':('delivery','Next steps')}
    section_id,section_title=sections[role]
    if role=='context' and extra.get('title') and extra['title']!=element:
        extra.setdefault('showTitle',True)
    return {'id':id_,'type':_ENGINE_TYPE[engine],'element':element,'engine':engine,'title':element,'order':order,'weight':1.0,'locked':False,'groupId':None,'z':order+1,'composition_role':role,'section_id':section_id,'section_title':section_title,**extra}

BLANK_REPORT = canonical_model({'items':[],'groups':{},'mode':'guided','layoutPreset':'editorial','crossFilter':None,'nextId':1})

REPORT_TEMPLATES = {
    'executive-brief': {
        'name':'Executive Brief','description':'Leadership-ready KPI, trend, takeaway, comparison and decision starting point.',
        'model': canonical_model({'mode':'smart','layoutPreset':'executive','nextId':6,'items':[
            _item('c1','Hero KPI','MetricEngine',0,value=None,unit='',delta=None,target=None),
            _item('c2','Line Chart','CoreChartEngine',1,data=[['Period 1',None],['Period 2',None],['Period 3',None]],brush=[0,2],revealed=True),
            _item('c3','Key Takeaway','TextEngine',2,text='Summarize what changed, why it matters, and what happens next.'),
            _item('c4','Before/After KPI','ComparisonEngine',3,before=None,after=None,unit=''),
            _item('c5','Risk Callout','DecisionCompositeEngine',4,statement='Decision required',detail='Describe the recommendation and trade-offs.',status='Open'),
        ]}),
    },
    'investigation-rca': {
        'name':'Investigation / RCA','description':'Problem statement, evidence, causal analysis, timeline and corrective action.',
        'model': canonical_model({'mode':'smart','layoutPreset':'technical','nextId':6,'items':[
            _item('c1','Executive Statement','TextEngine',0,text='Define the observed issue, affected scope, and impact.'),
            _item('c2','Evidence Card','EvidenceCompositeEngine',1,statement='Evidence item',detail='Record source, observation, and implication.',status='Observed'),
            _item('c3','Process Flow','DiagramEngine',2,nodes=['Problem','Method','Machine','Material','Measurement','Environment'],edges=[]),
            _item('c4','Event Timeline','TimelineEngine',3,milestones=[{'label':'Observed','date':None},{'label':'Verified','date':None}]),
            _item('c5','Evidence Card','EvidenceCompositeEngine',4,statement='Corrective action',detail='Owner · due date · verification',status='Planned'),
        ]}),
    },
    'operations-review': {
        'name':'Operations Review','description':'Operational scorecard, trend, action table, risk and project status.',
        'model': canonical_model({'mode':'smart','layoutPreset':'editorial','nextId':6,'items':[
            _item('c1','Hero KPI','MetricEngine',0,value=None,unit='',delta=None,target=None,metrics=[{'label':'Output','value':None},{'label':'Quality','value':None},{'label':'Cycle','value':None}]),
            _item('c2','Line Chart','CoreChartEngine',1,data=[['W1',None],['W2',None],['W3',None],['W4',None]],brush=[0,3],revealed=True),
            _item('c3','Clean Table','TableEngine',2,customTable={'headers':['Action','Owner','Due','Status'],'rows':[['','','','']]}),
            _item('c4','Risk Callout','DecisionCompositeEngine',3,statement='Top risk',detail='Describe exposure and mitigation.',status='Monitor'),
            _item('c5','Project Card','ProjectCompositeEngine',4,statement='Priority workstream',detail='Owner · milestone · current risk',status='Active'),
        ]}),
    },
    'wafer-fab-analysis': {
        'name':'Wafer / Fab Analysis','description':'Semiconductor spatial/process analysis with wafer, SPC, tool/chamber and evidence context.',
        'model': canonical_model({'mode':'smart','layoutPreset':'technical','nextId':6,'items':[
            _item('c1','Wafer Map','WaferFabEngine',0,observations=[],tool='',chamber='',lot='',route=''),
            _item('c2','SPC Control Chart','EngineeringChartEngine',1,observations=[],role='measurement',lower_limit=None,upper_limit=None),
            _item('c3','Wafer Map','WaferFabEngine',2,observations=[],tool='',chamber='',lot='',route=''),
            _item('c4','Vertical Bar','CoreChartEngine',3,data=[['Group A',None],['Group B',None]],brush=[0,1],revealed=True),
            _item('c5','Evidence Card','EvidenceCompositeEngine',4,statement='Engineering evidence',detail='Record provenance and interpretation.',status='Observed'),
        ]}),
    },
    'yield-loss-investigation': {
        'name':'Yield Loss Investigation','description':'A structured loss story from headline yield through Pareto, evidence, and corrective action.',
        'model': canonical_model({'mode':'smart','layoutPreset':'technical','nextId':8,'items':[
            _item('c1','Hero KPI','MetricEngine',0,value=None,unit='%',delta=None,target=None,title='Yield'),
            _item('c2','Pareto','CoreChartEngine',1,data=[],mapping={},showTitle=True,title='Yield loss contributors'),
            _item('c3','Clean Table','TableEngine',2,customTable={'headers':['Cause','Loss','Owner','Status'],'rows':[['','','','']]}),
            _item('c4','Wafer Map','WaferFabEngine',3,observations=[],showTitle=True,title='Spatial evidence'),
            _item('c5','Key Takeaway','TextEngine',4,text='State the dominant contributor, affected scope, and next decision.'),
            _item('c6','Evidence Card','EvidenceCompositeEngine',5,statement='Containment / corrective action',detail='Owner · due date · verification evidence',status='Planned'),
        ]}),
    },
    'spc-excursion-review': {
        'name':'SPC Excursion Review','description':'Ordered measurement review with control context, excursion evidence, and disposition.',
        'model': canonical_model({'mode':'smart','layoutPreset':'technical','nextId':7,'items':[
            _item('c1','Executive Statement','TextEngine',0,text='Define the excursion, affected process window, and current disposition.'),
            _item('c2','SPC Control Chart','EngineeringChartEngine',1,observations=[],lower_limit=None,upper_limit=None,showTitle=True,title='Process behavior'),
            _item('c3','Clean Table','TableEngine',2,customTable={'headers':['Time','Measurement','Tool','Chamber','Disposition'],'rows':[['','','','','']]}),
            _item('c4','Event Timeline','TimelineEngine',3,milestones=[{'label':'Excursion','date':None},{'label':'Containment','date':None},{'label':'Verification','date':None}]),
            _item('c5','Risk Callout','DecisionCompositeEngine',4,statement='Disposition decision',detail='Record evidence, risk, and approval needed.',status='Open'),
        ]}),
    },
    'tool-chamber-matching': {
        'name':'Tool / Chamber Matching','description':'Compare equipment contexts, rank meaningful differences, and capture the engineering conclusion.',
        'model': canonical_model({'mode':'smart','layoutPreset':'technical','nextId':7,'items':[
            _item('c1','Hero KPI','MetricEngine',0,value=None,unit='',delta=None,target=None,title='Matched metric'),
            _item('c2','Horizontal Bar','CoreChartEngine',1,data=[],mapping={},showTitle=True,title='Tool / chamber comparison'),
            _item('c3','Clean Table','TableEngine',2,customTable={'headers':['Tool','Chamber','Metric','Count','Disposition'],'rows':[['','','','','']]}),
            _item('c4','Scatter Plot','CoreChartEngine',3,data=[],mapping={},showTitle=True,title='Relationship check'),
            _item('c5','Key Takeaway','TextEngine',4,text='Explain the strongest equipment difference and the next validation step.'),
        ]}),
    },
    'golden-vs-affected': {
        'name':'Golden vs Affected','description':'Reference-versus-affected evidence with aligned trend, delta context, and action narrative.',
        'model': canonical_model({'mode':'smart','layoutPreset':'technical','nextId':7,'items':[
            _item('c1','Before/After KPI','ComparisonEngine',0,before=None,after=None,unit='',title='Reference vs affected'),
            _item('c2','Multi-Line','CoreChartEngine',1,data=[],mapping={},showTitle=True,title='Golden / affected profile'),
            _item('c3','Clean Table','TableEngine',2,customTable={'headers':['Position','Golden','Affected','Delta'],'rows':[['','','','']]}),
            _item('c4','Evidence Card','EvidenceCompositeEngine',3,statement='Divergence evidence',detail='Record aligned position, magnitude, and source.',status='Observed'),
            _item('c5','Executive Statement','TextEngine',4,text='Summarize where the affected population diverges and what should happen next.'),
        ]}),
    },
    'executive-business-review': {
        'name':'Executive Business Review','description':'A complete leadership narrative from context and KPI hierarchy through evidence, decision, and next step.',
        'model': canonical_model({'mode':'smart','layoutPreset':'executive','nextId':10,'items':[
            _item('c1','Executive Statement','TextEngine',0,text='Revenue recovery is on plan, with retention remaining the key exposure.',composition_role='report_headline',section_id='opening',section_title='Executive summary'),
            _item('c2','Body Narrative','TextEngine',1,title='Quarterly context',text='Quarterly business review · regional performance through Q3.',composition_role='context',section_id='opening',section_title='Executive summary'),
            _item('c3','Hero KPI','MetricEngine',2,value=None,unit='%',delta=None,target=None,title='Retention'),
            _item('c4','Hero KPI','MetricEngine',3,value=None,unit='%',delta=None,target=None,title='Recurring revenue',emphasis='prominent'),
            _item('c5','Before/After KPI','ComparisonEngine',4,before=None,after=None,unit='%',title='Quarter over quarter'),
            _item('c6','Line Chart','CoreChartEngine',5,data=[],mapping={},showTitle=True,title='Quarterly retention'),
            _item('c7','Clean Table','TableEngine',6,customTable={'headers':['Region','Revenue','Retention','Status'],'rows':[]},composition_role='detailed_evidence',section_id='evidence',section_title='Regional evidence'),
            _item('c8','Risk Callout','DecisionCompositeEngine',7,statement='Decision required',detail='Summarize the exposure, option, and trade-off.',status='Open'),
            _item('c9','Key Takeaway','TextEngine',8,text='State the decision and one concrete next step.',composition_role='conclusion',section_id='delivery',section_title='Decision and next step'),
        ]}),
    },
    'semiconductor-rca': {
        'name':'Semiconductor RCA','description':'A complete engineering investigation with spatial evidence, distributions, causal flow, findings, and corrective action.',
        'model': canonical_model({'mode':'smart','layoutPreset':'investigation','nextId':12,'items':[
            _item('c1','Executive Statement','TextEngine',0,text='A localized yield excursion follows etch chamber drift on the affected lot.',composition_role='report_headline',section_id='opening',section_title='Investigation summary'),
            _item('c2','Body Narrative','TextEngine',1,title='Affected scope',text='Define the affected product, lot, tool, chamber, route, and decision window.',composition_role='context',section_id='opening',section_title='Investigation summary'),
            _item('c3','Hero KPI','MetricEngine',2,value=None,unit='%',delta=None,target=None,title='Affected yield'),
            _item('c11','Before/After KPI','ComparisonEngine',3,before=None,after=None,unit='%',title='Affected versus reference yield'),
            _item('c4','Wafer Map','WaferFabEngine',3,observations=[],tool='',chamber='',lot='',route='',title='Affected die yield'),
            _item('c5','SPC Control Chart','EngineeringChartEngine',4,observations=[],lower_limit=None,upper_limit=None,title='Process stability and specification'),
            _item('c6','Box Plot','CoreChartEngine',5,data=[],mapping={},showTitle=True,title='Control versus affected distribution'),
            _item('c7','Clean Table','TableEngine',6,customTable={'headers':['Evidence','Affected','Reference','Interpretation'],'rows':[]},composition_role='detailed_evidence',section_id='evidence',section_title='Engineering evidence'),
            _item('c8','Process Flow','DiagramEngine',7,nodes=['Excursion signal','Compare affected and reference','Verify chamber mechanism','Confirm corrective action'],edges=[['Excursion signal','Compare affected and reference'],['Compare affected and reference','Verify chamber mechanism'],['Verify chamber mechanism','Confirm corrective action']],composition_role='causal_evidence',section_id='evidence',section_title='Causal analysis'),
            _item('c9','Evidence Card','EvidenceCompositeEngine',8,statement='Finding · chamber condition is consistent with the excursion onset.',detail='Record the measurement, population, source, and engineering implication.',status='Verified',composition_role='narrative_interpretation',section_id='analysis',section_title='Findings'),
            _item('c10','Project Card','ProjectCompositeEngine',9,title='Corrective action',statement='Requalify chamber and verify the matched reference lot.',detail='Owner: Process Engineering · verify before production release.',status='Planned',composition_role='action_status',section_id='delivery',section_title='Corrective action'),
        ]}),
    },
    'experiment-decision': {
        'name':'Experiment Decision','description':'Hypothesis, measured results, comparisons, distributions, evidence, interpretation, and a decision recommendation.',
        'model': canonical_model({'mode':'smart','layoutPreset':'comparison','nextId':10,'items':[
            _item('c1','Executive Statement','TextEngine',0,text='The treatment improves conversion without increasing defect rate.',composition_role='report_headline',section_id='opening',section_title='Experiment summary'),
            _item('c2','Body Narrative','TextEngine',1,title='Hypothesis and context',text='Hypothesis: the revised onboarding flow increases qualified conversion. Population: eligible new accounts randomized by cohort.',composition_role='context',section_id='opening',section_title='Experiment design'),
            _item('c3','Hero KPI','MetricEngine',2,value=None,unit='%',delta=None,target=None,title='Treatment conversion'),
            _item('c4','Before/After KPI','ComparisonEngine',3,before=None,after=None,unit='%',title='Control versus treatment'),
            _item('c5','Box Plot','CoreChartEngine',4,data=[],mapping={},showTitle=True,title='Outcome distribution by cohort',composition_role='supporting_analysis',section_id='analysis',section_title='Analysis'),
            _item('c6','Line Chart','CoreChartEngine',5,data=[],mapping={},showTitle=True,title='Conversion by week'),
            _item('c7','Clean Table','TableEngine',6,customTable={'headers':['Cohort','Eligible','Converted','Guardrail'],'rows':[]},composition_role='detailed_evidence',section_id='evidence',section_title='Experiment evidence'),
            _item('c8','Body Narrative','TextEngine',7,title='Interpretation',text='Explain the primary effect, uncertainty, guardrail results, and limits of the experiment.',composition_role='narrative_interpretation',section_id='analysis',section_title='Interpretation'),
            _item('c9','Risk Callout','DecisionCompositeEngine',8,title='Recommendation',statement='Recommend a staged rollout',detail='Proceed only while the quality guardrail remains within the agreed band.',status='Review',composition_role='decision_risk',section_id='decision',section_title='Recommendation'),
        ]}),
    },
    'technical-status-review': {
        'name':'Technical Status Review','description':'A dense but ordered operating report with repeated KPIs, trends, engineering evidence, risk, and action ownership.',
        'model': canonical_model({'mode':'smart','layoutPreset':'technical','nextId':13,'items':[
            _item('c1','Executive Statement','TextEngine',0,text='Line 4 is stable; two open items remain before the next capacity release.',composition_role='report_headline',section_id='opening',section_title='Operating summary'),
            _item('c2','Body Narrative','TextEngine',1,title='Report context',text='Daily technical review · Line 4 · shift B · report window 06:00–18:00.',composition_role='context',section_id='opening',section_title='Operating summary'),
            _item('c3','Hero KPI','MetricEngine',2,value=None,unit='%',delta=None,target=None,title='First pass yield'),
            _item('c4','Hero KPI','MetricEngine',3,value=None,unit='h',delta=None,target=None,title='Unplanned downtime'),
            _item('c5','Line Chart','CoreChartEngine',4,data=[],mapping={},showTitle=True,title='Yield by shift'),
            _item('c6','SPC Control Chart','EngineeringChartEngine',5,observations=[],lower_limit=None,upper_limit=None,title='Critical measurement trend'),
            _item('c7','Clean Table','TableEngine',6,customTable={'headers':['Tool','Chamber','Measure','Owner','Status'],'rows':[]},composition_role='detailed_evidence',section_id='evidence',section_title='Operating evidence'),
            _item('c8','Process Flow','DiagramEngine',7,nodes=['Detect','Contain','Verify','Release'],edges=[['Detect','Contain'],['Contain','Verify'],['Verify','Release']],composition_role='causal_evidence',section_id='evidence',section_title='Response workflow'),
            _item('c9','Evidence Card','EvidenceCompositeEngine',8,statement='Measurement system remains within the qualified reference range.',detail='Sample: 30 parts · method: inline metrology · source: shift B inspection.',status='Verified',composition_role='detailed_evidence',section_id='evidence',section_title='Operating evidence'),
            _item('c10','Risk Callout','DecisionCompositeEngine',9,statement='Capacity release depends on a repeat chamber check.',detail='Current exposure is bounded to one tool; no customer shipment impact is confirmed.',status='Watch'),
            _item('c11','Project Card','ProjectCompositeEngine',10,statement='Complete chamber verification and update the runbook.',detail='Owner: Equipment Engineering · due next shift · evidence: paired control lot.',status='Active'),
            _item('c12','Body Narrative','TextEngine',11,text='The overnight maintenance sequence restored the chamber pressure trend. The shift B control sample confirms stability across the critical measurement window. Keep the revised recipe locked until the next paired-lot check is complete. Share the result with Quality, Operations, and Equipment Engineering before releasing the additional capacity.',composition_role='narrative_interpretation',section_id='analysis',section_title='Shift interpretation'),
        ]}),
    },
}

def template_model(template_id: str) -> dict[str, Any]:
    if template_id == 'blank': return deepcopy(BLANK_REPORT)
    try: return deepcopy(REPORT_TEMPLATES[template_id]['model'])
    except KeyError as exc: raise KeyError(f'unknown Visualizer template: {template_id}') from exc
