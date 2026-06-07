import json
import logging
import os
from datetime import datetime, timedelta, timezone

import crawler
from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL, GOOGLE_SEARCH_CONSOLE_CREDENTIALS

log = logging.getLogger(__name__)

GSC_DISCOVERY_URL = "https://www.googleapis.com/discovery/v1/apis/searchconsole/v1/rest"
PROPERTY_URL = SITE_URL.rstrip("/") + "/"


def _build_gsc_service():
    """Build an authenticated Google Search Console API service, or return None."""
    if not GOOGLE_SEARCH_CONSOLE_CREDENTIALS:
        return None
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds_data = json.loads(GOOGLE_SEARCH_CONSOLE_CREDENTIALS)
        creds = service_account.Credentials.from_service_account_info(
            creds_data,
            scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
        )
        return build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    except Exception as e:
        log.warning("GSC service build failed: %s", e)
        return None


def _query_search_analytics(service, start_date: str, end_date: str, dimensions: list) -> list:
    """Run a Search Console searchAnalytics.query request."""
    try:
        resp = service.searchanalytics().query(
            siteUrl=PROPERTY_URL,
            body={
                "startDate": start_date,
                "endDate": end_date,
                "dimensions": dimensions,
                "rowLimit": 25,
                "startRow": 0,
            },
        ).execute()
        return resp.get("rows", [])
    except Exception as e:
        log.warning("GSC analytics query failed (%s): %s", dimensions, e)
        return []


def _list_sitemaps(service) -> list:
    """Get submitted sitemaps for the property."""
    try:
        resp = service.sitemaps().list(siteUrl=PROPERTY_URL).execute()
        return resp.get("sitemap", [])
    except Exception as e:
        log.warning("GSC sitemaps.list failed: %s", e)
        return []


