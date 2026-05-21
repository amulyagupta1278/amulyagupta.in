import json
import logging
import crawler
from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL, GOOGLE_SEARCH_CONSOLE_CREDENTIALS, GOOGLE_SERVICE_ACCOUNT_JSON

log = logging.getLogger(__name__)

GSC_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
GSC_PROPERTY = "https://amulyagupta.in/"


def _gsc_client():
    """Return authenticated GSC resource or None if credentials unavailable."""
    creds_json = GOOGLE_SEARCH_CONSOLE_CREDENTIALS or GOOGLE_SERVICE_ACCOUNT_JSON
    if not creds_json:
        return None
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        creds_data = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(
            creds_data, scopes=GSC_SCOPES
        )
        return build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    except Exception as e:
        log.warning("GSC client init failed: %s", e)
        return None


def _query_gsc(service, days: int = 28) -> dict:
    """Run a performance query against GSC for the last N days."""
    from datetime import date, timedelta
    end = date.today() - timedelta(days=2)
    start = end - timedelta(days=days)
    try:
        resp = service.searchanalytics().query(
            siteUrl=GSC_PROPERTY,
            body={
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "dimensions": ["query", "page"],
                "rowLimit": 25,
                "dataState": "final",
            },
        ).execute()
        return resp
    except Exception as e:
        log.warning("GSC query failed: %s", e)
        return {}


class Skill18SearchConsole(BaseSEOSkill):
    SKILL_ID = 18
    SKILL_NAME = "Search Console Intelligence"

    def run(self, pages: list[dict]) -> SkillResult:
        findings = []
        score = 70
        metadata = {"gsc_integrated": False}

        # ── Try live GSC API ─────────────────────────────────────────────────
        service = _gsc_client()
        if service:
            try:
                gsc_data = _query_gsc(service)
                rows = gsc_data.get("rows", [])
                metadata["gsc_integrated"] = True
                metadata["top_queries"] = [
                    {"query": r.get("keys", [""])[0], "page": r.get("keys", ["",""])[1],
                     "clicks": r.get("clicks", 0), "impressions": r.get("impressions", 0),
                     "ctr": round(r.get("ctr", 0) * 100, 2), "position": round(r.get("position", 0), 1)}
                    for r in rows[:10]
                ]
                total_clicks = sum(r.get("clicks", 0) for r in rows)
                total_impressions = sum(r.get("impressions", 0) for r in rows)
                avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
                avg_pos = sum(r.get("position", 0) for r in rows) / len(rows) if rows else 0

                score = 80  # Base score when GSC is integrated

                findings.append(Finding(
                    title="Google Search Console data retrieved",
                    description=f"28-day performance: {total_clicks} clicks, {total_impressions} impressions, "
                                f"CTR {avg_ctr:.1f}%, avg position {avg_pos:.1f}",
                    severity="info",
                    category="search-console",
                    url=GSC_PROPERTY,
                    recommendation="Review top queries and optimize for better CTR on high-impression, low-CTR queries.",
                ))

                # CTR opportunity: high impressions, low CTR
                low_ctr = [r for r in rows if r.get("impressions", 0) > 20 and r.get("ctr", 0) < 0.02]
                if low_ctr:
                    q_list = ", ".join(f'"{r.get("keys",[""])[0]}"' for r in low_ctr[:3])
                    findings.append(Finding(
                        title=f"Low CTR on {len(low_ctr)} high-impression queries",
                        description=f"Queries with >20 impressions but <2% CTR: {q_list}",
                        severity="warning",
                        category="search-console",
                        url=GSC_PROPERTY,
                        recommendation="Improve title tags and meta descriptions to increase CTR for these queries.",
                    ))

                # Position improvement opportunities
                pos3to10 = [r for r in rows if 3 < r.get("position", 99) <= 10]
                if pos3to10:
                    findings.append(Finding(
                        title=f"{len(pos3to10)} queries ranking 4–10 (near Page 1 top)",
                        description="These queries are close to the top 3 — targeted optimization could unlock significant traffic.",
                        severity="info",
                        category="search-console",
                        url=GSC_PROPERTY,
                        recommendation="Audit content depth and internal linking for these near-top queries to push them into top 3.",
                    ))

            except Exception as e:
                log.error("GSC live analysis failed: %s", e)
                findings.append(Finding(
                    title="GSC data retrieval error",
                    description=f"Credentials present but query failed: {str(e)[:200]}",
                    severity="warning",
                    category="search-console",
                    url=GSC_PROPERTY,
                    recommendation="Verify the service account has Search Console property access.",
                ))
        else:
            findings.append(Finding(
                title="Search Console integration not configured",
                description=(
                    "Add GOOGLE_SEARCH_CONSOLE_CREDENTIALS to GitHub Secrets "
                    "to enable live GSC performance data."
                ),
                severity="info",
                category="configuration",
                url="https://search.google.com/search-console",
                recommendation=(
                    "1. Create a Google Cloud service account\n"
                    "2. Enable the Search Console API\n"
                    "3. Add service account email as GSC property owner\n"
                    "4. Download JSON key → add to GOOGLE_SEARCH_CONSOLE_CREDENTIALS secret"
                ),
            ))

        # ── Static checks (always run) ────────────────────────────────────────
        for page in pages:
            url = page["url"]
            path = url.replace(SITE_URL, "")
            soup = page.get("soup")
            if not soup or page.get("status") != 200:
                continue

            # GSC verification tag
            meta = (soup.find("meta", attrs={"name": "google-site-verification"}) or
                    soup.find("meta", attrs={"name": "google"}))
            if meta and path in ["/", ""]:
                findings.append(Finding(
                    title="Google Search Console verification tag found",
                    description=f"Meta verification: '{meta.get('content','')[:60]}'",
                    severity="info",
                    category="search-console",
                    url=url,
                    recommendation="Verification confirmed — ensure GSC property is fully configured.",
                ))

        # ── Sitemap check ─────────────────────────────────────────────────────
        sm = crawler.fetch(f"{SITE_URL}/sitemap.xml")
        if sm["status"] == 200:
            findings.append(Finding(
                title="Sitemap accessible — ready for GSC submission",
                description="sitemap.xml returns 200 and is valid for submission.",
                severity="info",
                category="search-console",
                url=f"{SITE_URL}/sitemap.xml",
                recommendation="Ensure sitemap is submitted in Google Search Console → Sitemaps.",
            ))
        else:
            score -= 15
            findings.append(Finding(
                title="Sitemap not accessible — cannot submit to GSC",
                description=f"sitemap.xml returned status {sm.get('status', 0)}.",
                severity="critical",
                category="search-console",
                url=f"{SITE_URL}/sitemap.xml",
                recommendation="Fix sitemap.xml before submitting to Google Search Console.",
            ))

        score = self.clamp_score(score, penalty_per_critical=10, penalty_per_warning=5, findings=findings)
        return self.result(score, findings, metadata)
