"""Skill 10 — Redirect Chain Analysis"""
from .base import BaseSkill


class RedirectsSkill(BaseSkill):
    name = "Redirect Chain Analysis"
    priority = "P3"
    skill_number = 10

    def run(self) -> dict:
        findings = []
        import requests as req

        # Test key URLs from sitemap
        test_urls = [
            f"{self.site_url}/",
            f"{self.site_url}/about.html",
            f"{self.site_url}/projects.html",
            f"{self.site_url}/experience.html",
            f"{self.site_url}/contact.html",
            f"{self.site_url}/blog/",
            f"{self.site_url}/blog/post-1-mlops-pipeline.html",
            f"{self.site_url}/blog/ai-ml-guide-2026.html",
        ]

        chains = []
        for url in test_urls:
            try:
                r = req.get(url, timeout=10, allow_redirects=True,
                            headers={"User-Agent": "SEOAuditBot/1.0"})
                history = r.history
                if len(history) > 1:
                    chain = " → ".join([str(h.status_code) + " " + h.url for h in history] + [r.url])
                    chains.append((url, len(history), chain))
                elif len(history) == 1 and r.history[0].status_code in [301, 302]:
                    if r.history[0].url != r.url:
                        chains.append((url, 1, f"{r.history[0].status_code} {r.history[0].url} → {r.url}"))

                # Check for 404s
                if r.status_code == 404:
                    findings.append(self.finding(
                        "REDIR_001", f"404 Not Found: {url}", "critical", "P3",
                        f"URL returns 404: {url}",
                        "Add this URL to sitemap only if the page exists. If removed, add a redirect.",
                        "404 pages in sitemap waste crawl budget and signal poor site maintenance.",
                        pages=[url]
                    ))

            except Exception as e:
                findings.append(self.finding(
                    "REDIR_002", f"Network error checking {url}", "warning", "P3",
                    f"Could not reach {url}: {e}",
                    "Verify the URL is accessible and that DNS/hosting is configured correctly.",
                    pages=[url]
                ))

        # Report redirect chains > 1 hop
        multi_hop = [(u, n, c) for u, n, c in chains if n > 1]
        if multi_hop:
            for url, hops, chain in multi_hop[:5]:
                findings.append(self.finding(
                    "REDIR_003", f"Redirect chain ({hops} hops): {url}", "warning", "P3",
                    f"Chain: {chain}",
                    "Collapse redirect chains to a single direct redirect. Update all internal links to point to the final URL.",
                    "Each redirect hop adds ~100–300ms latency and reduces PageRank passed.",
                    pages=[url]
                ))

        single_hops = [(u, n, c) for u, n, c in chains if n == 1]
        if single_hops:
            for url, _, chain in single_hops[:3]:
                findings.append(self.finding(
                    "REDIR_004", f"Single redirect: {url}", "info", "P3",
                    f"Redirect: {chain}",
                    "Update internal links to point directly to the final destination URL.",
                    "Single redirects are acceptable but add unnecessary latency.",
                    pages=[url]
                ))

        if not findings:
            return self.result([], f"All {len(test_urls)} key URLs load directly with no redirect chains.",
                               [], ["Audit redirects whenever you restructure URLs or move pages."])

        return self.result(findings, f"Redirect audit: {len(findings)} issue(s) across {len(test_urls)} URLs.")
