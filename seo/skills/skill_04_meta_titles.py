"""Skill 04 — Meta Title Quality Audit"""
from .base import BaseSkill

PRIMARY_KEYWORDS = ["amulya gupta", "ai", "ml", "mlops", "agentic", "llm", "rag", "engineer"]


class MetaTitlesSkill(BaseSkill):
    name = "Meta Title Quality"
    priority = "P6"
    skill_number = 4

    def run(self) -> dict:
        findings = []
        seen_titles: dict[str, str] = {}
        title_data = []

        for f in self.html_files:
            soup = self.parse(f)
            title_tag = soup.find("title")
            page = str(f.relative_to(self.site_root))
            title = title_tag.get_text(strip=True) if title_tag else ""
            title_data.append((page, title))

            if not title:
                findings.append(self.finding(
                    "TITLE_001", f"Missing title tag: {page}", "critical", "P6",
                    f"{page} has no <title> tag.",
                    "Add a descriptive, keyword-rich title (50–60 chars) to this page.",
                    "Pages without titles get auto-generated titles by Google — usually poor quality.",
                    pages=[page]
                ))
                continue

            length = len(title)
            if length < 30:
                findings.append(self.finding(
                    "TITLE_002", f"Title too short ({length} chars): {page}", "warning", "P6",
                    f"Title '{title}' is only {length} characters — too short to be competitive.",
                    "Expand to 50–60 chars with primary keyword + brand: e.g., 'Keyword | Amulya Gupta'",
                    "Short titles miss keyword opportunities and look weak in SERPs.",
                    pages=[page]
                ))
            elif length > 70:
                findings.append(self.finding(
                    "TITLE_003", f"Title too long ({length} chars): {page}", "warning", "P6",
                    f"Title '{title[:60]}...' is {length} chars — Google truncates at ~60.",
                    "Shorten to under 60 characters, keeping primary keyword near the start.",
                    "Truncated titles hurt CTR and may cause keyword stuffing signals.",
                    pages=[page]
                ))

            # Check primary keyword presence
            title_lower = title.lower()
            has_keyword = any(kw in title_lower for kw in PRIMARY_KEYWORDS)
            if not has_keyword:
                findings.append(self.finding(
                    "TITLE_004", f"No primary keyword in title: {page}", "info", "P6",
                    f"Title '{title}' doesn't contain identifiable AI/ML keywords.",
                    "Include at least one of: AI, ML, MLOps, LLM, Agentic AI, Amulya Gupta.",
                    "Keyword-absent titles rank lower for target queries.",
                    pages=[page]
                ))

        # Duplicate title check
        for page, title in title_data:
            if not title:
                continue
            if title in seen_titles:
                findings.append(self.finding(
                    "TITLE_005", f"Duplicate title: '{title[:50]}'", "warning", "P6",
                    f"'{page}' and '{seen_titles[title]}' share the same title.",
                    "Give each page a unique title reflecting its specific content.",
                    "Duplicate titles confuse search engines about which page to rank.",
                    pages=[page, seen_titles[title]]
                ))
            else:
                seen_titles[title] = page

        if not findings:
            return self.result([], f"All {len(self.html_files)} page titles are well-optimized.",
                               [], ["A/B test title formats in Google Search Console to improve CTR."])

        recommendations = [
            "Keep primary keyword in the first 30 characters of every title.",
            "Use the format: 'Primary Keyword | Secondary Keyword | Brand' for maximum impact.",
            "Monitor CTR per title in Google Search Console and iterate monthly."
        ]
        return self.result(findings, f"Title audit: {len(findings)} issue(s) across {len(self.html_files)} pages.",
                           [], recommendations)
