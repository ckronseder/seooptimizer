"""
Graph module for article relationship analysis.

Uses NetworkX to build a graph of articles based on shared keyword overlap,
detect communities (clusters), and rank articles by centrality.
"""

import logging
from typing import Any

logger = logging.getLogger("Graph")


def _shared_keyword_score(text_a: str, text_b: str, keywords: list[str]) -> float:
    """Compute Jaccard similarity between two article texts on the given keywords."""
    a_keywords = {kw.lower() for kw in keywords if kw.lower() in text_a.lower()}
    b_keywords = {kw.lower() for kw in keywords if kw.lower() in text_b.lower()}

    if not a_keywords and not b_keywords:
        return 0.0

    intersection = a_keywords & b_keywords
    union = a_keywords | b_keywords
    return len(intersection) / len(union)


def build_article_graph(articles: list[dict], keywords: list[str]):
    """Build a NetworkX graph where nodes are articles and edges are keyword overlap.

    Args:
        articles: List of dicts with 'url', 'text' keys.
        keywords: List of keyword strings to compute similarity on.

    Returns:
        A NetworkX Graph object.
    """
    import networkx as nx

    G = nx.Graph()

    for article in articles:
        G.add_node(article["url"], **article)

    # Add edges based on keyword overlap
    for i in range(len(articles)):
        for j in range(i + 1, len(articles)):
            score = _shared_keyword_score(
                articles[i].get("text", ""),
                articles[j].get("text", ""),
                keywords,
            )
            if score > 0:
                G.add_edge(articles[i]["url"], articles[j]["url"], weight=score)

    logger.info("Built graph with %d nodes and %d edges", G.number_of_nodes(), G.number_of_edges())
    return G


def cluster_articles(G) -> list[list[str]]:
    """Detect communities in the article graph using Louvain.

    Args:
        G: A NetworkX Graph.

    Returns:
        List of clusters, where each cluster is a list of node (URL) strings.
    """
    from networkx.algorithms.community import louvain_communities

    communities = louvain_communities(G, seed=42)
    clusters = [sorted(list(c)) for c in communities]
    logger.info("Detected %d clusters", len(clusters))
    return clusters


def rank_articles(G) -> list[tuple[str, float]]:
    """Rank articles by PageRank centrality.

    Args:
        G: A NetworkX Graph.

    Returns:
        List of (url, score) tuples sorted by score descending.
    """
    import networkx as nx

    pr = nx.pagerank(G, weight="weight")
    ranked = sorted(pr.items(), key=lambda x: x[1], reverse=True)
    return ranked


def select_top_articles(
    G, articles: list[dict], top_k: int = 6,
) -> list[dict]:
    """Select the best articles by clustering + centrality.

    1. Cluster the graph
    2. Pick the most central article(s) from each cluster
    3. Return up to top_k articles total

    Args:
        G: A NetworkX Graph.
        articles: Full list of article dicts.
        top_k: Max articles to return.

    Returns:
        List of selected article dicts.
    """
    clusters = cluster_articles(G)
    ranked = rank_articles(G)
    ranked_urls = {url for url, _ in ranked}

    selected_urls = set()

    # Pick at least one article from each cluster
    for cluster in clusters:
        # Take the highest-ranked article from this cluster
        for url, _ in ranked:
            if url in cluster and url not in selected_urls:
                selected_urls.add(url)
                break

    # Fill remaining slots with highest-ranked unselected articles
    for url, _ in ranked:
        if len(selected_urls) >= top_k:
            break
        if url not in selected_urls:
            selected_urls.add(url)

    # Return in rank order
    article_by_url = {a["url"]: a for a in articles}
    result = []
    for url, _ in ranked:
        if url in selected_urls and url in article_by_url:
            result.append(article_by_url[url])

    return result[:top_k]
