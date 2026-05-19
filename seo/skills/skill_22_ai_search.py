"""Skill 22 — AI Search Optimization"""
from pathlib import Path
from .base import BaseSkill

ENTITY_CHECKS = ["Amulya Gupta", "BITS Pilani", "HCLTech", "Classplus", "LangGraph", "MLflow"]
AI_CRAWLERS = ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "Bingbot", "anthropic-ai"]


class AiSearchSkill(BaseSkill):
    name = "AI Search Optimization"
    priority = "P9"
    skill_number = 22

    def run(self) -> dict:
        findings = []
        auto_fixes = []

        # 1. llms.txt audit
        llms_path = self.site_root / "llms.txt"
        if not llms_path.exists():
            findings.append(self.finding(
                "AISEO_001", "llms.txt missing", "warning", "P9",
                "No llms.txt file found. This file helps LLMs understand site context.",
                "Create llms.txt with professional profile, skills, projects, and contact info.",
                "llms.txt is increasingly used by AI crawlers (Perplexity, ChatGPT) to understand site content.",
            ))
            self._create_llms_txt(llms_path, auto_fixes)
        else:
            content = llms_path.read_text(encoding="utf-8")
            word_count = len(content.split())
            if word_count < 200:
                findings.append(self.finding(
                    "AISEO_002", f"llms.txt is too thin ({word_count} words)", "warning", "P9",
                    "llms.txt should provide comprehensive context for AI systems.",
                    "Expand llms.txt with: skills, projects with descriptions, experience, contact, achievements.",
                    "Thin llms.txt reduces the quality of AI-generated responses about you.",
                ))
                self._enhance_llms_txt(llms_path, content, auto_fixes)

            # Check for entity mentions
            missing_entities = [e for e in ENTITY_CHECKS if e not in content]
            if missing_entities:
                findings.append(self.finding(
                    "AISEO_003", f"Missing entities in llms.txt: {', '.join(missing_entities)}",
                    "info", "P9",
                    f"Key entities not mentioned: {', '.join(missing_entities)}",
                    "Add all key entities (companies, tools, institutions) to llms.txt for Knowledge Graph clarity.",
                    "Entity completeness improves AI citation accuracy across ChatGPT, Perplexity, and Bing Copilot."
                ))

        # 2. robots.txt AI bot allowances
        robots_path = self.site_root / "robots.txt"
        if robots_path.exists():
            robots = robots_path.read_text(encoding="utf-8").lower()
            missing_bots = [b for b in AI_CRAWLERS if b.lower() not in robots]
            if missing_bots:
                findings.append(self.finding(
                    "AISEO_004", f"AI crawlers not in robots.txt: {', '.join(missing_bots)}", "warning", "P9",
                    "These AI search crawlers aren't explicitly allowed in robots.txt.",
                    "Add explicit User-agent entries for each AI crawler with Allow: /",
                    "Explicit allowances signal openness to AI indexing and may improve AI-search ranking.",
                ))

        # 3. Structured answer patterns (AI-readable content)
        structured_pages = []
        for f in self.html_files:
            soup = self.parse(f)
            body = soup.find("body")
            if not body:
                continue
            page = str(f.relative_to(self.site_root))
            # Check for structured answer patterns (definition lists, clear paragraphs after headings)
            dls = body.find_all("dl")
            bold_answers = body.find_all(["strong", "b"])
            if not dls and len(bold_answers) < 3:
                if "blog/" in page:
                    findings.append(self.finding(
                        "AISEO_005", f"Low AI-readable structure on {page}", "info", "P9",
                        "Content lacks definition lists and bold key terms that AI systems extract well.",
                        "Structure answers with: definition lists (<dl>), bold key terms, and clear paragraph answers after H2s.",
                        "AI systems prefer clearly structured content for accurate citation extraction.",
                        pages=[page]
                    ))

        # 4. Author entity markup
        for f in self.html_files:
            soup = self.parse(f)
            page = str(f.relative_to(self.site_root))
            # Check for author markup
            scripts = soup.find_all("script", type="application/ld+json")
            has_author = any('"author"' in (s.string or "") for s in scripts)
            has_person = any('"Person"' in (s.string or "") for s in scripts)
            if not has_author and not has_person and "blog/" in page:
                findings.append(self.finding(
                    "AISEO_006", f"No author entity markup on {page}", "info", "P9",
                    "Blog posts without author schema may not be attributed correctly by AI systems.",
                    "Add author Person schema to all blog posts with name, url, and sameAs links.",
                    "Author entity markup helps AI systems attribute content to the correct person.",
                    pages=[page]
                ))

        if not findings:
            return self.result([], "AI search optimization: All checks passed. Site is well-optimized for AI search.",
                               auto_fixes,
                               ["Monitor Perplexity and ChatGPT for mentions of your name and content.",
                                "Update llms.txt monthly with new projects and achievements."])

        return self.result(findings, f"AI search audit: {len(findings)} issue(s). {len(auto_fixes)} auto-fix(es).",
                           auto_fixes,
                           ["Test how ChatGPT, Perplexity, and Bing Copilot describe you — use results to improve content.",
                            "Structured data + llms.txt together maximize AI search visibility."])

    def _create_llms_txt(self, path: Path, auto_fixes: list):
        content = """# Amulya Gupta — AI Systems Engineer

## Professional Summary
Amulya Gupta is an AI Systems Engineer specializing in Agentic AI workflows, LLM pipelines, RAG systems, and MLOps. Based in India, with a M.Tech in Artificial Intelligence from BITS Pilani. Experienced in building production-grade AI systems for enterprise applications.

## Current Role
AI Systems Engineer building intelligent automation systems, LLM-powered pipelines, and production MLOps infrastructure.

## Education
- M.Tech in Artificial Intelligence & Machine Learning — BITS Pilani (Birla Institute of Technology and Science)

## Work Experience
- HCLTech — AI/ML Engineer (built enterprise AI systems)
- Classplus — ML Engineer (edtech platform ML features)

## Technical Skills
- LLM Frameworks: LangChain, LangGraph, OpenAI, Anthropic, Hugging Face
- MLOps: MLflow, FastAPI, Kubernetes, GitHub Actions, Docker
- RAG: Vector databases, embedding models, retrieval augmentation
- Languages: Python (primary), JavaScript
- Cloud & Infrastructure: AWS, GCP, containerization

## Key Projects
1. Multi-Agent AI Research Assistant — LangGraph-based multi-agent system for autonomous research
2. Heart Disease Prediction MLOps Pipeline — End-to-end MLflow + Kubernetes + FastAPI production system
3. Customer Churn Prediction ELT Pipeline — Prefect-orchestrated data pipeline
4. AI-Powered Customer Support System — RAG-based ticket automation achieving 92% accuracy and 60% response time reduction

## Blog & Writing
Technical blog at https://amulyagupta.in/blog/ covering:
- MLOps in production
- Building LLM applications
- AI/ML career guidance
- Agentic AI systems

## Contact
- Website: https://amulyagupta.in
- LinkedIn: https://www.linkedin.com/in/amulyagupta1278/
- GitHub: https://github.com/amulyagupta1278
- Email: amulya@amulyagupta.in

## Expertise Areas
Agentic AI, Retrieval-Augmented Generation (RAG), Large Language Models (LLMs), MLOps, Machine Learning Pipeline Design, Production AI Systems, Python, FastAPI, Kubernetes, MLflow, LangChain, LangGraph
"""
        path.write_text(content, encoding="utf-8")
        auto_fixes.append("Created comprehensive llms.txt for AI search crawler optimization.")

    def _enhance_llms_txt(self, path: Path, existing: str, auto_fixes: list):
        additions = []
        if "sameAs" not in existing and "linkedin" not in existing.lower():
            additions.append("\n## Social Profiles\n- LinkedIn: https://www.linkedin.com/in/amulyagupta1278/\n- GitHub: https://github.com/amulyagupta1278\n")
        if "project" not in existing.lower():
            additions.append("\n## Key Projects\n1. Multi-Agent AI Research Assistant (LangGraph)\n2. MLOps Pipeline (MLflow + Kubernetes)\n3. RAG-based Customer Support System (92% accuracy)\n")
        if additions:
            new_content = existing + "".join(additions)
            path.write_text(new_content, encoding="utf-8")
            auto_fixes.append("Enhanced llms.txt with additional entity and project information.")
