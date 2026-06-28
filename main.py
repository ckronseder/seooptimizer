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

Architecture:
  - Search UI (topic input, pills, confirm) is always rendered.
  - Pipeline runs in a background daemon thread so the UI stays responsive.
  - An auto-refreshing @st.fragment polls progress every 2 s, which keeps
    the Streamlit WebSocket alive indefinitely.
  - No state machine, no st.rerun() chains — just linear pipeline logic
    in a thread, with a shared dict for progress reporting.
"""

import hashlib
import json
import logging
import threading
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


@retry_api
def collect_articles(url_list: list) -> dict:
    """Download and parse news articles from a list of URLs (multi-threaded).

    Args:
        url_list: List of article URLs.

    Returns:
        A dict mapping URL -> parsed article data or error message.
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


# ===================== Background Pipeline Thread ==========================


def _run_pipeline_impl(
    pipeline: dict,
    search_topic: str,
    selected_words: list,
    search_id: str,
    keywords: list,
) -> None:
    """Run the full SEO pipeline in a background daemon thread.

    Writes progress / status / result / error into the shared *pipeline*
    dict.  The main thread and the ``@st.fragment`` poll this dict for
    updates — no ``st.session_state`` is accessed from this thread.

    Args:
        pipeline: A mutable dict shared with the main thread.
        search_topic: The user's original topic string.
        selected_words: The keywords the user selected from the pills.
        search_id: Hex digest computed from topic + keywords for caching.
        keywords: The full keyword list from DataForSEO.
    """
    pipe_logger = logging.getLogger("SEOOptimizer.Pipeline")
    try:
        pipeline["status"] = "Building search URLs..."
        pipeline["progress"] = 10
        url_list = create_search_urls(selected_words)

        pipeline["status"] = f"Scraping {len(url_list)} Google News pages..."
        pipeline["progress"] = 20
        google_news = googlecrawler.extracturls_threading.download_google_news_threaded(
            url_list
        )

        pipeline["status"] = "Extracting article links..."
        pipeline["progress"] = 35
        article_links = googlecrawler.extracturls_threading.extract_urls(google_news)
        if not article_links:
            raise RuntimeError("No article links found in Google News results")

        pipeline["status"] = f"Downloading {len(article_links)} articles..."
        pipeline["progress"] = 45
        all_articles = collect_articles(article_links)

        pipeline["status"] = "Storing articles in vector DB..."
        pipeline["progress"] = 60
        vectordb.store_articles(all_articles, search_id=search_id)

        pipeline["status"] = "Selecting best articles with graph analysis..."
        pipeline["progress"] = 70
        query = f"{search_topic} {' '.join(selected_words)}"
        retrieved = vectordb.query_articles(query, top_k=15)
        if retrieved:
            G = graph_builder.build_article_graph(retrieved, selected_words)
            selected = graph_builder.select_top_articles(G, retrieved, top_k=6)
        else:
            selected = [
                {"url": url, "text": data["text"], "title": data.get("title", "")}
                for url, data in all_articles.items()
                if isinstance(data, dict) and data.get("text")
            ]
        article_texts = [a.get("text", "") for a in selected if a.get("text")]

        if not article_texts:
            raise RuntimeError("No readable article texts found for AI analysis")

        pipeline["status"] = "Running AI analysis with Gemini..."
        pipeline["progress"] = 80
        companies_summary = create_sites(article_texts, keywords)

        if not companies_summary:
            raise RuntimeError("Gemini returned no website structures — "
                               "the model may have been blocked or returned empty output")

        pipeline["status"] = "Saving search history..."
        pipeline["progress"] = 95
        try:
            storesearches.save_search(
                topic=search_topic,
                keywords=selected_words,
                result=companies_summary,
            )
        except Exception:
            pipe_logger.warning("Failed to save search history", exc_info=True)

        pipeline["result"] = companies_summary
        pipeline["done"] = True
        pipeline["progress"] = 100
        pipeline["status"] = "Complete!"
        pipe_logger.info("Pipeline completed successfully for topic='%s'", search_topic)
    except Exception as exc:
        pipe_logger.exception("Pipeline failed for topic='%s'", search_topic)
        pipeline["error"] = str(exc)
        pipeline["done"] = True


