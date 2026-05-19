"""Skill 19 — Semantic SEO & Topical Authority"""
import re
from collections import Counter
from .base import BaseSkill

TARGET_KEYWORDS = {
    "primary": ["amulya gupta", "ai systems engineer", "agentic ai", "llm", "mlops"],
    "secondary": ["rag", "langchain", "langgraph", "fastapi", "kubernetes", "python", "machine learning"],
    "lsi": ["neural network", "deep learning", "data pipeline", "model deployment", "vector database",
            "fine-tuning", "embeddings", "transformer", "hugging face", "openai"]
}


class SemanticSeoSkill(BaseSkill):
    name = "Semantic SEO & Topical Authority"
    priority = "P9"
    skill_number = 19

    def run(self) -> dict:
        findings = []
        recommendations = []

        for f in self.html_files:
            soup = self.parse(f)
            page = str(f.relative_to(self.site_root))
            body = soup.find("body")
            if not body:
                continue

            text = body.get_text(separator=" ", strip=True).lower()
            words = re.findall(r'\b\w+\b', text)
            word_count = len(words)

            # Thin content check
            if word_count < 300 and page not in ["contact.html"]:
                findings.append(self.finding(
                    "SEM_001", f"Thin content on {page}: {word_count} words", "warning", "P9",
                    f"{page} has only {word_count} words. Google considers <300 words thin content.",
                    "Expand content to 600+ words with relevant examples, case studies, or technical depth.",
                    "Thin content pages are less likely to rank and may trigger quality penalties.",
                    pages=[page]
                ))

            # Primary keyword density
            for kw in TARGET_KEYWORDS["primary"]:
                kw_count = text.count(kw)
                density = (kw_count / word_count * 100) if word_count > 0 else 0
                if kw_count > 0 and density > 5:
                    findings.append(self.finding(
                        "SEM_002", f"Keyword stuffing risk: '{kw}' at {density:.1f}% density on {page}",
                        "warning", "P9",
                        f"'{kw}' appears {kw_count} times ({density:.1f}%). Over 3% density looks unnatural.",
                        "Reduce keyword repetition. Use synonyms and natural language variations.",
                        "Keyword stuffing is a negative ranking signal and may trigger manual action.",
                        pages=[page]
                    ))

            # Missing LSI keywords (for content-heavy pages)
            if word_count > 400:
                lsi_present = [kw for kw in TARGET_KEYWORDS["lsi"] if kw in text]
                if len(lsi_present) < 3:
                    missing_lsi = [kw for kw in TARGET_KEYWORDS["lsi"] if kw not in text][:5]
                    findings.append(self.finding(
                        "SEM_003", f"Low LSI keyword coverage on {page} ({len(lsi_present)}/10)",
                        "info", "P9",
                        f"Content lacks semantic diversity. Missing LSI terms: {', '.join(missing_lsi)}",
                        f"Naturally incorporate terms like: {', '.join(missing_lsi[:3])} to signal topical depth.",
                        "LSI keywords help Google understand page context and improve ranking for related queries.",
                        pages=[page]
                    ))

            # Content freshness for blog posts
            if "blog/" in page and page != "blog/index.html":
                year_match = re.search(r'(202[0-9])', text)
                if year_match:
                    year = int(year_match.group(1))
                    if year < 2024:
                        findings.append(self.finding(
                            "SEM_004", f"Potentially dated content on {page} (mentions {year})",
                            "info", "P9",
                            f"Blog post may contain outdated information from {year}.",
                            "Review and update content with current tools, techniques, and statistics.",
                            "Fresh content performs better in search — Google favors recently updated articles.",
                            pages=[page]
                        ))

        # Topical cluster analysis
        blog_topics = set()
        for f in self.html_files:
            if "blog/" in str(f) and str(f.relative_to(self.site_root)) != "blog/index.html":
                soup = self.parse(f)
                h1 = soup.find("h1")
                if h1:
                    blog_topics.add(h1.get_text(strip=True)[:60])

        if len(blog_topics) < 5:
            recommendations.append(
                f"Only {len(blog_topics)} blog posts detected. Target 10+ posts to establish topical authority in AI/ML/MLOps."
            )

        # Missing content opportunities
        topic_gaps = ["prompt engineering", "vector database", "ai agent", "fine-tuning llm",
                      "kubernetes mlops", "fastapi deployment", "rag evaluation"]
        all_content = " ".join(f.read_text(encoding="utf-8", errors="replace").lower()
                               for f in self.html_files)
        missing_topics = [t for t in topic_gaps if t not in all_content]
        if missing_topics:
            recommendations.append(
                f"Content gap opportunities: consider writing about {', '.join(missing_topics[:4])}. "
                "These are high-traffic topics in your niche with manageable competition."
            )

        if not findings:
            return self.result([], "Semantic SEO: Content quality and topical authority look solid.", [], recommendations)

        return self.result(findings, f"Semantic SEO: {len(findings)} issue(s). {len(findings)} opportunities identified.",
                           [], recommendations)
