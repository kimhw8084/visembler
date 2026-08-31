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
MAX_PRESETS = 50
MAX_PRESET_BYTES = 1_500_000
_ALLOWED_EVENTS = {
    'report.commit','report.save_requested','preset.preferences_requested','preset.preferences_save_requested',
    'ppt.export_requested','dataset.binding_requested','report.history_requested',
}
NAVIGATION = NavigationModel((NavSection('workspace','Workspace',(NavItem('visualizer','Visembler','/visualizer','chart-line'),)),))


def _asset_build() -> str:
    h=hashlib.sha256()
    for name in ('tokens.css','integrated_editor.css','integrated_editor.html','authoring_contracts.mjs','authoring_data.mjs','authoring_data_worker.mjs','authoring_transforms.mjs','authoring_performance.mjs','authoring_geometry.mjs','element_renderer.mjs','integrated_editor.mjs'):
        h.update(name.encode()); h.update((ASSETS/name).read_bytes())
    return h.hexdigest()[:16]


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


def _report_options(repository: ReportRepository, query: str='') -> dict[str,str]:
    needle=' '.join(str(query).split()).casefold(); records=repository.list(); counts:dict[str,int]={}
    for record in records:
        blank=not record.model.get('items') and not record.model.get('groups')
        label='New blank report' if record.title=='Untitled report' and blank else record.title
        counts[label]=counts.get(label,0)+1
    result={}
    for record in records:
        blank=not record.model.get('items') and not record.model.get('groups')
        label='New blank report' if record.title=='Untitled report' and blank else record.title
        if needle and needle not in label.casefold() and needle not in record.report_id.casefold(): continue
        if counts[label]>1:
            label=f'{label}{" · blank" if blank else ""} · {record.report_id[-6:]}'
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

    from fastapi.responses import Response
    @app.get(f'{STATIC_ROUTE}/report-assets/{{asset_id}}',include_in_schema=False)
    async def _report_asset(asset_id: str):
        data=repository.assets.read_image(asset_id); mime=str(validate_image_bytes(data)['mime'])
        return Response(content=data,media_type=mime,headers={'Cache-Control':'private, max-age=3600'})

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
                ppt_template.update(name=name,content=content); ppt_status.text=f'Export template · {name}'; ppt_status.update(); notifications.success('PowerPoint template loaded for export')
            except Exception as exc: notifications.error(f'PowerPoint rejected: {exc}')

        async def open_developer_console() -> None:
            await ui.run_javascript("window.dispatchEvent(new Event('company_ui:open-developer-console'))")

        with AppShell('Visembler',NAVIGATION,active_route='/visualizer',sidebar=SidebarMode.COMPACT,environment=None,subtitle='Visual report authoring',owner='Visembler',on_developer_console=open_developer_console):
            # company-ui: allow-ai005 — dialogs are isolated compatibility hosts for the report-authoring module.
            new_dialog=ui.dialog()
            with new_dialog:
                # company-ui: allow-ai005 — see dialog compatibility host above.
                with ui.card().classes('cui-dialog-card'):
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    ui.label('New report').classes('cui-dialog-title'); ui.label('Start with a genuinely blank canvas or a governed editable template.').classes('cui-field-description')
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    ui.button('Blank canvas',on_click=lambda: create_report('blank')).props('flat no-caps')
                    for template_id,spec in REPORT_TEMPLATES.items():
                        async def _choose(_event=None, template_id=template_id): await create_report(template_id)
                        # company-ui: allow-ai005 — see dialog compatibility host above.
                        with ui.button(on_click=_choose).props('flat no-caps').classes('w-full'):
                            # company-ui: allow-ai005 — see dialog compatibility host above.
                            ui.label(str(spec['name'])); ui.label(str(spec['description'])).classes('cui-field-description')
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
                    ui.label('Import a Visembler-exported PowerPoint as an editable report, or load any ordinary PowerPoint as an export template.').classes('cui-field-description')
                    # company-ui: allow-ai004 — upload controls require an isolated layout host for both validated upload adapters.
                    with ui.column().classes('w-full gap-3'):
                        FileUpload(label='Visembler report JSON',accept=('.json',),max_file_size_mb=2,on_upload=upload_report)
                        FileUpload(label='Visembler report PPTX or export template',accept=('.pptx',),max_file_size_mb=100,on_upload=upload_ppt)
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    ppt_status=ui.label('Export template · not loaded').classes('cui-field-description')
                    # company-ui: allow-ai005 — see dialog compatibility host above.
                    ui.button('Done',on_click=import_dialog.close).props('flat no-caps')

            # company-ui: allow-ai004 — the editor is an isolated application-owned canvas host.
            with ui.column().classes('cui-page cui-page--full cui-visualizer-workspace w-full'):
                # company-ui: allow-ai005 — the report-control strip is part of the isolated editor host.
                with ui.element('section').classes('cui-visualizer-reportbar w-full').props('aria-label="Report controls"'):
                    # company-ui: allow-ai005 — see isolated editor host above.
                    report_title=ui.input(label='Report title',value=current.title,on_change=rename_report,placeholder='Untitled report').props('outlined dense hide-bottom-space').classes('cui-visualizer-report-title')
                    # company-ui: allow-ai005 — see isolated editor host above.
                    report_select=ui.select(label='Reports',options=_report_options(repository),value=current.report_id,on_change=select_report).props('outlined dense options-dense hide-bottom-space').classes('cui-visualizer-report-select')
                    # company-ui: allow-ai005 — see isolated editor host above.
                    report_filter=ui.input(label='Find report',on_change=refresh_reports,placeholder='Search reports').props('outlined dense hide-bottom-space').classes('cui-visualizer-report-filter')
                    # company-ui: allow-ai005 — see isolated editor host above.
                    ui.button('New report',on_click=new_dialog.open).props('unelevated no-caps')
                    # company-ui: allow-ai005 — see isolated editor host above.
                    ui.button('Duplicate',on_click=duplicate_current).props('flat no-caps')
                    # company-ui: allow-ai005 — see isolated editor host above.
                    # company-ui: allow-ai005 — see isolated editor host above.
                    ui.button('Import…',on_click=import_dialog.open).props('flat no-caps')
                    # company-ui: allow-ai005 — see isolated editor host above.
                    ui.button('Clean up empty reports',on_click=clean_dialog.open).props('flat no-caps')
                    # company-ui: allow-ai005 — see isolated editor host above.
                    ui.button('Trash',on_click=delete_dialog.open).props('outline no-caps color=negative')
                    # company-ui: allow-ai005 — see isolated editor host above.
                    ui.button('Restore…',on_click=open_restore).props('flat no-caps')
                # company-ui: allow-ai005 — the editor mount point is an isolated application-owned canvas host.
                host=ui.element('div').classes('cui-visualizer-host w-full').props('aria-label="Visembler report editor"')
                host.on('visualizer_bridge',handle_semantic,args=['detail'])
                with host: ui.html((ASSETS/'integrated_editor.html').read_text(encoding='utf-8'),sanitize=False)

        css_url=f'{STATIC_ROUTE}/assets/integrated_editor.css?v={build}'
        token_url=f'{STATIC_ROUTE}/assets/tokens.css?v={build}'
        module_url=f'{STATIC_ROUTE}/assets/integrated_editor.mjs?v={build}'
        ui.add_head_html(f'<link rel="stylesheet" href="{token_url}"><link rel="stylesheet" href="{css_url}">')
        bootstrap={'report_id':current.report_id,'revision':current.revision,'model':current.model,'asset_build':build}
        await ui.run_javascript(f'''window.__CUI_VISUALIZER_BOOTSTRAP__={json.dumps(bootstrap,ensure_ascii=False)};window.__CUI_VISUALIZER_ASSET_BUILD__={json.dumps(build)};import({json.dumps(module_url)}).catch(error=>{{console.error(error);const root=document.querySelector('.cui-visualizer-root');if(root)root.dataset.editorReady='failed';}});''')
