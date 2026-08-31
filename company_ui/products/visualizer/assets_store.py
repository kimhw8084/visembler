from __future__ import annotations

import base64
import hashlib
import os
import tempfile
from pathlib import Path

from .domain import VisualizerContractError
from .files import validate_image_bytes


class AssetStore:
    """Local content-addressed binary storage for validated report assets."""
    def __init__(self, root: str | Path):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)

    @staticmethod
    def _id(data: bytes) -> str: return f'sha256-{hashlib.sha256(data).hexdigest()}'

    @staticmethod
    def _validate_id(asset_id: str) -> str:
        if not isinstance(asset_id,str) or not asset_id.startswith('sha256-') or len(asset_id)!=71 or any(ch not in '0123456789abcdef' for ch in asset_id[7:]): raise VisualizerContractError('invalid asset reference')
        return asset_id

    def _path(self, asset_id: str) -> Path: return self.root/f'{self._validate_id(asset_id)}.bin'

    def put_image(self, data: bytes) -> str:
        validate_image_bytes(data); asset_id=self._id(data); path=self._path(asset_id)
        if path.exists():
            if self.read_image(asset_id)==data: return asset_id
            raise VisualizerContractError('asset hash collision or corrupt asset')
        fd,temp=tempfile.mkstemp(prefix='.asset.',suffix='.tmp',dir=self.root)
        try:
            with os.fdopen(fd,'wb') as handle: handle.write(data); handle.flush(); os.fsync(handle.fileno())
            os.replace(temp,path)
        finally:
            try: os.unlink(temp)
            except FileNotFoundError: pass
        return asset_id

    def read_image(self, asset_id: str) -> bytes:
        path=self._path(asset_id)
        try: data=path.read_bytes()
        except FileNotFoundError as exc: raise VisualizerContractError(f'referenced asset is missing: {asset_id}') from exc
        if self._id(data)!=asset_id: raise VisualizerContractError(f'referenced asset is corrupt: {asset_id}')
        validate_image_bytes(data); return data

    def data_url(self, asset_id: str) -> str:
        data=self.read_image(asset_id); mime=str(validate_image_bytes(data)['mime'])
        return f'data:{mime};base64,{base64.b64encode(data).decode("ascii")}'

    def ids(self) -> set[str]: return {path.stem for path in self.root.glob('sha256-*.bin')}

    def delete(self, asset_id: str) -> None:
        try: self._path(asset_id).unlink()
        except FileNotFoundError: pass
