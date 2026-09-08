#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from company_ui.diagnostics.correlation import reset_correlation_id, set_correlation_id
from company_ui.products.visualizer.domain import RevisionConflictError, VisualizerContractError, canonical_model
from company_ui.products.visualizer.governance import CAPABILITY_ACTIONS, ReportAccessCatalog, ScopedReportRepository
from company_ui.products.visualizer.repository import ReportRepository
from company_ui.products.visualizer.templates import template_model
from company_ui.security import AuthorizationModel, Principal, RoleDefinition


def _auth() -> AuthorizationModel:
    return AuthorizationModel({'visembler.admin': RoleDefinition('visembler.admin', frozenset({'administration', 'report.create', *CAPABILITY_ACTIONS}))})


def run(output: Path) -> int:
    checks=[]
    def check(identifier, fn):
        try: fn(); checks.append({'id':identifier,'status':'PASS'})
        except Exception as exc: checks.append({'id':identifier,'status':'FAIL','detail':f'{type(exc).__name__}: {exc}'})

    with tempfile.TemporaryDirectory(prefix='visembler-company-users-') as temp:
        repository=ReportRepository(temp); access=ReportAccessCatalog(temp); auth=_auth()
        alice=ScopedReportRepository(repository,access,Principal('alice',permissions=frozenset({'report.create'})),auth)
        bob=ScopedReportRepository(repository,access,Principal('bob',permissions=frozenset({'report.create'})),auth)
        carol=ScopedReportRepository(repository,access,Principal('carol',permissions=frozenset({'report.create'})),auth)
        def create(): alice.create('company-report',title='Company report',model=template_model('blank'))
        check('MU001 owner creates',create)
        check('MU002 owner lists',lambda: assert_ids(alice.list(),{'company-report'}))
        check('MU003 unauthorized direct read',lambda: expect(PermissionError,lambda: carol.get('company-report')))
        check('MU004 viewer before grant',lambda: expect(PermissionError,lambda: bob.get('company-report')))
        check('MU005 grant viewer',lambda: alice.share('company-report','bob','viewer'))
        viewer=ScopedReportRepository(repository,access,Principal('bob',permissions=frozenset({'report.create'})),auth)
        check('MU006 viewer reads',lambda: viewer.get('company-report'))
        check('MU007 viewer duplicate',lambda: expect(PermissionError,lambda: viewer.duplicate('company-report','viewer-copy')))
        history=repository.list_history('company-report')[0]['history_id']
        check('MU008 viewer history duplicate',lambda: expect(PermissionError,lambda: viewer.duplicate_from_history('company-report',history,'viewer-history-copy')))
        check('MU009 viewer trash',lambda: expect(PermissionError,lambda: viewer.trash_report('company-report',expected_revision=1)))
        check('MU010 viewer restore history',lambda: expect(PermissionError,lambda: viewer.restore_history('company-report',history_id=history,expected_revision=1)))
        check('MU011 viewer commit',lambda: expect(PermissionError,lambda: viewer.commit('company-report',base_revision=1,model=canonical_model(),commit_id='viewer')))
        check('MU012 promote editor',lambda: alice.share('company-report','bob','editor'))
        editor=ScopedReportRepository(repository,access,Principal('bob',permissions=frozenset({'report.create'})),auth)
        changed=canonical_model({'items':[{'id':'c1','type':'text','order':0,'text':'editor change'}]})
        check('MU013 editor saves',lambda: editor.commit('company-report',base_revision=1,model=changed,commit_id='editor-1'))
        stale_base=repository.get('company-report').revision
        check('MU014 stale conflict',lambda: stale_conflict(editor,stale_base))
        token=set_correlation_id('company-acceptance-correlation')
        try: check('MU015 audit actor/correlation',lambda: audit_event(access,'company-report',editor))
        finally: reset_correlation_id(token)
        check('MU016 revoke',lambda: alice.share('company-report','bob',None))
        revoked=ScopedReportRepository(repository,access,Principal('bob',permissions=frozenset({'report.create'})),auth)
        check('MU017 open-session revoke',lambda: expect(PermissionError,lambda: revoked.commit('company-report',base_revision=2,model=canonical_model(),commit_id='revoked')))
        check('MU018 owner trash/restore',lambda: owner_trash_restore(alice,repository))
        check('MU019 governance reconcile',lambda: assert_no_blocked(access))
        check('MU020 assets do not bypass ACL',lambda: expect(PermissionError,lambda: revoked.read_asset_for_report('company-report','sha256-'+'0'*64)))
    result={'schema_version':1,'status':'PASS' if all(item['status']=='PASS' for item in checks) else 'FAIL','candidate_sha':git_head(),'created_at':datetime.now(timezone.utc).isoformat(),'browser_mode':'model-boundary; run with a live target URL for browser-context evidence','checks':checks,'passed':sum(item['status']=='PASS' for item in checks),'failed':sum(item['status']=='FAIL' for item in checks)}
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print(json.dumps({'status':result['status'],'passed':result['passed'],'failed':result['failed'],'output':str(output)},sort_keys=True)); return 0 if result['status']=='PASS' else 2


def git_head():
    import subprocess
    return subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()

def assert_ids(records, expected): assert {record.report_id for record in records}==expected
def assert_no_blocked(access): assert access.reconcile()['blocked']==[]
def expect(error, fn):
    try: fn()
    except error: return
    raise AssertionError(f'{error.__name__} was not raised')
def stale_conflict(editor, revision):
    editor.commit('company-report',base_revision=revision,model=canonical_model({'items':[{'id':'a','type':'text','order':0,'text':'first'}]}),commit_id='first')
    expect(RevisionConflictError,lambda: editor.commit('company-report',base_revision=revision,model=canonical_model({'items':[{'id':'b','type':'text','order':0,'text':'stale'}]}),commit_id='stale'))
def audit_event(access, report_id, editor):
    current=editor._repository.get(report_id)
    editor.commit(report_id,base_revision=current.revision,model=canonical_model(),commit_id='correlation-commit')
    event=access.audit.read(report_id=report_id)[-1]; assert event['actor_subject']=='bob'; assert event['correlation_id']=='company-acceptance-correlation'
def owner_trash_restore(owner, repository):
    current=repository.get('company-report'); owner.trash_report('company-report',expected_revision=current.revision); owner.restore('company-report'); assert repository.get('company-report').report_id=='company-report'

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument('--output',required=True,type=Path); return run(parser.parse_args().output)
if __name__=='__main__': raise SystemExit(main())
