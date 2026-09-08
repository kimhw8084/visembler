from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from company_ui.diagnostics import HealthCheck

from .page import register_visualizer
from .governance import ReportAccessCatalog
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
    access=ReportAccessCatalog(repository)
    existing=repository.list()+repository.list_trash()
    migration_owner=str(env.get('COMPANY_UI_MIGRATION_OWNER_SUBJECT') or '').strip() or (
        str(env.get('COMPANY_UI_DEV_SUBJECT') or 'local-dev') if env.get('COMPANY_UI_ENVIRONMENT') in {'dev','test'} else ''
    )
    if existing:
        access.migrate(existing,owner_subject=migration_owner or None,require_explicit_owner=env.get('COMPANY_UI_ENVIRONMENT')=='prod')
    else:
        if not migration_owner:
            raise RuntimeError('COMPANY_UI_MIGRATION_OWNER_SUBJECT is required to bootstrap a production report repository')
        record=repository.create('default',title='Untitled report',model=template_model('blank'),metadata={'template_id':'blank'})
        access.create(record.report_id,migration_owner)
    adapter.health.register(HealthCheck('visualizer.report_storage',lambda: repository.root.is_dir() and repository.root.exists()))
    adapter.health.register(HealthCheck('visualizer.access_catalog',access.health))
    register_visualizer(app,ui,repository,access=access,runtime=adapter)
    return adapter, env, repository


def main(environ: Mapping[str,str] | None = None) -> None:
    adapter, env, _ = build_application(environ)
    # Critical runtime contract: the exact mapping which resolved/generates
    # COMPANY_UI_STORAGE_SECRET is passed into Company UI's adapter at ui.run().
    adapter.run(environ=env)


if __name__ == '__main__':
    main()
