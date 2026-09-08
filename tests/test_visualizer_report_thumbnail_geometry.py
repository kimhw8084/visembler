from __future__ import annotations

import math
import re
from pathlib import Path

from company_ui.products.visualizer.page import _report_thumbnail_geometry, _report_thumbnail_markup


SVG_GEOMETRY = re.compile(r'\b(x|y|width|height)="([^"]+)"')


def _assert_valid_svg_geometry(markup: str) -> None:
    values = [(attribute, float(value)) for attribute, value in SVG_GEOMETRY.findall(markup)]
    assert values, "thumbnail did not emit measurable SVG geometry"
    assert all(math.isfinite(value) for _, value in values), values
    assert all(value >= 0 for _, value in values), values


def test_thumbnail_geometry_includes_items_beyond_stale_canvas_bounds() -> None:
    """Reproduce the -6.0/-27.9/-76.2 heights from the completed crawl."""
    model = {
        "canvas": {"width": 1600, "height": 900},
        "items": [
            {
                "id": "short",
                "engine": "TextEngine",
                "element": "Key Takeaway",
                "x": 40,
                "y": 973,
                "w": 520,
                "h": 24,
                "text": "Short item below the stale canvas",
            },
            {
                "id": "chart",
                "engine": "CoreChartEngine",
                "element": "Line Chart",
                "x": 600,
                "y": 1106,
                "w": 840,
                "h": 260,
                "data": [["A", 1], ["B", 2]],
            },
            {
                "id": "wafer",
                "engine": "WaferFabEngine",
                "element": "Wafer Map",
                "x": 1500,
                "y": 1400,
                "w": 0,
                "h": 0,
                "observations": [{"x": 0, "y": 0, "value": 1}],
            },
        ],
    }

    markup = _report_thumbnail_markup(model, "Out-of-bounds report")

    _assert_valid_svg_geometry(markup)
    assert 'height="-6.0"' not in markup
    assert 'height="-27.9"' not in markup
    assert 'height="-76.2"' not in markup


def test_thumbnail_geometry_bounds_dense_unpositioned_and_pathological_items() -> None:
    engines = (
        "TextEngine",
        "MetricEngine",
        "CoreChartEngine",
        "TableEngine",
        "TimelineEngine",
        "DiagramEngine",
        "ImageMediaEngine",
        "WaferFabEngine",
    )
    items = [
        {
            "id": f"item-{index}",
            "engine": engines[index % len(engines)],
            "element": "Preview fixture",
            "title": f"Item {index}",
            "data": [["A", 0], ["B", 2]],
            "nodes": ["A", "B"],
            "observations": [{"x": 0, "y": 0, "value": 0}],
        }
        for index in range(12)
    ]
    items[0].update(x=float("nan"), y=float("inf"), w=-20, h=-10)
    model = {"canvas": {"width": float("inf"), "height": -1}, "items": items}

    geometry = _report_thumbnail_geometry(model)
    markup = _report_thumbnail_markup(model, "Dense mixed report")

    assert len(geometry) == 12
    assert all(12 <= row["x"] <= 307 and 12 <= row["y"] <= 159 for row in geometry)
    assert all(1 <= row["w"] <= 308 - row["x"] for row in geometry)
    assert all(1 <= row["h"] <= 160 - row["y"] for row in geometry)
    assert markup.count("data-preview-family=") == 12
    _assert_valid_svg_geometry(markup)


def test_native_release_requires_report_hub_browser_error_gate() -> None:
    verifier = (Path(__file__).resolve().parents[1] / "scripts" / "verify_release.py").read_text(encoding="utf-8")
    assert "report-hub-browser-errors" in verifier
    assert "run_report_hub_browser_error_gate.py" in verifier
    assert "required_names.update({'report-hub-browser-errors'" in verifier
