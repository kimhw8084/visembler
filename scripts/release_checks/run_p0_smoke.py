"""Exercise the P0 authoring paths against the real isolated native host."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from PIL import Image
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


def select(page, item_id):
    page.locator(f'.component[data-id="{item_id}"]').evaluate("el=>el.click()")
    page.wait_for_function(
        "id=>document.querySelector(`.component[data-id=\"${id}\"]`)?.getAttribute('aria-selected')==='true'",
        arg=item_id,
    )


def edit(page, selector, value):
    control = page.locator(selector)
    control.scroll_into_view_if_needed()
    if control.evaluate("el=>el.tagName.toLowerCase()") == "select":
        control.select_option(str(value))
    else:
        control.fill(str(value))
        control.press("Tab")
    settled(page)


def add_element(page, name):
    search = page.locator("#componentSearch")
    search.fill(name)
    button = page.locator(f'[data-element="{name}"] .library-insert')
    button.wait_for(timeout=8000)
    button.click()
    settled(page)
    return model(page)["items"][-1]["id"]


def record(report, name, check):
    report["checks"][name] = {"status": "PASS", **check}


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

    with tempfile.TemporaryDirectory(prefix="visembler-p0-native-") as td:
        data_dir = Path(td) / "data"
        image_path = Path(td) / "smoke.png"
        Image.new("RGB", (80, 50), "#146090").save(image_path)
        with NativeHost(ROOT, data_dir) as host, sync_playwright() as playwright:
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

            # P0-09 + P0-08: blank intake, compatible switch, history, reopen.
            assert page.locator("#blankStartSurface").is_visible()
            page.locator('[data-blank-action="paste"]').click()
            page.locator("#dataFirstText").fill(
                "Time\tValue\n2026-01-01\t10\n2026-02-01\t12\n2026-03-01\t11"
            )
            page.locator('[data-data-first-view="line"]').wait_for(timeout=15000)
            page.locator('[data-data-first-view="line"]').click()
            page.locator("#dataFirstCreate").click()
            page.wait_for_function("()=>window.CompanyUIVisualizerBridge.state().model.items.length===1")
            settled(page)
            first = model(page)["items"][0]
            assert first["element"] == "Line Chart"
            assert page.locator("#blankStartSurface").is_hidden()
            dataset_id = first["dataset_id"]
            mapping = dict(first["mapping"])
            page.locator("#iVisualType").select_option("CoreChartEngine::Area Chart")
            page.wait_for_function(
                "()=>window.CompanyUIVisualizerBridge.state().model.items[0].element==='Area Chart'"
            )
            page.locator("#undo").click()
            page.wait_for_function(
                "()=>window.CompanyUIVisualizerBridge.state().model.items[0].element==='Line Chart'"
            )
            page.locator("#redo").click()
            page.wait_for_function(
                "()=>window.CompanyUIVisualizerBridge.state().model.items[0].element==='Area Chart'"
            )
            assert page.locator("#saveBtn").is_disabled()
            page.reload(wait_until="domcontentloaded")
            ready(page)
            assert model(page)["items"][0]["element"] == "Area Chart"
            assert model(page)["items"][0]["dataset_id"] == dataset_id
            assert model(page)["items"][0]["mapping"] == mapping
            record(report, "blank_intake_switch_history_reopen", {"element": "Area Chart"})

            # P0-10: Clean Table selected row and column operations.
            table_id = add_element(page, "Clean Table")
            page.locator("#tableEditorGrid").wait_for(timeout=8000)
            page.locator('[data-table-cell="1:0"]').focus()
            page.locator('[data-table-action="delete-rows"]').click()
            settled(page)
            table = next(item for item in model(page)["items"] if item["id"] == table_id)
            assert [row[0] for row in table["customTable"]["rows"]] == ["Yield", "Risk"]
            page.locator('[data-table-cell="0:1"]').focus()
            page.locator('[data-table-action="delete-columns"]').click()
            settled(page)
            table = next(item for item in model(page)["items"] if item["id"] == table_id)
            assert table["customTable"]["headers"] == ["Measure", "Status"]
            assert table["customTable"]["rows"][0] == ["Yield", "On track"]
            record(report, "clean_table_selection_ops", {"headers": table["customTable"]["headers"]})

            # P0-10: Data Dock selected row and column operations on the bound visual.
            select(page, "c1")
            page.locator("#dataDockGrid").wait_for(timeout=8000)
            page.locator('[data-dataset-cell="1:0"]').focus()
            page.locator('[data-dataset-action="delete-rows"]').click()
            settled(page)
            dataset = next(item for item in model(page)["datasets"] if item["id"] == dataset_id)
            assert len(dataset["rows"]) == 2
            assert dataset["rows"][0][0] == "2026-01-01"
            assert dataset["rows"][1][0] == "2026-03-01"
            page.locator('[data-dataset-cell="0:0"]').focus()
            page.locator('[data-dataset-action="delete-columns"]').click()
            settled(page)
            dataset = next(item for item in model(page)["datasets"] if item["id"] == dataset_id)
            assert len(dataset["fields"]) == 1
            assert dataset["rows"] == [[10], [11]]
            record(report, "data_dock_selection_ops", {"field_count": len(dataset["fields"])})

            # P0-04: diagram direction and default edge label.
            diagram_id = add_element(page, "Process Flow")
            edit(page, "#iNodes", "Start\nFinish")
            edit(page, "#iEdges", "Start -> Finish")
            edit(page, "#iDirection", "right")
            edit(page, "#iEdgeLabel", "Approved")
            right_svg = page.locator(f'.component[data-id="{diagram_id}"] svg')
            assert right_svg.get_attribute("data-direction") == "right"
            assert page.locator(f'.component[data-id="{diagram_id}"] .diagram-edge-label').text_content() == "Approved"
            right_path = right_svg.evaluate(
                "svg=>[...svg.children].find(node=>node.tagName.toLowerCase()==='path')?.getAttribute('d')"
            )
            edit(page, "#iDirection", "down")
            down_svg = page.locator(f'.component[data-id="{diagram_id}"] svg')
            assert down_svg.get_attribute("data-direction") == "down"
            down_path = down_svg.evaluate(
                "svg=>[...svg.children].find(node=>node.tagName.toLowerCase()==='path')?.getAttribute('d')"
            )
            assert down_path != right_path
            record(report, "diagram_direction_edge_label", {"direction": "down", "edge_label": "Approved"})

            # P0-05: image + caption uses author alt text as rendered semantics.
            image_id = add_element(page, "Image + Caption")
            page.locator("#iImageFile").set_input_files(str(image_path))
            settled(page)
            edit(page, "#iAlt", "Microscope image of wafer edge defects")
            edit(page, "#iCaption", "Edge defect review")
            accessible = page.locator(f'.component[data-id="{image_id}"] [role="img"]')
            assert accessible.get_attribute("aria-label") == "Microscope image of wafer edge defects"
            assert page.locator(f'.component[data-id="{image_id}"] figcaption').inner_text() == "Edge defect review"
            assert "Ready" in page.locator("#inspector").inner_text()
            record(report, "image_caption_alt_semantics", {"alt": accessible.get_attribute("aria-label")})

            # P0-06: Project Card reflects modeled statement/detail/status.
            project_id = add_element(page, "Project Card")
            edit(page, "#iStatement", "Recover chamber stability")
            edit(page, "#iDetail", "Verify with a matched control lot")
            edit(page, "#iStatus", "Blocked")
            project_content = page.locator(f'.component[data-id="{project_id}"] .card-body').inner_text()
            assert all(value in project_content for value in ["Recover chamber stability", "Verify with a matched control lot", "Blocked"])
            assert "68%" not in project_content and "Owner" not in project_content
            record(report, "project_card_semantic_truth", {"status": "Blocked"})

            # P0-07: variant-specific engineering controls and real analysis output.
            spc_id = add_element(page, "SPC Control Chart")
            assert page.locator("#iLcl").count() == 0 and page.locator("#iUcl").count() == 0
            assert page.locator("#iLsl").count() == 1 and page.locator("#iUsl").count() == 1
            cusum_id = add_element(page, "CUSUM Chart")
            before_cusum = page.locator(f'.component[data-id="{cusum_id}"] .card-body').inner_html()
            for selector, value in [("#iTarget", "99"), ("#iSigma", "0.4"), ("#iK", "0.25"), ("#iDecisionH", "4")]:
                edit(page, selector, value)
            cusum = next(item for item in model(page)["items"] if item["id"] == cusum_id)
            assert [cusum[key] for key in ["target", "sigma", "k", "decision_h"]] == [99, 0.4, 0.25, 4], cusum
            assert page.locator(f'.component[data-id="{cusum_id}"] .card-body').inner_html() != before_cusum
            ewma_id = add_element(page, "EWMA Chart")
            before_ewma = page.locator(f'.component[data-id="{ewma_id}"] .card-body').inner_html()
            for selector, value in [("#iTarget", "99"), ("#iSigma", "0.4"), ("#iLambda", "0.15"), ("#iControlL", "2.5")]:
                edit(page, selector, value)
            ewma = next(item for item in model(page)["items"] if item["id"] == ewma_id)
            assert [ewma[key] for key in ["target", "sigma", "lambda", "L"]] == [99, 0.4, 0.15, 2.5]
            assert page.locator(f'.component[data-id="{ewma_id}"] .card-body').inner_html() != before_ewma
            record(report, "engineering_variant_controls", {"spc": spc_id, "cusum": cusum_id, "ewma": ewma_id})

            assert not report["errors"], report["errors"]
            browser.close()

    report["status"] = "PASS"
    (out / "p0-smoke.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "checks": list(report["checks"]), "errors": report["errors"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
