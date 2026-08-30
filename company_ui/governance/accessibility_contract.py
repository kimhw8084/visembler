from __future__ import annotations

from pathlib import Path

from .models import GovernanceFinding


def scan_accessibility_contract(root: Path) -> tuple[GovernanceFinding, ...]:
    findings: list[GovernanceFinding] = []
    required_fragments = {
        'company_ui/design/css.py': (
            '@media (prefers-reduced-motion: reduce)',
            '.cui-focusable:focus-visible',
        ),
        'company_ui/integrations/nicegui_interactions.py': (
            'role="dialog" aria-modal="true"',
            'aria-labelledby=',
            'aria-describedby=',
            "node.setAttribute('role', 'tooltip')",
            'aria-live="polite"',
        ),
        'company_ui/integrations/nicegui_layout.py': (
            'aria-labelledby=',
            'aria-describedby=',
        ),
        'company_ui/integrations/nicegui_content.py': (
            'role="dialog" aria-modal="true" aria-label="Command palette"',
            'role="listbox" aria-label="Commands"',
            'aria-disabled=',
            "key == 'Escape'",
            "key == 'ArrowDown'",
            "key == 'ArrowUp'",
        ),
        'company_ui/integrations/nicegui_feedback_runtime.py': (
            "stack.setAttribute('aria-live', 'polite')",
            "close.setAttribute('aria-label', 'Dismiss notification')",
        ),
    }
    for rel, fragments in required_fragments.items():
        path = root / rel
        if not path.exists():
            findings.append(GovernanceFinding('a11y.missing-source', rel, 'critical accessibility source is missing'))
            continue
        text = path.read_text(encoding='utf-8')
        for fragment in fragments:
            if fragment not in text:
                findings.append(GovernanceFinding('a11y.critical-contract', rel, f'missing required accessibility behavior: {fragment}'))
    css = ''.join((root / rel).read_text(encoding='utf-8') for rel in (
        'company_ui/components/css.py', 'company_ui/design/constitution_css.py', 'company_ui/design/hardening_css.py'
    ))
    for selector in ('.cui-button:focus-visible', '.cui-icon-button:focus-visible', '.cui-toast__close:focus-visible'):
        if selector not in css:
            findings.append(GovernanceFinding('a11y.focus-visible', 'combined-css', f'missing visible focus treatment for {selector}'))
    return tuple(findings)
