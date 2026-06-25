# SEOOptimizer — Architecture Analysis

> Analysis generated: 2026-06-25

## Overview

**SEOOptimizer** is a Streamlit-based web application that automates SEO content creation. It takes a user-provided topic, fetches related keywords via the DataForSEO API, scrapes Google News for relevant articles, and uses Google Gemini to generate SEO-optimized webpage structures.

---

## 1. System Architecture

```
User Input (Streamlit UI)
        |
        v
+---------------------+
|  DataForSEO/client  |  Fetch keyword suggestions via DataForSEO Labs API
+---------------------+
        |
        v
+---------------------------+
|  searchstring/            |  Build Google News search URLs (Jinja2)
+---------------------------+
        |
        v
+-------------------------------+
|  googlecrawler/extracturls_   |  Download Google News pages & extract article
|  threading.py                 |  URLs via regex (multi-threaded)
+-------------------------------+
        |
        v
+-------------------------------+
|  googlecrawler/crawler_       |  Download & parse full article content
|  threading.py                 |  via newspaper4k (multi-threaded)
+-------------------------------+
        |
        v
+-------------------+
|  newssummary/     |  Send articles + keywords to Google Gemini,
|  summary.py       |  receive 3 SEO-optimized JSON structures
+-------------------+
        |
        v
  Streamlit UI displays results
```

---

## 2. Module Breakdown

### 2.1 `main.py` — Application Entry Point
- **Role:** Orchestrator & Streamlit UI
- **Key functions:** `fetch_suggestions()`, `download_articles()`, `get_ai_analysis()`
- **State management:** `st.session_state` for topic, keywords, and UI flow flags
- **Caching:** `@st.cache_data` on all pipeline functions to avoid redundant API/scrape calls

### 2.2 `config/config.py` — Configuration
- **Stores:** API keys (`GEM_API`), DataForSEO credentials (`SEO_USERNAME`, `SEO_PASSWORD`), `BASE_URL`, endpoint paths
- **Issue:** Secrets hardcoded in plain text; no `.env` usage despite `python-dotenv` being installed

### 2.3 `DataForSEO/client.py` — SEO Keyword API Client
- **`RestClient`:** HTTP Basic Auth wrapper for GET/POST requests to DataForSEO
- **`extract_keywords_from_dataforseo_response()`:** Parses JSON response, extracts keyword strings
- **`consolidate_keywords()`:** NLP pipeline (lowercase → remove punctuation → lemmatize → sort → deduplicate) to normalize and merge similar keywords

### 2.4 `searchstring/searchstring.py` — URL Builder
- **`url_templating()`:** Jinja2 template renders Google News search URLs with params: `q`, `hl`, `gl`, `tbs=qdr:`

### 2.5 `googlecrawler/` — Web Scraping

| File | Purpose |
|---|---|
| `extracturls.py` | Single-threaded: download Google News pages, extract article URLs via regex |
| `extracturls_threading.py` | Multi-threaded version of above (used by `main.py`) |
| `crawler.py` | Single-threaded: download & parse article content via `newspaper4k` |
| `crawler_threading.py` | Multi-threaded version of above (used by `main.py`) |

**Key pattern:** Single-threaded variants exist as earlier drafts / debugging tools. Only threaded variants are wired into the main app.

### 2.6 `newssummary/summary.py` — LLM Content Generation
- **`summarize_text()`:** Sends concatenated article text + keyword list to `gemini-2.0-flash-lite`
- **Prompt:** Hardcoded in German, requests 3 JSON objects with title, summary, Q&A, and sources
- **`prompt.txt`:** English reference version — not programmatically loaded

### 2.7 `searchstore/storesearches.py` — Placeholder
- **State:** Stub — only `import tinydb`, no logic implemented
- **Intended purpose:** Persist search queries and/or results

---

## 3. Data Flow

```
User topic string
    → DataForSEO Labs API → keyword list (strings)
    → Jinja2 URL templates → N Google News search URLs
    → HTTP GET (threaded) → raw HTML pages
    → Regex URL extraction → article URL list
    → newspaper4k (threaded) → article dicts (title, text, authors, date, image)
    → Gemini LLM → 3 JSON SEO structures
    → Streamlit UI rendering
```

---

## 4. Technology Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.13+ |
| **Web App** | Streamlit 1.48 |
| **LLM** | Google Gemini (`gemini-2.0-flash-lite`) |
| **SEO API** | DataForSEO Labs (keyword suggestions) |
| **Scraping** | `newspaper4k`, `requests`, `beautifulsoup4` |
| **Concurrency** | `threading` (stdlib) |
| **Templating** | Jinja2 |
| **NLP** | NLTK (lemmatization, tokenization) |
| **Persistence** | TinyDB (declared, unused) |
| **Dependencies** | 204 packages in `requirements.txt` |

---

## 5. Configuration

- **File:** `config/config.py`
- **Contents:** `API_KEY`, `GEM_API`, `SEO_USERNAME`, `SEO_PASSWORD`, `BASE_URL`, `SEO_post_path`
- **Security concern:** All secrets in plain text. No `.env` support despite `python-dotenv` being installed.

---

## 6. Issues & Recommendations

### Critical
1. **Secrets exposure** — API keys and credentials in `config/config.py` should be moved to environment variables or a `.env` file.
2. **No error handling** — Pipeline failures (API timeouts, network errors, parsing failures) can crash the Streamlit app or produce silent failures.
3. **Fragile scraping** — Regex-based URL extraction from Google News HTML is brittle; Google changes page structure frequently.

### Moderate
4. **Code duplication** — Single-threaded (`extracturls.py`, `crawler.py`) and multi-threaded versions (`*_threading.py`) duplicate the same logic.
5. **Incomplete module** — `searchstore/storesearches.py` is an empty stub with only an import.
6. **No documentation** — No README, setup guide, or user documentation.
7. **Hardcoded prompt** — LLM prompt is in German and embedded in `summary.py`; the `prompt.txt` file is unused English reference.
8. **Uknonwn `API_KEY`** — A generic `API_KEY` in config is not referenced anywhere in source code. Could be dead config.

### Minor
9. **Unused dependencies** — Several packages installed (Selenium, Playwright, Crawl4AI, LiteLLM, OpenAI, boto3) but not used in source.
10. **`opencode.jsonc`** — IDE/editor config committed to the repo (low impact).

---

## 7. Suggested Improvements

- [ ] Move secrets to `.env` and use `python-dotenv`
- [ ] Add comprehensive error handling and user-facing error messages
- [ ] Remove redundant single-threaded scraping files (or merge into configurable module)
- [ ] Implement `searchstore` persistence layer
- [ ] Add README with setup and usage instructions
- [ ] Externalize prompt to a text file loaded at runtime
- [ ] Replace fragile regex URL extraction with structured parsing (e.g., BeautifulSoup on `<a>` tags)
- [ ] Audit and remove unused dependencies
