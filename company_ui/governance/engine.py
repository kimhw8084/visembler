from __future__ import annotations

from pathlib import Path

from .accessibility_contract import scan_accessibility_contract
from .css_contract import scan_geometry_contract
from .models import GovernanceReport
from .public_api import scan_public_api_contract
from .release_contract import scan_release_contract
from .typography_motion_contract import scan_typography_motion_contract


def run_governance(root: str | Path = '.') -> GovernanceReport:
    source_root = Path(root).resolve()
    findings = (
        *scan_release_contract(source_root),
        *scan_accessibility_contract(source_root),
        *scan_geometry_contract(source_root),
        *scan_typography_motion_contract(source_root),
        *scan_public_api_contract(source_root),
    )
    return GovernanceReport(source_root, tuple(findings))