# ===================== Progress Fragment (Keepalive) ======================


@st.fragment(run_every=2)
def _show_pipeline_progress() -> None:
    """Auto-refreshing fragment that reads progress from the shared dict.

    Runs every 2 seconds, which keeps the Streamlit WebSocket alive
    (resets the 55 s idle timer on each execution).
    """
    pipeline = st.session_state.get("pipeline")
    if not pipeline:
        return

    if pipeline.get("done"):
        st.rerun()  # Full re-render to show results / error
        return

    progress = pipeline.get("progress", 0)
    status = pipeline.get("status", "Working...")
    st.progress(progress / 100, text=status)


# =========================== UI Helper Functions ============================


def set_continue_flag() -> None:
    """Callback: sets a flag in session state to indicate user wants to proceed."""
    st.session_state.continue_clicked = True


# ==================== Results / Error Rendering Helpers =====================


def _render_results(companies_summary: list, search_topic: str) -> None:
    """Render the three generated website-structure cards and a download button."""
    st.markdown("#### Generated Website Structures")
    if not companies_summary:
        st.error(
            "The AI was unable to generate website structures. "
            "This may happen if articles had no readable text, the AI "
            "response was blocked, or parsing failed. Check the terminal "
            "logs for detailed debug information."
        )
        return

    cols = st.columns([1, 1], gap="large")
    for i, site in enumerate(companies_summary):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"### Website {site['website_number']}")
                st.markdown(f"**{site['title']}**")
                st.markdown(site["summary"])

                qa_df = pd.DataFrame(site["qa_list"])
                st.dataframe(qa_df, use_container_width=True, hide_index=True)

                st.markdown("**Sources:**")
                for src in site["sources"]:
                    st.markdown(f"- {src}")

    topic_slug = search_topic.lower().replace(" ", "_")
    topic_slug = "".join(c for c in topic_slug if c.isalnum() or c == "_")
    st.download_button(
        label="Download Website Structures (JSON)",
        data=json.dumps(companies_summary, indent=2, ensure_ascii=False),
        file_name=f"seo_structures_{topic_slug}.json",
        mime="application/json",
    )


def _render_error(error_msg: str) -> None:
    """Render an error panel with a restart button."""
    st.error(f"Pipeline failed: {error_msg}")
    if st.button("Start Over"):
        for key in list(st.session_state.keys()):
            if key.startswith("pipeline") or key in (
                "continue_clicked", "keywords", "selected_search_words",
                "last_search_topic",
            ):
                del st.session_state[key]
        st.rerun()


# ======================== Helper: analyze cached articles ===================


def _run_analyze_cached(
    cached_articles: list,
    search_topic: str,
    selected_words: list,
    keywords: list,
) -> list | None:
    """Run graph + Gemini on cached articles synchronously (main thread)."""
    try:
        all_articles = {a["url"]: a for a in cached_articles}
        query = f"{search_topic} {' '.join(selected_words)}"
        retrieved = vectordb.query_articles(query, top_k=15)
        if retrieved:
            G = graph_builder.build_article_graph(retrieved, selected_words)
            selected = graph_builder.select_top_articles(G, retrieved, top_k=6)
        else:
            selected = [
                {"url": url, "text": data["text"], "title": data.get("title", "")}
                for url, data in all_articles.items()
                if isinstance(data, dict) and data.get("text")
            ]
        article_texts = [a.get("text", "") for a in selected if a.get("text")]
        if not article_texts:
            logger.warning("No article texts available for cached analysis")
            return None
        return create_sites(article_texts, keywords)
    except Exception as exc:
        logger.exception("Cached analysis failed")
        return None


# ======================== Helper: save & store result =======================


