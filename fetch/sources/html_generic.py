"""
Generic HTML scraper — used as final fallback for specs and as primary source for pricing.
"""
import requests
from bs4 import BeautifulSoup

from ..search import ddg_search
from ..extractor import extract_all, extract_price

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Retailers known to carry US solar panels with listed prices
_PRICE_DOMAINS = [
    "wholesalesolar.com",
    "altestore.com",
    "solar-electric.com",
    "solarelectricsupply.com",
    "gogreensolar.com",
]


def _scrape_url(url: str) -> str | None:
    """Fetch URL and extract text from spec tables; fall back to full page text."""
    try:
        res = requests.get(url, headers=HEADERS, timeout=12)
        res.raise_for_status()
    except Exception as e:
        print(f"  [html] request failed for {url}: {e}")
        return None

    soup = BeautifulSoup(res.text, "html.parser")
    lines: list[str] = []

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                label = cells[0].get_text(" ", strip=True)
                value = cells[1].get_text(" ", strip=True)
                if label and value:
                    lines.append(f"{label}: {value}")

    return "\n".join(lines) if lines else soup.get_text(" ")


def fetch(model: str) -> tuple[dict | None, str | None]:
    """
    Generic HTML fallback for spec extraction.
    Returns (specs_dict, source_url) or (None, None).
    """
    results = ddg_search(f"{model} solar panel specifications datasheet", max_results=5)
    if not results:
        return None, None

    for url in results:
        text = _scrape_url(url)
        if text:
            specs = extract_all(text)
            if specs.get("power_stc_w") or specs.get("dimensions_mm", {}).get("length_mm"):
                return specs, url

    return None, None


def fetch_price(model: str) -> tuple[float | None, float | None, str | None]:
    """
    Search retailer sites for panel price.
    Returns (price_usd, price_per_watt_usd, source_url).
    """
    for domain in _PRICE_DOMAINS:
        results = ddg_search(f"site:{domain} {model}", max_results=3)
        url = next((u for u in results if domain in u), None)
        if not url:
            continue
        text = _scrape_url(url)
        if not text:
            continue
        price, ppw = extract_price(text)
        if price:
            return price, ppw, url

    return None, None, None
