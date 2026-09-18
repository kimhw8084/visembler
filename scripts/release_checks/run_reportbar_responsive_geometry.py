"""Verify the editor reportbar's real browser geometry at governed widths."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from editor_host import NativeHost
from native_common import acceptance_model, browser_kwargs, ready

ROOT = Path(__file__).resolve().parents[2]
VIEWPORTS = (
    ("mobile-390", 390, 844),
    ("mobile-430", 430, 932),
    ("tablet-481", 481, 900),
    ("tablet-768", 768, 900),
    ("desktop-1440", 1440, 900),
)
ACTION_NAMES = ("New report", "Duplicate", "Manage")


def _box(page, selector: str) -> dict:
    return page.locator(selector).first.evaluate(
        """
        element => {
            const rect = element.getBoundingClientRect();
            const style = getComputedStyle(element);
            return {
                left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom,
                width: rect.width, height: rect.height,
                visible: !!(rect.width && rect.height && style.display !== 'none' && style.visibility !== 'hidden'),
                enabled: !element.disabled && element.getAttribute('aria-disabled') !== 'true',
                tabIndex: element.tabIndex,
            };
        }
        """
    )


def _overlap(first: dict, second: dict) -> dict:
    width = max(0.0, min(first["right"], second["right"]) - max(first["left"], second["left"]))
    height = max(0.0, min(first["bottom"], second["bottom"]) - max(first["top"], second["top"]))
    area = width * height
    first_area = first["width"] * first["height"]
    second_area = second["width"] * second["height"]
    return {
        "area": area,
        "ratio_to_reports": area / first_area if first_area else 0.0,
        "ratio_to_other": area / second_area if second_area else 0.0,
    }


def _in_viewport(box: dict, width: int, height: int) -> bool:
    return box["left"] >= 0 and box["top"] >= 0 and box["right"] <= width and box["bottom"] <= height


def _control(page, name: str) -> str:
    return f'.cui-visualizer-reportbar button:has-text("{name}")'


def run(output: Path | None = None) -> int:
    report = {
        "status": "PASS",
        "source": "native NiceGUI report editor",
        "viewports": [],
    }
    with tempfile.TemporaryDirectory(prefix="visembler-reportbar-geometry-") as temp_dir, NativeHost(ROOT, Path(temp_dir) / "data") as host, sync_playwright() as playwright:
        report_id = host.create(model=acceptance_model(), name="chg128-reportbar")
        record = host.repository.get(report_id)
        host.repository.rename(report_id, title="Operations Review Report", expected_revision=record.revision)
        record = host.repository.get(report_id)
        host.repository.update_description(
            report_id,
            "Representative responsive reportbar geometry fixture",
            expected_revision=record.revision,
        )
        for index in range(3):
            host.create(model=acceptance_model(), name=f"chg128-related-{index}")

        browser = playwright.chromium.launch(**browser_kwargs())
        try:
            for name, width, height in VIEWPORTS:
                context = browser.new_context(viewport={"width": width, "height": height})
                page = context.new_page()
                page.goto(f"{host.url}/visualizer?report={report_id}", wait_until="domcontentloaded")
                ready(page, require_settled=True)
                page.locator(".cui-visualizer-reportbar").wait_for(state="visible")

                report_box = _box(page, ".cui-visualizer-report-select")
                controls = {action: _box(page, _control(page, action)) for action in ACTION_NAMES}
                title_box = _box(page, '[aria-label="Report title"]')
                description_box = _box(page, '[aria-label="Description"]')
                report_input = _box(page, ".cui-visualizer-report-select input")
                overlap = {action: _overlap(report_box, box) for action, box in controls.items()}
                overflow = page.evaluate(
                    """() => ({
                        scrollWidth: document.documentElement.scrollWidth,
                        clientWidth: document.documentElement.clientWidth,
                        horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
                    })"""
                )
                reachability = {
                    "Reports": report_box["visible"] and report_box["enabled"] and _in_viewport(report_box, width, height) and report_input["visible"] and report_input["enabled"],
                    **{
                        action: box["visible"] and box["enabled"] and _in_viewport(box, width, height)
                        for action, box in controls.items()
                    },
                }
                target_dimensions = {
                    "Reports": {"width": report_box["width"], "height": report_box["height"]},
                    **{
                        action: {"width": box["width"], "height": box["height"]}
                        for action, box in controls.items()
                    },
                }
                case = {
                    "viewport": {"name": name, "width": width, "height": height},
                    "rectangles": {"Reports": report_box, **controls},
                    "pairwise_overlap": overlap,
                    "target_dimensions": target_dimensions,
                    "document": overflow,
                    "reachability": reachability,
                    "title_usable": title_box["visible"] and title_box["enabled"],
                    "description_usable": description_box["visible"] and description_box["enabled"],
                }
                report["viewports"].append(case)

                assert all(item["area"] == 0 for item in overlap.values()), case
                assert not overflow["horizontalOverflow"], case
                assert all(reachability.values()), case
                assert case["title_usable"] and case["description_usable"], case
                if width <= 430:
                    assert report_box["height"] >= 44 and all(box["height"] >= 44 for box in controls.values()), case
                context.close()
        finally:
            browser.close()

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    return run(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
