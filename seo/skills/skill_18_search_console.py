import json
import logging
import xml.etree.ElementTree as ET
import crawler
from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL, SITE_PAGES, GOOGLE_SEARCH_CONSOLE_CREDENTIALS

log = logging.getLogger(__name__)


def _try_gsc_api(site_url: str) -> dict:
    """Attempt live GSC API call when credentials are configured."""
    if not GOOGLE_SEARCH_CONSOLE_CREDENTIALS:
        return {}
    try:
        import google.auth
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds_data = json.loads(GOOGLE_SEARCH_CONSOLE_CREDENTIALS)
        creds = service_account.Credentials.from_service_account_info(
            creds_data,
            scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
        )
        service = build("searchconsole", "v1", credentials=creds, cache_discovery=False)

        # Query top pages by clicks (last 30 days)
        body = {
            "startDate": "2026-04-26",
            "endDate": "2026-05-26",
            "dimensions": ["page"],
            "rowLimit": 25,
        }
        response = (
            service.searchanalytics()
            .query(siteUrl=site_url, body=body)
            .execute()
        )
        return {"rows": response.get("rows", []), "error": None}
    except Exception as e:
        log.warning("GSC API call failed: %s", e)
        return {"error": str(e)}


class Skill18SearchConsole(BaseSEOSkill):
    SKILL_ID = 18
    SKILL_NAME = "Search Console Intelligence"

    def run(self, pages: list[dict]) -> SkillResult:
        findings = []
        score = 100

        # ── Live GSC data (when credentials configured) ───────────────────
        gsc_live = GOOGLE_SEARCH_CONSOLE_CREDENTIALS != ""
        if gsc_live:
            gsc_data = _try_gsc_api(SITE_URL)
            if gsc_data.get("error"):
                gsc_live = False
                score -= 5
                findings.append(Finding(
                    title="GSC API call failed",
                    description=f"Credentials set but API returned error: {gsc_data['error'][:200]}",
                    severity="warning",
                    category="search-console",
                    url="https://search.google.com/search-console",
                    recommendation="Verify the service account has Search Console property access.",
                ))
            elif gsc_data.get("rows"):
                rows = gsc_data["rows"]
                low_ctr = [r for r in rows if r.get("ctr", 1) < 0.02 and r.get("impressions", 0) > 100]
                for r in low_ctr[:3]:
                    findings.append(Finding(
                        title=f"Low CTR page: {r.get('keys', ['?'])[0].replace(SITE_URL,'')}",
                        description=f"CTR {r.get('ctr',0)*100:.1f}% with {r.get('impressions',0):,} impressions — underperforming title/meta.",
                        severity="warning",
                        category="search-console",
                        url=r.get("keys", [""])[0],
                        recommendation="Rewrite title tag and meta description to improve click-through rate.",
                    ))
        else:
            score -= 10
            findings.append(Finding(
                title="Search Console API not connected",
                description=(
                    "GOOGLE_SEARCH_CONSOLE_CREDENTIALS not set. Live click/impression data unavailable. "
                    "Running full static analysis instead."
                ),
                severity="info",
                category="configuration",
                url="https://search.google.com/search-console",
                recommendation=(
                    "1. Create a Google Cloud service account\n"
                    "2. Enable the Search Console API\n"
                    "3. Add the service account email as GSC property owner\n"
                    "4. Set GOOGLE_SEARCH_CONSOLE_CREDENTIALS GitHub Secret"
                ),
            ))

        # ── GSC verification tag ──────────────────────────────────────────
        verified = False
        home = next((p for p in pages if p["url"].rstrip("/") == SITE_URL.rstrip("/")), None)
        if home and home.get("soup"):
            soup = home["soup"]
            meta = (
                soup.find("meta", attrs={"name": "google-site-verification"})
                or soup.find("meta", attrs={"name": "google"})
            )
            if meta and meta.get("content"):
                verified = True
                findings.append(Finding(
                    title="GSC ownership verification confirmed",
                    description=f"Verification tag found: '{meta.get('content','')[:60]}'",
                    severity="info",
                    category="search-console",
                    url=SITE_URL,
                    recommendation="Verification confirmed. Ensure Search Console property is active and data is flowing.",
                ))
            else:
                score -= 15
                findings.append(Finding(
                    title="GSC verification tag missing",
                    description="No google-site-verification meta tag found on homepage.",
                    severity="warning",
                    category="search-console",
                    url=SITE_URL,
                    recommendation="Add <meta name=\"google-site-verification\" content=\"...\"> from Google Search Console.",
                ))

        # ── Sitemap accessibility and quality ─────────────────────────────
        sm = crawler.fetch(f"{SITE_URL}/sitemap.xml")
        if sm["status"] != 200:
            score -= 20
            findings.append(Finding(
                title="sitemap.xml not accessible — cannot submit to GSC",
                description=f"sitemap.xml returned HTTP {sm['status']}.",
                severity="critical",
                category="search-console",
                url=f"{SITE_URL}/sitemap.xml",
                recommendation="Fix sitemap.xml accessibility. GSC requires a valid sitemap for indexation monitoring.",
            ))
        else:
            sm_content = sm.get("html", "")
            try:
                root = ET.fromstring(sm_content)
                ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
                url_els = root.findall(".//sm:url/sm:loc", ns)
                lastmod_els = root.findall(".//sm:url/sm:lastmod", ns)
                url_count = len(url_els)

                findings.append(Finding(
                    title=f"Sitemap accessible: {url_count} URLs",
                    description=f"sitemap.xml is valid XML with {url_count} URLs and {len(lastmod_els)} lastmod dates.",
                    severity="info",
                    category="search-console",
                    url=f"{SITE_URL}/sitemap.xml",
                    recommendation="Submit https://amulyagupta.in/sitemap.xml in Google Search Console → Sitemaps if not already done.",
                ))

                if len(lastmod_els) < url_count:
                    findings.append(Finding(
                        title=f"{url_count - len(lastmod_els)} sitemap URLs missing lastmod",
                        description="GSC uses lastmod to prioritize recrawl scheduling. Missing dates reduce crawl efficiency.",
                        severity="info",
                        category="search-console",
                        url=f"{SITE_URL}/sitemap.xml",
                        recommendation="Add <lastmod>YYYY-MM-DD</lastmod> to every <url> entry in sitemap.xml.",
                    ))
            except ET.ParseError as e:
                score -= 20
                findings.append(Finding(
                    title="sitemap.xml is malformed XML",
                    description=f"GSC will reject this sitemap. Parse error: {e}",
                    severity="critical",
                    category="search-console",
                    url=f"{SITE_URL}/sitemap.xml",
                    recommendation="Fix XML syntax. Validate at https://validator.w3.org/feed/",
                ))

        # ── robots.txt GSC-critical checks ───────────────────────────────
        rb = crawler.fetch(f"{SITE_URL}/robots.txt")
        if rb["status"] == 200:
            rb_content = rb.get("html", "")
            if "disallow: /" in rb_content.lower() and "allow: /" not in rb_content.lower():
                score -= 30
                findings.append(Finding(
                    title="robots.txt may block Googlebot",
                    description="Disallow: / without a preceding Allow: / blocks all crawling.",
                    severity="critical",
                    category="search-console",
                    url=f"{SITE_URL}/robots.txt",
                    recommendation="Remove 'Disallow: /' or add 'Allow: /' before it.",
                ))
        else:
            score -= 10
            findings.append(Finding(
                title="robots.txt inaccessible",
                description=f"HTTP {rb['status']} — GSC will report crawl errors.",
                severity="warning",
                category="search-console",
                url=f"{SITE_URL}/robots.txt",
                recommendation="Ensure robots.txt is served at the root with a 200 status.",
            ))

        # ── Per-page indexation signals ───────────────────────────────────
        non_indexable = []
        missing_canonical = []
        noindex_intentional = {"/privacy.html"}

        for page in pages:
            url = page["url"]
            path = url.replace(SITE_URL, "")
            soup = page.get("soup")
            if not soup or page.get("status") != 200:
                continue

            meta = crawler.extract_meta(soup)
            robots_meta = meta.get("robots", "").lower()

            if "noindex" in robots_meta and path not in noindex_intentional:
                score -= 10
                non_indexable.append(path)
                findings.append(Finding(
                    title=f"Unintended noindex: {path}",
                    description=f"GSC will not index this page. Meta robots: '{robots_meta}'",
                    severity="critical",
                    category="search-console",
                    url=url,
                    recommendation="Remove noindex from meta robots unless intentionally excluding from Google.",
                ))

            canon = soup.find("link", rel="canonical")
            if not canon:
                missing_canonical.append(path)
            elif canon.get("href", "").rstrip("/") != url.rstrip("/"):
                findings.append(Finding(
                    title=f"Canonical points away: {path}",
                    description=f"Canonical → {canon.get('href','')} — GSC will defer to that URL.",
                    severity="info",
                    category="search-console",
                    url=url,
                    recommendation="Verify cross-page canonical is intentional. GSC attributes all signals to the canonical.",
                ))

        if missing_canonical:
            score -= 5
            findings.append(Finding(
                title=f"{len(missing_canonical)} pages missing canonical tag",
                description=f"Pages: {', '.join(missing_canonical[:5])}",
                severity="warning",
                category="search-console",
                url=SITE_URL,
                recommendation="Add <link rel=\"canonical\" href=\"...\"> to every page to prevent duplicate content issues in GSC.",
            ))

        # ── HTTPS compliance ──────────────────────────────────────────────
        http_pages = [p for p in pages if p["url"].startswith("http://")]
        if http_pages:
            score -= 15
            findings.append(Finding(
                title=f"{len(http_pages)} pages served over HTTP",
                description="Google requires HTTPS. Non-HTTPS pages may not rank.",
                severity="critical",
                category="search-console",
                url=http_pages[0]["url"],
                recommendation="Enforce HTTPS across all pages. Add HSTS header for full compliance.",
            ))

        # ── Render-blocking resources (impacts CWV in GSC) ───────────────
        blocking_pages = []
        for page in pages:
            soup = page.get("soup")
            if not soup or page.get("status") != 200:
                continue
            blocking = [
                s for s in soup.find_all("script", src=True)
                if not s.get("defer") and not s.get("async")
                and "analytics" not in s.get("src", "").lower()
            ]
            if len(blocking) > 3:
                blocking_pages.append(page["url"].replace(SITE_URL, ""))

        if blocking_pages:
            findings.append(Finding(
                title=f"Render-blocking scripts on {len(blocking_pages)} page(s)",
                description=f"Pages: {', '.join(blocking_pages[:3])} — impacts Core Web Vitals in GSC.",
                severity="warning",
                category="search-console",
                url=SITE_URL,
                recommendation="Add defer or async to non-critical <script> tags to improve LCP scores reported in GSC.",
            ))

        # ── Structured data richness (GSC rich results eligibility) ──────
        schema_pages = 0
        for page in pages:
            soup = page.get("soup")
            if soup and soup.find("script", type="application/ld+json"):
                schema_pages += 1

        schema_pct = int(schema_pages / len(pages) * 100) if pages else 0
        if schema_pct < 50:
            score -= 10
            findings.append(Finding(
                title=f"Low schema coverage: {schema_pct}% of pages",
                description=f"Only {schema_pages}/{len(pages)} pages have JSON-LD structured data.",
                severity="warning",
                category="search-console",
                url=SITE_URL,
                recommendation="Add structured data to all key pages. GSC shows Rich Results eligibility in the Enhancement reports.",
            ))
        else:
            findings.append(Finding(
                title=f"Good schema coverage: {schema_pct}% of pages",
                description=f"{schema_pages}/{len(pages)} pages have JSON-LD structured data — eligible for GSC Rich Results.",
                severity="info",
                category="search-console",
                url=SITE_URL,
                recommendation="Test schema with Google Rich Results Test. Monitor GSC → Enhancements for errors.",
            ))

        score = self.clamp_score(max(0, score), findings=findings)
        return self.result(score, findings, {
            "gsc_integrated": gsc_live,
            "gsc_verified": verified,
            "non_indexable_pages": non_indexable,
            "schema_coverage_pct": schema_pct,
        })
