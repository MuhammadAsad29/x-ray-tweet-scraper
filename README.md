# 🐦 Live X (Twitter) Scraper & NLU Intent Pipeline

An end-to-end, polite, and resilient Twitter/X scraper designed to collect live tweets for any hashtag or keyword within a date range without official API keys. Features Dialogflow CX/ES (with local NLP fallback) for intent detection, stealth Playwright automation, human-like polite delays, and structured data export.

---

## 🌟 Key Features

1. **Natural Language Understanding (NLU)**:
   - Powered by **Google Cloud Dialogflow CX / ES** with an automatic **Local Rule-Based Fallback**.
   - Accepts prompts like:
     - *"Scrape 50 live tweets about #Python from 2025-05-01 to 2025-05-15"*
     - *"Collect 100 tweets for #Bitcoin in the last 7 days"*
     - *"Search #MachineLearning limit 30"*

2. **Stealth Playwright Automation**:
   - Overrides `navigator.webdriver`, `window.chrome`, and automation detection flags.
   - Emulates real desktop screen resolutions and modern Chrome user agents.

3. **Polite Scraping Practices**:
   - Random Gaussian delay jitter ($2.0s - 4.5s$) between scrolls to avoid server stress.
   - Natural, stepped micro-scrolling via mouse wheel emulation.
   - Exponential backoff upon empty feeds or rate-limit warnings.

4. **Robust Authentication & Session Persistence**:
   - **One-Time Headful Login**: Run `python main.py --login` to log in manually once and save your session state to `config/auth_state.json`.
   - **Cookie Injection**: Alternatively, supply `TWITTER_AUTH_TOKEN` and `TWITTER_CT0` in `.env`.

5. **Data Extraction & Clean Exporter**:
   - Extracts: `tweet_id`, `url`, `username`, `display_name`, `text`, `timestamp`, `replies`, `retweets`, `likes`, `views`, `media_urls`.
   - Exports directly to CSV, JSON, or JSON Lines with dataset summary statistics.

---

## 📁 Project Architecture

```
X_Tweets_Scrapers/
├── config/
│   ├── __init__.py
│   ├── settings.py              # Pydantic environment configuration
│   └── dialogflow_config.json    # Intent & entity schema definition
├── src/
│   ├── nlu/
│   │   ├── models.py            # ScrapeRequest data model & search query builder
│   │   ├── dialogflow_client.py # Dialogflow CX/ES integration
│   │   └── local_nlu_fallback.py# Local regex/NLP date & hashtag extractor
│   ├── core/
│   │   ├── stealth.py           # Anti-detection flags & navigator overrides
│   │   ├── polite_throttler.py  # Jitter, exponential backoff, natural scrolling
│   │   ├── session_manager.py   # Cookie persistence & interactive login
│   │   ├── parser.py            # BeautifulSoup + data-testid tweet extractor
│   │   └── scraper_engine.py    # Playwright timeline orchestration loop
│   └── storage/
│       └── exporter.py          # CSV/JSON/JSONL dataset exporter
├── tests/
│   └── test_scraper.py          # Unit test suite
├── main.py                      # Interactive CLI & prompt runner
├── requirements.txt             # Project dependencies
├── .env.example                 # Configuration template
└── README.md
```

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure Environment
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### 3. Authenticate (One-Time Setup)
Since Twitter/X requires authentication to view search timelines, save your session state once:
```bash
python main.py --login
```
*A visible browser window will open. Log into your account and press ENTER in the terminal when you reach the home feed.*

---

## 💡 Usage Examples

### Option A: Streamlit Interactive Web Dashboard (Recommended ⭐)
```bash
streamlit run app.py
```
*Launches the sleek, cyber-dark dashboard in your browser with live tweet feed cards, Plotly charts, preset prompt chips, and 1-click CSV/JSON export.*

### Option B: Natural Language Prompt CLI Mode
```bash
python main.py --prompt "Scrape top 25 tweets for #PSL2026 with min 50 likes"
```

### Option C: Interactive Prompt REPL
```bash
python main.py
```

### Option D: Direct CLI Flags
```bash
python main.py --query "#Bitcoin" --top --min-likes 100 --limit 50 --format csv
```

### Option D: Run Unit Tests
```bash
python -m unittest discover tests
```

---

## 📊 Output Schema

Scraped tweets are saved in the `output/` directory with the following fields:

| Field | Type | Description |
| :--- | :--- | :--- |
| `tweet_id` | `str` | Unique status ID (e.g. `1880000000000000000`) |
| `url` | `str` | Full permalink to the tweet on X |
| `username` | `str` | Author's handle (e.g. `@elonmusk`) |
| `display_name`| `str` | Author's display name |
| `text` | `str` | Tweet content text with emojis and links |
| `timestamp` | `str` | ISO 8601 UTC timestamp (`YYYY-MM-DDTHH:MM:SS.000Z`) |
| `replies` | `int` | Reply count |
| `retweets` | `int` | Retweet count |
| `likes` | `int` | Like count |
| `views` | `int` | View count (if available) |
| `is_retweet` | `bool` | True if the tweet is a retweet |
| `media_urls` | `list` | Image or thumbnail URLs attached to the tweet |
