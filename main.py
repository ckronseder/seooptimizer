"""
SEOOptimizer — Streamlit Application Entry Point

Orchestrates the full SEO content-generation pipeline:
  1. Fetch keyword suggestions from DataForSEO
  2. Build Google News search URLs
  3. Scrape Google News pages and extract article links (multi-threaded)
  4. Download and parse full article content (multi-threaded)
  5. Send articles to Google Gemini for SEO-optimised structures
  6. Store search history in TinyDB
  7. Display results in the Streamlit UI
"""

import hashlib
import json
import logging
from pathlib import Path

import pandas as pd
import streamlit as st
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import googlecrawler.extracturls_threading
import googlecrawler.crawler_threading
import newssummary.summary
from config import config
from searchstring import searchstring
from DataForSEO import client
from searchstore import storesearches
from vectordb import store as vectordb
from graph import builder as graph_builder
from auth import auth_ui

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("SEOOptimizer")

# ---------------------------------------------------------------------------
# Retry configuration (tenacity)
# ---------------------------------------------------------------------------
retry_api = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(
        (ConnectionError, TimeoutError, ValueError)
    ),
    reraise=True,
)

# =========================== Pipeline Functions ============================


@st.cache_data
@retry_api
def google_keyword_search(topic: str) -> list:
    """Fetch keyword suggestions from the DataForSEO API.

    Args:
        topic: The search topic string.

    Returns:
        A list of consolidated keyword strings.

    Raises:
        RuntimeError: If the API call or parsing fails after retries.
    """
    logger.info("Fetching keyword suggestions for topic='%s'", topic)
    try:
        linking = client.RestClient(config.SEO_USERNAME, config.SEO_PASSWORD)
        post_data = [
            {
                "language_code": "de",
                "location_code": 2276,  # Germany
                "keyword": topic,
                "limit": 50,
            }
        ]
        post_response = linking.post(config.SEO_post_path, post_data)
        keywords_list = client.extract_keywords_from_dataforseo_response(post_response)
        consolidated = client.consolidate_keywords(keywords_list)
        logger.info("Got %d consolidated keywords", len(consolidated))
        return consolidated
    except Exception as exc:
        logger.exception("DataForSEO keyword search failed for topic='%s'", topic)
        raise RuntimeError(
            f"Keyword search failed. Please check your DataForSEO credentials "
            f"and internet connection. Details: {exc}"
        ) from exc


@st.cache_data
def create_search_urls(search_words: list) -> list:
    """Build a list of Google News search URLs for the given keywords.

    Args:
        search_words: List of keyword strings.

    Returns:
        A list of fully-qualified Google News search URLs.
    """
    base_url = config.BASE_URL
    url_list = []
    for word in search_words:
        url_list.append(
            searchstring.url_templating(base_url, word, language="de", country="DE")
        )
        url_list.append(
            searchstring.url_templating(base_url, word)
        )
    logger.debug("Created %d search URLs", len(url_list))
    return url_list


@st.cache_data
def collect_articles(url_list: list) -> dict:
    """Download and parse news articles from a list of URLs (multi-threaded).

    Args:
        url_list: List of article URLs.

    Returns:
        A dict mapping URL → parsed article data or error message.
    """
    logger.info("Collecting articles from %d URLs", len(url_list))
    try:
        result = googlecrawler.crawler_threading.download_and_parse_article(url_list)
        logger.info("Collected %d articles", len(result))
        return result
    except Exception as exc:
        logger.exception("Article collection failed")
        raise RuntimeError(
            f"Failed to download and parse articles. Details: {exc}"
        ) from exc


@st.cache_data
@retry_api
def create_sites(text: list, search_words: list) -> list | None:
    """Generate SEO-optimised website structures via Google Gemini.

    Args:
        text: Concatenated article text.
        search_words: List of keywords to incorporate.

    Returns:
        A list of dicts (each representing a website structure), or ``None`` if
        the AI analysis failed or was blocked.
    """
    logger.info("Calling Gemini summarization")
    try:
        result = newssummary.summary.summarize_text(text, search_words)
        logger.info("Gemini summarization complete")
        return result
    except Exception as exc:
        logger.exception("Gemini summarization failed")
        raise RuntimeError(
            f"AI analysis failed. Please check your Gemini API key. Details: {exc}"
        ) from exc


# =========================== UI Helper Functions ============================


def set_continue_flag() -> None:
    """Callback: sets a flag in session state to indicate user wants to proceed."""
    st.session_state.continue_clicked = True


# =========================== Streamlit Application ===========================

