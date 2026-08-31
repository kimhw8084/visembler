from __future__ import annotations

import base64, json, os, shutil, tempfile, uuid
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from threading import RLock
from typing import Mapping, Any, Iterator

from .domain import ReportRecord, ReportNotFoundError, RevisionConflictError, VisualizerContractError, canonical_model, stable_json, utc_now, validate_report_id
from .assets_store import AssetStore


class ReportRepository:
    """Atomic revision-aware file repository.

    The in-process RLock protects threads. A repository lock file additionally
    serializes transactions across independent application processes which point
    at the same data directory. This prevents two stale writers from both
    accepting the same base revision and silently losing an edit.
    """
    def __init__(self, root: str | Path, *, history_limit: int=80):
        self.root=Path(root).expanduser().resolve(); self.root.mkdir(parents=True, exist_ok=True)
        self.quarantine=self.root/'_quarantine'; self.trash=self.root/'_trash'; self._lock=RLock(); self._lock_path=self.root/'.repository.lock'
        self.assets=AssetStore(self.root/'_assets')
        self.history=self.root/'_history'; self.history_limit=max(4,int(history_limit))

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
    def _history_path(self, report_id: str) -> Path: return self.history/validate_report_id(report_id)
    def _trash_history_path(self, report_id: str) -> Path: return self.trash/'_history'/validate_report_id(report_id)

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

    def _snapshot_unlocked(self, record: ReportRecord, *, label: str='', checkpoint: bool=False) -> None:
        directory=self._history_path(record.report_id); suffix=f'-checkpoint-{uuid.uuid4().hex[:10]}' if checkpoint else ''
        payload={'report_id':record.report_id,'revision':record.revision,'title':record.title,'updated_at':record.updated_at,'label':' '.join(label.split())[:160],'checkpoint':checkpoint,'model':record.model}
        self._atomic_write(directory/f'r{record.revision}{suffix}.json',stable_json(payload)+'\n'); self._trim_history_unlocked(record.report_id)

    def _trim_history_unlocked(self, report_id: str) -> None:
        entries=sorted(self._history_path(report_id).glob('*.json'),key=lambda path:(path.stat().st_mtime_ns,path.name),reverse=True)
        for path in entries[self.history_limit:]: path.unlink(missing_ok=True)

    def _history_entries_unlocked(self, report_id: str) -> list[dict[str,Any]]:
        entries=[]
        for path in self._history_path(report_id).glob('*.json'):
            try:
                value=json.loads(path.read_text(encoding='utf-8'))
                if value.get('report_id')!=report_id or not isinstance(value.get('revision'),int) or not isinstance(value.get('model'),Mapping): raise ValueError('invalid history entry')
                entries.append({key:value.get(key) for key in ('revision','title','updated_at','label','checkpoint')}|{'history_id':path.stem})
            except Exception:
                self.quarantine.mkdir(parents=True,exist_ok=True); os.replace(path,self.quarantine/f'{path.stem}.{uuid.uuid4().hex}.history-corrupt.json')
        return sorted(entries,key=lambda value:(value['revision'],value['history_id']),reverse=True)

    def _load_history_unlocked(self, report_id: str, history_id: str) -> Mapping[str,Any]:
        if not isinstance(history_id,str) or not history_id.startswith('r') or '/' in history_id or '\\' in history_id: raise VisualizerContractError('invalid history revision')
        path=self._history_path(report_id)/f'{history_id}.json'
        try: value=json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError as exc: raise ReportNotFoundError(history_id) from exc
        except Exception as exc: raise VisualizerContractError('corrupt report history entry') from exc
        if value.get('report_id')!=report_id or not isinstance(value.get('model'),Mapping): raise VisualizerContractError('invalid report history entry')
        return value

    def _prepare_model_unlocked(self, model: Mapping[str,Any]) -> dict[str,Any]:
        prepared=canonical_model(model)
        for entry in prepared['items']:
            if entry.get('engine')=='ImageMediaEngine' and entry.get('asset_id'):
                self.assets.read_image(str(entry['asset_id'])); entry.pop('src',None); continue
            if entry.get('engine')!='ImageMediaEngine' or not isinstance(entry.get('src'),str): continue
            src=entry['src']
            if not src.startswith('data:') or ';base64,' not in src: raise VisualizerContractError(f'image {entry.get("id","?")} must use an embedded validated data URL or asset reference')
            header,encoded=src.split(',',1)
            if header not in {'data:image/png;base64','data:image/jpeg;base64','data:image/webp;base64'}: raise VisualizerContractError('only embedded PNG, JPEG, or WebP images are supported')
            try: data=base64.b64decode(encoded,validate=True)
            except Exception as exc: raise VisualizerContractError('embedded image base64 is invalid') from exc
            entry['asset_id']=self.assets.put_image(data); entry.pop('src',None)
        return canonical_model(prepared)

    def _asset_refs_unlocked(self) -> set[str]:
        refs=set()
        for directory in (self.root,self.trash,self.history,self.trash/'_history'):
            if not directory.exists(): continue
            for path in directory.rglob('*.json'):
                try: value=json.loads(path.read_text(encoding='utf-8')); model=value.get('model',{})
                except Exception: continue
                for entry in model.get('items',[]) if isinstance(model,Mapping) else []:
                    if isinstance(entry,Mapping) and isinstance(entry.get('asset_id'),str): refs.add(entry['asset_id'])
        return refs

    def collect_garbage(self) -> list[str]:
        with self._transaction():
            return self._collect_garbage_unlocked()

    def _collect_garbage_unlocked(self) -> list[str]:
        refs=self._asset_refs_unlocked(); removed=sorted(self.assets.ids()-refs)
        for asset_id in removed: self.assets.delete(asset_id)
        return removed

    def _get_unlocked(self, report_id: str) -> ReportRecord:
        path=self._path(report_id)
        if not path.is_file(): raise ReportNotFoundError(report_id)
        try: record=ReportRecord.from_dict(json.loads(path.read_text(encoding='utf-8')))
        except Exception as exc:
            self.quarantine.mkdir(parents=True,exist_ok=True)
            target=self.quarantine/f'{path.stem}.{int(path.stat().st_mtime_ns)}.corrupt.json'
            try: os.replace(path,target); self._fsync_dir(path.parent)
            except OSError: pass
            raise VisualizerContractError(f'corrupt report quarantined: {report_id}') from exc
        prepared=self._prepare_model_unlocked(record.model)
        if prepared!=record.model: record=replace(record,model=prepared); self._save_unlocked(record)
        return record

    def save(self, record: ReportRecord) -> ReportRecord:
        with self._transaction(): return self._save_unlocked(record)

    def create(self, report_id: str, *, title: str='Untitled report', model: Mapping[str,Any]|None=None, metadata: Mapping[str,Any]|None=None) -> ReportRecord:
        with self._transaction():
            path=self._path(report_id)
            if path.exists(): raise VisualizerContractError(f'report already exists: {report_id}')
            now=utc_now(); rec=ReportRecord(validate_report_id(report_id),1,str(title).strip() or 'Untitled report',self._prepare_model_unlocked(model or {}),dict(metadata or {}),(),now,now)
            self._save_unlocked(rec); self._snapshot_unlocked(rec,label='Created'); return rec

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
            now=utc_now(); next_=replace(cur,revision=cur.revision+1,model=self._prepare_model_unlocked(model),commit_ids=tuple((*cur.commit_ids,commit_id)[-256:]),updated_at=now)
            self._save_unlocked(next_); self._snapshot_unlocked(next_,label='Edit'); return next_

    def list_history(self, report_id: str) -> list[dict[str,Any]]:
        with self._transaction(): self._get_unlocked(report_id); return self._history_entries_unlocked(validate_report_id(report_id))

    def checkpoint(self, report_id: str, name: str, *, expected_revision: int) -> dict[str,Any]:
        with self._transaction():
            record=self._get_unlocked(report_id)
            if record.revision!=expected_revision: raise RevisionConflictError(record.revision,expected_revision)
            label=' '.join(str(name).replace('\x00','').split())[:160]
            if not label: raise VisualizerContractError('checkpoint name is required')
            self._snapshot_unlocked(record,label=label,checkpoint=True)
            return self._history_entries_unlocked(record.report_id)[0]

    def restore_history(self, report_id: str, history_id: str, *, expected_revision: int) -> ReportRecord:
        with self._transaction():
            current=self._get_unlocked(report_id)
            if current.revision!=expected_revision: raise RevisionConflictError(current.revision,expected_revision)
            source=self._load_history_unlocked(current.report_id,history_id); now=utc_now()
            restored=replace(current,revision=current.revision+1,model=self._prepare_model_unlocked(source['model']),commit_ids=(),updated_at=now)
            self._save_unlocked(restored); self._snapshot_unlocked(restored,label=f'Restored {history_id}'); return restored

    def duplicate_from_history(self, source_report_id: str, history_id: str, new_report_id: str, *, title: str|None=None) -> ReportRecord:
        with self._transaction():
            source=self._load_history_unlocked(validate_report_id(source_report_id),history_id)
            target=self._path(new_report_id)
            if target.exists(): raise VisualizerContractError(f'report already exists: {new_report_id}')
            now=utc_now(); record=ReportRecord(validate_report_id(new_report_id),1,str(title or f'{source.get("title","Report")} copy')[:160],self._prepare_model_unlocked(source['model']),{'duplicated_from_history':f'{source_report_id}:{history_id}'},(),now,now)
            self._save_unlocked(record); self._snapshot_unlocked(record,label=f'Duplicated from {history_id}'); return record

    def rename(self, report_id: str, title: str, *, expected_revision: int) -> ReportRecord:
        with self._transaction():
            cur=self._get_unlocked(report_id)
            if cur.revision != expected_revision: raise RevisionConflictError(cur.revision,expected_revision)
            cleaned=' '.join(str(title).replace('\x00','').split())[:160] or 'Untitled report'
            updated=replace(cur,title=cleaned,revision=cur.revision+1,updated_at=utc_now())
            self._save_unlocked(updated); self._snapshot_unlocked(updated,label='Renamed'); return updated

    def delete(self, report_id: str, *, expected_revision: int) -> bool:
        with self._transaction():
            cur=self._get_unlocked(report_id)
            if cur.revision != expected_revision: raise RevisionConflictError(cur.revision,expected_revision)
            self._path(report_id).unlink(); shutil.rmtree(self._history_path(report_id),ignore_errors=True); self._fsync_dir(self.root); self._collect_garbage_unlocked(); return True

    def trash_report(self, report_id: str, *, expected_revision: int) -> ReportRecord:
        with self._transaction():
            cur=self._get_unlocked(report_id)
            if cur.revision != expected_revision: raise RevisionConflictError(cur.revision,expected_revision)
            self.trash.mkdir(parents=True,exist_ok=True); target=self.trash/f'{cur.report_id}.json'
            if target.exists(): raise VisualizerContractError('a trashed report with this id already exists')
            os.replace(self._path(report_id),target)
            if self._history_path(report_id).exists(): self._trash_history_path(report_id).parent.mkdir(parents=True,exist_ok=True); os.replace(self._history_path(report_id),self._trash_history_path(report_id))
            self._fsync_dir(self.root); self._fsync_dir(self.trash); return cur

    def list_trash(self) -> list[ReportRecord]:
        with self._transaction():
            if not self.trash.exists(): return []
            out=[]
            for path in sorted(self.trash.glob('*.json')):
                try: out.append(ReportRecord.from_dict(json.loads(path.read_text(encoding='utf-8'))))
                except Exception: continue
            return sorted(out,key=lambda r:(r.updated_at,r.report_id),reverse=True)

    def restore(self, report_id: str) -> ReportRecord:
        with self._transaction():
            report_id=validate_report_id(report_id); source=self.trash/f'{report_id}.json'
            if not source.is_file(): raise ReportNotFoundError(report_id)
            if self._path(report_id).exists(): raise VisualizerContractError('an active report already uses this id')
            record=ReportRecord.from_dict(json.loads(source.read_text(encoding='utf-8')))
            os.replace(source,self._path(report_id))
            if self._trash_history_path(report_id).exists(): self.history.mkdir(parents=True,exist_ok=True); os.replace(self._trash_history_path(report_id),self._history_path(report_id))
            self._fsync_dir(self.root); self._fsync_dir(self.trash); return record

    def delete_if_blank(self, report_id: str, *, expected_revision: int) -> bool:
        with self._transaction():
            cur=self._get_unlocked(report_id)
            if cur.revision != expected_revision: raise RevisionConflictError(cur.revision,expected_revision)
            if cur.model.get('items') or cur.model.get('groups'): return False
            self._path(report_id).unlink(); shutil.rmtree(self._history_path(report_id),ignore_errors=True); self._fsync_dir(self.root); self._collect_garbage_unlocked(); return True
