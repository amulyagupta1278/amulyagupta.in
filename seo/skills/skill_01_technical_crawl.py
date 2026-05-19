from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL, SITE_PAGES
import crawler


class Skill01TechnicalCrawl(BaseSEOSkill):
    SKILL_ID = 1
    SKILL_NAME = "Technical Crawl Audit"

    def run(self, pages: list[dict]) -> SkillResult:
        findings = []
        total = len(pages)
        ok_count = 0

        for page in pages:
            url = page["url"]
            status = page["status"]
            elapsed = page["elapsed_ms"]
            error = page["error"]
            path = url.replace(SITE_URL, "")

            if error:
                findings.append(Finding(
                    title=f"Crawl error: {path}",
                    description=f"Failed to fetch page: {error}",
                    severity="critical",
                    category="crawlability",
                    url=url,
                    recommendation="Verify the page is accessible and the server is responding correctly.",
                ))
                continue

            if status == 200:
                ok_count += 1
            elif status in (301, 302):
                findings.append(Finding(
                    title=f"Redirect on {path}",
                    description=f"Page returns HTTP {status} → {page.get('redirect_url','')}",
                    severity="warning",
                    category="redirects",
                    url=url,
                    recommendation="Ensure redirects are intentional and update internal links to point directly to canonical URLs.",
                ))
            elif status == 404:
                findings.append(Finding(
                    title=f"404 Not Found: {path}",
                    description="Page returns 404. Broken link or removed page.",
                    severity="critical",
                    category="crawlability",
                    url=url,
                    recommendation="Restore the page, set up a 301 redirect to an equivalent page, or remove all links pointing to this URL.",
                ))
            elif status >= 500:
                findings.append(Finding(
                    title=f"Server error on {path}",
                    description=f"Page returns HTTP {status} — server-side error.",
                    severity="critical",
                    category="crawlability",
                    url=url,
                    recommendation="Investigate server logs and fix the underlying server error immediately.",
                ))
            else:
                findings.append(Finding(
                    title=f"Unexpected status {status} on {path}",
                    description=f"Page returned HTTP {status}.",
                    severity="warning",
                    category="crawlability",
                    url=url,
                    recommendation="Investigate why this status code is returned.",
                ))

            if status == 200 and elapsed > 3000:
                findings.append(Finding(
                    title=f"Slow TTFB: {path}",
                    description=f"Page took {elapsed}ms to respond (threshold: 3000ms).",
                    severity="warning",
                    category="performance",
                    url=url,
                    recommendation="Optimize server response time. Consider CDN, caching, and server-side optimizations.",
                ))

            ct = page.get("content_type", "")
            if status == 200 and "html" not in ct.lower():
                findings.append(Finding(
                    title=f"Non-HTML content type: {path}",
                    description=f"Content-Type is '{ct}' — not standard HTML.",
                    severity="warning",
                    category="crawlability",
                    url=url,
                    recommendation="Ensure HTML pages serve text/html content type.",
                ))

        health_pct = (ok_count / total * 100) if total else 0
        avg_ms = sum(p["elapsed_ms"] for p in pages if p["status"] == 200) / max(ok_count, 1)

        score = self.clamp_score(100, findings=findings)

        return self.result(score, findings, {
            "total_pages": total,
            "ok_pages": ok_count,
            "health_pct": round(health_pct, 1),
            "avg_response_ms": round(avg_ms, 0),
        })
