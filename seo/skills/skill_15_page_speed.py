import requests
import logging
from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL, PAGESPEED_API_KEY

log = logging.getLogger(__name__)
PAGESPEED_API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
AUDIT_PAGES = ["/", "/projects.html", "/blog/ai-ml-guide-2026.html"]


def run_pagespeed(url: str, strategy: str = "mobile") -> dict | None:
    if not PAGESPEED_API_KEY:
        return None
    try:
        r = requests.get(PAGESPEED_API, params={"url": url, "strategy": strategy, "key": PAGESPEED_API_KEY}, timeout=60)
        return r.json() if r.status_code == 200 else None
    except Exception as e:
        log.warning("PageSpeed error: %s", e)
        return None


OPPORTUNITY_MAP = {
    "render-blocking-resources": ("Render-blocking resources", "critical"),
    "unused-css-rules": ("Unused CSS", "warning"),
    "unused-javascript": ("Unused JavaScript", "warning"),
    "uses-optimized-images": ("Unoptimized images", "warning"),
    "uses-webp-images": ("Images not in WebP/AVIF", "info"),
    "offscreen-images": ("Offscreen images not deferred", "warning"),
    "uses-text-compression": ("Text compression not enabled", "warning"),
    "uses-long-cache-ttl": ("Long cache TTL not set", "info"),
    "efficient-animated-content": ("Animated content inefficiency", "info"),
    "uses-rel-preconnect": ("Missing preconnect for origins", "info"),
    "font-display": ("Font display not optimized", "info"),
    "third-party-summary": ("Third-party code impact", "warning"),
    "bootup-time": ("JavaScript execution time", "warning"),
    "mainthread-work-breakdown": ("Main thread work", "warning"),
}


class Skill15PageSpeed(BaseSEOSkill):
    SKILL_ID = 15
    SKILL_NAME = "Page Speed Deep Dive"

    def run(self, pages: list[dict]) -> SkillResult:
        findings = []

        if not PAGESPEED_API_KEY:
            findings.append(Finding(
                title="PageSpeed API key not configured",
                description="PAGESPEED_API_KEY secret not set — detailed speed audit skipped.",
                severity="warning",
                category="configuration",
                url="",
                recommendation="Set PAGESPEED_API_KEY in GitHub Secrets to enable PageSpeed audits.",
            ))
            return self.result(50, findings)

        scores = []
        for path in AUDIT_PAGES:
            url = SITE_URL + path
            for strategy in ["mobile", "desktop"]:
                data = run_pagespeed(url, strategy)
                if not data:
                    continue

                lr = data.get("lighthouseResult", {})
                perf_score = int((lr.get("categories", {}).get("performance", {}).get("score", 0) or 0) * 100)
                scores.append(perf_score)

                audits = lr.get("audits", {})

                for audit_id, (label, sev) in OPPORTUNITY_MAP.items():
                    audit = audits.get(audit_id, {})
                    if audit.get("score") is not None and audit.get("score", 1) < 0.9:
                        savings = audit.get("details", {}).get("overallSavingsMs", 0)
                        desc = audit.get("description", "")[:200]
                        title = f"{label} on {path} ({strategy})"
                        if savings:
                            title += f" — save ~{savings:.0f}ms"
                        findings.append(Finding(
                            title=title,
                            description=desc,
                            severity=sev if perf_score < 50 else ("warning" if sev == "critical" else "info"),
                            category="performance",
                            url=url,
                            recommendation=audit.get("title", ""),
                        ))

                if perf_score < 50:
                    findings.append(Finding(
                        title=f"Poor performance score: {path} ({strategy}) — {perf_score}/100",
                        description=f"PageSpeed score of {perf_score} is below the good threshold (90+).",
                        severity="critical",
                        category="performance",
                        url=url,
                        recommendation="Address the opportunities above to improve the performance score.",
                    ))
                elif perf_score < 90:
                    findings.append(Finding(
                        title=f"Performance needs improvement: {path} ({strategy}) — {perf_score}/100",
                        description=f"PageSpeed score of {perf_score} should target 90+.",
                        severity="warning",
                        category="performance",
                        url=url,
                        recommendation="Address the listed opportunities to reach a 90+ performance score.",
                    ))

        avg_score = int(sum(scores) / len(scores)) if scores else 50
        score = self.clamp_score(avg_score, penalty_per_critical=10, penalty_per_warning=4, findings=findings)
        return self.result(score, findings, {"avg_performance_score": avg_score})
