import argparse
import asyncio
import logging
import sys
from typing import Optional
from config.settings import get_settings
from src.nlu.dialogflow_client import DialogflowNLUClient
from src.nlu.local_nlu_fallback import LocalNLUParser
from src.nlu.models import ScrapeRequest
from src.core.session_manager import SessionManager
from src.core.scraper_engine import TwitterScraperEngine
from src.storage.exporter import DataExporter

# Configure clean logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("TwitterScraperCLI")


def parse_arguments() -> argparse.Namespace:
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Live X (Twitter) Scraper powered by NLU (Dialogflow / Local) & Playwright with Polite Scraping Practices.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 1. One-time interactive login to save session:
  python main.py --login

  # 2. Natural language prompt scraping (parsed via Dialogflow/Local NLU):
  python main.py --prompt "Scrape 50 live tweets for #Python from 2025-05-01 to 2025-05-15"

  # 3. Direct argument scraping:
  python main.py --query "#Bitcoin" --since 2025-06-01 --until 2025-06-15 --limit 100

  # 4. Interactive Natural Language REPL:
  python main.py
        """,
    )

    parser.add_argument("--login", action="store_true", help="Launch visible browser to perform one-time manual login and save cookies")
    parser.add_argument("-p", "--prompt", type=str, help="Natural language scraping request")
    parser.add_argument("-q", "--query", "--hashtag", dest="query", type=str, help="Search query or hashtag (e.g. '#AI')")
    parser.add_argument("-s", "--since", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("-u", "--until", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("-l", "--limit", type=int, default=50, help="Maximum tweets to scrape (default: 50)")
    parser.add_argument("--lang", type=str, default="en", help="Language filter (default: en)")
    parser.add_argument("--top", action="store_true", help="Scrape Top/Highest Reach tweets instead of Latest/Live feed")
    parser.add_argument("--min-likes", type=int, default=None, help="Filter by minimum likes (e.g. 100)")
    parser.add_argument("--min-retweets", type=int, default=None, help="Filter by minimum retweets (e.g. 50)")
    parser.add_argument("--headful", action="store_true", help="Run browser visibly instead of headless")
    parser.add_argument("--format", type=str, default="csv", choices=["csv", "json", "jsonl", "all"], help="Export file format")

    return parser.parse_args()


async def run_cli():
    args = parse_arguments()
    settings = get_settings()

    if args.headful:
        settings.HEADLESS = False

    # 1. Handle Login Command
    if args.login:
        session_mgr = SessionManager()
        await session_mgr.run_interactive_login()
        return

    # 2. Determine Scrape Request Parameters
    request: Optional[ScrapeRequest] = None

    if args.prompt:
        logger.info(f"🧠 Processing natural language prompt: '{args.prompt}'")
        nlu_client = DialogflowNLUClient()
        request = nlu_client.parse_user_intent(args.prompt)

    elif args.query:
        request = ScrapeRequest(
            query=args.query,
            since=args.since,
            until=args.until,
            limit=args.limit,
            language=args.lang,
            filter_retweets=True,
            f_live=not args.top,
            min_likes=args.min_likes,
            min_retweets=args.min_retweets
        )

    else:
        # Interactive REPL mode
        print("\n" + "=" * 65)
        print(" 🐦 X (Twitter) Live Scraper & NLU Intent Interface")
        print("=" * 65)
        user_input = input("👉 Enter your scraping prompt (e.g. 'Scrape top 30 tweets for #AI with min 100 likes'): ").strip()
        if not user_input:
            print("No prompt provided. Exiting.")
            return

        nlu_client = DialogflowNLUClient()
        request = nlu_client.parse_user_intent(user_input)

    # 3. Confirm parameters with user
    tab_name = "Latest / Live Feed" if request.f_live else "Top / Highest Reach Feed"
    print("\n" + "-" * 50)
    print(" 📋 SCRAPE SPECIFICATION")
    print("-" * 50)
    print(f" Target Query   : {request.query}")
    print(f" Feed Category  : {tab_name}")
    if request.min_likes:
        print(f" Min Likes Filter: >= {request.min_likes}")
    if request.min_retweets:
        print(f" Min RT Filter  : >= {request.min_retweets}")
    print(f" Date Range     : {request.since or 'Any'} to {request.until or 'Any'}")
    print(f" Tweet Limit    : {request.limit}")
    print(f" Language       : {request.language}")
    print(f" Search URL     : {request.build_search_url()}")
    print("-" * 50 + "\n")

    # 4. Check Session Readiness
    session_mgr = SessionManager()
    if not session_mgr.has_saved_session() and not session_mgr.has_direct_cookies():
        print("⚠️ Warning: No saved session (`auth_state.json`) or `TWITTER_AUTH_TOKEN` found.")
        print("Twitter/X requires authentication to view search results.")
        print("Tip: You can run `python main.py --login` first to authenticate once.\n")

    # 5. Run Scraper Engine
    scraper = TwitterScraperEngine(settings=settings)
    tweets = await scraper.scrape(request)

    # 6. Export Results
    exporter = DataExporter()
    exporter.export(tweets, query_tag=request.query, export_format=args.format)


if __name__ == "__main__":
    try:
        asyncio.run(run_cli())
    except KeyboardInterrupt:
        print("\n🛑 Scrape cancelled by user.")
        sys.exit(0)
