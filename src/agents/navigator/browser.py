"""Strict Chromium lifecycle for the navigator.

One browser at a time (1-2 GB hosts), 30 s navigation/action timeouts, and a
guaranteed teardown so crashes and timeouts never leave zombie Chromium
processes. Uses Playwright's sync API: all callers (CLI, background runner
threads) are synchronous.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager

from playwright.sync_api import Page, sync_playwright

TIMEOUT_MS = 30_000
USER_AGENT = "Mozilla/5.0 (job-butler; +https://github.com/SelfOverflow/job-butler)"
_ONE_BROWSER = threading.Lock()


class BrowserBusyError(RuntimeError):
    """Another navigator session is already running."""


@contextmanager
def browser_page(headless: bool = True, timeout_ms: int = TIMEOUT_MS) -> Iterator[Page]:
    if not _ONE_BROWSER.acquire(blocking=False):
        raise BrowserBusyError("A browser session is already running; try again when it finishes")
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=headless)
            try:
                context = browser.new_context(user_agent=USER_AGENT)
                try:
                    page = context.new_page()
                    page.set_default_timeout(timeout_ms)
                    page.set_default_navigation_timeout(timeout_ms)
                    yield page
                finally:
                    context.close()
            finally:
                browser.close()
    finally:
        _ONE_BROWSER.release()
