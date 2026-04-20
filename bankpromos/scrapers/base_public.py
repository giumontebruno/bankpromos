from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

from bankpromos.core.exceptions import NavigationError, ScrapingError, AntiBotDetectedError


class BasePublicScraper(ABC):
    def __init__(
        self,
        headless: Optional[bool] = None,
        debug_mode: bool = False,
        user_agent: Optional[str] = None,
    ):
        self.headless = False if debug_mode else (True if headless is None else headless)
        self.debug_mode = debug_mode
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        )
        self.default_timeout = 30000
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._debug_dir = Path("debug_output")

    @abstractmethod
    def _get_bank_id(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def _scrape_promotions(self) -> list:
        raise NotImplementedError

    def _ensure_page(self) -> Page:
        if not self.page:
            raise RuntimeError("Page not initialized")
        return self.page

    def _navigate(self, url: str, wait_for: Optional[str] = None):
        page = self._ensure_page()
        try:
            page.goto(url, timeout=self.default_timeout, wait_until=wait_for or "domcontentloaded")
        except PlaywrightTimeoutError as e:
            raise NavigationError(f"Timeout navigating to {url}", {"url": url}) from e
        except Exception as e:
            raise NavigationError(f"Failed to navigate to {url}", {"url": url, "error": str(e)}) from e

    def _click(self, selector: str, timeout: Optional[int] = None):
        page = self._ensure_page()
        try:
            page.click(selector, timeout=timeout or self.default_timeout)
        except PlaywrightTimeoutError as e:
            raise NavigationError(f"Timeout clicking {selector}", {"selector": selector}) from e

    def _wait_for_selector(self, selector: str, timeout: Optional[int] = None):
        page = self._ensure_page()
        try:
            page.wait_for_selector(selector, timeout=timeout or self.default_timeout)
        except PlaywrightTimeoutError as e:
            raise NavigationError(f"Timeout waiting for {selector}", {"selector": selector}) from e

    def _wait_for_load_state(self, state: str = "domcontentloaded"):
        page = self._ensure_page()
        page.wait_for_load_state(state)

    def _scroll_down(self, times: int = 1, delay_ms: int = 500):
        page = self._ensure_page()
        for _ in range(times):
            page.mouse.wheel(0, 1000)
            page.wait_for_timeout(delay_ms)

    def _human_delay(self, min_ms: int = 500, max_ms: int = 1500):
        import random
        import time
        delay = random.randint(min_ms, max_ms) / 1000
        time.sleep(delay)

    def _save_debug_screenshot(self, name: str):
        if not self.debug_mode:
            return
        bank_id = self._get_bank_id()
        debug_dir = self._debug_dir / bank_id
        debug_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.page.screenshot(path=str(debug_dir / f"{name}_{timestamp}.png"))

    def _save_debug_html(self, name: str):
        if not self.debug_mode:
            return
        bank_id = self._get_bank_id()
        debug_dir = self._debug_dir / bank_id
        debug_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_path = debug_dir / f"{name}_{timestamp}.html"
        html_path.write_text(self.page.content())

    def scrape(self) -> list:
        with sync_playwright() as p:
            self.playwright = p
            try:
                self.browser = p.chromium.launch(
                    headless=self.headless,
                    channel="chrome",
                )
            except Exception:
                self.browser = p.chromium.launch(headless=self.headless)

            self.context = self.browser.new_context(
                locale="es-PY",
                timezone_id="America/Asuncion",
                viewport={"width": 1366, "height": 768},
                user_agent=self.user_agent,
            )
            self.context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
            )
            self.page = self.context.new_page()
            self.page.set_default_timeout(self.default_timeout)

            try:
                result = self._scrape_promotions()
            except AntiBotDetectedError:
                self._save_debug_html("blocked")
                raise
            except Exception as e:
                self._save_debug_screenshot("error")
                self._save_debug_html("error")
                raise ScrapingError(f"Scraping failed: {str(e)}") from e
            finally:
                self.browser.close()

        return result