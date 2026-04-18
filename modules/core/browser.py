"""
modules/core/browser.py
Browser Manager - Khởi tạo Playwright với proxy + anti-detection
"""

import os
import asyncio
import random
from typing import Optional, Dict, Any
from pathlib import Path

from loguru import logger

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from modules.utils.logger import get_logger
from modules.utils.retry import retry_on_failure, async_random_delay


# ─── User-Agent pool ────────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


# ═══════════════════════════════════════════════════════════════════════════
#  BROWSER MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class BrowserManager:
    """
    Quản lý trình duyệt Playwright với anti-detection và proxy.
    """

    def __init__(self,
                 headless: bool = True,
                 browser_type: str = "chromium",
                 screenshots_dir: str = "screenshots",
                 user_agent: Optional[str] = None,
                 proxy_url: Optional[str] = None):
        self.headless       = headless
        self.browser_type   = browser_type
        self.screenshots_dir = Path(screenshots_dir)
        self.screenshots_dir.mkdir(exist_ok=True)
        self.user_agent     = user_agent or random.choice(USER_AGENTS)
        self.proxy_url      = proxy_url

        self._playwright  = None
        self._browser     = None
        self._contexts    = {}  # account_id -> context
        self._log         = get_logger("BrowserManager")

    # ─────────────────────────────────────────────────────────────────────
    #  Lifecycle
    # ─────────────────────────────────────────────────────────────────────
    async def start(self) -> None:
        """Khởi tạo Playwright và browser."""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "Playwright chưa được cài đặt.\n"
                "Chạy: pip install playwright && playwright install chromium"
            )
        self._playwright = await async_playwright().start()
        self._browser    = await self._playwright.chromium.launch(
            headless=self.headless,
            args=self._get_chrome_args(),
        )
        self._log.info(f"Browser started: {self.browser_type}, headless={self.headless}")

    async def stop(self) -> None:
        """Đóng toàn bộ browser và contexts."""
        for ctx in self._contexts.values():
            try:
                await ctx.close()
            except Exception:
                pass
        self._contexts.clear()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._log.info("Browser stopped.")

    # ─────────────────────────────────────────────────────────────────────
    #  Context helpers
    # ─────────────────────────────────────────────────────────────────────
    async def new_context(self, account_id: int,
                           proxy: Optional[Dict[str, Any]] = None,
                           locale: str = "en-US",
                           storage_state: Optional[str] = None) -> BrowserContext:
        """Tạo trình duyệt context mới cho 1 account."""

        # Build playwright proxy dict
        playwright_proxy = None
        if proxy:
            pw = {"server": proxy.get("server")}  # e.g. "http://host:port"
            if proxy.get("username"):
                pw["username"] = proxy["username"]
                pw["password"]  = proxy.get("password", "")
            playwright_proxy = pw

        context_kwargs = {
            "locale": locale,
            "viewport": {"width": 1280, "height": 800},
            "user_agent": self.user_agent,
            "proxy": playwright_proxy,
            "accept_downloads": True,
        }

        if storage_state:
            storage_state_path = Path(storage_state)
            if storage_state_path.exists():
                context_kwargs["storage_state"] = str(storage_state_path)
                self._log.info(f"Using saved session state: {storage_state_path}")
            else:
                self._log.warning(f"Session state not found: {storage_state_path}")

        ctx = await self._browser.new_context(
            **context_kwargs,
        )

        # Anti-detection: disable webdriver flag
        await ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)

        self._contexts[account_id] = ctx
        return ctx

    async def get_context(self, account_id: int) -> Optional[BrowserContext]:
        return self._contexts.get(account_id)

    async def close_context(self, account_id: int) -> None:
        ctx = self._contexts.pop(account_id, None)
        if ctx:
            await ctx.close()

    # ─────────────────────────────────────────────────────────────────────
    #  Page helpers
    # ─────────────────────────────────────────────────────────────────────
    async def new_page(self, account_id: int,
                       locale: str = "en-US") -> Page:
        """Tạo page mới trong context của account."""
        ctx = self._contexts.get(account_id)
        if ctx is None:
            ctx = await self.new_context(account_id, locale=locale)
        page = await ctx.new_page()
        return page

    async def screenshot_page(self, page: Page,
                              name: str,
                              job_id: Optional[int] = None) -> str:
        """Chụp màn hình page, trả về đường dẫn file."""
        ts = asyncio.get_event_loop().time()
        filename = f"{name}_{job_id or 'nofile'}_{ts}.png"
        path = self.screenshots_dir / filename
        await page.screenshot(path=str(path), full_page=True)
        return str(path)

    # ─────────────────────────────────────────────────────────────────────
    #  Navigation helpers
    # ─────────────────────────────────────────────────────────────────────
    async def safe_goto(self, page: Page, url: str,
                        wait_until: str = "domcontentloaded",
                        timeout: int = 30000) -> bool:
        """Navigate an toàn, retry nếu timeout."""
        try:
            await page.goto(url, wait_until=wait_until, timeout=timeout)
            await async_random_delay(1.5, 3.0)
            return True
        except Exception as e:
            self._log.error(f"Goto failed: {url} — {e}")
            return False

    async def safe_click(self, page: Page,
                         selector: str,
                         timeout: int = 10000,
                         delay: float = 0.5) -> bool:
        """Click an toàn, đợi element có thể click được."""
        try:
            await page.wait_for_selector(selector, state="visible", timeout=timeout)
            await async_random_delay(delay, delay + 1.0)
            await page.click(selector)
            return True
        except Exception as e:
            self._log.warning(f"Click failed: {selector} — {e}")
            return False

    async def safe_fill(self, page: Page,
                        selector: str,
                        value: str,
                        delay: float = 0.3) -> bool:
        """Điền text an toàn."""
        try:
            await page.wait_for_selector(selector, state="visible", timeout=10000)
            await async_random_delay(delay, delay + 0.5)
            await page.fill(selector, value)
            return True
        except Exception as e:
            self._log.warning(f"Fill failed: {selector} — {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────
    #  Chrome args (anti-detection)
    # ─────────────────────────────────────────────────────────────────────
    def _get_chrome_args(self) -> list:
        return [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-accelerated-2d-canvas",
            "--no-first-run",
            "--no-zygote",
            "--disable-gpu",
            "--window-size=1280,800",
            "--disable-infobars",
            "--disable-extensions",
            "--disable-notifications",
            "--disable-popup-blocking",
            "--disable-default-apps",
            "--disable-hang-monitor",
            "--disable-prompt-on-repost",
            "--disable-sync",
            "--disable-translate",
            "--metrics-recording-only",
            "--mute-audio",
            "--no-default-browser-check",
            "--password-store=basic",
            "--use-mock-keychain",
        ]

    def __repr__(self):
        return (f"<BrowserManager(type={self.browser_type}, "
                f"headless={self.headless}, "
                f"active_contexts={len(self._contexts)})>")