def _save_and_store_result(
    companies_summary: list,
    search_topic: str,
    selected_words: list,
) -> None:
    """Persist a completed result to search history."""
    try:
        storesearches.save_search(
            topic=search_topic,
            keywords=selected_words,
            result=companies_summary,
        )
        logger.info("Search saved to history for topic='%s'", search_topic)
    except Exception as exc:
        logger.warning("Failed to save search history: %s", exc)


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

    # ── Custom CSS ──────────────────────────────────────────────────────────
    st.markdown("""
<style>
    .main-header { text-align: center; padding: 1rem 0; }
    .main-header h1 { font-size: 2.2rem; margin-bottom: 0.2rem; }
    .main-header p { color: #666; font-size: 1rem; }
    .step-badge {
        display: inline-block; background: #1E88E5; color: white;
        padding: 0.2rem 0.8rem; border-radius: 12px; font-size: 0.8rem;
        font-weight: 600; margin-right: 0.5rem;
    }
    .stContainer { border-radius: 12px !important; box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important; padding: 1.5rem !important; margin-bottom: 1rem !important; }
    .stButton button { border-radius: 8px !important; font-weight: 500 !important; }
    .stProgress > div > div { background-color: #1E88E5 !important; }
    .css-1d391kg { padding-top: 1rem !important; }
    .stAlert { border-radius: 8px !important; }
</style>
""", unsafe_allow_html=True)

    # ── Sidebar: User info & Search History ─────────────────────────────────
    with st.sidebar:
        st.markdown(f"### {st.session_state.username}")
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.username = None
            st.rerun()
        st.divider()

        st.markdown("### Search History")
        history = storesearches.get_search_history()
        if history:
            for record in history[-10:]:
                with st.expander(
                    f"**{record.get('topic', '?')}** "
                    f"({record.get('timestamp', '')[:10]})"
                ):
                    st.write(f"**Topic:** {record['topic']}")
                    st.write(f"**Keywords:** {', '.join(record.get('keywords', []))}")
                    if record.get("result"):
                        result_preview = str(record.get("result", ""))[:300]
                        st.write(f"**Result (preview):** {result_preview}...")
                    if st.button("Rerun", key=f"rerun_{record['doc_id']}"):
                        st.session_state.rerun_topic = record["topic"]
                        st.session_state.rerun_keywords = record.get("keywords", [])
                        st.session_state.rerun_auto_start = True
                        st.rerun()
                    if st.button("Delete", key=f"delete_{record['doc_id']}"):
                        storesearches.delete_search(record["doc_id"])
                        st.rerun()
        else:
            st.info("No searches yet.")

        st.divider()
        st.markdown("### Cache Settings")
        st.session_state.max_cache_hours = st.slider(
            "Max cache age (hours)",
            min_value=1,
            max_value=168,
            value=st.session_state.get("max_cache_hours", 24),
            help="Articles cached longer than this will be re-scraped",
        )

    # ── Main content ────────────────────────────────────────────────────────
    st.markdown(
        '<div class="main-header">'
        "<h1>SEO Optimizer</h1>"
        "<p>Generate SEO-optimized website structures from news articles</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.divider()

    # ── Initialise minimal session state ────────────────────────────────────
    if "continue_clicked" not in st.session_state:
        st.session_state.continue_clicked = False
    if "selected_search_words" not in st.session_state:
        st.session_state.selected_search_words = []
    if "last_search_topic" not in st.session_state:
        st.session_state.last_search_topic = None
    if "keywords" not in st.session_state:
        st.session_state.keywords = None  # None = not yet fetched
    if "rerun_topic" not in st.session_state:
        st.session_state.rerun_topic = None
    if "rerun_keywords" not in st.session_state:
        st.session_state.rerun_keywords = None
    if "rerun_auto_start" not in st.session_state:
        st.session_state.rerun_auto_start = False
    if "max_cache_hours" not in st.session_state:
        st.session_state.max_cache_hours = 24

    # ═══════════════════════════════════════════════════════════════════════
    # ALWAYS-RENDERED SEARCH UI (rendered BEFORE results so it stays at top)
    # ═══════════════════════════════════════════════════════════════════════

    # ── Handle history rerun ──────────────────────────────────────────────
    if st.session_state.get("rerun_topic"):
        search_topic = st.session_state.pop("rerun_topic")
        rerun_keywords = st.session_state.pop("rerun_keywords", [])
        st.session_state.last_search_topic = search_topic
        if rerun_keywords:
            st.session_state.selected_search_words = rerun_keywords
        st.markdown(f"**Rerunning search for:** {search_topic}")
        # Fall through to fetch keywords if needed
    else:
        st.markdown(
            '<span class="step-badge">Step 1</span> Input search topic',
            unsafe_allow_html=True,
        )
        search_topic = st.text_input(" ", key="search_topic_input")

    # ── Fetch keywords when topic changes ────────────────────────────────
    if search_topic and st.session_state.last_search_topic != search_topic:
        st.session_state.last_search_topic = search_topic
        st.session_state.selected_search_words = []
        st.session_state.continue_clicked = False
        # Clear previous pipeline results
        st.session_state.pop("pipeline", None)
        with st.spinner("Fetching keyword suggestions from DataForSEO..."):
            try:
                keywords = google_keyword_search(search_topic)
                st.session_state.keywords = keywords if keywords else []
            except Exception as exc:
                st.error(f"Keyword fetch failed: {exc}")
                st.session_state.keywords = []

    # ── Show keyword pills + confirm button ──────────────────────────────
    if st.session_state.keywords is not None:
        st.markdown(
            '<span class="step-badge">Step 2</span> Select search terms',
            unsafe_allow_html=True,
        )
        st.pills(
            "Select search words:",
            options=st.session_state.keywords,
            key="selected_search_words",
            selection_mode="multi",
        )
        st.button(
            "Confirm selection and start searching",
            on_click=set_continue_flag,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # START PIPELINE ON CONFIRM (or auto-start from history rerun)
    # ═══════════════════════════════════════════════════════════════════════

    if st.session_state.get("continue_clicked") or st.session_state.get("rerun_auto_start"):
        st.session_state.rerun_auto_start = False
        final_selection = st.session_state.selected_search_words
        if not final_selection:
            st.warning("Please select at least one keyword before continuing.")
            st.stop()

        if not search_topic:
            search_topic = st.session_state.last_search_topic

        st.markdown("---")
        st.markdown("**Processing selected keywords**")
        st.write(f"Selected words: {', '.join(final_selection)}")

        # Synchronous cache check (fast, main thread)
        search_id = vectordb.compute_search_id(search_topic, final_selection)
        cached_articles = vectordb.get_cached_articles(
            search_id,
            min_count=5,
            max_cache_hours=st.session_state.max_cache_hours,
        )

        if cached_articles:
            logger.info(
                "Cache hit: %d articles for search_id=%s",
                len(cached_articles),
                search_id,
            )
            companies_summary = _run_analyze_cached(cached_articles, search_topic, final_selection, st.session_state.keywords)
            if companies_summary:
                _save_and_store_result(companies_summary, search_topic, final_selection)
                st.session_state.pipeline = {
                    "done": True, "result": companies_summary, "error": None,
                    "progress": 100, "status": "Complete!",
                }
                st.rerun()
            else:
                st.error("Cache hit but AI analysis returned no results. "
                         "Try refreshing the cache.")
                st.stop()

        logger.info("Cache miss: starting background pipeline for search_id=%s", search_id)
        shared = {
            "progress": 0,
            "status": "Starting...",
            "done": False,
            "error": None,
            "result": None,
        }
        st.session_state.pipeline = shared
        st.session_state.continue_clicked = False

        thread = threading.Thread(
            target=_run_pipeline_impl,
            args=(
                shared,
                search_topic,
                final_selection,
                search_id,
                st.session_state.keywords,
            ),
            daemon=True,
        )
        thread.start()
        st.rerun()

    # ═══════════════════════════════════════════════════════════════════════
    # PIPELINE COMPLETION CHECK — show results / error BELOW the search UI
    # ═══════════════════════════════════════════════════════════════════════

    pipeline = st.session_state.get("pipeline")
    if pipeline and pipeline.get("done"):
        if pipeline.get("error"):
            _render_error(pipeline["error"])
        elif pipeline.get("result"):
            _render_results(
                pipeline["result"],
                st.session_state.get("last_search_topic", ""),
            )

    # ═══════════════════════════════════════════════════════════════════════
    # SHOW PIPELINE PROGRESS (auto-refreshing fragment)
    # ═══════════════════════════════════════════════════════════════════════

    pipeline = st.session_state.get("pipeline")
    if pipeline and not pipeline.get("done"):
        _show_pipeline_progress()
