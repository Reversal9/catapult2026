"""
ENF Solar scraper — structured spec tables, 100k+ panels indexed.
Primary source: tried before PDF or generic HTML.
"""
import requests
from bs4 import BeautifulSoup

from ..search import ddg_search
from ..extractor import extract_all

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _find_url(model: str) -> str | None:
    queries = [
        f'site:enfsolar.com "{model}" specifications',
        f"site:enfsolar.com {model} solar panel",
    ]
    for q in queries:
        results = ddg_search(q, max_results=5)
        for url in results:
            if "enfsolar.com" in url and "/pv/panel" in url:
                return url
    return None


def _parse_spec_page(html: str) -> str:
    """Extract label: value pairs from ENF Solar's spec tables and definition lists."""
    soup = BeautifulSoup(html, "html.parser")
    lines: list[str] = []

    # Spec tables
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                label = cells[0].get_text(" ", strip=True)
                value = cells[1].get_text(" ", strip=True)
                if label and value:
                    lines.append(f"{label}: {value}")

    # Definition lists (some pages use <dl>)
    for dl in soup.find_all("dl"):
        terms = dl.find_all("dt")
        defs = dl.find_all("dd")
        for t, d in zip(terms, defs):
            lines.append(f"{t.get_text(strip=True)}: {d.get_text(strip=True)}")

    return "\n".join(lines) if lines else soup.get_text(" ")


def fetch(model: str) -> tuple[dict | None, str | None]:
    """
    Attempt to retrieve specs from ENF Solar.
    Returns (specs_dict, source_url) or (None, None) on failure.
    """
    url = _find_url(model)
    if not url:
        return None, None

    try:
        res = requests.get(url, headers=HEADERS, timeout=12)
        res.raise_for_status()
    except Exception as e:
        print(f"  [enfsolar] request failed: {e}")
        return None, None

    text = _parse_spec_page(res.text)
    if not text.strip():
        return None, None

    return extract_all(text), url
