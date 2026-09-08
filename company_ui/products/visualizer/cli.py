from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from company_ui.diagnostics import HealthCheck
from .governance import ReportAccessCatalog, ScopedReportRepository
from .page import register_visualizer
from .repository import ReportRepository
from .runtime import build_runtime_adapter
from .templates import template_model


def build_application(environ: Mapping[str,str] | None = None):
    adapter, env = build_runtime_adapter(environ)
    try:
        # company-ui: allow-ai001 — application bootstrap must bind NiceGUI's app/ui runtime to the Company adapter.
        from nicegui import app, ui
    except ImportError as exc:  # pragma: no cover - certified on target
        raise RuntimeError('NiceGUI 3.15.0 is required to run Visembler.') from exc
    data_dir=Path(env.get('COMPANY_UI_VISUALIZER_DATA_DIR') or (Path.home()/'.company_ui'/'visualizer')).expanduser()
    reports_dir=data_dir/'reports'; reports_dir.mkdir(parents=True,exist_ok=True)
    repository=ReportRepository(reports_dir)
    access=ReportAccessCatalog(reports_dir)
    records=repository.list(); trashed_records=repository.list_trash()
    production=env.get('COMPANY_UI_ENVIRONMENT') == 'prod'
    migration_owner=env.get('COMPANY_UI_MIGRATION_OWNER_SUBJECT') or (None if production else env.get('COMPANY_UI_DEV_SUBJECT','local-dev'))
    access.migrate([record.report_id for record in [*records, *trashed_records]], owner=migration_owner, production=production, trashed_ids={record.report_id for record in trashed_records})
    reconciliation=access.reconcile()
    if reconciliation['blocked']:
        raise RuntimeError('governance reconciliation blocked resources: ' + ', '.join(reconciliation['blocked']))
    access.rebuild_summaries([*records, *trashed_records])
    if not records:
        # The local bootstrap is owned by the deterministic development
        # principal. Production requires the explicit migration owner.
        owner=migration_owner
        if not owner: raise RuntimeError('COMPANY_UI_MIGRATION_OWNER_SUBJECT is required to bootstrap production storage')
        access.begin_create('default', owner)
        default_record=repository.create('default',title='Untitled report',model=template_model('blank'),metadata={'template_id':'blank'})
        access.mark_active('default')
        access.update_summary(default_record)
    register_visualizer(app,ui,repository,access=access,authorization=adapter.authorization)
    adapter.health.register(HealthCheck('visualizer-storage-writable', lambda: access.write_readiness()['ok']))
    return adapter, env, repository


def main(environ: Mapping[str,str] | None = None) -> None:
    adapter, env, _ = build_application(environ)
    # Critical runtime contract: the exact mapping which resolved/generates
    # COMPANY_UI_STORAGE_SECRET is passed into Company UI's adapter at ui.run().
    adapter.run(environ=env)


if __name__ == '__main__':
    main()
