"""Skill 21 — FAQ Schema Opportunities"""
import json
import re
from .base import BaseSkill

QUESTION_PATTERNS = [
    r'^what\s+', r'^how\s+', r'^why\s+', r'^when\s+', r'^where\s+',
    r'^which\s+', r'^is\s+', r'^are\s+', r'^can\s+', r'^do\s+', r'^does\s+'
]


class FaqOpportunitiesSkill(BaseSkill):
    name = "FAQ Schema Opportunities"
    priority = "P9"
    skill_number = 21

    def run(self) -> dict:
        findings = []
        auto_fixes = []

        for f in self.html_files:
            soup = self.parse(f)
            page = str(f.relative_to(self.site_root))
            body = soup.find("body")
            if not body:
                continue

            # Find question-like headings
            headers = body.find_all(["h2", "h3", "h4"])
            qa_pairs: list[dict] = []
            for h in headers:
                h_text = h.get_text(strip=True)
                if self._is_question(h_text):
                    # Find answer (next sibling paragraphs)
                    answer_parts = []
                    for sibling in h.find_next_siblings():
                        if sibling.name in ["h1", "h2", "h3", "h4"]:
                            break
                        text = sibling.get_text(strip=True)
                        if text and len(text) > 20:
                            answer_parts.append(text)
                        if len(answer_parts) >= 2:
                            break
                    if answer_parts:
                        qa_pairs.append({
                            "question": h_text,
                            "answer": " ".join(answer_parts)[:500]
                        })

            if len(qa_pairs) >= 2:
                # Check if FAQ schema already exists
                existing_scripts = soup.find_all("script", type="application/ld+json")
                has_faq_schema = any(
                    '"FAQPage"' in (s.string or "") or "FAQPage" in (s.string or "")
                    for s in existing_scripts
                )
                if not has_faq_schema:
                    findings.append(self.finding(
                        "FAQ_001", f"{len(qa_pairs)} FAQ opportunity(ies) detected on {page}",
                        "info", "P9",
                        f"Found {len(qa_pairs)} question headings with answers that could use FAQPage schema.",
                        f"Add FAQPage JSON-LD schema to unlock FAQ rich results in Google.",
                        "FAQ rich results add expandable Q&A sections in SERP — can double CTR.",
                        pages=[page], auto_fixed=True
                    ))
                    self._add_faq_schema(f, qa_pairs, auto_fixes)

            # Identify FAQ content opportunities (questions in body text)
            text = body.get_text(separator="\n")
            inline_questions = re.findall(r'[A-Z][^.?!]*\?', text)
            unanswered = [q for q in inline_questions if len(q) > 20 and len(q) < 200]
            if len(unanswered) > 3:
                findings.append(self.finding(
                    "FAQ_002", f"Inline question patterns on {page} ({len(unanswered)} found)",
                    "info", "P9",
                    f"Questions found in body text could be structured as proper FAQ sections: {unanswered[0][:80]}...",
                    "Convert inline questions to structured H2/H3 FAQ sections with clear answers.",
                    "Structured FAQs rank better for conversational and voice search queries.",
                    pages=[page]
                ))

        # Check for common FAQ topics missing from the site
        missing_faqs = self._check_missing_faq_topics()
        if missing_faqs:
            findings.append(self.finding(
                "FAQ_003", f"Missing FAQ content opportunities: {', '.join(missing_faqs[:3])}",
                "info", "P9",
                f"Common questions in your niche not addressed on your site: {', '.join(missing_faqs)}",
                "Create a dedicated FAQ page or add FAQ sections to relevant pages addressing these questions.",
                "FAQ content captures featured snippets and voice search traffic."
            ))

        if not findings:
            return self.result([], "FAQ analysis complete. All FAQ opportunities are addressed.", auto_fixes,
                               ["Regularly update FAQ content based on Search Console's 'Questions' query filter."])

        return self.result(findings, f"FAQ audit: {len(findings)} opportunity(ies). {len(auto_fixes)} auto-fix(es).",
                           auto_fixes,
                           ["Target featured snippets by structuring answers in 40-60 word paragraphs.",
                            "Add FAQ schema to pages where you want to capture voice search traffic."])

    def _is_question(self, text: str) -> bool:
        text_lower = text.lower().strip()
        return (text_lower.endswith("?") or
                any(re.match(p, text_lower) for p in QUESTION_PATTERNS))

    def _add_faq_schema(self, path, qa_pairs: list, auto_fixes: list):
        content = path.read_text(encoding="utf-8")
        schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": qa["question"],
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": qa["answer"]
                    }
                }
                for qa in qa_pairs[:10]
            ]
        }
        tag = f'\n<script type="application/ld+json">\n{json.dumps(schema, indent=2)}\n</script>'
        new_content = content.replace("</head>", tag + "\n</head>", 1)
        path.write_text(new_content, encoding="utf-8")
        auto_fixes.append(f"Added FAQPage schema with {len(qa_pairs)} Q&A pairs to {path.relative_to(self.site_root)}.")

    def _check_missing_faq_topics(self) -> list:
        all_content = " ".join(
            f.read_text(encoding="utf-8", errors="replace").lower()
            for f in self.html_files
        )
        topics = {
            "how to get started with mlops": ["mlops", "getting started"],
            "what is agentic ai": ["agentic ai", "what is agentic"],
            "rag vs fine-tuning": ["rag vs", "vs fine-tuning"],
            "best mlops tools 2025": ["best mlops", "mlops tools"],
            "how to deploy llm": ["deploy llm", "llm deployment"],
        }
        missing = []
        for question, indicators in topics.items():
            if not any(ind in all_content for ind in indicators):
                missing.append(question)
        return missing
