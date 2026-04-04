"""
Playwright-based fallback scraper for JS-rendered sites.

Requires:
    pip install playwright
    playwright install chromium

Gracefully skipped (returns None) if playwright is not installed.

Tries in order:
  1. Bing search → top spec page
  2. ENF Solar (bypasses Cloudflare via real browser)
  3. Manufacturer site derived from brand name
"""
import re
from typing import Optional
from urllib.parse import quote_plus

from ..extractor import extract_all

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    _PLAYWRIGHT = True
except ImportError:
    _PLAYWRIGHT = False

_BRAND_DOMAINS: dict[str, str] = {
    "rec":         "recgroup.com",
    "longi":       "longi.com",
    "jinko":       "jinkosolar.com",
    "trina":       "trina-solar.com",
    "canadian":    "canadiansolar.com",
    "sunpower":    "sunpower.com",
    "lg":          "lg.com",
    "panasonic":   "panasonic.com",
    "q cells":     "q-cells.com",
    "qcells":      "q-cells.com",
    "silfab":      "silfabsolar.com",
    "mission":     "missionsolar.com",
    "solaria":     "solaria.com",
    "solaredge":   "solaredge.com",
    "hyundai":     "hyundai-energy.com",
}


def _detect_manufacturer_domain(model: str) -> Optional[str]:
    lower = model.lower()
    for keyword, domain in _BRAND_DOMAINS.items():
        if keyword in lower:
            return domain
    return None


def _extract_text_from_page(page) -> str:
    """Pull labelled spec rows from tables and definition lists; fall back to body text."""
    lines: list[str] = []
    try:
        rows = page.query_selector_all("table tr")
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                label = cells[0].inner_text().strip()
                value = cells[1].inner_text().strip()
                if label and value:
                    lines.append(f"{label}: {value}")
    except Exception:
        pass

    try:
        dts = page.query_selector_all("dl dt")
        dds = page.query_selector_all("dl dd")
        for dt, dd in zip(dts, dds):
            lines.append(f"{dt.inner_text().strip()}: {dd.inner_text().strip()}")
    except Exception:
        pass

    if lines:
        return "\n".join(lines)

    try:
        return page.inner_text("body")
    except Exception:
        return ""


def _scrape_url(browser, url: str) -> Optional[str]:
    ctx = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    )
    page = ctx.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20_000)
        return _extract_text_from_page(page)
    except PWTimeout:
        return None
    finally:
        ctx.close()


def _bing_top_url(browser, query: str) -> Optional[str]:
    url = f"https://www.bing.com/search?q={quote_plus(query)}"
    ctx = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    )
    page = ctx.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=15_000)
        # Bing result links are inside <li class="b_algo"> → <h2> → <a>
        anchors = page.query_selector_all("li.b_algo h2 a")
        for a in anchors:
            href = a.get_attribute("href") or ""
            if href.startswith("http") and "bing.com" not in href:
                return href
    except PWTimeout:
        pass
    finally:
        ctx.close()
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def available() -> bool:
    return _PLAYWRIGHT


def fetch(model: str) -> tuple[dict | None, str | None]:
    """
    Use a real Chromium browser to scrape specs.
    Returns (specs_dict, source_url) or (None, None) if playwright is not installed.
    """
    if not _PLAYWRIGHT:
        return None, None

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            return _fetch_with_browser(browser, model)
        finally:
            browser.close()


def _fetch_with_browser(browser, model: str) -> tuple[dict | None, str | None]:
    # 1 — Try manufacturer site if brand is recognisable
    domain = _detect_manufacturer_domain(model)
    if domain:
        url = _bing_top_url(
            browser, f"site:{domain} {model} datasheet specifications"
        )
        if url:
            text = _scrape_url(browser, url)
            if text:
                specs = extract_all(text)
                if specs.get("power_stc_w"):
                    return specs, url

    # 2 — Bing general search
    url = _bing_top_url(browser, f"{model} solar panel specifications datasheet")
    if url:
        text = _scrape_url(browser, url)
        if text:
            specs = extract_all(text)
            if specs.get("power_stc_w") or (specs.get("dimensions_mm") or {}).get("length_mm"):
                return specs, url

    # 3 — ENF Solar (now accessible via real browser)
    enf_url = _bing_top_url(
        browser, f"site:enfsolar.com {model} specifications"
    )
    if enf_url and "enfsolar.com" in enf_url:
        text = _scrape_url(browser, enf_url)
        if text:
            specs = extract_all(text)
            if specs.get("power_stc_w"):
                return specs, enf_url

    return None, None


def fetch_price(model: str) -> tuple[float | None, float | None, str | None]:
    """
    Use a real browser to find pricing on retailer sites.
    Returns (price_usd, price_per_watt_usd, source_url).
    """
    if not _PLAYWRIGHT:
        return None, None, None

    from ..extractor import extract_price

    retailer_queries = [
        f"site:wholesalesolar.com {model} price",
        f"site:altestore.com {model} buy",
        f"{model} solar panel buy price USD",
    ]

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            for query in retailer_queries:
                url = _bing_top_url(browser, query)
                if not url:
                    continue
                text = _scrape_url(browser, url)
                if not text:
                    continue
                price, ppw = extract_price(text)
                if price:
                    return price, ppw, url
        finally:
            browser.close()

    return None, None, None
