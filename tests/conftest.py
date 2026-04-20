import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class MockPage:
    def __init__(self, html: str = ""):
        self._html = html
        self._locator_results: Dict[str, Any] = {}
        self._last_goto_url = ""
        self._default_timeout = 30000

    def goto(self, url: str, timeout: int = 30000, wait_until: str = "domcontentloaded"):
        self._last_goto_url = url
        return self

    def wait_for_load_state(self, state: str = "domcontentloaded"):
        return self

    def wait_for_timeout(self, ms: int):
        return self

    def locator(self, selector: str):
        return MockLocator(selector, self)

    def evaluate(self, expr: str):
        return None

    def set_default_timeout(self, timeout: int):
        self._default_timeout = timeout
        return self

    def inner_text(self) -> str:
        return self._html

    def content(self) -> str:
        return f"<html><body>{self._html}</body></html>"

    def screenshot(self, path: str) -> bytes:
        return b""


class MockLocator:
    def __init__(self, selector: str, page: MockPage):
        self._selector = selector
        self._page = page
        self._results: List[MockElement] = []

    def all(self) -> List["MockLocator"]:
        results = []
        html = self._page.inner_text()

        if "body" in self._selector:
            results.append(MockElement(html, self._selector))
        elif "card" in self._selector or "promo" in self._selector or "beneficio" in self._selector:
            blocks = self._extract_blocks(html)
            for block in blocks:
                results.append(MockLocator(block, self._page))
        elif "h2" in self._selector or "h3" in self._selector or "h4" in self._selector or "title" in self._selector:
            lines = html.split("\n")
            for line in lines[:5]:
                if line.strip():
                    results.append(MockLocator(line.strip(), self._page))
        elif "a[href" in self._selector:
            links = self._extract_links(html)
            for link in links:
                el = MagicMock()
                el.get_attribute = lambda att, lnk=link: lnk if att == "href" else None
                results.append(el)
        elif "[" in self._selector:
            results.append(MockLocator(html.split("\n")[0] if html else "", self._page))

        return results

    def first(self) -> "MockLocator":
        all_results = self.all()
        if all_results:
            if isinstance(all_results[0], MockLocator):
                return all_results[0]
            el = all_results[0]
            ml = MockLocator(self._selector, self._page)
            ml._results = [el]
            return ml
        return MockLocator("", self._page)

    def inner_text(self) -> str:
        if self._selector in self._page._locator_results:
            return self._page._locator_results[self._selector]
        return self._selector

    def _extract_blocks(self, html: str) -> List[str]:
        blocks = []
        lines = html.split("\n")
        current = []

        for line in lines:
            line = line.strip()
            if not line:
                if current:
                    blocks.append("\n".join(current))
                    current = []
            elif len(line) < 50 and len(line) > 3:
                if current:
                    blocks.append("\n".join(current))
                current = [line]
            else:
                current.append(line)

        if current:
            blocks.append("\n".join(current))

        return blocks[:10]

    def _extract_links(self, html: str) -> List[str]:
        links = []
        for line in html.split("\n"):
            if ".pdf" in line.lower():
                parts = line.split('href="')
                if len(parts) > 1:
                    url = parts[1].split('"')[0]
                    links.append(url)
        return links


class MockElement:
    def __init__(self, text: str, selector: str):
        self.text = text
        self.selector = selector

    def inner_text(self) -> str:
        return self.text

    def get_attribute(self, attr: str) -> Optional[str]:
        return None


class MockBrowser:
    def __init__(self, html: str = ""):
        self._page = MockPage(html)

    def new_context(self, **kwargs):
        return self

    def launch(self, headless: bool = True, channel: str = None):
        return self


class MockPlaywright:
    def __init__(self, html: str = ""):
        self._html = html
        self._browser = MockBrowser(html)

    def chromium(self):
        return self._browser

    def start(self):
        return self


def load_fixture(bank: str) -> str:
    fixture_path = FIXTURES_DIR / f"{bank}.html"
    if fixture_path.exists():
        return fixture_path.read_text(encoding="utf-8")
    return f"<html><body>Test fixture for {bank}</body></html>"


def load_pdf_fixture(bank: str) -> bytes:
    fixture_path = FIXTURES_DIR / f"{bank}.pdf"
    if fixture_path.exists():
        return fixture_path.read_bytes()
    return b""


@pytest.fixture
def mock_playwright():
    return MockPlaywright


@pytest.fixture
def sudameris_html():
    return load_fixture("sudameris")


@pytest.fixture
def ueno_html():
    return load_fixture("ueno")


@pytest.fixture
def itau_html():
    return load_fixture("itau")


@pytest.fixture
def continental_html():
    return load_fixture("continental")


@pytest.fixture
def bnf_html():
    return load_fixture("bnf")


@pytest.fixture
def ueno_pdf():
    return load_pdf_fixture("ueno")


@pytest.fixture
def bnf_pdf():
    return load_pdf_fixture("bnf")


@pytest.fixture
def patch_playwright():
    def _create_playwright_with_html(html: str = ""):
        mp = MockPlaywright(html)

        class MockSyncPlaywright:
            def __init__(self, html_content: str):
                self._html = html_content

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def chromium(self):
                return MockBrowser(self._html)

        return MockSyncPlaywright(html)

    return _create_playwright_with_html


@pytest.fixture
def patch_requests():
    def _create_mock_requests(pdf_content: bytes = b"", html_content: str = ""):
        class MockResponse:
            def __init__(self, content: bytes, status: int = 200):
                self.content = content
                self.status_code = status
                self._raise_for_status_called = False

            def raise_for_status(self):
                self._raise_for_status_called = True
                if self.status_code >= 400:
                    raise Exception(f"HTTP {self.status_code}")

        class MockRequests:
            def __init__(self, pdf: bytes = b"", html: str = ""):
                self._pdf = pdf
                self._html = html

            def get(self, url: str, timeout: int = 30, headers: dict = None):
                if ".pdf" in url.lower():
                    return MockResponse(self._pdf)
                if url and "http" in url.lower():
                    return MockResponse(self._html.encode() if self._html else b"")
                return MockResponse(b"")

        return MockRequests(pdf_content, html_content)

    return _create_mock_requests


@pytest.fixture
def run_scraper_func():
    from bankpromos.run_all import run_scraper as _run_scraper
    return _run_scraper


@pytest.fixture
def run_all_func():
    from bankpromos.run_all import run_all_scrapers as _run_all
    return _run_all


@pytest.fixture
def normalizer():
    from bankpromos.core.normalizer import normalize_promotion
    return normalize_promotion


@pytest.fixture
def deduper():
    from bankpromos.core.deduper import dedupe_promotions
    return dedupe_promotions


@pytest.fixture
def scorer():
    from bankpromos.core.scoring import score_promotion
    return score_promotion