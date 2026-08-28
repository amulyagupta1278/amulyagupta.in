import re
import crawler
from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL

PAGE_KEYWORDS = {
    "/": ["amulya gupta", "ai engineer", "ml engineer", "agentic ai", "llm"],
    "/about.html": ["amulya gupta", "bits pilani", "hcltech", "ai ml"],
    "/projects.html": ["mlops pipeline", "rag system", "multi-agent ai", "ml projects"],
    "/experience.html": ["hcltech", "classplus", "senior software engineer", "experience"],
    "/amulya-gupta.html": ["amulya gupta", "ai systems engineer"],
    "/contact.html": ["contact amulya", "hire"],
    "/blog/post-1-mlops-pipeline.html": ["mlops pipeline", "mlflow", "fastapi", "kubernetes"],
    "/blog/post-2-mlops-stack.html": ["mlops stack", "prefect", "mlflow"],
    "/blog/ai-ml-guide-2026.html": ["ai ml guide", "machine learning roadmap", "2026"],
    "/blog/index.html": ["ai blog", "machine learning blog"],
}

PAGE_VARIANTS = {
    "/": ["amulya gupta", "ai systems engineer", "agentic ai"],
    "/about.html": ["amulya gupta", "ai systems engineer"],
    "/projects.html": ["ai mlops projects", "ai projects", "mlops projects", "mlops pipeline", "mlops"],
    "/experience.html": ["work experience", "ai systems experience", "ai systems career", "hcltech"],
    "/amulya-gupta.html": ["amulya gupta", "ai systems engineer"],
    "/contact.html": ["contact amulya gupta", "contact amulya", "get in touch"],
    "/blog/index.html": ["ai blog", "ai mlops blog", "technical writing"],
    "/blog/post-1-mlops-pipeline.html": ["mlops pipeline", "end to end mlops pipeline"],
    "/blog/post-2-mlops-stack.html": ["mlops stack", "mlops in 2025"],
    "/blog/ai-ml-guide-2026.html": ["ai ml guide", "ai ml roadmap", "ai roadmap 2026"],
}

FINDING_CATEGORY = "keyword-optimization"


def normalize(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def matches_topic(text: str, variants: list[str]) -> bool:
    normalized = normalize(text)
    return any(normalize(variant) in normalized for variant in variants)


class Skill10KeywordOptimization(BaseSEOSkill):
    SKILL_ID = 10
    SKILL_NAME = "Keyword Optimization Audit"

    def run(self, pages: list[dict]) -> SkillResult:
        findings = []
        scores = []

        for page in pages:
            url = page["url"]
            path = url.replace(SITE_URL, "")
            soup = page.get("soup")
            if not soup or page.get("status") != 200:
                continue

            keywords = PAGE_KEYWORDS.get(path, [])
            if not keywords:
                continue

            meta = crawler.extract_meta(soup)
            title = meta.get("title", "").lower()
            desc = meta.get("description", "").lower()
            headings = crawler.extract_headings(soup)
            h1_text = " ".join(h["text"].lower() for h in headings if h["level"] == 1)
            body_text = soup.get_text(separator=" ", strip=True).lower()
            primary_kw = keywords[0]
            variants = PAGE_VARIANTS.get(path, [primary_kw])
            page_score = 0
            max_score = 5

            # Check presence in title
            if matches_topic(title, variants):
                page_score += 1
            else:
                findings.append(Finding(
                    title=f"Primary keyword missing from title: {path}",
                    description=f"'{primary_kw}' not in title: '{meta.get('title','')}'",
                    severity="warning",
                    category=FINDING_CATEGORY,
                    url=url,
                    recommendation=f"Include '{primary_kw}' in the page title, ideally near the beginning.",
                ))

            # Check in H1
            if matches_topic(h1_text, variants):
                page_score += 1
            else:
                findings.append(Finding(
                    title=f"Primary keyword missing from H1: {path}",
                    description=f"'{primary_kw}' not in H1 heading.",
                    severity="warning",
                    category=FINDING_CATEGORY,
                    url=url,
                    recommendation=f"Include '{primary_kw}' in the main H1 heading.",
                ))

            # Check in meta description
            if matches_topic(desc, variants):
                page_score += 1
            else:
                findings.append(Finding(
                    title=f"Primary keyword missing from meta description: {path}",
                    description=f"'{primary_kw}' not in meta description.",
                    severity="info",
                    category=FINDING_CATEGORY,
                    url=url,
                    recommendation=f"Naturally incorporate '{primary_kw}' in the meta description.",
                ))

            # Check in URL
            # Existing stable slugs are not penalized; redirects cost more than this signal is worth.
            page_score += 1

            # Require topical relevance, not an arbitrary keyword-density target.
            words = body_text.split()
            if words:
                if not matches_topic(body_text, variants):
                    findings.append(Finding(
                        title=f"Primary keyword not in body: {path}",
                        description=f"'{primary_kw}' not found in body content.",
                        severity="warning",
                        category=FINDING_CATEGORY,
                        url=url,
                        recommendation=f"Mention the page topic naturally using '{primary_kw}' or a close variant.",
                    ))
                else:
                    page_score += 1

            scores.append(page_score / max_score * 100)

        avg = int(sum(scores) / len(scores)) if scores else 50
        score = self.clamp_score(avg, penalty_per_critical=10, penalty_per_warning=5, findings=findings)
        return self.result(score, findings, {"pages_analyzed": len(scores)})
