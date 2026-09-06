from __future__ import annotations

import base64
import hashlib
import inspect
import io
import json
import os
import uuid
from html import escape as html_escape
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote

from company_ui.integrations.nicegui_components import FileUpload
from company_ui.integrations.nicegui_layout import AppShell
from company_ui.integrations.nicegui_state import NiceGUIStateServices
from company_ui.layouts.models import SidebarMode
from company_ui.navigation import NavItem, NavigationModel, NavSection

from .domain import BRIDGE_MAX_BYTES, MODEL_MAX_BYTES, RevisionConflictError, VisualizerContractError, canonical_model, stable_json
from .files import PPT_MAX_BYTES, validate_image_bytes, validate_pptx_bytes
from .ppt_service import export_pptx, import_visembler_pptx
from .repository import ReportRepository
from .templates import REPORT_TEMPLATES, template_model

PRODUCT = Path(__file__).resolve().parent
ASSETS = PRODUCT / 'assets'
VENDOR = PRODUCT / 'vendor' / 'production_core'
STATIC_ROUTE = '/_cui_visualizer'
BRIDGE_VERSION = 1
PRESET_KEY = 'visualizer.personal_presets'
MAPPING_PRESET_KEY = 'visualizer.data_mapping_presets'
MAX_PRESETS = 50
MAX_PRESET_BYTES = 1_500_000
MAX_MAPPING_PRESET_BYTES = 100_000
_ALLOWED_EVENTS = {
    'report.commit','report.save_requested','preset.preferences_requested','preset.preferences_save_requested','mapping.preferences_requested','mapping.preferences_save_requested',
    'ppt.export_requested','dataset.binding_requested','report.history_requested',
}
_MAPPING_VIEWS={'bar','line','table','timeline','diagram','diagram_flow','engineering','wafer'}
_MAPPING_ROLES={'category','value','x','y','series','time','source','target','weight','subgroup','specification_low','specification_high','lower_limit','upper_limit','die_x','die_y','wafer_id','lot_id','tool','chamber','recipe','process','product','bin','label','size','color','tooltip'}

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
NAVIGATION = NavigationModel((NavSection('workspace','Workspace',(NavItem('visualizer','Visembler','/visualizer','chart-line'),NavItem('visualizer-reports','Reports','/visualizer/reports','folder'))),))


def _asset_build() -> str:
    h=hashlib.sha256()
    asset_names=('tokens.css','integrated_editor.css','integrated_editor.html','diagram_studio.html','diagram_studio.css','chart_studio.html','chart_studio.css','authoring_contracts.mjs','authoring_data.mjs','authoring_mapping_presets.mjs','authoring_dataset_refresh.mjs','authoring_portability.mjs','authoring_intake_client.mjs','authoring_values.mjs','authoring_format.mjs','authoring_selection.mjs','authoring_arrange.mjs','authoring_clipboard.mjs','authoring_reuse.mjs','authoring_presets.mjs','authoring_style.mjs','authoring_batch.mjs','authoring_data_worker.mjs','authoring_transforms.mjs','authoring_performance.mjs','authoring_geometry.mjs','authoring_grid.mjs','production_library.mjs','element_renderer.mjs','authoring_diagram_studio.mjs','diagram_studio.mjs','authoring_chart_studio.mjs','chart_studio.mjs','integrated_editor.mjs')
    paths=[ASSETS/name for name in asset_names]
    paths.extend(sorted((VENDOR/'core').glob('*.mjs')))
    for path in paths:
        h.update(path.relative_to(PRODUCT).as_posix().encode())
        h.update(path.read_bytes())
    return h.hexdigest()[:16]


def _bootstrap_editor(ui: Any, bootstrap: Mapping[str, Any], build: str, module_url: str) -> None:
    script=f'''window.__CUI_VISUALIZER_BOOTSTRAP__={json.dumps(bootstrap,ensure_ascii=False)};window.__CUI_VISUALIZER_ASSET_BUILD__={json.dumps(build)};import({json.dumps(module_url)}).catch(error=>{{console.error(error);const root=document.querySelector('.cui-visualizer-root');if(root)root.dataset.editorReady='failed';}});'''
    ui.run_javascript(script)


