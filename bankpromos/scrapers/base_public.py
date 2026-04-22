import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

from bankpromos.core.exceptions import NavigationError, ScrapingError, AntiBotDetectedError

logger = logging.getLogger(__name__)


@dataclass
class ScraperDiagnostics:
    bank_id: str = ""
    success: bool = False
    url: str = ""
    title: str = ""
    body_text_length: int = 0
    card_matches: int = 0
    pdf_links_found: int = 0
    fallback_ran: bool = False
    extracted_before_dedupe: int = 0
    extracted_after_dedupe: int = 0
    error: str = ""
    source_used: str = "unknown"
    xhr_urls: List[str] = field(default_factory=list)
    relevant_urls: List[str] = field(default_factory=list)
    promos_from_dom: int = 0
    promos_from_pdf: int = 0
    promos_from_api: int = 0
    rejected_generic_count: int = 0
    quality_label: str = "unknown"

    def to_dict(self):
        result = asdict(self)
        result["xhr_urls"] = self.xhr_urls
        result["relevant_urls"] = self.relevant_urls
        return result


class BasePublicScraper(ABC):
    INTERESTING_PATTERNS = [
        "beneficio", "promo", "discount", "merchant", "json", "api",
        "pdf", "beneficios", "catalogo", "catalog", "assets", "data",
    ]

    def __init__(
        self,
        headless: Optional[bool] = None,
        debug_mode: bool = False,
        user_agent: Optional[str] = None,
    ):
        if os.getenv("RAILWAY") or os.getenv("DYNO") or os.getenv("KOYEB"):
            self.headless = True
        else:
            self.headless = False if debug_mode else (True if headless is None else headless)
        self.debug_mode = debug_mode
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        )
        self.default_timeout = 60000
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._debug_dir = Path("debug_output")
        self._diagnostics = ScraperDiagnostics()
        self._card_match_count = 0
        self._pdf_link_count = 0
        self._fallback_ran = False
        self._extracted_count = 0
        self._captured_urls: List[str] = []
        self._relevant_urls: List[str] = []

    def _init_diagnostics(self):
        self._diagnostics = ScraperDiagnostics(bank_id=self._get_bank_id())
        self._card_match_count = 0
        self._pdf_link_count = 0
        self._fallback_ran = False
        self._extracted_count = 0
        self._captured_urls = []
        self._relevant_urls = []

    def get_diagnostics(self) -> ScraperDiagnostics:
        self._diagnostics.xhr_urls = self._captured_urls
        self._diagnostics.relevant_urls = self._relevant_urls
        return self._diagnostics

    def _record_card_match(self):
        self._card_match_count += 1

    def _record_pdf_link(self):
        self._pdf_link_count += 1

    def _record_fallback(self):
        self._fallback_ran = True

    def _record_extracted(self, count: int):
        self._extracted_count = count

    def _finalize_diagnostics(self, url: str, title: str, before_dedupe: int, after_dedupe: int, body_len: int = 0):
        self._diagnostics.url = url
        self._diagnostics.title = title
        self._diagnostics.card_matches = self._card_match_count
        self._diagnostics.pdf_links_found = self._pdf_link_count
        self._diagnostics.fallback_ran = self._fallback_ran
        self._diagnostics.extracted_before_dedupe = self._extracted_count
        self._diagnostics.extracted_after_dedupe = after_dedupe
        self._diagnostics.body_text_length = body_len
        self._diagnostics.xhr_urls = self._captured_urls
        self._diagnostics.relevant_urls = self._relevant_urls
        self._diagnostics.success = True

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

    def _setup_request_capture(self):
        if not self.page:
            return

        def handle_request(request):
            url = request.url
            if url not in self._captured_urls:
                self._captured_urls.append(url)
                if self._is_relevant_url(url):
                    if url not in self._relevant_urls:
                        self._relevant_urls.append(url)

        self.page.on("request", handle_request)

    def _is_relevant_url(self, url: str) -> bool:
        url_lower = url.lower()
        return any(pattern in url_lower for pattern in self.INTERESTING_PATTERNS)

    def _navigate_staged(self, url: str) -> bool:
        page = self._ensure_page()
        strategies_tried = []

        try:
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            strategies_tried.append("domcontentloaded")
        except PlaywrightTimeoutError:
            pass

        try:
            page.wait_for_load_state("load", timeout=5000)
            strategies_tried.append("load")
        except PlaywrightTimeoutError:
            pass

        try:
            page.wait_for_load_state("networkidle", timeout=8000)
            strategies_tried.append("networkidle")
        except PlaywrightTimeoutError:
            pass

        page.wait_for_timeout(1500)

        self._diagnostics.url = page.url
        self._diagnostics.title = page.title() or ""
        logger.info(f"[{self._get_bank_id()}] Wait strategies tried: {strategies_tried}")

        return len(strategies_tried) > 0

    def _navigate(self, url: str, wait_for: Optional[str] = None):
        page = self._ensure_page()
        try:
            page.goto(url, timeout=self.default_timeout, wait_until=wait_for or "domcontentloaded")
            self._diagnostics.url = page.url
            self._diagnostics.title = page.title() or ""
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

    def _get_debug_dir(self) -> Path:
        bank_id = self._get_bank_id()
        debug_dir = self._debug_dir / bank_id
        debug_dir.mkdir(parents=True, exist_ok=True)
        return debug_dir

    def _save_debug_screenshot(self, name: str):
        if not self.debug_mode or not self._page_is_alive():
            return
        debug_dir = self._get_debug_dir()
        try:
            self.page.screenshot(path=str(debug_dir / f"{name}.png"), full_page=True)
        except Exception as e:
            logger.warning(f"Failed to save screenshot: {e}")

    def _save_debug_html(self, name: str):
        if not self.debug_mode or not self._page_is_alive():
            return
        debug_dir = self._get_debug_dir()
        try:
            (debug_dir / f"{name}.html").write_text(self.page.content()[:500000], encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to save HTML: {e}")

    def _save_debug_preview(self):
        if not self.debug_mode or not self._page_is_alive():
            return
        debug_dir = self._get_debug_dir()
        try:
            body_text = ""
            if self.page:
                try:
                    body_text = self.page.locator("body").inner_text()
                except Exception:
                    pass
            (debug_dir / "preview.txt").write_text(body_text[:5000], encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to save preview: {e}")

    def _save_debug_urls(self):
        if not self.debug_mode:
            return
        debug_dir = self._get_debug_dir()
        try:
            (debug_dir / "response_urls.txt").write_text(
                "\n".join(self._captured_urls),
                encoding="utf-8"
            )
            (debug_dir / "relevant_urls.txt").write_text(
                "\n".join(self._relevant_urls),
                encoding="utf-8"
            )
        except Exception as e:
            logger.warning(f"Failed to save URLs: {e}")

    def _save_debug_summary(self):
        if not self.debug_mode:
            return
        debug_dir = self._get_debug_dir()
        try:
            summary = {
                "bank_id": self._get_bank_id(),
                "source_used": self._diagnostics.source_used,
                "url": self._diagnostics.url,
                "title": self._diagnostics.title,
                "cards_found": self._card_match_count,
                "pdf_links_found": self._pdf_link_count,
                "xhr_urls_found": len(self._captured_urls),
                "relevant_urls_found": len(self._relevant_urls),
                "promos_from_dom": self._diagnostics.promos_from_dom,
                "promos_from_pdf": self._diagnostics.promos_from_pdf,
                "promos_from_api": self._diagnostics.promos_from_api,
                "final_saved": self._diagnostics.extracted_after_dedupe,
                "relevant_urls": self._relevant_urls[:20],
            }
            (debug_dir / "source_summary.json").write_text(
                json.dumps(summary, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            logger.warning(f"Failed to save summary: {e}")

    def _page_is_alive(self) -> bool:
        try:
            return self.page is not None and self.browser is not None and self.browser.is_connected()
        except Exception:
            return False

    def scrape(self) -> list:
        self._init_diagnostics()
        result = []
        with sync_playwright() as p:
            self.playwright = p
            launch_args = [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--headless=new",
            ]
            try:
                self.browser = p.chromium.launch(
                    headless=True,
                    args=launch_args,
                )
            except Exception:
                try:
                    self.browser = p.firefox.launch(
                        headless=True,
                    )
                except Exception:
                    self.browser = p.chromium.launch(
                        headless=True,
                        args=launch_args,
                    )

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

            self._setup_request_capture()

            try:
                result = self._scrape_promotions()
            except AntiBotDetectedError:
                if self._page_is_alive():
                    self._save_debug_html("blocked")
                self._diagnostics.error = "Anti-bot detected"
                raise
            except Exception as e:
                self._diagnostics.error = str(e)[:200]
                if self._page_is_alive():
                    self._save_debug_screenshot("error")
                    self._save_debug_html("error")
                raise ScrapingError(f"Scraping failed: {str(e)}") from e
            finally:
                if self.debug_mode and self._page_is_alive():
                    try:
                        self._save_debug_screenshot("final")
                        self._save_debug_html("final")
                        self._save_debug_preview()
                        self._save_debug_urls()
                        self._save_debug_summary()
                    except Exception as e:
                        logger.warning(f"Failed to save debug artifacts: {e}")
                try:
                    self.browser.close()
                except Exception:
                    pass

        return result