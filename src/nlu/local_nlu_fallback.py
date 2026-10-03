import re
from datetime import datetime, timedelta
from typing import Optional, Tuple
from src.nlu.models import ScrapeRequest


class LocalNLUParser:
    """Robust local rule-based Natural Language parser for extracting scraping parameters."""

    @staticmethod
    def parse_prompt(prompt: str) -> ScrapeRequest:
        """Parses natural language prompt into a ScrapeRequest object."""
        text = prompt.strip()

        # 1. Extract Limit / Count (handles 'top 10', 'limit 50', '25 latest tweets', etc.)
        limit = 50
        limit_match = re.search(r"(?:limit|max|count|get|scrape|collect|fetch|top)\s+(\d+)", text, re.IGNORECASE)
        if not limit_match:
            limit_match = re.search(r"(\d+)\s*(?:latest|live|viral|recent|popular|top)?\s*(?:tweets|posts)", text, re.IGNORECASE)
        if limit_match:
            try:
                limit = int(limit_match.group(1))
            except (ValueError, IndexError):
                limit = 50

        # 2. Extract Dates
        since_date, until_date = LocalNLUParser._extract_dates(text)

        # 3. Detect Top / Highest Reach vs Live / Latest Tab
        # If user asks for 'top', 'highest reach', 'viral', 'most liked', OR sets min_likes/min_retweets,
        # we MUST target the 'Top' tab (f_live=False) because live stream tweets have 0-1 likes!
        has_engagement_filter = bool(min_likes or min_retweets)
        has_top_kw = bool(re.search(r"\b(top|highest reach|popular|most liked|most viewed|viral|best)\b", text, re.IGNORECASE))
        has_latest_kw = bool(re.search(r"\b(latest|live|recent|newest)\b", text, re.IGNORECASE))

        if has_engagement_filter or (has_top_kw and not (has_latest_kw and not has_top_kw)):
            f_live = False
        else:
            f_live = True

        # 4. Extract Min Likes / Retweets threshold
        min_likes = None
        min_likes_match = re.search(r"(?:min|minimum|at least)\s+(\d+)\s*(?:likes?|faves?|favorites?)", text, re.IGNORECASE)
        if min_likes_match:
            min_likes = int(min_likes_match.group(1))

        min_retweets = None
        min_rt_match = re.search(r"(?:min|minimum|at least)\s+(\d+)\s*(?:retweets?|rts?)", text, re.IGNORECASE)
        if min_rt_match:
            min_retweets = int(min_rt_match.group(1))

        # 5. Extract Hashtag or Query Topic
        query = LocalNLUParser._extract_query(text)

        # 6. Extract Language (if specified)
        lang = "en"
        lang_match = re.search(r"(?:lang|language)[:\s]+([a-zA-Z]{2})", text, re.IGNORECASE)
        if lang_match:
            lang = lang_match.group(1).lower()

        return ScrapeRequest(
            query=query,
            since=since_date,
            until=until_date,
            limit=limit,
            language=lang,
            filter_retweets=True,
            f_live=f_live,
            min_likes=min_likes,
            min_retweets=min_retweets
        )

    @staticmethod
    def _extract_dates(text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extracts start (since) and end (until) dates from query text."""
        since_date: Optional[str] = None
        until_date: Optional[str] = None

        date_pattern = r"\b(\d{4}-\d{2}-\d{2})\b"
        all_dates = re.findall(date_pattern, text)

        if len(all_dates) >= 2:
            since_date = all_dates[0]
            until_date = all_dates[1]
        elif len(all_dates) == 1:
            if re.search(r"(?:since|from|start|after)\s+" + re.escape(all_dates[0]), text, re.IGNORECASE):
                since_date = all_dates[0]
            elif re.search(r"(?:until|to|end|before)\s+" + re.escape(all_dates[0]), text, re.IGNORECASE):
                until_date = all_dates[0]
            else:
                since_date = all_dates[0]

        if not since_date and not until_date:
            today = datetime.utcnow().date()
            relative_days_match = re.search(r"(?:last|past)\s+(\d+)\s+days?", text, re.IGNORECASE)
            relative_weeks_match = re.search(r"(?:last|past)\s+(\d+)\s+weeks?", text, re.IGNORECASE)
            relative_months_match = re.search(r"(?:last|past)\s+(\d+)\s+months?", text, re.IGNORECASE)

            if relative_days_match:
                days = int(relative_days_match.group(1))
                since_date = (today - timedelta(days=days)).isoformat()
                until_date = today.isoformat()
            elif relative_weeks_match:
                weeks = int(relative_weeks_match.group(1))
                since_date = (today - timedelta(weeks=weeks)).isoformat()
                until_date = today.isoformat()
            elif relative_months_match:
                months = int(relative_months_match.group(1))
                since_date = (today - timedelta(days=months * 30)).isoformat()
                until_date = today.isoformat()
            elif re.search(r"\b(?:yesterday)\b", text, re.IGNORECASE):
                yesterday = today - timedelta(days=1)
                since_date = yesterday.isoformat()
                until_date = today.isoformat()

        return since_date, until_date

    @staticmethod
    def _extract_query(text: str) -> str:
        """Extracts target hashtag (#topic) or keywords from the natural text."""
        # 1. Direct hashtag check (Twitter hashtags are alphanumeric + underscores)
        hashtags = re.findall(r"#[a-zA-Z0-9_]+", text)
        if hashtags:
            return " ".join(hashtags)

        # 2. Extract after trigger words like "about", "for", "with", "hashtag", "query", "topic"
        trigger_match = re.search(
            r"(?:about|for|with|hashtag|topic|keyword|search)\s+[\"']?([^\"'\n,]+?)[\"']?"
            r"(?:\s+(?:from|since|between|in the last|with limit|limit|max|during|with min|min)|\s*$)",
            text,
            re.IGNORECASE
        )
        if trigger_match:
            candidate = trigger_match.group(1).strip()
            cleaned = re.sub(r"\b(tweets|live tweets|top tweets|latest tweets|posts)\b", "", candidate, flags=re.IGNORECASE).strip()
            if cleaned:
                return cleaned

        cleaned = re.sub(
            r"(?:scrape|collect|fetch|find|get|search|live|top|latest|recent|highest reach|popular|tweets|posts|from|to|between|since|until|\d{4}-\d{2}-\d{2}|\d+)",
            "",
            text,
            flags=re.IGNORECASE
        ).strip()
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned if cleaned else "#trending"
