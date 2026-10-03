import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd
from config.settings import get_settings

logger = logging.getLogger(__name__)


class DataExporter:
    """Exports collected tweet datasets to CSV, JSON, and summary reports."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.settings = get_settings()
        self.output_dir = output_dir or self.settings.get_output_path()

    def export(
        self,
        tweets: List[Dict[str, Any]],
        query_tag: str,
        export_format: str = "csv"
    ) -> Optional[Path]:
        """Saves tweets to disk in the requested format (csv, json, jsonl, or all)."""
        if not tweets:
            logger.warning("⚠️ No tweets to export.")
            return None

        # Sanitize query for filename
        sanitized_query = re.sub(r"[^\w\-]", "_", query_tag).strip("_")
        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        base_name = f"tweets_{sanitized_query}_{timestamp_str}"

        df = pd.DataFrame(tweets)

        # Ensure directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        primary_path: Optional[Path] = None

        if export_format in ("csv", "all"):
            csv_path = self.output_dir / f"{base_name}.csv"
            df.to_csv(csv_path, index=False, encoding="utf-8-sig")
            logger.info(f"💾 Saved CSV: {csv_path}")
            primary_path = csv_path

        if export_format in ("json", "all"):
            json_path = self.output_dir / f"{base_name}.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(tweets, f, indent=2, ensure_ascii=False)
            logger.info(f"💾 Saved JSON: {json_path}")
            if not primary_path:
                primary_path = json_path

        if export_format in ("jsonl", "all"):
            jsonl_path = self.output_dir / f"{base_name}.jsonl"
            with open(jsonl_path, "w", encoding="utf-8") as f:
                for tweet in tweets:
                    f.write(json.dumps(tweet, ensure_ascii=False) + "\n")
            logger.info(f"💾 Saved JSONL: {jsonl_path}")
            if not primary_path:
                primary_path = jsonl_path

        self._print_summary(df)
        return primary_path

    def _print_summary(self, df: pd.DataFrame) -> None:
        """Prints a rich summary of the scraped dataset."""
        print("\n" + "=" * 60)
        print(" 📊 DATASET SUMMARY")
        print("=" * 60)
        print(f" Total Tweets Scraped : {len(df)}")
        if "username" in df.columns:
            print(f" Unique Authors       : {df['username'].nunique()}")
        if "likes" in df.columns:
            print(f" Total Likes          : {df['likes'].sum():,}")
        if "retweets" in df.columns:
            print(f" Total Retweets       : {df['retweets'].sum():,}")
        if "timestamp" in df.columns and not df["timestamp"].isnull().all():
            timestamps = df["timestamp"].dropna().tolist()
            if timestamps:
                print(f" Date Coverage        : {min(timestamps)[:10]} to {max(timestamps)[:10]}")
        print("=" * 60 + "\n")
