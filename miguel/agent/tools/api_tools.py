"""HTTP client and API integration tools for Miguel.

Provides a flexible HTTP client for calling external REST APIs with configurable
methods, headers, authentication, and response parsing. Includes pre-built
integrations for popular free APIs (weather, exchange rates, IP info, etc).
"""

import json
from typing import Optional
from urllib.parse import urlencode, urljoin

from miguel.agent.tools.error_utils import safe_tool


def _ensure_requests():
    """Lazily import requests, with a helpful error if not installed."""
    try:
        import requests as _requests
        return _requests
    except ImportError:
        raise ImportError(
            "The 'requests' package is required for API tools. "
            "Use add_dependency('requests') to install it."
        )


def _truncate(text: str, max_len: int = 5000) -> str:
    """Truncate text to a maximum length with indicator."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n... [truncated, {len(text)} total chars]"


def _format_response(resp, include_headers: bool = False) -> str:
    """Format an HTTP response into a readable string."""
    parts = []
    parts.append(f"**Status:** {resp.status_code} {resp.reason}")
    parts.append(f"**URL:** {resp.url}")

    if include_headers:
        header_lines = []
        for k, v in resp.headers.items():
            header_lines.append(f"  {k}: {v}")
        parts.append("**Response Headers:**\n" + "\n".join(header_lines))

    content_type = resp.headers.get("content-type", "")

    # Try to parse as JSON
    if "json" in content_type or "javascript" in content_type:
        try:
            data = resp.json()
            formatted = json.dumps(data, indent=2, ensure_ascii=False, default=str)
            parts.append("**Body (JSON):**\n```json\n" + _truncate(formatted) + "\n```")
            return "\n\n".join(parts)
        except (json.JSONDecodeError, ValueError):
            pass

    # Try to auto-detect JSON even without content-type
    body = resp.text
    if body.strip().startswith(("{", "[")):
        try:
            data = json.loads(body)
            formatted = json.dumps(data, indent=2, ensure_ascii=False, default=str)
            parts.append("**Body (JSON):**\n```json\n" + _truncate(formatted) + "\n```")
            return "\n\n".join(parts)
        except (json.JSONDecodeError, ValueError):
            pass

    # Plain text / HTML
    if "html" in content_type:
        parts.append("**Body (HTML):** " + _truncate(body, 2000))
    elif "xml" in content_type:
        parts.append("**Body (XML):**\n```xml\n" + _truncate(body, 3000) + "\n```")
    else:
        parts.append("**Body:**\n" + _truncate(body))

    return "\n\n".join(parts)


# ── Primary HTTP Client ─────────────────────────────────────────────


@safe_tool
def http_request(
    url: str,
    method: str = "GET",
    headers: Optional[str] = None,
    body: Optional[str] = None,
    params: Optional[str] = None,
    auth_type: Optional[str] = None,
    auth_value: Optional[str] = None,
    timeout: int = 30,
    include_headers: bool = False,
) -> str:
    """Make an HTTP request to any URL/API endpoint.

    This is the primary tool for calling external REST APIs. Supports all HTTP
    methods, custom headers, request bodies, query parameters, and authentication.

    Args:
        url: The full URL to request (e.g. 'https://api.example.com/data').
        method: HTTP method — GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS.
                Default: GET.
        headers: Optional JSON string of headers.
                 Example: '{"Content-Type": "application/json", "X-Custom": "value"}'
        body: Optional request body. For JSON APIs, pass a JSON string.
              Example: '{"name": "test", "value": 42}'
        params: Optional JSON string of query parameters.
                Example: '{"page": "1", "limit": "10"}'
                These are appended to the URL as ?page=1&limit=10.
        auth_type: Authentication type — 'bearer', 'basic', 'api_key_header', or 'api_key_param'.
                   - 'bearer': Adds Authorization: Bearer <auth_value>
                   - 'basic': auth_value should be 'username:password'
                   - 'api_key_header': auth_value should be 'HeaderName:value'
                   - 'api_key_param': auth_value should be 'param_name:value' (added to query params)
        auth_value: The authentication credential (see auth_type for format).
        timeout: Request timeout in seconds (default 30, max 120).
        include_headers: If True, include response headers in the output.

    Returns:
        Formatted response with status code, URL, and body (auto-parsed if JSON).
    """
    requests = _ensure_requests()

    # Validate method
    method = method.upper()
    valid_methods = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
    if method not in valid_methods:
        return f"Error: Invalid HTTP method '{method}'. Use one of: {', '.join(sorted(valid_methods))}"

    # Validate timeout
    timeout = min(max(1, timeout), 120)

    # Parse headers
    req_headers = {}
    if headers:
        try:
            req_headers = json.loads(headers)
            if not isinstance(req_headers, dict):
                return "Error: headers must be a JSON object (dict), e.g. '{\"Content-Type\": \"application/json\"}'"
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in headers — {e}"

    # Parse query params
    req_params = {}
    if params:
        try:
            req_params = json.loads(params)
            if not isinstance(req_params, dict):
                return "Error: params must be a JSON object (dict), e.g. '{\"page\": \"1\"}'"
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON in params — {e}"

    # Parse body
    req_body = None
    req_json = None
    if body:
        # Try to parse as JSON for automatic Content-Type handling
        try:
            req_json = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            req_body = body  # Send as raw text

    # Handle authentication
    req_auth = None
    if auth_type and auth_value:
        auth_type_lower = auth_type.lower()
        if auth_type_lower == "bearer":
            req_headers["Authorization"] = f"Bearer {auth_value}"
        elif auth_type_lower == "basic":
            if ":" not in auth_value:
                return "Error: For basic auth, auth_value must be 'username:password'"
            username, password = auth_value.split(":", 1)
            req_auth = (username, password)
        elif auth_type_lower == "api_key_header":
            if ":" not in auth_value:
                return "Error: For api_key_header, auth_value must be 'HeaderName:value'"
            header_name, header_val = auth_value.split(":", 1)
            req_headers[header_name.strip()] = header_val.strip()
        elif auth_type_lower == "api_key_param":
            if ":" not in auth_value:
                return "Error: For api_key_param, auth_value must be 'param_name:value'"
            param_name, param_val = auth_value.split(":", 1)
            req_params[param_name.strip()] = param_val.strip()
        else:
            return f"Error: Unknown auth_type '{auth_type}'. Use: bearer, basic, api_key_header, api_key_param"

    # Set a user agent
    if "User-Agent" not in req_headers:
        req_headers["User-Agent"] = "Miguel-Agent/1.0"

    # Make the request
    resp = requests.request(
        method=method,
        url=url,
        headers=req_headers,
        params=req_params if req_params else None,
        json=req_json,
        data=req_body,
        auth=req_auth,
        timeout=timeout,
        allow_redirects=True,
    )

    return _format_response(resp, include_headers=include_headers)


# ── Convenience Helpers ──────────────────────────────────────────────


@safe_tool
def api_get(url: str, params: Optional[str] = None, headers: Optional[str] = None) -> str:
    """Make a simple GET request to a URL or API endpoint.

    A convenience wrapper around http_request for quick GET calls.

    Args:
        url: The URL to request.
        params: Optional JSON string of query parameters.
                Example: '{"q": "python", "page": "1"}'
        headers: Optional JSON string of headers.

    Returns:
        Formatted response with status and body.
    """
    return http_request(
        url=url,
        method="GET",
        params=params,
        headers=headers,
    )


@safe_tool
def api_post(url: str, body: str, headers: Optional[str] = None) -> str:
    """Make a POST request to a URL or API endpoint.

    A convenience wrapper around http_request for quick POST calls.
    Automatically detects JSON bodies and sets Content-Type accordingly.

    Args:
        url: The URL to request.
        body: The request body. JSON strings are auto-detected and parsed.
        headers: Optional JSON string of additional headers.

    Returns:
        Formatted response with status and body.
    """
    return http_request(
        url=url,
        method="POST",
        body=body,
        headers=headers,
    )


# ── Pre-built API Integrations ───────────────────────────────────────


@safe_tool
def api_quickstart(service: str, query: Optional[str] = None) -> str:
    """Call a pre-built API integration for common services.

    These are free, no-API-key-required services. Use them for quick
    lookups without needing to construct URLs manually.

    Args:
        service: The service to call. Available services:
                 - 'weather <city>' — Current weather (wttr.in)
                 - 'ip' or 'ip <address>' — IP geolocation info (ip-api.com)
                 - 'exchange <FROM> <TO>' — Currency exchange rate (frankfurter.app)
                 - 'exchange <FROM> <TO> <amount>' — Convert currency amount
                 - 'joke' — Random programming joke (official-joke-api)
                 - 'uuid' — Generate a UUID (httpbin.org)
                 - 'headers' — See what headers your request sends (httpbin.org)
                 - 'time <timezone>' — Current time in a timezone (worldtimeapi.org)
                 - 'country <code>' — Country info by code (restcountries.com)
                 - 'github <user>' — GitHub user profile info
                 - 'list' — Show all available services
        query: Optional additional parameter (alternative to including it in service string).

    Returns:
        Formatted API response.
    """
    requests = _ensure_requests()

    # Parse service and arguments
    parts = service.strip().split(None, 1)
    svc = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else (query or "")

    timeout = 15

    if svc == "list":
        return """## Available API Quickstart Services

