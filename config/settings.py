import os
from functools import lru_cache
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings and configuration parameters."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Base Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    OUTPUT_DIR: str = "output"
    CONFIG_DIR: str = "config"

    # Browser & Politeness Settings
    HEADLESS: bool = Field(default=True, description="Run browser in headless mode")
    MIN_SCROLL_DELAY: float = Field(default=2.0, description="Minimum delay between scroll operations (seconds)")
    MAX_SCROLL_DELAY: float = Field(default=4.5, description="Maximum delay between scroll operations (seconds)")
    PAGE_TIMEOUT_MS: int = Field(default=60000, description="Navigation timeout in milliseconds")
    MAX_RETRIES: int = Field(default=3, description="Maximum retries upon failure")
    MAX_CONSECUTIVE_EMPTY_SCROLLS: int = Field(default=5, description="Stop after N scrolls with no new tweets")
    DEFAULT_USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    # Authentication & Session Persistence
    AUTH_STATE_FILE: str = Field(default="config/auth_state.json", description="Path to saved session state")
    TWITTER_AUTH_TOKEN: Optional[str] = Field(default=None, description="Direct auth_token cookie from X")
    TWITTER_CT0: Optional[str] = Field(default=None, description="Direct ct0 (CSRF) cookie from X")

    # Dialogflow NLU Settings
    DIALOGFLOW_EDITION: str = Field(default="local", description="'cx', 'es', or 'local'")
    DIALOGFLOW_PROJECT_ID: Optional[str] = Field(default=None, description="GCP Project ID for Dialogflow")
    DIALOGFLOW_LOCATION: str = Field(default="global", description="Dialogflow CX Location")
    DIALOGFLOW_AGENT_ID: Optional[str] = Field(default=None, description="Dialogflow CX Agent ID")
    DIALOGFLOW_LANGUAGE_CODE: str = Field(default="en", description="Language code for NLU intent detection")
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = Field(default=None, description="Path to service account key")

    def get_output_path(self) -> Path:
        """Returns the resolved output directory and ensures it exists."""
        path = self.BASE_DIR / self.OUTPUT_DIR
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_auth_state_path(self) -> Path:
        """Returns the resolved auth state JSON path."""
        path = Path(self.AUTH_STATE_FILE)
        if not path.is_absolute():
            path = self.BASE_DIR / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache()
def get_settings() -> Settings:
    """Singleton getter for application settings."""
    return Settings()
