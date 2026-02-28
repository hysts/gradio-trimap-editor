"""Shared test helpers for trimap-editor Playwright tests.

Fixtures live in conftest.py; this module holds reusable helpers, constants,
and the GradioApp context manager that test files import directly.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from playwright.sync_api import Browser, Locator, Page, expect

if TYPE_CHECKING:
    import gradio as gr

# ── Constants ──

EXAMPLES_DIR = Path(__file__).parent.parent / "demo" / "showcase" / "examples"

RE_ACTIVE = re.compile(r"\bactive\b")
RE_VIS_OFF = re.compile(r"\bte-vis-off\b")
RE_MAXIMIZED = re.compile(r"\bte-maximized\b")
RE_VISIBLE = re.compile(r"\bte-visible\b")
RE_DANGER_CONFIRM = re.compile(r"\bte-btn-danger-confirm\b")

# ── Locator helpers ──


def get_editor_block(page: Page) -> Locator:
    """Return the locator scoped to the TrimapEditor Gradio block."""
    return page.locator(".trimap-editor").first


def get_editor_element(page: Page) -> Locator:
    """Return the Gradio wrapper element (parent of .trimap-editor).

    te-maximized is set on this element (outside the morph scope) so
    maximize-related assertions must target this locator, not the block.
    """
    return page.locator(".trimap-editor").first.locator("xpath=..")


def upload_image(block: Locator, image_path: Path) -> None:
    """Upload an image via the file input and wait for the canvas to appear."""
    block.locator("#te-file-input").set_input_files(str(image_path))
    expect(block.locator(".te-canvas-wrapper.te-has-image")).to_be_visible(timeout=8000)


def wait_for_server_upload(page: Page) -> None:
    """Wait for the background server upload to complete (filePath is set)."""
    page.wait_for_function(
        """() => {
            var el = document.querySelector('.trimap-editor');
            return el && el._teState && el._teState.filePath !== null;
        }""",
        timeout=8000,
    )


def upload_and_draw(page: Page, block: Locator) -> None:
    """Upload an image, wait for server upload, then draw a stroke that commits."""
    example_img = next(EXAMPLES_DIR.glob("*.jpg"))
    upload_image(block, example_img)
    wait_for_server_upload(page)
    canvas = block.locator(".te-canvas")
    box = canvas.bounding_box()
    page.mouse.move(box["x"] + 60, box["y"] + 80)
    page.mouse.down()
    page.mouse.move(box["x"] + 120, box["y"] + 80, steps=6)
    page.mouse.up()
    page.wait_for_timeout(600)


# ── GradioApp context manager ──


class GradioApp:
    """Context manager that launches a Gradio demo and opens a Playwright page."""

    def __init__(self, demo: gr.Blocks, browser: Browser) -> None:
        self._demo = demo
        self._browser = browser
        self.page: Page | None = None

    def __enter__(self) -> Page:
        _, url, _ = self._demo.launch(prevent_thread_lock=True)
        self.page = self._browser.new_page(viewport={"width": 1280, "height": 900})
        self.page.set_default_timeout(10_000)
        self.page.goto(url)
        self.page.wait_for_timeout(500)
        return self.page

    def __exit__(self, *_: object) -> None:
        if self.page:
            self.page.close()
        self._demo.close()
