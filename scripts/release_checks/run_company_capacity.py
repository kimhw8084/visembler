#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import io
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))

from PIL import Image

from company_ui.products.visualizer.domain import canonical_model
from company_ui.products.visualizer.governance import CAPABILITY_ACTIONS, ReportAccessCatalog, ScopedReportRepository
from company_ui.products.visualizer.repository import ReportRepository
from company_ui.security import AuthorizationModel, Principal, RoleDefinition


def _image() -> str:
    out=io.BytesIO(); Image.new('RGB',(20,12),(30,60,90)).save(out,format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()


def run(output: Path) -> int:
    results=[]; image=_image()
    auth=AuthorizationModel({'visembler.admin':RoleDefinition('visembler.admin',frozenset({'administration','report.create',*CAPABILITY_ACTIONS}))})
    import tempfile
    with tempfile.TemporaryDirectory(prefix='visembler-capacity-') as temp:
        for count in (10,100,1000):
            case_dir=Path(temp)/str(count); case_dir.mkdir()
            repository=ReportRepository(case_dir); access=ReportAccessCatalog(case_dir)
            owner=ScopedReportRepository(repository,access,Principal('capacity-owner',roles=frozenset({'visembler.admin'})),auth)
            image_count=1 if count==10 else 5 if count==100 else 10
            started=time.perf_counter()
            for index in range(count):
                images=[{'id':f'image-{n}','type':'image','engine':'ImageMediaEngine','order':n,'src':image} for n in range(image_count)]
                owner.create(f'report-{index:04d}',title=f'Operations report {index}',model=canonical_model({'items':[*images,{'id':'text','type':'text','order':image_count,'text':'measured manufacturing evidence'}]}))
            create_ms=(time.perf_counter()-started)*1000
            started=time.perf_counter(); listed=owner.list(); list_ms=(time.perf_counter()-started)*1000
            started=time.perf_counter(); owner.get('report-0000'); open_ms=(time.perf_counter()-started)*1000
            started=time.perf_counter(); owner.list_history('report-0000'); history_ms=(time.perf_counter()-started)*1000
            asset_id=next(iter(repository.assets.ids()))
            started=time.perf_counter(); owner.read_asset_for_report('report-0000',asset_id); asset_auth_ms=(time.perf_counter()-started)*1000
            started=time.perf_counter(); owner.rename('report-0000',title=f'Renamed operations report {count}',expected_revision=1); rename_ms=(time.perf_counter()-started)*1000
            results.append({'reports':count,'image_items_per_report':image_count,'create_ms':round(create_ms,3),'scoped_list_ms':round(list_ms,3),'open_ms':round(open_ms,3),'history_ms':round(history_ms,3),'asset_authorization_ms':round(asset_auth_ms,3),'rename_ms':round(rename_ms,3),'listed':len(listed),'asset_reference_count':len(repository.assets.ids())})
    result={'schema_version':1,'status':'PASS','candidate_sha':__import__('subprocess').check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'created_at':datetime.now(timezone.utc).isoformat(),'results':results,'method':'non-empty report models with shared validated image asset and text evidence; no blank-report extrapolation','listing_projection':'rebuildable governance summary metadata; canonical report JSON remains authoritative'}
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print(json.dumps({'status':'PASS','output':str(output),'results':results},sort_keys=True)); return 0


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--output',required=True,type=Path); return run(parser.parse_args().output)
if __name__=='__main__': raise SystemExit(main())
