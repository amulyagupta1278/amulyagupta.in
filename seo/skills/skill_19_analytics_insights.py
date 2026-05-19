import re
import crawler
from base import BaseSEOSkill, Finding
from config import SITE_URL

GA4_PATTERN = re.compile(r'G-[A-Z0-9]{8,}')
UA_PATTERN = re.compile(r'UA-\d{6,}-\d+')
GTM_PATTERN = re.compile(r'GTM-[A-Z0-9]{6,}')


class Skill19AnalyticsInsights(BaseSEOSkill):
    SKILL_ID = 19
    SKILL_NAME = "Analytics Insights"

    def run(self, pages: list[dict]) -> SkillResult:
        from base import SkillResult
        findings = []

        # Check analytics implementation on homepage
        home = next((p for p in pages if p["url"].rstrip("/") == SITE_URL.rstrip("/")), None)
        if home:
            html = home.get("html", "")
            soup = home.get("soup")

            ga4_ids = GA4_PATTERN.findall(html)
            ua_ids = UA_PATTERN.findall(html)
            gtm_ids = GTM_PATTERN.findall(html)

            if ga4_ids:
                findings.append(Finding(
                    title=f"GA4 tracking found: {ga4_ids[0]}",
                    description=f"Google Analytics 4 ({ga4_ids[0]}) detected on homepage.",
                    severity="info",
                    category="analytics",
                    url=SITE_URL,
                    recommendation="Ensure GA4 is configured with Goals, Conversions, and key Events.",
                ))
            elif ua_ids:
                findings.append(Finding(
                    title=f"Legacy Universal Analytics found: {ua_ids[0]}",
                    description="UA-XXXXX tracking detected — Google has deprecated Universal Analytics.",
                    severity="critical",
                    category="analytics",
                    url=SITE_URL,
                    recommendation="Migrate immediately to Google Analytics 4 (GA4). UA data collection has stopped.",
                ))
            else:
                findings.append(Finding(
                    title="No analytics tracking found",
                    description="No GA4, Universal Analytics, or GTM detected on homepage.",
                    severity="critical",
                    category="analytics",
                    url=SITE_URL,
                    recommendation="Add Google Analytics 4 tracking to measure traffic and user behavior.",
                ))

            if gtm_ids:
                findings.append(Finding(
                    title=f"Google Tag Manager detected: {gtm_ids[0]}",
                    description="GTM container found — ensure all tags are properly configured.",
                    severity="info",
                    category="analytics",
                    url=SITE_URL,
                    recommendation="Audit GTM container: remove unused tags, enable debug mode, verify triggers.",
                ))

            # Check for lazy-loaded analytics (performance best practice)
            if ga4_ids and soup:
                scripts = soup.find_all("script", src=True)
                analytics_scripts = [s for s in scripts if "google" in s.get("src", "").lower() or "gtag" in s.get("src", "").lower()]
                for script in analytics_scripts:
                    if not (script.get("defer") or script.get("async")):
                        findings.append(Finding(
                            title="Analytics script blocking render",
                            description="Google Analytics script loaded synchronously — impacts LCP.",
                            severity="warning",
                            category="analytics",
                            url=SITE_URL,
                            recommendation="Add defer or async attribute to analytics <script> tags.",
                        ))

        # Check all pages have analytics
        pages_without_analytics = []
        for page in pages:
            html = page.get("html", "")
            if page.get("status") != 200 or not html:
                continue
            if not GA4_PATTERN.search(html) and not GTM_PATTERN.search(html):
                path = page["url"].replace(SITE_URL, "")
                pages_without_analytics.append(path)

        if pages_without_analytics:
            findings.append(Finding(
                title=f"Analytics missing on {len(pages_without_analytics)} pages",
                description=f"Pages without tracking: {', '.join(pages_without_analytics[:5])}",
                severity="warning",
                category="analytics",
                url=SITE_URL,
                recommendation="Add GA4 tracking to all pages via a shared template or GTM.",
            ))

        score = self.clamp_score(70, findings=findings)
        return self.result(score, findings, {
            "ga4_detected": bool(home and GA4_PATTERN.search(home.get("html", ""))),
            "pages_without_analytics": len(pages_without_analytics),
        })
