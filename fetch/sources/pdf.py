"""
PDF datasheet scraper.
Searches for manufacturer PDFs via DuckDuckGo, downloads and parses them.
"""
import io
import requests
import pdfplumber

from ..search import ddg_search
from ..extractor import extract_all

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _find_pdf_url(model: str) -> str | None:
    queries = [
        f'"{model}" datasheet filetype:pdf',
        f"{model} solar panel datasheet pdf specifications",
    ]
    for q in queries:
        results = ddg_search(q, max_results=8)
        for url in results:
            if ".pdf" in url.lower():
                return url
    return None


def _is_pdf_response(res: requests.Response, url: str) -> bool:
    ct = res.headers.get("Content-Type", "").lower()
    return "pdf" in ct or url.lower().endswith(".pdf")


def _extract_text(content: bytes) -> str:
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
            # Flatten embedded tables into "label: value" rows
            for table in (page.extract_tables() or []):
                for row in table:
                    if row:
                        clean = [str(c or "").strip() for c in row]
                        text_parts.append(" | ".join(clean))
    return "\n".join(text_parts)


def fetch(model: str) -> tuple[dict | None, str | None]:
    """
    Find and parse a PDF datasheet for `model`.
    Returns (specs_dict, source_url) or (None, None).
    """
    url = _find_pdf_url(model)
    if not url:
        return None, None

    try:
        res = requests.get(url, headers=HEADERS, timeout=20)
        res.raise_for_status()
        if not _is_pdf_response(res, url):
            return None, None
    except Exception as e:
        print(f"  [pdf] download failed: {e}")
        return None, None

    try:
        text = _extract_text(res.content)
    except Exception as e:
        print(f"  [pdf] parse failed: {e}")
        return None, None

    if not text.strip():
        return None, None

    return extract_all(text), url
