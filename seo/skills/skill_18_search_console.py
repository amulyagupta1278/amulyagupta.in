"""
Skill 18: Search Console Intelligence

When GOOGLE_SEARCH_CONSOLE_CREDENTIALS is set (service account JSON with
GSC property owner access), queries the live GSC API for:
  - Search analytics: clicks, impressions, CTR, position (28-day window)
  - Sitemap submission status and error/warning counts
  - Low-CTR / zero-click page detection

Falls back to rich static analysis when credentials are absent:
  - Sitemap accessibility and lastmod coverage
  - Noindex tag detection on indexable pages
  - Canonical tag presence and consistency
  - GSC verification meta tag (homepage)
  - Structured data types that affect rich results
"""

import json
import logging
import socket
from datetime import datetime, timedelta

import crawler
from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL, GOOGLE_SEARCH_CONSOLE_CREDENTIALS

# Default socket timeout for GSC API calls — prevents infinite hangs on slow responses
_API_TIMEOUT_S = 45

log = logging.getLogger(__name__)

_GSC_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

# Both URL-prefix and Domain property formats tried automatically
_SITE_VARIANTS = [
    SITE_URL.rstrip("/") + "/",          # https://amulyagupta.in/
    "sc-domain:" + SITE_URL.replace("https://", "").replace("http://", "").rstrip("/"),
]


# ─────────────────────────────────────────────────────────────────────────────
# GSC API helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_service():
    """Build GSC v1 API client from service account JSON. Returns None on failure."""
    if not GOOGLE_SEARCH_CONSOLE_CREDENTIALS:
        return None
    try:
        import httplib2
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds_data = json.loads(GOOGLE_SEARCH_CONSOLE_CREDENTIALS)
        credentials = service_account.Credentials.from_service_account_info(
            creds_data, scopes=_GSC_SCOPES
        )
        # Apply socket-level timeout so a hung API call doesn't stall the workflow
        http = httplib2.Http(timeout=_API_TIMEOUT_S)
        return build("searchconsole", "v1", credentials=credentials,
                     http=http, cache_discovery=False)
    except Exception as e:
        log.warning("GSC API init failed: %s", e)
        return None


