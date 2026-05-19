import requests
import logging
from base import BaseSEOSkill, Finding
from config import SITE_URL, PAGESPEED_API_KEY, CWV_THRESHOLDS

log = logging.getLogger(__name__)

KEY_PAGES = ["/", "/about.html", "/projects.html", "/blog/ai-ml-guide-2026.html"]
PAGESPEED_API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def call_pagespeed(url: str, strategy: str = "mobile") -> dict | None:
    if not PAGESPEED_API_KEY:
        return None
    params = {"url": url, "strategy": strategy, "key": PAGESPEED_API_KEY}
    try:
        r = requests.get(PAGESPEED_API, params=params, timeout=60)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        log.warning("PageSpeed API error: %s", e)
    return None


def extract_cwv(data: dict) -> dict:
    metrics = {}
    cats = data.get("lighthouseResult", {}).get("audits", {})

    lcp = cats.get("largest-contentful-paint", {})
    metrics["lcp_ms"] = lcp.get("numericValue", 0)

    cls = cats.get("cumulative-layout-shift", {})
    metrics["cls"] = cls.get("numericValue", 0)

    fid = cats.get("max-potential-fid", {})
    metrics["fid_ms"] = fid.get("numericValue", 0)

    inp = cats.get("interaction-to-next-paint", {})
    metrics["inp_ms"] = inp.get("numericValue", 0)

    ttfb = cats.get("server-response-time", {})
    metrics["ttfb_ms"] = ttfb.get("numericValue", 0)

    perf = data.get("lighthouseResult", {}).get("categories", {}).get("performance", {})
    metrics["performance_score"] = int((perf.get("score", 0) or 0) * 100)

    return metrics


def rate_metric(metric: str, value: float) -> str:
    t = CWV_THRESHOLDS.get(metric, {})
    if not t:
        return "unknown"
    if value <= t.get("good", float("inf")):
        return "good"
    elif value <= t.get("poor", float("inf")):
        return "needs-improvement"
    return "poor"


class Skill05CoreWebVitals(BaseSEOSkill):
    SKILL_ID = 5
    SKILL_NAME = "Core Web Vitals"

    def run(self, pages: list[dict]) -> SkillResult:
        from base import SkillResult
        findings = []
        cwv_data = []

        if not PAGESPEED_API_KEY:
            findings.append(Finding(
                title="PageSpeed API key not configured",
                description="PAGESPEED_API_KEY secret not set — CWV audit skipped.",
                severity="warning",
                category="configuration",
                url="",
                recommendation="Set PAGESPEED_API_KEY GitHub secret to enable Core Web Vitals monitoring.",
            ))
            return self.result(50, findings, {"api_available": False})

        scores = []
        for path in KEY_PAGES:
            url = SITE_URL + path
            for strategy in ["mobile", "desktop"]:
                data = call_pagespeed(url, strategy)
                if not data:
                    continue

                metrics = extract_cwv(data)
                cwv_data.append({"url": url, "strategy": strategy, **metrics})
                scores.append(metrics.get("performance_score", 0))

                lcp_rating = rate_metric("lcp", metrics.get("lcp_ms", 0))
                if lcp_rating == "poor":
                    findings.append(Finding(
                        title=f"Poor LCP on {path} ({strategy})",
                        description=f"LCP is {metrics['lcp_ms']:.0f}ms — above 4000ms threshold.",
                        severity="critical",
                        category="cwv",
                        url=url,
                        recommendation="Optimize the largest contentful element: use preload for hero images, reduce server response time, eliminate render-blocking resources.",
                    ))
                elif lcp_rating == "needs-improvement":
                    findings.append(Finding(
                        title=f"LCP needs improvement on {path} ({strategy})",
                        description=f"LCP is {metrics['lcp_ms']:.0f}ms — target under 2500ms.",
                        severity="warning",
                        category="cwv",
                        url=url,
                        recommendation="Optimize LCP: compress hero images, use WebP format, add preload hints.",
                    ))

                cls_rating = rate_metric("cls", metrics.get("cls", 0))
                if cls_rating == "poor":
                    findings.append(Finding(
                        title=f"Poor CLS on {path} ({strategy})",
                        description=f"CLS is {metrics['cls']:.3f} — above 0.25 threshold.",
                        severity="critical",
                        category="cwv",
                        url=url,
                        recommendation="Fix layout shifts: add size attributes to images/embeds, avoid inserting content above existing content.",
                    ))
                elif cls_rating == "needs-improvement":
                    findings.append(Finding(
                        title=f"CLS needs improvement on {path} ({strategy})",
                        description=f"CLS is {metrics['cls']:.3f} — target under 0.1.",
                        severity="warning",
                        category="cwv",
                        url=url,
                        recommendation="Reduce layout shifts by reserving space for dynamically loaded content.",
                    ))

                ttfb_rating = rate_metric("ttfb", metrics.get("ttfb_ms", 0))
                if ttfb_rating == "poor":
                    findings.append(Finding(
                        title=f"Poor TTFB on {path} ({strategy})",
                        description=f"TTFB is {metrics['ttfb_ms']:.0f}ms — above 1800ms.",
                        severity="warning",
                        category="cwv",
                        url=url,
                        recommendation="Improve TTFB: use a CDN, enable caching, optimize server configuration.",
                    ))

        avg_score = int(sum(scores) / len(scores)) if scores else 50
        score = self.clamp_score(avg_score, penalty_per_critical=10, penalty_per_warning=4, findings=findings)
        return self.result(score, findings, {"cwv_records": cwv_data, "avg_performance_score": avg_score})
