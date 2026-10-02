"""Controlled plain-copy extension for the report application.

The content registry offers entity/property/document viewers, but no short
plain-text heading, caption or changing report-status primitive. These roles
must not acquire Markdown semantics or stock Quasar label anatomy. This small
adapter renders escaped text in a semantic element, keeps sanitization enabled,
and inherits Company typography/classes. It owns no layout or control behavior.
"""
from __future__ import annotations

from html import escape


class ReportCopy:
    def __init__(self, text: str, *, tag: str = 'div'):
        if tag not in {'div', 'span', 'p', 'h2', 'h3'}:
            raise ValueError('Unsupported report copy semantics')
        # company-ui: allow-ai001 — catalog gap: escaped semantic plain copy; see module contract.
        from nicegui import ui
        self.element = ui.html(escape(str(text)), tag=tag, sanitize=True).classes('cui-report-copy')

    def classes(self, value: str):
        self.element.classes(value)
        return self

    def props(self, value: str):
        self.element.props(value)
        return self

    def set_text(self, value: str):
        self.element.set_content(escape(str(value)))
        return self
