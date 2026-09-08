"""Bounded, ownership-safe fixtures for exhaustive Visembler crawlers."""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any, Mapping

from company_ui.products.visualizer.domain import stable_json
from company_ui.products.visualizer.governance import ReportAccessCatalog


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:48] or "scenario"


class CrawlerReportManager:
    """Reuse a bounded report set and delete only resources owned by this run.

    The caller must provide an isolated NativeHost data directory.  Reports
    created directly carry ownership metadata; reports created indirectly by a
    UI action are adopted from an exact before/after identity delta and recorded
    in an ownership sidecar before they can be removed.
    """

    def __init__(self, host: Any, *, run_id: str | None = None, max_existing: int = 24) -> None:
        if max_existing < 2:
            raise ValueError("max_existing must allow at least two crawler fixtures")
        self.host = host
        self.repository = host.repository
        self.access = ReportAccessCatalog(self.repository)
        self.run_id = _slug(run_id or uuid.uuid4().hex[:10])
        self.max_existing = max_existing
        self.scenarios: dict[str, str] = {}
        self.scenario_models: dict[str, dict[str, Any]] = {}
        self.owned_ids: set[str] = set()
        self.created_total = 0
        self.cleaned = 0
        self.peak_existing = 0
        self._reset_count = 0
        self.data_root = Path(host.data).resolve()
        self.marker = self.data_root / f".crawler-owner-{self.run_id}.json"
        self.final_metrics: dict[str, int] | None = None
        self.data_root.mkdir(parents=True, exist_ok=True)
        self._write_marker()

    def __enter__(self) -> "CrawlerReportManager":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        cleanup_error: Exception | None = None
        try:
            self.cleanup_all()
        except Exception as error:  # cleanup failure must remain observable
            cleanup_error = error
        self.final_metrics = {
            "active": len(self.owned_ids),
            "created_total": self.created_total,
            "cleaned": self.cleaned,
            "peak_active": self.peak_existing,
        }
        if cleanup_error is not None and exc is None:
            raise cleanup_error
        return False

    def _write_marker(self) -> None:
        payload = {
            "schema": "visembler.crawler-ownership.v1",
            "run_id": self.run_id,
            "owned_report_ids": sorted(self.owned_ids),
        }
        self.marker.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _active(self) -> dict[str, Any]:
        return {record.report_id: record for record in self.repository.list()}

    def _trash(self) -> dict[str, Any]:
        return {record.report_id: record for record in self.repository.list_trash()}

    def all_ids(self) -> set[str]:
        return set(self._active()) | set(self._trash())

    def snapshot_ids(self) -> set[str]:
        return self.all_ids()

    def _metadata_owned(self, record: Any) -> bool:
        return str(record.metadata.get("crawler_owner") or "") == self.run_id

    def _is_owned(self, report_id: str, record: Any) -> bool:
        return report_id in self.owned_ids or self._metadata_owned(record)

    def _record_created(self, report_id: str) -> str:
        self.owned_ids.add(report_id)
        self.created_total += 1
        self._write_marker()
        self.assert_bounded()
        return report_id

    def _fixture_title(self, scenario: str) -> str:
        return f"[Crawler {self.run_id}] {scenario}"[:160]

    def _reset_record_shell(self, record: Any, scenario: str) -> Any:
        """Restore report-level fields which editor controls can mutate.

        Model commits do not reset the repository record's title or metadata
        description.  Leaving those fields dirty makes later crawler scenarios
        state-dependent even when the report model itself is canonical.
        """
        expected_title = self._fixture_title(scenario)
        if record.title != expected_title:
            record = self.repository.rename(
                record.report_id,
                expected_title,
                expected_revision=record.revision,
            )
        if str(record.metadata.get("description") or ""):
            record = self.repository.update_description(
                record.report_id,
                "",
                expected_revision=record.revision,
            )
        return record

    def create(self, model: Mapping[str, Any], scenario: str) -> str:
        key = _slug(scenario)
        report_id = f"crawler-{self.run_id}-{key}"
        suffix = 1
        existing = self.all_ids()
        while report_id in existing and report_id not in self.owned_ids:
            suffix += 1
            report_id = f"crawler-{self.run_id}-{key}-{suffix}"
        record = self.repository.create(
            report_id,
            title=self._fixture_title(scenario),
            model=model,
            metadata={"crawler_owner": self.run_id, "crawler_scenario": scenario, "temporary": True},
        )
        # Direct fixture creation must use the same explicit local owner as a
        # native application bootstrap; otherwise the production ACL boundary
        # correctly hides the synthetic report from the browser.
        self.access.migrate([record], owner_subject="local-dev", require_explicit_owner=True)
        self.scenarios[scenario] = record.report_id
        self.scenario_models[scenario] = json.loads(stable_json(model))
        return self._record_created(record.report_id)

    def reset(self, model: Mapping[str, Any], scenario: str) -> str:
        expected_model = json.loads(stable_json(model))
        self.scenario_models[scenario] = expected_model
        report_id = self.scenarios.get(scenario)
        active = self._active()
        trash = self._trash()
        if report_id in trash:
            if not self._is_owned(report_id, trash[report_id]):
                raise RuntimeError(f"refusing to restore unowned report: {report_id}")
            self.repository.restore(report_id)
            active = self._active()
        if report_id not in active:
            return self.create(model, scenario)
        record = active[report_id]
        if not self._is_owned(report_id, record):
            raise RuntimeError(f"refusing to reset unowned report: {report_id}")
        if stable_json(record.model) != stable_json(expected_model):
            self._reset_count += 1
            record = self.repository.commit(
                report_id,
                base_revision=record.revision,
                model=expected_model,
                commit_id=f"crawler-reset-{self.run_id}-{self._reset_count}",
            )
        self._reset_record_shell(record, scenario)
        self.assert_bounded()
        return report_id

    def reset_all(self) -> None:
        for scenario, model in tuple(self.scenario_models.items()):
            self.reset(model, scenario)

    def restore_missing_scenarios(self) -> None:
        active = self._active()
        trash = self._trash()
        for scenario, report_id in tuple(self.scenarios.items()):
            if report_id in trash or report_id not in active:
                self.reset(self.scenario_models[scenario], scenario)

    def adopt_new(self, before: set[str], scenario: str) -> set[str]:
        """Adopt only identities created by one just-completed UI action."""
        created = self.all_ids() - set(before) - self.owned_ids
        for report_id in sorted(created):
            self.owned_ids.add(report_id)
            self.created_total += 1
            active = self._active().get(report_id)
            if active is not None and not self._metadata_owned(active):
                self.access.migrate([active], owner_subject="local-dev", require_explicit_owner=True)
                marker = f"Crawler-owned temporary report · {self.run_id} · {scenario}"
                self.repository.update_description(report_id, marker, expected_revision=active.revision)
        if created:
            self._write_marker()
        self.assert_bounded()
        return created

    def discover_inherited(self) -> set[str]:
        """Track duplicates which inherited this run's ownership metadata."""
        discovered = {
            report_id
            for report_id, record in {**self._active(), **self._trash()}.items()
            if self._metadata_owned(record)
        } - self.owned_ids
        if discovered:
            self.owned_ids.update(discovered)
            self.created_total += len(discovered)
            self._write_marker()
        self.assert_bounded()
        return discovered

    def delete_owned(self, report_id: str) -> bool:
        active = self._active()
        trash = self._trash()
        record = active.get(report_id) or trash.get(report_id)
        if record is None:
            self.owned_ids.discard(report_id)
            self.cleaned += 1
            self._write_marker()
            return False
        if not self._is_owned(report_id, record):
            raise RuntimeError(f"refusing to delete unowned report: {report_id}")
        if report_id in trash:
            self.repository.restore(report_id)
            record = self.repository.get(report_id)
        self.repository.delete(report_id, expected_revision=record.revision)
        self.access.delete(report_id)
        self.owned_ids.discard(report_id)
        for scenario, value in tuple(self.scenarios.items()):
            if value == report_id:
                del self.scenarios[scenario]
                self.scenario_models.pop(scenario, None)
        self.cleaned += 1
        self._write_marker()
        return True

    def cleanup_extras(self, keep: set[str] | None = None) -> None:
        keep = set(keep or ())
        self.discover_inherited()
        for report_id in sorted(self.owned_ids - keep):
            self.delete_owned(report_id)
        self.assert_bounded()

    def cleanup_all(self) -> None:
        self.cleanup_extras(set())
        if self.owned_ids:
            raise RuntimeError(f"crawler cleanup left owned reports: {sorted(self.owned_ids)}")
        self.marker.unlink(missing_ok=True)

    def assert_bounded(self) -> int:
        active = self._active()
        trash = self._trash()
        existing = sum(
            1
            for report_id, record in {**active, **trash}.items()
            if self._is_owned(report_id, record)
        )
        self.peak_existing = max(self.peak_existing, existing)
        if existing > self.max_existing:
            raise RuntimeError(f"crawler report bound exceeded: {existing} > {self.max_existing}")
        return existing

    def metrics(self) -> dict[str, int]:
        return {
            "active": self.assert_bounded(),
            "created_total": self.created_total,
            "cleaned": self.cleaned,
            "peak_active": self.peak_existing,
        }
