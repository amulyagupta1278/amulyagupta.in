import logging
import crawler
from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL

log = logging.getLogger(__name__)

GSC_INDEXING_CHECKS = [
    ("sitemap.xml accessible", f"{SITE_URL}/sitemap.xml"),
    ("robots.txt accessible", f"{SITE_URL}/robots.txt"),
]

INDEXING_SIGNALS = [
    ("noindex detected", "noindex"),
    ("nofollow detected", "nofollow"),
    ("disallow all", "disallow: /"),
]


class Skill18SearchConsole(BaseSEOSkill):
    SKILL_ID = 18
    SKILL_NAME = "Search Console Intelligence"

    def run(self, pages: list[dict]) -> SkillResult:
        findings = []
        score = 70

        # ── GSC credentials status ────────────────────────────────────────────
        findings.append(Finding(
            title="Search Console API integration: credentials required",
            description=(
                "Live GSC ranking, crawl error, and coverage data requires "
                "GOOGLE_SEARCH_CONSOLE_CREDENTIALS in GitHub Secrets. "
                "All checks below are inferred from crawl data."
            ),
            severity="info",
            category="configuration",
            url="https://search.google.com/search-console",
            recommendation=(
                "1. Create a Google Cloud service account and enable Search Console API.\n"
                "2. Grant the service account 'Full' GSC property access.\n"
                "3. Export JSON key and add as GOOGLE_SEARCH_CONSOLE_CREDENTIALS secret."
            ),
        ))

        # ── Sitemap and robots.txt accessibility ──────────────────────────────
        for label, url in GSC_INDEXING_CHECKS:
            resp = crawler.fetch(url)
            if resp["status"] != 200:
                score -= 15
                findings.append(Finding(
                    title=f"GSC blocker: {label} — HTTP {resp['status']}",
                    description=f"{url} returned non-200 status. GSC cannot process this file.",
                    severity="critical",
                    category="search-console",
                    url=url,
                    recommendation=f"Ensure {url.split('/')[-1]} is deployed and publicly accessible.",
                ))
            else:
                findings.append(Finding(
                    title=f"GSC ready: {label}",
                    description=f"{url} is accessible (HTTP 200) — ready for GSC submission.",
                    severity="info",
                    category="search-console",
                    url=url,
                    recommendation="Submit the sitemap in Google Search Console → Sitemaps if not already done.",
                ))

        # ── robots.txt analysis ───────────────────────────────────────────────
        robots_resp = crawler.fetch(f"{SITE_URL}/robots.txt")
        if robots_resp["status"] == 200:
            robots_content = robots_resp.get("html", "").lower()

            if "disallow: /" in robots_content and "disallow: /\n" in robots_content:
                score -= 30
                findings.append(Finding(
                    title="robots.txt blocks all crawling — CRITICAL INDEXATION RISK",
                    description="Disallow: / blocks all search engine crawlers from indexing any page.",
                    severity="critical",
                    category="search-console",
                    url=f"{SITE_URL}/robots.txt",
                    recommendation="Remove or correct the 'Disallow: /' directive — replace with specific paths to block.",
                ))

            if "sitemap:" not in robots_content:
                score -= 5
                findings.append(Finding(
                    title="robots.txt missing Sitemap directive",
                    description="No Sitemap: directive in robots.txt — GSC relies on this for faster discovery.",
                    severity="warning",
                    category="search-console",
                    url=f"{SITE_URL}/robots.txt",
                    recommendation=f"Add 'Sitemap: {SITE_URL}/sitemap.xml' to robots.txt.",
                ))

        # ── Page-level indexability signals ───────────────────────────────────
        noindex_pages = []
        missing_canonical = []
        google_verification = None

        for page in pages:
            url = page["url"]
            path = url.replace(SITE_URL, "") or "/"
            soup = page.get("soup")
            if not soup or page.get("status") != 200:
                continue

            meta_robots = soup.find("meta", attrs={"name": "robots"})
            if meta_robots:
                content = meta_robots.get("content", "").lower()
                if "noindex" in content:
                    noindex_pages.append(path)

            canonical = soup.find("link", rel="canonical")
            if not canonical or not canonical.get("href"):
                missing_canonical.append(path)

            if path == "/":
                gv = (soup.find("meta", attrs={"name": "google-site-verification"}) or
                      soup.find("meta", attrs={"name": "google"}))
                if gv:
                    google_verification = gv.get("content", "")[:40]

        if noindex_pages:
            score -= 10 * len(noindex_pages)
            findings.append(Finding(
                title=f"noindex detected on {len(noindex_pages)} page(s)",
                description=f"Pages with noindex meta robots: {', '.join(noindex_pages[:5])}. "
                            f"These pages will not appear in search results.",
                severity="critical" if len(noindex_pages) > 2 else "warning",
                category="search-console",
                url=SITE_URL + noindex_pages[0],
                recommendation="Remove 'noindex' from pages you want indexed. Only use noindex on admin/duplicate pages.",
            ))

        if missing_canonical:
            findings.append(Finding(
                title=f"Missing canonical tag on {len(missing_canonical)} page(s)",
                description=f"Pages without canonical: {', '.join(missing_canonical[:5])}. "
                            f"GSC uses canonical to determine the preferred URL.",
                severity="warning",
                category="search-console",
                url=SITE_URL + missing_canonical[0],
                recommendation="Add <link rel='canonical' href='...'> to every page to prevent duplicate content issues.",
            ))

        if google_verification:
            findings.append(Finding(
                title="Google Search Console verification tag found",
                description=f"Meta verification: '{google_verification}' — GSC property is connected.",
                severity="info",
                category="search-console",
                url=SITE_URL,
                recommendation="Ensure all pages are submitted, coverage report shows no errors, and Core Web Vitals pass.",
            ))
        else:
            score -= 5
            findings.append(Finding(
                title="Google Search Console verification tag not found",
                description="No google-site-verification meta tag detected on homepage.",
                severity="warning",
                category="search-console",
                url=SITE_URL,
                recommendation=(
                    "Verify ownership in Google Search Console → Settings → Ownership Verification. "
                    "Add the HTML tag verification method to your homepage <head>."
                ),
            ))

        # ── Sitemap coverage vs known pages ───────────────────────────────────
        sitemap_resp = crawler.fetch(f"{SITE_URL}/sitemap.xml")
        if sitemap_resp["status"] == 200:
            sitemap_content = sitemap_resp.get("html", "")
            page_count_in_sitemap = sitemap_content.count("<loc>")
            total_audited = len([p for p in pages if p.get("status") == 200])
            if page_count_in_sitemap < total_audited:
                delta = total_audited - page_count_in_sitemap
                findings.append(Finding(
                    title=f"Sitemap missing {delta} page(s) vs crawled pages",
                    description=f"Sitemap has {page_count_in_sitemap} URLs but {total_audited} pages were audited. "
                                f"Missing pages won't be submitted to GSC.",
                    severity="warning",
                    category="search-console",
                    url=f"{SITE_URL}/sitemap.xml",
                    recommendation="Update sitemap.xml to include all published pages. The SEO Fixer can auto-add missing URLs.",
                ))

        score = self.clamp_score(score, findings=findings)
        return self.result(score, findings, {
            "gsc_integrated": False,
            "noindex_pages": noindex_pages,
            "missing_canonical": missing_canonical,
            "google_verification": bool(google_verification),
        })
