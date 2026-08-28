import re
import crawler
from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL

PAGE_THRESHOLDS = {
    "/": 500,
    "/about.html": 400,
    "/amulya-gupta.html": 400,
    "/projects.html": 600,
    "/experience.html": 600,
    "/contact.html": 200,
    "/blog/index.html": 400,
    "/blog/post-1-mlops-pipeline.html": 1500,
    "/blog/post-2-mlops-stack.html": 1500,
    "/blog/ai-ml-guide-2026.html": 1500,
}


def flesch_reading_ease(text: str) -> float:
    sentences = max(1, len(re.split(r'[.!?]+', text)))
    words = text.split()
    word_count = max(1, len(words))
    syllables = sum(_count_syllables(w) for w in words)
    return 206.835 - 1.015 * (word_count / sentences) - 84.6 * (syllables / word_count)


def _count_syllables(word: str) -> int:
    word = word.lower().strip(".,!?;:'\"")
    if not word:
        return 1
    vowels = "aeiouy"
    count = 0
    prev_vowel = False
    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    if word.endswith("e"):
        count = max(1, count - 1)
    return max(1, count)


def reading_level(score: float) -> str:
    if score >= 70:
        return "easy"
    elif score >= 50:
        return "moderate"
    elif score >= 30:
        return "difficult"
    return "very difficult"


class Skill08ContentQuality(BaseSEOSkill):
    SKILL_ID = 8
    SKILL_NAME = "Content Quality Audit"

    def run(self, pages: list[dict]) -> SkillResult:
        findings = []
        page_scores = []
        observations = []

        for page in pages:
            url = page["url"]
            path = url.replace(SITE_URL, "")
            soup = page.get("soup")
            if not soup or page.get("status") != 200:
                continue

            wc = crawler.word_count(soup)

            page_score = 100

            minimum = PAGE_THRESHOLDS.get(path)
            if minimum is None:
                page_scores.append(page_score)
                continue

            thin_threshold = min(300, minimum)
            if wc < thin_threshold:
                page_score -= 40
                findings.append(Finding(
                    title=f"Thin content: {path} ({wc} words)",
                    description=f"Only {wc} words — below the {minimum}-word target for this page type.",
                    severity="critical",
                    category="content-quality",
                    url=url,
                    recommendation=f"Expand to at least {minimum} useful, unique words.",
                ))
            elif wc < minimum:
                page_score -= 15
                findings.append(Finding(
                    title=f"Below-ideal content length: {path} ({wc} words)",
                    description=f"{wc} words — below the {minimum}-word target for this page type.",
                    severity="warning",
                    category="content-quality",
                    url=url,
                    recommendation="Add more comprehensive content: examples, case studies, technical depth.",
                ))

            # Keyword stuffing detection
            body_text = soup.get_text(separator=" ", strip=True)
            words = body_text.lower().split()
            if words:
                word_freq = {}
                for w in words:
                    if len(w) > 4:
                        word_freq[w] = word_freq.get(w, 0) + 1
                top_word = max(word_freq, key=word_freq.get) if word_freq else ""
                top_density = word_freq.get(top_word, 0) / len(words) * 100
                if top_density > 5:
                    page_score -= 20
                    findings.append(Finding(
                        title=f"Possible keyword stuffing: {path}",
                        description=f"Word '{top_word}' appears {word_freq[top_word]} times ({top_density:.1f}% density).",
                        severity="warning",
                        category="content-quality",
                        url=url,
                        recommendation="Reduce keyword density below 3%. Use synonyms and related terms naturally.",
                        evidence=f"'{top_word}': {word_freq[top_word]}x ({top_density:.1f}%)",
                    ))

            # Readability
            try:
                fre = flesch_reading_ease(body_text[:5000])
                level = reading_level(fre)
                if fre < 30:
                    page_score -= 10
                    observations.append({"path": path, "type": "readability", "flesch_score": round(fre)})
            except Exception:
                pass

            # Check for content in main/article tag
            main = soup.find("main") or soup.find("article")
            if not main and wc > 100:
                findings.append(Finding(
                    title=f"No semantic content container: {path}",
                    description="Page content not wrapped in <main> or <article> tag.",
                    severity="info",
                    category="content-quality",
                    url=url,
                    recommendation="Wrap primary content in <main> or <article> tags for semantic clarity.",
                ))

            page_scores.append(page_score)

        avg = int(sum(page_scores) / len(page_scores)) if page_scores else 50
        score = self.clamp_score(avg, findings=findings)
        return self.result(score, findings, {"pages_analyzed": len(page_scores), "observations": observations})
