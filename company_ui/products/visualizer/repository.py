from __future__ import annotations

import json, os, tempfile
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from threading import RLock
from typing import Mapping, Any, Iterator

from .domain import ReportRecord, ReportNotFoundError, RevisionConflictError, VisualizerContractError, canonical_model, stable_json, utc_now, validate_report_id


class ReportRepository:
    """Atomic revision-aware file repository.

    The in-process RLock protects threads. A repository lock file additionally
    serializes transactions across independent application processes which point
    at the same data directory. This prevents two stale writers from both
    accepting the same base revision and silently losing an edit.
    """
    def __init__(self, root: str | Path):
        self.root=Path(root).expanduser().resolve(); self.root.mkdir(parents=True, exist_ok=True)
        self.quarantine=self.root/'_quarantine'; self._lock=RLock(); self._lock_path=self.root/'.repository.lock'

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        with self._lock:
            handle=self._lock_path.open('a+b')
            try:
                try:
                    import fcntl
                    fcntl.flock(handle.fileno(),fcntl.LOCK_EX)
                except ImportError:  # pragma: no cover - production target is Linux
                    pass
                yield
            finally:
                try:
                    import fcntl
                    fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
                except ImportError:  # pragma: no cover
                    pass
                handle.close()

    def _path(self, report_id: str) -> Path: return self.root/f'{validate_report_id(report_id)}.json'

    @staticmethod
    def _fsync_dir(directory: Path) -> None:
        try:
            fd=os.open(directory,os.O_DIRECTORY); os.fsync(fd); os.close(fd)
        except (AttributeError,OSError): pass

    def _atomic_write(self, path: Path, payload: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd,tmp=tempfile.mkstemp(prefix=f'.{path.name}.',suffix='.tmp',dir=path.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as f:
                f.write(payload); f.flush(); os.fsync(f.fileno())
            os.replace(tmp,path); self._fsync_dir(path.parent)
        finally:
            try: os.unlink(tmp)
            except FileNotFoundError: pass

    def _save_unlocked(self, record: ReportRecord) -> ReportRecord:
        self._atomic_write(self._path(record.report_id),stable_json(record.to_dict())+'\n'); return record

    def _get_unlocked(self, report_id: str) -> ReportRecord:
        path=self._path(report_id)
        if not path.is_file(): raise ReportNotFoundError(report_id)
        try: return ReportRecord.from_dict(json.loads(path.read_text(encoding='utf-8')))
        except Exception as exc:
            self.quarantine.mkdir(parents=True,exist_ok=True)
            target=self.quarantine/f'{path.stem}.{int(path.stat().st_mtime_ns)}.corrupt.json'
            try: os.replace(path,target); self._fsync_dir(path.parent)
            except OSError: pass
            raise VisualizerContractError(f'corrupt report quarantined: {report_id}') from exc

    def save(self, record: ReportRecord) -> ReportRecord:
        with self._transaction(): return self._save_unlocked(record)

    def create(self, report_id: str, *, title: str='Untitled report', model: Mapping[str,Any]|None=None, metadata: Mapping[str,Any]|None=None) -> ReportRecord:
        with self._transaction():
            path=self._path(report_id)
            if path.exists(): raise VisualizerContractError(f'report already exists: {report_id}')
            now=utc_now(); rec=ReportRecord(validate_report_id(report_id),1,str(title).strip() or 'Untitled report',canonical_model(model),dict(metadata or {}),(),now,now)
            return self._save_unlocked(rec)

    def get(self, report_id: str) -> ReportRecord:
        with self._transaction(): return self._get_unlocked(report_id)

    def list(self) -> list[ReportRecord]:
        with self._transaction():
            out=[]
            for path in sorted(self.root.glob('*.json')):
                try: out.append(self._get_unlocked(path.stem))
                except VisualizerContractError: continue
            return sorted(out,key=lambda r:(r.updated_at,r.report_id),reverse=True)

    def commit(self, report_id: str, *, base_revision: int, model: Mapping[str,Any], commit_id: str) -> ReportRecord:
        if not commit_id or len(commit_id)>160: raise VisualizerContractError('invalid commit id')
        with self._transaction():
            cur=self._get_unlocked(report_id)
            if commit_id in cur.commit_ids: return cur
            if cur.revision != base_revision: raise RevisionConflictError(cur.revision, base_revision)
            now=utc_now(); next_=replace(cur,revision=cur.revision+1,model=canonical_model(model),commit_ids=tuple((*cur.commit_ids,commit_id)[-256:]),updated_at=now)
            return self._save_unlocked(next_)

    def rename(self, report_id: str, title: str, *, expected_revision: int) -> ReportRecord:
        with self._transaction():
            cur=self._get_unlocked(report_id)
            if cur.revision != expected_revision: raise RevisionConflictError(cur.revision,expected_revision)
            cleaned=' '.join(str(title).replace('\x00','').split())[:160] or 'Untitled report'
            return self._save_unlocked(replace(cur,title=cleaned,revision=cur.revision+1,updated_at=utc_now()))

    def delete(self, report_id: str, *, expected_revision: int) -> bool:
        with self._transaction():
            cur=self._get_unlocked(report_id)
            if cur.revision != expected_revision: raise RevisionConflictError(cur.revision,expected_revision)
            self._path(report_id).unlink(); self._fsync_dir(self.root); return True

    def delete_if_blank(self, report_id: str, *, expected_revision: int) -> bool:
        with self._transaction():
            cur=self._get_unlocked(report_id)
            if cur.revision != expected_revision: raise RevisionConflictError(cur.revision,expected_revision)
            if cur.model.get('items') or cur.model.get('groups'): return False
            self._path(report_id).unlink(); self._fsync_dir(self.root); return True
