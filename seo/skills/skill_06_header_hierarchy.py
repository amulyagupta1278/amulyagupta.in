"""Skill 06 — Header Hierarchy Analysis"""
from .base import BaseSkill


class HeaderHierarchySkill(BaseSkill):
    name = "Header Hierarchy Structure"
    priority = "P6"
    skill_number = 6

    def run(self) -> dict:
        findings = []

        for f in self.html_files:
            soup = self.parse(f)
            page = str(f.relative_to(self.site_root))
            body = soup.find("body")
            if not body:
                continue

            headers = body.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
            h1s = [h for h in headers if h.name == "h1"]

            # Multiple H1
            if len(h1s) > 1:
                findings.append(self.finding(
                    "HEADER_001", f"Multiple H1 tags ({len(h1s)}): {page}", "warning", "P6",
                    f"{page} has {len(h1s)} H1 tags. Only one H1 should exist per page.",
                    "Demote secondary H1s to H2. The single H1 should be the primary topic statement.",
                    "Multiple H1s dilute topical signal and confuse crawlers about the primary topic.",
                    pages=[page]
                ))

            # Missing H1
            if len(h1s) == 0:
                findings.append(self.finding(
                    "HEADER_002", f"No H1 tag: {page}", "critical", "P6",
                    f"{page} has no H1 heading.",
                    "Add an H1 that includes the primary keyword and describes the page topic.",
                    "Missing H1 is a significant on-page SEO weakness. Google uses H1 as a primary relevance signal.",
                    pages=[page]
                ))
                continue

            # Check hierarchy skips
            levels = [int(h.name[1]) for h in headers]
            skips = []
            for i in range(1, len(levels)):
                if levels[i] > levels[i - 1] + 1:
                    skips.append(f"H{levels[i-1]}→H{levels[i]}")
            if skips:
                findings.append(self.finding(
                    "HEADER_003", f"Header hierarchy skip on {page}: {', '.join(skips)}", "warning", "P6",
                    f"Headers jump levels ({', '.join(skips)}) which breaks semantic structure.",
                    "Ensure headers increment by 1 level at a time: H1→H2→H3, not H1→H3.",
                    "Hierarchy skips reduce semantic clarity for both crawlers and assistive technologies.",
                    pages=[page]
                ))

            # H2 presence check (for content pages)
            h2s = [h for h in headers if h.name == "h2"]
            if len(h2s) == 0 and len(headers) > 1:
                findings.append(self.finding(
                    "HEADER_004", f"No H2 subheadings: {page}", "info", "P6",
                    f"{page} has an H1 but no H2 subheadings to structure the content.",
                    "Add H2 subheadings for major content sections to improve readability and crawlability.",
                    "H2s help search engines understand content structure and identify subtopics.",
                    pages=[page]
                ))

        if not findings:
            return self.result([], f"Header hierarchy is correct across all {len(self.html_files)} pages.",
                               [], ["Keep H1 text aligned with the page's meta title keyword focus."])

        recs = [
            "Each page's H1 should contain the primary keyword near the start.",
            "Use H2s to organize major content sections; H3s for subsections.",
            "Keep H1 under 70 characters for clarity."
        ]
        return self.result(findings, f"Header analysis: {len(findings)} issue(s) found.", [], recs)