def _payload(record, asset_url: Any=None) -> dict[str, Any]:
    model=record.model
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
    needle=' '.join(str(query).split()).casefold(); records=repository.list()
    if sort=='title': records=sorted(records,key=lambda record:(record.title.casefold(),record.report_id))
    elif sort=='created': records=sorted(records,key=lambda record:(record.created_at,record.report_id),reverse=True)
    counts:dict[str,int]={}
    for record in records:
        blank=not record.model.get('items') and not record.model.get('groups')
        label='New blank report' if record.title=='Untitled report' and blank else record.title
        counts[label]=counts.get(label,0)+1
    result={}
    for record in records:
        blank=not record.model.get('items') and not record.model.get('groups')
        label='New blank report' if record.title=='Untitled report' and blank else record.title
        description=str(record.metadata.get('description') or '')
        if needle and needle not in label.casefold() and needle not in record.report_id.casefold() and needle not in description.casefold(): continue
        if counts[label]>1:
            label=f'{label}{" · blank" if blank else ""} · {record.report_id[-6:]}'
        result[record.report_id]=label
    return result


def _report_thumbnail_markup(model: Mapping[str,Any], title: str='Report') -> str:
    """Render a small, content-safe report preview for the report hub."""
    items=[entry for entry in model.get('items',[]) if isinstance(entry,Mapping)]
    colors=('#2f80ed','#63b3ed','#86c5a5','#f2b84b','#a78bfa','#ef8f8f')
    blocks=[]
    for index,entry in enumerate(items[:8]):
        x=8+(index%3)*31; y=10+(index//3)*25; w=25 if index%3 else 28; h=18 if index%3 else 20
        blocks.append(f'<span class="cui-report-thumb-block" style="left:{x}%;top:{y}%;width:{w}%;height:{h}%;background:{colors[index%len(colors)]}"></span>')
    if not blocks: blocks=['<span class="cui-report-thumb-empty">Blank canvas</span>']
    return f'<div class="cui-report-thumb" role="img" aria-label="Preview of {html_escape(title)}">{"".join(blocks)}</div>'


def _history_diff_summary(before: Mapping[str,Any], after: Mapping[str,Any]) -> str:
    before_items={str(entry.get('id')):entry for entry in before.get('items',[]) if isinstance(entry,Mapping)}
    after_items={str(entry.get('id')):entry for entry in after.get('items',[]) if isinstance(entry,Mapping)}
    added=len(set(after_items)-set(before_items)); removed=len(set(before_items)-set(after_items)); changed=sum(before_items[key]!=after_items[key] for key in set(before_items)&set(after_items))
    data='data changed' if before.get('datasets')!=after.get('datasets') else 'data unchanged'
    mapping='mapping changed' if any(before_items.get(key,{}).get('mapping')!=after_items.get(key,{}).get('mapping') for key in set(before_items)&set(after_items)) else 'mapping unchanged'
    style_keys={'style','presentation','theme','accent'}
    style='style changed' if any(any(before_items.get(key,{}).get(field)!=after_items.get(key,{}).get(field) for field in style_keys) for key in set(before_items)&set(after_items)) else 'style unchanged'
    return f'+{added} / −{removed} elements · {changed} changed · {data} · {mapping} · {style}'


def register_visualizer(app: Any, ui: Any, repository: ReportRepository) -> None:
    if getattr(app,'_company_ui_visualizer_registered',False): return
    app._company_ui_visualizer_registered=True
    build=_asset_build()
    app.add_static_files(f'{STATIC_ROUTE}/assets',str(ASSETS),follow_symlink=False,max_cache_age=0)
    app.add_static_files(f'{STATIC_ROUTE}/vendor/production_core',str(VENDOR),follow_symlink=False,max_cache_age=0)

    from fastapi.responses import RedirectResponse
    @app.get('/',include_in_schema=False)
    async def _root_redirect(): return RedirectResponse('/visualizer',status_code=307)

    from fastapi.responses import Response
    @app.get(f'{STATIC_ROUTE}/report-assets/{{asset_id}}',include_in_schema=False)
    async def _report_asset(asset_id: str):
        data=repository.assets.read_image(asset_id); mime=str(validate_image_bytes(data)['mime'])
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
        report_id=str(request.query_params.get('report') or '').strip()
        element_id=str(request.query_params.get('element') or '').strip()
        chart_engines={'CoreChartEngine','EngineeringChartEngine','WaferFabEngine'}
        try:
            current=repository.get(report_id)
            entry=next(item for item in current.model.get('items',[]) if isinstance(item,Mapping) and str(item.get('id'))==element_id)
            if entry.get('engine') not in chart_engines: raise VisualizerContractError('Chart Studio requires a chart, engineering chart, or Wafer Map element')
            datasets=current.model.get('datasets',[])
            dataset=next((item for item in datasets if isinstance(item,Mapping) and str(item.get('id'))==str(entry.get('dataset_id'))),{})
            chart_model=entry.get('chart_studio') if isinstance(entry.get('chart_studio'),Mapping) else {'chart_type':entry.get('element'),'mapping':entry.get('mapping',{}),'dataset':dataset,'data':entry.get('data',[]),'rows':entry.get('rows',[])}
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
        query_report=str(request.query_params.get('report') or '')
        history_report_id=query_report or str(page_state.get('visualizer.current_report') or '')
        delete_target={'report_id':None,'revision':None}; restore_target={'report_id':None,'history_id':None}

        ui.add_head_html('''<style>
          .cui-report-hub{max-width:1440px;margin:0 auto;padding:var(--cui-space-8) var(--cui-space-8) var(--cui-space-16);display:grid;gap:var(--cui-space-5)}
          .cui-report-hub-head{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap}
          .cui-report-hub-head h1{margin:0;font-size:var(--cui-font-size-32);letter-spacing:-.04em}.cui-report-hub-head p{margin:var(--cui-space-1) 0 0;color:#69717d}
          .cui-report-hub-toolbar{display:flex;gap:var(--cui-space-2);align-items:center;flex-wrap:wrap;padding:var(--cui-space-3);border:1px solid #dfe4eb;border-radius:var(--cui-radius-control);background:#fff}
          .cui-report-hub-toolbar>*{min-width:150px}.cui-report-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:var(--cui-space-3)}
          .cui-report-card,.cui-history-card{display:grid;gap:var(--cui-space-2);padding:var(--cui-space-3);border:1px solid #dfe4eb;border-radius:var(--cui-radius-surface);background:#fff;box-shadow:0 2px 10px rgba(30,55,90,.05)}
          .cui-report-card h2{margin:0;font-size:var(--cui-font-size-16)}.cui-report-card small,.cui-history-card small{color:#69717d;line-height:var(--cui-line-height-ratio-1_35)}
          .cui-report-card .q-field{min-width:0}.cui-report-card .q-field__control{min-height:36px!important;height:36px!important}.cui-report-card .q-field__native{font-size:var(--cui-font-size-13)!important}
          .cui-report-card-actions,.cui-history-actions{display:flex;gap:var(--cui-space-1);flex-wrap:wrap}.cui-report-card-actions .q-btn,.cui-history-actions .q-btn{min-height:34px}
          .cui-report-thumb{height:132px;position:relative;overflow:hidden;border-radius:var(--cui-radius-control);background:linear-gradient(135deg,#f4f7fb,#e9eff7);border:1px solid #dfe4eb}
          .cui-report-thumb-block{position:absolute;display:block;border-radius:var(--cui-radius-micro);opacity:.86}.cui-report-thumb-empty{position:absolute;inset:0;display:grid;place-items:center;color:#69717d;font-size:var(--cui-font-size-12)}
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
                source=repository.get(report_id); record=repository.create(f'report-{uuid.uuid4().hex}',title=f'{source.title} copy'[:160],model=source.model,metadata={**source.metadata,'duplicated_from':source.report_id})
                notifications.success('Report duplicated'); history_report_id=record.report_id; render_cards.refresh(); render_history.refresh()
            except Exception as exc: notifications.error(f'Duplicate rejected: {exc}')

        async def rename_hub_report(report_id: str,event: Any) -> None:
            try:
                latest=repository.get(report_id); value=str(getattr(event,'value','') or '')
                if value.strip()!=latest.title: repository.rename(report_id,value,expected_revision=latest.revision); notifications.success('Report renamed'); render_cards.refresh()
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
            record=repository.get(report_id); payload=stable_json({'report_id':record.report_id,'title':record.title,'description':record.metadata.get('description',''),'revision':record.revision,'model':record.model}).encode('utf-8'); downloads.download(f'{record.title or "visembler-report"}.json',payload,media_type='application/json')

        async def checkpoint_hub(report_id: str,field: Any) -> None:
            try:
                record=repository.get(report_id); repository.checkpoint(report_id,str(field.value or ''),expected_revision=record.revision); field.value=''; field.update(); notifications.success('Named checkpoint saved'); render_history.refresh()
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

        @ui.refreshable
        def render_cards() -> None:
            needle=' '.join(str(search.value or '').split()).casefold(); view=str(view_filter.value or 'active'); active=sorted_records(repository.list()); trash=sorted_records(repository.list_trash())
            def matches(record): return not needle or needle in record.title.casefold() or needle in record.report_id.casefold() or needle in str(record.metadata.get('description') or '').casefold()
            if view in {'active','all'}:
                visible=[record for record in active if matches(record)]
                with ui.element('section').classes('cui-report-hub-section'):
                    ui.label(f'Active reports · {len(visible)}').classes('text-h6')
                    if not visible: ui.label('No active reports match this search.').classes('cui-report-hub-empty')
                    else:
                        with ui.element('div').classes('cui-report-grid'):
                            for record in visible:
                                with ui.card().classes('cui-report-card'):
                                    ui.html(_report_thumbnail_markup(record.model,record.title),sanitize=False)
                                    ui.input(value=record.title,label='Title',on_change=lambda event,rid=record.report_id:rename_hub_report(rid,event)).props('outlined dense hide-bottom-space').classes('w-full')
                                    ui.input(value=str(record.metadata.get('description') or ''),label='Description',placeholder='What this report is for',on_change=lambda event,rid=record.report_id:describe_hub_report(rid,event)).props('outlined dense hide-bottom-space').classes('w-full')
                                    ui.label(f'Created {record.created_at} · Modified {record.updated_at} · revision {record.revision} · {len(record.model.get("items",[]))} elements').classes('text-caption')
                                    with ui.row().classes('cui-report-card-actions'):
                                        ui.button('Open',on_click=lambda rid=record.report_id:ui.navigate.to(hub_url(rid))).props('unelevated no-caps')
                                        ui.button('Duplicate',on_click=lambda rid=record.report_id:duplicate_hub_report(rid)).props('flat no-caps')
                                        ui.button('History',on_click=lambda rid=record.report_id:select_history(rid)).props('flat no-caps')
                                        ui.button('Export JSON',on_click=lambda rid=record.report_id:export_hub_json(rid)).props('flat no-caps')
                                        ui.button('Move to trash',on_click=lambda rid=record.report_id:begin_trash(rid)).props('flat no-caps color=negative')
            if view in {'trash','all'}:
                visible=[record for record in trash if matches(record)]
                with ui.element('section').classes('cui-report-hub-section'):
                    ui.label(f'Trash · {len(visible)}').classes('text-h6')
                    if not visible: ui.label('Trash is empty.').classes('cui-report-hub-empty')
                    else:
                        with ui.element('div').classes('cui-report-grid'):
                            for record in visible:
                                with ui.card().classes('cui-report-card'):
                                    ui.html(_report_thumbnail_markup(record.model,record.title),sanitize=False); ui.label(record.title).classes('text-subtitle1'); ui.label(f'Moved from active storage · revision {record.revision} · {len(record.model.get("items",[]))} elements').classes('text-caption')
                                    with ui.row().classes('cui-report-card-actions'):
                                        ui.button('Restore',on_click=lambda rid=record.report_id:restore_hub_report(rid)).props('unelevated no-caps'); ui.button('Export JSON',on_click=lambda rid=record.report_id:export_hub_json(rid)).props('flat no-caps')

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
                checkpoint=ui.input(label='Named checkpoint',placeholder='Before review').props('outlined dense hide-bottom-space')
                ui.button('Save checkpoint',on_click=lambda rid=record.report_id,field=checkpoint:checkpoint_hub(rid,field)).props('flat no-caps')
                if not entries: ui.label('No saved revisions yet.').classes('cui-report-hub-empty')
                else:
                    with ui.element('div').classes('cui-history-list'):
                        for entry in entries[:40]:
                            try: snapshot=repository.get_history(record.report_id,str(entry['history_id'])); historical=snapshot.get('model',{})
                            except Exception: continue
                            summary=f'r{entry["revision"]} · {entry.get("updated_at") or "timestamp unavailable"} · {entry.get("label") or "Saved revision"}{" · checkpoint" if entry.get("checkpoint") else ""}'
                            with ui.card().classes('cui-history-card'):
                                ui.html(_report_thumbnail_markup(historical,f'{record.title} revision {entry["revision"]}'),sanitize=False)
                                with ui.element('div').classes('cui-history-card-copy'):
                                    ui.label(summary).classes('text-subtitle2'); ui.label(_history_diff_summary(record.model,historical)).classes('text-caption')
                                    with ui.row().classes('cui-history-actions'):
                                        ui.button('Restore this revision',on_click=lambda rid=record.report_id,hid=entry['history_id'],s=summary:begin_history_restore(rid,str(hid),s)).props('unelevated no-caps')
                                        ui.button('Duplicate as new report',on_click=lambda rid=record.report_id,hid=entry['history_id']:duplicate_hub_history(rid,str(hid))).props('flat no-caps')

        import_hub_dialog=ui.dialog()
        with AppShell('Visembler',NAVIGATION,active_route='/visualizer/reports',sidebar=SidebarMode.COMPACT,environment=None,subtitle='Report hub',owner='Visembler'):
            with ui.column().classes('cui-report-hub w-full'):
                with ui.element('header').classes('cui-report-hub-head'):
                    with ui.column().classes('gap-0'):
                        ui.label('Reports').classes('text-h3'); ui.label('Open, organize, and recover reports without covering the authoring canvas.').classes('text-body1')
                    ui.button('Open editor',on_click=lambda:ui.navigate.to(hub_url(history_report_id) if history_report_id else '/visualizer')).props('flat no-caps')
                    ui.button('Import…',on_click=import_hub_dialog.open).props('flat no-caps')
                with ui.element('section').classes('cui-report-hub-toolbar'):
                    search=ui.input(label='Search reports',placeholder='Title, description, or report ID',on_change=lambda _event:render_cards.refresh()).props('outlined dense hide-bottom-space').classes('flex-grow')
                    sort_select=ui.select(label='Sort',options={'modified':'Recently modified','created':'Recently created','title':'Title'},value='modified',on_change=lambda _event:render_cards.refresh()).props('outlined dense hide-bottom-space')
                    view_filter=ui.select(label='View',options={'active':'Active','all':'Active + trash','trash':'Trash'},value='active',on_change=lambda _event:render_cards.refresh()).props('outlined dense hide-bottom-space')
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
        records=repository.list()
        if not records:
            records=[repository.create('default',title='Untitled report',model=template_model('blank'),metadata={'template_id':'blank'})]
        query_report=str(ui.context.client.request.query_params.get('report') or '')
        preferred=query_report or str(page_state.get('visualizer.current_report') or '')
        current=next((record for record in records if record.report_id==preferred),records[0]); page_state['visualizer.current_report']=current.report_id
        ppt_template:dict[str,Any]={'name':None,'content':None}

        async def send(kind: str, payload: Mapping[str,Any]) -> None:
            message={'bridge_version':BRIDGE_VERSION,'type':kind,'payload':dict(payload)}
            await ui.run_javascript(f'window.CompanyUIVisualizerBridge?.receive({json.dumps(message,ensure_ascii=False)})')

        async def activate(record, *, notice: str|None=None) -> None:
            nonlocal current
            current=record; page_state['visualizer.current_report']=record.report_id
            report_select.options=_report_options(repository); report_select.value=record.report_id; report_select.update()
            report_title.value=record.title; report_title.update()
            report_description.value=str(record.metadata.get('description') or ''); report_description.update()
            report_meta.set_text(f'Created {record.created_at} · Modified {record.updated_at} · revision {record.revision}')
            await send('report.bootstrap',_payload(record,lambda asset_id:f'{STATIC_ROUTE}/report-assets/{asset_id}'))
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
                if kind=='ppt.export_requested':
                    latest=repository.get(current.report_id); output=export_pptx(ppt_template['content'],latest.model,asset_data_url=repository.assets.data_url)
                    downloads.download(f'{latest.title or "visembler-report"}.pptx',output,media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation')
                    await send('application.notification',{'level':'success','message':'Editable PowerPoint export generated'}); return
                if kind=='dataset.binding_requested':
                    await send('report.error',{'message':'Dataset binding is unavailable until a Company UI Dataset/DataSession is attached to this report.'}); return
            except RevisionConflictError:
                latest=repository.get(current.report_id); await send('report.conflict',{**_payload(latest,lambda asset_id:f'{STATIC_ROUTE}/report-assets/{asset_id}'),'rejected_commit_id':str(payload.get('commit_id') or '')})
            except Exception as exc:
                try: latest=repository.get(current.report_id); record_payload=_payload(latest,lambda asset_id:f'{STATIC_ROUTE}/report-assets/{asset_id}')
                except Exception: record_payload=None
                await send('report.error',{'message':str(exc)[:400],'commit_id':str(payload.get('commit_id') or ''),**({'report':record_payload} if record_payload else {})})

        async def create_report(template_id: str) -> None:
            spec=REPORT_TEMPLATES.get(template_id); title='New report' if template_id=='blank' else str(spec['name'])
            record=repository.create(f'report-{uuid.uuid4().hex}',title=title,model=template_model(template_id),metadata={'template_id':template_id})
            new_dialog.close(); await activate(record,notice=f'{title} created')

        async def duplicate_current() -> None:
            try:
                latest=repository.get(current.report_id); title=f'{latest.title} copy'[:160]
                record=repository.create(f'report-{uuid.uuid4().hex}',title=title,model=latest.model,metadata={**latest.metadata,'duplicated_from':latest.report_id})
                await activate(record,notice='Report duplicated')
            except Exception as exc: notifications.error(f'Duplicate rejected: {exc}')

        async def rename_report(event: Any) -> None:
            try:
                latest=repository.get(current.report_id); value=str(getattr(event,'value','') or '').strip()
                if value==latest.title: return
                await activate(repository.rename(latest.report_id,value,expected_revision=latest.revision),notice='Report renamed')
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
                try: await activate(repository.get(report_id))
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
            latest=repository.get(current.report_id); repository.checkpoint(latest.report_id,str(checkpoint_name.value or ''),expected_revision=latest.revision)
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
                    checkpoint_name=ui.input(label='Checkpoint name',placeholder='Before review').props('outlined dense hide-bottom-space')
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    ui.button('Save checkpoint',on_click=create_checkpoint).props('flat no-caps')
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
            with ui.column().classes('cui-page cui-page--full cui-visualizer-workspace w-full'):
                # company-ui: allow-ai005 — the report-control strip is part of the isolated editor host.
                with ui.element('section').classes('cui-visualizer-reportbar w-full').props('aria-label="Report controls"'):
                    # company-ui: allow-ai005 — report title is the primary identity control.
                    report_title=ui.input(label='Report title',value=current.title,on_change=rename_report,placeholder='Untitled report').props('outlined dense hide-bottom-space').classes('cui-visualizer-report-title')
                    report_description=ui.input(label='Description',value=str(current.metadata.get('description') or ''),on_change=update_report_description,placeholder='What this report is for').props('outlined dense hide-bottom-space').classes('cui-visualizer-report-description')
                    report_meta=ui.label(f'Created {current.created_at} · Modified {current.updated_at} · revision {current.revision}').classes('cui-visualizer-report-meta')
                    # company-ui: allow-ai005 — searchable report switcher replaces a separate filter field.
                    report_select=ui.select(label='Reports',options=_report_options(repository),value=current.report_id,on_change=select_report).props('outlined dense options-dense hide-bottom-space use-input input-debounce=0').classes('cui-visualizer-report-select')
                    # company-ui: allow-ai005 — frequent creation remains one click away.
                    ui.button('New report',on_click=new_dialog.open).props('unelevated no-caps')
                    # company-ui: allow-ai005 — report reuse remains a primary action.
                    ui.button('Duplicate',on_click=duplicate_current).props('flat no-caps')
                    # Report lifecycle is a separate route so it never obscures the active canvas.
                    ui.button('Manage',on_click=lambda:ui.navigate.to(f'/visualizer/reports?report={quote(current.report_id,safe="")}')).props('flat no-caps').tooltip('Open the dedicated report hub')
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
        bootstrap={**_payload(current,lambda asset_id:f'{STATIC_ROUTE}/report-assets/{asset_id}'),'asset_build':build}
        _bootstrap_editor(ui,bootstrap,build,module_url)
