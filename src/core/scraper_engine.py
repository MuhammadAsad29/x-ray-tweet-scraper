import asyncio
import logging
from typing import List, Dict, Any, Optional, Set
from playwright.async_api import async_playwright, Page
from config.settings import get_settings
from src.nlu.models import ScrapeRequest
from src.core.session_manager import SessionManager
from src.core.stealth import get_stealth_browser_args
from src.core.polite_throttler import PoliteThrottler
from src.core.parser import TweetParser

logger = logging.getLogger(__name__)


class TwitterScraperEngine:
    """Core Playwright engine for polite, authenticated live tweet scraping."""

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.session_mgr = SessionManager()
        self.throttler = PoliteThrottler(
            min_delay=self.settings.MIN_SCROLL_DELAY,
            max_delay=self.settings.MAX_SCROLL_DELAY,
        )

    async def scrape(self, request: ScrapeRequest) -> List[Dict[str, Any]]:
        """Executes the full scraping lifecycle for the given ScrapeRequest."""
        search_url = request.build_search_url()
        logger.info(f"🎯 Starting scrape for query: '{request.query}' (Target limit: {request.limit})")
        logger.info(f"🔗 Target Search URL: {search_url}")

        collected_tweets: List[Dict[str, Any]] = []
        seen_tweet_ids: Set[str] = set()

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.settings.HEADLESS,
                args=get_stealth_browser_args(),
            )

            context = await self.session_mgr.create_authenticated_context(browser)
            page = await context.new_page()

            try:
                # 1. Navigate to search URL
                logger.info("🌐 Navigating to X search page...")
                response = await page.goto(search_url, timeout=self.settings.PAGE_TIMEOUT_MS, wait_until="domcontentloaded")

                if response and response.status >= 400:
                    logger.warning(f"⚠️ Page returned HTTP status {response.status}")

                # Initial polite wait for timeline hydration
                await self.throttler.polite_delay()

                # 2. Check for login wall or empty state
                is_blocked = await self._check_for_blocks(page)
                if is_blocked:
                    logger.error("❌ Hit login wall or access restriction. Please verify your cookies or run `python main.py --login`.")
                    await browser.close()
                    return []

                # Wait for tweet container to appear (up to 10s)
                try:
                    await page.wait_for_selector('article[data-testid="tweet"], div[data-testid="empty_state_header"]', timeout=10000)
                except Exception:
                    logger.debug("Initial selector wait timed out, proceeding to scroll loop...")

                # Immediate check for "No results" header
                empty_header = await page.query_selector('div[data-testid="empty_state_header"], div[data-testid="emptyState"]')
                if empty_header:
                    logger.warning("🔍 Twitter returned: 'No results found' for this specific query/filter combination.")
                    await browser.close()
                    return []

                # 3. Main Scrolling & Collection Loop
                consecutive_empty = 0
                max_empty = self.settings.MAX_CONSECUTIVE_EMPTY_SCROLLS

                while len(collected_tweets) < request.limit and consecutive_empty < max_empty:
                    # Find all visible tweet articles
                    article_elements = await page.query_selector_all('article[data-testid="tweet"], article')

                    new_in_batch = 0
                    for article in article_elements:
                        tweet_data = await TweetParser.parse_tweet_element(article)
                        if tweet_data and tweet_data["tweet_id"] not in seen_tweet_ids:
                            seen_tweet_ids.add(tweet_data["tweet_id"])
                            collected_tweets.append(tweet_data)
                            new_in_batch += 1

                            logger.info(
                                f"📥 [{len(collected_tweets)}/{request.limit}] "
                                f"{tweet_data['username']}: {tweet_data['text'][:65]}..."
                            )

                            if len(collected_tweets) >= request.limit:
                                break

                    if new_in_batch > 0:
                        consecutive_empty = 0
                        self.throttler.reset_backoff()
                    else:
                        consecutive_empty += 1
                        logger.debug(f"No new tweets in view (empty count: {consecutive_empty}/{max_empty})")
                        if consecutive_empty >= 2:
                            await self.throttler.trigger_backoff("No new tweets loaded")

                    if len(collected_tweets) >= request.limit:
                        break

                    # Perform polite human-like scroll
                    await self.throttler.human_like_scroll(page)

                final_tweets = collected_tweets[:request.limit]
                logger.info(f"✅ Scraping completed. Total tweets collected: {len(final_tweets)}")
                return final_tweets

            except Exception as e:
                logger.error(f"❌ Error during scrape execution: {e}", exc_info=True)
                return collected_tweets[:request.limit]

            finally:
                await browser.close()

    async def _check_for_blocks(self, page: Page) -> bool:
        """Inspects the page to detect login prompts or rate limits."""
        try:
            # Check for login redirection
            current_url = page.url
            if "/i/flow/login" in current_url:
                return True

            # Check for login wall modal / text
            login_indicators = await page.query_selector_all(
                'text="Sign in to X", text="Log in to Twitter", div[data-testid="loginButton"]'
            )
            if len(login_indicators) > 0:
                return True

            return False
        except Exception:
            return False
