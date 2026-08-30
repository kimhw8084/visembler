from __future__ import annotations

import io
import json
import os
import zipfile
from pathlib import Path

import pytest
from PIL import Image
from pptx import Presentation

from company_ui.products.visualizer.domain import RevisionConflictError, VisualizerContractError, canonical_model
from company_ui.products.visualizer.files import validate_image_bytes, validate_pptx_bytes
from company_ui.products.visualizer.ppt_service import export_pptx
from company_ui.products.visualizer.page import _decode_bridge_event, _normalize_presets, _validate_model_images
from company_ui.products.visualizer.repository import ReportRepository
from company_ui.products.visualizer.runtime import application_environment, resolve_runtime
from company_ui.products.visualizer.templates import REPORT_TEMPLATES, template_model


def test_runtime_secret_is_generated_reused_and_reaches_nicegui_kwargs(tmp_path: Path):
    base={'COMPANY_UI_ENVIRONMENT':'dev','COMPANY_UI_VISUALIZER_DATA_DIR':str(tmp_path),'HOST':'127.0.0.1','PORT':'8123'}
    first=application_environment(base); second=application_environment(base); config, env=resolve_runtime(base); kwargs=config.nicegui_run_kwargs(env)
    assert first['COMPANY_UI_STORAGE_SECRET']==second['COMPANY_UI_STORAGE_SECRET']
    assert len(first['COMPANY_UI_STORAGE_SECRET'])>=32
    assert kwargs['storage_secret']==first['COMPANY_UI_STORAGE_SECRET']
    assert kwargs['host']=='127.0.0.1' and kwargs['port']==8123
    assert (tmp_path/'.storage_secret').read_text().strip()==first['COMPANY_UI_STORAGE_SECRET']


def test_concurrent_local_startups_share_one_storage_secret(tmp_path: Path):
    from concurrent.futures import ThreadPoolExecutor
    base={'COMPANY_UI_ENVIRONMENT':'dev','COMPANY_UI_VISUALIZER_DATA_DIR':str(tmp_path)}
    with ThreadPoolExecutor(max_workers=8) as pool:
        values=list(pool.map(lambda _: application_environment(base)['COMPANY_UI_STORAGE_SECRET'], range(24)))
    assert len(set(values))==1
    assert (tmp_path/'.storage_secret').read_text().strip()==values[0]


def test_production_missing_storage_secret_fails_closed(tmp_path: Path):
    with pytest.raises(RuntimeError, match='COMPANY_UI_STORAGE_SECRET is required'):
        application_environment({'COMPANY_UI_ENVIRONMENT':'prod','COMPANY_UI_VISUALIZER_DATA_DIR':str(tmp_path)})


def test_repository_revision_idempotency_cleanup_and_corruption_isolation(tmp_path: Path):
    repo=ReportRepository(tmp_path)
    r=repo.create('r1',model=template_model('blank'))
    model=canonical_model({'items':[{'id':'c1','type':'text','order':0,'text':'a'}],'nextId':2})
    committed=repo.commit('r1',base_revision=1,model=model,commit_id='same')
    assert repo.commit('r1',base_revision=1,model=model,commit_id='same').revision==committed.revision
    with pytest.raises(RevisionConflictError): repo.commit('r1',base_revision=1,model=model,commit_id='new')
    assert repo.delete_if_blank('r1',expected_revision=committed.revision) is False
    repo.create('bad',model=template_model('blank')); (tmp_path/'bad.json').write_text('{bad',encoding='utf-8')
    assert [x.report_id for x in repo.list()]==['r1']
    assert any((tmp_path/'_quarantine').glob('bad.*.corrupt.json'))


def test_two_repository_instances_cannot_accept_same_base_revision(tmp_path: Path):
    from concurrent.futures import ThreadPoolExecutor
    repo=ReportRepository(tmp_path); repo.create('shared',model=template_model('blank'))
    model_a=canonical_model({'items':[{'id':'a','type':'text','order':0,'text':'A'}],'nextId':2})
    model_b=canonical_model({'items':[{'id':'b','type':'text','order':0,'text':'B'}],'nextId':2})
    def write(which):
        local=ReportRepository(tmp_path)
        try:
            value=model_a if which=='a' else model_b
            return ('ok',local.commit('shared',base_revision=1,model=value,commit_id=which).revision)
        except RevisionConflictError as exc:
            return ('conflict',exc.expected)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(write,['a','b']))
    assert sorted(kind for kind,_ in results)==['conflict','ok']
    final=repo.get('shared'); assert final.revision==2 and len(final.model['items'])==1


def test_templates_are_deep_copied_and_blank_is_really_blank():
    blank=template_model('blank'); assert blank['items']==[] and blank['groups']=={} and blank['mode']=='guided'
    for key in REPORT_TEMPLATES:
        one=template_model(key); two=template_model(key); one['items'][0]['title']='changed'; assert two['items'][0]['title']!='changed'