| Service | Usage | Description |
|---------|-------|-------------|
| `weather` | `weather London` | Current weather for a city |
| `ip` | `ip` or `ip 8.8.8.8` | IP geolocation info |
| `exchange` | `exchange USD EUR` or `exchange USD EUR 100` | Currency exchange rates |
| `joke` | `joke` | Random programming joke |
| `uuid` | `uuid` | Generate a UUID |
| `headers` | `headers` | See your request headers |
| `time` | `time America/New_York` | Current time in a timezone |
| `country` | `country US` | Country information |
| `github` | `github torvalds` | GitHub user profile |

All services are free and require no API key."""

    elif svc == "weather":
        city = arg or "New York"
        resp = requests.get(f"https://wttr.in/{city}?format=j1", timeout=timeout,
                            headers={"User-Agent": "Miguel-Agent/1.0"})
        if resp.status_code != 200:
            return f"Weather API returned status {resp.status_code} for '{city}'"
        data = resp.json()
        current = data.get("current_condition", [{}])[0]
        area = data.get("nearest_area", [{}])[0]
        area_name = area.get("areaName", [{}])[0].get("value", city)
        country = area.get("country", [{}])[0].get("value", "")
        desc = current.get("weatherDesc", [{}])[0].get("value", "Unknown")
        temp_c = current.get("temp_C", "?")
        temp_f = current.get("temp_F", "?")
        feels_c = current.get("FeelsLikeC", "?")
        humidity = current.get("humidity", "?")
        wind_kmph = current.get("windspeedKmph", "?")
        wind_dir = current.get("winddir16Point", "?")
        precip = current.get("precipMM", "0")
        visibility = current.get("visibility", "?")
        uv = current.get("uvIndex", "?")

        return f"""## Weather for {area_name}, {country}

