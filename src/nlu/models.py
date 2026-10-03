from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ScrapeRequest(BaseModel):
    """Structured parameters parsed from natural language or CLI for scraping tweets."""

    query: str = Field(description="Search term or hashtag (e.g. '#Python' or 'Artificial Intelligence')")
    since: Optional[str] = Field(default=None, description="Start date in YYYY-MM-DD format")
    until: Optional[str] = Field(default=None, description="End date in YYYY-MM-DD format")
    limit: int = Field(default=50, ge=1, le=5000, description="Maximum number of tweets to collect")
    language: str = Field(default="en", description="Language filter (e.g. 'en')")
    filter_retweets: bool = Field(default=True, description="Exclude retweets to avoid duplicate noise")
    f_live: bool = Field(default=True, description="True for 'Latest/Live' tab, False for 'Top/Highest Reach' tab")
    min_likes: Optional[int] = Field(default=None, ge=0, description="Minimum likes/favorites filter (min_faves:N)")
    min_retweets: Optional[int] = Field(default=None, ge=0, description="Minimum retweets filter (min_retweets:N)")

    @field_validator("query")
    @classmethod
    def clean_query(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Query string cannot be empty")
        return v

    def build_search_query(self) -> str:
        """Constructs the X/Twitter advanced search query string with reach/engagement filters."""
        terms = [self.query]

        if self.filter_retweets:
            terms.append("-is:retweet")

        if self.language:
            terms.append(f"lang:{self.language}")

        if self.since:
            terms.append(f"since:{self.since}")

        if self.until:
            terms.append(f"until:{self.until}")

        if self.min_likes and self.min_likes > 0:
            terms.append(f"min_faves:{self.min_likes}")

        if self.min_retweets and self.min_retweets > 0:
            terms.append(f"min_retweets:{self.min_retweets}")

        return " ".join(terms)

    def build_search_url(self) -> str:
        """Constructs the full X/Twitter search URL with query parameters."""
        import urllib.parse
        raw_query = self.build_search_query()
        encoded = urllib.parse.quote(raw_query)
        tab_param = "&f=live" if self.f_live else ""
        return f"https://x.com/search?q={encoded}&src=typed_query{tab_param}"
