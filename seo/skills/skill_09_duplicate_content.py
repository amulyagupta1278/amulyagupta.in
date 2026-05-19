import re
import crawler
from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL


def text_fingerprint(text: str, size: int = 200) -> str:
    cleaned = re.sub(r'\s+', ' ', text.lower().strip())
    words = cleaned.split()
    sample = ' '.join(words[:size])
    return sample


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    sa = set(a.split())
    sb = set(b.split())
    if not sa or not sb:
        return 0.0
    intersection = sa & sb
    union = sa | sb
    return len(intersection) / len(union)


class Skill09DuplicateContent(BaseSEOSkill):
    SKILL_ID = 9
    SKILL_NAME = "Duplicate Content Detection"

    def run(self, pages: list[dict]) -> SkillResult:
        findings = []

        page_data = []
        for page in pages:
            url = page["url"]
            path = url.replace(SITE_URL, "")
            soup = page.get("soup")
            if not soup or page.get("status") != 200:
                continue

            meta = crawler.extract_meta(soup)
            body = soup.get_text(separator=" ", strip=True)
            fp = text_fingerprint(body)

            page_data.append({
                "url": url,
                "path": path,
                "title": meta.get("title", ""),
                "description": meta.get("description", ""),
                "fingerprint": fp,
                "word_count": len(body.split()),
            })

        # Check for duplicate titles
        seen_titles = {}
        for p in page_data:
            t = p["title"]
            if t and t in seen_titles:
                findings.append(Finding(
                    title=f"Duplicate title: {p['path']}",
                    description=f"Same title as {seen_titles[t]}: '{t}'",
                    severity="critical",
                    category="duplicate-content",
                    url=p["url"],
                    recommendation="Write unique, descriptive titles for each page.",
                    evidence=f"'{t}' also used on {seen_titles[t]}",
                ))
            else:
                seen_titles[t] = p["path"]

        # Check for duplicate descriptions
        seen_descs = {}
        for p in page_data:
            d = p["description"]
            if d and d in seen_descs:
                findings.append(Finding(
                    title=f"Duplicate meta description: {p['path']}",
                    description=f"Same description as {seen_descs[d]}",
                    severity="warning",
                    category="duplicate-content",
                    url=p["url"],
                    recommendation="Write unique meta descriptions for each page.",
                ))
            else:
                seen_descs[d] = p["path"]

        # Content similarity matrix
        similar_pairs = []
        for i in range(len(page_data)):
            for j in range(i + 1, len(page_data)):
                a = page_data[i]
                b = page_data[j]
                sim = similarity(a["fingerprint"], b["fingerprint"])
                if sim > 0.7:
                    similar_pairs.append((a["path"], b["path"], sim))
                    severity = "critical" if sim > 0.85 else "warning"
                    findings.append(Finding(
                        title=f"High content similarity: {a['path']} ↔ {b['path']}",
                        description=f"Content similarity is {sim:.0%} — near-duplicate content risk.",
                        severity=severity,
                        category="duplicate-content",
                        url=a["url"],
                        recommendation="Differentiate content significantly or consolidate pages with canonical tags.",
                        evidence=f"Similarity: {sim:.0%}",
                    ))

        dup_count = len(similar_pairs)
        score = max(0, 100 - dup_count * 20)
        score = self.clamp_score(score, findings=findings)
        return self.result(score, findings, {
            "pages_analyzed": len(page_data),
            "duplicate_pairs": dup_count,
        })