| Metric | Value |
|--------|-------|
| **Condition** | {desc} |
| **Temperature** | {temp_c}°C / {temp_f}°F |
| **Feels like** | {feels_c}°C |
| **Humidity** | {humidity}% |
| **Wind** | {wind_kmph} km/h {wind_dir} |
| **Precipitation** | {precip} mm |
| **Visibility** | {visibility} km |
| **UV Index** | {uv} |"""

    elif svc == "ip":
        target = arg.strip() if arg.strip() else ""
        url = f"http://ip-api.com/json/{target}?fields=status,message,country,regionName,city,zip,lat,lon,timezone,isp,org,as,query"
        resp = requests.get(url, timeout=timeout)
        data = resp.json()
        if data.get("status") == "fail":
            return f"IP lookup failed: {data.get('message', 'Unknown error')}"
        return f"""## IP Geolocation: {data.get('query', 'Unknown')}

| Field | Value |
|-------|-------|
| **IP** | {data.get('query', '?')} |
| **City** | {data.get('city', '?')} |
| **Region** | {data.get('regionName', '?')} |
| **Country** | {data.get('country', '?')} |
| **ZIP** | {data.get('zip', '?')} |
| **Coordinates** | {data.get('lat', '?')}, {data.get('lon', '?')} |
| **Timezone** | {data.get('timezone', '?')} |
| **ISP** | {data.get('isp', '?')} |
| **Organization** | {data.get('org', '?')} |
| **AS** | {data.get('as', '?')} |"""

    elif svc == "exchange":
        exchange_parts = arg.strip().split()
        if len(exchange_parts) < 2:
            return "Usage: `exchange <FROM> <TO> [amount]`\nExample: `exchange USD EUR` or `exchange USD EUR 100`"
        base = exchange_parts[0].upper()
        target_cur = exchange_parts[1].upper()
        amount = None
        if len(exchange_parts) >= 3:
            try:
                amount = float(exchange_parts[2])
            except ValueError:
                return f"Error: '{exchange_parts[2]}' is not a valid number for amount."

        if amount:
            url = f"https://api.frankfurter.app/latest?amount={amount}&from={base}&to={target_cur}"
        else:
            url = f"https://api.frankfurter.app/latest?from={base}&to={target_cur}"

        resp = requests.get(url, timeout=timeout)
        if resp.status_code != 200:
            return f"Exchange rate API error: {resp.status_code} — {resp.text[:200]}"
        data = resp.json()
        rates = data.get("rates", {})
        rate_val = rates.get(target_cur, "?")
        date = data.get("date", "?")
        base_amount = data.get("amount", 1)
        return f"""## Exchange Rate ({date})

**{base_amount} {base}** = **{rate_val} {target_cur}**

