"""Web search and information retrieval tools for Miguel.

Provides DuckDuckGo-based search capabilities for text, news, and more.
Enables Miguel to look up current information, research topics, and answer
questions about recent events.
"""

import json
from typing import Optional

from miguel.agent.tools.error_utils import safe_tool


@safe_tool
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo and return results.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return (default 5, max 20).

    Returns:
        Formatted search results with titles, URLs, and snippets.
    """
    from duckduckgo_search import DDGS

    max_results = min(max(1, max_results), 20)

    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))

    if not results:
        return f"No results found for: {query}"

    formatted = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "No title")
        url = r.get("href", r.get("link", "No URL"))
        snippet = r.get("body", r.get("snippet", "No snippet"))
        formatted.append(f"{i}. **{title}**\n   URL: {url}\n   {snippet}")

    return f"## Search results for: {query}\n\n" + "\n\n".join(formatted)


@safe_tool
def web_news(query: str, max_results: int = 5) -> str:
    """Search for recent news articles using DuckDuckGo.

    Args:
        query: The news search query string.
        max_results: Maximum number of results to return (default 5, max 20).

    Returns:
        Formatted news results with titles, URLs, dates, and snippets.
    """
    from duckduckgo_search import DDGS

    max_results = min(max(1, max_results), 20)

    with DDGS() as ddgs:
        results = list(ddgs.news(query, max_results=max_results))

    if not results:
        return f"No news results found for: {query}"

    formatted = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "No title")
        url = r.get("url", r.get("link", "No URL"))
        date = r.get("date", "Unknown date")
        source = r.get("source", "Unknown source")
        snippet = r.get("body", r.get("snippet", "No snippet"))
        formatted.append(
            f"{i}. **{title}**\n   Source: {source} | Date: {date}\n   URL: {url}\n   {snippet}"
        )

    return f"## News results for: {query}\n\n" + "\n\n".join(formatted)


@safe_tool
def web_search_detailed(query: str, region: str = "wt-wt", max_results: int = 10) -> str:
    """Perform a detailed web search with additional options.

    Use this for more thorough research when you need more results
    or region-specific information.

    Args:
        query: The search query string.
        region: Region code for results (default 'wt-wt' for worldwide).
                Examples: 'us-en', 'uk-en', 'de-de', 'fr-fr', 'es-es'.
        max_results: Maximum number of results (default 10, max 20).

    Returns:
        Detailed formatted search results as JSON-like structure for parsing.
    """
    from duckduckgo_search import DDGS

    max_results = min(max(1, max_results), 20)

    with DDGS() as ddgs:
        results = list(ddgs.text(query, region=region, max_results=max_results))

    if not results:
        return f"No results found for: {query} (region: {region})"

    # Return as structured JSON for easy parsing
    cleaned = []
    for r in results:
        cleaned.append({
            "title": r.get("title", ""),
            "url": r.get("href", r.get("link", "")),
            "snippet": r.get("body", r.get("snippet", "")),
        })

    return json.dumps({"query": query, "region": region, "count": len(cleaned), "results": cleaned}, indent=2)