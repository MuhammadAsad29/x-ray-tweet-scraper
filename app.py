import asyncio
import json
import logging
import random
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import pandas as pd
import streamlit as st

try:
    import plotly.express as px
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

import os
import subprocess
from config.settings import get_settings
from src.core.scraper_engine import TwitterScraperEngine
from src.core.session_manager import SessionManager
from src.nlu.dialogflow_client import DialogflowNLUClient
from src.nlu.local_nlu_fallback import LocalNLUParser
from src.nlu.models import ScrapeRequest

@st.cache_resource
def ensure_playwright_browsers():
    """Ensures Chromium binaries are installed on cloud deployment platforms."""
    try:
        subprocess.run(["playwright", "install", "chromium"], check=False)
    except Exception:
        pass

ensure_playwright_browsers()

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & THEME
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="X-Ray | Smart Twitter & NLU Scraper",
    page_icon="🐦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------------------------------------------------------
# 2. CUSTOM CSS (Cyber-Minimalist / Premium Dark Glassmorphism)
# -----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }

    /* Gradient Hero Title */
    .hero-title {
        font-size: 2.75rem;
        font-weight: 800;
        background: linear-gradient(135deg, #1DA1F2 0%, #a855f7 50%, #06b6d4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
        letter-spacing: -0.03em;
    }

    .hero-subtitle {
        font-size: 1.1rem;
        color: #94a3b8;
        margin-bottom: 1.5rem;
        font-weight: 400;
    }

    /* Glassmorphism Metric Cards */
    .metric-card {
        background: rgba(22, 27, 34, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        backdrop-filter: blur(8px);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-3px);
        border-color: rgba(29, 161, 242, 0.4);
    }
    .metric-value {
        font-size: 1.9rem;
        font-weight: 700;
        color: #f8fafc;
        margin-top: 4px;
    }
    .metric-label {
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #64748b;
        font-weight: 600;
    }

    /* Tweet Cards */
    .tweet-container {
        background: rgba(15, 23, 42, 0.65);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 14px;
        padding: 18px 22px;
        margin-bottom: 14px;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .tweet-container:hover {
        border-color: rgba(29, 161, 242, 0.5);
        box-shadow: 0 4px 20px -2px rgba(29, 161, 242, 0.2);
        transform: scale(1.005);
    }
    .tweet-author {
        font-weight: 700;
        color: #f1f5f9;
        font-size: 1.05rem;
    }
    .tweet-handle {
        color: #1DA1F2;
        font-size: 0.9rem;
        font-weight: 500;
        margin-left: 6px;
    }
    .tweet-text {
        font-size: 0.98rem;
        color: #e2e8f0;
        line-height: 1.55;
        margin: 10px 0 12px 0;
    }
    .tweet-meta {
        font-size: 0.82rem;
        color: #64748b;
        display: flex;
        gap: 18px;
        align-items: center;
    }
    .badge-pill {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        background: rgba(29, 161, 242, 0.15);
        color: #38bdf8;
        border: 1px solid rgba(56, 189, 248, 0.3);
    }

    /* Witty Tips Box */
    .witty-box {
        background: linear-gradient(135deg, rgba(168, 85, 247, 0.1) 0%, rgba(6, 182, 212, 0.1) 100%);
        border-left: 4px solid #a855f7;
        padding: 12px 16px;
        border-radius: 8px;
        margin: 15px 0;
        font-size: 0.9rem;
        color: #cbd5e1;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# 3. WITTY QUOTES REPOSITORY
# -----------------------------------------------------------------------------
WITTY_QUOTES = [
    "💸 API Subscription: $0.00 / month. Thanks to open-source browser magic!",
    "🤫 Sneaking past Twitter's rate limits like a ninja in socks...",
    "☕ Scrolling with polite human-like delays so the server thinks we're sipping chai.",
    "🤖 Dialogflow NLU: Translating your casual thoughts into precise X search queries.",
    "🚀 Elon may charge $100 for API access, but Playwright runs for free.",
    "🧠 Brain over brute force: Jitter delays prevent sudden account restrictions.",
]

# -----------------------------------------------------------------------------
# 4. INITIALIZE SESSION STATE
# -----------------------------------------------------------------------------
if "scraped_df" not in st.session_state:
    st.session_state["scraped_df"] = None
if "last_query" not in st.session_state:
    st.session_state["last_query"] = ""
if "active_request" not in st.session_state:
    st.session_state["active_request"] = None

settings = get_settings()
custom_auth = st.session_state.get("custom_auth_token", "")
custom_ct0 = st.session_state.get("custom_ct0", "")

if custom_auth:
    settings.TWITTER_AUTH_TOKEN = custom_auth
    if custom_ct0:
        settings.TWITTER_CT0 = custom_ct0

session_mgr = SessionManager(settings=settings)

# -----------------------------------------------------------------------------
# 5. SIDEBAR: STATUS & CONFIGURATION
# -----------------------------------------------------------------------------
with st.sidebar:
    st.image("https://img.icons8.com/color/96/twitter--v1.png", width=64)
    st.title("🎛️ Scraper Cockpit")

    # Session Status Indicator
    has_session = session_mgr.has_saved_session() or session_mgr.has_direct_cookies()
    if has_session:
        st.success("🟢 Authenticated Session Active")
        if session_mgr.has_direct_cookies():
            st.caption("🔑 Cookies loaded (`auth_token` / `ct0`)")
        else:
            st.caption("💾 Storage state loaded from `auth_state.json`")
    else:
        st.warning("🟡 Guest / Unauthenticated Mode")
        st.caption("Configure `.env`, add secrets on Streamlit Cloud, or paste cookies below.")

    with st.expander("🔑 Session & Cookie Settings", expanded=not has_session):
        st.caption("For cloud demo testing, paste your X session cookies:")
        user_auth_token = st.text_input("auth_token", value=custom_auth, type="password", help="X auth_token cookie value")
        user_ct0 = st.text_input("ct0 (CSRF token)", value=custom_ct0, type="password", help="X ct0 cookie value")
        if user_auth_token != custom_auth or user_ct0 != custom_ct0:
            st.session_state["custom_auth_token"] = user_auth_token
            st.session_state["custom_ct0"] = user_ct0
            st.rerun()

    st.markdown("---")

    # Politeness Controls
    st.subheader("🛡️ Polite Throttling")
    min_delay = st.slider("Min Scroll Delay (s)", 1.0, 5.0, float(settings.MIN_SCROLL_DELAY), 0.5)
    max_delay = st.slider("Max Scroll Delay (s)", 2.0, 8.0, float(settings.MAX_SCROLL_DELAY), 0.5)
    st.caption("⏳ Adds random Gaussian jitter to mimic natural user browsing.")

    st.markdown("---")

    # Witty Quote Widget
    st.markdown(f'<div class="witty-box">💡 <i>"{random.choice(WITTY_QUOTES)}"</i></div>', unsafe_allow_html=True)

    st.markdown("---")
    st.caption("Built with Playwright • BeautifulSoup • Dialogflow NLU • Streamlit")


# -----------------------------------------------------------------------------
# 6. HERO SECTION
# -----------------------------------------------------------------------------
st.markdown('<div class="hero-title">🐦 X-Ray: Smart Tweet Scraper</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-subtitle">'
    'Scrape live & viral tweets without paying Elon\'s API rent. '
    'Powered by <b>Natural Language Intent Detection</b> and <b>Stealth Browser Automation</b>.'
    '</div>',
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# 7. SEARCH & INTENT CAPTURE (MODE SWITCHER)
# -----------------------------------------------------------------------------
search_mode = st.radio(
    "Select Search Mode",
    ["🧠 Natural Language (AI / NLU Mode)", "🎛️ Precision Filter Controls"],
    horizontal=True,
    label_visibility="collapsed"
)

scrape_request: Optional[ScrapeRequest] = None

if "nl_prompt" not in st.session_state:
    st.session_state["nl_prompt"] = "top 10 latest tweets for #web3.0 with min 70 likes"

if search_mode == "🧠 Natural Language (AI / NLU Mode)":
    st.markdown("##### 💬 Tell X-Ray what you want in plain English or Urdu/Roman Urdu:")

    # Quick Preset Chips
    col_chip1, col_chip2, col_chip3, col_chip4 = st.columns(4)
    if col_chip1.button("🏏 #PSL2026 Viral (Min 50 Likes)", use_container_width=True):
        st.session_state["nl_prompt"] = "Scrape top 25 tweets for #PSL2026 with min 50 likes"
        st.rerun()
    if col_chip2.button("🤖 #AI & Tech News", use_container_width=True):
        st.session_state["nl_prompt"] = "Scrape 30 live tweets about #ArtificialIntelligence"
        st.rerun()
    if col_chip3.button("📈 #Bitcoin / Crypto Surge", use_container_width=True):
        st.session_state["nl_prompt"] = "Collect top 20 tweets for #Bitcoin with min 100 likes"
        st.rerun()
    if col_chip4.button("🌐 #web3.0 Trends", use_container_width=True):
        st.session_state["nl_prompt"] = "top 10 latest tweets for #web3.0 with min 70 likes"
        st.rerun()

    user_prompt = st.text_input(
        "Natural Language Prompt",
        value=st.session_state["nl_prompt"],
        placeholder="e.g. top 10 latest tweets for #web3.0 with min 70 likes",
        label_visibility="collapsed",
    )
    st.session_state["nl_prompt"] = user_prompt

    if user_prompt:
        nlu_client = DialogflowNLUClient()
        scrape_request = nlu_client.parse_user_intent(user_prompt)

else:
    st.markdown("##### 🎯 Manually tune your query and threshold filters:")
    col_m1, col_m2, col_m3 = st.columns([2, 1, 1])

    with col_m1:
        manual_query = st.text_input("Hashtag or Keywords", value="#web3.0")
    with col_m2:
        feed_type = st.selectbox("Feed Category", ["🔥 Top / Viral Tweets", "⚡ Live / Latest Stream"])
    with col_m3:
        manual_limit = st.number_input("Tweet Limit", min_value=5, max_value=500, value=10, step=5)

    col_d1, col_d2, col_d3, col_d4 = st.columns(4)
    with col_d1:
        manual_since = st.date_input("Start Date (Optional)", value=None)
    with col_d2:
        manual_until = st.date_input("End Date (Optional)", value=None)
    with col_d3:
        manual_min_likes = st.number_input("Min Likes (0 for any)", min_value=0, value=70, step=10)
    with col_d4:
        manual_min_rts = st.number_input("Min Retweets (0 for any)", min_value=0, value=0, step=5)

    scrape_request = ScrapeRequest(
        query=manual_query,
        since=manual_since.isoformat() if manual_since else None,
        until=manual_until.isoformat() if manual_until else None,
        limit=manual_limit,
        filter_retweets=True,
        f_live=False if "Top" in feed_type else True,
        min_likes=manual_min_likes if manual_min_likes > 0 else None,
        min_retweets=manual_min_rts if manual_min_rts > 0 else None,
    )

# -----------------------------------------------------------------------------
# 8. INTENT SPECIFICATION PREVIEW & LAUNCH BUTTON
# -----------------------------------------------------------------------------
if scrape_request:
    st.markdown("---")
    col_spec1, col_spec2, col_spec3, col_spec4 = st.columns(4)

    with col_spec1:
        st.markdown(f"**🎯 Target Query:** `{scrape_request.query}`")
    with col_spec2:
        feed_label = "⚡ Latest / Live Feed" if scrape_request.f_live else "🔥 Top / Highest Reach"
        st.markdown(f"**📑 Tab Target:** `{feed_label}`")
    with col_spec3:
        eng_label = []
        if scrape_request.min_likes:
            eng_label.append(f"❤️ ≥{scrape_request.min_likes}")
        if scrape_request.min_retweets:
            eng_label.append(f"🔁 ≥{scrape_request.min_retweets}")
        st.markdown(f"**⚡ Filter Threshold:** `{', '.join(eng_label) if eng_label else 'None'}`")
    with col_spec4:
        st.markdown(f"**📊 Max Target:** `{scrape_request.limit} tweets`")

    # Launch Button
    col_btn, col_hint = st.columns([1, 3])
    with col_btn:
        start_scrape = st.button("🚀 Launch X-Ray Scraper", type="primary", use_container_width=True)
    with col_hint:
        st.caption(f"🔗 **Constructed X URL:** `{scrape_request.build_search_url()}`")

    # -------------------------------------------------------------------------
    # 9. SCRAPING EXECUTION ENGINE
    # -------------------------------------------------------------------------
    if start_scrape:
        with st.status("🕵️ X-Ray Scraper In Action...", expanded=True) as status:
            st.write("⚙️ Initializing stealth browser context...")
            time.sleep(0.5)

            st.write(f"🌐 Navigating to search stream for `{scrape_request.query}`...")

            # Run Async Scraper Engine
            engine = TwitterScraperEngine(settings=settings)
            engine.throttler.min_delay = min_delay
            engine.throttler.max_delay = max_delay

            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                tweets = loop.run_until_complete(engine.scrape(scrape_request))
                loop.close()

                if tweets:
                    df = pd.DataFrame(tweets)
                    st.session_state["scraped_df"] = df
                    st.session_state["last_query"] = scrape_request.query
                    status.update(label=f"✅ Successfully scraped {len(df)} tweets!", state="complete", expanded=False)
                    st.balloons()
                else:
                    status.update(label="⚠️ Scraping ended with 0 tweets. Check your cookies or try broadening query.", state="error")
            except Exception as e:
                status.update(label=f"❌ Scraper error: {e}", state="error")


# -----------------------------------------------------------------------------
# 10. RESULTS, METRICS & VISUAL ANALYTICS DASHBOARD
# -----------------------------------------------------------------------------
if st.session_state["scraped_df"] is not None and not st.session_state["scraped_df"].empty:
    df = st.session_state["scraped_df"]

    st.markdown("---")
    st.subheader(f"📊 Scraped Intelligence: `{st.session_state['last_query']}`")

    # Top KPI Metrics Cards
    m1, m2, m3, m4 = st.columns(4)

    total_likes = int(df["likes"].sum()) if "likes" in df.columns else 0
    total_rts = int(df["retweets"].sum()) if "retweets" in df.columns else 0
    unique_authors = int(df["username"].nunique()) if "username" in df.columns else 0
    avg_likes = int(df["likes"].mean()) if "likes" in df.columns else 0

    with m1:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Total Tweets</div><div class="metric-value">📬 {len(df):,}</div></div>',
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Unique Voices</div><div class="metric-value">👥 {unique_authors:,}</div></div>',
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Total Engagement</div><div class="metric-value">🔥 {total_likes + total_rts:,}</div></div>',
            unsafe_allow_html=True,
        )
    with m4:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Avg Likes / Tweet</div><div class="metric-value">❤️ {avg_likes:,}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # 11. TABS: FEED CARDS vs CHARTS vs RAW DATA
    # -------------------------------------------------------------------------
    tab_cards, tab_charts, tab_table = st.tabs(["📱 Live Tweet Cards", "📈 Visual Analytics & Insights", "🗃️ Raw Data Table"])

    # TAB 1: TWEET CARDS
    with tab_cards:
        for idx, row in df.iterrows():
            author = row.get("display_name", "User")
            handle = row.get("username", "@user")
            text = row.get("text", "")
            ts = row.get("timestamp", "")
            likes = row.get("likes", 0)
            rts = row.get("retweets", 0)
            replies = row.get("replies", 0)
            url = row.get("url", "https://x.com")

            time_display = ts[:10] + " " + ts[11:16] if ts and len(ts) >= 16 else "Recent"

            st.markdown(
                f"""
                <div class="tweet-container">
                    <div>
                        <span class="tweet-author">{author}</span>
                        <span class="tweet-handle">{handle}</span>
                        <span style="float: right;" class="badge-pill">📅 {time_display}</span>
                    </div>
                    <div class="tweet-text">{text}</div>
                    <div class="tweet-meta">
                        <span>💬 <b>{replies:,}</b> replies</span>
                        <span>🔁 <b>{rts:,}</b> retweets</span>
                        <span>❤️ <b>{likes:,}</b> likes</span>
                        <a href="{url}" target="_blank" style="margin-left: auto; text-decoration: none; color: #38bdf8; font-weight: 600;">🔗 View on X →</a>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # TAB 2: VISUAL ANALYTICS
    with tab_charts:
        col_c1, col_c2 = st.columns(2)

        with col_c1:
            st.markdown("##### 🏆 Top Most Liked Tweets")
            top_liked = df.sort_values(by="likes", ascending=False).head(8)
            if HAS_PLOTLY:
                fig_bar = px.bar(
                    top_liked,
                    x="likes",
                    y="username",
                    orientation="h",
                    color="likes",
                    color_continuous_scale="Viridis",
                    hover_data=["text"],
                    labels={"likes": "Likes Count", "username": "Author Handle"},
                )
                fig_bar.update_layout(yaxis={"categoryorder": "total ascending"}, template="plotly_dark", height=380)
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.bar_chart(top_liked.set_index("username")["likes"])

        with col_c2:
            st.markdown("##### ⚡ Likes vs. Retweets Engagement Distribution")
            if HAS_PLOTLY:
                fig_scatter = px.scatter(
                    df,
                    x="likes",
                    y="retweets",
                    size="likes",
                    color="username",
                    hover_data=["text"],
                    labels={"likes": "Likes", "retweets": "Retweets"},
                )
                fig_scatter.update_layout(template="plotly_dark", height=380, showlegend=False)
                st.plotly_chart(fig_scatter, use_container_width=True)
            else:
                st.scatter_chart(df[["likes", "retweets"]])

    # TAB 3: RAW TABLE VIEW
    with tab_table:
        st.dataframe(df, use_container_width=True, height=450)

    # -------------------------------------------------------------------------
    # 12. 1-CLICK EXPORT SUITE
    # -------------------------------------------------------------------------
    st.markdown("---")
    st.subheader("💾 Export Intelligence Suite")
    col_exp1, col_exp2 = st.columns(2)

    csv_data = df.to_csv(index=False, encoding="utf-8-sig")
    json_data = df.to_json(orient="records", indent=2, force_ascii=False)
    timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    with col_exp1:
        st.download_button(
            label="📥 Download Dataset as CSV",
            data=csv_data,
            file_name=f"xray_tweets_{timestamp_str}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col_exp2:
        st.download_button(
            label="📥 Download Dataset as JSON",
            data=json_data,
            file_name=f"xray_tweets_{timestamp_str}.json",
            mime="application/json",
            use_container_width=True,
        )
