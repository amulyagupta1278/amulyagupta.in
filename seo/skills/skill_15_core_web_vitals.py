"""Skill 15 — Core Web Vitals Analysis"""
import os
from .base import BaseSkill


class CoreWebVitalsSkill(BaseSkill):
    name = "Core Web Vitals Analysis"
    priority = "P2"
    skill_number = 15

    PSI_API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

    def run(self) -> dict:
        findings = []
        api_key = os.environ.get("GOOGLE_PAGESPEED_API_KEY", "")

        if api_key:
            findings.extend(self._check_via_api(api_key))
        else:
            findings.extend(self._check_heuristically())

        if not findings:
            return self.result([], "Core Web Vitals: All signals are within acceptable ranges.", [],
                               ["Set GOOGLE_PAGESPEED_API_KEY secret for real CWV data from Google's API.",
                                "Monitor CWV in Google Search Console under 'Core Web Vitals' report."])

        return self.result(findings, f"CWV audit: {len(findings)} issue(s) found.", [],
                           ["Target: LCP < 2.5s, CLS < 0.1, FID/INP < 200ms.",
                            "Use Chrome DevTools Performance panel to diagnose LCP elements."])

    def _check_via_api(self, api_key: str) -> list:
        findings = []
        import requests
        url = f"{self.PSI_API}?url={self.site_url}&strategy=mobile&key={api_key}"
        try:
            r = requests.get(url, timeout=30)
            if r.status_code != 200:
                return self._check_heuristically()
            data = r.json()
            cats = data.get("lighthouseResult", {}).get("categories", {})
            perf_score = int((cats.get("performance", {}).get("score", 1) or 1) * 100)
            audits = data.get("lighthouseResult", {}).get("audits", {})

            lcp = audits.get("largest-contentful-paint", {})
            cls = audits.get("cumulative-layout-shift", {})
            fid = audits.get("interactive", {})

            lcp_val = lcp.get("displayValue", "N/A")
            cls_val = cls.get("displayValue", "N/A")
            fid_val = fid.get("displayValue", "N/A")

            if perf_score < 90:
                severity = "critical" if perf_score < 50 else "warning"
                findings.append(self.finding(
                    "CWV_001", f"Mobile performance score: {perf_score}/100", severity, "P2",
                    f"Google PageSpeed Insights: Performance={perf_score}. LCP={lcp_val}, CLS={cls_val}, TTI={fid_val}",
                    "Optimize images, reduce JavaScript, use lazy loading, and minify CSS.",
                    f"Performance score {perf_score} means Google may downrank this site in mobile results.",
                    pages=[self.site_url]
                ))

            # Check specific audits for critical issues
            blocking = audits.get("render-blocking-resources", {})
            if blocking.get("score", 1) < 0.9:
                items = blocking.get("details", {}).get("items", [])
                urls = [i.get("url", "")[:60] for i in items[:3]]
                findings.append(self.finding(
                    "CWV_002", f"Render-blocking resources detected", "warning", "P2",
                    f"Resources blocking first paint: {', '.join(urls)}",
                    "Add defer/async to JS, and use preload for critical CSS.",
                    "Render-blocking resources directly increase LCP and FCP.",
                    pages=[self.site_url]
                ))

            unused_js = audits.get("unused-javascript", {})
            if unused_js.get("score", 1) is not None and (unused_js.get("score") or 1) < 0.9:
                savings = unused_js.get("details", {}).get("overallSavingsBytes", 0)
                if savings > 20000:
                    findings.append(self.finding(
                        "CWV_003", f"Unused JavaScript: {savings // 1024}KB could be removed", "info", "P2",
                        "Lighthouse detected significant unused JavaScript.",
                        "Audit main.js for dead code and remove unused library imports.",
                        pages=[self.site_url]
                    ))

        except Exception as e:
            findings.append(self.finding(
                "CWV_004", f"PageSpeed API error: {e}", "info", "P2",
                "Could not retrieve CWV data from PageSpeed Insights API.",
                "Verify your GOOGLE_PAGESPEED_API_KEY secret is valid.",
            ))
        return findings

    def _check_heuristically(self) -> list:
        findings = []
        for f in self.html_files:
            content = f.read_text(encoding="utf-8")
            page = str(f.relative_to(self.site_root))
            soup = self.parse(f)

            # Count render-blocking scripts in head
            head = soup.find("head")
            if head:
                blocking_scripts = [
                    s for s in head.find_all("script", src=True)
                    if not s.get("defer") and not s.get("async")
                    and "analytics" not in s.get("src", "").lower()
                ]
                if blocking_scripts:
                    findings.append(self.finding(
                        "CWV_010", f"{len(blocking_scripts)} potentially blocking script(s) in head: {page}",
                        "warning", "P2",
                        f"Scripts without defer/async in <head> block HTML parsing.",
                        "Add defer attribute to non-critical scripts, or move to end of <body>.",
                        "Blocking scripts increase Time to First Byte and LCP.",
                        pages=[page]
                    ))

            # Check for non-lazy images
            imgs = soup.find_all("img")
            non_lazy = [img for img in imgs if not img.get("loading")]
            if len(non_lazy) > 2:
                findings.append(self.finding(
                    "CWV_011", f"{len(non_lazy)} image(s) without lazy loading: {page}", "info", "P2",
                    "Images without loading='lazy' are all loaded eagerly, increasing initial page weight.",
                    "Add loading='lazy' to all images below the fold.",
                    "Lazy loading can reduce initial page load by 30-50% for image-heavy pages.",
                    pages=[page]
                ))

            # Google Fonts performance
            gf_links = [l for l in soup.find_all("link", rel="stylesheet")
                        if "fonts.googleapis.com" in l.get("href", "")]
            preconnect = [l for l in soup.find_all("link", rel="preconnect")
                          if "fonts.googleapis.com" in l.get("href", "")]
            if gf_links and not preconnect:
                findings.append(self.finding(
                    "CWV_012", f"Google Fonts without preconnect on {page}", "info", "P2",
                    "Loading Google Fonts without a preconnect hint adds ~100ms DNS lookup time.",
                    "Add <link rel='preconnect' href='https://fonts.googleapis.com'> before the fonts link.",
                    pages=[page]
                ))

        return findings
