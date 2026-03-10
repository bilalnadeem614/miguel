"""Reddit integration tools for Miguel.

Provides browsing, posting, commenting, and searching on Reddit via
the official Reddit API with OAuth2 authentication.

Credentials are read from environment variables:
  REDDIT_CLIENT_ID     — OAuth2 app client ID
  REDDIT_CLIENT_SECRET — OAuth2 app client secret
  REDDIT_USERNAME      — Reddit account username
  REDDIT_PASSWORD      — Reddit account password

To create credentials: https://www.reddit.com/prefs/apps
  → Create a "script" type application
  → Use http://localhost:8080 as the redirect URI

All tools gracefully handle missing credentials with clear setup instructions.
"""

import json
import os
import time
from typing import Optional

from miguel.agent.tools.error_utils import safe_tool

# --- Auth & HTTP layer ---

_token_cache: dict = {"access_token": None, "expires_at": 0.0}

USER_AGENT = "Miguel-AI-Agent/1.0 (by /u/miguel-agent)"


def _get_credentials() -> dict:
    """Load Reddit credentials from environment variables."""
    creds = {
        "client_id": os.environ.get("REDDIT_CLIENT_ID", ""),
        "client_secret": os.environ.get("REDDIT_CLIENT_SECRET", ""),
        "username": os.environ.get("REDDIT_USERNAME", ""),
        "password": os.environ.get("REDDIT_PASSWORD", ""),
    }
    missing = [k for k, v in creds.items() if not v]
    if missing:
        env_names = {
            "client_id": "REDDIT_CLIENT_ID",
            "client_secret": "REDDIT_CLIENT_SECRET",
            "username": "REDDIT_USERNAME",
            "password": "REDDIT_PASSWORD",
        }
        missing_envs = [env_names[k] for k in missing]
        raise EnvironmentError(
            f"Missing Reddit credentials: {', '.join(missing_envs)}.\n"
            "Set these environment variables to enable Reddit integration.\n"
            "Create an app at https://www.reddit.com/prefs/apps (type: script)."
        )
    return creds


def _get_access_token() -> str:
    """Get a valid OAuth2 access token, refreshing if expired."""
    import urllib.request
    import base64

    now = time.time()
    if _token_cache["access_token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["access_token"]

    creds = _get_credentials()
    auth_str = base64.b64encode(
        f"{creds['client_id']}:{creds['client_secret']}".encode()
    ).decode()

    data = (
        f"grant_type=password"
        f"&username={creds['username']}"
        f"&password={creds['password']}"
    ).encode()

    req = urllib.request.Request(
        "https://www.reddit.com/api/v1/access_token",
        data=data,
        headers={
            "Authorization": f"Basic {auth_str}",
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode())

    if "access_token" not in result:
        raise RuntimeError(f"Reddit auth failed: {result.get('error', result)}")

    _token_cache["access_token"] = result["access_token"]
    _token_cache["expires_at"] = now + result.get("expires_in", 3600)
    return result["access_token"]


def _reddit_request(
    endpoint: str,
    method: str = "GET",
    data: Optional[dict] = None,
    params: Optional[dict] = None,
) -> dict:
    """Make an authenticated request to Reddit's OAuth API."""
    import urllib.request
    import urllib.parse

    token = _get_access_token()
    base_url = "https://oauth.reddit.com"
    url = f"{base_url}{endpoint}"

    if params:
        url += "?" + urllib.parse.urlencode(params)

    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode()

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": USER_AGENT,
        },
        method=method,
    )
    if body:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


# --- Formatting helpers ---


def _format_post(post: dict, include_body: bool = False) -> str:
    """Format a Reddit post for display."""
    d = post.get("data", post)
    lines = [
        f"**{d.get('title', 'No title')}**",
        f"  r/{d.get('subreddit', '?')} · u/{d.get('author', '?')} · "
        f"⬆ {d.get('score', 0)} · 💬 {d.get('num_comments', 0)} comments",
        f"  🔗 https://reddit.com{d.get('permalink', '')}",
    ]
    if include_body and d.get("selftext"):
        body = d["selftext"][:500]
        if len(d["selftext"]) > 500:
            body += "..."
        lines.append(f"  > {body}")
    if d.get("url") and not d.get("is_self"):
        lines.append(f"  Link: {d['url']}")
    return "\n".join(lines)


