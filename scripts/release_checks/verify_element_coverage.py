#!/usr/bin/env python3
"""Validate the exact maintained Visembler production-element proof map."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAP = ROOT / "scripts" / "release_checks" / "production_element_coverage.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _matrix_elements(path: Path) -> list[str]:
    elements = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.count("|") < 3:
            continue
        element = line.split("|", 2)[1].strip()
        if element and element != "Element" and not set(element) <= {"-", ":", " "}:
            elements.append(element)
    return elements


def _proof_error(proof: dict) -> str | None:
    target = ROOT / proof["path"]
    if not target.is_file():
        return f"proof path does not exist: {proof['path']}"
    source = target.read_text(encoding="utf-8")
    if "test" in proof and not re.search(rf"\bdef\s+{re.escape(proof['test'])}\s*\(", source):
        return f"proof test is not defined: {proof['path']}::{proof['test']}"
    if "check_id" in proof and proof["check_id"] not in source:
        return f"release check id is not defined: {proof['path']}::{proof['check_id']}"
    return None


def coverage_report() -> dict:
    config = _read_json(MAP)
    maintained = _matrix_elements(ROOT / config["maintained_set"])
    fixtures = _read_json(ROOT / config["generic_fixture_set"])["cases"]
    fixture_by_element = {case["element"]: case for case in fixtures}
    entries = config["entries"]
    mapped = [entry["element"] for entry in entries]
    errors: list[str] = []

    if len(maintained) != len(set(maintained)):
        errors.append("maintained matrix contains duplicate elements")
    if len(mapped) != len(set(mapped)):
        errors.append("coverage map contains duplicate elements")
    if set(mapped) != set(maintained):
        errors.append("coverage map set does not exactly match the maintained matrix")
    if len(fixtures) != len(fixture_by_element):
        errors.append("generic fixture set contains duplicate elements")

    generic_elements: list[str] = []
    specialized_elements: list[str] = []
    for entry in entries:
        element = entry["element"]
        verification = entry.get("verification", {})
        mode = verification.get("mode")
        if mode == "generic":
            generic_elements.append(element)
            case_name = verification.get("fixture_case")
            case = fixture_by_element.get(case_name)
            if case is None:
                errors.append(f"{element}: generic fixture case is missing: {case_name}")
            elif case["engine"] != entry["engine"]:
                errors.append(f"{element}: generic engine differs from fixture ({entry['engine']} != {case['engine']})")
            if case_name != element:
                errors.append(f"{element}: generic fixture mapping is not explicit to the same element")
        elif mode == "specialized":
            specialized_elements.append(element)
            proofs = verification.get("proofs", [])
            if not proofs:
                errors.append(f"{element}: specialized entry has no proof paths")
            if not any("browser" in proof.get("kind", "") for proof in proofs):
                errors.append(f"{element}: specialized entry has no browser proof")
            for proof in proofs:
                error = _proof_error(proof)
                if error:
                    errors.append(f"{element}: {error}")
        else:
            errors.append(f"{element}: unknown verification mode {mode!r}")

    unexpected_fixtures = sorted(set(fixture_by_element) - set(maintained))
    if unexpected_fixtures:
        errors.append(f"generic fixtures contain elements outside the maintained matrix: {unexpected_fixtures}")
    if set(fixture_by_element) != set(generic_elements):
        errors.append("generic fixture set does not exactly match generic entries in the coverage map")
    uncovered = sorted(set(maintained) - set(fixture_by_element) - set(specialized_elements))
    if uncovered:
        errors.append(f"maintained elements have no generic or specialized proof: {uncovered}")

    report = {
        "status": "FAIL" if errors else "PASS",
        "maintained_count": len(maintained),
        "mapped_count": len(mapped),
        "generic_fixture_count": len(fixtures),
        "generic_mapped_count": len(generic_elements),
        "specialized_mapped_count": len(specialized_elements),
        "generic_elements": generic_elements,
        "specialized_elements": specialized_elements,
        "errors": errors,
    }
    if errors:
        raise ValueError(json.dumps(report, indent=2, ensure_ascii=False))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit the derived coverage report as JSON")
    args = parser.parse_args()
    try:
        report = coverage_report()
    except ValueError as error:
        print(error)
        return 1
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(
            f"PASS maintained={report['maintained_count']} mapped={report['mapped_count']} "
            f"generic_fixture={report['generic_fixture_count']} specialized={report['specialized_mapped_count']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