def _image_bytes(fmt: str='PNG') -> bytes:
    out=io.BytesIO(); Image.new('RGB',(20,10),(10,20,30)).save(out,format=fmt); return out.getvalue()


@pytest.mark.parametrize('fmt', ['PNG','JPEG','WEBP'])
def test_image_content_validation_allowlist(fmt: str):
    result=validate_image_bytes(_image_bytes(fmt)); assert result['format']==fmt and result['width']==20 and result['height']==10


def test_image_rejects_active_or_invalid_content():
    with pytest.raises(VisualizerContractError): validate_image_bytes(b'<svg onload="alert(1)"></svg>')
    with pytest.raises(VisualizerContractError): validate_image_bytes(b'not-an-image')


def test_embedded_image_server_validation_rejects_external_url_and_accepts_data_url():
    raw=_image_bytes(); import base64
    ok=canonical_model({'items':[{'id':'c1','type':'image','engine':'ImageMediaEngine','order':0,'src':'data:image/png;base64,'+base64.b64encode(raw).decode()}]})
    _validate_model_images(ok)
    bad=canonical_model({'items':[{'id':'c1','type':'image','engine':'ImageMediaEngine','order':0,'src':'https://example.invalid/a.png'}]})
    with pytest.raises(VisualizerContractError): _validate_model_images(bad)


def _pptx() -> bytes:
    prs=Presentation(); prs.slides.add_slide(prs.slide_layouts[6]); out=io.BytesIO(); prs.save(out); return out.getvalue()


def test_pptx_validation_and_archive_traversal_rejection():
    data=_pptx(); assert validate_pptx_bytes(data)['slides']==1
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('../evil','x'); z.writestr('[Content_Types].xml','x'); z.writestr('ppt/presentation.xml','x')
    with pytest.raises(VisualizerContractError, match='unsafe PowerPoint archive path'): validate_pptx_bytes(out.getvalue())


def test_bridge_rejects_unknown_version_type_and_oversize():
    good={'bridge_version':1,'type':'report.save_requested','payload':{}}
    assert _decode_bridge_event(json.dumps(good))['type']=='report.save_requested'
    with pytest.raises(VisualizerContractError): _decode_bridge_event({'bridge_version':2,'type':'report.save_requested','payload':{}})
    with pytest.raises(VisualizerContractError): _decode_bridge_event({'bridge_version':1,'type':'pointermove','payload':{}})


def test_preset_normalization_isolates_corruption_and_preserves_zero():
    raw=[{'id':'good','name':'Good','model':{'items':[{'id':'c1','type':'metric','order':0,'value':0}]}},{'name':'bad','model':{'items':[{'id':'x','order':0}]}}]
    result=_normalize_presets(raw); assert len(result)==1 and result[0]['model']['items'][0]['value']==0


def test_image_pixel_bomb_is_rejected_even_when_compressed_small():
    out=io.BytesIO(); Image.new('RGB',(5000,5000),(0,0,0)).save(out,format='PNG',compress_level=9)
    assert len(out.getvalue()) < 750_000
    with pytest.raises(VisualizerContractError,match='dimensions exceed safety limit'):
        validate_image_bytes(out.getvalue())


def test_pptx_duplicate_path_and_compression_bomb_rejected():
    duplicate=io.BytesIO()
    with zipfile.ZipFile(duplicate,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','x'); z.writestr('ppt/presentation.xml','x'); z.writestr('ppt/presentation.xml','again')
    with pytest.raises(VisualizerContractError,match='duplicate PowerPoint archive path'):
        validate_pptx_bytes(duplicate.getvalue())
    bomb=io.BytesIO()
    with zipfile.ZipFile(bomb,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        z.writestr('[Content_Types].xml','x'); z.writestr('ppt/presentation.xml','x'); z.writestr('ppt/media/zeros.bin',b'0'*(2*1024*1024))
    with pytest.raises(VisualizerContractError,match='suspicious compression ratio'):
        validate_pptx_bytes(bomb.getvalue())


def test_editable_ppt_round_trip_remains_openable_and_adds_native_shapes():
    template=_pptx(); before=Presentation(io.BytesIO(template)); before_count=len(before.slides[0].shapes)
    model=canonical_model({'items':[
        {'id':'m1','type':'metric','engine':'MetricEngine','order':0,'title':'Yield','value':0},
        {'id':'t1','type':'text','engine':'TextEngine','order':1,'title':'Finding','text':'Native editable text'},
    ],'nextId':3})
    output=export_pptx(template,model); validate_pptx_bytes(output)
    after=Presentation(io.BytesIO(output)); assert len(after.slides)==1 and len(after.slides[0].shapes)>before_count
    assert any(getattr(shape,'has_text_frame',False) for shape in after.slides[0].shapes)


def test_visualizer_page_does_not_touch_tab_storage_before_client_connection():
    from company_ui.products.visualizer import page as visualizer_page_module
    source=Path(visualizer_page_module.__file__).read_text(encoding='utf-8')
    assert 'NiceGUIStateServices.tab_store()' not in source
    assert 'NiceGUIStateServices.user_store()' in source

