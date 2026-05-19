"""Skill 23 — Competitor Intelligence Analysis"""
from .base import BaseSkill

COMPETITOR_DOMAINS = [
    "chip.huyen.com",
    "eugeneyan.com",
    "vicki.dev",
    "mlops.community",
    "neptune.ai/blog",
    "towardsdatascience.com",
    "sebastianraschka.com",
]

CONTENT_GAPS = [
    ("prompt engineering guide", "prompt engineering"),
    ("llm evaluation metrics", "llm eval"),
    ("rag vs fine-tuning comparison", "rag vs fine"),
    ("mlops best practices 2025", "mlops best practices"),
    ("langgraph tutorial", "langgraph tutorial"),
    ("vector database comparison", "vector database"),
    ("ai agent architecture", "agent architecture"),
    ("production llm monitoring", "llm monitoring"),
    ("kubernetes ml deployment", "kubernetes ml"),
    ("fastapi ml serving", "fastapi ml"),
]


class CompetitorIntelligenceSkill(BaseSkill):
    name = "Competitor Intelligence Analysis"
    priority = "P10"
    skill_number = 23

    def run(self) -> dict:
        findings = []
        recommendations = []

        # Content gap analysis (based on site's existing content)
        all_content = " ".join(
            f.read_text(encoding="utf-8", errors="replace").lower()
            for f in self.html_files
        )

        gaps = []
        for topic_name, indicator in CONTENT_GAPS:
            if indicator not in all_content:
                gaps.append(topic_name)

        if gaps:
            high_priority = gaps[:5]
            findings.append(self.finding(
                "COMP_001", f"{len(gaps)} content gap(s) vs. AI/ML content leaders",
                "info", "P10",
                f"Your site doesn't cover these high-traffic topics: {', '.join(high_priority)}",
                f"Create content targeting: {', '.join(high_priority[:3])}. These are established traffic drivers for ML engineers.",
                "Content gaps mean missed ranking opportunities for high-intent search queries in your niche.",
            ))

        # Check competitor reachability and structure
        live_competitors = []
        for domain in COMPETITOR_DOMAINS[:5]:
            r = self.fetch(f"https://{domain}", timeout=8)
            if r and r.status_code == 200:
                live_competitors.append(domain)

        if live_competitors:
            findings.append(self.finding(
                "COMP_002", f"Competitor landscape: {len(live_competitors)} active competing domains",
                "info", "P10",
                f"Active competitor sites: {', '.join(live_competitors[:5])}",
                "Analyze their content structure, topic coverage, and backlink profiles for strategic insights.",
                "Understanding competitor content depth helps prioritize your own content roadmap."
            ))

        # Keyword differentiation opportunities
        your_unique_topics = self._identify_unique_angles(all_content)
        if your_unique_topics:
            recommendations.append(
                f"Your unique angles to amplify: {', '.join(your_unique_topics[:3])}. "
                "Double down on these in future content — they differentiate you from generic ML blogs."
            )

        # Publishing velocity analysis
        blog_posts = [f for f in self.html_files
                      if "blog/" in str(f) and str(f.relative_to(self.site_root)) != "blog/index.html"]
        if len(blog_posts) < 8:
            findings.append(self.finding(
                "COMP_003", f"Low publishing velocity: {len(blog_posts)} posts vs. competitor pace",
                "info", "P10",
                f"With only {len(blog_posts)} blog posts, content velocity is below competitive threshold.",
                "Target 2 high-quality posts per month (1,500+ words) to build topical authority faster.",
                "Top AI/ML blogs publish 4-8 posts/month. Consistent publishing is the strongest organic signal."
            ))

        # Domain authority signals
        internal_link_count = sum(
            len(self.parse(f).find_all("a", href=lambda h: h and not h.startswith("http")))
            for f in self.html_files
        )
        if internal_link_count < 30:
            findings.append(self.finding(
                "COMP_004", f"Weak internal link density: {internal_link_count} internal links across site",
                "info", "P10",
                "Strong competitor sites have dense internal linking — average 5-10 links per page.",
                "Build content clusters: each blog post should link to 3+ other site pages and vice versa.",
                "Internal link density signals content depth and distributes authority across the domain."
            ))

        # Backlink opportunities
        recommendations.extend([
            "Guest post on eugeneyan.com, Towards Data Science, and The Batch newsletter — high DA sources in your niche.",
            "Submit your LangGraph and MLOps projects to Hacker News 'Show HN' — drives backlinks and traffic.",
            "Create shareable resources: 'MLOps Tools Comparison 2025' or 'LLM Evaluation Cheatsheet' attract organic backlinks.",
            "LinkedIn long-form posts linking to your blog increase referral traffic and topical authority signals.",
        ])

        # SEO strategy summary
        strategy_insights = {
            "blog_count": len(blog_posts),
            "content_gaps": len(gaps),
            "competitor_domains": COMPETITOR_DOMAINS,
            "priority_content_topics": gaps[:5],
            "unique_angles": your_unique_topics[:3],
        }

        summary = (
            f"Competitor intelligence complete. {len(blog_posts)} posts vs. 50+ from top competitors. "
            f"{len(gaps)} content gaps identified. Focus on: {', '.join(gaps[:2]) if gaps else 'content depth'}."
        )
        return self.result(findings, summary, [], recommendations)

    def _identify_unique_angles(self, content: str) -> list:
        unique_angles = []
        if "agentic" in content and "multi-agent" in content:
            unique_angles.append("agentic AI systems design")
        if "mlops" in content and "kubernetes" in content:
            unique_angles.append("production MLOps with Kubernetes")
        if "rag" in content and "accuracy" in content:
            unique_angles.append("RAG system optimization for production accuracy")
        if "langgraph" in content:
            unique_angles.append("LangGraph workflow engineering")
        if "bits pilani" in content.lower():
            unique_angles.append("elite Indian AI/ML talent perspective")
        return unique_angles
