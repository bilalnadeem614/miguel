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

    print(f"DEBUG: web_search - Query: {query}, Max Results: {max_results}") # Debug print

    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    
    print(f"DEBUG: web_search - Raw results from DDGS: {results}") # Debug print


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


import re as _re
import urllib.request as _urllib_request
import urllib.error as _urllib_error


def _extract_content(html: str, url: str) -> dict:
    """Extract readable text content from HTML.

    Uses BeautifulSoup to parse HTML, remove noise elements (scripts, styles,
    navigation, footers, etc.), and extract the main text content.

    Returns dict with 'title', 'text', 'links', and 'word_count'.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    # Extract title
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    # Extract meta description
    meta_desc = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        meta_desc = meta["content"].strip()

    # Remove noise elements
    noise_tags = [
        "script", "style", "nav", "footer", "header", "aside",
        "iframe", "noscript", "svg", "form", "button",
    ]
    for tag in soup(noise_tags):
        tag.decompose()

    # Remove common noise by class/id patterns
    noise_patterns = _re.compile(
        r"(cookie|consent|popup|modal|sidebar|advert|promo|newsletter|signup|"
        r"social[-_]?share|comment[-_]?form|related[-_]?post)",
        _re.IGNORECASE,
    )
    for el in soup.find_all(attrs={"class": noise_patterns}):
        el.decompose()
    for el in soup.find_all(attrs={"id": noise_patterns}):
        el.decompose()

    # Try to find main content area first
    main_content = (
        soup.find("main")
        or soup.find("article")
        or soup.find(attrs={"role": "main"})
        or soup.find(attrs={"id": _re.compile(r"(content|main|article)", _re.I)})
        or soup.find(attrs={"class": _re.compile(r"(content|main|article|post|entry)", _re.I)})
    )

    target = main_content if main_content else soup.body if soup.body else soup

    # Extract text
    text = target.get_text(separator="\n", strip=True)
    # Collapse excessive whitespace
    text = _re.sub(r"\n{3,}", "\n\n", text)
    text = _re.sub(r"[ \t]{2,}", " ", text)

    # Extract useful links from the content area
    links = []
    for a in target.find_all("a", href=True, limit=20):
        href = a["href"]
        link_text = a.get_text(strip=True)
        if link_text and href and not href.startswith(("#", "javascript:")):
            links.append({"text": link_text[:80], "url": href})

    word_count = len(text.split())

    return {
        "title": title,
        "description": meta_desc,
        "text": text,
        "links": links,
        "word_count": word_count,
    }


@safe_tool
def web_read(url: str, max_chars: int = 15000) -> str:
    """Fetch a webpage and extract its readable text content.

    Use this to read articles, documentation, Stack Overflow answers, blog posts,
    or any webpage. Strips HTML/JS/CSS and returns clean text.
    Pair with web_search: search first to find URLs, then web_read to get full content.

    Args:
        url: The URL to fetch and extract content from.
        max_chars: Maximum characters of content to return (default 15000, max 50000).
            Use higher values for long articles/docs, lower for quick checks.

    Returns:
        Extracted page content with title, word count, and main text.
    """
    max_chars = min(max(500, max_chars), 50000)

    # Build request with browser-like headers
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Miguel/0.2; +research-assistant)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "identity",  # Don't request compressed — simpler handling
    }
    req = _urllib_request.Request(url, headers=headers)

    try:
        with _urllib_request.urlopen(req, timeout=20) as resp:
            # Check content type
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                # For non-HTML, just return raw text if it's text-based
                if "text/" in content_type or "json" in content_type or "xml" in content_type:
                    raw = resp.read(max_chars + 1000).decode("utf-8", errors="replace")
                    truncated = len(raw) > max_chars
                    raw = raw[:max_chars]
                    result = f"## {url}\n**Type:** {content_type}\n\n{raw}"
                    if truncated:
                        result += "\n\n*[Content truncated]*"
                    return result
                else:
                    return f"Cannot extract text from {content_type} content at {url}"

            # Read HTML — limit to 2MB to avoid huge pages
            raw_bytes = resp.read(2 * 1024 * 1024)
            charset = resp.headers.get_content_charset() or "utf-8"
            html = raw_bytes.decode(charset, errors="replace")
    except _urllib_error.HTTPError as e:
        return f"HTTP {e.code} error fetching {url}: {e.reason}"
    except _urllib_error.URLError as e:
        return f"URL error fetching {url}: {e.reason}"
    except TimeoutError:
        return f"Timeout (20s) fetching {url}"

    # Extract content
    content = _extract_content(html, url)

    # Build output
    parts = [f"## {content['title'] or url}"]
    parts.append(f"**URL:** {url}")
    parts.append(f"**Words:** {content['word_count']}")
    if content["description"]:
        parts.append(f"**Description:** {content['description']}")
    parts.append("")

    # Truncate text if needed
    text = content["text"]
    truncated = False
    if len(text) > max_chars:
        # Try to truncate at a paragraph boundary
        truncation_point = text.rfind("\n\n", 0, max_chars)
        if truncation_point < max_chars * 0.5:
            truncation_point = text.rfind("\n", 0, max_chars)
        if truncation_point < max_chars * 0.5:
            truncation_point = max_chars
        text = text[:truncation_point]
        truncated = True

    parts.append(text)

    if truncated:
        remaining = content["word_count"] - len(text.split())
        parts.append(f"\n*[Truncated — ~{remaining} more words. Use max_chars={max_chars * 2} for more.]*")

    # Add key links if present
    if content["links"]:
        parts.append("\n**Key links:**")
        for link in content["links"][:10]:
            parts.append(f"- [{link['text']}]({link['url']})")

    return "\n".join(parts)