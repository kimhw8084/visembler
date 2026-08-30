from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePath

from .redaction import safe_filename


@dataclass(frozen=True, slots=True)
class UploadPolicy:
    max_bytes: int = 25 * 1024 * 1024
    allowed_extensions: frozenset[str] = frozenset({'.csv', '.xlsx', '.json', '.txt', '.png', '.jpg', '.jpeg', '.pdf'})
    allowed_media_types: frozenset[str] = frozenset({
        'text/csv', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/json', 'text/plain', 'image/png', 'image/jpeg', 'application/pdf',
    })
    reject_active_content: bool = True

    def __post_init__(self) -> None:
        if self.max_bytes <= 0:
            raise ValueError('max_bytes must be positive')
        if any(not ext.startswith('.') for ext in self.allowed_extensions):
            raise ValueError('allowed extensions must start with a dot')

    def validate(self, filename: str, size: int, media_type: str | None = None) -> str:
        if size < 0 or size > self.max_bytes:
            raise ValueError('upload size is not permitted')
        name = safe_filename(filename)
        ext = PurePath(name).suffix.lower()
        if ext not in self.allowed_extensions:
            raise ValueError(f'file extension {ext or "<none>"} is not permitted')
        if media_type and media_type.lower() not in self.allowed_media_types:
            raise ValueError(f'media type {media_type} is not permitted')
        if self.reject_active_content and ext in {'.html', '.htm', '.svg', '.js', '.mjs'}:
            raise ValueError('active content uploads are not permitted')
        return name
