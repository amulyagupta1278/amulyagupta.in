import re
import xml.etree.ElementTree as ET
import crawler
from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL


class Skill02RobotsSitemap(BaseSEOSkill):
    SKILL_ID = 2
    SKILL_NAME = "Robots.txt & Sitemap Validation"

    def run(self, pages: list[dict]) -> SkillResult:
        findings = []

        # --- robots.txt ---
        rb = crawler.fetch(f"{SITE_URL}/robots.txt")
        if rb["status"] != 200:
            findings.append(Finding(
                title="robots.txt not accessible",
                description=f"HTTP {rb['status']} returned for /robots.txt.",
                severity="critical",
                category="robots",
                url=f"{SITE_URL}/robots.txt",
                recommendation="Create and serve a valid robots.txt file at the root of the domain.",
            ))
        else:
            rb_content = rb.get("html", "")
            if not rb_content.strip():
                findings.append(Finding(
                    title="robots.txt is empty",
                    description="robots.txt exists but contains no directives.",
                    severity="warning",
                    category="robots",
                    url=f"{SITE_URL}/robots.txt",
                    recommendation="Add appropriate Allow/Disallow directives and Sitemap reference.",
                ))
            else:
                if "sitemap:" not in rb_content.lower():
                    findings.append(Finding(
                        title="Missing Sitemap reference in robots.txt",
                        description="robots.txt does not include a Sitemap: directive.",
                        severity="warning",
                        category="robots",
                        url=f"{SITE_URL}/robots.txt",
                        recommendation="Add 'Sitemap: https://amulyagupta.in/sitemap.xml' to robots.txt.",
                    ))
                if re.search(r"disallow\s*:\s*/\s*$", rb_content, re.IGNORECASE | re.MULTILINE):
                    findings.append(Finding(
                        title="robots.txt disallows all crawling",
                        description="'Disallow: /' blocks all search engine crawlers.",
                        severity="critical",
                        category="robots",
                        url=f"{SITE_URL}/robots.txt",
                        recommendation="Remove or fix the 'Disallow: /' directive to allow search engine crawling.",
                    ))
                for bot in ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended"]:
                    if bot.lower() not in rb_content.lower():
                        findings.append(Finding(
                            title=f"Missing {bot} directive in robots.txt",
                            description=f"No explicit rule for {bot} found.",
                            severity="info",
                            category="ai-crawlers",
                            url=f"{SITE_URL}/robots.txt",
                            recommendation=f"Add 'User-agent: {bot}\\nAllow: /' to grant AI crawlers access.",
                        ))

        # --- sitemap.xml ---
        sm = crawler.fetch(f"{SITE_URL}/sitemap.xml")
        if sm["status"] != 200:
            findings.append(Finding(
                title="sitemap.xml not accessible",
                description=f"HTTP {sm['status']} returned for /sitemap.xml.",
                severity="critical",
                category="sitemap",
                url=f"{SITE_URL}/sitemap.xml",
                recommendation="Create a valid sitemap.xml and submit it to Google Search Console.",
            ))
        else:
            sm_content = sm.get("html", "")
            try:
                root = ET.fromstring(sm_content)
                ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
                urls = root.findall(".//sm:url/sm:loc", ns)
                url_texts = [u.text for u in urls if u.text]

                if len(url_texts) == 0:
                    findings.append(Finding(
                        title="sitemap.xml has no URLs",
                        description="Sitemap parsed but contains zero <url> entries.",
                        severity="critical",
                        category="sitemap",
                        url=f"{SITE_URL}/sitemap.xml",
                        recommendation="Add all site pages to the sitemap.",
                    ))
                else:
                    known_paths = ["/", "/about.html", "/projects.html",
                                   "/experience.html", "/amulya-gupta.html", "/contact.html",
                                   "/blog/index.html", "/blog/post-1-mlops-pipeline.html",
                                   "/blog/post-2-mlops-stack.html", "/blog/ai-ml-guide-2026.html",
                                   "/blog/post-2-rag-system.html"]
                    # Normalize sitemap URLs (strip trailing slash) for consistent comparison.
                    sitemap_normalized = {u.rstrip("/") for u in url_texts}
                    for path in known_paths:
                        full_url = SITE_URL + path
                        # Normalize the known URL the same way: strip trailing slash.
                        # This prevents false positives where "/" → "https://amulyagupta.in/"
                        # is not found in a set containing "https://amulyagupta.in" (stripped).
                        if full_url.rstrip("/") not in sitemap_normalized:
                            findings.append(Finding(
                                title=f"Page missing from sitemap: {path}",
                                description="This page exists on the site but is not listed in sitemap.xml.",
                                severity="warning",
                                category="sitemap",
                                url=full_url,
                                recommendation="Add this URL to sitemap.xml with appropriate lastmod and priority.",
                            ))

                    for u in url_texts:
                        if not u.startswith("https://"):
                            findings.append(Finding(
                                title=f"Non-HTTPS URL in sitemap: {u}",
                                description="Sitemap contains a non-HTTPS URL.",
                                severity="warning",
                                category="sitemap",
                                url=u,
                                recommendation="Use HTTPS URLs in sitemap.xml.",
                            ))

                    lastmods = root.findall(".//sm:url/sm:lastmod", ns)
                    if len(lastmods) < len(urls):
                        findings.append(Finding(
                            title="Some URLs missing lastmod in sitemap",
                            description=f"{len(urls) - len(lastmods)} URLs lack a <lastmod> date.",
                            severity="info",
                            category="sitemap",
                            url=f"{SITE_URL}/sitemap.xml",
                            recommendation="Add <lastmod> dates to all sitemap entries to help crawlers prioritize fresh content.",
                        ))

            except ET.ParseError as e:
                findings.append(Finding(
                    title="sitemap.xml is malformed XML",
                    description=f"XML parsing failed: {e}",
                    severity="critical",
                    category="sitemap",
                    url=f"{SITE_URL}/sitemap.xml",
                    recommendation="Fix XML syntax errors in sitemap.xml.",
                ))

        score = self.clamp_score(100, findings=findings)
        return self.result(score, findings)