def _format_comment(comment: dict, depth: int = 0) -> str:
    """Format a Reddit comment for display."""
    d = comment.get("data", comment)
    indent = "  " * depth
    body = (d.get("body") or "")[:300]
    if len(d.get("body", "")) > 300:
        body += "..."
    return (
        f"{indent}**u/{d.get('author', '?')}** · ⬆ {d.get('score', 0)}\n"
        f"{indent}  {body}"
    )


# --- Public tools ---


@safe_tool
def reddit_browse(subreddit: str, sort: str = "hot", limit: int = 10) -> str:
    """Browse posts in a subreddit.

    Args:
        subreddit: Subreddit name without the r/ prefix (e.g. 'python', 'machinelearning').
        sort: Sort order — 'hot', 'new', 'top', 'rising'. Default: 'hot'.
        limit: Number of posts to return (1-25). Default: 10.
    """
    limit = max(1, min(25, limit))
    sort = sort if sort in ("hot", "new", "top", "rising") else "hot"

    result = _reddit_request(
        f"/r/{subreddit}/{sort}",
        params={"limit": str(limit)},
    )

    posts = result.get("data", {}).get("children", [])
    if not posts:
        return f"No posts found in r/{subreddit} ({sort})."

    lines = [f"## r/{subreddit} — {sort} ({len(posts)} posts)\n"]
    for i, post in enumerate(posts, 1):
        lines.append(f"{i}. {_format_post(post)}")
    return "\n\n".join(lines)


@safe_tool
def reddit_read(post_url_or_id: str, comment_limit: int = 10) -> str:
    """Read a Reddit post and its top comments.

    Args:
        post_url_or_id: A Reddit post URL or post ID (e.g. 't3_abc123' or full URL).
        comment_limit: Number of top comments to show (1-25). Default: 10.
    """
    comment_limit = max(1, min(25, comment_limit))

    # Parse URL or ID to get the API endpoint
    url_or_id = post_url_or_id.strip()
    if "reddit.com" in url_or_id:
        # Extract path from URL
        import urllib.parse
        parsed = urllib.parse.urlparse(url_or_id)
        path = parsed.path.rstrip("/")
        if not path.startswith("/r/"):
            return "Invalid Reddit URL. Expected format: https://reddit.com/r/subreddit/comments/id/title"
        endpoint = path
    elif url_or_id.startswith("t3_"):
        # Fetch post info to get the permalink
        info = _reddit_request("/api/info", params={"id": url_or_id})
        children = info.get("data", {}).get("children", [])
        if not children:
            return f"Post not found: {url_or_id}"
        endpoint = children[0]["data"]["permalink"].rstrip("/")
    else:
        # Assume it's a bare ID
        info = _reddit_request("/api/info", params={"id": f"t3_{url_or_id}"})
        children = info.get("data", {}).get("children", [])
        if not children:
            return f"Post not found: {url_or_id}"
        endpoint = children[0]["data"]["permalink"].rstrip("/")

    result = _reddit_request(endpoint, params={"limit": str(comment_limit)})

    if not isinstance(result, list) or len(result) < 1:
        return "Could not load post data."

    # First element: post, second: comments
    post_data = result[0]["data"]["children"][0] if result[0].get("data", {}).get("children") else {}
    lines = [_format_post(post_data, include_body=True), "\n---\n### Comments\n"]

    if len(result) > 1:
        comments = result[1].get("data", {}).get("children", [])
        for c in comments[:comment_limit]:
            if c.get("kind") == "t1":
                lines.append(_format_comment(c))
                # Show one level of replies
                replies = c.get("data", {}).get("replies")
                if isinstance(replies, dict):
                    for reply in replies.get("data", {}).get("children", [])[:3]:
                        if reply.get("kind") == "t1":
                            lines.append(_format_comment(reply, depth=1))
                lines.append("")

    return "\n".join(lines)


