from __future__ import annotations

from company_ui.products.visualizer.page import _normalize_presets


def test_wave6_server_preserves_legacy_report_preset_shape() -> None:
    raw = [{
        "id": "report-1",
        "name": "Review",
        "model": {
            "version": 1,
            "mode": "smart",
            "layoutPreset": "editorial",
            "nextId": 2,
            "items": [],
            "groups": {},
            "datasets": [],
        },
    }]
    presets = _normalize_presets(raw)
    assert len(presets) == 1
    assert presets[0]["id"] == "report-1"
    assert presets[0]["name"] == "Review"
    assert "model" in presets[0]
    assert "kind" not in presets[0]


def test_wave6_server_roundtrips_section_preset_with_typed_values() -> None:
    raw = [{
        "id": "section-1",
        "name": "Fab evidence",
        "kind": "section",
        "payload": {
            "version": 2,
            "kind": "composition",
            "source_mode": "guided",
            "items": [
                {
                    "id": "c1",
                    "type": "metric",
                    "engine": "MetricEngine",
                    "element": "Hero KPI",
                    "title": "Numeric zero",
                    "value": 0,
                    "_clipboard_rect": {"x": 10, "y": 20, "w": 220, "h": 140},
                },
                {
                    "id": "c2",
                    "type": "metric",
                    "engine": "MetricEngine",
                    "element": "Hero KPI",
                    "title": "String zero",
                    "value": "0",
                    "intentional_blank": "",
                    "missing": None,
                    "_clipboard_rect": {"x": 250, "y": 20, "w": 220, "h": 140},
                },
            ],
            "groups": [],
            "datasets": [{
                "id": "ds1",
                "name": "Typed",
                "fields": [{"id": "v", "name": "Value", "type": "string"}],
                "rows": [[0, "0", None, ""]],
            }],
        },
    }]

    presets = _normalize_presets(raw)
    assert len(presets) == 1
    preset = presets[0]
    assert preset["kind"] == "section"
    assert preset["payload"]["kind"] == "composition"
    assert preset["payload"]["items"][0]["value"] == 0
    assert preset["payload"]["items"][1]["value"] == "0"
    assert preset["payload"]["items"][1]["intentional_blank"] == ""
    assert preset["payload"]["items"][1]["missing"] is None
    assert preset["payload"]["datasets"][0]["rows"][0] == [0, "0", None, ""]


def test_wave6_server_rejects_malformed_section_without_breaking_valid_entries() -> None:
    valid_report = {
        "id": "report-1",
        "name": "Review",
        "model": {
            "version": 1,
            "mode": "smart",
            "layoutPreset": "editorial",
            "nextId": 2,
            "items": [],
            "groups": {},
            "datasets": [],
        },
    }
    malformed = {
        "id": "bad",
        "name": "Bad section",
        "kind": "section",
        "payload": {"kind": "composition", "items": [{"id": "only-one"}]},
    }
    presets = _normalize_presets([malformed, valid_report])
    assert len(presets) == 1
    assert presets[0]["id"] == "report-1"


def test_wave6_server_rejects_invalid_embedded_image_in_section() -> None:
    malformed = {
        "id": "bad-image",
        "name": "Bad image section",
        "kind": "section",
        "payload": {
            "kind": "composition",
            "items": [
                {
                    "id": "c1",
                    "engine": "ImageMediaEngine",
                    "src": "data:image/png;base64,not-valid-base64!",
                },
                {"id": "c2", "engine": "TextEngine", "text": "Evidence"},
            ],
            "groups": [],
            "datasets": [],
        },
    }
    assert _normalize_presets([malformed]) == []
