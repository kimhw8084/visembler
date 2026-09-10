from __future__ import annotations

import base64
import csv
import hashlib
import inspect
import io
import json
import math
import os
import uuid
from html import escape as html_escape
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, quote

from fastapi import HTTPException, Request

from company_ui.integrations.nicegui_components import FileUpload
from company_ui.integrations.nicegui_layout import AppShell
from company_ui.integrations.nicegui_state import NiceGUIStateServices
from company_ui.layouts.models import SidebarMode
from company_ui.navigation import NavItem, NavigationModel, NavSection
from company_ui.data_engine import DataQuery, FilterClause, FilterOperation, SortClause

from .domain import BRIDGE_MAX_BYTES, MODEL_MAX_BYTES, ReportNotFoundError, RevisionConflictError, VisualizerContractError, canonical_model, stable_json
from .files import PPT_MAX_BYTES, validate_image_bytes, validate_pptx_bytes
from .governance import REPORT_EDIT, REPORT_EXPORT, REPORT_READ, REPORT_SHARE, ReportAccessCatalog, ReportRole, ScopedReportRepository
from .dataset_resources import DatasetResourceStore, ScopedDatasetRepository
from .ppt_service import export_pptx, import_visembler_pptx
from .repository import ReportRepository
from .runtime import NiceGUIRuntimeAdapter
from .statistical_analysis import analyze_statistical_items, require_valid_statistical_results
from .templates import REPORT_TEMPLATES, template_model

PRODUCT = Path(__file__).resolve().parent
ASSETS = PRODUCT / 'assets'
VENDOR = PRODUCT / 'vendor' / 'production_core'
STATIC_ROUTE = '/_cui_visualizer'
BRIDGE_VERSION = 1
PRESET_KEY = 'visualizer.personal_presets'
MAPPING_PRESET_KEY = 'visualizer.data_mapping_presets'
REUSE_KEY = 'visualizer.reusable_library'
MAX_PRESETS = 50
MAX_PRESET_BYTES = 1_500_000
MAX_MAPPING_PRESET_BYTES = 100_000
MAX_REUSE_RECORDS = 100
MAX_REUSE_BYTES = 1_000_000
_ALLOWED_EVENTS = {
    'report.commit','report.save_requested','preset.preferences_requested','preset.preferences_save_requested','mapping.preferences_requested','mapping.preferences_save_requested',
    'ppt.export_requested','dataset.binding_requested','dataset.filter_requested','dataset.filters_requested','dataset.reset_requested','dataset.export_requested','dataset.resource_requested','dataset.resource_refresh_requested','reuse.preferences_requested','reuse.preferences_save_requested','report.history_requested',
}
_MAPPING_VIEWS={'bar','line','table','timeline','diagram','diagram_flow','engineering','wafer','wafer_difference','tool_chamber_matrix','golden_affected_profile','control_affected_distribution'}
_MAPPING_ROLES={'category','value','x','y','series','time','source','target','weight','subgroup','cohort','reference_value','affected_value','delta','specification_low','specification_high','lower_limit','upper_limit','die_x','die_y','wafer_id','lot_id','tool','chamber','recipe','process','product','bin','label','size','color','tooltip'}


def _safe_download_stem(value: Any, fallback: str = 'visembler-dataset') -> str:
    stem = ''.join(character if character.isalnum() or character in '-_' else '-' for character in str(value or '').strip()).strip('-_')
    return (stem[:96] or fallback)


def _dataset_export_bytes(fields: list[Mapping[str, Any]], rows: list[Mapping[str, Any]], *, delimiter: str) -> bytes:
    output = io.StringIO(newline='')
    writer = csv.writer(output, delimiter=delimiter, lineterminator='\n', quoting=csv.QUOTE_MINIMAL)
    field_ids = [str(field.get('id') or '') for field in fields]
    writer.writerow([str(field.get('name') or field_id) for field, field_id in zip(fields, field_ids)])
    for row in rows:
        writer.writerow([row.get(field_id) for field_id in field_ids])
    return output.getvalue().encode('utf-8')

def _normalized_mapping_field(value: Any) -> str:
    import re
    return re.sub(r'^_+|_+$','',re.sub(r'[^a-z0-9]+','_',str(value or '').strip().lower()))

def _normalize_mapping_presets(raw: Any) -> list[dict[str,Any]]:
    if not isinstance(raw,list): return []
    output=[]
    for value in raw[:MAX_PRESETS]:
        if not isinstance(value,Mapping) or value.get('version',1)!=1: continue
        ident=''.join(ch for ch in str(value.get('id','')) if ch.isalnum() or ch in '-_')[:96]
        name=' '.join(str(value.get('name','')).split())[:80]
        view=str(value.get('view','')).strip().lower(); schema=value.get('schema'); mapping=value.get('mapping')
        if not ident or not name or view not in _MAPPING_VIEWS or not isinstance(schema,Mapping) or not isinstance(mapping,Mapping): continue
        fields=sorted({_normalized_mapping_field(field) for field in schema.get('fields',[]) if _normalized_mapping_field(field)})
        if not fields or len(fields)!=len(schema.get('fields',[])): continue
        clean={role:_normalized_mapping_field(field) for role,field in mapping.items() if role in _MAPPING_ROLES and _normalized_mapping_field(field) in fields}
        if not clean: continue
        output.append({'version':1,'id':ident,'name':name,'schema':{'fields':fields,'signature':'|'.join(fields)},'view':'diagram' if view=='diagram_flow' else view,'mapping':clean})
    encoded=stable_json(output).encode('utf-8')
    return output if len(encoded)<=MAX_MAPPING_PRESET_BYTES else []

def _normalize_reuse_records(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list): return []
    output=[]
    for value in raw[:MAX_REUSE_RECORDS]:
        if not isinstance(value, Mapping): continue
        ident=''.join(ch for ch in str(value.get('id') or '') if ch.isalnum() or ch in '-_')[:96]
        name=' '.join(str(value.get('name') or '').replace('\x00','').split())[:120]
        kind=' '.join(str(value.get('type') or 'reusable asset').replace('\x00','').split())[:80]
        version=value.get('version',1)
        if not ident or not name or not kind or isinstance(version,bool) or not isinstance(version,int) or version<1: continue
        output.append({**json.loads(stable_json(value)),'id':ident,'name':name,'type':kind,'version':version})
    if len(stable_json(output).encode('utf-8'))>MAX_REUSE_BYTES: raise VisualizerContractError('Reusable library exceeds the configured storage limit')
    return output
NAVIGATION = NavigationModel((NavSection('workspace','Workspace',(NavItem('visualizer','Visembler','/visualizer','chart-line'),NavItem('visualizer-reports','Reports','/visualizer/reports','folder'))),))


class _VisualizerResourceBoundary:
    """Reject protected Visualizer HTTP requests before NiceGUI renders a page.

    NiceGUI can turn an exception raised while constructing a ``ui.page`` into
    an HTML error surface with a 200 response on a subsequent client request.
    That is unsuitable for protected report URLs: the transport boundary must
    remain an opaque 404 before a page/client is created.  This middleware
    reuses the configured Company UI authentication adapter and the same
    scoped repository used by the page handlers; it does not create a second
    authorization model.
    """

    def __init__(self, app: Any, *, auth_adapter: Any, repository: ReportRepository,
                 access: ReportAccessCatalog, authorization: Any) -> None:
        self.app = app
        self.auth_adapter = auth_adapter
        self.repository = repository
        self.access = access
        self.authorization = authorization

    async def __call__(self, scope: Mapping[str, Any], receive: Any, send: Any) -> None:
        if scope.get('type') != 'http' or not str(scope.get('path') or '').startswith('/visualizer'):
            await self.app(scope, receive, send)
            return
        headers = {key.decode('latin-1').lower(): value.decode('latin-1') for key, value in scope.get('headers', [])}
        client = scope.get('client')
        client_host = client[0] if client else None
        principal = await self.auth_adapter.authenticate(headers, client_host) if self.auth_adapter is not None else None
        report_id = parse_qs(bytes(scope.get('query_string') or b'').decode('latin-1')).get('report', [''])[0].strip()
        denied = principal is None or not principal.authenticated
        if not denied and report_id:
            scoped = ScopedReportRepository(self.repository, self.access, principal, self.authorization)
            try:
                scoped.get(report_id)
            except (PermissionError, ReportNotFoundError, ValueError):
                denied = True
        if denied:
            from starlette.responses import PlainTextResponse
            await PlainTextResponse('Not found', status_code=404)(scope, receive, send)
            return
        await self.app(scope, receive, send)


def _asset_build() -> str:
    h=hashlib.sha256()
    asset_names=('tokens.css','integrated_editor.css','integrated_editor.html','diagram_studio.html','diagram_studio.css','chart_studio.html','chart_studio.css','authoring_contracts.mjs','authoring_data.mjs','analysis_semantics.mjs','engineering_recipes.mjs','authoring_mapping_presets.mjs','authoring_dataset_refresh.mjs','authoring_portability.mjs','authoring_intake_client.mjs','authoring_values.mjs','authoring_format.mjs','authoring_selection.mjs','authoring_arrange.mjs','authoring_clipboard.mjs','authoring_reuse.mjs','authoring_presets.mjs','authoring_style.mjs','authoring_batch.mjs','authoring_data_worker.mjs','authoring_transforms.mjs','authoring_performance.mjs','authoring_geometry.mjs','authoring_grid.mjs','production_library.mjs','element_renderer.mjs','authoring_diagram_studio.mjs','diagram_studio.mjs','authoring_chart_studio.mjs','chart_studio.mjs','authoring_stage_d.mjs','integrated_editor.mjs')
    paths=[ASSETS/name for name in asset_names]
    paths.extend(sorted((VENDOR/'core').glob('*.mjs')))
    for path in paths:
        h.update(path.relative_to(PRODUCT).as_posix().encode())
        h.update(path.read_bytes())
    return h.hexdigest()[:16]


def _bootstrap_editor(ui: Any, bootstrap: Mapping[str, Any], build: str, module_url: str, *, capabilities: Mapping[str, Any] | None = None) -> None:
    browser_bootstrap=dict(bootstrap)
    if capabilities is not None: browser_bootstrap['capabilities']=dict(capabilities)
    script=f'''window.__CUI_VISUALIZER_BOOTSTRAP__={json.dumps(browser_bootstrap,ensure_ascii=False)};window.__CUI_VISUALIZER_ASSET_BUILD__={json.dumps(build)};import({json.dumps(module_url)}).catch(error=>{{console.error(error);const root=document.querySelector('.cui-visualizer-root');if(root)root.dataset.editorReady='failed';}});'''
    ui.run_javascript(script)


def _payload(record, asset_url: Any=None, model_override: Mapping[str, Any] | None=None) -> dict[str, Any]:
    model=model_override if model_override is not None else record.model
    if asset_url:
        model=json.loads(stable_json(model))
        for entry in model.get('items',[]):
            if isinstance(entry,Mapping) and entry.get('engine')=='ImageMediaEngine' and entry.get('asset_id'):
                entry['src']=asset_url(str(entry['asset_id']))
    return {'report_id':record.report_id,'revision':record.revision,'title':record.title,'model':model,'fingerprint':record.to_dict()['fingerprint']}


def _decode_bridge_event(event: Any) -> Mapping[str, Any]:
    value=event
    args=getattr(event,'args',None)
    if args is not None:
        if isinstance(args,Mapping): value=args.get('detail',args)
        elif isinstance(args,(list,tuple)) and args: value=args[0]
        else: value=args
    if isinstance(value,Mapping) and 'detail' in value and len(value)==1: value=value['detail']
    if isinstance(value,bytes): value=value.decode('utf-8','strict')
    if isinstance(value,str):
        if len(value.encode('utf-8'))>BRIDGE_MAX_BYTES: raise VisualizerContractError('bridge message exceeds size limit')
        value=json.loads(value)
    if not isinstance(value,Mapping): raise VisualizerContractError('bridge message must be an object')
    if len(stable_json(value).encode('utf-8'))>BRIDGE_MAX_BYTES: raise VisualizerContractError('bridge message exceeds size limit')
    if value.get('bridge_version') != BRIDGE_VERSION: raise VisualizerContractError('unsupported bridge version')
    kind=value.get('type')
    if kind not in _ALLOWED_EVENTS: raise VisualizerContractError(f'unsupported bridge event: {kind!r}')
    payload=value.get('payload',{})
    if not isinstance(payload,Mapping): raise VisualizerContractError('bridge payload must be an object')
    return {'type':kind,'payload':payload}


def _validate_model_images(model: Mapping[str, Any]) -> None:
    for entry in model.get('items',[]):
        if not isinstance(entry,Mapping) or entry.get('engine') != 'ImageMediaEngine': continue
        if entry.get('asset_id'): continue
        src=entry.get('src')
        if src in (None,''): continue
        if not isinstance(src,str) or not src.startswith('data:') or ';base64,' not in src:
            raise VisualizerContractError(f'image {entry.get("id","?")} must use an embedded validated data URL')
        header,encoded=src.split(',',1)
        if header not in {'data:image/png;base64','data:image/jpeg;base64','data:image/webp;base64'}:
            raise VisualizerContractError('only embedded PNG, JPEG, or WebP images are supported')
        try: payload=base64.b64decode(encoded,validate=True)
        except Exception as exc: raise VisualizerContractError('embedded image base64 is invalid') from exc
        validate_image_bytes(payload)


