#!/usr/bin/env python3
"""Native browser acceptance for CHG-208 reusable remap diagnostics."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata
import json
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from editor_host import NativeHost
from native_common import BrowserEvents, browser_kwargs, ready, text_model, write_json


FIXTURE = ROOT / "tests/fixtures/chg208/chg173-remap-scenes.json"


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _open_editor(page, host: NativeHost, report_id: str) -> None:
    response = page.goto(f"{host.url}/visualizer?report={quote(report_id)}", wait_until="domcontentloaded")
    assert response and response.status == 200, response.status if response else None
    ready(page, require_settled=True)


def _open_presets(page) -> None:
    if page.locator("#libraryToggle").get_attribute("aria-pressed") != "true":
        page.locator("#libraryToggle").click()
    page.locator("#presetsTab").click()


def _preset_action(page, name: str, attribute: str):
    cards = page.locator("#presetList .preset")
    for index in range(cards.count()):
        card = cards.nth(index)
        if card.locator(".preset-name-edit").input_value() == name:
            return card.locator(f"[{attribute}]")
    raise AssertionError(f"Reusable preset {name!r} was not found.")


def _save_report_preset(page, name: str) -> None:
    _open_presets(page)
    page.locator("#presetSave").click()
    form = page.locator("#presetSaveForm")
    form.wait_for(timeout=5_000)
    page.locator("#presetSaveName").fill(name)
    page.locator('input[name="presetDataMode"][value="structure"]').check()
    form.locator('button[type="submit"]').click()
    page.locator("#genericModal.show").wait_for(state="hidden", timeout=8_000)


def _create_from_exact_paste(page, text: str) -> dict:
    if page.locator("#libraryToggle").get_attribute("aria-pressed") != "true":
        page.locator("#libraryToggle").click()
    page.locator("#elementsTab").click()
    page.locator("#pasteDataBtn").click()
    page.locator("#genericModal.show #dataFirstText").fill(text)
    page.locator("#genericModal.show .data-first-summary").wait_for(timeout=10_000)
    page.wait_for_function(
        "()=>document.querySelector('#genericModal.show .data-first-summary')?.innerText.includes('Header detected')",
        timeout=10_000,
    )
    page.locator('[data-data-first-stage="choose"]').last.click()
    table_choice = page.locator('[data-data-first-view="table"]')
    table_choice.wait_for(state="visible", timeout=5_000)
    table_choice.click()
    create = page.locator("#genericModal.show #dataFirstCreate")
    create.wait_for(state="visible", timeout=5_000)
    assert create.is_enabled(), page.locator("#genericModal.show #modalBody").inner_text()
    create.click()
    page.locator("#genericModal.show").wait_for(state="hidden", timeout=8_000)
    page.wait_for_function(
        "()=>{const s=window.CompanyUIVisualizerBridge?.state?.();return s&&s.pending===0&&!s.inflight}",
        timeout=15_000,
    )
    return page.evaluate("()=>CompanyUIVisualizerBridge.state().model")


def _source_model(scene: dict) -> dict:
    return copy.deepcopy(scene["source"]["model"])


def _ambiguous_target_model(scene: dict) -> dict:
    observed = scene["destination"]["observed_dataset"]
    dataset = {
        "id": "chg208-ambiguous-data",
        "name": "Pasted data",
        "revision": 1,
        "fields": copy.deepcopy(observed["fields"]),
        "rows": copy.deepcopy(observed["rows"]),
        "metadata": {"header": copy.deepcopy(observed["header"])},
        "source": {"kind": "clipboard", "label": "TSV", "imported_at": "2026-09-24T18:35:00.000Z"},
        "warnings": [],
    }
    return {
        "schema_version": 1,
        "canvas": {"width": 1600, "height": 900},
        "mode": "smart",
        "layoutPreset": "editorial",
        "items": [],
        "groups": {},
        "datasets": [dataset],
        "nextId": 1,
    }


def _save_screenshot(page, output: Path, name: str) -> dict:
    path = output / "screenshots" / Path(name).name
    path.parent.mkdir(parents=True, exist_ok=True)
    page.locator("#genericModal.show").screenshot(path=str(path))
    from PIL import Image

    with Image.open(path) as image:
        size = {"width": image.width, "height": image.height}
    return {"path": path.relative_to(output).as_posix(), "sha256": _digest(path), **size}


def _remap_focus_state(page) -> dict:
    return page.evaluate(
        """()=>{
          const form=document.querySelector('#reuseRemapForm'),active=document.activeElement;
          if(!form||!active)return {contained:false,visible:false};
          const rect=active.getBoundingClientRect(),clip=form.getBoundingClientRect();
          const left=clip.left+form.clientLeft,top=clip.top+form.clientTop;
          const right=left+form.clientWidth,bottom=top+form.clientHeight;
          return {contained:form.contains(active),visible:active.checkVisibility()&&rect.width>0&&rect.height>0&&rect.left>=left&&rect.right<=right&&rect.top>=top&&rect.bottom<=bottom&&rect.top>=0&&rect.bottom<=innerHeight,tag:active.tagName,role:active.dataset?.role||'',item:active.dataset?.remapItem||'',label:active.getAttribute('aria-label')||''};
        }"""
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "screenshots").mkdir(exist_ok=True)
    scenes = json.loads(FIXTURE.read_text(encoding="utf-8"))
    receipt = {
        "schema": "visembler-chg208-remap-diagnostics.v1",
        "candidate_sha": _git("rev-parse", "HEAD"),
        "candidate_tree": _git("rev-parse", "HEAD^{tree}"),
        "fixture": {
            "path": FIXTURE.relative_to(ROOT).as_posix(),
            "sha256": _digest(FIXTURE),
            "evidence_commit": scenes["evidence"]["commit"],
            "authoring_receipt": scenes["evidence"]["authoring_receipt"],
            "authoring_receipt_blob_sha": scenes["evidence"]["authoring_receipt_blob_sha"],
            "source_report": {key: scenes["incompatible"]["source"][key] for key in ("report_id", "path", "blob_sha")},
            "incompatible_report": {key: scenes["incompatible"]["destination"][key] for key in ("report_id", "path", "blob_sha")},
            "ambiguous_source_report": {key: scenes["ambiguous"]["source"][key] for key in ("report_id", "path", "blob_sha")},
            "ambiguous_report": {key: scenes["ambiguous"]["destination"][key] for key in ("report_id", "path", "blob_sha")},
        },
        "runtime": {},
        "cases": {},
        "browser_errors": [],
        "status": "RUNNING",
    }
    try:
        with tempfile.TemporaryDirectory(prefix="visembler-chg208-native-") as temporary:
            with NativeHost(ROOT, Path(temporary) / "data") as host:
                incompatible_source = host.create(model=_source_model(scenes["incompatible"]), name="chg208-pareto-source")
                incompatible_target = host.create(model=text_model("CHG-208 remap target remains unchanged until Apply."), name="chg208-incompatible-target")
                ambiguous_source = host.create(model=_source_model(scenes["ambiguous"]), name="chg208-ambiguity-source")
                ambiguous_target = host.create(model=_ambiguous_target_model(scenes["ambiguous"]), name="chg208-ambiguous-target")
                events = BrowserEvents()
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(**browser_kwargs())
                    context = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
                    page = context.new_page()
                    page.set_default_timeout(10_000)
                    events.attach(page)

                    _open_editor(page, host, incompatible_source)
                    _save_report_preset(page, "CHG-208 Pareto source")
                    source_before = copy.deepcopy(host.repository.get(incompatible_source).model)
                    source_preset_model = page.evaluate("()=>localStorage.getItem('viz-prod-presets-cache')")
                    assert source_preset_model and "CHG-208 Pareto source" in source_preset_model

                    _open_editor(page, host, incompatible_target)
                    pasted_target_model = _create_from_exact_paste(page, scenes["incompatible"]["destination_paste_tsv"])
                    destination = pasted_target_model["datasets"][-1]
                    destination_before = copy.deepcopy(pasted_target_model)
                    assert [field["name"] for field in destination["fields"]] == ["Cycle", "Failure count"]
                    assert [field["type"] for field in destination["fields"]] == ["categorical", "categorical"]

                    _open_presets(page)
                    incompatible_trigger = _preset_action(page, "CHG-208 Pareto source", "data-reusepreset")
                    incompatible_trigger.click()
                    dialog = page.locator("#reuseRemapForm")
                    dialog.wait_for(timeout=5_000)
                    focus_after_open = _remap_focus_state(page)
                    assert focus_after_open["contained"] and focus_after_open["visible"], focus_after_open
                    dataset_select = dialog.locator("[data-remap-dataset]")
                    dataset_select.select_option(str(destination["id"]))
                    page.wait_for_function("()=>document.activeElement?.matches('[data-remap-dataset]')")
                    focus_after_dataset_change = _remap_focus_state(page)
                    assert focus_after_dataset_change["contained"] and focus_after_dataset_change["visible"], focus_after_dataset_change
                    dialog = page.locator("#reuseRemapForm")
                    apply = dialog.locator('button[type="submit"]')
                    assert apply.count() == 1, page.locator("#genericModal").inner_text()
                    assert apply.is_disabled(), "Same-name category data must not satisfy the Pareto measurement."
                    visible_text = dialog.inner_text()
                    field_options = {
                        selector.get_attribute("aria-label"): [value.strip() for value in selector.locator("option").all_text_contents() if value.strip()]
                        for selector in dialog.locator("[data-remap-role]").all()
                    }
                    assert "Source fields: Cycle, Failure count" in visible_text
                    assert "Failure count is Category in Pasted data; Measurement requires a numeric field." in visible_text, visible_text
                    assert "Required source field Failure count is missing" not in visible_text
                    assert any("Failure count · Category" in option for options in field_options.values() for option in options)
                    incompatible_screenshot = _save_screenshot(page, output, "chg173-pareto-wrong-type-dialog.png")
                    measurement = next(
                        selector for selector in dialog.locator("[data-remap-role]").all()
                        if "Measurement" in (selector.get_attribute("aria-label") or "")
                    )
                    measurement.select_option("cycle_1")
                    page.wait_for_function("()=>document.activeElement?.matches('[data-remap-role]')")
                    wrong_field_focus = _remap_focus_state(page)
                    assert wrong_field_focus["contained"] and wrong_field_focus["visible"], wrong_field_focus
                    assert apply.is_disabled()
                    measurement = next(
                        selector for selector in page.locator("#reuseRemapForm [data-remap-role]").all()
                        if "Measurement" in (selector.get_attribute("aria-label") or "")
                    )
                    measurement.select_option("")
                    page.wait_for_function("()=>document.activeElement?.matches('[data-remap-role]')")
                    assert apply.is_disabled()
                    page.keyboard.press("Escape")
                    dialog.wait_for(state="hidden", timeout=5_000)
                    focus_returned = page.evaluate("()=>document.activeElement?.matches('[data-reusepreset]')")
                    assert focus_returned, "Cancel via Escape must return focus to the reusable preset action."
                    assert page.evaluate("()=>CompanyUIVisualizerBridge.state().model") == destination_before
                    assert host.repository.get(incompatible_target).model == destination_before
                    assert host.repository.get(incompatible_source).model == source_before
                    assert page.evaluate("()=>localStorage.getItem('viz-prod-presets-cache')") == source_preset_model
                    receipt["cases"]["incompatible_pareto"] = {
                        "source_fields": [field["name"] for field in destination["fields"]],
                        "destination_fields": [{"name": field["name"], "type": field["type"]} for field in destination["fields"]],
                        "apply_disabled": apply.is_disabled(),
                        "visible_text": visible_text,
                        "field_options": field_options,
                        "focus_after_open": focus_after_open,
                        "focus_after_dataset_change": focus_after_dataset_change,
                        "focus_after_field_change": wrong_field_focus,
                        "focus_restored_after_escape": focus_returned,
                        "report_unchanged": page.evaluate("()=>CompanyUIVisualizerBridge.state().model") == destination_before,
                        "source_report_unchanged": host.repository.get(incompatible_source).model == source_before,
                        "preset_cache_unchanged": page.evaluate("()=>localStorage.getItem('viz-prod-presets-cache')") == source_preset_model,
                        "screenshot": incompatible_screenshot,
                    }

                    _open_editor(page, host, ambiguous_source)
                    _save_report_preset(page, "CHG-208 ambiguity source")
                    ambiguous_source_before = copy.deepcopy(host.repository.get(ambiguous_source).model)
                    ambiguous_preset_model = page.evaluate("()=>localStorage.getItem('viz-prod-presets-cache')")
                    _open_editor(page, host, ambiguous_target)
                    ambiguous_before = copy.deepcopy(page.evaluate("()=>CompanyUIVisualizerBridge.state().model"))
                    _open_presets(page)
                    ambiguous_trigger = _preset_action(page, "CHG-208 ambiguity source", "data-reusepreset")
                    ambiguous_trigger.click()
                    dialog = page.locator("#reuseRemapForm")
                    dialog.wait_for(timeout=5_000)
                    apply = dialog.locator('button[type="submit"]')
                    assert apply.count() == 1, page.locator("#genericModal").inner_text()
                    assert apply.is_disabled(), "Duplicate compatible header names require an explicit field choice."
                    ambiguous_text = dialog.inner_text()
                    category = next(
                        selector for selector in dialog.locator("[data-remap-role]").all()
                        if any("Service week · Category" in value for value in selector.locator("option").all_text_contents())
                    )
                    candidate_options = [value.strip() for value in category.locator("option").all_text_contents() if value.strip()]
                    assert any("Service week · Category" in value for value in candidate_options)
                    assert any("SERVICE WEEK · Category" in value for value in candidate_options)
                    assert "Compatible fields: Service week · Category, SERVICE WEEK · Category." in ambiguous_text
                    ambiguous_screenshot = _save_screenshot(page, output, "chg173-ambiguous-remap-dialog.png")
                    category.select_option("service_week_1")
                    page.wait_for_function("()=>document.activeElement?.matches('[data-remap-role]')")
                    focus_after_choice = _remap_focus_state(page)
                    assert focus_after_choice["contained"] and focus_after_choice["visible"], focus_after_choice
                    assert not apply.is_disabled(), "The explicit compatible source choice should resolve the ambiguity."
                    assert page.evaluate("()=>CompanyUIVisualizerBridge.state().model") == ambiguous_before
                    apply.click()
                    page.locator("#genericModal.show").wait_for(state="hidden", timeout=8_000)
                    page.wait_for_function(
                        "()=>{const s=window.CompanyUIVisualizerBridge?.state?.();return s&&s.pending===0&&!s.inflight}",
                        timeout=15_000,
                    )
                    applied_model = page.evaluate("()=>CompanyUIVisualizerBridge.state().model")
                    selected_ids = {str(item.get("dataset_id")) for item in applied_model["items"] if item.get("dataset_id")}
                    assert selected_ids == {"chg208-ambiguous-data"}, (selected_ids, applied_model)
                    assert host.repository.get(ambiguous_source).model == ambiguous_source_before
                    assert page.evaluate("()=>localStorage.getItem('viz-prod-presets-cache')") == ambiguous_preset_model
                    receipt["cases"]["ambiguous_compatible"] = {
                        "options": candidate_options,
                        "visible_text": ambiguous_text,
                        "apply_disabled_before_choice": True,
                        "focus_after_choice": focus_after_choice,
                        "apply_enabled_after_choice": True,
                        "selected_destination_ids": sorted(selected_ids),
                        "destination_fields_preserved": next(dataset for dataset in applied_model["datasets"] if dataset["id"] == "chg208-ambiguous-data")["fields"] == ambiguous_before["datasets"][0]["fields"],
                        "source_report_unchanged": host.repository.get(ambiguous_source).model == ambiguous_source_before,
                        "preset_cache_unchanged": page.evaluate("()=>localStorage.getItem('viz-prod-presets-cache')") == ambiguous_preset_model,
                        "screenshot": ambiguous_screenshot,
                    }
                    receipt["browser_errors"] = events.unexpected
                    assert not receipt["browser_errors"], receipt["browser_errors"]
                    browser.close()
        receipt["runtime"] = {
            "python": sys.version.split()[0],
            "nicegui": importlib.metadata.version("nicegui"),
            "playwright": importlib.metadata.version("playwright"),
            "browser": "Chromium",
            "browser_version": browser.version,
            "native_host": True,
            "evidence_only_test_data": True,
        }
        receipt["status"] = "PASS"
    except Exception as error:
        receipt["status"] = "FAIL"
        receipt["error"] = f"{type(error).__name__}: {error}"
        receipt["traceback"] = traceback.format_exc(limit=20)
        write_json(output / "acceptance.json", receipt)
        raise
    write_json(output / "acceptance.json", receipt)
    print(json.dumps({"status": receipt["status"], "output": str(output / "acceptance.json")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
