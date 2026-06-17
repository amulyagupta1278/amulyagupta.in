import json
import logging
import crawler
from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL, GOOGLE_SEARCH_CONSOLE_CREDENTIALS

log = logging.getLogger(__name__)

_GSC_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
_GSC_DISCOVERY = "https://www.googleapis.com/discovery/v1/apis/searchconsole/v1/rest"


def _build_gsc_service():
    """Return an authenticated GSC service, or None if credentials are unavailable."""
    if not GOOGLE_SEARCH_CONSOLE_CREDENTIALS:
        return None
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds_data = json.loads(GOOGLE_SEARCH_CONSOLE_CREDENTIALS)
        creds = service_account.Credentials.from_service_account_info(
            creds_data, scopes=_GSC_SCOPES
        )
        return build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    except Exception as e:
        log.warning("GSC service build failed: %s", e)
        return None


def _query_search_analytics(service, site_url: str, days: int = 28) -> dict:
    """Run a Search Analytics query for the last N days."""
    try:
        from datetime import datetime, timedelta, timezone
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=days)

        body = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": ["query"],
            "rowLimit": 25,
            "dataState": "final",
        }
        resp = (
            service.searchanalytics()
            .query(siteUrl=site_url, body=body)
            .execute()
        )
        return resp
    except Exception as e:
        log.warning("GSC search analytics query failed: %s", e)
        return {}


def _query_page_analytics(service, site_url: str, days: int = 28) -> dict:
    """Run a Search Analytics query grouped by page."""
    try:
        from datetime import datetime, timedelta, timezone
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=days)

        body = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": ["page"],
            "rowLimit": 25,
            "dataState": "final",
        }
        resp = (
            service.searchanalytics()
            .query(siteUrl=site_url, body=body)
            .execute()
        )
        return resp
    except Exception as e:
        log.warning("GSC page analytics query failed: %s", e)
        return {}


