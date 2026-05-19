import re
import crawler
from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL

THIN_CONTENT_THRESHOLD = 300
IDEAL_MIN_WORDS = 600


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

        for page in pages:
            url = page["url"]
            path = url.replace(SITE_URL, "")
            soup = page.get("soup")
            if not soup or page.get("status") != 200:
                continue

            wc = crawler.word_count(soup)

            page_score = 100

            if wc < THIN_CONTENT_THRESHOLD:
                page_score -= 40
                findings.append(Finding(
                    title=f"Thin content: {path} ({wc} words)",
                    description=f"Only {wc} words — below {THIN_CONTENT_THRESHOLD} threshold.",
                    severity="critical",
                    category="content-quality",
                    url=url,
                    recommendation=f"Expand content to at least {IDEAL_MIN_WORDS} words with substantive, unique information.",
                ))
            elif wc < IDEAL_MIN_WORDS:
                page_score -= 15
                findings.append(Finding(
                    title=f"Below-ideal content length: {path} ({wc} words)",
                    description=f"{wc} words — aim for {IDEAL_MIN_WORDS}+ words for better ranking potential.",
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
                    findings.append(Finding(
                        title=f"Very difficult readability: {path}",
                        description=f"Flesch score {fre:.0f} — content may be too complex for general readers.",
                        severity="info",
                        category="content-quality",
                        url=url,
                        recommendation="Simplify language, use shorter sentences and paragraphs.",
                    ))
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
        return self.result(score, findings, {"pages_analyzed": len(page_scores)})
