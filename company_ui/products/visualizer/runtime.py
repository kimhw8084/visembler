from __future__ import annotations

import os, secrets, tempfile, time
from pathlib import Path
from typing import Mapping

from company_ui.runtime import RuntimeConfig, RuntimeEnvironment
from company_ui.integrations.nicegui_runtime import NiceGUIRuntimeAdapter


def _persistent_local_secret(secret_file: Path) -> str:
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    if secret_file.is_file():
        value=secret_file.read_text(encoding='utf-8').strip()
        if len(value)>=32: return value
    secret=secrets.token_urlsafe(48)
    fd,tmp_name=tempfile.mkstemp(prefix='.storage-secret.',suffix='.tmp',dir=secret_file.parent)
    tmp=Path(tmp_name)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as handle:
            handle.write(secret+'\n'); handle.flush(); os.fsync(handle.fileno())
        try: tmp.chmod(0o600)
        except OSError: pass
        try:
            # A hard-link publishes an already-complete file only when the final
            # path does not exist, so concurrent launches cannot overwrite a secret.
            os.link(tmp,secret_file)
            try:
                dfd=os.open(secret_file.parent,os.O_DIRECTORY); os.fsync(dfd); os.close(dfd)
            except (AttributeError,OSError): pass
            return secret
        except FileExistsError:
            for _ in range(100):
                try:
                    existing=secret_file.read_text(encoding='utf-8').strip()
                    if len(existing)>=32: return existing
                except OSError: pass
                time.sleep(.01)
            raise RuntimeError(f'local storage secret exists but is unreadable or invalid: {secret_file}')
        except OSError:
            # Filesystems without hard-link support: exclusive create still prevents
            # overwrites; readers retry while the winner completes its write.
            try:
                out_fd=os.open(secret_file,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            except FileExistsError:
                for _ in range(100):
                    existing=secret_file.read_text(encoding='utf-8').strip()
                    if len(existing)>=32: return existing
                    time.sleep(.01)
                raise RuntimeError(f'local storage secret exists but is invalid: {secret_file}')
            else:
                with os.fdopen(out_fd,'w',encoding='utf-8',newline='\n') as handle:
                    handle.write(secret+'\n'); handle.flush(); os.fsync(handle.fileno())
                return secret
    finally:
        try: tmp.unlink()
        except FileNotFoundError: pass


def application_environment(environ: Mapping[str,str] | None = None) -> dict[str,str]:
    env=dict(os.environ if environ is None else environ)
    if not env.get('COMPANY_UI_HOST') and env.get('HOST'): env['COMPANY_UI_HOST']=env['HOST']
    if not env.get('COMPANY_UI_PORT') and env.get('PORT'): env['COMPANY_UI_PORT']=env['PORT']
    env.setdefault('COMPANY_UI_HOST','0.0.0.0'); env.setdefault('COMPANY_UI_PORT','8080')
    raw=env.get('COMPANY_UI_ENVIRONMENT','dev').strip().lower()
    if raw == 'production': raw='prod'; env['COMPANY_UI_ENVIRONMENT']='prod'
    if raw not in {'dev','test','qa','prod'}: raise RuntimeError(f'unsupported COMPANY_UI_ENVIRONMENT: {raw!r}')
    secret=env.get('COMPANY_UI_STORAGE_SECRET','').strip()
    if not secret:
        if raw == 'prod':
            raise RuntimeError('COMPANY_UI_STORAGE_SECRET is required in production because Visembler uses NiceGUI user storage.')
        data_dir=Path(env.get('COMPANY_UI_VISUALIZER_DATA_DIR') or (Path.home()/'.company_ui'/'visualizer')).expanduser()
        secret=_persistent_local_secret(data_dir/'.storage_secret')
        env['COMPANY_UI_STORAGE_SECRET']=secret
    if len(env['COMPANY_UI_STORAGE_SECRET']) < 32: raise RuntimeError('COMPANY_UI_STORAGE_SECRET must be at least 32 characters')
    return env


def resolve_runtime(environ: Mapping[str,str] | None = None) -> tuple[RuntimeConfig, dict[str,str]]:
    env=application_environment(environ)
    config=RuntimeConfig.from_env('Visembler',environ=env)
    return config,env


def build_runtime_adapter(environ: Mapping[str,str] | None = None) -> tuple[NiceGUIRuntimeAdapter, dict[str,str]]:
    config,env=resolve_runtime(environ)
    issues=config.validate_environment(env)
    # Multi-replica/proxy concerns remain Company UI configuration checks; Visembler does not infer infrastructure.
    if issues: raise RuntimeError('runtime environment validation failed: '+', '.join(issues))
    return NiceGUIRuntimeAdapter(config),env
