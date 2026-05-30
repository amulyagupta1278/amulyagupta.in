from collections import defaultdict
from urllib.parse import urlparse, urlunparse
import crawler
from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL, SITE_PAGES


def _norm(url: str) -> str:
    """Canonical form: strip query/fragment, /index.html→/, trailing slash."""
    p = urlparse(url)
    clean = urlunparse(p._replace(query="", fragment=""))
    if clean.endswith("/index.html"):
        clean = clean[: -len("index.html")]
    return clean.rstrip("/") or clean


class Skill07InternalLinking(BaseSEOSkill):
    SKILL_ID = 7
    SKILL_NAME = "Internal Linking Analysis"

    def run(self, pages: list[dict]) -> SkillResult:
        findings = []

        inbound: defaultdict[str, list] = defaultdict(list)
        outbound: defaultdict[str, list] = defaultdict(list)

        # Build normalised lookup from the known page list.
        all_norms = {_norm(SITE_URL + p) for p in SITE_PAGES}
        # Map normalised → original for reporting
        norm_to_orig = {_norm(SITE_URL + p): SITE_URL + p for p in SITE_PAGES}

        for page in pages:
            url = page["url"]
            url_norm = _norm(url)
            soup = page.get("soup")
            if not soup:
                continue

            links = crawler.get_all_links(soup, page_url=url)
            for link in links["internal"]:
                target_norm = _norm(link["url"])
                if target_norm in all_norms:
                    outbound[url_norm].append(link)
                    inbound[target_norm].append({"from": url, "text": link["text"]})

        # Orphan pages (no inbound internal links)
        homepage_norm = _norm(SITE_URL + "/")
        for p in SITE_PAGES:
            page_url = SITE_URL + p
            page_norm = _norm(page_url)
            if page_norm == homepage_norm:
                continue  # homepage exempt — it is the entry point
            if not inbound.get(page_norm):
                path = p
                findings.append(Finding(
                    title=f"Orphan page: {path}",
                    description="This page has no internal links pointing to it.",
                    severity="warning",
                    category="internal-linking",
                    url=page_url,
                    recommendation=f"Add at least 2–3 internal links to {path} from relevant pages.",
                ))

        # Pages with too many outbound internal links
        for url_norm, links in outbound.items():
            if len(links) > 40:
                orig_url = norm_to_orig.get(url_norm, url_norm)
                path = orig_url.replace(SITE_URL, "")
                findings.append(Finding(
                    title=f"Too many internal links: {path}",
                    description=f"{len(links)} internal links — dilutes link equity.",
                    severity="info",
                    category="internal-linking",
                    url=orig_url,
                    recommendation="Reduce internal links to the most relevant pages.",
                ))

        # Generic anchor text
        generic_anchors = {"click here", "here", "read more", "learn more", "this", "link", "page"}
        for page in pages:
            url = page["url"]
            soup = page.get("soup")
            if not soup:
                continue
            links = crawler.get_all_links(soup, page_url=url)
            for link in links["internal"]:
                if link["text"].lower().strip() in generic_anchors:
                    path = url.replace(SITE_URL, "")
                    findings.append(Finding(
                        title=f"Generic anchor text on {path}",
                        description=f"Link to {link['url']} uses generic anchor: '{link['text']}'",
                        severity="info",
                        category="anchor-text",
                        url=url,
                        recommendation="Use descriptive, keyword-rich anchor text.",
                        evidence=f"Text: '{link['text']}' → {link['url']}",
                    ))

        # Pages with no outbound internal links
        exempt = {_norm(SITE_URL + p) for p in ("/privacy.html", "/contact.html")}
        for page in pages:
            url = page["url"]
            url_norm = _norm(url)
            path = url.replace(SITE_URL, "")
            soup = page.get("soup")
            if not soup or page.get("status") != 200:
                continue
            if url_norm not in exempt and len(outbound.get(url_norm, [])) == 0:
                findings.append(Finding(
                    title=f"No internal links on {path}",
                    description="Page has no outbound internal links, reducing link equity flow.",
                    severity="warning",
                    category="internal-linking",
                    url=url,
                    recommendation="Add relevant internal links to improve crawlability and UX.",
                ))

        # Percentage-based score: penalise by fraction of affected pages
        total_pages = sum(1 for p in pages if p.get("status") == 200)
        orphan_count = sum(1 for f in findings if "Orphan" in f.title)
        no_links_count = sum(1 for f in findings if "No internal links" in f.title)
        affected = min(total_pages, orphan_count + no_links_count)
        if total_pages:
            coverage_score = max(0, round(100 * (1 - affected / total_pages)))
        else:
            coverage_score = 100
        # Small penalty for generic anchors and over-linked pages
        extra_penalty = sum(3 for f in findings if f.severity == "info")
        score = max(0, coverage_score - extra_penalty)

        inbound_counts = {u: len(links) for u, links in inbound.items()}
        return self.result(score, findings, {
            "inbound_counts": inbound_counts,
            "total_internal_links": sum(len(v) for v in outbound.values()),
        })
