"""Exercise the finite P1 usability paths against the real isolated native host."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from editor_host import NativeHost, load_editor  # noqa: E402


def state(page):
    return page.evaluate("window.CompanyUIVisualizerBridge.state()")


def model(page):
    return state(page)["model"]


def settled(page):
    page.wait_for_function(
        "()=>{const s=window.CompanyUIVisualizerBridge.state();return s.pending===0&&!s.inflight}",
        timeout=15000,
    )


def ready(page):
    page.locator('.cui-visualizer-root[data-editor-ready="true"]').wait_for(timeout=20000)
    settled(page)


def add_element(page, name):
    page.locator("#componentSearch").fill(name)
    button = page.locator(f'[data-element="{name}"] .library-insert')
    button.wait_for(timeout=8000)
    button.click()
    settled(page)
    return model(page)["items"][-1]["id"]


def record(report, name, detail):
    report["checks"][name] = {"status": "PASS", **detail}


def transform_type(page, value):
    control = page.locator(".data-transform-panel [data-transform-type]")
    control.select_option(value)
    page.wait_for_timeout(50)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "host": "native NiceGUI",
        "status": "FAIL",
        "checks": {},
        "source_sha256": hashlib.sha256(
            (ROOT / "company_ui/products/visualizer/assets/integrated_editor.mjs").read_bytes()
        ).hexdigest(),
        "errors": [],
    }

    with tempfile.TemporaryDirectory(prefix="visembler-p1-native-") as td:
        with NativeHost(ROOT, Path(td) / "data") as host, sync_playwright() as playwright:
            executable = os.environ.get("VISEMBLER_BROWSER") or shutil.which("chromium")
            launch = {"headless": True}
            if executable:
                launch.update(executable_path=executable, args=["--no-sandbox"])
            browser = playwright.chromium.launch(**launch)
            page = browser.new_page(
                viewport={"width": 1440, "height": 1000},
                accept_downloads=True,
                permissions=["clipboard-read", "clipboard-write"],
            )
            page.on("pageerror", lambda error: report["errors"].append(f"pageerror: {error}"))
            page.on(
                "console",
                lambda message: report["errors"].append(f"console: {message.text}")
                if message.type == "error"
                else None,
            )
            load_editor(page, host, "default")
            ready(page)

            # P1-01/P1-08: wide intake, operation-specific ordered recipe, and scroll contract.
            page.locator("#pasteDataBtn").click()
            page.locator("#dataFirstText").fill(
                "Time\tValue\n"
                "2026-01-01\t2\n"
                "2026-02-01\t9\n"
                "2026-03-01\t4\n"
                "2026-04-01\t7"
            )
            page.locator('[data-data-first-view="line"]').wait_for(timeout=15000)
            page.locator('[data-data-first-view="line"]').click()
            page.locator("#dataFirstCreate").click()
            page.wait_for_function("()=>window.CompanyUIVisualizerBridge.state().model.items.length===1")
            settled(page)
            chart_id = model(page)["items"][0]["id"]
            page.locator("#pasteDataBtn").click()
            page.locator("#dataFirstText").fill(
                "Time\tCategory\tValue\tRegion\tOwner\tNotes\n"
                "2026-01-01\tA\t2\tEast\tKim\tfirst\n"
                "2026-02-01\tB\t9\tWest\tLee\tsecond\n"
                "2026-03-01\tC\t4\tEast\tPark\tthird\n"
                "2026-04-01\tD\t7\tNorth\tCho\tfourth"
            )
            page.locator("#dataFirstReplace").wait_for(timeout=15000)
            page.locator("#dataFirstReplace").click()
            settled(page)
            page.locator(f'.component[data-id="{chart_id}"]').click()
            page.locator(".data-transform-panel").wait_for(timeout=10000)
            panel = page.locator(".data-transform-panel")
            panel.locator('[data-transform-type]').select_option("filter")
            panel.locator("[data-transform-field]").select_option(index=2)
            panel.locator("[data-transform-value]").fill("A")
            panel.locator('[data-transform-action="save"]').click()
            settled(page)
            transform_type(page, "sort")
            page.locator(".data-transform-panel [data-transform-field]").select_option(index=3)
            page.locator('[data-transform-action="save"]').click()
            settled(page)
            transform_type(page, "top_n")
            page.locator(".data-transform-panel [data-transform-n]").fill("2")
            page.locator(".data-transform-panel [data-transform-ranking-field]").select_option(index=3)
            page.locator('[data-transform-action="save"]').click()
            settled(page)
            entry = next(item for item in model(page)["items"] if item["id"] == chart_id)
            assert [step["type"] for step in entry["transform_recipe"]["steps"]] == ["filter", "sort", "top_n"]
            page.locator('[data-transform-step-action="down"][data-transform-index="0"]').click()
            settled(page)
            entry = next(item for item in model(page)["items"] if item["id"] == chart_id)
            assert [step["type"] for step in entry["transform_recipe"]["steps"]] == ["sort", "filter", "top_n"]
            page.locator('[data-transform-step-action="edit"][data-transform-index="1"]').click()
            page.locator(".data-transform-panel [data-transform-value]").fill("B")
            page.locator('[data-transform-action="save"]').click()
            settled(page)
            assert next(item for item in model(page)["items"] if item["id"] == chart_id)["transform_recipe"]["steps"][1]["value"] == "B"
            page.locator('[data-transform-step-action="remove"][data-transform-index="0"]').click()
            settled(page)
            assert len(next(item for item in model(page)["items"] if item["id"] == chart_id)["transform_recipe"]["steps"]) == 2
            grid = page.locator("#dataDockGrid")
            assert grid.locator(".data-dock-scroll").evaluate("el=>el.scrollWidth>el.clientWidth")
            assert grid.locator(".data-dock-scroll .data-dock-header").count() == 1
            record(report, "transform_stack_and_wide_data", {"steps": 2, "columns": 6})

            # P1-02: save, rename, duplicate, and explicitly apply a mapping preset.
            page.locator("#pasteDataBtn").click()
            page.locator("#dataFirstText").fill("Time\tValue\n2026-01-01\t1\n2026-02-01\t2")
            page.locator('[data-data-first-view="line"]').wait_for(timeout=15000)
            page.locator("#dataFirstSaveMapping").click()
            page.locator("#mappingPresetName").fill("Pilot mapping")
            page.locator("#mappingSaveConfirm").click()
            page.locator("#dataFirstManageMappings").click()
            page.locator("[data-mapping-name]").first.fill("Renamed mapping")
            page.locator("[data-mapping-name]").first.press("Tab")
            page.locator('[data-mapping-action="duplicate"]').first.click()
            assert page.locator(".mapping-manager-row").count() >= 2
            page.locator('[data-mapping-action="apply"]').first.click()
            assert page.locator("#dataFirstCreate").is_visible()
            page.locator('#genericModal .dialog-head [data-close]').click()
            record(report, "mapping_management", {"presets": page.locator("[data-mapping-name]").count()})

            # P1-07 direct editing: caption commits as one normal editor operation.
            image_id = add_element(page, "Image + Caption")
            page.locator(f'.component[data-id="{image_id}"] figcaption').dblclick()
            direct = page.locator(f'.component[data-id="{image_id}"] .direct-editor-control')
            direct.fill("Inline review caption")
            direct.press("Tab")
            settled(page)
            assert next(item for item in model(page)["items"] if item["id"] == image_id)["caption"] == "Inline review caption"
            record(report, "direct_caption_edit", {"caption": "Inline review caption"})

            # P1-03: report metadata, switching, duplicate, and manager/search/export surface.
            page.get_by_role("button", name="New report").click()
            page.get_by_role("button", name="Blank canvas").click()
            page.wait_for_function("()=>window.CompanyUIVisualizerBridge.state().model.items.length===0")
            report_title = page.get_by_label("Report title")
            report_title.fill("P1 Managed Report")
            report_title.press("Tab")
            description = page.get_by_label("Description")
            description.fill("P1 usability review")
            description.press("Tab")
            settled(page)
            assert "P1 Managed Report" in report_title.input_value()
            page.get_by_role("button", name="Duplicate").click()
            settled(page)
            page.get_by_role("button", name="Manage").click()
            page.get_by_label("Search active reports").fill("P1 Managed")
            assert page.get_by_text("active match(es)").is_visible()
            page.get_by_role("button", name="Export current JSON").click()
            page.get_by_role("button", name="Close").last.click()
            record(report, "report_manager_metadata", {"title": "P1 Managed Report", "duplicated": True})

            # P1-05: mutually exclusive mobile drawer with close affordance and backdrop.
            page.set_viewport_size({"width": 390, "height": 844})
            page.reload(wait_until="domcontentloaded")
            ready(page)
            if page.locator('.cui-visualizer-root[data-library="closed"]').count():
                page.locator("#libraryToggle").click()
            assert page.locator('.cui-visualizer-root[data-library="open"]').count() == 1
            assert page.locator("#panelBackdrop").is_visible()
            page.locator("#libraryClose").click()
            assert page.locator('.cui-visualizer-root[data-library="closed"]').count() == 1
            page.locator("#inspectorToggle").click()
            page.keyboard.press("Escape")
            assert page.locator('.cui-visualizer-root[data-inspector="closed"]').count() == 1
            record(report, "mobile_drawer_controls", {"viewport": "390x844"})

            assert not report["errors"], report["errors"]
            browser.close()

    report["status"] = "PASS"
    (out / "p1-smoke.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "checks": list(report["checks"]), "errors": report["errors"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
