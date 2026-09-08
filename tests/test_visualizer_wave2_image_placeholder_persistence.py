from __future__ import annotations

from company_ui.products.visualizer.repository import ReportRepository


def _metric(index: int) -> dict:
    return {
        "id": f"c{index}",
        "type": "metric",
        "engine": "MetricEngine",
        "element": "Hero KPI",
        "title": f"Metric {index}",
        "order": index - 1,
        "weight": 1.15,
        "z": index,
        "locked": False,
        "groupId": None,
        "value": index,
    }


def _base_model() -> dict:
    return {
        "schema_version": 1,
        "authoring_schema": "authoring-p0-v1",
        "datasets": [],
        "items": [_metric(index) for index in range(1, 6)],
        "groups": {},
        "mode": "smart",
        "layoutPreset": "editorial",
        "crossFilter": None,
        "canvas": {"width": 1600, "height": 900},
        "nextId": 6,
    }


def _image_item() -> dict:
    return {
        "id": "c6",
        "type": "image",
        "engine": "ImageMediaEngine",
        "element": "Image",
        "title": "Image",
        "showTitle": False,
        "textAlign": "left",
        "weight": 1.25,
        "order": 5,
        "locked": False,
        "groupId": None,
        "z": 6,
        "src": "",
        "alt": "",
        "caption": "",
        "fit": "fill",
        "focal": "50% 50%",
    }


def _diagram_item() -> dict:
    return {
        "id": "c7",
        "type": "diagram",
        "engine": "DiagramEngine",
        "element": "Process Flow",
        "title": "Process Flow",
        "showTitle": False,
        "textAlign": "left",
        "weight": 1.5,
        "order": 6,
        "locked": False,
        "groupId": None,
        "z": 7,
        "nodes": ["Signal", "Analyze", "Validate", "Decision"],
        "edges": [["Signal", "Analyze"], ["Analyze", "Validate"], ["Validate", "Decision"]],
        "direction": "right",
    }


def test_blank_image_placeholder_can_persist_before_upload(tmp_path) -> None:
    repository = ReportRepository(tmp_path)
    created = repository.create("wave2-image-placeholder", model=_base_model())
    model = dict(created.model)
    model["items"] = [*created.model["items"], _image_item()]
    model["nextId"] = 7
    committed = repository.commit(
        created.report_id,
        base_revision=created.revision,
        model=model,
        commit_id="wave2-add-blank-image",
    )
    assert committed.revision == created.revision + 1
    persisted = repository.get(created.report_id)
    assert len(persisted.model["items"]) == 6
    assert persisted.model["items"][-1]["engine"] == "ImageMediaEngine"
    assert persisted.model["items"][-1]["src"] == ""


def test_seventh_element_persists_after_blank_image_placeholder(tmp_path) -> None:
    repository = ReportRepository(tmp_path)
    created = repository.create("wave2-seventh-after-image", model=_base_model())
    first = dict(created.model)
    first["items"] = [*created.model["items"], _image_item()]
    first["nextId"] = 7
    after_image = repository.commit(
        created.report_id,
        base_revision=created.revision,
        model=first,
        commit_id="wave2-sixth-image",
    )
    second = dict(after_image.model)
    second["items"] = [*after_image.model["items"], _diagram_item()]
    second["nextId"] = 8
    after_diagram = repository.commit(
        created.report_id,
        base_revision=after_image.revision,
        model=second,
        commit_id="wave2-seventh-diagram",
    )
    assert after_diagram.revision == created.revision + 2
    persisted = repository.get(created.report_id)
    assert len(persisted.model["items"]) == 7
    assert persisted.model["items"][-2]["src"] == ""
    assert persisted.model["items"][-1]["engine"] == "DiagramEngine"
    assert persisted.model["items"][-1]["element"] == "Process Flow"
