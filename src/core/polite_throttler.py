import asyncio
import logging
import random
import time
from typing import Optional
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class PoliteThrottler:
    """Manages polite delay intervals, human-like jitter, and rate-limit backoff."""

    def __init__(self, min_delay: float = 2.0, max_delay: float = 4.5):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.consecutive_backoffs = 0
        self.total_polite_sleep_time = 0.0
        self.scroll_count = 0

    async def polite_delay(self, extra_jitter: bool = True) -> float:
        """Sleeps for a random duration within [min_delay, max_delay] with optional Gaussian jitter."""
        base_delay = random.uniform(self.min_delay, self.max_delay)
        if extra_jitter:
            jitter = random.gauss(0, 0.3)
            delay = max(self.min_delay * 0.8, base_delay + jitter)
        else:
            delay = base_delay

        logger.debug(f"Polite delay sleeping for {delay:.2f}s...")
        await asyncio.sleep(delay)
        self.total_polite_sleep_time += delay
        return delay

    async def trigger_backoff(self, reason: str = "Rate Limit or Empty Response") -> float:
        """Applies exponential backoff when encountering rate limits or empty results."""
        self.consecutive_backoffs += 1
        backoff_seconds = min(60.0, (2 ** self.consecutive_backoffs) * 3.0 + random.uniform(1.0, 3.0))
        logger.warning(
            f"⚠️ Triggering backoff (#{self.consecutive_backoffs}) due to: {reason}. "
            f"Pausing for {backoff_seconds:.2f}s..."
        )
        await asyncio.sleep(backoff_seconds)
        self.total_polite_sleep_time += backoff_seconds
        return backoff_seconds

    def reset_backoff(self) -> None:
        """Resets the consecutive backoff counter upon successful data extraction."""
        self.consecutive_backoffs = 0

    async def human_like_scroll(self, page: Page) -> None:
        """Performs a natural, stepped scroll down the page to simulate real user scrolling."""
        self.scroll_count += 1
        steps = random.randint(2, 4)
        for _ in range(steps):
            delta_y = random.randint(300, 700)
            await page.mouse.wheel(0, delta_y)
            await asyncio.sleep(random.uniform(0.15, 0.4))

        # Small micro-pause after completing the scroll gesture
        await self.polite_delay(extra_jitter=True)
