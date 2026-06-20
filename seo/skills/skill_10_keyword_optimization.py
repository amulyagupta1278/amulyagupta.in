import re
import crawler
from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL

PAGE_KEYWORDS = {
    "/": ["amulya gupta", "ai engineer", "agentic ai", "ml engineer", "llm"],
    "/about.html": ["amulya gupta", "ai systems engineer", "bits pilani", "ai ml"],
    "/projects.html": ["ai projects", "mlops pipeline", "rag system", "multi-agent ai"],
    # Primary keyword must realistically appear in title/H1 — company names should not
    # be primary keywords since they belong in content not page headings.
    "/experience.html": ["ai engineer", "software engineer", "hcltech", "experience"],
    "/amulya-gupta.html": ["amulya gupta", "ai systems engineer"],
    "/contact.html": ["amulya gupta", "ai engineer", "hire"],
    "/blog/post-1-mlops-pipeline.html": ["mlops pipeline", "mlflow", "fastapi", "kubernetes"],
    "/blog/post-2-mlops-stack.html": ["mlops stack", "mlflow", "prefect"],
    # Actual title: "AI/ML Roadmap 2026: From Zero to Job-Ready" — use matching keyword
    "/blog/ai-ml-guide-2026.html": ["ai ml roadmap", "machine learning roadmap", "2026"],
    "/blog/index.html": ["machine learning", "ai blog", "machine learning blog"],
}


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
            url_lower = url.lower()

            primary_kw = keywords[0]
            page_score = 0
            max_score = 5

            # Check presence in title
            if primary_kw in title:
                page_score += 1
            else:
                findings.append(Finding(
                    title=f"Primary keyword missing from title: {path}",
                    description=f"'{primary_kw}' not in title: '{meta.get('title','')}'",
                    severity="warning",
                    category="keyword",
                    url=url,
                    recommendation=f"Include '{primary_kw}' in the page title, ideally near the beginning.",
                ))

            # Check in H1
            if primary_kw in h1_text:
                page_score += 1
            else:
                findings.append(Finding(
                    title=f"Primary keyword missing from H1: {path}",
                    description=f"'{primary_kw}' not in H1 heading.",
                    severity="warning",
                    category="keyword",
                    url=url,
                    recommendation=f"Include '{primary_kw}' in the main H1 heading.",
                ))

            # Check in meta description
            if primary_kw in desc:
                page_score += 1
            else:
                findings.append(Finding(
                    title=f"Primary keyword missing from meta description: {path}",
                    description=f"'{primary_kw}' not in meta description.",
                    severity="info",
                    category="keyword",
                    url=url,
                    recommendation=f"Naturally incorporate '{primary_kw}' in the meta description.",
                ))

            # Check in URL
            kw_slug = primary_kw.replace(" ", "-").replace(" ", "_")
            if any(part in url_lower for part in primary_kw.split()):
                page_score += 1

            # Check density in body (1-3% ideal)
            words = body_text.split()
            if words:
                kw_parts = primary_kw.split()
                kw_count = sum(1 for i in range(len(words) - len(kw_parts) + 1)
                              if words[i:i+len(kw_parts)] == kw_parts)
                density = kw_count / len(words) * 100 if words else 0
                if kw_count == 0:
                    findings.append(Finding(
                        title=f"Primary keyword not in body: {path}",
                        description=f"'{primary_kw}' not found in body content.",
                        severity="warning",
                        category="keyword",
                        url=url,
                        recommendation=f"Use '{primary_kw}' naturally throughout the content (aim for 1–2% density).",
                    ))
                elif density > 4:
                    findings.append(Finding(
                        title=f"Keyword over-density: {path}",
                        description=f"'{primary_kw}' used {kw_count}x ({density:.1f}%) — may appear unnatural.",
                        severity="warning",
                        category="keyword",
                        url=url,
                        recommendation="Reduce keyword repetition and use semantic variations instead.",
                    ))
                else:
                    page_score += 1

            scores.append(page_score / max_score * 100)

        avg = int(sum(scores) / len(scores)) if scores else 50
        score = self.clamp_score(avg, penalty_per_critical=10, penalty_per_warning=5, findings=findings)
        return self.result(score, findings, {"pages_analyzed": len(scores)})
