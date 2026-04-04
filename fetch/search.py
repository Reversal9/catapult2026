"""
DuckDuckGo HTML search — no API key required.
Used by all sources to discover relevant URLs.
"""
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urlparse, parse_qs, unquote

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def ddg_search(query: str, max_results: int = 8) -> list[str]:
    """Return a list of URLs from a DuckDuckGo HTML search."""
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.raise_for_status()
    except Exception as e:
        print(f"  [search] DDG failed: {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    urls: list[str] = []

    for a in soup.select("a.result__a"):
        href = a.get("href", "")
        # DDG wraps real URLs in a redirect: /l/?uddg=<encoded>
        if "uddg=" in href:
            qs = parse_qs(urlparse(href).query)
            real = qs.get("uddg", [None])[0]
            if real:
                href = unquote(real)
        if href.startswith("http"):
            urls.append(href)
        if len(urls) >= max_results:
            break

    return urls
