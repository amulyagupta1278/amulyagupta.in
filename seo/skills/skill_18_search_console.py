import logging
from base import BaseSEOSkill, Finding
from config import SITE_URL

log = logging.getLogger(__name__)


class Skill18SearchConsole(BaseSEOSkill):
    SKILL_ID = 18
    SKILL_NAME = "Search Console Intelligence"

    def run(self, pages: list[dict]) -> SkillResult:
        from base import SkillResult
        findings = []

        findings.append(Finding(
            title="Search Console integration requires credentials",
            description=(
                "To enable live GSC data, add GOOGLE_SEARCH_CONSOLE_CREDENTIALS "
                "to GitHub Secrets with a service account that has GSC property access."
            ),
            severity="info",
            category="configuration",
            url="https://search.google.com/search-console",
            recommendation=(
                "1. Create a Google Cloud service account\n"
                "2. Enable the Search Console API\n"
                "3. Add the service account email as a property owner in GSC\n"
                "4. Download JSON credentials and add to GOOGLE_SEARCH_CONSOLE_CREDENTIALS secret"
            ),
        ))

        # Still run available checks from the page data
        for page in pages:
            url = page["url"]
            path = url.replace(SITE_URL, "")
            soup = page.get("soup")
            if not soup or page.get("status") != 200:
                continue

            meta = (soup.find("meta", attrs={"name": "google-site-verification"}) or
                    soup.find("meta", attrs={"name": "google"}))
            if meta and path == "/":
                findings.append(Finding(
                    title="Google Search Console verification found",
                    description=f"Meta verification tag found: '{meta.get('content','')[:50]}'",
                    severity="info",
                    category="search-console",
                    url=url,
                    recommendation="Verification confirmed — ensure GSC property is fully set up.",
                ))

        # Check if sitemap is submitted (we can infer from sitemap existence)
        import crawler
        sm = crawler.fetch(f"{SITE_URL}/sitemap.xml")
        if sm["status"] == 200:
            findings.append(Finding(
                title="Sitemap ready for GSC submission",
                description="sitemap.xml exists and is accessible.",
                severity="info",
                category="search-console",
                url=f"{SITE_URL}/sitemap.xml",
                recommendation="Submit https://amulyagupta.in/sitemap.xml in Google Search Console → Sitemaps.",
            ))
        else:
            findings.append(Finding(
                title="Sitemap not accessible — cannot submit to GSC",
                description="sitemap.xml returned non-200 status.",
                severity="critical",
                category="search-console",
                url=f"{SITE_URL}/sitemap.xml",
                recommendation="Fix sitemap.xml before submitting to Google Search Console.",
            ))

        score = 60
        score = self.clamp_score(score, findings=findings)
        return self.result(score, findings, {"gsc_integrated": False})