class Skill18SearchConsole(BaseSEOSkill):
    SKILL_ID = 18
    SKILL_NAME = "Search Console Intelligence"

    def run(self, pages: list[dict]) -> SkillResult:
        findings = []
        metadata: dict = {"gsc_integrated": False}

        service = _build_gsc_service()

        if service is None:
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
                    "4. Download JSON credentials and set GOOGLE_SEARCH_CONSOLE_CREDENTIALS secret"
                ),
            ))
        else:
            metadata["gsc_integrated"] = True
            log.info("[Skill18] GSC service available — querying search analytics")

            # ── Query-level performance ────────────────────────────────────────
            query_data = _query_search_analytics(service, SITE_URL)
            rows = query_data.get("rows", [])
            metadata["total_queries"] = len(rows)

            if rows:
                total_clicks = sum(r.get("clicks", 0) for r in rows)
                total_impr = sum(r.get("impressions", 0) for r in rows)
                avg_ctr = (total_clicks / total_impr * 100) if total_impr else 0
                avg_pos = (
                    sum(r.get("position", 0) for r in rows) / len(rows)
                ) if rows else 0

                metadata.update({
                    "total_clicks_28d": total_clicks,
                    "total_impressions_28d": total_impr,
                    "avg_ctr_pct": round(avg_ctr, 2),
                    "avg_position": round(avg_pos, 1),
                })

                if avg_ctr < 2.0 and total_impr > 100:
                    findings.append(Finding(
                        title=f"Low average CTR: {avg_ctr:.1f}% (last 28 days)",
                        description=(
                            f"Average click-through rate of {avg_ctr:.1f}% is below the 2% benchmark. "
                            f"Total impressions: {total_impr:,} | Clicks: {total_clicks:,}"
                        ),
                        severity="warning",
                        category="search-console",
                        url=SITE_URL,
                        recommendation=(
                            "Improve title tags and meta descriptions to increase click-through rate. "
                            "Use numbers, power words, and clear value propositions in snippets."
                        ),
                    ))

                if avg_pos > 20 and total_impr > 50:
                    findings.append(Finding(
                        title=f"Low average position: {avg_pos:.0f} (last 28 days)",
                        description=(
                            f"Average SERP position of {avg_pos:.0f} means most queries appear beyond page 2. "
                            f"Queries tracked: {len(rows)}"
                        ),
                        severity="warning",
                        category="search-console",
                        url=SITE_URL,
                        recommendation=(
                            "Target long-tail keywords with less competition. "
                            "Improve content depth and add authoritative backlinks for priority pages."
                        ),
                    ))

                # Top queries with high impressions but low CTR (quick wins)
                quick_wins = [
                    r for r in rows
                    if r.get("impressions", 0) >= 10
                    and r.get("ctr", 0) < 0.03
                    and r.get("position", 100) <= 10
                ]
                if quick_wins:
                    qw_queries = [r["keys"][0] for r in quick_wins[:3] if r.get("keys")]
                    findings.append(Finding(
                        title=f"Quick wins: {len(quick_wins)} queries rank well but have low CTR",
                        description=(
                            f"Queries in top 10 with CTR < 3%: {', '.join(qw_queries)}. "
                            "These are high-value optimisation opportunities."
                        ),
                        severity="info",
                        category="search-console",
                        url=SITE_URL,
                        recommendation=(
                            "Rewrite title tags and meta descriptions for these queries to improve CTR. "
                            "Match the searcher's intent more precisely."
                        ),
                        evidence=f"Queries: {', '.join(qw_queries[:5])}",
                    ))
            else:
                findings.append(Finding(
                    title="No search analytics data returned from GSC",
                    description=(
                        "GSC returned zero rows. This may mean the property has no traffic "
                        "yet, or the service account lacks sufficient permissions."
                    ),
                    severity="warning",
                    category="search-console",
                    url="https://search.google.com/search-console",
                    recommendation=(
                        "Verify the service account is added as a full owner of the GSC property. "
                        "Ensure the site has been verified in Search Console."
                    ),
                ))

            # ── Page-level performance ─────────────────────────────────────────
            page_data = _query_page_analytics(service, SITE_URL)
            page_rows = page_data.get("rows", [])
            metadata["total_pages_in_gsc"] = len(page_rows)

            # Identify pages with zero impressions (potential indexation issues)
            crawled_urls = {p["url"] for p in pages if p.get("status") == 200}
            gsc_urls = {r["keys"][0] for r in page_rows if r.get("keys")}
            missing_from_gsc = [
                u for u in crawled_urls
                if u not in gsc_urls and "privacy" not in u
            ]
            if missing_from_gsc:
                findings.append(Finding(
                    title=f"{len(missing_from_gsc)} pages not appearing in GSC",
                    description=(
                        f"These pages have not appeared in GSC search results in the last 28 days: "
                        f"{', '.join(p.replace(SITE_URL,'') for p in missing_from_gsc[:4])}"
                    ),
                    severity="warning",
                    category="search-console",
                    url=SITE_URL,
                    recommendation=(
                        "Check that these pages are indexed (Google site: operator), "
                        "submit sitemap in GSC, and request indexing for important new pages."
                    ),
                ))

        # ── Checks that always run ─────────────────────────────────────────────
        # Verify sitemap accessible
        sm = crawler.fetch(f"{SITE_URL}/sitemap.xml")
        if sm["status"] == 200:
            findings.append(Finding(
                title="Sitemap accessible — ready for GSC submission",
                description="sitemap.xml returns 200 and is accessible to search engines.",
                severity="info",
                category="search-console",
                url=f"{SITE_URL}/sitemap.xml",
                recommendation="Ensure https://amulyagupta.in/sitemap.xml is submitted in Google Search Console → Sitemaps.",
            ))
        else:
            findings.append(Finding(
                title="Sitemap not accessible",
                description=f"sitemap.xml returned HTTP {sm['status']} — cannot be submitted to GSC.",
                severity="critical",
                category="search-console",
                url=f"{SITE_URL}/sitemap.xml",
                recommendation="Fix sitemap.xml accessibility before submitting to Google Search Console.",
            ))

        # Check homepage for GSC verification tag
        home = next((p for p in pages if p["url"].rstrip("/") == SITE_URL.rstrip("/")), None)
        if home and home.get("soup"):
            soup = home["soup"]
            meta_v = (
                soup.find("meta", attrs={"name": "google-site-verification"})
                or soup.find("meta", attrs={"name": "google"})
            )
            if meta_v:
                findings.append(Finding(
                    title="Google Search Console verification meta tag found",
                    description=f"Verification tag present: '{meta_v.get('content','')[:60]}'",
                    severity="info",
                    category="search-console",
                    url=home["url"],
                    recommendation="Property verified — ensure GSC is configured with Goals and Coverage reports.",
                ))
            else:
                findings.append(Finding(
                    title="No GSC verification meta tag on homepage",
                    description="No google-site-verification meta tag found on homepage.",
                    severity="info",
                    category="search-console",
                    url=home["url"],
                    recommendation=(
                        "Add Google Site Verification meta tag to confirm ownership in GSC. "
                        "Alternatively, verify via DNS TXT record or HTML file upload."
                    ),
                ))

        base_score = 70 if metadata.get("gsc_integrated") else 55
        score = self.clamp_score(base_score, findings=findings)
        return self.result(score, findings, metadata)