@safe_tool
def reddit_search(query: str, subreddit: str = "", sort: str = "relevance", limit: int = 10) -> str:
    """Search Reddit for posts matching a query.

    Args:
        query: Search query string.
        subreddit: Optional subreddit to search within (without r/ prefix). Empty = all of Reddit.
        sort: Sort order — 'relevance', 'hot', 'top', 'new', 'comments'. Default: 'relevance'.
        limit: Number of results (1-25). Default: 10.
    """
    limit = max(1, min(25, limit))
    sort = sort if sort in ("relevance", "hot", "top", "new", "comments") else "relevance"

    endpoint = f"/r/{subreddit}/search" if subreddit else "/search"
    params = {
        "q": query,
        "sort": sort,
        "limit": str(limit),
        "restrict_sr": "true" if subreddit else "false",
    }

    result = _reddit_request(endpoint, params=params)
    posts = result.get("data", {}).get("children", [])

    if not posts:
        scope = f"r/{subreddit}" if subreddit else "Reddit"
        return f"No results for '{query}' on {scope}."

    scope = f"r/{subreddit}" if subreddit else "all of Reddit"
    lines = [f"## Search results for '{query}' on {scope} ({len(posts)} results)\n"]
    for i, post in enumerate(posts, 1):
        lines.append(f"{i}. {_format_post(post, include_body=True)}")
    return "\n\n".join(lines)


@safe_tool
def reddit_post(subreddit: str, title: str, body: str = "", url: str = "", flair_id: str = "") -> str:
    """Submit a new post to a subreddit.

    Creates either a self (text) post or a link post.

    Args:
        subreddit: Subreddit to post to (without r/ prefix).
        title: Post title.
        body: Post body text (for self/text posts). Supports Reddit markdown.
        url: URL to submit (for link posts). If provided, body is ignored.
        flair_id: Optional flair ID for the post.
    """
    if not title.strip():
        return "Error: Post title cannot be empty."

    data = {
        "sr": subreddit,
        "title": title.strip(),
        "resubmit": "true",
    }

    if url.strip():
        data["kind"] = "link"
        data["url"] = url.strip()
    else:
        data["kind"] = "self"
        data["text"] = body

    if flair_id:
        data["flair_id"] = flair_id

    result = _reddit_request("/api/submit", method="POST", data=data)

    if result.get("success") is False:
        errors = result.get("jquery", result.get("json", {}).get("errors", []))
        return f"Post failed: {errors}"

    # Extract the new post URL
    post_url = ""
    json_data = result.get("json", {})
    if json_data.get("data", {}).get("url"):
        post_url = json_data["data"]["url"]

    return (
        f"✅ Post submitted to r/{subreddit}!\n"
        f"**{title}**\n"
        f"URL: {post_url}"
    )


@safe_tool
def reddit_comment(thing_id: str, body: str) -> str:
    """Reply to a post or comment on Reddit.

    Args:
        thing_id: The fullname of the post (t3_xxx) or comment (t1_xxx) to reply to.
                  Can also be a bare ID — will be treated as a post (t3_) by default.
        body: Comment text. Supports Reddit markdown.
    """
    if not body.strip():
        return "Error: Comment body cannot be empty."

    # Normalize the thing_id
    tid = thing_id.strip()
    if not tid.startswith("t1_") and not tid.startswith("t3_"):
        tid = f"t3_{tid}"

    result = _reddit_request(
        "/api/comment",
        method="POST",
        data={"thing_id": tid, "text": body},
    )

    json_data = result.get("json", {})
    errors = json_data.get("errors", [])
    if errors:
        return f"Comment failed: {errors}"

    comment_data = json_data.get("data", {}).get("things", [{}])[0].get("data", {})
    permalink = comment_data.get("permalink", "")

    return (
        f"✅ Comment posted!\n"
        f"Replied to: {tid}\n"
        f"Link: https://reddit.com{permalink}" if permalink else f"✅ Comment posted on {tid}!"
    )


@safe_tool
def reddit_user(username: str) -> str:
    """Get information about a Reddit user.

    Args:
        username: Reddit username (without u/ prefix).
    """
    result = _reddit_request(f"/user/{username}/about")
    d = result.get("data", result)

    karma_comment = d.get("comment_karma", 0)
    karma_post = d.get("link_karma", 0)
    created = d.get("created_utc", 0)

    import datetime
    created_date = datetime.datetime.fromtimestamp(created, tz=datetime.timezone.utc).strftime("%Y-%m-%d") if created else "?"

    return (
        f"## u/{d.get('name', username)}\n"
        f"- **Post karma:** {karma_post:,}\n"
        f"- **Comment karma:** {karma_comment:,}\n"
        f"- **Account created:** {created_date}\n"
        f"- **Verified:** {'✅' if d.get('verified') else '❌'}\n"
        f"- **Has Premium:** {'✅' if d.get('is_gold') else '❌'}"
    )