"""Shared fixtures for trimap-editor tests."""

from __future__ import annotations

import pytest
from _helpers import GradioApp
from playwright.sync_api import Browser, sync_playwright


@pytest.fixture(scope="session")
def browser():
    """Launch a single Chromium browser for the entire test session."""
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def demo_app(browser: Browser):
    """Launch the test-only Gradio demo and yield a Playwright Page."""
    import _demo as app_module  # noqa: PLC0415

    with GradioApp(app_module.demo, browser) as page:
        yield page
