import time
import requests
from bs4 import BeautifulSoup
from config import SITE_URL, SITE_PAGES

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "SEO-Runtime-Bot/1.0 (amulyagupta.in audit; +https://amulyagupta.in)"
})


def fetch(url: str, timeout: int = 15) -> dict:
    start = time.time()
    try:
        r = SESSION.get(url, timeout=timeout, allow_redirects=True)
        elapsed = int((time.time() - start) * 1000)
        return {
            "url": url,
            "status": r.status_code,
            "elapsed_ms": elapsed,
            "content_type": r.headers.get("content-type", ""),
            "html": r.text,  # always return full text; skills handle non-HTML types
            "headers": dict(r.headers),
            "redirect_url": r.url if r.url != url else None,
            "error": None,
        }
    except requests.exceptions.Timeout:
        return {"url": url, "status": 0, "elapsed_ms": timeout * 1000,
                "content_type": "", "html": "", "headers": {}, "redirect_url": None, "error": "timeout"}
    except Exception as e:
        return {"url": url, "status": 0, "elapsed_ms": int((time.time() - start) * 1000),
                "content_type": "", "html": "", "headers": {}, "redirect_url": None, "error": str(e)}


def parse(html: str, base_url: str = SITE_URL) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def crawl_all_pages(delay: float = 0.5) -> list[dict]:
    results = []
    for path in SITE_PAGES:
        url = SITE_URL + path
        result = fetch(url)
        if result["html"]:
            result["soup"] = parse(result["html"])
        else:
            result["soup"] = None
        results.append(result)
        time.sleep(delay)
    return results


def get_all_links(soup: BeautifulSoup, base_url: str = SITE_URL) -> dict:
    internal, external = [], []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(strip=True)
        if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        if href.startswith("/") or base_url in href:
            full = (base_url + href) if href.startswith("/") else href
            internal.append({"url": full, "text": text, "element": str(a)[:200]})
        elif href.startswith("http"):
            external.append({"url": href, "text": text})
    return {"internal": internal, "external": external}


def extract_json_ld(soup: BeautifulSoup) -> list[dict]:
    import json
    import logging
    _log = logging.getLogger("seo.crawler")
    schemas = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            schemas.append(data if isinstance(data, dict) else {"@graph": data})
        except Exception as exc:
            _log.debug("JSON-LD parse failed: %s", exc)
    return schemas


def extract_meta(soup: BeautifulSoup) -> dict:
    meta = {}
    title_tag = soup.find("title")
    meta["title"] = title_tag.get_text(strip=True) if title_tag else ""

    for m in soup.find_all("meta"):
        name = m.get("name", m.get("property", "")).lower()
        content = m.get("content", "")
        if name:
            meta[name] = content

    return meta


def extract_headings(soup: BeautifulSoup) -> list[dict]:
    headings = []
    for level in range(1, 7):
        for h in soup.find_all(f"h{level}"):
            headings.append({"level": level, "text": h.get_text(strip=True)})
    return headings


def word_count(soup: BeautifulSoup) -> int:
    skip = {"script", "style", "nav", "footer", "header"}
    words = [
        w
        for string in soup.strings
        if getattr(string.parent, "name", None) not in skip
        for w in string.split()
    ]
    return len(words)
