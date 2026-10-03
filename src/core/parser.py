import re
from typing import Dict, Any, Optional, List
from bs4 import BeautifulSoup
from playwright.async_api import ElementHandle


class TweetParser:
    """Extracts structured tweet information from Playwright ElementHandles and BeautifulSoup DOM."""

    @staticmethod
    async def parse_tweet_element(element: ElementHandle) -> Optional[Dict[str, Any]]:
        """Extracts complete tweet fields from an article ElementHandle."""
        try:
            # 1. Get raw inner HTML for BeautifulSoup parsing
            html = await element.inner_html()
            soup = BeautifulSoup(html, "lxml")

            # 2. Extract Tweet Link & ID
            tweet_id, permalink = TweetParser._extract_tweet_id_and_url(soup)
            if not tweet_id:
                # Fallback to direct evaluate
                status_link = await element.query_selector('a[href*="/status/"]')
                if status_link:
                    href = await status_link.get_attribute("href")
                    if href:
                        tweet_id, permalink = TweetParser._parse_status_href(href)

            if not tweet_id:
                return None

            # 3. Extract User Information
            username, display_name = TweetParser._extract_user_info(soup)

            # 4. Extract Tweet Content
            text = TweetParser._extract_tweet_text(soup)

            # 5. Extract Timestamp
            timestamp = TweetParser._extract_timestamp(soup)

            # 6. Extract Engagement Metrics
            metrics = TweetParser._extract_metrics(soup)

            # 7. Extract Media Links
            media_urls = TweetParser._extract_media(soup)

            # 8. Check Retweet / Quote flag
            is_retweet = bool(soup.select_one('[data-testid="socialContext"]'))

            return {
                "tweet_id": tweet_id,
                "url": permalink,
                "username": username,
                "display_name": display_name,
                "text": text,
                "timestamp": timestamp,
                "replies": metrics.get("replies", 0),
                "retweets": metrics.get("retweets", 0),
                "likes": metrics.get("likes", 0),
                "views": metrics.get("views", 0),
                "is_retweet": is_retweet,
                "media_urls": media_urls,
            }

        except Exception as e:
            return None

    @staticmethod
    def _parse_status_href(href: str) -> tuple[Optional[str], Optional[str]]:
        match = re.search(r"/([^/]+)/status/(\d+)", href)
        if match:
            tweet_id = match.group(2)
            permalink = f"https://x.com{href}" if href.startswith("/") else href
            return tweet_id, permalink
        return None, None

    @staticmethod
    def _extract_tweet_id_and_url(soup: BeautifulSoup) -> tuple[Optional[str], Optional[str]]:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/status/" in href:
                tweet_id, permalink = TweetParser._parse_status_href(href)
                if tweet_id:
                    return tweet_id, permalink
        return None, None

    @staticmethod
    def _extract_user_info(soup: BeautifulSoup) -> tuple[str, str]:
        username = "Unknown"
        display_name = "Unknown"

        user_block = soup.select_one('[data-testid="User-Name"]') or soup.select_one('[data-testid="User-Names"]')
        if user_block:
            # Display name is usually the first span or bold text
            spans = [s.get_text(strip=True) for s in user_block.find_all("span") if s.get_text(strip=True)]
            for s in spans:
                if s.startswith("@"):
                    username = s
                elif display_name == "Unknown" and not s.startswith("@") and s != "·":
                    display_name = s

        return username, display_name

    @staticmethod
    def _extract_tweet_text(soup: BeautifulSoup) -> str:
        text_elem = soup.select_one('[data-testid="tweetText"]')
        if text_elem:
            return text_elem.get_text(separator=" ", strip=True)
        return ""

    @staticmethod
    def _extract_timestamp(soup: BeautifulSoup) -> Optional[str]:
        time_elem = soup.find("time")
        if time_elem and time_elem.get("datetime"):
            return time_elem["datetime"]
        return None

    @staticmethod
    def _extract_metrics(soup: BeautifulSoup) -> Dict[str, int]:
        metrics = {"replies": 0, "retweets": 0, "likes": 0, "views": 0}

        reply_elem = soup.select_one('[data-testid="reply"]')
        if reply_elem:
            metrics["replies"] = TweetParser._parse_metric_number(reply_elem.get_text(strip=True))

        retweet_elem = soup.select_one('[data-testid="retweet"]')
        if retweet_elem:
            metrics["retweets"] = TweetParser._parse_metric_number(retweet_elem.get_text(strip=True))

        like_elem = soup.select_one('[data-testid="like"]')
        if like_elem:
            metrics["likes"] = TweetParser._parse_metric_number(like_elem.get_text(strip=True))

        return metrics

    @staticmethod
    def _parse_metric_number(val_str: str) -> int:
        if not val_str:
            return 0
        val_str = val_str.replace(",", "").strip().upper()
        try:
            if "K" in val_str:
                return int(float(val_str.replace("K", "")) * 1000)
            elif "M" in val_str:
                return int(float(val_str.replace("M", "")) * 1000000)
            return int(float(val_str))
        except ValueError:
            return 0

    @staticmethod
    def _extract_media(soup: BeautifulSoup) -> List[str]:
        media = []
        photos = soup.select('[data-testid="tweetPhoto"] img')
        for img in photos:
            if img.get("src"):
                media.append(img["src"])
        return media
