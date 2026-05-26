from collections import defaultdict
import crawler
from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL, SITE_PAGES

# Pages that are intentionally low-link (utility pages)
_UTILITY_PATHS = {"/privacy.html", "/contact.html"}

# Ideal inbound link minimums per page type
_MIN_INBOUND = {
    "/blog/post-1-mlops-pipeline.html": 3,
    "/blog/post-2-mlops-stack.html": 3,
    "/blog/ai-ml-guide-2026.html": 3,
    "/projects.html": 4,
    "/experience.html": 3,
    "/about.html": 3,
    "/amulya-gupta.html": 3,
    "/blog/index.html": 3,
}

_GENERIC_ANCHORS = {
    "click here", "here", "read more", "learn more", "this", "link",
    "page", "more", "continue", "next", "previous", "go", "visit",
}


class Skill07InternalLinking(BaseSEOSkill):
    SKILL_ID = 7
    SKILL_NAME = "Internal Linking Analysis"

    def run(self, pages: list[dict]) -> SkillResult:
        findings = []

        inbound: dict[str, list] = defaultdict(list)
        outbound: dict[str, list] = defaultdict(list)
        all_urls = {SITE_URL + p for p in SITE_PAGES}
        all_urls_norm = {u.rstrip("/") for u in all_urls}

        # ── Build link graph ──────────────────────────────────────────────
        for page in pages:
            url = page["url"]
            soup = page.get("soup")
            if not soup or page.get("status") != 200:
                continue

            links = crawler.get_all_links(soup)
            seen_targets: set[str] = set()
            for link in links["internal"]:
                target = link["url"].split("?")[0].split("#")[0].rstrip("/")
                if target not in all_urls_norm:
                    continue
                outbound[url].append(link)
                if target not in seen_targets:
                    inbound[target].append({"from": url, "text": link["text"]})
                    seen_targets.add(target)

        # ── Orphan pages ──────────────────────────────────────────────────
        for page_url in all_urls:
            path = page_url.replace(SITE_URL, "")
            if path in _UTILITY_PATHS:
                continue
            norm = page_url.rstrip("/")
            if not inbound.get(norm) and not inbound.get(page_url):
                findings.append(Finding(
                    title=f"Orphan page: {path}",
                    description="No internal links point to this page — search engines may not discover or prioritise it.",
                    severity="warning",
                    category="internal-linking",
                    url=page_url,
                    recommendation=(
                        f"Add at least 3 contextual internal links to {path} from relevant pages "
                        f"(homepage, blog index, projects page)."
                    ),
                ))

        # ── Underlinked pages (below recommended inbound threshold) ───────
        for path, min_links in _MIN_INBOUND.items():
            page_url = SITE_URL + path
            norm = page_url.rstrip("/")
            count = len(inbound.get(norm, inbound.get(page_url, [])))
            if 0 < count < min_links:
                findings.append(Finding(
                    title=f"Underlinked: {path} ({count}/{min_links} inbound)",
                    description=f"Only {count} internal link(s) point to this page; {min_links} recommended for link equity.",
                    severity="info",
                    category="internal-linking",
                    url=page_url,
                    recommendation=f"Add {min_links - count} more contextual internal link(s) to {path} to improve crawl priority.",
                ))

        # ── Pages with zero outbound internal links ───────────────────────
        for page in pages:
            url = page["url"]
            path = url.replace(SITE_URL, "")
            soup = page.get("soup")
            if not soup or page.get("status") != 200 or path in _UTILITY_PATHS:
                continue
            if not outbound.get(url):
                findings.append(Finding(
                    title=f"No outbound internal links: {path}",
                    description="Page distributes no link equity to other pages — a crawl dead-end.",
                    severity="warning",
                    category="internal-linking",
                    url=url,
                    recommendation="Add 3-5 contextual internal links to related pages to distribute link equity.",
                ))

        # ── Generic anchor text ───────────────────────────────────────────
        generic_seen: set[str] = set()
        for page in pages:
            url = page["url"]
            soup = page.get("soup")
            if not soup:
                continue
            for link in crawler.get_all_links(soup)["internal"]:
                anchor = link["text"].lower().strip()
                key = f"{url}:{anchor}"
                if anchor in _GENERIC_ANCHORS and key not in generic_seen:
                    generic_seen.add(key)
                    path = url.replace(SITE_URL, "")
                    findings.append(Finding(
                        title=f"Generic anchor on {path}: '{link['text']}'",
                        description=f"Link to {link['url']} uses generic anchor text — misses keyword signals.",
                        severity="info",
                        category="anchor-text",
                        url=url,
                        recommendation="Replace with descriptive anchor: e.g. 'MLOps pipeline tutorial' instead of 'read more'.",
                        evidence=f"Anchor: '{link['text']}' → {link['url']}",
                    ))

        # ── Link equity concentration (too many links on one page) ────────
        for url, links in outbound.items():
            if len(links) > 40:
                path = url.replace(SITE_URL, "")
                findings.append(Finding(
                    title=f"Link equity dilution: {path} ({len(links)} outbound links)",
                    description=f"{len(links)} internal links dilutes PageRank passed to each destination.",
                    severity="info",
                    category="internal-linking",
                    url=url,
                    recommendation="Reduce to 20-30 internal links on high-link pages. Prioritise links to pillar content.",
                ))

        # ── PageRank proximity from homepage ─────────────────────────────
        homepage_url = SITE_URL + "/"
        homepage_norm = homepage_url.rstrip("/")
        homepage_outbound = {
            link["url"].rstrip("/")
            for link in outbound.get(homepage_url, outbound.get(homepage_norm, []))
        }
        key_pages = {
            SITE_URL + p for p in ["/projects.html", "/blog/index.html", "/experience.html", "/about.html"]
        }
        unreachable_from_home = [
            p for p in key_pages
            if p.rstrip("/") not in homepage_outbound and p not in homepage_outbound
        ]
        for p in unreachable_from_home:
            path = p.replace(SITE_URL, "")
            findings.append(Finding(
                title=f"Key page not linked from homepage: {path}",
                description="Homepage link is a strong PageRank signal. Missing it forces deeper crawl for this page.",
                severity="info",
                category="internal-linking",
                url=p,
                recommendation=f"Add a direct link to {path} from the homepage navigation or hero section.",
            ))

        # ── Link equity distribution summary ─────────────────────────────
        inbound_counts = {url: len(links) for url, links in inbound.items()}
        total_links = sum(len(v) for v in outbound.values())

        score = self.clamp_score(100, findings=findings)
        return self.result(score, findings, {
            "inbound_counts": inbound_counts,
            "total_internal_links": total_links,
            "orphan_count": sum(1 for f in findings if "Orphan" in f.title),
            "pages_linked_from_home": len(homepage_outbound),
        })
