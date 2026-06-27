# ═══════════════════════════════════════════════════════════════════════════════
# SEOOptimizer — Docker Image
#
# Build:
#   docker build -t seooptimizer .
#
# Run:
#   docker run -d -p 8501:8501 --env-file .env seooptimizer
# ═══════════════════════════════════════════════════════════════════════════════

# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN python -m nltk.downloader -d /usr/share/nltk_data \
    punkt_tab \
    punkt \
    wordnet \
    omw-1.4

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /usr/share/nltk_data /usr/share/nltk_data

ENV NLTK_DATA=/usr/share/nltk_data

RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

COPY --chown=appuser:appuser . .

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8501}/_stcore/health').read()"

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["streamlit", "run", "main.py", "--server.address=0.0.0.0", "--server.port=8501"]
