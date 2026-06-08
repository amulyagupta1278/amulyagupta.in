from collections import defaultdict
import crawler
from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL, SITE_PAGES

# Map URL aliases produced by navigation links to their canonical SITE_PAGES URL.
# e.g. /blog/ in nav links resolves to /blog/index.html in SITE_PAGES.
_URL_ALIASES: dict[str, str] = {
    SITE_URL + "/blog/": SITE_URL + "/blog/index.html",
    SITE_URL + "/blog":  SITE_URL + "/blog/index.html",
}


class Skill07InternalLinking(BaseSEOSkill):
    SKILL_ID = 7
    SKILL_NAME = "Internal Linking Analysis"

    def run(self, pages: list[dict]) -> SkillResult:
        findings = []

        inbound = defaultdict(list)
        outbound = defaultdict(list)
        all_urls = {SITE_URL + p for p in SITE_PAGES}
        # Normalised set used for membership tests (rstrip trailing slash).
        norm_urls = {u.rstrip("/") for u in all_urls}

        def _resolve_alias(target: str) -> str:
            """Resolve URL aliases so nav-style /blog/ matches /blog/index.html."""
            return _URL_ALIASES.get(target, _URL_ALIASES.get(target.rstrip("/"), target))

        for page in pages:
            url = page["url"]
            soup = page.get("soup")
            if not soup:
                continue

            links = crawler.get_all_links(soup)
            for link in links["internal"]:
                target = _resolve_alias(
                    link["url"].split("?")[0].split("#")[0].rstrip("/")
                )
                if target in norm_urls:
                    outbound[url].append(link)
                    inbound[target].append({"from": url, "text": link["text"]})

        # Orphan pages (no inbound links)
        for page_url in all_urls:
            norm = page_url.rstrip("/")
            # Skip the homepage — it's always reachable from the root.
            if norm == SITE_URL or norm == SITE_URL.rstrip("/"):
                continue
            if not inbound.get(norm) and not inbound.get(page_url):
                path = page_url.replace(SITE_URL, "")
                findings.append(Finding(
                    title=f"Orphan page: {path}",
                    description="This page has no internal links pointing to it.",
                    severity="warning",
                    category="internal-linking",
                    url=page_url,
                    recommendation=f"Add at least 2-3 internal links to {path} from relevant pages.",
                ))

        # Pages with too many outbound internal links
        for url, links in outbound.items():
            if len(links) > 40:
                path = url.replace(SITE_URL, "")
                findings.append(Finding(
                    title=f"Too many internal links: {path}",
                    description=f"{len(links)} internal links on this page dilutes link equity.",
                    severity="info",
                    category="internal-linking",
                    url=url,
                    recommendation="Reduce internal links to the most relevant pages to concentrate link equity.",
                ))

        # Generic anchor text
        generic_anchors = {"click here", "here", "read more", "learn more", "this", "link", "page"}
        for page in pages:
            url = page["url"]
            soup = page.get("soup")
            if not soup:
                continue
            links = crawler.get_all_links(soup)
            for link in links["internal"]:
                if link["text"].lower().strip() in generic_anchors:
                    path = url.replace(SITE_URL, "")
                    findings.append(Finding(
                        title=f"Generic anchor text on {path}",
                        description=f"Link to {link['url']} uses generic anchor: '{link['text']}'",
                        severity="info",
                        category="anchor-text",
                        url=url,
                        recommendation="Use descriptive, keyword-rich anchor text instead of generic phrases.",
                        evidence=f"Text: '{link['text']}' → {link['url']}",
                    ))

        # Pages with very few outbound links (potential link equity hoarding)
        for page in pages:
            url = page["url"]
            path = url.replace(SITE_URL, "")
            soup = page.get("soup")
            if not soup or page.get("status") != 200:
                continue
            if len(outbound.get(url, [])) == 0 and path not in ["/privacy.html", "/contact.html"]:
                findings.append(Finding(
                    title=f"No internal links on {path}",
                    description="Page has no outbound internal links, reducing link equity flow.",
                    severity="warning",
                    category="internal-linking",
                    url=url,
                    recommendation="Add relevant internal links to other pages to improve crawlability and UX.",
                ))

        score = self.clamp_score(100, findings=findings)

        inbound_counts = {url: len(links) for url, links in inbound.items()}
        return self.result(score, findings, {
            "inbound_counts": inbound_counts,
            "total_internal_links": sum(len(v) for v in outbound.values()),
        })