def _search_analytics(service, site_url: str, days: int = 28) -> list[dict]:
    """Query search analytics by page. Returns [] on failure."""
    end_date = (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%d")
    start_date = (datetime.utcnow() - timedelta(days=3 + days)).strftime("%Y-%m-%d")
    try:
        resp = service.searchanalytics().query(
            siteUrl=site_url,
            body={
                "startDate": start_date,
                "endDate": end_date,
                "dimensions": ["page"],
                "rowLimit": 25,
                "dataState": "all",
            },
        ).execute()
        return resp.get("rows", [])
    except Exception as e:
        log.warning("GSC search analytics [%s] error: %s", site_url, e)
        return []


def _list_sitemaps(service, site_url: str) -> list[dict]:
    """List submitted sitemaps. Returns [] on failure."""
    try:
        return service.sitemaps().list(siteUrl=site_url).execute().get("sitemap", [])
    except Exception as e:
        log.warning("GSC sitemaps [%s] error: %s", site_url, e)
        return []


def _try_variants(fn, service):
    """Try fn(service, variant) for each site variant; return first non-empty result."""
    for variant in _SITE_VARIANTS:
        result = fn(service, variant)
        if result:
            return result, variant
    return [], _SITE_VARIANTS[0]


# ─────────────────────────────────────────────────────────────────────────────
# Skill class
# ─────────────────────────────────────────────────────────────────────────────

class Skill18SearchConsole(BaseSEOSkill):
    SKILL_ID = 18
    SKILL_NAME = "Search Console Intelligence"

    def run(self, pages: list[dict]) -> SkillResult:
        findings: list[Finding] = []
        metadata: dict = {"gsc_integrated": False}

        service = _build_service()

        if service:
            api_findings, api_meta = self._api_checks(service)
            findings.extend(api_findings)
            metadata.update(api_meta)
        else:
            findings.append(Finding(
                title="Search Console API not configured",
                description=(
                    "GOOGLE_SEARCH_CONSOLE_CREDENTIALS secret not set. "
                    "Add a service account JSON with GSC property owner access "
                    "to enable live search analytics, CTR analysis, and sitemap monitoring."
                ),
                severity="info",
                category="configuration",
                url="https://search.google.com/search-console",
                recommendation=(
                    "1. Create a Google Cloud service account and enable the Search Console API. "
                    "2. Add the service account email as a property owner in GSC. "
                    "3. Download the JSON key and add it to the "
                    "GOOGLE_SEARCH_CONSOLE_CREDENTIALS GitHub secret."
                ),
            ))

        # Static checks always run (complement API data or stand alone)
        findings.extend(self._static_checks(pages))

        score = self._compute_score(metadata, findings)
        return self.result(score, findings, metadata)

    # ── API checks ─────────────────────────────────────────────────────────

    def _api_checks(self, service) -> tuple[list[Finding], dict]:
        findings: list[Finding] = []
        meta: dict = {"gsc_integrated": False}

        # Search analytics
        rows, active_variant = _try_variants(_search_analytics, service)

        if rows:
            meta["gsc_integrated"] = True
            meta["property"] = active_variant

            clicks = sum(r.get("clicks", 0) for r in rows)
            impressions = sum(r.get("impressions", 0) for r in rows)
            avg_ctr = (clicks / impressions * 100) if impressions else 0
            avg_pos = sum(r.get("position", 0) for r in rows) / len(rows) if rows else 0

            meta.update({
                "clicks_28d": clicks,
                "impressions_28d": impressions,
                "avg_ctr": round(avg_ctr, 2),
                "avg_position": round(avg_pos, 1),
                "pages_tracked": len(rows),
            })

            findings.append(Finding(
                title=(
                    f"GSC: {clicks:,} clicks · {impressions:,} impressions · "
                    f"{avg_ctr:.1f}% CTR · pos {avg_pos:.1f} (28d)"
                ),
                description=(
                    f"Property: {active_variant} | "
                    f"Pages tracked: {len(rows)}"
                ),
                severity="info",
                category="search-console",
                url=SITE_URL,
                recommendation=(
                    "Target avg CTR > 5% for branded queries. "
                    "Pages at positions 4–10 are the best CTR-lift opportunities — "
                    "improving title/description can double clicks without changing rankings."
                ),
            ))

            # Low-CTR, high-impression pages (positions 1-20, >50 impressions)
            for row in rows:
                page_url = (row.get("keys") or [""])[0]
                if not page_url:
                    continue
                p_clicks = row.get("clicks", 0)
                p_impr = row.get("impressions", 0)
                p_ctr = (p_clicks / p_impr * 100) if p_impr else 100
                p_pos = row.get("position", 99)

                if p_impr >= 50 and p_ctr < 2.0 and p_pos <= 20:
                    path = page_url.replace(SITE_URL, "") or "/"
                    findings.append(Finding(
                        title=f"Low-CTR opportunity: {path} ({p_ctr:.1f}% CTR, {p_impr:,} impressions)",
                        description=(
                            f"Ranks ~{p_pos:.0f} with {p_impr:,} impressions but only {p_ctr:.1f}% CTR. "
                            f"Better title/description could significantly increase clicks."
                        ),
                        severity="warning",
                        category="search-console",
                        url=page_url,
                        recommendation=(
                            "A/B test a more compelling title and meta description. "
                            "Add a power word, number, or year. Match search intent precisely."
                        ),
                    ))

            # Pages with impressions but zero clicks
            zero_click_pages = [
                r for r in rows
                if r.get("clicks", 0) == 0 and r.get("impressions", 0) >= 20
            ]
            if zero_click_pages:
                paths = ", ".join(
                    (r.get("keys") or [""])[0].replace(SITE_URL, "") or "/"
                    for r in zero_click_pages[:3]
                )
                findings.append(Finding(
                    title=f"{len(zero_click_pages)} pages have impressions but zero clicks",
                    description=f"These pages appear in search but attract no clicks: {paths}…",
                    severity="warning",
                    category="search-console",
                    url=SITE_URL,
                    recommendation=(
                        "Rewrite titles and meta descriptions to be more enticing. "
                        "Consider adding structured data (FAQ, HowTo) for richer SERP snippets."
                    ),
                ))

            # Very low average position (deep SERPs)
            if avg_pos > 30:
                findings.append(Finding(
                    title=f"Low average position: {avg_pos:.0f} — pages buried in SERPs",
                    description="Average ranking above position 30 means most pages are rarely seen.",
                    severity="warning",
                    category="search-console",
                    url=SITE_URL,
                    recommendation=(
                        "Prioritize long-tail keyword targeting, content depth, and internal "
                        "linking to surface buried pages."
                    ),
                ))
        else:
            meta["gsc_integrated"] = False
            findings.append(Finding(
                title="No GSC search analytics data returned",
                description=(
                    "The GSC API returned no rows. "
                    "Property may not be verified, service account may lack access, "
                    "or the site has no search traffic yet."
                ),
                severity="warning",
                category="search-console",
                url=SITE_URL,
                recommendation=(
                    "Verify the site property in Google Search Console "
                    "and ensure the service account email has 'Owner' permission."
                ),
            ))

        # Sitemaps
        sitemaps, sm_variant = _try_variants(_list_sitemaps, service)
        meta["sitemaps_submitted"] = len(sitemaps)

        if sitemaps:
            for sm in sitemaps:
                sm_url = sm.get("path", "")
                errors = int(sm.get("errors", 0) or 0)
                warnings = int(sm.get("warnings", 0) or 0)
                if errors:
                    findings.append(Finding(
                        title=f"Sitemap error(s) in GSC: {sm_url} ({errors} errors)",
                        description=f"Google Search Console reports {errors} sitemap errors.",
                        severity="critical",
                        category="search-console",
                        url=sm_url or SITE_URL,
                        recommendation=(
                            "Open GSC → Sitemaps to see specific errors. "
                            "Common causes: unreachable URLs, incorrect date formats, "
                            "or unsupported content types."
                        ),
                    ))
                elif warnings:
                    findings.append(Finding(
                        title=f"Sitemap warnings in GSC: {sm_url} ({warnings} warnings)",
                        description=f"Google Search Console reports {warnings} sitemap warnings.",
                        severity="warning",
                        category="search-console",
                        url=sm_url or SITE_URL,
                        recommendation="Review and resolve sitemap warnings in Google Search Console → Sitemaps.",
                    ))
                else:
                    findings.append(Finding(
                        title=f"Sitemap healthy in GSC: {sm_url}",
                        description="Sitemap submitted with no errors or warnings.",
                        severity="info",
                        category="search-console",
                        url=sm_url or SITE_URL,
                        recommendation="Monitor sitemap health weekly in GSC.",
                    ))
        else:
            findings.append(Finding(
                title="No sitemaps submitted to GSC",
                description="Google Search Console has no sitemaps listed for this property.",
                severity="warning",
                category="search-console",
                url=SITE_URL,
                recommendation=(
                    "Submit https://amulyagupta.in/sitemap.xml in "
                    "Google Search Console → Indexing → Sitemaps."
                ),
            ))

        return findings, meta

    # ── Static checks ──────────────────────────────────────────────────────

    def _static_checks(self, pages: list[dict]) -> list[Finding]:
        findings: list[Finding] = []

        # Sitemap accessibility and lastmod
        sm_resp = crawler.fetch(f"{SITE_URL}/sitemap.xml")
        if sm_resp["status"] == 200:
            sm_content = sm_resp.get("html", "")
            url_count = sm_content.count("<url>")
            has_lastmod = "<lastmod>" in sm_content

            findings.append(Finding(
                title=f"Sitemap accessible — {url_count} URL entries",
                description="sitemap.xml returns 200 OK.",
                severity="info",
                category="search-console",
                url=f"{SITE_URL}/sitemap.xml",
                recommendation=(
                    "Submit sitemap.xml to Google Search Console → Sitemaps if not already done."
                ),
            ))
            if not has_lastmod:
                findings.append(Finding(
                    title="Sitemap missing <lastmod> dates",
                    description="No <lastmod> tags found — Googlebot cannot prioritise freshly updated pages.",
                    severity="warning",
                    category="search-console",
                    url=f"{SITE_URL}/sitemap.xml",
                    recommendation="Add <lastmod>YYYY-MM-DD</lastmod> to every <url> block in sitemap.xml.",
                ))
        else:
            findings.append(Finding(
                title=f"Sitemap not accessible (HTTP {sm_resp['status']})",
                description="sitemap.xml returned a non-200 response — it cannot be submitted to GSC.",
                severity="critical",
                category="search-console",
                url=f"{SITE_URL}/sitemap.xml",
                recommendation="Fix sitemap.xml before attempting to submit to Google Search Console.",
            ))

        # Per-page static checks
        for page in pages:
            url = page["url"]
            path = url.replace(SITE_URL, "") or "/"
            soup = page.get("soup")
            if not soup or page.get("status") != 200:
                continue

            # GSC verification tag (homepage only)
            if path in ("/", ""):
                meta_verify = (
                    soup.find("meta", attrs={"name": "google-site-verification"})
                    or soup.find("meta", attrs={"name": "google"})
                )
                if meta_verify:
                    findings.append(Finding(
                        title="Google Search Console verification tag found",
                        description=f"Meta verification content: '{(meta_verify.get('content', ''))[:60]}'",
                        severity="info",
                        category="search-console",
                        url=url,
                        recommendation=(
                            "Verification confirmed. Ensure the GSC property is fully set up "
                            "with sitemap submitted and URL inspection enabled."
                        ),
                    ))

            # Noindex detection — any page carrying noindex is invisible to Google
            robots_meta = soup.find("meta", attrs={"name": "robots"})
            if robots_meta:
                content = (robots_meta.get("content") or "").lower()
                if "noindex" in content:
                    findings.append(Finding(
                        title=f"Noindex tag prevents indexation: {path}",
                        description=(
                            "meta robots contains 'noindex' — Googlebot will deindex this page "
                            "or refuse to index it."
                        ),
                        severity="critical",
                        category="search-console",
                        url=url,
                        recommendation=(
                            "Remove 'noindex' from the robots meta tag unless this page is "
                            "intentionally excluded from the index (e.g. admin pages, duplicates)."
                        ),
                    ))

            # Canonical presence and self-reference
            canonical = soup.find("link", attrs={"rel": "canonical"})
            if not canonical:
                findings.append(Finding(
                    title=f"Missing canonical tag: {path}",
                    description="No canonical tag — search engines may select a different canonical and dilute signals.",
                    severity="warning",
                    category="search-console",
                    url=url,
                    recommendation=f"Add <link rel='canonical' href='{url}'> inside the <head> of this page.",
                ))
            else:
                href = (canonical.get("href") or "").rstrip("/")
                page_url_norm = url.rstrip("/")
                if href and href != page_url_norm and href.startswith("http"):
                    findings.append(Finding(
                        title=f"Non-self canonical on: {path}",
                        description=f"Canonical points to '{href}' instead of this page's URL.",
                        severity="info",
                        category="search-console",
                        url=url,
                        recommendation=(
                            "Verify this cross-page canonical is intentional. "
                            "Unintended non-self canonicals can prevent pages from ranking."
                        ),
                    ))

            # Rich result eligibility — check for key schema types
            schemas = crawler.extract_json_ld(soup)
            schema_types = set()
            for s in schemas:
                if "@graph" in s:
                    for item in (s["@graph"] if isinstance(s["@graph"], list) else [s["@graph"]]):
                        schema_types.add(item.get("@type", ""))
                else:
                    schema_types.add(s.get("@type", ""))

            if ("blog/post" in path or "guide" in path) and "BlogPosting" not in schema_types:
                findings.append(Finding(
                    title=f"BlogPosting schema missing on: {path}",
                    description=(
                        "Blog articles without BlogPosting schema miss rich result eligibility "
                        "and AI Overview citations."
                    ),
                    severity="warning",
                    category="search-console",
                    url=url,
                    recommendation=(
                        "Add BlogPosting JSON-LD with headline, datePublished, author, "
                        "and image properties."
                    ),
                ))

        return findings

    # ── Score computation ──────────────────────────────────────────────────

    def _compute_score(self, metadata: dict, findings: list[Finding]) -> int:
        if metadata.get("gsc_integrated"):
            score = 85  # start high — we have live data
            avg_pos = metadata.get("avg_position", 50)
            avg_ctr = metadata.get("avg_ctr", 0)
            if avg_pos > 30:
                score -= 20
            elif avg_pos > 15:
                score -= 10
            elif avg_pos > 7:
                score -= 4
            if avg_ctr < 1.0:
                score -= 12
            elif avg_ctr < 2.5:
                score -= 6
        else:
            score = 60  # lower baseline without live data

        return self.clamp_score(score, findings=findings)
