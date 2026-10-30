from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from playwright.sync_api import Page, sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_until_healthy(url: str, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 40
    health_url = f"{url}/_stcore/health"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Streamlit exited before its health endpoint became ready.")
        try:
            with urlopen(health_url, timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, URLError):
            time.sleep(0.25)
    raise TimeoutError("Timed out waiting for the local Streamlit app to start.")


def _app_frame(page: Page):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        for frame in page.frames:
            if "/~/+/" in frame.url:
                return frame
        time.sleep(0.2)
    return page.main_frame


@pytest.mark.mobile
def test_mobile_discover_renders_without_legacy_tosorted_support(tmp_path):
    port = _free_port()
    app_url = f"http://127.0.0.1:{port}"
    environment = os.environ.copy()
    environment["OTAKU_ORBIT_OFFLINE_MODE"] = "1"
    environment["OTAKU_ORBIT_DB_PATH"] = str(tmp_path / "mobile-smoke.db")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "app.py",
            "--server.headless=true",
            "--server.address=127.0.0.1",
            f"--server.port={port}",
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_until_healthy(app_url, process)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
            page.add_init_script(
                "Object.defineProperty(Array.prototype, 'toSorted', "
                "{configurable: true, writable: true, value: undefined});"
            )
            page_errors: list[str] = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(app_url, wait_until="domcontentloaded", timeout=30000)
            frame = _app_frame(page)
            frame.get_by_role("heading", name="Otaku Orbit").wait_for(timeout=30000)
            frame.get_by_role("heading", name="Find your next obsession").wait_for(timeout=15000)
            project_link = frame.get_by_role("link", name="Open live app")
            assert project_link.get_attribute("href") == "https://otaku-orbit.streamlit.app/"
            hero = frame.locator(".orbit-hero")
            assert hero.is_visible()
            assert hero.evaluate("element => getComputedStyle(element).padding") == "16px"
            assert not any("toSorted is not a function" in error for error in page_errors)
            browser.close()
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
