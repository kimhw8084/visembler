from __future__ import annotations

import base64
import hashlib
import inspect
import io
import json
import os
import uuid
from pathlib import Path
from typing import Any, Mapping

from company_ui.integrations.nicegui_components import FileUpload
from company_ui.integrations.nicegui_layout import AppShell, PageHeader
from company_ui.integrations.nicegui_state import NiceGUIStateServices
from company_ui.navigation import NavItem, NavigationModel, NavSection

from .domain import BRIDGE_MAX_BYTES, MODEL_MAX_BYTES, RevisionConflictError, VisualizerContractError, canonical_model, stable_json
from .files import PPT_MAX_BYTES, validate_image_bytes, validate_pptx_bytes
from .ppt_service import export_pptx
from .repository import ReportRepository
from .templates import REPORT_TEMPLATES, template_model

PRODUCT = Path(__file__).resolve().parent
ASSETS = PRODUCT / 'assets'
VENDOR = PRODUCT / 'vendor' / 'production_core'
STATIC_ROUTE = '/_cui_visualizer'
BRIDGE_VERSION = 1
PRESET_KEY = 'visualizer.personal_presets'
MAX_PRESETS = 50
MAX_PRESET_BYTES = 1_500_000
_ALLOWED_EVENTS = {
    'report.commit','report.save_requested','preset.preferences_requested','preset.preferences_save_requested',
    'ppt.export_requested','dataset.binding_requested',
}
NAVIGATION = NavigationModel((NavSection('workspace','Workspace',(NavItem('visualizer','Visembler','/visualizer','chart-line'),)),))


def _asset_build() -> str:
    h=hashlib.sha256()
    for name in ('tokens.css','integrated_editor.css','integrated_editor.html','authoring_contracts.mjs','authoring_data.mjs','authoring_transforms.mjs','element_renderer.mjs','integrated_editor.mjs'):
        h.update(name.encode()); h.update((ASSETS/name).read_bytes())
    return h.hexdigest()[:16]


def _payload(record) -> dict[str, Any]:
    return {'report_id':record.report_id,'revision':record.revision,'title':record.title,'model':record.model,'fingerprint':record.to_dict()['fingerprint']}


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


def _normalize_presets(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw,list): raise VisualizerContractError('presets must be a list')
    result=[]; total=0
    for entry in raw[:MAX_PRESETS]:
        if not isinstance(entry,Mapping): continue
        name=' '.join(str(entry.get('name') or '').replace('\x00','').split())[:80]
        model=entry.get('model')
        if not name or not isinstance(model,Mapping): continue
        try: canonical=canonical_model(model); _validate_model_images(canonical)
        except Exception: continue
        preset={'id':str(entry.get('id') or uuid.uuid4().hex)[:160],'name':name,'model':canonical}
        total += len(stable_json(preset).encode('utf-8'))
        if total > MAX_PRESET_BYTES: break
        result.append(preset)
    return result


async def _read_upload(event: Any, *, max_bytes: int) -> tuple[str, bytes]:
    file_obj=getattr(event,'file',None)
    name=str(getattr(file_obj,'name',None) or getattr(event,'name',None) or getattr(event,'filename',None) or 'upload')
    source=getattr(file_obj,'content',None) or getattr(event,'content',None) or file_obj
    reader=getattr(source,'read',None)
    if reader is None: raise VisualizerContractError('upload content is unavailable')
    value=reader()
    if inspect.isawaitable(value): value=await value
    if isinstance(value,str): value=value.encode()
    if not isinstance(value,(bytes,bytearray)): raise VisualizerContractError('upload did not provide bytes')
    payload=bytes(value)
    if len(payload)>max_bytes: raise VisualizerContractError(f'upload exceeds {max_bytes} bytes')
    return Path(name).name,payload


def _report_options(repository: ReportRepository) -> dict[str,str]:
    records=repository.list(); counts:dict[str,int]={}
    for record in records: counts[record.title]=counts.get(record.title,0)+1
    result={}
    for record in records:
        label=record.title
        if counts[label]>1:
            blank=' · blank' if not record.model.get('items') and not record.model.get('groups') else ''
            label=f'{label}{blank} · {record.report_id[-6:]}'
        result[record.report_id]=label
    return result


