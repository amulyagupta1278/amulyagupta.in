"""Skill 01 — robots.txt Integrity"""
from pathlib import Path
from .base import BaseSkill


class RobotsTxtSkill(BaseSkill):
    name = "robots.txt Integrity"
    priority = "P1"
    skill_number = 1

    REQUIRED_BOTS = ["GPTBot", "ClaudeBot", "Google-Extended", "PerplexityBot", "Googlebot"]

    def run(self) -> dict:
        findings = []
        auto_fixes = []
        robots_path = self.site_root / "robots.txt"

        if not robots_path.exists():
            findings.append(self.finding(
                "ROBOTS_001", "robots.txt missing", "critical", "P1",
                "No robots.txt file found at site root.",
                "Create a robots.txt allowing all crawlers and referencing the sitemap.",
                "Crawlers may behave unpredictably; sitemap won't be auto-discovered."
            ))
            self._create_robots(robots_path, auto_fixes)
            return self.result(findings, "robots.txt was missing and has been created.", auto_fixes)

        content = robots_path.read_text(encoding="utf-8")
        lines = [l.strip() for l in content.splitlines()]

        # Check sitemap reference
        if not any(l.lower().startswith("sitemap:") for l in lines):
            findings.append(self.finding(
                "ROBOTS_002", "Sitemap not referenced in robots.txt", "warning", "P1",
                "robots.txt does not include a Sitemap: directive.",
                "Add 'Sitemap: https://amulyagupta.in/sitemap.xml' to robots.txt.",
                "Search engines won't auto-discover your sitemap from robots.txt.",
            ))
            self._add_sitemap(robots_path, content, auto_fixes)
            content = robots_path.read_text(encoding="utf-8")

        # Check for disallow of important pages
        disallow_all = any(l.lower() == "disallow: /" for l in lines)
        if disallow_all:
            findings.append(self.finding(
                "ROBOTS_003", "CRITICAL: All pages disallowed", "critical", "P1",
                "robots.txt contains 'Disallow: /' which blocks all crawlers from all pages.",
                "Remove or scope the Disallow: / directive immediately.",
                "Complete deindexation risk — no pages will be crawled or indexed."
            ))

        # Check AI bot allowances
        missing_bots = [b for b in self.REQUIRED_BOTS if b.lower() not in content.lower()]
        if missing_bots:
            findings.append(self.finding(
                "ROBOTS_004", f"AI/major bots not explicitly allowed: {', '.join(missing_bots)}",
                "warning", "P1",
                f"The following important crawlers are not explicitly mentioned: {', '.join(missing_bots)}.",
                "Add explicit Allow entries for each AI crawler to ensure AI-search visibility.",
                "Missing AI-bot entries may reduce AI-search discoverability (Perplexity, ChatGPT, Bing Copilot).",
            ))
            self._add_bots(robots_path, missing_bots, auto_fixes)

        # Check crawl-delay (not recommended for most sites)
        if any(l.lower().startswith("crawl-delay:") for l in lines):
            findings.append(self.finding(
                "ROBOTS_005", "Crawl-Delay directive present", "info", "P1",
                "crawl-delay may slow Googlebot's indexation of your site.",
                "Remove Crawl-Delay unless you have a specific need — Google ignores it anyway.",
                "Minor: may slightly reduce crawl frequency on other engines."
            ))

        if not findings:
            return self.result([], "robots.txt is well-configured with sitemap reference and AI bot allowances.", auto_fixes,
                               ["Consider reviewing robots.txt every 90 days as new AI crawlers emerge."])

        health_summary = f"robots.txt reviewed. {len(findings)} issue(s) found. {len(auto_fixes)} auto-fix(es) applied."
        return self.result(findings, health_summary, auto_fixes)

    def _create_robots(self, path: Path, auto_fixes: list):
        content = (
            "User-agent: *\nAllow: /\n\n"
            "User-agent: GPTBot\nAllow: /\n\n"
            "User-agent: ClaudeBot\nAllow: /\n\n"
            "User-agent: Google-Extended\nAllow: /\n\n"
            "User-agent: PerplexityBot\nAllow: /\n\n"
            "User-agent: Googlebot\nAllow: /\n\n"
            "Sitemap: https://amulyagupta.in/sitemap.xml\n"
        )
        path.write_text(content, encoding="utf-8")
        auto_fixes.append("Created robots.txt with full crawler allowances and sitemap reference.")

    def _add_sitemap(self, path: Path, content: str, auto_fixes: list):
        new_content = content.rstrip() + "\n\nSitemap: https://amulyagupta.in/sitemap.xml\n"
        path.write_text(new_content, encoding="utf-8")
        auto_fixes.append("Added Sitemap directive to robots.txt.")

    def _add_bots(self, path: Path, bots: list, auto_fixes: list):
        content = path.read_text(encoding="utf-8")
        additions = "\n".join(f"User-agent: {b}\nAllow: /" for b in bots)
        content = content.rstrip() + "\n\n" + additions + "\n"
        path.write_text(content, encoding="utf-8")
        auto_fixes.append(f"Added explicit Allow entries for: {', '.join(bots)}.")
