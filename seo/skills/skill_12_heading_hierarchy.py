import crawler
from base import BaseSEOSkill, Finding
from config import SITE_URL


class Skill12HeadingHierarchy(BaseSEOSkill):
    SKILL_ID = 12
    SKILL_NAME = "Heading Hierarchy Audit"

    def run(self, pages: list[dict]) -> SkillResult:
        from base import SkillResult
        findings = []
        ok_count = 0
        total = 0

        for page in pages:
            url = page["url"]
            path = url.replace(SITE_URL, "")
            soup = page.get("soup")
            if not soup or page.get("status") != 200:
                continue

            total += 1
            headings = crawler.extract_headings(soup)
            page_ok = True

            h1s = [h for h in headings if h["level"] == 1]

            if not h1s:
                page_ok = False
                findings.append(Finding(
                    title=f"Missing H1: {path}",
                    description="Page has no H1 heading — critical for SEO and accessibility.",
                    severity="critical",
                    category="headings",
                    url=url,
                    recommendation="Add exactly one H1 heading with the primary keyword for this page.",
                ))
            elif len(h1s) > 1:
                page_ok = False
                findings.append(Finding(
                    title=f"Multiple H1s ({len(h1s)}): {path}",
                    description=f"Found {len(h1s)} H1 headings: {[h['text'] for h in h1s]}",
                    severity="warning",
                    category="headings",
                    url=url,
                    recommendation="Use exactly one H1 per page. Convert additional H1s to H2 or lower.",
                    evidence=str([h["text"] for h in h1s]),
                ))
            else:
                h1_text = h1s[0]["text"]
                if len(h1_text) < 10:
                    findings.append(Finding(
                        title=f"H1 too short: {path}",
                        description=f"H1 '{h1_text}' is only {len(h1_text)} characters — not descriptive enough.",
                        severity="warning",
                        category="headings",
                        url=url,
                        recommendation="Write a more descriptive H1 that includes the primary keyword.",
                    ))

            # Heading hierarchy check (no skipped levels)
            if headings:
                prev_level = 0
                for h in headings:
                    level = h["level"]
                    if level > prev_level + 1 and prev_level > 0:
                        findings.append(Finding(
                            title=f"Skipped heading level H{prev_level}→H{level}: {path}",
                            description=f"Heading hierarchy jumps from H{prev_level} to H{level} ('{h['text'][:50]}').",
                            severity="warning",
                            category="headings",
                            url=url,
                            recommendation=f"Don't skip heading levels. Use H{prev_level + 1} instead of H{level}.",
                            evidence=f"After H{prev_level}, found H{level}: '{h['text'][:50]}'",
                        ))
                    prev_level = level

            # Check H2 count — good content should have structure
            h2s = [h for h in headings if h["level"] == 2]
            if path not in ["/contact.html", "/privacy.html"] and len(h2s) == 0 and total > 1:
                findings.append(Finding(
                    title=f"No H2 headings: {path}",
                    description="Page lacks H2 subheadings, reducing scanability and topic clarity.",
                    severity="info",
                    category="headings",
                    url=url,
                    recommendation="Add H2 subheadings to organize content into scannable sections.",
                ))

            if page_ok:
                ok_count += 1

        score = int(ok_count / total * 100) if total else 50
        score = self.clamp_score(score, findings=findings)
        return self.result(score, findings, {"pages_ok": ok_count, "total_pages": total})