Source: [Frankfurter API](https://frankfurter.app) (European Central Bank data)"""

    elif svc == "joke":
        resp = requests.get("https://official-joke-api.appspot.com/random_joke", timeout=timeout)
        data = resp.json()
        return f"## Random Joke\n\n**{data.get('setup', '?')}**\n\n{data.get('punchline', '?')}"

    elif svc == "uuid":
        resp = requests.get("https://httpbin.org/uuid", timeout=timeout)
        data = resp.json()
        return f"Generated UUID: `{data.get('uuid', '?')}`"

    elif svc == "headers":
        resp = requests.get("https://httpbin.org/headers",
                            headers={"User-Agent": "Miguel-Agent/1.0"}, timeout=timeout)
        data = resp.json()
        headers_dict = data.get("headers", {})
        lines = [f"| `{k}` | `{v}` |" for k, v in headers_dict.items()]
        return "## Request Headers\n\n| Header | Value |\n|--------|-------|\n" + "\n".join(lines)

    elif svc == "time":
        tz = arg.strip() if arg.strip() else "UTC"
        resp = requests.get(f"https://worldtimeapi.org/api/timezone/{tz}", timeout=timeout)
        if resp.status_code == 404:
            # List available timezones matching
            tz_resp = requests.get("https://worldtimeapi.org/api/timezone", timeout=timeout)
            all_tz = tz_resp.json()
            matches = [t for t in all_tz if tz.lower() in t.lower()][:10]
            if matches:
                return f"Timezone '{tz}' not found. Did you mean:\n" + "\n".join(f"- `{m}`" for m in matches)
            return f"Timezone '{tz}' not found. Use format like 'America/New_York', 'Europe/London', 'Asia/Tokyo'."
        data = resp.json()
        return f"""## Current Time: {data.get('timezone', tz)}

| Field | Value |
|-------|-------|
| **DateTime** | {data.get('datetime', '?')} |
| **Timezone** | {data.get('timezone', '?')} |
| **UTC Offset** | {data.get('utc_offset', '?')} |
| **Day of Week** | {data.get('day_of_week', '?')} |
| **Day of Year** | {data.get('day_of_year', '?')} |
| **Week Number** | {data.get('week_number', '?')} |"""

    elif svc == "country":
        code = arg.strip().upper() if arg.strip() else "US"
        resp = requests.get(f"https://restcountries.com/v3.1/alpha/{code}", timeout=timeout)
        if resp.status_code != 200:
            return f"Country lookup failed for '{code}'. Use 2-letter ISO codes (US, GB, DE, FR, JP, etc)."
        data = resp.json()
        if isinstance(data, list):
            data = data[0]
        name = data.get("name", {}).get("common", "?")
        official = data.get("name", {}).get("official", "?")
        capital = ", ".join(data.get("capital", ["?"])) if data.get("capital") else "?"
        region = data.get("region", "?")
        subregion = data.get("subregion", "?")
        population = data.get("population", 0)
        area = data.get("area", 0)
        languages = ", ".join(data.get("languages", {}).values()) if data.get("languages") else "?"
        currencies_data = data.get("currencies", {})
        currencies = ", ".join(f"{v.get('name', k)} ({v.get('symbol', '')})" for k, v in currencies_data.items()) if currencies_data else "?"
        flag = data.get("flag", "")

        pop_formatted = f"{population:,}" if isinstance(population, int) else str(population)
        area_formatted = f"{area:,.0f}" if isinstance(area, (int, float)) else str(area)

        return f"""## {flag} {name} ({code})

| Field | Value |
|-------|-------|
| **Official Name** | {official} |
| **Capital** | {capital} |
| **Region** | {region} / {subregion} |
| **Population** | {pop_formatted} |
| **Area** | {area_formatted} km² |
| **Languages** | {languages} |
| **Currencies** | {currencies} |"""

    elif svc == "github":
        username = arg.strip() if arg.strip() else "octocat"
        resp = requests.get(f"https://api.github.com/users/{username}",
                            headers={"User-Agent": "Miguel-Agent/1.0"}, timeout=timeout)
        if resp.status_code == 404:
            return f"GitHub user '{username}' not found."
        if resp.status_code != 200:
            return f"GitHub API returned status {resp.status_code}"
        data = resp.json()
        return f"""## GitHub: {data.get('login', username)}

| Field | Value |
|-------|-------|
| **Name** | {data.get('name', '?')} |
| **Bio** | {data.get('bio', 'No bio')} |
| **Location** | {data.get('location', '?')} |
| **Company** | {data.get('company', '?')} |
| **Public Repos** | {data.get('public_repos', 0)} |
| **Followers** | {data.get('followers', 0)} |
| **Following** | {data.get('following', 0)} |
| **Created** | {data.get('created_at', '?')} |
| **Profile** | {data.get('html_url', '?')} |"""

    else:
        return f"Unknown service: '{svc}'. Use `api_quickstart list` to see available services."