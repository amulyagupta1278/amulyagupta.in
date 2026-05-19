import re
import crawler
from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL

CORE_TOPICS = {
    "agentic ai": ["agent", "agentic", "autonomous ai", "ai agent"],
    "llm engineering": ["llm", "large language model", "gpt", "claude", "prompt"],
    "mlops": ["mlops", "ml pipeline", "model deployment", "model monitoring"],
    "rag systems": ["rag", "retrieval augmented", "vector database", "embedding"],
    "langchain / langgraph": ["langchain", "langgraph", "langsmith"],
    "pytorch / tensorflow": ["pytorch", "tensorflow", "neural network", "deep learning"],
    "kubernetes": ["kubernetes", "k8s", "container", "docker"],
    "bits pilani": ["bits pilani", "bits", "m.tech", "mtech"],
    "hcltech": ["hcltech", "hcl technologies", "hcl"],
    "fastapi": ["fastapi", "api", "rest api"],
}

ENTITY_MARKERS = {
    "Amulya Gupta": ["amulya", "amulya gupta"],
    "HCLTech": ["hcltech", "hcl technologies"],
    "BITS Pilani": ["bits pilani", "bits"],
    "AI Engineering": ["ai engineer", "ai systems engineer", "artificial intelligence"],
}


class Skill21SemanticCoverage(BaseSEOSkill):
    SKILL_ID = 21
    SKILL_NAME = "Semantic Coverage Audit"

    def run(self, pages: list[dict]) -> SkillResult:
        findings = []

        all_text = ""
        for page in pages:
            soup = page.get("soup")
            if soup and page.get("status") == 200:
                all_text += " " + soup.get_text(separator=" ", strip=True).lower()

        # Topic coverage check
        covered = []
        missing = []
        for topic, signals in CORE_TOPICS.items():
            if any(sig in all_text for sig in signals):
                covered.append(topic)
            else:
                missing.append(topic)
                findings.append(Finding(
                    title=f"Topic gap: '{topic}' not covered",
                    description=f"Site doesn't mention '{topic}' — a core topic for AI/ML engineers.",
                    severity="warning",
                    category="semantic",
                    url=SITE_URL,
                    recommendation=f"Add content about '{topic}' to improve topical authority and semantic relevance.",
                ))

        # Entity coverage check
        for entity, signals in ENTITY_MARKERS.items():
            if not any(sig in all_text for sig in signals):
                findings.append(Finding(
                    title=f"Entity not mentioned: '{entity}'",
                    description=f"The entity '{entity}' is not found in site content.",
                    severity="warning",
                    category="semantic",
                    url=SITE_URL,
                    recommendation=f"Mention '{entity}' explicitly and consistently across key pages.",
                ))

        # Check for semantic HTML
        for page in pages:
            url = page["url"]
            path = url.replace(SITE_URL, "")
            soup = page.get("soup")
            if not soup or page.get("status") != 200:
                continue

            semantic_tags = ["article", "section", "nav", "aside", "footer", "header", "main"]
            found_tags = [t for t in semantic_tags if soup.find(t)]
            if len(found_tags) < 3:
                findings.append(Finding(
                    title=f"Limited semantic HTML: {path}",
                    description=f"Only {len(found_tags)} semantic HTML5 tags found ({', '.join(found_tags) or 'none'}).",
                    severity="info",
                    category="semantic",
                    url=url,
                    recommendation="Use semantic HTML5 elements (article, section, main, aside) to improve machine readability.",
                ))

        # Topical authority score
        coverage_pct = len(covered) / len(CORE_TOPICS) * 100 if CORE_TOPICS else 0
        if coverage_pct < 50:
            findings.append(Finding(
                title=f"Low topical authority: {coverage_pct:.0f}% topic coverage",
                description=f"Only {len(covered)}/{len(CORE_TOPICS)} core topics covered.",
                severity="critical",
                category="semantic",
                url=SITE_URL,
                recommendation="Create dedicated content pages or sections for each core topic to build topical authority.",
            ))

        score = int(coverage_pct)
        score = self.clamp_score(score, findings=findings)
        return self.result(score, findings, {
            "topics_covered": covered,
            "topics_missing": missing,
            "coverage_pct": coverage_pct,
        })
