import crawler
from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL, SITE_PAGES

INTENTIONALLY_NOINDEX = ["/privacy.html"]


class Skill16Indexation(BaseSEOSkill):
    SKILL_ID = 16
    SKILL_NAME = "Indexation Coverage Audit"

    def run(self, pages: list[dict]) -> SkillResult:
        findings = []
        indexable = 0
        total = 0

        # Fetch sitemap once, reuse across all page checks
        sm_result = crawler.fetch(f"{SITE_URL}/sitemap.xml")
        sitemap_content = sm_result.get("html", "") if sm_result["status"] == 200 else ""

        for page in pages:
            url = page["url"]
            path = url.replace(SITE_URL, "")
            soup = page.get("soup")
            if not soup or page.get("status") != 200:
                continue

            total += 1
            is_indexable = True
            meta = crawler.extract_meta(soup)

            # Meta robots
            robots_content = meta.get("robots", "").lower()
            if "noindex" in robots_content:
                is_indexable = False
                severity = "info" if path in INTENTIONALLY_NOINDEX else "critical"
                findings.append(Finding(
                    title=f"noindex on {'intentional' if severity == 'info' else 'indexable'} page: {path}",
                    description=f"Meta robots: '{robots_content}'",
                    severity=severity,
                    category="indexation",
                    url=url,
                    recommendation="" if severity == "info" else "Remove noindex directive to allow search engine indexing.",
                ))

            if "nofollow" in robots_content and path not in INTENTIONALLY_NOINDEX:
                findings.append(Finding(
                    title=f"nofollow on page: {path}",
                    description="Meta robots nofollow prevents crawling of links on this page.",
                    severity="warning",
                    category="indexation",
                    url=url,
                    recommendation="Remove nofollow unless you specifically want to block link equity flow.",
                ))

            # Canonical pointing elsewhere
            canon = soup.find("link", rel="canonical")
            if canon:
                href = canon.get("href", "").rstrip("/")
                if href and href != url.rstrip("/") and href != SITE_URL + path.rstrip("/"):
                    is_indexable = False
                    findings.append(Finding(
                        title=f"Canonical points off-page: {path}",
                        description=f"Canonical points to {href} — this page won't be indexed.",
                        severity="warning",
                        category="indexation",
                        url=url,
                        recommendation="Verify cross-page canonical is intentional.",
                    ))

            # X-Robots-Tag header
            headers = page.get("headers", {})
            x_robots = headers.get("X-Robots-Tag", headers.get("x-robots-tag", "")).lower()
            if "noindex" in x_robots:
                is_indexable = False
                findings.append(Finding(
                    title=f"X-Robots-Tag noindex: {path}",
                    description="HTTP header X-Robots-Tag contains noindex directive.",
                    severity="critical",
                    category="indexation",
                    url=url,
                    recommendation="Remove the noindex X-Robots-Tag header from server configuration.",
                ))

            # Check sitemap inclusion
            if sitemap_content and is_indexable:
                if url not in sitemap_content:
                    findings.append(Finding(
                        title=f"Indexable page missing from sitemap: {path}",
                        description="This page should be indexed but is not in sitemap.xml.",
                        severity="warning",
                        category="indexation",
                        url=url,
                        recommendation="Add this page to sitemap.xml.",
                    ))

            if is_indexable:
                indexable += 1

        coverage = int(indexable / total * 100) if total else 0
        score = self.clamp_score(coverage, findings=findings)
        return self.result(score, findings, {
            "indexable_pages": indexable,
            "total_pages": total,
            "coverage_pct": coverage,
        })