def _normalize_section_preset_payload(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise VisualizerContractError('section preset payload must be an object')
    if raw.get('kind') != 'composition':
        raise VisualizerContractError('section preset payload must be a composition')
    items = raw.get('items')
    groups = raw.get('groups', [])
    datasets = raw.get('datasets', [])
    if not isinstance(items, list) or len(items) < 2 or not all(isinstance(item, Mapping) for item in items):
        raise VisualizerContractError('section preset requires at least two elements')
    if not isinstance(groups, list) or not all(isinstance(group, Mapping) for group in groups):
        raise VisualizerContractError('section preset groups must be a list of objects')
    if not isinstance(datasets, list) or not all(isinstance(dataset, Mapping) for dataset in datasets):
        raise VisualizerContractError('section preset datasets must be a list of objects')

    # Deterministic JSON-only clone preserving 0, "0", null, and "" exactly.
    payload = json.loads(stable_json(raw))
    payload['kind'] = 'composition'
    _validate_model_images({'items': payload['items']})
    return payload


def _normalize_presets(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw,list): raise VisualizerContractError('presets must be a list')
    result=[]; total=0
    for entry in raw[:MAX_PRESETS]:
        if not isinstance(entry,Mapping): continue
        name=' '.join(str(entry.get('name') or '').replace('\x00','').split())[:80]
        if not name: continue
        preset_id=str(entry.get('id') or uuid.uuid4().hex)[:160]
        try:
            if entry.get('kind') == 'section':
                payload=_normalize_section_preset_payload(entry.get('payload'))
                preset={'id':preset_id,'name':name,'kind':'section','payload':payload}
            else:
                model=entry.get('model')
                if not isinstance(model,Mapping): continue
                canonical=canonical_model(model); _validate_model_images(canonical)
                # Preserve the legacy server shape for whole-report presets.
                preset={'id':preset_id,'name':name,'model':canonical}
        except Exception:
            continue
        total += len(stable_json(preset).encode('utf-8'))
        if total > MAX_PRESET_BYTES: break
        result.append(preset)
    return result


async def _read_upload(event: Any, *, max_bytes: int) -> tuple[str, bytes]:
    file_obj=getattr(event,'file',None)
    name=str(getattr(file_obj,'name',None) or getattr(event,'name',None) or getattr(event,'filename',None) or 'upload')
    source=getattr(file_obj,'content',None) or getattr(event,'content',None) or file_obj
    size=getattr(source,'size',None)
    if callable(size):
        try: reported=size()
        except Exception: reported=None
        if isinstance(reported,int) and not isinstance(reported,bool) and reported>max_bytes:
            raise VisualizerContractError(f'upload exceeds {max_bytes} bytes')
    reader=getattr(source,'read',None)
    if reader is None: raise VisualizerContractError('upload content is unavailable')
    value=reader()
    if inspect.isawaitable(value): value=await value
    if isinstance(value,str): value=value.encode()
    if not isinstance(value,(bytes,bytearray)): raise VisualizerContractError('upload did not provide bytes')
    payload=bytes(value)
    if len(payload)>max_bytes: raise VisualizerContractError(f'upload exceeds {max_bytes} bytes')
    return Path(name).name,payload


def _report_options(repository: ReportRepository, query: str='', sort: str='modified') -> dict[str,str]:
    # Preserve the report-selector contract while reading governed summaries:
    # label='New blank report' if record.title=='Untitled report' and blank else record.title
    # and record.report_id[-6:] remain the disambiguation rules.
    needle=' '.join(str(query).split()).casefold(); records=repository.list_summaries()
    if sort=='title': records=sorted(records,key=lambda record:(str(record.get('title') or '').casefold(),str(record.get('report_id') or '')))
    elif sort=='created': records=sorted(records,key=lambda record:(str(record.get('created_at') or ''),str(record.get('report_id') or '')),reverse=True)
    counts:dict[str,int]={}
    for record in records:
        blank=not record.get('item_count') and not record.get('group_count')
        title=str(record.get('title') or 'Untitled report')
        label='New blank report' if title=='Untitled report' and blank else title
        counts[label]=counts.get(label,0)+1
    result={}
    for record in records:
        blank=not record.get('item_count') and not record.get('group_count'); report_id=str(record.get('report_id') or '')
        title=str(record.get('title') or 'Untitled report'); label='New blank report' if title=='Untitled report' and blank else title
        description=str(record.get('description') or '')
        if needle and needle not in label.casefold() and needle not in report_id.casefold() and needle not in description.casefold(): continue
        if counts[label]>1:
            label=f'{label}{" · blank" if blank else ""} · {report_id[-6:]}'
        result[report_id]=label
    return result


_THUMBNAIL_DRAWABLE=(12.0,12.0,296.0,148.0)
_THUMBNAIL_MIN_CARD=(28.0,20.0)


def _finite_float(value: Any, default: float | None=None) -> float | None:
    if isinstance(value,bool) or not isinstance(value,(int,float)): return default
    number=float(value)
    return number if math.isfinite(number) else default


def _report_thumbnail_geometry(model: Mapping[str,Any]) -> list[dict[str,Any]]:
    """Fit report items into the thumbnail's drawable area.

    Smart and Guided layouts may legitimately extend beyond a persisted canvas
    height.  The miniature therefore fits the union of the canvas and explicit
    item bounds, rather than clipping item sizes against a stale canvas edge.
    Items without complete geometry use a bounded grid which always fits all
    twelve miniature slots.
    """
    items=[entry for entry in model.get('items',[]) if isinstance(entry,Mapping)][:12]
    if not items: return []
    left,top,drawable_w,drawable_h=_THUMBNAIL_DRAWABLE;right=left+drawable_w;bottom=top+drawable_h
    canvas=model.get('canvas') if isinstance(model.get('canvas'),Mapping) else {}
    canvas_w=_finite_float(canvas.get('w')) or _finite_float(canvas.get('width')) or 1200.0
    canvas_h=_finite_float(canvas.get('h')) or _finite_float(canvas.get('height')) or 900.0
    canvas_w=max(1.0,canvas_w);canvas_h=max(1.0,canvas_h)
    explicit=[]
    for entry in items:
        values=tuple(_finite_float(entry.get(key)) for key in ('x','y','w','h'))
        explicit.append(values if all(value is not None for value in values) else None)

    positioned=[value for value in explicit if value is not None]
    min_x=min([0.0,*[value[0] for value in positioned]]);min_y=min([0.0,*[value[1] for value in positioned]])
    max_x=max([canvas_w,*[value[0]+max(0.0,value[2]) for value in positioned]])
    max_y=max([canvas_h,*[value[1]+max(0.0,value[3]) for value in positioned]])
    sx=drawable_w/max(1.0,max_x-min_x);sy=drawable_h/max(1.0,max_y-min_y)

    columns=2 if len(items)>1 else 1
    rows=math.ceil(len(items)/columns)
    gap=4.0
    fallback_w=(drawable_w-gap*(columns-1))/columns
    fallback_h=(drawable_h-gap*(rows-1))/rows
    min_w,min_h=_THUMBNAIL_MIN_CARD
    result=[]
    for index,(entry,source) in enumerate(zip(items,explicit)):
        if source is None:
            col=index%columns;row=index//columns
            x=left+col*(fallback_w+gap);y=top+row*(fallback_h+gap);w=fallback_w;h=fallback_h
        else:
            source_x,source_y,source_w,source_h=source
            w=min(drawable_w,max(min_w,max(0.0,source_w)*sx))
            h=min(drawable_h,max(min_h,max(0.0,source_h)*sy))
            x=left+(source_x-min_x)*sx;y=top+(source_y-min_y)*sy
            x=min(max(left,x),right-w);y=min(max(top,y),bottom-h)
        # This is the SVG rendering boundary.  The fit model above should
        # already satisfy these invariants; the final normalization protects
        # against future malformed input without emitting invalid attributes.
        x=min(max(left,float(x)),right-1.0);y=min(max(top,float(y)),bottom-1.0)
        w=min(max(1.0,float(w)),right-x);h=min(max(1.0,float(h)),bottom-y)
        result.append({'entry':entry,'x':x,'y':y,'w':w,'h':h})
    return result


def _report_thumbnail_markup(model: Mapping[str,Any], title: str='Report') -> str:
    """Render a content-derived miniature, never a generic item-count block."""
    items=[entry for entry in model.get('items',[]) if isinstance(entry,Mapping)]
    if not items:
        return f'<div class="cui-report-thumb cui-report-thumb--blank" role="img" aria-label="Blank preview of {html_escape(title)}"><svg viewBox="0 0 320 180"><rect class="thumb-page" x="8" y="8" width="304" height="164" rx="7"/><path class="thumb-blank-mark" d="M132 90h56M160 62v56"/><text x="160" y="140" text-anchor="middle">Blank report</text></svg></div>'
    datasets={str(value.get('id')):value for value in model.get('datasets',[]) if isinstance(value,Mapping)}
    def values(entry: Mapping[str,Any]) -> list[float]:
        source=entry.get('chart_studio') if isinstance(entry.get('chart_studio'),Mapping) else {}
        dataset=source.get('dataset') if isinstance(source.get('dataset'),Mapping) else datasets.get(str(entry.get('dataset_id')), {})
        rows=dataset.get('rows',[]) if isinstance(dataset,Mapping) else []
        output=[]
        for row in rows:
            if isinstance(row,list): output.extend(value for value in row if isinstance(value,(int,float)) and not isinstance(value,bool))
        if not output:
            for row in entry.get('data',[]):
                if isinstance(row,(list,tuple)) and len(row)>1 and isinstance(row[1],(int,float)) and not isinstance(row[1],bool): output.append(float(row[1]))
        return output[:20]
    shapes=[]
    for geometry in _report_thumbnail_geometry(model):
        entry=geometry['entry'];x=geometry['x'];y=geometry['y'];w=geometry['w'];h=geometry['h']
        engine=str(entry.get('engine') or '');element=str(entry.get('element') or '');family='text'
        outer=f'<rect class="thumb-card" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="4"/>'
        if engine in {'CoreChartEngine','EngineeringChartEngine'}:
            family='chart';nums=values(entry) or [2,5,3,7];lo=min(nums);span=max(1e-9,max(nums)-lo);points=' '.join(f'{x+6+i*max(1,w-12)/max(1,len(nums)-1):.1f},{y+h-6-(value-lo)/span*max(6,h-14):.1f}' for i,value in enumerate(nums));inner=f'<path class="thumb-axis" d="M{x+5:.1f} {y+5:.1f}V{y+h-5:.1f}H{x+w-4:.1f}"/><polyline class="thumb-chart-line" points="{points}"/>'
        elif engine=='WaferFabEngine':
            family='wafer';observations=entry.get('observations',[]);count=max(1,min(18,len(observations)));radius=max(9,min(w,h)*.34);cx=x+w/2;cy=y+h/2;dies=''.join(f'<rect class="thumb-die" x="{cx-radius+3+(i%5)*radius*.36:.1f}" y="{cy-radius+3+(i//5)*radius*.36:.1f}" width="{max(2,radius*.28):.1f}" height="{max(2,radius*.28):.1f}"/>' for i in range(count));inner=f'<circle class="thumb-wafer" cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.1f}"/>{dies}'
        elif engine=='DiagramEngine':
            family='diagram';labels=[str(node.get('label') or node.get('id')) if isinstance(node,Mapping) else str(node) for node in entry.get('nodes',[])][:4] or ['Start','Process','End'];step=max(1,(w-20)/max(1,len(labels)-1));nodes=''.join(f'<rect class="thumb-node" x="{x+5+i*step:.1f}" y="{y+h/2-6:.1f}" width="{min(24,max(13,step-5)):.1f}" height="12" rx="3"/>' for i in range(len(labels)));links=''.join(f'<path class="thumb-edge" d="M{x+18+i*step:.1f} {y+h/2:.1f}H{x+5+(i+1)*step:.1f}"/>' for i in range(len(labels)-1));inner=links+nodes
        elif engine=='MetricEngine':
            family='metric';inner=f'<text class="thumb-metric" x="{x+8:.1f}" y="{y+h*.62:.1f}">{html_escape(str(entry.get("value") if entry.get("value") is not None else "—")[:12])}</text><path class="thumb-rule" d="M{x+8:.1f} {y+h-8:.1f}H{x+w-8:.1f}"/>'
        elif engine=='TableEngine':
            family='table';inner=''.join(f'<path class="thumb-rule" d="M{x+5:.1f} {y+5+i*max(1,(h-10)/3):.1f}H{x+w-5:.1f}"/>' for i in range(4))
        elif engine=='ImageMediaEngine':
            family='media';inner=f'<rect class="thumb-media" x="{x+5:.1f}" y="{y+5:.1f}" width="{max(1,w-10):.1f}" height="{max(1,h-10):.1f}" rx="3"/><path class="thumb-media-mark" d="M{x+8:.1f} {y+h-9:.1f}l{w*.28:.1f}-{h*.32:.1f} {w*.18:.1f} {h*.17:.1f} {w*.18:.1f}-{h*.24:.1f}"/>'
        else:
            label=str(entry.get('title') or entry.get('statement') or entry.get('text') or element or 'Text');family='text';text_y=y+min(15,max(7,h*.42));line_one=y+min(h-5,max(10,h*.68));line_two=y+min(h-3,max(13,h*.84));inner=f'<text class="thumb-copy" x="{x+7:.1f}" y="{text_y:.1f}">{html_escape(label[:32])}</text><path class="thumb-copy-line" d="M{x+7:.1f} {line_one:.1f}H{x+w-9:.1f}M{x+7:.1f} {line_two:.1f}H{x+w*.7:.1f}"/>'
        shapes.append(f'<g data-preview-family="{family}" data-preview-element="{html_escape(element)}">{outer}{inner}</g>')
    return f'<div class="cui-report-thumb" role="img" aria-label="Content preview of {html_escape(title)}"><svg class="cui-report-thumb-svg" viewBox="0 0 320 180"><rect class="thumb-page" x="5" y="5" width="310" height="170" rx="8"/>{"".join(shapes)}</svg></div>'


def _history_diff_summary(before: Mapping[str,Any], after: Mapping[str,Any]) -> str:
    before_items={str(entry.get('id')):entry for entry in before.get('items',[]) if isinstance(entry,Mapping)}
    after_items={str(entry.get('id')):entry for entry in after.get('items',[]) if isinstance(entry,Mapping)}
    common=set(before_items)&set(after_items); parts=[]
    added=len(set(after_items)-set(before_items)); removed=len(set(before_items)-set(after_items))
    if added: parts.append(f'{added} added')
    if removed: parts.append(f'{removed} removed')
    def count(keys: set[str]) -> int: return sum(any(before_items[key].get(field)!=after_items[key].get(field) for field in keys) for key in common)
    categories=(('content/text',{'title','text','statement','detail','status','caption','alt','value','unit','delta','target','milestones'}),('geometry',{'x','y','w','h','order','z','groupId','locked'}),('data',{'data','rows','observations','customTable'}),('mapping',{'dataset_id','mapping','transform_recipe'}),('chart config',{'chart_studio','analysis_fields','analysis_rows','analysis_mapping'}),('diagram config',{'diagram','nodes','edges','direction','edge_label'}),('style/theme',{'style','presentation','theme','accent','textAlign','emphasis','message_role'}))
    for label,keys in categories:
        changed=count(keys)
        if changed: parts.append(f'{changed} {label}')
    if before.get('datasets')!=after.get('datasets'): parts.append('report data')
    metadata_keys={'title','description','theme','layoutPreset','mode','canvas'}
    if any(before.get(key)!=after.get(key) for key in metadata_keys): parts.append('report metadata')
    return ' · '.join(parts) if parts else 'No material model change'


def register_visualizer(
    app: Any,
    ui: Any,
    repository: ReportRepository,
    *,
    access: ReportAccessCatalog | None = None,
    runtime: NiceGUIRuntimeAdapter | None = None,
    dataset_store: DatasetResourceStore | None = None,
) -> None:
    if getattr(app,'_company_ui_visualizer_registered',False): return
    app._company_ui_visualizer_registered=True
    base_repository=repository
    access=access or ReportAccessCatalog(base_repository)
    dataset_store=dataset_store or DatasetResourceStore(base_repository.root.parent)
    if runtime is None:
        raise RuntimeError('Visembler registration requires the Company UI runtime adapter')

    def scoped_repository(request: Any) -> ScopedReportRepository:
        principal=runtime.principal_from_request(request)
        if not principal.authenticated:
            # Protected visualizer routes deliberately do not distinguish an
            # anonymous caller from a missing report.  This keeps the report
            # id, title, and existence boundary opaque while still allowing
            # the platform health/auth probes to use their own semantics.
            raise HTTPException(status_code=404, detail='resource unavailable')
        return ScopedReportRepository(base_repository,access,principal,runtime.authorization)

    app.add_middleware(
        _VisualizerResourceBoundary,
        auth_adapter=runtime.auth_adapter,
        repository=base_repository,
        access=access,
        authorization=runtime.authorization,
    )
    build=_asset_build()
    app.add_static_files(f'{STATIC_ROUTE}/assets',str(ASSETS),follow_symlink=False,max_cache_age=0)
    app.add_static_files(f'{STATIC_ROUTE}/vendor/production_core',str(VENDOR),follow_symlink=False,max_cache_age=0)

    from fastapi.responses import RedirectResponse
    @app.get('/',include_in_schema=False)
    async def _root_redirect(): return RedirectResponse('/visualizer',status_code=307)

    from fastapi.responses import Response
    @app.get(f'{STATIC_ROUTE}/report-assets/{{asset_id}}',include_in_schema=False)
    async def _report_asset(request: Request, asset_id: str):
        principal=runtime.principal_from_request(request)
        if not principal.authenticated:
            raise HTTPException(status_code=404,detail='asset unavailable')
        scoped=ScopedReportRepository(base_repository,access,principal,runtime.authorization)
        try:
            data=scoped.read_asset_by_id(asset_id)
        except (PermissionError, ReportNotFoundError):
            raise HTTPException(status_code=404,detail='asset unavailable')
        mime=str(validate_image_bytes(data)['mime'])
        return Response(content=data,media_type=mime,headers={'Cache-Control':'private, max-age=3600'})

    @ui.page('/visualizer/diagram-studio')
    async def visualizer_diagram_studio_page():
        """Dedicated structured diagram authoring surface.

        The studio owns diagram interactions in the browser, while the report
        repository remains the sole persistence boundary.  Opening this route
        is read-only; only an explicit Save diagram command commits a report
        revision and therefore appears in report history.
        """
        notifications=NiceGUIStateServices.notification_service()
        request=ui.context.client.request
        repository=scoped_repository(request)
        report_id=str(request.query_params.get('report') or '').strip()
        element_id=str(request.query_params.get('element') or '').strip()
        try:
            current=repository.get(report_id)
            entry=next(item for item in current.model.get('items',[]) if isinstance(item,Mapping) and str(item.get('id'))==element_id)
            if entry.get('engine')!='DiagramEngine': raise VisualizerContractError('Diagram Studio requires a DiagramEngine report element')
        except Exception as exc:
            notifications.error(f'Unable to open Diagram Studio: {exc}')
            ui.navigate.to(f'/visualizer?report={quote(report_id,safe="")}')
            return

        async def handle_studio_event(event: Any) -> None:
            nonlocal current
            payload:Mapping[str,Any]={}
            try:
                message=_decode_bridge_event(event); kind=message['type']; payload=message['payload']
                if kind!='report.commit': raise VisualizerContractError(f'unsupported Diagram Studio event: {kind}')
                if str(payload.get('report_id') or '')!=current.report_id: raise VisualizerContractError('diagram commit targets a different report')
                model_value=payload.get('model')
                if not isinstance(model_value,Mapping): raise VisualizerContractError('diagram commit model is required')
                canonical=canonical_model(model_value); _validate_model_images(canonical)
                current=repository.commit(current.report_id,base_revision=int(payload.get('base_revision')),model=canonical,commit_id=str(payload.get('commit_id') or ''))
                await ui.run_javascript(f'window.CompanyUIDiagramStudio?.receive({json.dumps({"bridge_version":BRIDGE_VERSION,"type":"report.commit_result","payload":{"report_id":current.report_id,"revision":current.revision,"commit_id":str(payload.get("commit_id") or ""),"fingerprint":current.to_dict()["fingerprint"]}},ensure_ascii=False)})')
            except RevisionConflictError:
                latest=repository.get(current.report_id)
                await ui.run_javascript(f'window.CompanyUIDiagramStudio?.receive({json.dumps({"bridge_version":BRIDGE_VERSION,"type":"report.error","payload":{"commit_id":str(payload.get("commit_id") or ""),"message":f"Report changed elsewhere at revision {latest.revision}; reopen Diagram Studio."}},ensure_ascii=False)})')
            except Exception as exc:
                await ui.run_javascript(f'window.CompanyUIDiagramStudio?.receive({json.dumps({"bridge_version":BRIDGE_VERSION,"type":"report.error","payload":{"commit_id":str(payload.get("commit_id") or ""),"message":str(exc)[:400]}},ensure_ascii=False)})')

        css_url=f'{STATIC_ROUTE}/assets/diagram_studio.css?v={build}'
        token_url=f'{STATIC_ROUTE}/assets/tokens.css?v={build}'
        module_url=f'{STATIC_ROUTE}/assets/diagram_studio.mjs?v={build}'
        ui.add_head_html(f'<link rel="stylesheet" href="{token_url}"><link rel="stylesheet" href="{css_url}">')
        with AppShell('Visembler',NAVIGATION,active_route='/visualizer',sidebar=SidebarMode.COMPACT,environment=None,subtitle='Diagram Studio',owner='Visembler'):
            with ui.column().classes('cui-page cui-page--full cui-diagram-studio-page w-full'):
                host=ui.element('div').classes('cui-diagram-studio-host w-full').props('aria-label="Visembler Diagram Studio"')
                host.on('visualizer_bridge',handle_studio_event,args=['detail'])
                with host: ui.html((ASSETS/'diagram_studio.html').read_text(encoding='utf-8'),sanitize=False)
        studio_bootstrap={
            'report_id':current.report_id,'revision':current.revision,'title':current.title,
            'element_id':element_id,'entry':json.loads(stable_json(entry)),'model':json.loads(stable_json(current.model)),
            'capabilities': repository.capabilities(current.report_id).to_dict(),
            'asset_build':build,
        }
        script=f'''window.__CUI_DIAGRAM_STUDIO_BOOTSTRAP__={json.dumps(studio_bootstrap,ensure_ascii=False)};import({json.dumps(module_url)}).catch(error=>{{console.error(error);const root=document.querySelector('#diagram-studio');if(root)root.dataset.studioReady='failed';}});'''
        ui.run_javascript(script)

    @ui.page('/visualizer/chart-studio')
    async def visualizer_chart_studio_page():
        """Dedicated local/offline chart authoring surface.

        Chart Studio owns semantic chart editing in the browser.  The report
        repository remains the only persistence boundary, so opening the
        studio is read-only and an explicit Save chart creates one revision.
        """
        notifications=NiceGUIStateServices.notification_service()
        request=ui.context.client.request
        repository=scoped_repository(request)
        dataset_repository=ScopedDatasetRepository(dataset_store, repository)
        report_id=str(request.query_params.get('report') or '').strip()
        element_id=str(request.query_params.get('element') or '').strip()
        chart_engines={'CoreChartEngine','EngineeringChartEngine','WaferFabEngine'}
        try:
            current=repository.get(report_id)
            entry=next(item for item in current.model.get('items',[]) if isinstance(item,Mapping) and str(item.get('id'))==element_id)
            if entry.get('engine') not in chart_engines: raise VisualizerContractError('Chart Studio requires a chart, engineering chart, or Wafer Map element')
            datasets=current.model.get('datasets',[])
            dataset=next((item for item in datasets if isinstance(item,Mapping) and str(item.get('id'))==str(entry.get('dataset_id'))),{})
            if isinstance(dataset, Mapping) and dataset.get('resource_id'):
                dataset=dataset_repository.preview_for_report(current.report_id, str(dataset.get('id')))
            # The browser-side canonical adapter owns legacy/core/engineering/
            # wafer hydration. Do not create a second chart model here.
            chart_model=entry.get('chart_studio') if isinstance(entry.get('chart_studio'),Mapping) else None
        except Exception as exc:
            notifications.error(f'Unable to open Chart Studio: {exc}')
            ui.navigate.to(f'/visualizer?report={quote(report_id,safe="")}')
            return

        async def handle_chart_event(event: Any) -> None:
            nonlocal current
            payload:Mapping[str,Any]={}
            try:
                message=_decode_bridge_event(event); kind=message['type']; payload=message['payload']
                if kind!='report.commit': raise VisualizerContractError(f'unsupported Chart Studio event: {kind}')
                if str(payload.get('report_id') or '')!=current.report_id: raise VisualizerContractError('chart commit targets a different report')
                model_value=payload.get('model')
                if not isinstance(model_value,Mapping): raise VisualizerContractError('chart commit model is required')
                canonical=canonical_model(model_value); _validate_model_images(canonical)
                current=repository.commit(current.report_id,base_revision=int(payload.get('base_revision')),model=canonical,commit_id=str(payload.get('commit_id') or ''))
                await ui.run_javascript(f'window.CompanyUIChartStudio?.receive({json.dumps({"bridge_version":BRIDGE_VERSION,"type":"report.commit_result","payload":{"report_id":current.report_id,"revision":current.revision,"commit_id":str(payload.get("commit_id") or ""),"fingerprint":current.to_dict()["fingerprint"]}},ensure_ascii=False)})')
            except RevisionConflictError:
                latest=repository.get(current.report_id)
                await ui.run_javascript(f'window.CompanyUIChartStudio?.receive({json.dumps({"bridge_version":BRIDGE_VERSION,"type":"report.error","payload":{"commit_id":str(payload.get("commit_id") or ""),"message":f"Report changed elsewhere at revision {latest.revision}; reopen Chart Studio."}},ensure_ascii=False)})')
            except Exception as exc:
                await ui.run_javascript(f'window.CompanyUIChartStudio?.receive({json.dumps({"bridge_version":BRIDGE_VERSION,"type":"report.error","payload":{"commit_id":str(payload.get("commit_id") or ""),"message":str(exc)[:400]}},ensure_ascii=False)})')

        css_url=f'{STATIC_ROUTE}/assets/chart_studio.css?v={build}'
        token_url=f'{STATIC_ROUTE}/assets/tokens.css?v={build}'
        module_url=f'{STATIC_ROUTE}/assets/chart_studio.mjs?v={build}'
        ui.add_head_html(f'<link rel="stylesheet" href="{token_url}"><link rel="stylesheet" href="{css_url}">')
        with AppShell('Visembler',NAVIGATION,active_route='/visualizer',sidebar=SidebarMode.COMPACT,environment=None,subtitle='Chart Studio',owner='Visembler'):
            with ui.column().classes('cui-page cui-page--full cui-chart-studio-page w-full'):
                host=ui.element('div').classes('cui-chart-studio-host w-full').props('aria-label="Visembler Chart Studio"')
                host.on('visualizer_bridge',handle_chart_event,args=['detail'])
                with host: ui.html((ASSETS/'chart_studio.html').read_text(encoding='utf-8'),sanitize=False)
        studio_bootstrap={
            'report_id':current.report_id,'revision':current.revision,'title':current.title,
            'element_id':element_id,'entry':json.loads(stable_json(entry)),'dataset':json.loads(stable_json(dataset or {})),
            'chart_model':json.loads(stable_json(chart_model)),'report_model':json.loads(stable_json(current.model)),
            'capabilities': repository.capabilities(current.report_id).to_dict(),
            'asset_build':build,
        }
        script=f'''window.__CUI_CHART_STUDIO_BOOTSTRAP__={json.dumps(studio_bootstrap,ensure_ascii=False)};import({json.dumps(module_url)}).catch(error=>{{console.error(error);const root=document.querySelector('#chart-studio');if(root)root.dataset.studioReady='failed';}});'''
        ui.run_javascript(script)

    @ui.page('/visualizer/reports')
    async def visualizer_reports_page():
        """Dedicated report hub; report management never needs the live canvas."""
        notifications=NiceGUIStateServices.notification_service(); downloads=NiceGUIStateServices.download_service()
        page_state=NiceGUIStateServices.user_store()
        request=ui.context.client.request
        repository=scoped_repository(request)
        query_report=str(request.query_params.get('report') or '')
        history_report_id=query_report or str(page_state.get('visualizer.current_report') or '')
        can_create='report.create' in runtime.authorization.effective_permissions(repository.principal) or 'administration' in runtime.authorization.effective_permissions(repository.principal)
        delete_target={'report_id':None,'revision':None}; restore_target={'report_id':None,'history_id':None}; hub_layout='grid'
        share_target={'report_id':None}

        ui.add_head_html('''<style>
          .cui-report-hub{max-width:1440px;margin:0 auto;padding:var(--cui-space-8) var(--cui-space-8) var(--cui-space-16);display:grid;gap:var(--cui-space-5)}
          .cui-report-hub-head{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap}
          .cui-report-hub-head h1{margin:0;font-size:var(--cui-font-size-32);letter-spacing:-.04em}.cui-report-hub-head p{margin:var(--cui-space-1) 0 0;color:#69717d}
          .cui-report-hub-toolbar{display:flex;gap:var(--cui-space-2);align-items:center;flex-wrap:wrap;padding:var(--cui-space-3);border:1px solid #dfe4eb;border-radius:var(--cui-radius-control);background:#fff}
          .cui-report-hub-toolbar>*{min-width:150px}.cui-report-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:var(--cui-space-3)}
          .cui-report-grid.cui-report-list{grid-template-columns:1fr;gap:var(--cui-space-2)}
          .cui-report-list .cui-report-card{grid-template-columns:180px minmax(0,1fr);align-items:start}.cui-report-list .cui-report-thumb{grid-row:span 2;height:108px}
          .cui-report-card,.cui-history-card{display:grid;gap:var(--cui-space-2);padding:var(--cui-space-3);border:1px solid #dfe4eb;border-radius:var(--cui-radius-surface);background:#fff;box-shadow:0 2px 10px rgba(30,55,90,.05)}
          .cui-report-card h2{margin:0;font-size:var(--cui-font-size-16)}.cui-report-card small,.cui-history-card small{color:#69717d;line-height:var(--cui-line-height-ratio-1_35)}
          .cui-report-card .q-field{min-width:0}.cui-report-card .q-field__control{min-height:36px!important;height:36px!important}.cui-report-card .q-field__native{font-size:var(--cui-font-size-13)!important}
          .cui-report-card-actions,.cui-history-actions{display:flex;gap:var(--cui-space-1);flex-wrap:wrap}.cui-report-card-actions .q-btn,.cui-history-actions .q-btn{min-height:34px}
          .cui-report-thumb{height:132px;position:relative;overflow:hidden;border-radius:var(--cui-radius-control);background:linear-gradient(135deg,#f4f7fb,#e9eff7);border:1px solid #dfe4eb}
          .cui-report-thumb svg{width:100%;height:100%;display:block}.thumb-page{fill:#f8fafc;stroke:#d9e1eb}.thumb-card{fill:#fff;stroke:#cad4e0}.thumb-chart-line{fill:none;stroke:#1769d1;stroke-width:2}.thumb-axis,.thumb-edge,.thumb-rule,.thumb-copy-line{fill:none;stroke:#94a3b8;stroke-width:1}.thumb-wafer{fill:#edf4fb;stroke:#496a8e}.thumb-die{fill:#2f80ed;stroke:#fff;stroke-width:.5}.thumb-node{fill:#eef5ff;stroke:#1769d1}.thumb-metric{font-size:var(--cui-font-size-18);font-weight:var(--cui-font-weight-700);font-family:system-ui;fill:#1f3a57}.thumb-copy{font-size:var(--cui-font-size-10);font-weight:var(--cui-font-weight-700);font-family:system-ui;fill:#25364a}.thumb-media{fill:#adc9dd}.thumb-media-mark{fill:none;stroke:#fff;stroke-width:2}.thumb-blank-mark{stroke:#9cb0c7;stroke-width:2}.cui-report-thumb text{font-size:var(--cui-font-size-10);font-family:system-ui;fill:#69717d}.cui-history-compare{display:grid;grid-template-columns:1fr 1fr;gap:6px}.cui-history-compare .cui-report-thumb{height:78px}.cui-history-preview-label{font-size:var(--cui-font-size-10);color:#69717d;text-align:center}
          .cui-report-hub-section{display:grid;gap:var(--cui-space-2)}.cui-report-hub-section>h2{margin:0;font-size:var(--cui-font-size-18)}.cui-report-hub-empty{padding:var(--cui-space-6);border:1px dashed #cbd3df;border-radius:var(--cui-radius-control);color:#69717d;background:#fafbfc}
          .cui-history-panel{display:grid;gap:var(--cui-space-2);padding:var(--cui-space-4);border:1px solid #dfe4eb;border-radius:var(--cui-radius-surface);background:#f8fafc}.cui-history-list{display:grid;gap:var(--cui-space-2)}
          .cui-history-card{grid-template-columns:150px minmax(0,1fr);align-items:start}.cui-history-card .cui-report-thumb{height:94px}.cui-history-card h3{margin:0;font-size:var(--cui-font-size-14)}
          @media(max-width:800px){.cui-report-hub{padding:var(--cui-space-5) var(--cui-space-3) 78px}.cui-report-hub-toolbar>*{flex:1 1 100%;min-width:0}.cui-history-card{grid-template-columns:1fr}.cui-history-card .cui-report-thumb{height:120px}}
        </style>''')

        def hub_url(report_id: str) -> str: return f'/visualizer?report={quote(report_id,safe="")}'
        def sorted_records(records):
            sort=str(sort_select.value or 'modified')
            if sort=='title': return sorted(records,key=lambda record:(record.title.casefold(),record.report_id))
            if sort=='created': return sorted(records,key=lambda record:(record.created_at,record.report_id),reverse=True)
            return sorted(records,key=lambda record:(record.updated_at,record.report_id),reverse=True)

        def set_hub_layout(layout: str) -> None:
            nonlocal hub_layout
            hub_layout='list' if layout=='list' else 'grid'
            render_cards.refresh()

        async def create_hub_report() -> None:
            template_id=str(template_select.value or 'blank')
            spec=REPORT_TEMPLATES.get(template_id); title='Untitled report' if template_id=='blank' else str(spec['name'])
            record=repository.create(f'report-{uuid.uuid4().hex}',title=title,model=template_model(template_id),metadata={'template_id':template_id})
            notifications.success(f'{title} created'); ui.navigate.to(hub_url(record.report_id))

        async def upload_hub_report(event: Any) -> None:
            try:
                name,content=await _read_upload(event,max_bytes=MODEL_MAX_BYTES)
                value=json.loads(content.decode('utf-8')); model_source=value.get('model',value) if isinstance(value,Mapping) else None
                if not isinstance(model_source,Mapping): raise VisualizerContractError('report JSON must contain a model object')
                canonical=canonical_model(model_source); _validate_model_images(canonical)
                record=repository.create(f'import-{uuid.uuid4().hex}',title=Path(name).stem[:160] or 'Imported report',model=canonical,metadata={'imported_from':name})
                import_hub_dialog.close(); notifications.success('Report imported'); ui.navigate.to(hub_url(record.report_id))
            except Exception as exc: notifications.error(f'Report import rejected: {exc}')

        async def duplicate_hub_report(report_id: str) -> None:
            try:
                source=repository.get(report_id); record=repository.duplicate(source.report_id,f'report-{uuid.uuid4().hex}',title=f'{source.title} copy'[:160],metadata={**source.metadata,'duplicated_from':source.report_id})
                notifications.success('Report duplicated'); history_report_id=record.report_id; render_cards.refresh(); render_history.refresh()
            except Exception as exc: notifications.error(f'Duplicate rejected: {exc}')

        async def rename_hub_report(report_id: str,event: Any) -> None:
            try:
                latest=repository.get(report_id); value=str(getattr(event,'value','') or '')
                if value.strip()!=latest.title: repository.rename(report_id,title=value,expected_revision=latest.revision); notifications.success('Report renamed'); render_cards.refresh()
            except RevisionConflictError: notifications.error('Report changed elsewhere; reload the report hub before renaming.')
            except Exception as exc: notifications.error(f'Rename rejected: {exc}')

        async def describe_hub_report(report_id: str,event: Any) -> None:
            try:
                latest=repository.get(report_id); value=str(getattr(event,'value','') or '')
                if value!=str(latest.metadata.get('description') or ''): repository.update_description(report_id,value,expected_revision=latest.revision); notifications.success('Description updated'); render_cards.refresh()
            except RevisionConflictError: notifications.error('Report changed elsewhere; reload the report hub before editing metadata.')
            except Exception as exc: notifications.error(f'Description update rejected: {exc}')

        def select_history(report_id: str) -> None:
            nonlocal history_report_id
            history_report_id=report_id; page_state['visualizer.current_report']=report_id; render_history.refresh()

        def begin_trash(report_id: str) -> None:
            record=repository.get(report_id); delete_target.update(report_id=record.report_id,revision=record.revision); delete_summary.set_text(f'Move “{record.title}” to trash? Its history remains recoverable.'); delete_dialog.open()

        async def confirm_trash() -> None:
            report_id=delete_target.get('report_id'); revision=delete_target.get('revision')
            if not report_id or not isinstance(revision,int): return
            try:
                repository.trash_report(report_id,expected_revision=revision); delete_dialog.close(); notifications.success('Report moved to trash'); render_cards.refresh()
            except Exception as exc: notifications.error(f'Trash rejected: {exc}')

        async def restore_hub_report(report_id: str) -> None:
            try: repository.restore(report_id); notifications.success('Report restored'); render_cards.refresh()
            except Exception as exc: notifications.error(f'Restore rejected: {exc}')

        def export_hub_json(report_id: str) -> None:
            repository.require_export(report_id)
            record=repository.get(report_id); payload=stable_json({'report_id':record.report_id,'title':record.title,'description':record.metadata.get('description',''),'revision':record.revision,'model':record.model}).encode('utf-8'); downloads.download(f'{record.title or "visembler-report"}.json',payload,media_type='application/json')

        async def checkpoint_hub(report_id: str,field: Any) -> None:
            try:
                name=' '.join(str(field.value or '').split())
                if not name: notifications.warning('Enter a checkpoint name first'); return
                record=repository.get(report_id); repository.checkpoint(report_id,name=name,expected_revision=record.revision); field.value=''; field.update(); notifications.success('Named checkpoint saved'); render_history.refresh()
            except Exception as exc: notifications.error(f'Checkpoint rejected: {exc}')

        def begin_history_restore(report_id: str,history_id: str,summary: str) -> None:
            restore_target.update(report_id=report_id,history_id=history_id); history_restore_summary.set_text(f'Restore {summary}? This replaces the active report state and creates a new revision.'); history_restore_dialog.open()

        async def confirm_history_restore() -> None:
            report_id=restore_target.get('report_id'); history_id=restore_target.get('history_id')
            if not report_id or not history_id: return
            try:
                record=repository.get(report_id); repository.restore_history(report_id,history_id,expected_revision=record.revision); history_restore_dialog.close(); notifications.success('Revision restored as a new revision'); render_cards.refresh(); render_history.refresh()
            except Exception as exc: notifications.error(f'Revision restore rejected: {exc}')

        async def duplicate_hub_history(report_id: str,history_id: str) -> None:
            try:
                repository.duplicate_from_history(report_id,history_id,f'report-{uuid.uuid4().hex}'); notifications.success('Historical revision duplicated as a new report'); render_cards.refresh()
            except Exception as exc: notifications.error(f'Historical duplicate rejected: {exc}')

        def open_share(report_id: str) -> None:
            try:
                record=repository.get(report_id); summary=access.access_summary(report_id,repository.principal)
                share_target['report_id']=record.report_id
                share_summary.set_text(f"Owner: {summary['owner']} · Grants: {len(summary['grants'])}")
                share_subject.value=''; share_subject.update(); share_dialog.open()
            except Exception as exc: notifications.error(f'Unable to open sharing: {exc}')

        async def apply_share() -> None:
            report_id=share_target.get('report_id'); subject=str(share_subject.value or '').strip(); role=ReportRole(str(share_role.value or 'viewer'))
            if not report_id or not subject:
                notifications.warning('Enter a user or group before sharing'); return
            try:
                access.grant(report_id,repository.principal,subject,role,group=bool(share_group.value)); share_dialog.close(); notifications.success('Report access updated'); render_cards.refresh()
            except Exception as exc: notifications.error(f'Share rejected: {exc}')

        async def revoke_share() -> None:
            report_id=share_target.get('report_id'); subject=str(share_subject.value or '').strip()
            if not report_id or not subject:
                notifications.warning('Enter the user or group to revoke'); return
            try:
                access.revoke(report_id,repository.principal,subject,group=bool(share_group.value)); share_dialog.close(); notifications.success('Report access revoked'); render_cards.refresh()
            except Exception as exc: notifications.error(f'Revoke rejected: {exc}')

        @ui.refreshable
        def render_cards() -> None:
            needle=' '.join(str(search.value or '').split()).casefold(); view=str(view_filter.value or 'active'); active_summaries=repository.list_summaries(); trash=sorted_records(repository.list_trash())
            if sort_select.value=='title': active_summaries=sorted(active_summaries,key=lambda value:(str(value.get('title') or '').casefold(),str(value.get('report_id') or '')))
            elif sort_select.value=='created': active_summaries=sorted(active_summaries,key=lambda value:(str(value.get('created_at') or ''),str(value.get('report_id') or '')),reverse=True)
            else: active_summaries=sorted(active_summaries,key=lambda value:(str(value.get('updated_at') or ''),str(value.get('report_id') or '')),reverse=True)
            def summary_matches(value): return not needle or needle in str(value.get('title') or '').casefold() or needle in str(value.get('report_id') or '').casefold() or needle in str(value.get('description') or '').casefold()
            def matches(record): return not needle or needle in record.title.casefold() or needle in record.report_id.casefold() or needle in str(record.metadata.get('description') or '').casefold()
            if view in {'active','all'}:
                visible_summaries=[value for value in active_summaries if summary_matches(value)]
                visible=[]
                for summary in visible_summaries[:40]:
                    try: visible.append(repository.get(str(summary['report_id'])))
                    except Exception: continue
                with ui.element('section').classes('cui-report-hub-section'):
                    ui.label(f'Active reports · {len(visible_summaries)}').classes('text-h6')
                    if not visible: ui.label('No active reports match this search.').classes('cui-report-hub-empty')
                    else:
                        with ui.element('div').classes(f'cui-report-grid cui-report-{hub_layout}'):
                            for record in visible:
                                with ui.card().classes('cui-report-card').props(f'data-testid="report-card" data-report-id="{record.report_id}" data-report-state="active"'):
                                    ui.html(_report_thumbnail_markup(record.model,record.title),sanitize=False)
                                    projection=repository.capabilities(record.report_id)
                                    if projection.can_rename:
                                        ui.input(value=record.title,label='Title',on_change=lambda event,rid=record.report_id:rename_hub_report(rid,event)).props('outlined dense hide-bottom-space').classes('w-full')
                                        ui.input(value=str(record.metadata.get('description') or ''),label='Description',placeholder='What this report is for',on_change=lambda event,rid=record.report_id:describe_hub_report(rid,event)).props('outlined dense hide-bottom-space').classes('w-full')
                                    else:
                                        ui.label(record.title).classes('cui-report-card-title')
                                        ui.label(str(record.metadata.get('description') or '') or 'No description').classes('cui-report-card-description')
                                    ui.label(f'Created {record.created_at} · Modified {record.updated_at} · revision {record.revision} · {len(record.model.get("items",[]))} elements').classes('text-caption')
                                    ui.label(f"Owner {record.metadata.get('owner_display_name') or 'account owner'} · Access {projection.role or 'none'}").classes('text-caption')
                                    with ui.row().classes('cui-report-card-actions'):
                                        ui.button('Open',on_click=lambda rid=record.report_id:ui.navigate.to(hub_url(rid))).props('unelevated no-caps data-report-action="open"')
                                        if projection.can_duplicate: ui.button('Duplicate',on_click=lambda rid=record.report_id:duplicate_hub_report(rid)).props('flat no-caps data-report-action="duplicate"')
                                        if projection.can_read_history: ui.button('History',on_click=lambda rid=record.report_id:select_history(rid)).props('flat no-caps data-report-action="history"')
                                        if projection.can_export: ui.button('Export JSON',on_click=lambda rid=record.report_id:export_hub_json(rid)).props('flat no-caps data-report-action="export-json"')
                                        if projection.can_share:
                                            ui.button('Share',on_click=lambda rid=record.report_id:open_share(rid)).props('flat no-caps data-report-action="share"')
                                        if projection.can_delete: ui.button('Move to trash',on_click=lambda rid=record.report_id:begin_trash(rid)).props('flat no-caps color=negative data-report-action="trash"')
                        if len(visible_summaries)>len(visible): ui.label(f'Showing the first {len(visible)} reports. Search to narrow the collection.').classes('text-caption')
            if view in {'trash','all'}:
                visible=[record for record in trash if matches(record)]
                with ui.element('section').classes('cui-report-hub-section'):
                    ui.label(f'Trash · {len(visible)}').classes('text-h6')
                    if not visible: ui.label('Trash is empty.').classes('cui-report-hub-empty')
                    else:
                        with ui.element('div').classes('cui-report-grid'):
                            for record in visible:
                                with ui.card().classes('cui-report-card').props(f'data-testid="report-card" data-report-id="{record.report_id}" data-report-state="trash"'):
                                    ui.html(_report_thumbnail_markup(record.model,record.title),sanitize=False); ui.label(record.title).classes('text-subtitle1'); ui.label(f'Moved from active storage · revision {record.revision} · {len(record.model.get("items",[]))} elements').classes('text-caption')
                                    with ui.row().classes('cui-report-card-actions'):
                                        projection=repository.capabilities(record.report_id)
                                        if projection.can_restore: ui.button('Restore',on_click=lambda rid=record.report_id:restore_hub_report(rid)).props('unelevated no-caps data-report-action="restore"')
                                        if projection.can_export: ui.button('Export JSON',on_click=lambda rid=record.report_id:export_hub_json(rid)).props('flat no-caps data-report-action="export-json"')

        @ui.refreshable
        def render_history() -> None:
            if not history_report_id:
                with ui.element('section').classes('cui-history-panel'): ui.label('Select History on an active report to inspect revisions.').classes('cui-report-hub-empty')
                return
            try: record=repository.get(history_report_id); entries=repository.list_history(history_report_id)
            except Exception: entries=[]; record=None
            with ui.element('section').classes('cui-history-panel'):
                if not record: ui.label('The selected report is no longer available.').classes('cui-report-hub-empty'); return
                ui.label(f'History · {record.title}').classes('text-h6'); ui.label('Each restore is explicit, revisioned, and leaves the prior state in history.').classes('text-caption')
                checkpoint=ui.input(label='Named checkpoint',placeholder='Before review',value='Review checkpoint').props('outlined dense hide-bottom-space')
                projection=repository.capabilities(record.report_id)
                if projection.can_restore_history:
                    async def save_hub_checkpoint(_event: Any = None, rid: str = record.report_id, field: Any = checkpoint) -> None:
                        await checkpoint_hub(rid,field)
                    checkpoint_button=ui.button('Save checkpoint',on_click=save_hub_checkpoint).props('flat no-caps')
                    checkpoint.on_value_change(lambda event,button=checkpoint_button:button.enable() if str(event.value or '').strip() else button.disable())
                else:
                    checkpoint.disable(); ui.label('Read-only history · restore and duplicate are unavailable.').classes('cui-field-description')
                if not entries: ui.label('No saved revisions yet.').classes('cui-report-hub-empty')
                else:
                    with ui.element('div').classes('cui-history-list'):
                        for entry in entries[:40]:
                            try: snapshot=repository.get_history(record.report_id,str(entry['history_id'])); historical=snapshot.get('model',{})
                            except Exception: continue
                            summary=f'r{entry["revision"]} · {entry.get("updated_at") or "timestamp unavailable"} · {entry.get("label") or "Saved revision"}{" · checkpoint" if entry.get("checkpoint") else ""}'
                            with ui.card().classes('cui-history-card'):
                                with ui.element('div').classes('cui-history-compare'):
                                    with ui.element('div'): ui.html(_report_thumbnail_markup(historical,f'{record.title} revision {entry["revision"]}'),sanitize=False); ui.label(f'r{entry["revision"]}').classes('cui-history-preview-label')
                                    with ui.element('div'): ui.html(_report_thumbnail_markup(record.model,f'{record.title} current'),sanitize=False); ui.label(f'Current r{record.revision}').classes('cui-history-preview-label')
                                with ui.element('div').classes('cui-history-card-copy'):
                                    ui.label(summary).classes('text-subtitle2'); ui.label(_history_diff_summary(historical,record.model)).classes('text-caption')
                                    with ui.row().classes('cui-history-actions'):
                                        if projection.can_restore_history: ui.button('Restore this revision',on_click=lambda rid=record.report_id,hid=entry['history_id'],s=summary:begin_history_restore(rid,str(hid),s)).props('unelevated no-caps')
                                        if projection.can_duplicate: ui.button('Duplicate as new report',on_click=lambda rid=record.report_id,hid=entry['history_id']:duplicate_hub_history(rid,str(hid))).props('flat no-caps')

        import_hub_dialog=ui.dialog()
        with AppShell('Visembler',NAVIGATION,active_route='/visualizer/reports',sidebar=SidebarMode.COMPACT,environment=None,subtitle='Report hub',owner='Visembler'):
            with ui.column().classes('cui-report-hub w-full').props('data-testid="report-hub"'):
                with ui.element('header').classes('cui-report-hub-head'):
                    with ui.column().classes('gap-0'):
                        ui.label('Reports').classes('text-h3'); ui.label('Open, organize, and recover reports without covering the authoring canvas.').classes('text-body1')
                    ui.button('Open editor',on_click=lambda:ui.navigate.to(hub_url(history_report_id) if history_report_id else '/visualizer')).props('flat no-caps')
                    ui.button('Dataset library',on_click=lambda:ui.navigate.to(f'{hub_url(history_report_id)}&panel=datasets' if history_report_id else '/visualizer?panel=datasets')).props('flat no-caps')
                    ui.button('Reusable assets',on_click=lambda:ui.navigate.to(f'{hub_url(history_report_id)}&panel=assets' if history_report_id else '/visualizer?panel=assets')).props('flat no-caps')
                    ui.button('Blueprints',on_click=lambda:ui.navigate.to(f'{hub_url(history_report_id)}&panel=blueprints' if history_report_id else '/visualizer?panel=blueprints')).props('flat no-caps')
                    if can_create: ui.button('Import…',on_click=import_hub_dialog.open).props('flat no-caps')
                with ui.element('section').classes('cui-report-hub-toolbar'):
                    search=ui.input(label='Search reports',placeholder='Title, description, or report ID',on_change=lambda _event:render_cards.refresh()).props('outlined dense hide-bottom-space').classes('flex-grow')
                    sort_select=ui.select(label='Sort',options={'modified':'Recently modified','created':'Recently created','title':'Title'},value='modified',on_change=lambda _event:render_cards.refresh()).props('outlined dense hide-bottom-space')
                    view_filter=ui.select(label='View',options={'active':'Active','all':'Active + trash','trash':'Trash'},value='active',on_change=lambda _event:render_cards.refresh()).props('outlined dense hide-bottom-space')
                    ui.button('Grid',on_click=lambda:set_hub_layout('grid')).props('flat no-caps data-testid="report-grid-view"').tooltip('Show report cards')
                    ui.button('List',on_click=lambda:set_hub_layout('list')).props('flat no-caps data-testid="report-list-view"').tooltip('Show a compact report list')
                    if can_create:
                        template_select=ui.select(label='New report from',options={'blank':'Blank canvas',**{key:str(spec['name']) for key,spec in REPORT_TEMPLATES.items()}},value='blank').props('outlined dense hide-bottom-space')
                        ui.button('Create report',on_click=create_hub_report).props('unelevated no-caps')
                render_cards()
                render_history()

            with import_hub_dialog:
                with ui.card().classes('cui-dialog-card cui-visualizer-import-card'):
                    ui.label('Import').classes('cui-dialog-title')
                    ui.label('Import a Visembler report from its canonical JSON file.').classes('cui-field-description')
                    with ui.column().classes('w-full gap-3'):
                        FileUpload(label='Visembler report JSON',accept=('.json',),max_file_size_mb=2,on_upload=upload_hub_report)
                    ui.button('Done',on_click=import_hub_dialog.close).props('flat no-caps')

            share_dialog=ui.dialog()
            with share_dialog:
                with ui.card().classes('cui-dialog-card'):
                    ui.label('Share report').classes('cui-dialog-title')
                    share_summary=ui.label('').classes('cui-field-description')
                    share_subject=ui.input(label='User or group subject',placeholder='alice@example.com or team-id').props('outlined dense hide-bottom-space').classes('w-full')
                    share_role=ui.select(label='Access',options={'viewer':'Viewer · read/export','editor':'Editor · authoring/history'},value='viewer').props('outlined dense hide-bottom-space').classes('w-full')
                    share_group=ui.checkbox('This is a group subject')
                    with ui.row():
                        ui.button('Grant or update',on_click=apply_share).props('unelevated no-caps')
                        ui.button('Revoke',on_click=revoke_share).props('flat no-caps color=negative')
                        ui.button('Close',on_click=share_dialog.close).props('flat no-caps')

            delete_dialog=ui.dialog()
            with delete_dialog:
                with ui.card().classes('cui-dialog-card'):
                    delete_summary=ui.label('Move this report to trash?').classes('cui-dialog-title'); ui.label('The report and its history remain recoverable until the trash entry is removed from storage.').classes('cui-field-description')
                    with ui.row(): ui.button('Move to trash',on_click=confirm_trash).props('unelevated no-caps color=negative'); ui.button('Cancel',on_click=delete_dialog.close).props('flat no-caps')
            history_restore_dialog=ui.dialog()
            with history_restore_dialog:
                with ui.card().classes('cui-dialog-card'):
                    history_restore_summary=ui.label('Restore this revision?').classes('cui-dialog-title'); ui.label('The current state is retained in history and the restore creates a new revision.').classes('cui-field-description')
                    with ui.row(): ui.button('Restore revision',on_click=confirm_history_restore).props('unelevated no-caps'); ui.button('Cancel',on_click=history_restore_dialog.close).props('flat no-caps')

    @ui.page('/visualizer')
    async def visualizer_page():
        notifications=NiceGUIStateServices.notification_service(); downloads=NiceGUIStateServices.download_service()
        preferences=NiceGUIStateServices.user_preferences(key='company_ui_visualizer_preferences')
        page_state=NiceGUIStateServices.user_store()
        request=ui.context.client.request
        repository=scoped_repository(request)
        dataset_repository=ScopedDatasetRepository(dataset_store, repository)
        data_sessions: dict[str, Any] = {}
        summaries=repository.list_summaries()
        records=[]
        if summaries:
            try: records=[repository.get(str(summaries[0]['report_id']))]
            except Exception: records=[]
        if not records:
            # A newly authenticated user may legitimately have no reports in
            # scope.  Do not collide with another user's default report or
            # reveal it while bootstrapping a personal blank report.
            try:
                records=[repository.create(f'report-{uuid.uuid4().hex}',title='Untitled report',model=template_model('blank'),metadata={'template_id':'blank'})]
            except PermissionError:
                ui.notify('No reports are available for this account. Ask an owner to share one.',type='warning')
                return
        query_report=str(request.query_params.get('report') or '')
        preferred=query_report or str(page_state.get('visualizer.current_report') or '')
        try: current=repository.get(preferred) if preferred else records[0]
        except Exception: current=records[0]
        page_state['visualizer.current_report']=current.report_id
        current_capabilities=repository.capabilities(current.report_id)
        ppt_template:dict[str,Any]={'name':None,'content':None}

        def session_key(dataset_id: str, raw_session_id: str) -> str:
            return f'{raw_session_id}:{dataset_id}'

        def bound_analysis(dataset_id: str, *, session: Any = None, record: Any = None) -> dict[str, dict[str, Any]]:
            target_record = record or current
            resource = dataset_repository.get_for_report(target_record.report_id, dataset_id)
            active_session = session or dataset_repository.session_for_report(target_record.report_id, dataset_id)
            full = active_session.query(DataQuery(limit=None))
            fields = resource['fields']
            rows = [[row.get(field['id']) for field in fields] for row in full.rows]
            items = [item for item in target_record.model.get('items', []) if isinstance(item, Mapping) and str(item.get('dataset_id')) == str(dataset_id)]
            return analyze_statistical_items(
                report_id=target_record.report_id,
                dataset_id=dataset_id,
                resource_id=str(resource['resource_id']),
                revision=int(resource['revision']),
                fields=fields,
                rows=rows,
                items=items,
                session_id=f'report:{target_record.report_id}',
                filters=active_session.filters,
                source_total=int(resource['row_count']),
                filtered_total=int(full.filtered_total if full.filtered_total is not None else len(rows)),
                complete=True,
            )

        def report_statistical_results(record: Any) -> dict[str, dict[str, Any]]:
            results: dict[str, dict[str, Any]] = {}
            for dataset in record.model.get('datasets', []) if isinstance(record.model, Mapping) else []:
                if not isinstance(dataset, Mapping) or not dataset.get('resource_id'):
                    continue
                results.update(bound_analysis(str(dataset.get('id')), record=record))
            return results

        def export_model(record: Any) -> dict[str, Any]:
            model = json.loads(stable_json(record.model))
            results: dict[str, dict[str, Any]] = {}
            for dataset in model.get('datasets', []):
                if not isinstance(dataset, Mapping):
                    continue
                dataset_id = str(dataset.get('id') or '')
                if dataset.get('resource_id'):
                    key = session_key(dataset_id, f'report:{record.report_id}')
                    active_session = data_sessions.get(key) or dataset_repository.session_for_report(record.report_id, dataset_id)
                    results.update(bound_analysis(dataset_id, session=active_session, record=record))
                else:
                    items = [item for item in record.model.get('items', []) if isinstance(item, Mapping) and str(item.get('dataset_id')) == dataset_id]
                    if not items:
                        continue
                    results.update(analyze_statistical_items(
                        report_id=record.report_id,
                        dataset_id=dataset_id,
                        resource_id='',
                        revision=int(dataset.get('revision') or 0),
                        fields=list(dataset.get('fields') or []),
                        rows=[list(row) for row in dataset.get('rows') or []],
                        items=items,
                        session_id=f'report:{record.report_id}',
                        source_total=len(dataset.get('rows') or []),
                        filtered_total=len(dataset.get('rows') or []),
                        complete=True,
                    ))
            require_valid_statistical_results(results)
            for item in model.get('items', []):
                if isinstance(item, dict) and item.get('id') in results:
                    item['authoritative_analysis'] = results[item['id']]
            return model

        def report_payload(record: Any) -> dict[str, Any]:
            model = dataset_repository.hydrate_model(record.report_id, record.model)
            return {
                **_payload(record,lambda asset_id:f'{STATIC_ROUTE}/report-assets/{asset_id}', model_override=model),
                'capabilities': repository.capabilities(record.report_id).to_dict(),
                'analysis_results': report_statistical_results(record),
            }

        def data_query(session: Any, raw: Mapping[str, Any]) -> dict[str, Any]:
            filters=[]
            for value in raw.get('filters', ()) if isinstance(raw.get('filters'), list) else ():
                if not isinstance(value, Mapping):
                    continue
                try:
                    filters.append(FilterClause(str(value.get('field') or ''), FilterOperation(str(value.get('operation') or 'equals')), value.get('value'), value.get('value2'), str(value.get('filter_id') or '') or None))
                except (TypeError, ValueError):
                    raise VisualizerContractError('invalid dataset filter')
            with session.transaction():
                for clause in filters:
                    session.set_filter(clause)
            sorts=[]
            for value in raw.get('sorts', ()) if isinstance(raw.get('sorts'), list) else ():
                if isinstance(value, Mapping) and value.get('key'):
                    sorts.append(SortClause(str(value['key']), bool(value.get('descending'))))
            query=DataQuery(
                search=str(raw.get('search') or ''),
                search_fields=tuple(str(item) for item in raw.get('search_fields', ()) if item),
                dimensions=tuple(str(item) for item in raw.get('dimensions', ()) if item),
                metrics=tuple(str(item) for item in raw.get('metrics', ()) if item),
                sorts=tuple(sorts), offset=max(0, int(raw.get('offset') or 0)),
                limit=max(1, int(raw['limit'])) if raw.get('limit') is not None else None,
            )
            result=session.query(query)
            return {'rows': list(result.rows), 'total': result.total, 'filtered_total': result.filtered_total, 'revision': result.revision, 'source_revision': result.source_revision}

        async def send(kind: str, payload: Mapping[str,Any]) -> None:
            message={'bridge_version':BRIDGE_VERSION,'type':kind,'payload':dict(payload)}
            await ui.run_javascript(f'window.CompanyUIVisualizerBridge?.receive({json.dumps(message,ensure_ascii=False)})')

        async def activate(record, *, notice: str|None=None) -> None:
            nonlocal current, current_capabilities
            current=record; current_capabilities=repository.capabilities(record.report_id); page_state['visualizer.current_report']=record.report_id
            data_sessions.clear()
            report_select.options=_report_options(repository); report_select.value=record.report_id; report_select.update()
            if report_title is not None:
                report_title.value=record.title; report_title.update()
            if report_description is not None:
                report_description.value=str(record.metadata.get('description') or ''); report_description.update()
            if report_meta is not None:
                report_meta.set_text(f'Created {record.created_at} · Modified {record.updated_at} · revision {record.revision}')
            await send('report.bootstrap',report_payload(record))
            if notice: notifications.success(notice)

        async def handle_semantic(event: Any) -> None:
            nonlocal current
            payload: Mapping[str,Any]={}
            try:
                message=_decode_bridge_event(event); kind=message['type']; payload=message['payload']
                if kind=='report.commit':
                    report_id=str(payload.get('report_id') or '')
                    if report_id != current.report_id: raise VisualizerContractError('commit targets a non-active report')
                    model_value=payload.get('model')
                    if not isinstance(model_value,Mapping): raise VisualizerContractError('commit model is required')
                    canonical=canonical_model(model_value); _validate_model_images(canonical)
                    record=repository.commit(report_id,base_revision=int(payload.get('base_revision')),model=canonical,commit_id=str(payload.get('commit_id') or ''))
                    current=record
                    await send('report.commit_result',{'report_id':record.report_id,'revision':record.revision,'commit_id':str(payload.get('commit_id') or ''),'fingerprint':record.to_dict()['fingerprint']})
                    return
                if kind=='report.save_requested':
                    latest=repository.get(current.report_id); await send('application.notification',{'level':'success','message':f'Saved · revision {latest.revision}'})
                    return
                if kind=='report.history_requested':
                    await open_history()
                    return
                if kind=='preset.preferences_requested':
                    raw=preferences.load().filter_views.get(PRESET_KEY,{})
                    presets=_normalize_presets(raw.get('presets',[])) if isinstance(raw,Mapping) else []
                    await send('preset.preferences_result',{'presets':presets}); return
                if kind=='preset.preferences_save_requested':
                    presets=_normalize_presets(payload.get('presets'))
                    preferences.save_filter_view(PRESET_KEY,{'presets':presets})
                    await send('preset.preferences_result',{'presets':presets,'saved':True}); return
                if kind=='mapping.preferences_requested':
                    raw=preferences.load().filter_views.get(MAPPING_PRESET_KEY,{})
                    presets=_normalize_mapping_presets(raw.get('presets',[])) if isinstance(raw,Mapping) else []
                    await send('mapping.preferences_result',{'presets':presets}); return
                if kind=='mapping.preferences_save_requested':
                    presets=_normalize_mapping_presets(payload.get('presets'))
                    preferences.save_filter_view(MAPPING_PRESET_KEY,{'presets':presets})
                    await send('mapping.preferences_result',{'presets':presets,'saved':True}); return
                if kind=='reuse.preferences_requested':
                    raw=preferences.load().filter_views.get(REUSE_KEY,{})
                    assets=_normalize_reuse_records(raw.get('assets',[])) if isinstance(raw,Mapping) else []
                    datasets=_normalize_reuse_records(raw.get('datasets',[])) if isinstance(raw,Mapping) else []
                    await send('reuse.preferences_result',{'assets':assets,'datasets':datasets}); return
                if kind=='reuse.preferences_save_requested':
                    bucket='datasets' if str(payload.get('bucket') or '')=='datasets' else 'assets'
                    records=_normalize_reuse_records(payload.get('records'))
                    current_library=preferences.load().filter_views.get(REUSE_KEY,{})
                    library={
                        'assets':_normalize_reuse_records(current_library.get('assets',[])) if isinstance(current_library,Mapping) else [],
                        'datasets':_normalize_reuse_records(current_library.get('datasets',[])) if isinstance(current_library,Mapping) else [],
                    }
                    library[bucket]=records
                    preferences.save_filter_view(REUSE_KEY,library)
                    await send('reuse.preferences_result',{'bucket':bucket,'records':records,'assets':library['assets'],'datasets':library['datasets'],'saved':True}); return
                if kind=='ppt.export_requested':
                    repository.require_export(current.report_id)
                    latest=repository.export(current.report_id); output=export_pptx(ppt_template['content'],export_model(latest),asset_data_url=lambda asset_id: repository.asset_data_url(latest.report_id,asset_id))
                    downloads.download(f'{latest.title or "visembler-report"}.pptx',output,media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation')
                    await send('application.notification',{'level':'success','message':'Editable PowerPoint export generated'}); return
                if kind=='dataset.binding_requested':
                    dataset_id=str(payload.get('dataset_id') or '')
                    if not dataset_id: raise VisualizerContractError('dataset_id is required')
                    session_id=str(payload.get('session_id') or dataset_id)
                    key=session_key(dataset_id, session_id)
                    session=data_sessions.get(key)
                    if session is None:
                        session=dataset_repository.session_for_report(current.report_id,dataset_id)
                        data_sessions[key]=session
                    resource=dataset_repository.get_for_report(current.report_id,dataset_id)
                    result=data_query(session,payload)
                    await send('dataset.binding_result',{'report_id':current.report_id,'dataset_id':dataset_id,'session_id':session_id,'resource_id':resource['resource_id'],'schema':resource['schema'],'row_count':resource['row_count'],'analysis_results':bound_analysis(dataset_id,session=session),'result':result}); return
                if kind=='dataset.filter_requested':
                    dataset_id=str(payload.get('dataset_id') or '')
                    session_id=str(payload.get('session_id') or dataset_id)
                    key=session_key(dataset_id, session_id)
                    session=data_sessions.get(key) or dataset_repository.session_for_report(current.report_id,dataset_id)
                    data_sessions[key]=session
                    filter_value=payload.get('filter')
                    if not isinstance(filter_value, Mapping): raise VisualizerContractError('dataset filter is required')
                    resource=dataset_repository.get_for_report(current.report_id,dataset_id)
                    result=data_query(session,{'filters':[filter_value],'offset':payload.get('offset',0),'limit':payload.get('limit')})
                    await send('dataset.binding_result',{'report_id':current.report_id,'dataset_id':dataset_id,'session_id':session_id,'schema':resource['schema'],'row_count':resource['row_count'],'analysis_results':bound_analysis(dataset_id,session=session),'result':result,'request_id':payload.get('request_id')}); return
                if kind=='dataset.filters_requested':
                    dataset_id=str(payload.get('dataset_id') or '')
                    session_id=str(payload.get('session_id') or dataset_id)
                    key=session_key(dataset_id, session_id)
                    session=data_sessions.get(key) or dataset_repository.session_for_report(current.report_id,dataset_id)
                    filters=payload.get('filters')
                    if not isinstance(filters,list): raise VisualizerContractError('dataset filters are required')
                    resource=dataset_repository.get_for_report(current.report_id,dataset_id)
                    with session.transaction():
                        session.clear_filters()
                    result=data_query(session,{'filters':filters,'offset':payload.get('offset',0),'limit':payload.get('limit')})
                    data_sessions[key]=session
                    await send('dataset.binding_result',{'report_id':current.report_id,'dataset_id':dataset_id,'session_id':session_id,'schema':resource['schema'],'row_count':resource['row_count'],'analysis_results':bound_analysis(dataset_id,session=session),'result':result,'request_id':payload.get('request_id')}); return
                if kind=='dataset.reset_requested':
                    dataset_id=str(payload.get('dataset_id') or '')
                    session_id=str(payload.get('session_id') or dataset_id)
                    key=session_key(dataset_id, session_id)
                    session=data_sessions.get(key) or dataset_repository.session_for_report(current.report_id,dataset_id)
                    session.clear_filters(); data_sessions[key]=session
                    resource=dataset_repository.get_for_report(current.report_id,dataset_id)
                    result=data_query(session,{'offset':payload.get('offset',0),'limit':payload.get('limit')})
                    await send('dataset.binding_result',{'report_id':current.report_id,'dataset_id':dataset_id,'session_id':session_id,'schema':resource['schema'],'row_count':resource['row_count'],'analysis_results':bound_analysis(dataset_id,session=session),'result':result,'request_id':payload.get('request_id')}); return
                if kind=='dataset.export_requested':
                    repository.require_export(current.report_id)
                    dataset_id=str(payload.get('dataset_id') or '')
                    if not dataset_id: raise VisualizerContractError('dataset_id is required')
                    export_format=str(payload.get('format') or 'csv').lower()
                    if export_format not in {'csv','tsv'}: raise VisualizerContractError('unsupported dataset export format')
                    scope=str(payload.get('scope') or 'current').lower()
                    if scope not in {'current','full'}: raise VisualizerContractError('unsupported dataset export scope')
                    resource=dataset_repository.get_for_report(current.report_id,dataset_id)
                    if scope=='current':
                        session_id=str(payload.get('session_id') or dataset_id)
                        key=session_key(dataset_id, session_id)
                        session=data_sessions.get(key) or dataset_repository.session_for_report(current.report_id,dataset_id)
                        data_sessions[key]=session
                    else:
                        # A fresh session deliberately ignores the current
                        # report-wide filter state for an explicit full export.
                        session=dataset_repository.session_for_report(current.report_id,dataset_id)
                    result=session.query(DataQuery(limit=None))
                    rows=[dict(row) for row in result.rows]
                    suffix='tsv' if export_format=='tsv' else 'csv'
                    media_type='text/tab-separated-values' if suffix=='tsv' else 'text/csv'
                    filename=f'{_safe_download_stem(current.title)}-{_safe_download_stem(resource.get("name"), "dataset")}.{suffix}'
                    downloads.download(filename,_dataset_export_bytes(resource['fields'],rows,delimiter='\t' if suffix=='tsv' else ','),media_type=media_type)
                    await send('application.notification',{'level':'success','message':f'Exported {scope} dataset ({len(rows):,} rows)'}); return
                if kind=='dataset.resource_requested':
                    dataset_value=payload.get('dataset')
                    if not isinstance(dataset_value, Mapping): raise VisualizerContractError('dataset resource payload is required')
                    dataset_id=str(dataset_value.get('id') or '')
                    if not dataset_id: raise VisualizerContractError('dataset_id is required')
                    source_dataset=next((value for value in current.model.get('datasets',[]) if isinstance(value,Mapping) and str(value.get('id'))==dataset_id),None)
                    if not isinstance(source_dataset,Mapping): raise ReportNotFoundError(dataset_id)
                    if source_dataset.get('resource_id'): raise VisualizerContractError('dataset is already a bound resource')
                    candidate_items=[item for item in current.model.get('items',[]) if isinstance(item,Mapping) and str(item.get('dataset_id'))==dataset_id]
                    candidate_results=analyze_statistical_items(report_id=current.report_id,dataset_id=dataset_id,resource_id='pending',revision=1,fields=list(source_dataset.get('fields') or dataset_value.get('fields') or []),rows=[list(row) for row in source_dataset.get('rows') or dataset_value.get('rows') or []],items=candidate_items,session_id=f'report:{current.report_id}',source_total=len(source_dataset.get('rows') or dataset_value.get('rows') or []),filtered_total=len(source_dataset.get('rows') or dataset_value.get('rows') or []),complete=True)
                    require_valid_statistical_results(candidate_results)
                    resource=dataset_repository.create_for_report(current.report_id,name=str(dataset_value.get('name') or source_dataset.get('name') or 'Bound dataset'),fields=source_dataset.get('fields') or dataset_value.get('fields') or [],rows=source_dataset.get('rows') or dataset_value.get('rows') or [],description=str(dataset_value.get('description') or source_dataset.get('description') or ''),provenance=str((dataset_value.get('source') or source_dataset.get('source') or {}).get('label') if isinstance(dataset_value.get('source') or source_dataset.get('source'),Mapping) else ''),source_metadata=dataset_value.get('source') if isinstance(dataset_value.get('source'),Mapping) else source_dataset.get('source') if isinstance(source_dataset.get('source'),Mapping) else {})
                    try:
                        preview=dataset_store.preview(resource['dataset_id'])
                        external={**dict(source_dataset),'external':True,'resource_id':resource['dataset_id'],'revision':resource['revision'],'fields':preview['fields'],'rows':preview['rows'],'row_count':preview['row_count'],'content_fingerprint':preview['content_fingerprint']}
                        model_value={**dict(current.model),'datasets':[external if str(value.get('id'))==dataset_id else value for value in current.model.get('datasets',[])]}
                        record=repository.commit(current.report_id,base_revision=int(payload.get('base_revision',current.revision)),model=canonical_model(model_value),commit_id=str(payload.get('commit_id') or ''))
                    except Exception:
                        dataset_store.delete(resource['dataset_id'])
                        raise
                    current=record; data_sessions.clear()
                    await send('report.commit_result',{'report_id':record.report_id,'revision':record.revision,'commit_id':str(payload.get('commit_id') or ''),'fingerprint':record.to_dict()['fingerprint']})
                    await send('report.bootstrap',report_payload(record)); return
                if kind=='dataset.resource_refresh_requested':
                    dataset_id=str(payload.get('dataset_id') or '')
                    dataset_value=payload.get('dataset')
                    if not isinstance(dataset_value, Mapping): raise VisualizerContractError('dataset refresh payload is required')
                    if payload.get('selected_only') and len(dataset_consumers := [value for value in current.model.get('items',[]) if isinstance(value,Mapping) and str(value.get('dataset_id'))==dataset_id]) > 1:
                        raise VisualizerContractError('Refresh the linked dataset together before refreshing a shared resource independently')
                    resource_before=dataset_repository.get_for_report(current.report_id,dataset_id)
                    refresh_key=session_key(dataset_id,str(payload.get('session_id') or f'report:{current.report_id}'))
                    refresh_session=data_sessions.get(refresh_key) or dataset_repository.session_for_report(current.report_id,dataset_id)
                    candidate_fields=list(dataset_value.get('fields') or [])
                    candidate_rows=[list(row) for row in dataset_value.get('rows') or []]
                    consumers=[value for value in current.model.get('items',[]) if isinstance(value,Mapping) and str(value.get('dataset_id'))==dataset_id]
                    candidate_results=analyze_statistical_items(report_id=current.report_id,dataset_id=dataset_id,resource_id=str(resource_before['resource_id']),revision=int(resource_before['revision'])+1,fields=candidate_fields,rows=candidate_rows,items=consumers,session_id=f'report:{current.report_id}',filters=refresh_session.filters,source_total=len(candidate_rows),filtered_total=len(candidate_rows),complete=True)
                    require_valid_statistical_results(candidate_results)
                    resource=dataset_repository.replace_for_report(current.report_id,dataset_id,fields=dataset_value.get('fields') or [],rows=dataset_value.get('rows') or [],expected_revision=payload.get('expected_revision'),provenance=str((dataset_value.get('source') or {}).get('label') if isinstance(dataset_value.get('source'),Mapping) else ''),source_metadata=dataset_value.get('source') if isinstance(dataset_value.get('source'),Mapping) else {})
                    try:
                        preview=dataset_store.preview(resource['dataset_id'],revision=resource['revision'])
                        model_value={**dict(current.model),'datasets':[({**dict(value),'revision':resource['revision'],'fields':preview['fields'],'rows':preview['rows'],'row_count':preview['row_count'],'content_fingerprint':preview['content_fingerprint'],'external':True} if isinstance(value,Mapping) and str(value.get('id'))==dataset_id else value) for value in current.model.get('datasets',[])]}
                        record=repository.commit(current.report_id,base_revision=int(payload.get('base_revision',current.revision)),model=canonical_model(model_value),commit_id=str(payload.get('commit_id') or ''))
                    except Exception:
                        # The old report binding remains authoritative if the
                        # report commit fails; the immutable new revision is
                        # retained for deterministic operator recovery.
                        raise
                    current=record; data_sessions.clear()
                    await send('report.commit_result',{'report_id':record.report_id,'revision':record.revision,'commit_id':str(payload.get('commit_id') or ''),'fingerprint':record.to_dict()['fingerprint']})
                    await send('report.bootstrap',report_payload(record)); return
            except RevisionConflictError:
                latest=repository.get(current.report_id); await send('report.conflict',{**report_payload(latest),'rejected_commit_id':str(payload.get('commit_id') or '')})
            except Exception as exc:
                try: latest=repository.get(current.report_id); record_payload=report_payload(latest)
                except Exception: record_payload=None
                await send('report.error',{'message':str(exc)[:400],'commit_id':str(payload.get('commit_id') or ''),**({'report':record_payload} if record_payload else {})})

        async def create_report(template_id: str) -> None:
            spec=REPORT_TEMPLATES.get(template_id); title='New report' if template_id=='blank' else str(spec['name'])
            record=repository.create(f'report-{uuid.uuid4().hex}',title=title,model=template_model(template_id),metadata={'template_id':template_id})
            new_dialog.close(); await activate(record,notice=f'{title} created')

        async def duplicate_current() -> None:
            try:
                latest=repository.get(current.report_id); title=f'{latest.title} copy'[:160]
                record=repository.duplicate(latest.report_id,f'report-{uuid.uuid4().hex}',title=title,metadata={**latest.metadata,'duplicated_from':latest.report_id})
                await activate(record,notice='Report duplicated')
            except Exception as exc: notifications.error(f'Duplicate rejected: {exc}')

        async def rename_report(event: Any) -> None:
            try:
                latest=repository.get(current.report_id); value=str(getattr(event,'value','') or '').strip()
                if value==latest.title: return
                await activate(repository.rename(latest.report_id,title=value,expected_revision=latest.revision),notice='Report renamed')
            except RevisionConflictError: await activate(repository.get(current.report_id),notice='Report changed elsewhere; latest revision loaded')
            except Exception as exc: notifications.error(f'Rename rejected: {exc}')

        async def update_report_description(event: Any) -> None:
            try:
                latest=repository.get(current.report_id); value=str(getattr(event,'value','') or '')
                if value.strip()==str(latest.metadata.get('description') or ''): return
                await activate(repository.update_description(latest.report_id,value,expected_revision=latest.revision),notice='Report description updated')
            except RevisionConflictError: await activate(repository.get(current.report_id),notice='Report changed elsewhere; latest revision loaded')
            except Exception as exc: notifications.error(f'Description update rejected: {exc}')

        async def select_report(event: Any) -> None:
            report_id=str(getattr(event,'value','') or '')
            if report_id and report_id != current.report_id:
                try: ui.navigate.to(f'/visualizer?report={quote(report_id,safe="")}')
                except Exception as exc: notifications.error(f'Unable to open report: {exc}')

        async def delete_current() -> None:
            nonlocal current
            try:
                latest=repository.get(current.report_id); repository.trash_report(latest.report_id,expected_revision=latest.revision)
                remaining=repository.list()
                if not remaining: remaining=[repository.create(f'report-{uuid.uuid4().hex}',title='New report',model=template_model('blank'),metadata={'template_id':'blank'})]
                delete_dialog.close(); await activate(remaining[0],notice='Report moved to trash')
            except Exception as exc: notifications.error(f'Delete rejected: {exc}')

        async def restore_report(report_id: str) -> None:
            try:
                record=repository.restore(report_id); restore_dialog.close(); await activate(record,notice='Report restored')
            except Exception as exc: notifications.error(f'Restore rejected: {exc}')

        async def open_restore() -> None:
            records=repository.list_trash(); restore_select.options={record.report_id:record.title for record in records}; restore_select.value=records[0].report_id if records else None; restore_select.update(); restore_dialog.open()

        async def restore_selected() -> None:
            if restore_select.value: await restore_report(str(restore_select.value))

        def refresh_reports(event: Any=None) -> None:
            query=str(getattr(event,'value','') or '')
            report_select.options=_report_options(repository,query); report_select.value=current.report_id; report_select.update()

        def refresh_manage(event: Any=None) -> None:
            query=str(getattr(manage_search,'value','') or '')
            sort=str(getattr(manage_sort,'value','modified') or 'modified')
            manage_results.set_text(f'{len(_report_options(repository,query,sort))} active match(es) · {len(repository.list_trash())} in trash')

        async def clean_empty() -> None:
            removed=0
            for record in list(repository.list()):
                if record.report_id==current.report_id or record.title!='Untitled report': continue
                try: removed += 1 if repository.delete_if_blank(record.report_id,expected_revision=record.revision) else 0
                except RevisionConflictError: continue
            clean_dialog.close(); report_select.options=_report_options(repository); report_select.update(); notifications.success(f'Removed {removed} empty Untitled report{"s" if removed!=1 else ""}')

        async def open_history() -> None:
            entries=repository.list_history(current.report_id)
            history_select.options={entry['history_id']:f"r{entry['revision']} · {entry.get('label') or 'Saved revision'}" for entry in entries}
            history_select.value=entries[0]['history_id'] if entries else None; history_select.update(); history_dialog.open()

        async def restore_history_selected() -> None:
            if not history_select.value: return
            latest=repository.get(current.report_id)
            await activate(repository.restore_history(latest.report_id,str(history_select.value),expected_revision=latest.revision),notice='Historical revision restored')
            history_dialog.close()

        async def duplicate_history_selected() -> None:
            if not history_select.value: return
            record=repository.duplicate_from_history(current.report_id,str(history_select.value),f'report-{uuid.uuid4().hex}')
            history_dialog.close(); await activate(record,notice='Historical revision duplicated')

        async def create_checkpoint() -> None:
            name=' '.join(str(checkpoint_name.value or '').split())
            if not name: notifications.warning('Enter a checkpoint name first'); return
            latest=repository.get(current.report_id); repository.checkpoint(latest.report_id,name=name,expected_revision=latest.revision)
            checkpoint_name.value=''; checkpoint_name.update(); await open_history(); notifications.success('Checkpoint created')

        async def upload_report(event: Any) -> None:
            try:
                name,content=await _read_upload(event,max_bytes=MODEL_MAX_BYTES)
                value=json.loads(content.decode('utf-8')); model_source=value.get('model',value) if isinstance(value,Mapping) else None
                if not isinstance(model_source,Mapping): raise VisualizerContractError('report JSON must contain a model object')
                canonical=canonical_model(model_source); _validate_model_images(canonical)
                record=repository.create(f'import-{uuid.uuid4().hex}',title=Path(name).stem[:160] or 'Imported report',model=canonical,metadata={'imported_from':name})
                await activate(record,notice='Report imported')
            except Exception as exc: notifications.error(f'Report import rejected: {exc}')

        async def upload_ppt(event: Any) -> None:
            try:
                name,content=await _read_upload(event,max_bytes=PPT_MAX_BYTES); validate_pptx_bytes(content)
                restored=import_visembler_pptx(content)
                if restored is not None:
                    record=repository.create(f'import-{uuid.uuid4().hex}',title=Path(name).stem[:160] or 'Imported Visembler report',model=restored,metadata={'imported_from':name,'semantic_pptx':True})
                    import_dialog.close(); await activate(record,notice='Visembler PowerPoint restored as an editable report'); return
                ppt_template.update(name=name,content=content); notifications.success('PowerPoint template loaded for export')
            except Exception as exc: notifications.error(f'PowerPoint rejected: {exc}')

        async def open_manage_reports() -> None:
            active_count=len(repository.list())
            trash_count=len(repository.list_trash())
            manage_current.set_text(f'Current · {current.title}')
            manage_counts.set_text(f'{active_count} active report{"s" if active_count!=1 else ""} · {trash_count} in trash · history is retained per active report')
            manage_search.value=''; manage_search.update(); manage_sort.value='modified'; manage_sort.update()
            manage_results.set_text(f'{active_count} active match(es) · {trash_count} in trash')
            manage_dialog.open()

        async def export_current_json() -> None:
            repository.require_export(current.report_id)
            latest=repository.get(current.report_id)
            payload=stable_json({'report_id':latest.report_id,'title':latest.title,'description':latest.metadata.get('description',''),'revision':latest.revision,'model':latest.model}).encode('utf-8')
            downloads.download(f'{latest.title or "visembler-report"}.json',payload,media_type='application/json')

        async def manage_duplicate() -> None:
            manage_dialog.close()
            await duplicate_current()

        async def manage_history() -> None:
            manage_dialog.close()
            await open_history()

        def manage_import() -> None:
            manage_dialog.close()
            import_dialog.open()

        def manage_trash() -> None:
            manage_dialog.close()
            delete_dialog.open()

        async def manage_restore() -> None:
            manage_dialog.close()
            await open_restore()

        def manage_cleanup() -> None:
            manage_dialog.close()
            clean_dialog.open()

        report_title=None; report_description=None; report_meta=None
        can_create='report.create' in runtime.authorization.effective_permissions(repository.principal) or 'administration' in runtime.authorization.effective_permissions(repository.principal)
        with AppShell('Visembler',NAVIGATION,active_route='/visualizer',sidebar=SidebarMode.COMPACT,environment=None,subtitle='Visual report authoring',owner='Visembler'):
            # company-ui: allow-ai005 — dialogs are isolated compatibility hosts for the report-authoring module.
            new_dialog=ui.dialog()
            with new_dialog:
                # company-ui: allow-ai005 — see dialog compatibility host above.
                with ui.card().classes('cui-dialog-card'):
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    ui.label('New report').classes('cui-dialog-title')
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    ui.label('Start with a genuinely blank canvas or a governed editable template.').classes('cui-field-description')
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    with ui.button(on_click=lambda: create_report('blank')).props('flat no-caps').classes('cui-report-template'):
                        # company-ui: allow-ai005 — template-card label inside the compatibility host.
                        ui.label('Blank canvas').classes('cui-report-template-title')
                        # company-ui: allow-ai005 — template-card description inside the compatibility host.
                        ui.label('Start with an empty, editable report.').classes('cui-report-template-description')
                    for template_id,spec in REPORT_TEMPLATES.items():
                        async def _choose(_event=None, template_id=template_id): await create_report(template_id)
                        # company-ui: allow-ai005 — see dialog compatibility host above.
                        with ui.button(on_click=_choose).props('flat no-caps').classes('w-full cui-report-template'):
                            # company-ui: allow-ai005 — see dialog compatibility host above.
                            ui.label(str(spec['name'])).classes('cui-report-template-title'); ui.label(str(spec['description'])).classes('cui-report-template-description')
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    ui.button('Cancel',on_click=new_dialog.close).props('flat no-caps')
            # company-ui: allow-ai005 — dialogs are isolated compatibility hosts for the report-authoring module.
            delete_dialog=ui.dialog()
            with delete_dialog:
                # company-ui: allow-ai005 — see dialog compatibility host above.
                with ui.card().classes('cui-dialog-card'):
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    ui.label('Move report to trash?').classes('cui-dialog-title'); ui.label('The report can be restored until its trash entry is removed from storage.').classes('cui-field-description')
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    ui.button('Move to trash',on_click=delete_current).props('unelevated no-caps color=negative'); ui.button('Cancel',on_click=delete_dialog.close).props('flat no-caps')
            # company-ui: allow-ai005 — dialog remains inside the isolated report-authoring compatibility host.
            restore_dialog=ui.dialog()
            with restore_dialog:
                # company-ui: allow-ai005 — see dialog compatibility host above.
                with ui.card().classes('cui-dialog-card'):
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    ui.label('Restore report').classes('cui-dialog-title'); ui.label('Recently trashed reports').classes('cui-field-description')
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    restore_select=ui.select(label='Trashed reports',options={}).props('outlined dense hide-bottom-space')
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    ui.button('Restore report',on_click=restore_selected).props('unelevated no-caps'); ui.button('Cancel',on_click=restore_dialog.close).props('flat no-caps')
            # company-ui: allow-ai005 — dialogs are isolated compatibility hosts for the report-authoring module.
            clean_dialog=ui.dialog()
            with clean_dialog:
                # company-ui: allow-ai005 — see dialog compatibility host above.
                with ui.card().classes('cui-dialog-card'):
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    ui.label('Clean up empty reports?').classes('cui-dialog-title'); ui.label('Remove other genuinely blank Untitled reports. The current report is always preserved.').classes('cui-field-description')
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    ui.button('Clean up empty reports',on_click=clean_empty).props('unelevated no-caps'); ui.button('Cancel',on_click=clean_dialog.close).props('flat no-caps')
            # company-ui: allow-ai005 — dialog remains inside the isolated report-authoring compatibility host.
            history_dialog=ui.dialog()
            with history_dialog:
                # company-ui: allow-ai005 — see dialog compatibility host above.
                with ui.card().classes('cui-dialog-card'):
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    ui.label('Report history').classes('cui-dialog-title'); ui.label('Restore creates a new revision; saved history remains intact.').classes('cui-field-description')
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    history_select=ui.select(label='Revision',options={}).props('outlined dense hide-bottom-space')
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    checkpoint_name=ui.input(label='Checkpoint name',placeholder='Before review',value='Review checkpoint').props('outlined dense hide-bottom-space')
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    checkpoint_button=ui.button('Save checkpoint',on_click=create_checkpoint).props('flat no-caps')
                    checkpoint_name.on_value_change(lambda event,button=checkpoint_button:button.enable() if str(event.value or '').strip() else button.disable())
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    ui.button('Restore revision',on_click=restore_history_selected).props('unelevated no-caps')
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    ui.button('Duplicate revision',on_click=duplicate_history_selected).props('flat no-caps')
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    ui.button('Close',on_click=history_dialog.close).props('flat no-caps')
            # company-ui: allow-ai005 — dialogs are isolated compatibility hosts for the report-authoring module.
            import_dialog=ui.dialog()
            with import_dialog:
                # company-ui: allow-ai005 — see dialog compatibility host above.
                with ui.card().classes('cui-dialog-card cui-visualizer-import-card'):
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    ui.label('Import').classes('cui-dialog-title')
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    ui.label('Import a Visembler report from its canonical JSON file.').classes('cui-field-description')
                    # company-ui: allow-ai004 — upload controls require an isolated layout host for both validated upload adapters.
                    with ui.column().classes('w-full gap-3'):
                        FileUpload(label='Visembler report JSON',accept=('.json',),max_file_size_mb=2,on_upload=upload_report)
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    ui.button('Done',on_click=import_dialog.close).props('flat no-caps')

            # company-ui: allow-ai005 — report lifecycle manager remains inside the isolated authoring host.
            manage_dialog=ui.dialog()
            with manage_dialog:
                # company-ui: allow-ai005 — see isolated authoring host above.
                with ui.card().classes('cui-dialog-card'):
                    # company-ui: allow-ai005 — see isolated authoring host above.
                    ui.label('Manage reports').classes('cui-dialog-title')
                    # company-ui: allow-ai005 — dynamic report identity in the isolated compatibility host.
                    manage_current=ui.label('').classes('cui-field-description')
                    # company-ui: allow-ai005 — dynamic report counts in the isolated compatibility host.
                    manage_counts=ui.label('').classes('cui-field-description')
                    manage_search=ui.input(label='Search active reports',on_change=refresh_manage).props('outlined dense hide-bottom-space').classes('w-full')
                    manage_sort=ui.select(label='Sort',options={'modified':'Recently modified','created':'Recently created','title':'Title'},value='modified',on_change=refresh_manage).props('outlined dense hide-bottom-space').classes('w-full')
                    manage_results=ui.label('').classes('cui-field-description')
                    # company-ui: allow-ai005 — primary reuse action.
                    ui.button('Duplicate current report',on_click=manage_duplicate).props('unelevated no-caps')
                    ui.button('Export current JSON',on_click=export_current_json).props('flat no-caps')
                    # company-ui: allow-ai005 — existing history workflow.
                    ui.button('Report history',on_click=manage_history).props('flat no-caps')
                    # company-ui: allow-ai005 — existing canonical JSON import workflow.
                    ui.button('Import…',on_click=manage_import).props('flat no-caps')
                    # company-ui: allow-ai005 — restore remains reversible.
                    ui.button('Restore trashed report…',on_click=manage_restore).props('flat no-caps')
                    # company-ui: allow-ai005 — cleanup only removes empty legacy Untitled reports.
                    ui.button('Clean up empty reports',on_click=manage_cleanup).props('flat no-caps')
                    # company-ui: allow-ai005 — destructive action remains confirmation-gated.
                    ui.button('Move current to trash…',on_click=manage_trash).props('outline no-caps color=negative')
                    # company-ui: allow-ai005 — dismiss manager.
                    ui.button('Close',on_click=manage_dialog.close).props('flat no-caps')

            # company-ui: allow-ai004 — the editor is an isolated application-owned canvas host.
            with ui.column().classes('cui-page cui-page--full cui-visualizer-workspace w-full').props(f'data-report-read-only="{str(current_capabilities.read_only).lower()}"'):
                # company-ui: allow-ai005 — the report-control strip is part of the isolated editor host.
                with ui.element('section').classes('cui-visualizer-reportbar w-full').props('aria-label="Report controls"'):
                    # company-ui: allow-ai005 — report title is the primary identity control.
                    if current_capabilities.read_only:
                        ui.label(current.title).classes('cui-visualizer-report-title cui-report-read-only-title')
                        ui.label('Read-only').classes('cui-report-read-only-indicator')
                        ui.label(str(current.metadata.get('description') or '')).classes('cui-visualizer-report-description cui-report-read-only-description')
                    else:
                        report_title=ui.input(label='Report title',value=current.title,on_change=rename_report,placeholder='Untitled report').props('outlined dense hide-bottom-space').classes('cui-visualizer-report-title')
                        report_description=ui.input(label='Description',value=str(current.metadata.get('description') or ''),on_change=update_report_description,placeholder='What this report is for').props('outlined dense hide-bottom-space').classes('cui-visualizer-report-description')
                    report_meta=ui.label(f'Created {current.created_at} · Modified {current.updated_at} · revision {current.revision}').classes('cui-visualizer-report-meta')
                    # company-ui: allow-ai005 — searchable report switcher replaces a separate filter field.
                    report_select=ui.select(label='Reports',options=_report_options(repository),value=current.report_id,on_change=select_report).props('outlined dense options-dense hide-bottom-space use-input input-debounce=0').classes('cui-visualizer-report-select')
                    # company-ui: allow-ai005 — frequent creation remains one click away.
                    if can_create: ui.button('New report',on_click=new_dialog.open).props('unelevated no-caps')
                    # company-ui: allow-ai005 — report reuse remains a primary action.
                    if current_capabilities.can_duplicate: ui.button('Duplicate',on_click=duplicate_current).props('flat no-caps')
                    # Report lifecycle is a separate route so it never obscures the active canvas.
                    ui.button('Manage',on_click=lambda:ui.navigate.to(f'/visualizer/reports?report={quote(current.report_id,safe="")}')).props('flat no-caps data-testid="manage-reports"').tooltip('Open the dedicated report hub')
                # company-ui: allow-ai005 — the editor mount point is an isolated application-owned canvas host.
                host=ui.element('div').classes('cui-visualizer-host w-full').props('aria-label="Visembler report editor"')
                host.on('visualizer_bridge',handle_semantic,args=['detail'])
                with host: ui.html((ASSETS/'integrated_editor.html').read_text(encoding='utf-8'),sanitize=False)

        css_url=f'{STATIC_ROUTE}/assets/integrated_editor.css?v={build}'
        token_url=f'{STATIC_ROUTE}/assets/tokens.css?v={build}'
        module_url=f'{STATIC_ROUTE}/assets/integrated_editor.mjs?v={build}'
        ui.add_head_html(f'<link rel="stylesheet" href="{token_url}"><link rel="stylesheet" href="{css_url}">')
        # Cold loads must resolve stored media just like activate()/conflict payloads.
        # Keep asset IDs canonical; add renderable URLs only to the browser copy.
        bootstrap={
            **_payload(current,lambda asset_id:f'{STATIC_ROUTE}/report-assets/{asset_id}'),
            'asset_build':build,
            # Reopen must hydrate the same governed statistical result as the
            # live report/bootstrap and export paths. A resource-backed report
            # cannot safely reconstruct statistics from its 250-row preview.
            **({
                'analysis_results': report_statistical_results(current),
            } if any(isinstance(dataset, Mapping) and dataset.get('resource_id') for dataset in current.model.get('datasets', [])) else {}),
        }
        _bootstrap_editor(ui,bootstrap,build,module_url,capabilities=current_capabilities.to_dict())
