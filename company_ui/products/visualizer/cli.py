from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

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
    if not repository.list(): repository.create('default',title='Untitled report',model=template_model('blank'),metadata={'template_id':'blank'})
    register_visualizer(app,ui,repository)
    return adapter, env, repository


def main(environ: Mapping[str,str] | None = None) -> None:
    adapter, env, _ = build_application(environ)
    # Critical runtime contract: the exact mapping which resolved/generates
    # COMPANY_UI_STORAGE_SECRET is passed into Company UI's adapter at ui.run().
    adapter.run(environ=env)


if __name__ == '__main__':
    main()