class Skill18SearchConsole(BaseSEOSkill):
    SKILL_ID = 18
    SKILL_NAME = "Search Console Intelligence"

    def run(self, pages: list[dict]) -> SkillResult:
        findings = []
        service = _build_gsc_service()
        gsc_integrated = service is not None

        if not gsc_integrated:
            findings.append(Finding(
                title="Search Console integration not configured",
                description=(
                    "GOOGLE_SEARCH_CONSOLE_CREDENTIALS secret is not set. "
                    "Live keyword ranking, click, and index coverage data is unavailable."
                ),
                severity="warning",
                category="configuration",
                url="https://search.google.com/search-console",
                recommendation=(
                    "1. Create a Google Cloud service account\n"
                    "2. Enable the Search Console API\n"
                    "3. Add the service account email as a verified owner in GSC\n"
                    "4. Download JSON key → add as GOOGLE_SEARCH_CONSOLE_CREDENTIALS secret"
                ),
            ))
        else:
            self._run_live_gsc_audit(service, findings)

        # Static checks available without API access
        self._run_static_checks(pages, findings)

        base = 60 if gsc_integrated else 45
        score = self.clamp_score(base, findings=findings)
        return self.result(score, findings, {"gsc_integrated": gsc_integrated})

    # ── Live GSC audit (requires credentials) ───────────────────────────────────

    def _run_live_gsc_audit(self, service, findings: list) -> None:
        now = datetime.now(timezone.utc)
        end = now.strftime("%Y-%m-%d")
        start_28d = (now - timedelta(days=28)).strftime("%Y-%m-%d")
        start_7d = (now - timedelta(days=7)).strftime("%Y-%m-%d")

        # ── Top queries (last 28 days) ───────────────────────────────────────
        queries = _query_search_analytics(service, start_28d, end, ["query"])
        if queries:
            top = queries[:3]
            names = ", ".join(r["keys"][0] for r in top)
            avg_pos = sum(r.get("position", 0) for r in top) / len(top)
            findings.append(Finding(
                title=f"Top search queries: {names}",
                description=(
                    f"{len(queries)} unique queries in the last 28 days. "
                    f"Average position of top 3: {avg_pos:.1f}."
                ),
                severity="info",
                category="search-console",
                url=PROPERTY_URL,
                recommendation=(
                    "Target top queries with dedicated content, FAQ schema, and internal "
                    "links pointing to the most relevant pages."
                ),
            ))

            # Flag high-impression / low-CTR opportunities
            for row in queries:
                impr = row.get("impressions", 0)
                ctr = row.get("ctr", 0)
                pos = row.get("position", 0)
                q = row["keys"][0]
                if impr > 50 and ctr < 0.03 and pos <= 10:
                    findings.append(Finding(
                        title=f"Low-CTR opportunity: '{q}'",
                        description=(
                            f"'{q}' ranks in position {pos:.1f} with {impr} impressions "
                            f"but only {ctr*100:.1f}% CTR."
                        ),
                        severity="warning",
                        category="search-console",
                        url=PROPERTY_URL,
                        recommendation=(
                            f"Improve title tag and meta description for pages ranking for '{q}' "
                            "to increase click-through rate."
                        ),
                    ))

        # ── Page-level performance (last 7 days) ────────────────────────────
        pages_data = _query_search_analytics(service, start_7d, end, ["page"])
        if pages_data:
            total_clicks_7d = sum(r.get("clicks", 0) for r in pages_data)
            total_impr_7d = sum(r.get("impressions", 0) for r in pages_data)
            findings.append(Finding(
                title=f"Last 7 days: {total_clicks_7d} clicks, {total_impr_7d} impressions",
                description=(
                    f"{len(pages_data)} pages received search traffic in the last 7 days."
                ),
                severity="info",
                category="search-console",
                url=PROPERTY_URL,
                recommendation=(
                    "Focus optimization on pages with high impressions but low clicks. "
                    "Review Search Console for any manual actions or coverage issues."
                ),
            ))

            # Identify pages with zero clicks despite impressions
            zero_click_pages = [
                r for r in pages_data
                if r.get("impressions", 0) > 10 and r.get("clicks", 0) == 0
            ]
            if zero_click_pages:
                paths = [r["keys"][0].replace(SITE_URL, "") for r in zero_click_pages[:3]]
                findings.append(Finding(
                    title=f"{len(zero_click_pages)} pages with impressions but zero clicks",
                    description=f"Pages with impressions but 0 clicks: {', '.join(paths)}",
                    severity="warning",
                    category="search-console",
                    url=PROPERTY_URL,
                    recommendation=(
                        "Audit title tags and meta descriptions on these pages. "
                        "Consider adding FAQ schema and improving content relevance."
                    ),
                ))

        # ── Sitemaps ─────────────────────────────────────────────────────────
        sitemaps = _list_sitemaps(service)
        if not sitemaps:
            findings.append(Finding(
                title="No sitemap submitted to Google Search Console",
                description="Submitting a sitemap helps Google discover and index all pages faster.",
                severity="warning",
                category="search-console",
                url="https://search.google.com/search-console/sitemaps",
                recommendation="Submit https://amulyagupta.in/sitemap.xml in GSC → Sitemaps.",
            ))
        else:
            for sm in sitemaps:
                errors = sm.get("errors", 0)
                warnings = sm.get("warnings", 0)
                if errors:
                    findings.append(Finding(
                        title=f"Sitemap errors in GSC: {sm.get('path','')}",
                        description=f"Sitemap has {errors} error(s) and {warnings} warning(s) in GSC.",
                        severity="critical",
                        category="search-console",
                        url=sm.get("path", ""),
                        recommendation="Fix sitemap errors in Google Search Console → Sitemaps.",
                    ))

    # ── Static checks (no API required) ─────────────────────────────────────

    def _run_static_checks(self, pages: list, findings: list) -> None:
        # Sitemap accessibility
        sm = crawler.fetch(f"{SITE_URL}/sitemap.xml")
        if sm["status"] == 200:
            findings.append(Finding(
                title="sitemap.xml is accessible",
                description="sitemap.xml returns HTTP 200 — ready for GSC submission.",
                severity="info",
                category="search-console",
                url=f"{SITE_URL}/sitemap.xml",
                recommendation="Ensure sitemap.xml is submitted in Google Search Console → Sitemaps.",
            ))
        else:
            findings.append(Finding(
                title="sitemap.xml not accessible",
                description=f"sitemap.xml returned HTTP {sm['status']}.",
                severity="critical",
                category="search-console",
                url=f"{SITE_URL}/sitemap.xml",
                recommendation="Fix sitemap.xml before submitting to Google Search Console.",
            ))

        # GSC verification meta tag check
        for page in pages:
            if page["url"].rstrip("/") != SITE_URL.rstrip("/"):
                continue
            soup = page.get("soup")
            if not soup:
                continue
            meta = (
                soup.find("meta", attrs={"name": "google-site-verification"}) or
                soup.find("meta", attrs={"name": "google"})
            )
            if meta:
                findings.append(Finding(
                    title="Google Search Console verification meta tag found",
                    description=f"Verification content: '{(meta.get('content',''))[:60]}'",
                    severity="info",
                    category="search-console",
                    url=page["url"],
                    recommendation="Verification confirmed — ensure GSC property is active and sitemaps are submitted.",
                ))