def register_visualizer(app: Any, ui: Any, repository: ReportRepository) -> None:
    if getattr(app,'_company_ui_visualizer_registered',False): return
    app._company_ui_visualizer_registered=True
    build=_asset_build()
    app.add_static_files(f'{STATIC_ROUTE}/assets',str(ASSETS),follow_symlink=False,max_cache_age=0)
    app.add_static_files(f'{STATIC_ROUTE}/vendor/production_core',str(VENDOR),follow_symlink=False,max_cache_age=3600)

    from fastapi.responses import RedirectResponse
    @app.get('/',include_in_schema=False)
    async def _root_redirect(): return RedirectResponse('/visualizer',status_code=307)

    @ui.page('/visualizer')
    async def visualizer_page():
        notifications=NiceGUIStateServices.notification_service(); downloads=NiceGUIStateServices.download_service()
        preferences=NiceGUIStateServices.user_preferences(key='company_ui_visualizer_preferences')
        page_state=NiceGUIStateServices.user_store()
        records=repository.list()
        if not records:
            records=[repository.create('default',title='Untitled report',model=template_model('blank'),metadata={'template_id':'blank'})]
        preferred=str(page_state.get('visualizer.current_report') or '')
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
            await send('report.bootstrap',_payload(record))
            if notice: notifications.success(notice)

        async def handle_semantic(event: Any) -> None:
            nonlocal current
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
                if kind=='preset.preferences_requested':
                    raw=preferences.load().filter_views.get(PRESET_KEY,{})
                    presets=_normalize_presets(raw.get('presets',[])) if isinstance(raw,Mapping) else []
                    await send('preset.preferences_result',{'presets':presets}); return
                if kind=='preset.preferences_save_requested':
                    presets=_normalize_presets(payload.get('presets'))
                    preferences.save_filter_view(PRESET_KEY,{'presets':presets})
                    await send('preset.preferences_result',{'presets':presets,'saved':True}); return
                if kind=='ppt.export_requested':
                    if not ppt_template['content']: raise VisualizerContractError('Load a PowerPoint template before exporting')
                    latest=repository.get(current.report_id); output=export_pptx(ppt_template['content'],latest.model)
                    downloads.download(f'{latest.title or "visembler-report"}.pptx',output,media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation')
                    await send('application.notification',{'level':'success','message':'Editable PowerPoint export generated'}); return
                if kind=='dataset.binding_requested':
                    await send('report.error',{'message':'Dataset binding is unavailable until a Company UI Dataset/DataSession is attached to this report.'}); return
            except RevisionConflictError:
                latest=repository.get(current.report_id); await send('report.conflict',_payload(latest))
            except Exception as exc:
                try: latest=repository.get(current.report_id); record_payload=_payload(latest)
                except Exception: record_payload=None
                await send('report.error',{'message':str(exc)[:400],**({'report':record_payload} if record_payload else {})})

        async def create_report(template_id: str) -> None:
            spec=REPORT_TEMPLATES.get(template_id); title='Untitled report' if template_id=='blank' else str(spec['name'])
            record=repository.create(f'report-{uuid.uuid4().hex}',title=title,model=template_model(template_id),metadata={'template_id':template_id})
            new_dialog.close(); await activate(record,notice=f'{title} created')

        async def rename_report(event: Any) -> None:
            try:
                latest=repository.get(current.report_id); value=str(getattr(event,'value','') or '').strip()
                if value==latest.title: return
                await activate(repository.rename(latest.report_id,value,expected_revision=latest.revision),notice='Report renamed')
            except RevisionConflictError: await activate(repository.get(current.report_id),notice='Report changed elsewhere; latest revision loaded')
            except Exception as exc: notifications.error(f'Rename rejected: {exc}')

        async def select_report(event: Any) -> None:
            report_id=str(getattr(event,'value','') or '')
            if report_id and report_id != current.report_id:
                try: await activate(repository.get(report_id))
                except Exception as exc: notifications.error(f'Unable to open report: {exc}')

        async def delete_current() -> None:
            nonlocal current
            try:
                latest=repository.get(current.report_id); repository.delete(latest.report_id,expected_revision=latest.revision)
                remaining=repository.list()
                if not remaining: remaining=[repository.create(f'report-{uuid.uuid4().hex}',title='Untitled report',model=template_model('blank'),metadata={'template_id':'blank'})]
                delete_dialog.close(); await activate(remaining[0],notice='Report deleted')
            except Exception as exc: notifications.error(f'Delete rejected: {exc}')

        async def clean_empty() -> None:
            removed=0
            for record in list(repository.list()):
                if record.report_id==current.report_id or record.title!='Untitled report': continue
                try: removed += 1 if repository.delete_if_blank(record.report_id,expected_revision=record.revision) else 0
                except RevisionConflictError: continue
            clean_dialog.close(); report_select.options=_report_options(repository); report_select.update(); notifications.success(f'Removed {removed} empty Untitled report{"s" if removed!=1 else ""}')

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
                ppt_template.update(name=name,content=content); ppt_status.text=f'PowerPoint template · {name}'; ppt_status.update(); notifications.success('PowerPoint template loaded')
            except Exception as exc: notifications.error(f'PowerPoint rejected: {exc}')

        with AppShell('Visembler',NAVIGATION,active_route='/visualizer',environment=None,subtitle='Visual report authoring',owner='Visembler'):
            new_dialog=ui.dialog()
            with new_dialog:
                with ui.card().classes('cui-dialog-card'):
                    ui.label('New report').classes('cui-dialog-title'); ui.label('Start with a genuinely blank canvas or a governed editable template.').classes('cui-field-description')
                    ui.button('Blank canvas',on_click=lambda: create_report('blank')).props('flat no-caps')
                    for template_id,spec in REPORT_TEMPLATES.items():
                        async def _choose(_event=None, template_id=template_id): await create_report(template_id)
                        with ui.button(on_click=_choose).props('flat no-caps').classes('w-full'):
                            ui.label(str(spec['name'])); ui.label(str(spec['description'])).classes('cui-field-description')
                    ui.button('Cancel',on_click=new_dialog.close).props('flat no-caps')
            delete_dialog=ui.dialog()
            with delete_dialog:
                with ui.card().classes('cui-dialog-card'):
                    ui.label('Delete report?').classes('cui-dialog-title'); ui.label('This permanently removes the current report.').classes('cui-field-description')
                    ui.button('Delete report',on_click=delete_current).props('unelevated no-caps color=negative'); ui.button('Cancel',on_click=delete_dialog.close).props('flat no-caps')
            clean_dialog=ui.dialog()
            with clean_dialog:
                with ui.card().classes('cui-dialog-card'):
                    ui.label('Clean up empty reports?').classes('cui-dialog-title'); ui.label('Remove other genuinely blank Untitled reports. The current report is always preserved.').classes('cui-field-description')
                    ui.button('Clean up empty reports',on_click=clean_empty).props('unelevated no-caps'); ui.button('Cancel',on_click=clean_dialog.close).props('flat no-caps')
            import_dialog=ui.dialog()
            with import_dialog:
                with ui.card().classes('cui-dialog-card cui-visualizer-import-card'):
                    ui.label('Import').classes('cui-dialog-title')
                    ui.label('Bring an existing report model or PowerPoint template into the current Visembler workspace.').classes('cui-field-description')
                    with ui.column().classes('w-full gap-3'):
                        FileUpload(label='Visembler report JSON',accept=('.json',),max_file_size_mb=2,on_upload=upload_report)
                        FileUpload(label='Existing work PPTX',accept=('.pptx',),max_file_size_mb=100,on_upload=upload_ppt)
                    ppt_status=ui.label('PowerPoint template · not loaded').classes('cui-field-description')
                    ui.button('Done',on_click=import_dialog.close).props('flat no-caps')

            with ui.column().classes('cui-page cui-page--full w-full'):
                PageHeader('Visembler','Build, arrange, validate, and export the current report.')
                with ui.element('section').classes('cui-visualizer-reportbar w-full').props('aria-label="Report controls"'):
                    report_title=ui.input(label='Report title',value=current.title,on_change=rename_report,placeholder='Untitled report').props('outlined dense hide-bottom-space').classes('cui-visualizer-report-title')
                    report_select=ui.select(label='Reports',options=_report_options(repository),value=current.report_id,on_change=select_report).props('outlined dense options-dense hide-bottom-space').classes('cui-visualizer-report-select')
                    ui.button('New report',on_click=new_dialog.open).props('unelevated no-caps')
                    ui.button('Import…',on_click=import_dialog.open).props('flat no-caps')
                    ui.button('Clean up empty reports',on_click=clean_dialog.open).props('flat no-caps')
                    ui.button('Delete report',on_click=delete_dialog.open).props('outline no-caps color=negative')
                host=ui.element('div').classes('cui-visualizer-host w-full').props('aria-label="Visembler report editor"')
                host.on('visualizer_bridge',handle_semantic,args=['detail'])
                with host: ui.html((ASSETS/'integrated_editor.html').read_text(encoding='utf-8'),sanitize=False)

        css_url=f'{STATIC_ROUTE}/assets/integrated_editor.css?v={build}'
        token_url=f'{STATIC_ROUTE}/assets/tokens.css?v={build}'
        module_url=f'{STATIC_ROUTE}/assets/integrated_editor.mjs?v={build}'
        ui.add_head_html(f'<link rel="stylesheet" href="{token_url}"><link rel="stylesheet" href="{css_url}">')
        bootstrap={'report_id':current.report_id,'revision':current.revision,'model':current.model,'asset_build':build}
        await ui.run_javascript(f'''window.__CUI_VISUALIZER_BOOTSTRAP__={json.dumps(bootstrap,ensure_ascii=False)};window.__CUI_VISUALIZER_ASSET_BUILD__={json.dumps(build)};import({json.dumps(module_url)}).catch(error=>{{console.error(error);const root=document.querySelector('.cui-visualizer-root');if(root)root.dataset.editorReady='failed';}});''')
