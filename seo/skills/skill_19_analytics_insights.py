import re
import crawler
from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL

GA4_PATTERN = re.compile(r'G-[A-Z0-9]{8,}')
UA_PATTERN = re.compile(r'UA-\d{6,}-\d+')
GTM_PATTERN = re.compile(r'GTM-[A-Z0-9]{6,}')
GTAG_PATTERN = re.compile(r'gtag\.js|googletagmanager\.com/gtag', re.IGNORECASE)
ANALYTICS_JS_PATTERN = re.compile(r'analytics\.js|google-analytics\.com/analytics', re.IGNORECASE)
CONVERSION_PATTERN = re.compile(r'gtag\s*\(\s*[\'"]event[\'"]\s*,|fbq\s*\(|_gaq\.push|dataLayer\.push', re.IGNORECASE)
COOKIE_CONSENT_PATTERN = re.compile(
    r'cookie.?consent|cookie.?banner|cookie.?notice|cookiebot|onetrust|gdpr|ccpa|cookie.?policy'
    r'|privacy.?notice|\.cookiebanner|#cookie|cookielawinfo',
    re.IGNORECASE
)
PRIVACY_LINK_PATTERN = re.compile(r'privacy.?policy|privacy.?notice|cookie.?policy', re.IGNORECASE)


class Skill19AnalyticsInsights(BaseSEOSkill):
    SKILL_ID = 19
    SKILL_NAME = "Analytics Insights"

    def run(self, pages: list[dict]) -> SkillResult:
        findings = []

        # Check analytics implementation on homepage
        home = next((p for p in pages if p["url"].rstrip("/") == SITE_URL.rstrip("/")), None)
        ga4_detected = False
        gtm_detected = False
        gtag_detected = False

        if home:
            html = home.get("html", "")
            soup = home.get("soup")

            ga4_ids = GA4_PATTERN.findall(html)
            ua_ids = UA_PATTERN.findall(html)
            gtm_ids = GTM_PATTERN.findall(html)
            gtag_script = bool(GTAG_PATTERN.search(html))
            analytics_js = bool(ANALYTICS_JS_PATTERN.search(html))

            ga4_detected = bool(ga4_ids)
            gtm_detected = bool(gtm_ids)
            gtag_detected = gtag_script

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

            # gtag.js vs analytics.js check
            if gtag_script:
                findings.append(Finding(
                    title="gtag.js detected",
                    description="Global site tag (gtag.js) found — modern analytics/ads tagging approach.",
                    severity="info",
                    category="analytics",
                    url=SITE_URL,
                    recommendation="Confirm all desired GA4 events and conversion actions are firing via gtag.js.",
                ))
            if analytics_js:
                findings.append(Finding(
                    title="Legacy analytics.js detected",
                    description="analytics.js (Universal Analytics library) found — this is deprecated.",
                    severity="critical",
                    category="analytics",
                    url=SITE_URL,
                    recommendation="Replace analytics.js with the GA4 gtag.js snippet.",
                ))

            # Check for lazy-loaded analytics (performance best practice)
            if (ga4_ids or gtm_ids) and soup:
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

            # Conversion tracking check
            if CONVERSION_PATTERN.search(html):
                findings.append(Finding(
                    title="Conversion/event tracking code detected",
                    description="Custom event tracking (gtag event, dataLayer.push, or pixel) found on homepage.",
                    severity="info",
                    category="analytics",
                    url=SITE_URL,
                    recommendation="Verify conversion events are mapped to GA4 goals and reporting correctly.",
                ))
            elif ga4_ids or gtm_ids:
                findings.append(Finding(
                    title="No conversion tracking events detected",
                    description="Analytics is present but no event/conversion tracking calls found on homepage.",
                    severity="warning",
                    category="analytics",
                    url=SITE_URL,
                    recommendation="Add gtag('event', ...) calls or GTM triggers for key interactions: form submits, CTA clicks, downloads.",
                ))

            # Cookie consent / privacy compliance check
            cookie_consent_found = bool(COOKIE_CONSENT_PATTERN.search(html))
            if cookie_consent_found:
                findings.append(Finding(
                    title="Cookie consent mechanism detected",
                    description="Cookie consent / GDPR notice found on homepage.",
                    severity="info",
                    category="compliance",
                    url=SITE_URL,
                    recommendation="Ensure the consent banner fires before analytics loads (consent mode v2 for GA4).",
                ))
            else:
                # Check if there's a privacy policy link as a softer signal
                privacy_link = bool(PRIVACY_LINK_PATTERN.search(html))
                if privacy_link:
                    findings.append(Finding(
                        title="Privacy policy linked but no consent banner detected",
                        description="A privacy/cookie policy link exists but no consent banner was found.",
                        severity="warning",
                        category="compliance",
                        url=SITE_URL,
                        recommendation="If targeting EU/CA users, add a cookie consent banner and implement GA4 Consent Mode v2.",
                    ))
                else:
                    findings.append(Finding(
                        title="No cookie consent or privacy notice detected",
                        description="No cookie consent banner or privacy policy link found on homepage.",
                        severity="warning",
                        category="compliance",
                        url=SITE_URL,
                        recommendation="Add a cookie consent notice and link to a privacy policy to comply with GDPR/CCPA.",
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

        # Check for conversion opportunities on non-home pages
        contact_pages = [p for p in pages if "contact" in p.get("url", "").lower() and p.get("status") == 200]
        for page in contact_pages:
            html = page.get("html", "")
            if not CONVERSION_PATTERN.search(html):
                findings.append(Finding(
                    title=f"No conversion tracking on contact page",
                    description="Contact page has no event tracking — form submissions won't be recorded.",
                    severity="warning",
                    category="analytics",
                    url=page["url"],
                    recommendation="Add a gtag('event','generate_lead') or GTM trigger on form submission.",
                ))

        # Scoring: base on what's detectable without API access
        # Start from 70 (can't fully audit without API access)
        critical_count = sum(1 for f in findings if f.severity == "critical")
        warning_count = sum(1 for f in findings if f.severity == "warning")
        crit_deduction = min(40, critical_count * 10)
        warn_deduction = min(20, warning_count * 4)
        score = max(0, 70 - crit_deduction - warn_deduction)

        return self.result(score, findings, {
            "ga4_detected": ga4_detected,
            "gtm_detected": gtm_detected,
            "gtag_detected": gtag_detected,
            "pages_without_analytics": len(pages_without_analytics),
        })
