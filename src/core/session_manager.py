import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from playwright.async_api import Browser, BrowserContext, async_playwright
from config.settings import get_settings
from src.core.stealth import get_stealth_browser_args, get_default_context_options, STEALTH_INIT_SCRIPT

logger = logging.getLogger(__name__)


class SessionManager:
    """Handles session persistence, cookie injection, and interactive login."""

    def __init__(self):
        self.settings = get_settings()
        self.state_file_path = self.settings.get_auth_state_path()

    def has_saved_session(self) -> bool:
        """Checks if a valid storage state JSON file exists."""
        if self.state_file_path.exists() and self.state_file_path.stat().st_size > 10:
            return True
        return False

    def has_direct_cookies(self) -> bool:
        """Checks if auth_token cookie is provided in settings."""
        return bool(self.settings.TWITTER_AUTH_TOKEN)

    def get_direct_cookies_list(self) -> List[Dict[str, Any]]:
        """Constructs cookie dictionaries from settings for both .x.com and .twitter.com."""
        cookies = []
        if self.settings.TWITTER_AUTH_TOKEN:
            for domain in [".x.com", ".twitter.com"]:
                cookies.append({
                    "name": "auth_token",
                    "value": self.settings.TWITTER_AUTH_TOKEN.strip(),
                    "domain": domain,
                    "path": "/",
                    "secure": True,
                    "httpOnly": True,
                    "sameSite": "None",
                })
        if self.settings.TWITTER_CT0:
            for domain in [".x.com", ".twitter.com"]:
                cookies.append({
                    "name": "ct0",
                    "value": self.settings.TWITTER_CT0.strip(),
                    "domain": domain,
                    "path": "/",
                    "secure": True,
                    "httpOnly": False,
                    "sameSite": "Lax",
                })
        return cookies

    async def create_authenticated_context(self, browser: Browser) -> BrowserContext:
        """Creates a browser context with restored session state or injected cookies."""
        context_options = get_default_context_options(self.settings.DEFAULT_USER_AGENT)

        if self.has_saved_session():
            logger.info(f"🔑 Loading saved session state from: {self.state_file_path}")
            context = await browser.new_context(
                storage_state=str(self.state_file_path),
                **context_options
            )
        else:
            logger.info("⚡ Creating new browser context...")
            context = await browser.new_context(**context_options)

            if self.has_direct_cookies():
                logger.info("🍪 Injecting direct session cookies (auth_token/ct0)...")
                await context.add_cookies(self.get_direct_cookies_list())

        # Inject stealth scripts into the context
        await context.add_init_script(STEALTH_INIT_SCRIPT)
        return context

    async def save_session_state(self, context: BrowserContext) -> None:
        """Saves current cookies and local storage to the auth state file."""
        self.state_file_path.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(self.state_file_path))
        logger.info(f"💾 Successfully saved session state to {self.state_file_path}")

    async def run_interactive_login(self) -> bool:
        """Opens a visible (headful) browser window so the user can log in manually once."""
        logger.info("🚀 Launching visible browser for interactive login...")
        print("\n" + "=" * 65)
        print(" [MANUAL LOGIN MODE]")
        print(" A browser window is opening. Please log into your X/Twitter account.")
        print(" Once logged in and on the home feed, press ENTER in this terminal.")
        print("=" * 65 + "\n")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                args=get_stealth_browser_args()
            )
            context = await browser.new_context(
                **get_default_context_options(self.settings.DEFAULT_USER_AGENT)
            )
            await context.add_init_script(STEALTH_INIT_SCRIPT)

            page = await context.new_page()
            try:
                logger.info("🌐 Opening login page (https://x.com/login)...")
                await page.goto("https://x.com/login", timeout=self.settings.PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
            except Exception as e:
                logger.warning(f"⚠️ x.com navigation issue: {e}. Retrying with twitter.com/login...")
                await page.goto("https://twitter.com/login", timeout=self.settings.PAGE_TIMEOUT_MS, wait_until="domcontentloaded")

            # Wait for user confirmation in console
            input("👉 Log in on the browser window, then press ENTER here when on the home feed...")

            # Save state
            await self.save_session_state(context)
            await browser.close()

        print("✅ Authentication state saved successfully! You can now run scrapers in headless mode.")
        return True
