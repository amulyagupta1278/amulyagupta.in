"""Skill 20 — Internal Anchor Text Diversity"""
from collections import Counter
from .base import BaseSkill

GENERIC_ANCHORS = {"click here", "here", "read more", "learn more", "more", "this", "link",
                   "this page", "continue", "view", "see", "next", "prev", "previous"}


class InternalAnchorsSkill(BaseSkill):
    name = "Internal Anchor Text Diversity"
    priority = "P7"
    skill_number = 20

    def run(self) -> dict:
        findings = []
        all_anchors: list[tuple[str, str, str]] = []  # (anchor_text, url, source_page)

        for f in self.html_files:
            soup = self.parse(f)
            page = str(f.relative_to(self.site_root))
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                text = a.get_text(separator=" ", strip=True).lower()
                if text and href and not href.startswith("http") and not href.startswith("#"):
                    all_anchors.append((text, href, page))

        # Generic anchor check
        generic_found: list[tuple[str, str, str]] = []
        for text, url, page in all_anchors:
            if text in GENERIC_ANCHORS:
                generic_found.append((text, url, page))

        if generic_found:
            examples = [f"'{t}' → {u} (on {p})" for t, u, p in generic_found[:5]]
            findings.append(self.finding(
                "ANCHOR_001", f"{len(generic_found)} generic anchor text(s) found",
                "warning", "P7",
                f"Generic anchors provide no keyword signal: {'; '.join(examples)}",
                "Replace generic anchors with descriptive, keyword-rich text. e.g., 'click here' → 'view MLOps pipeline project'",
                "Generic anchors waste internal PageRank and miss keyword relevance signals.",
                pages=list({p for _, _, p in generic_found[:5]})
            ))

        # Keyword-rich anchor ratio
        keyword_anchors = [t for t, _, _ in all_anchors
                           if any(kw in t for kw in ["mlops", "ai", "ml", "rag", "llm", "project",
                                                      "pipeline", "system", "engineer", "blog"])]
        total = len(all_anchors)
        if total > 0:
            ratio = len(keyword_anchors) / total
            if ratio < 0.3:
                findings.append(self.finding(
                    "ANCHOR_002", f"Low keyword anchor ratio: {ratio:.0%} ({len(keyword_anchors)}/{total})",
                    "info", "P7",
                    "Less than 30% of internal links use keyword-rich anchor text.",
                    "Improve anchor text to include relevant keywords naturally. Avoid over-optimization (>50% exact match).",
                    "Keyword anchors distribute topical relevance through the site's link graph."
                ))

        # Anchor diversity — check for over-optimization
        anchor_counter = Counter(t for t, _, _ in all_anchors)
        over_used = [(a, n) for a, n in anchor_counter.most_common(5) if n > 5 and a not in GENERIC_ANCHORS]
        if over_used:
            for anchor, count in over_used[:3]:
                findings.append(self.finding(
                    "ANCHOR_003", f"Overused anchor text: '{anchor}' ({count} times)", "info", "P7",
                    f"Same anchor '{anchor}' used {count} times. May appear unnatural to search engines.",
                    "Vary anchor text using synonyms: e.g., mix 'MLOps pipeline', 'ML deployment system', 'production ML workflow'.",
                ))

        # Count unique vs total anchors
        unique_anchors = len(set(t for t, _, _ in all_anchors))
        if total > 0 and unique_anchors / total < 0.5:
            findings.append(self.finding(
                "ANCHOR_004", f"Low anchor diversity: {unique_anchors} unique / {total} total links",
                "info", "P7",
                f"Only {unique_anchors}/{total} ({unique_anchors/total:.0%}) anchor texts are unique.",
                "Use more varied descriptive anchor text to signal topic diversity.",
            ))

        if not findings:
            return self.result([], f"Anchor text diversity is strong across all {len(self.html_files)} pages.",
                               [], ["Audit anchor text after adding new blog posts or pages."])

        return self.result(findings, f"Anchor audit: {len(findings)} issue(s) across {total} internal links.",
                           [], ["Never use 'click here' — always describe the destination."])
