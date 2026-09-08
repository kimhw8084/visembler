#!/usr/bin/env python3
"""Native multi-principal browser acceptance for the Visembler ACL boundary."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright

from company_ui.products.visualizer.repository import ReportRepository


def _port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _headers(subject: str, role: str = "visembler.user") -> dict[str, str]:
    return {"x-auth-user": subject, "x-auth-roles": role}


class CompanyHost:
    def __init__(self, data: Path):
        self.data = data
        self.port = _port()
        self.process: subprocess.Popen | None = None
        self.log_path = data / "server.log"

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        self.data.mkdir(parents=True, exist_ok=True)
        env = os.environ | {
            "PYTHONPATH": str(ROOT),
            "COMPANY_UI_ENVIRONMENT": "prod",
            "COMPANY_UI_AUTH_MODE": "header",
            "COMPANY_UI_PROXY_ENABLED": "true",
            "COMPANY_UI_TRUSTED_PROXIES": "127.0.0.1/32",
            "COMPANY_UI_MIGRATION_OWNER_SUBJECT": "alice",
            "COMPANY_UI_STORAGE_SECRET": "company-browser-storage-secret-0123456789",
            "COMPANY_UI_VISUALIZER_DATA_DIR": str(self.data),
            # Bind broadly as a proxy-backed process would; the browser still
            # connects through the loopback test endpoint.
            "COMPANY_UI_HOST": "0.0.0.0",
            "COMPANY_UI_PORT": str(self.port),
            "PYTHONUNBUFFERED": "1",
        }
        self.process = subprocess.Popen(
            [sys.executable, "-m", "company_ui.products.visualizer.cli"],
            cwd=ROOT,
            env=env,
            stdout=self.log_path.open("w", encoding="utf-8"),
            stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(self.log_path.read_text(encoding="utf-8", errors="replace")[-12000:])
            try:
                with urlopen(Request(self.url + "/readyz", headers=_headers("alice")), timeout=1) as response:
                    if response.status in {200, 503}:
                        return
            except Exception:
                time.sleep(0.25)
        raise TimeoutError("company multi-principal server did not start")

    def stop(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.send_signal(signal.SIGTERM)
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.process = None


def _attach(page, errors: list[dict[str, str]], principal: str, viewport: int) -> None:
    page.on("console", lambda message: errors.append({"principal": principal, "viewport": str(viewport), "kind": "console", "detail": message.text}) if message.type == "error" else None)
    page.on("pageerror", lambda error: errors.append({"principal": principal, "viewport": str(viewport), "kind": "pageerror", "detail": str(error)}))
    page.on("requestfailed", lambda request: errors.append({"principal": principal, "viewport": str(viewport), "kind": "requestfailed", "detail": request.url}))


def _wait_hub(page) -> None:
    page.locator('[data-testid="report-hub"]').wait_for(timeout=20000)


def _no_overflow(page) -> None:
    assert page.evaluate("()=>document.documentElement.scrollWidth-window.innerWidth") <= 1


def _share(page, subject: str, role: str) -> None:
    page.get_by_role("button", name="Share", exact=True).click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("User or group subject").fill(subject)
    if role != "Viewer":
        dialog.get_by_label("Access").click()
        # Quasar's option list is a transient portal; keyboard selection is
        # deterministic and exercises the same accessible control path.
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
    dialog.get_by_role("button", name="Grant or update", exact=True).click()
    page.wait_for_timeout(250)


def _bridge_commit(page, *, text: str, base_revision: int) -> None:
    payload = {
        "bridge_version": 1,
        "type": "report.commit",
        "payload": {
            "report_id": "default",
            "base_revision": base_revision,
            "commit_id": f"browser-{text}",
            "model": {
                "schema_version": 1,
                "authoring_schema": "authoring-p0-v1",
                "datasets": [],
                "items": [{"id": "c1", "type": "text", "engine": "TextEngine", "element": "Body Narrative", "order": 0, "text": text, "body": text}],
                "groups": {},
                "mode": "guided",
                "layoutPreset": "editorial",
                "crossFilter": None,
                "canvas": {"width": 1600, "height": 900},
                "nextId": 2,
            },
        },
    }
    page.evaluate("payload=>document.querySelector('.cui-visualizer-host').dispatchEvent(new CustomEvent('visualizer_bridge',{bubbles:true,detail:JSON.stringify(payload)}))", payload)
    page.wait_for_timeout(800)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    receipt: dict[str, object] = {"scope": "native multi-principal company ACL browser acceptance", "checks": [], "browser_errors": []}

    def check(check_id: str, name: str, fn) -> None:
        try:
            fn()
            receipt["checks"].append({"id": check_id, "name": name, "status": "PASS"})
        except Exception as exc:
            receipt["checks"].append({"id": check_id, "name": name, "status": "FAIL", "detail": f"{type(exc).__name__}: {str(exc)[:500]}"})

    with tempfile.TemporaryDirectory(prefix="visembler-company-browser-") as td:
        data = Path(td) / "data"
        host = CompanyHost(data)
        host.start()
        anonymous_route = {"rejected": False, "status": None}
        try:
            with urlopen(Request(host.url + "/visualizer/reports"), timeout=5) as response:
                anonymous_route["status"] = response.status
        except HTTPError as exc:
            anonymous_route["rejected"] = exc.code in {401, 403}
            anonymous_route["status"] = exc.code

        security_headers = {"verified": False}
        with urlopen(Request(host.url + "/readyz", headers=_headers("alice")), timeout=5) as response:
            security_headers["verified"] = (
                response.status in {200, 503}
                and response.headers.get("x-content-type-options") == "nosniff"
                and response.headers.get("x-frame-options") in {"DENY", "SAMEORIGIN"}
                and bool(response.headers.get("referrer-policy"))
            )

        def anonymous_route_check() -> None:
            assert anonymous_route["rejected"], f"anonymous report route returned {anonymous_route['status']}"

        def security_headers_check() -> None:
            assert security_headers["verified"], "required production security headers were not present"

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            alice = browser.new_context(extra_http_headers=_headers("alice"), viewport={"width": 1440, "height": 900})
            bob = browser.new_context(extra_http_headers=_headers("bob"), viewport={"width": 1440, "height": 900})
            carol = browser.new_context(extra_http_headers=_headers("carol"), viewport={"width": 1440, "height": 900})
            alice_page = alice.new_page(); bob_page = bob.new_page(); carol_page = carol.new_page()
            _attach(alice_page, receipt["browser_errors"], "alice", 1440)
            _attach(bob_page, receipt["browser_errors"], "bob", 1440)
            _attach(carol_page, receipt["browser_errors"], "carol", 1440)

            def alice_owner_setup() -> None:
                alice_page.goto(host.url + "/visualizer/reports", wait_until="domcontentloaded")
                _wait_hub(alice_page)
                assert alice_page.locator('[data-report-id="default"][data-report-state="active"]').count() == 1
                assert "owner" in alice_page.locator('[data-report-id="default"]').inner_text()
                _share(alice_page, "bob", "Viewer")

            def bob_receives_and_edits() -> None:
                bob_page.goto(host.url + "/visualizer/reports", wait_until="domcontentloaded")
                _wait_hub(bob_page)
                card = bob_page.locator('[data-report-id="default"][data-report-state="active"]')
                assert card.count() == 1
                bob_page.goto(host.url + "/visualizer?report=default", wait_until="domcontentloaded")
                bob_page.locator('.cui-visualizer-host').wait_for(timeout=20000)
                _bridge_commit(bob_page, text="viewer-write", base_revision=1)
                assert ReportRepository(data / "reports").get("default").revision == 1

            def promote_bob() -> None:
                alice_page.goto(host.url + "/visualizer/reports", wait_until="domcontentloaded")
                _wait_hub(alice_page)
                _share(alice_page, "bob", "Editor")

            def bob_editor_write() -> None:
                bob_page.goto(host.url + "/visualizer?report=default", wait_until="domcontentloaded")
                bob_page.locator('.cui-visualizer-host').wait_for(timeout=20000)
                _bridge_commit(bob_page, text="editor-write", base_revision=1)
                assert ReportRepository(data / "reports").get("default").revision == 2

            def carol_is_denied() -> None:
                carol_page.goto(host.url + "/visualizer/reports", wait_until="domcontentloaded")
                _wait_hub(carol_page)
                assert carol_page.locator('[data-report-id="default"]').count() == 0

            def responsive_scope() -> None:
                for viewport in (768, 390):
                    alice_page.set_viewport_size({"width": viewport, "height": 900 if viewport == 768 else 844})
                    alice_page.goto(host.url + "/visualizer/reports", wait_until="domcontentloaded")
                    _wait_hub(alice_page)
                    _no_overflow(alice_page)

            check("MU000", "anonymous production report route is rejected", anonymous_route_check)
            check("MU007", "production readiness and security headers are present", security_headers_check)
            check("MU001", "owner sees owned report and grants viewer access", alice_owner_setup)
            check("MU002", "shared viewer sees report and server rejects viewer write", bob_receives_and_edits)
            check("MU003", "owner promotes viewer to editor", promote_bob)
            check("MU004", "shared editor write is accepted", bob_editor_write)
            check("MU005", "unauthorized principal does not see report", carol_is_denied)
            check("MU006", "shared report hub responsive at 768 and 390", responsive_scope)

            browser.close()
        host.stop()
        repository = ReportRepository(data / "reports")
        report = repository.get("default")
        receipt["post_run"] = {"revision": report.revision, "audit_events": len((data / "reports" / "_governance" / "audit.jsonl").read_text(encoding="utf-8").splitlines())}

    receipt["browser_error_count"] = len(receipt["browser_errors"])
    receipt["passed"] = sum(item["status"] == "PASS" for item in receipt["checks"])
    receipt["total"] = len(receipt["checks"])
    receipt["status"] = "PASS" if receipt["passed"] == receipt["total"] and not receipt["browser_errors"] else "FAIL"
    (output / "company-user-browser-acceptance.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
