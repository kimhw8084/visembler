from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "release_checks"))
try:
    from verify_element_coverage import coverage_report
finally:
    sys.path.pop(0)


def test_maintained_production_element_map_is_exact_and_complete() -> None:
    report = coverage_report()

    assert report["status"] == "PASS"
    assert report["maintained_count"] == report["mapped_count"] == 52
    assert report["generic_fixture_count"] == report["generic_mapped_count"] == 39
    assert report["specialized_mapped_count"] == 13
    assert report["generic_fixture_count"] + report["specialized_mapped_count"] == report["maintained_count"]
