from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "release_checks"))

from crawler_runtime import CrawlerReportManager
from editor_host import EditorHost
from native_common import text_model


def test_crawler_report_manager_reuses_bounds_and_cleans_only_owned_reports(tmp_path: Path) -> None:
    host = EditorHost(ROOT, tmp_path / "isolated-data")
    unrelated = host.repository.create("real-report", title="Preserve me", model=text_model("real"))
    manager = CrawlerReportManager(host, run_id="test-run", max_existing=4)

    first = manager.reset(text_model("one"), "editor")
    second = manager.reset(text_model("two"), "editor")

    assert first == second
    assert manager.created_total == 1
    assert manager.assert_bounded() == 1
    assert host.repository.get(first).model["items"][0]["text"] == "two"

    changed = host.repository.rename(first, "Mutated title", expected_revision=host.repository.get(first).revision)
    host.repository.update_description(first, "Mutated description", expected_revision=changed.revision)
    manager.reset(text_model("two"), "editor")
    reset = host.repository.get(first)
    assert reset.title == "[Crawler test-run] editor"
    assert reset.metadata["description"] == ""

    host.repository.trash_report(first, expected_revision=reset.revision)
    manager.restore_missing_scenarios()
    assert host.repository.get(first).model["items"][0]["text"] == "two"

    before = manager.snapshot_ids()
    ui_created = host.create(model=text_model("ui-created"), name="ui-generated")
    assert manager.adopt_new(before, "duplicate action") == {ui_created}
    assert manager.assert_bounded() == 2
    assert "Crawler-owned temporary report" in host.repository.get(ui_created).metadata["description"]

    owned = host.repository.get(first)
    host.repository.trash_report(first, expected_revision=owned.revision)
    manager.cleanup_all()

    assert manager.metrics()["active"] == 0
    assert manager.created_total == manager.cleaned == 2
    assert host.repository.get(unrelated.report_id).title == "Preserve me"


def test_crawler_report_manager_rejects_unowned_deletion(tmp_path: Path) -> None:
    host = EditorHost(ROOT, tmp_path / "isolated-data")
    host.repository.create("real-report", title="Preserve me", model=text_model("real"))
    manager = CrawlerReportManager(host, run_id="test-run", max_existing=3)

    try:
        manager.delete_owned("real-report")
    except RuntimeError as error:
        assert "refusing to delete unowned report" in str(error)
    else:
        raise AssertionError("crawler manager deleted an unowned report")

    assert host.repository.get("real-report").title == "Preserve me"