if __name__ == "__main__":
    st.set_page_config(
        page_title="SEO Optimizer",
        page_icon="./favicon.ico",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    # ── Authentication ──────────────────────────────────────────────────────
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "username" not in st.session_state:
        st.session_state.username = None
    if not st.session_state.authenticated:
        username = auth_ui.show_login_page()
        if username:
            st.session_state.authenticated = True
            st.session_state.username = username
            st.rerun()
        st.stop()

    # ── Custom CSS ───────────────────────────────────────────────────────────
    st.markdown("""
<style>
    /* Main header */
    .main-header {
        text-align: center;
        padding: 1rem 0;
    }
    .main-header h1 {
        font-size: 2.2rem;
        margin-bottom: 0.2rem;
    }
    .main-header p {
        color: #666;
        font-size: 1rem;
    }
    /* Step badges */
    .step-badge {
        display: inline-block;
        background: #1E88E5;
        color: white;
        padding: 0.2rem 0.8rem;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-right: 0.5rem;
    }
    /* Result cards */
    .stContainer {
        border-radius: 12px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
        padding: 1.5rem !important;
        margin-bottom: 1rem !important;
    }
    /* Buttons */
    .stButton button {
        border-radius: 8px !important;
        font-weight: 500 !important;
    }
    /* Progress bars */
    .stProgress > div > div {
        background-color: #1E88E5 !important;
    }
    /* Sidebar */
    .css-1d391kg {
        padding-top: 1rem !important;
    }
    /* Success/Info boxes */
    .stAlert {
        border-radius: 8px !important;
    }
</style>
""", unsafe_allow_html=True)

    # ── Sidebar: User info & Search History ─────────────────────────────────
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state.username}")
        if st.button("🚪 Logout"):
            st.session_state.authenticated = False
            st.session_state.username = None
            st.rerun()
        st.divider()

        st.markdown("### Search History")
        history = storesearches.get_search_history()
        if history:
            for record in history[-10:]:  # show last 10
                with st.expander(
                    f"**{record.get('topic', '?')}** "
                    f"({record.get('timestamp', '')[:10]})"
                ):
                    st.write(f"**Topic:** {record['topic']}")
                    st.write(f"**Keywords:** {', '.join(record.get('keywords', []))}")
                    if record.get("result"):
                        result_preview = str(record.get("result", ""))[:300]
                        st.write(f"**Result (preview):** {result_preview}...")
                    if st.button("▶️ Rerun", key=f"rerun_{record['doc_id']}"):
                        st.session_state.rerun_topic = record["topic"]
                        st.session_state.rerun_keywords = record.get("keywords", [])
                        st.session_state.continue_clicked = True
                        st.session_state.last_search_topic = record["topic"]
                        st.session_state.selected_search_words = record.get("keywords", [])
                        st.rerun()
                    if st.button("🗑️ Delete", key=f"delete_{record['doc_id']}"):
                        storesearches.delete_search(record['doc_id'])
                        st.rerun()
        else:
            st.info("No searches yet.")

        st.divider()
        st.markdown("### Cache Settings")
        st.session_state.max_cache_hours = st.slider(
            "Max cache age (hours)",
            min_value=1,
            max_value=168,  # 1 week
            value=st.session_state.get("max_cache_hours", 24),
            help="Articles cached longer than this will be re-scraped",
        )

    # ── Main content ────────────────────────────────────────────────────────
    st.markdown('<div class="main-header"><h1>🔍 SEO Optimizer</h1><p>Generate SEO-optimized website structures from news articles</p></div>', unsafe_allow_html=True)
    st.divider()

    # Initialise session state
    if "continue_clicked" not in st.session_state:
        st.session_state.continue_clicked = False
    if "selected_search_words" not in st.session_state:
        st.session_state.selected_search_words = []
    if "last_search_topic" not in st.session_state:
        st.session_state.last_search_topic = None
    if "rerun_topic" not in st.session_state:
        st.session_state.rerun_topic = None
    if "rerun_keywords" not in st.session_state:
        st.session_state.rerun_keywords = None
    if "max_cache_hours" not in st.session_state:
        st.session_state.max_cache_hours = 24

    # ── Step 1: Input topic ─────────────────────────────────────────────────
    if st.session_state.rerun_topic:
        search_topic = st.session_state.rerun_topic
        st.markdown(f"**Rerunning search for:** {search_topic}")
        st.session_state.rerun_topic = None  # clear after use
    else:
        st.markdown('<span class="step-badge">Step 1</span> Input search topic', unsafe_allow_html=True)
        search_topic = st.text_input(" ")
        if not search_topic:
            st.stop()  # nothing to do

    # Reset session when topic changes
    if st.session_state.last_search_topic != search_topic:
        st.session_state.selected_search_words = []
        st.session_state.continue_clicked = False
        st.session_state.last_search_topic = search_topic

    # ── Fetch keywords ──────────────────────────────────────────────────────
    st.divider()
    try:
        with st.spinner("Fetching keyword suggestions from DataForSEO..."):
            google_keyword_list = google_keyword_search(search_topic)
        if not google_keyword_list:
            st.warning("No keyword suggestions returned. Try a different topic.")
            st.stop()
    except RuntimeError as exc:
        st.error(f"🔴 {exc}")
        logger.exception("Step 1 (keyword search) failed")
        st.stop()

    # ── Step 2: User keyword selection ──────────────────────────────────────
    st.markdown('<span class="step-badge">Step 2</span> Select search terms', unsafe_allow_html=True)
    current_selection = st.pills(
        "Select search words:",
        options=google_keyword_list,
        key="selected_search_words",
        selection_mode="multi",
    )
    st.button(
        ":grey-background[**Confirm selection and start searching**]",
        on_click=set_continue_flag,
    )

    # ── Step 3: Process ────────────────────────────────────────────────────
    if not st.session_state.continue_clicked:
        st.stop()

    st.markdown("---")
    st.markdown("**Step 3: Processing selected keywords**")

    final_selection = st.session_state.selected_search_words
    if not final_selection:
        st.warning("Please select at least one keyword before continuing.")
        st.stop()

    st.write(f"Processing with selected words: {', '.join(final_selection)}")

    # ── Check vector DB cache before scraping ────────────────────────────
    search_id = vectordb.compute_search_id(search_topic, final_selection)
    cached_articles = vectordb.get_cached_articles(
        search_id,
        min_count=5,
        max_cache_hours=st.session_state.max_cache_hours,
    )

    if cached_articles:
        st.toast(
            f"Using {len(cached_articles)} cached articles from previous run",
            icon="📦",
        )
        logger.info(
            "Cache hit: using %d cached articles for search_id=%s",
            len(cached_articles),
            search_id,
        )
        all_articles = {a["url"]: a for a in cached_articles}
        # Skip steps 3a-3c, go directly to Gemini
    else:
        st.toast("No cached articles found, scraping fresh", icon="🕸️")
        logger.info(
            "Cache miss: scraping fresh articles for search_id=%s", search_id
        )

    if not cached_articles:
        # ── 3a. Build URLs ─────────────────────────────────────────────────
        try:
            url_list = create_search_urls(final_selection)
        except Exception as exc:
            st.error(f"🔴 Failed to build search URLs: {exc}")
            logger.exception("Step 3a (URL building) failed")
            st.stop()

        # ── 3b. Extract article links from Google News ──────────────────────────
        progress_bar_extract = st.progress(0, text="Starting download...")
        status_text_extract = st.empty()
        try:
            with st.spinner(
                "Downloading and extracting URLs from Google News... "
                "This may take a moment."
            ):
                status_text_extract.text(
                    f"Downloading {len(url_list)} Google search pages..."
                )
                google_news = (
                    googlecrawler.extracturls_threading.download_google_news_threaded(
                        url_list
                    )
                )
                progress_bar_extract.progress(
                    70, text="Downloaded pages. Now extracting article links..."
                )
                article_links = googlecrawler.extracturls_threading.extract_urls(
                    google_news
                )
                progress_bar_extract.progress(
                    100, text="Google News link extraction complete!"
                )
                status_text_extract.text("Google News link extraction complete!")
        except Exception as exc:
            st.error(f"🔴 Failed to extract article links: {exc}")
            logger.exception("Step 3b (link extraction) failed")
            st.stop()
        finally:
            progress_bar_extract.empty()
            status_text_extract.empty()

        st.toast(f"Found {len(article_links)} article links", icon="🔗")

        # ── 3c. Download and parse articles ─────────────────────────────────────
        progress_bar_collect = st.progress(0, text="Starting article collection...")
        status_text_collect = st.empty()
        try:
            with st.spinner(
                "Collecting and parsing articles... "
                "This can take some time based on the number of links."
            ):
                status_text_collect.text(
                    f"Downloading and parsing {len(article_links)} articles..."
                )
                all_articles = collect_articles(article_links)
                progress_bar_collect.progress(100, text="Article collection complete!")
                status_text_collect.text("Article collection complete!")
        except Exception as exc:
            st.error(f"🔴 Failed to collect articles: {exc}")
            logger.exception("Step 3c (article collection) failed")
            st.stop()
        finally:
            progress_bar_collect.empty()
            status_text_collect.empty()

        st.toast("Articles collected", icon="📰")

    # ── Store articles in vector DB (only if freshly scraped) ──────────────
    if not cached_articles:
        try:
            stored = vectordb.store_articles(all_articles, search_id=search_id)
            logger.info("Stored %d articles in vector DB", stored)
        except Exception as exc:
            logger.warning("Failed to store articles in vector DB: %s", exc)

    # ── 3d. Retrieve, rank, and generate ─────────────────────────────────
    progress_bar_ai = st.progress(0, text="Analyzing content...")
    status_text_ai = st.empty()
    try:
        with st.spinner("Analyzing content with AI..."):
            status_text_ai.text("Selecting best articles...")

            # Build query from topic and keywords
            query = f"{search_topic} {' '.join(final_selection)}"

            # Retrieve relevant articles from vector DB
            retrieved = vectordb.query_articles(query, top_k=15)

            if retrieved:
                # Build graph and select top articles
                G = graph_builder.build_article_graph(retrieved, final_selection)
                selected = graph_builder.select_top_articles(G, retrieved, top_k=6)
                logger.info("Selected %d articles via graph ranking", len(selected))
            else:
                # Fallback: use all articles directly
                selected = [
                    {"url": url, "text": data["text"], "title": data.get("title", "")}
                    for url, data in all_articles.items()
                    if isinstance(data, dict) and data.get("text")
                ]

            # Extract text for Gemini
            article_texts = [a.get("text", "") for a in selected if a.get("text")]

            if not article_texts:
                logger.warning(
                    "No article texts available for Gemini — "
                    "all articles had empty text"
                )
            else:
                logger.info(
                    "Passing %d article texts to Gemini. "
                    "First article preview: %.200s...",
                    len(article_texts),
                    article_texts[0],
                )

            status_text_ai.text("Running AI analysis...")
            companies_summary = create_sites(article_texts, google_keyword_list)

            if not companies_summary:
                logger.warning(
                    "Gemini returned None/empty for %d article texts. "
                    "Check summarize_text logs for detailed debug info.",
                    len(article_texts),
                )
            progress_bar_ai.progress(100, text="Analysis complete!")
            status_text_ai.text("Analysis complete!")
    except Exception as exc:
        st.error(f"🔴 AI analysis failed: {exc}")
        logger.exception("Step 3d (Gemini summarization) failed")
        st.stop()
    finally:
        progress_bar_ai.empty()
        status_text_ai.empty()

    st.toast("Analysis complete!", icon="✅")

    # ── Display results ────────────────────────────────────────────────────
    st.markdown("#### Generated Website Structures")

    if not companies_summary:
        st.error(
            "🔴 The AI was unable to generate website structures. "
            "This may happen if articles had no readable text, the AI "
            "response was blocked, or parsing failed. Check the terminal "
            "logs for detailed debug information."
        )
    else:
        cols = st.columns([1, 1], gap="large")
        for i, site in enumerate(companies_summary):
            with cols[i % 2]:
                with st.container(border=True):
                    st.markdown(f"### 🌐 Website {site['website_number']}")
                    st.markdown(f"**{site['title']}**")
                    st.markdown(site['summary'])

                    qa_df = pd.DataFrame(site["qa_list"])
                    st.dataframe(qa_df, use_container_width=True, hide_index=True)

                    st.markdown("**📎 Sources:**")
                    for src in site['sources']:
                        st.markdown(f"- {src}")

        # ── Download button ────────────────────────────────────────────────
        topic_slug = search_topic.lower().replace(' ', '_')
        topic_slug = ''.join(c for c in topic_slug if c.isalnum() or c == '_')

        st.download_button(
            label="📥 Download Website Structures (JSON)",
            data=json.dumps(companies_summary, indent=2, ensure_ascii=False),
            file_name=f"seo_structures_{topic_slug}.json",
            mime="application/json",
        )

    # ── Persist search to history ───────────────────────────────────────────
    try:
        storesearches.save_search(
            topic=search_topic,
            keywords=final_selection,
            result=companies_summary,
        )
        logger.info("Search saved to history for topic='%s'", search_topic)
    except Exception as exc:
        logger.warning("Failed to save search history: %s", exc)

    # Reset flag so next run waits for button again
    st.session_state.continue_clicked = False
