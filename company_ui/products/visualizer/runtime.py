from __future__ import annotations

import os, secrets, tempfile, time
from pathlib import Path
from typing import Mapping

from company_ui.runtime import RuntimeConfig, RuntimeEnvironment
from company_ui.integrations.nicegui_runtime import NiceGUIRuntimeAdapter
from company_ui.security import AccessPolicy, AuthMethod, AuthorizationModel, HeaderAuthenticationAdapter, HeaderIdentityConfig, Principal, RoleDefinition, TrustedProxyPolicy


_REPORT_PERMISSIONS = frozenset({
    'report.create', 'report.read', 'report.edit', 'report.rename', 'report.duplicate',
    'report.share', 'report.delete', 'report.restore', 'report.history.read',
    'report.history.restore', 'report.export', 'template.use', 'template.manage',
})
_ROLE_DEFINITIONS = {
    'visembler.user': RoleDefinition('visembler.user', frozenset({'report.create', 'template.use'})),
    'visembler.editor': RoleDefinition('visembler.editor', frozenset({'report.create', 'template.use'})),
    'visembler.admin': RoleDefinition('visembler.admin', _REPORT_PERMISSIONS | frozenset({'template.manage', 'diagnostics.read', 'administration'})),
    'visembler.support': RoleDefinition('visembler.support', frozenset({'report.read', 'report.history.read', 'report.export', 'diagnostics.read'})),
}


class _DevelopmentAuthenticationAdapter:
    """Explicit local/test identity; never selected for a production environment."""

    def __init__(self, subject: str):
        self.subject = subject

    async def authenticate(self, headers: Mapping[str, str], client_host: str | None = None) -> Principal:
        return Principal(
            self.subject,
            display_name='Local development user',
            roles=frozenset({'visembler.admin'}),
            permissions=_REPORT_PERMISSIONS | frozenset({'template.manage', 'diagnostics.read', 'administration'}),
            method=AuthMethod.CUSTOM,
            metadata={'groups': ()},
        )


def _authentication_contract(config: RuntimeConfig, env: Mapping[str, str]):
    mode = str(env.get('COMPANY_UI_AUTH_MODE', 'local')).strip().lower()
    if config.environment is RuntimeEnvironment.PROD and mode != 'header':
        raise RuntimeError('production Visembler requires COMPANY_UI_AUTH_MODE=header; anonymous/local identity is not permitted')
    if mode == 'local':
        if config.environment not in {RuntimeEnvironment.DEV, RuntimeEnvironment.TEST}:
            raise RuntimeError('local Visembler identity is allowed only in dev or test environments')
        return _DevelopmentAuthenticationAdapter(str(env.get('COMPANY_UI_DEV_SUBJECT') or 'local-dev'))
    if mode != 'header':
        raise RuntimeError('COMPANY_UI_AUTH_MODE must be local or header')
    assertion_secret = str(env.get('COMPANY_UI_AUTH_ASSERTION_SECRET') or '').strip()
    if assertion_secret and len(assertion_secret) < 32:
        raise RuntimeError('COMPANY_UI_AUTH_ASSERTION_SECRET must be at least 32 characters')
    if config.environment is RuntimeEnvironment.PROD and not config.proxy.enabled and not assertion_secret:
        raise RuntimeError('production header identity requires trusted proxy mode or a validated assertion secret')
    header_config = HeaderIdentityConfig(
        subject_header=env.get('COMPANY_UI_AUTH_SUBJECT_HEADER', 'x-auth-user'),
        display_name_header=env.get('COMPANY_UI_AUTH_NAME_HEADER', 'x-auth-name'),
        email_header=env.get('COMPANY_UI_AUTH_EMAIL_HEADER', 'x-auth-email'),
        roles_header=env.get('COMPANY_UI_AUTH_ROLES_HEADER', 'x-auth-roles'),
        permissions_header=env.get('COMPANY_UI_AUTH_PERMISSIONS_HEADER', 'x-auth-permissions'),
        groups_header=env.get('COMPANY_UI_AUTH_GROUPS_HEADER', 'x-auth-groups'),
        assertion_header=env.get('COMPANY_UI_AUTH_ASSERTION_HEADER', 'x-company-auth-assertion'),
        require_trusted_proxy=True,
    )
    return HeaderAuthenticationAdapter(
        header_config,
        trusted_proxies=TrustedProxyPolicy(tuple(config.proxy.trusted_proxies)),
        assertion_secret=assertion_secret or None,
    )


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
    if issues: raise RuntimeError('runtime environment validation failed: '+', '.join(issues))
    authentication = _authentication_contract(config, env)
    authorization = AuthorizationModel(_ROLE_DEFINITIONS)
    diagnostics_policy = AccessPolicy(
        any_permissions=frozenset({'diagnostics.read'}),
        any_roles=frozenset({'visembler.admin', 'visembler.support'}),
    )
    return NiceGUIRuntimeAdapter(
        config,
        auth_adapter=authentication,
        authorization=authorization,
        diagnostics_policy=diagnostics_policy,
    ),env
