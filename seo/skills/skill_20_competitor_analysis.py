import crawler
from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL

COMPETITORS = [
    {"name": "Competitor ML Engineer 1", "url": "https://mlops.community"},
    {"name": "Typical AI Portfolio", "url": "https://www.deeplearning.ai"},
]

OWN_KEYWORDS = [
    "amulya gupta", "ai engineer", "mlops", "rag pipeline", "langchain",
    "agentic ai", "llm engineer", "bits pilani",
]

SCHEMA_TYPES_TO_CHECK = ["Person", "BlogPosting", "WebSite", "BreadcrumbList", "FAQPage"]


class Skill20CompetitorAnalysis(BaseSEOSkill):
    SKILL_ID = 20
    SKILL_NAME = "Competitor SEO Analysis"

    def run(self, pages: list[dict]) -> SkillResult:
        findings = []

        # Analyze own site strengths
        home = next((p for p in pages if p["url"].rstrip("/") == SITE_URL.rstrip("/")), None)
        own_schema_types = set()
        if home and home.get("soup"):
            schemas = crawler.extract_json_ld(home["soup"])
            for s in schemas:
                if "@graph" in s:
                    for item in (s["@graph"] if isinstance(s["@graph"], list) else [s["@graph"]]):
                        own_schema_types.add(item.get("@type", ""))
                else:
                    own_schema_types.add(s.get("@type", ""))

        missing_schema = [t for t in SCHEMA_TYPES_TO_CHECK if t not in own_schema_types]
        if missing_schema:
            findings.append(Finding(
                title=f"Schema types not implemented: {', '.join(missing_schema)}",
                description="Competitive sites typically implement these schema types for richer SERPs.",
                severity="warning",
                category="competitive",
                url=SITE_URL,
                recommendation=f"Implement {', '.join(missing_schema)} JSON-LD schemas to match competitive standards.",
            ))

        # Check own content freshness
        blog_pages = [p for p in pages if "blog" in p["url"] and p.get("status") == 200]
        if len(blog_pages) < 3:
            findings.append(Finding(
                title="Insufficient blog content for competitive ranking",
                description=f"Only {len(blog_pages)} blog pages found. Competitive AI/ML portfolios typically have 10+ articles.",
                severity="warning",
                category="competitive",
                url=f"{SITE_URL}/blog/",
                recommendation="Publish 2-4 high-quality technical articles per month on AI/ML topics to build topical authority.",
            ))

        # Check title tag competitiveness
        for page in pages:
            soup = page.get("soup")
            if not soup:
                continue
            meta = crawler.extract_meta(soup)
            title = meta.get("title", "")
            if title and "amulya gupta" not in title.lower() and page["url"].replace(SITE_URL, "") in ["/", "/amulya-gupta.html", "/about.html"]:
                findings.append(Finding(
                    title=f"Name not in title tag: {page['url'].replace(SITE_URL,'')}",
                    description="Personal brand pages should include your name in the title for branded search.",
                    severity="warning",
                    category="competitive",
                    url=page["url"],
                    recommendation="Include 'Amulya Gupta' in the page title for personal brand visibility.",
                ))

        # Self-assessment vs competitive benchmarks
        benchmarks = [
            ("llms.txt exists", True),
            ("Blog section active", len(blog_pages) > 0),
            ("Person schema", "Person" in own_schema_types),
            ("Multiple schema types", len(own_schema_types) >= 3),
        ]

        for benchmark, met in benchmarks:
            if not met:
                findings.append(Finding(
                    title=f"Competitive gap: {benchmark}",
                    description=f"Benchmark '{benchmark}' not met — competitor sites typically implement this.",
                    severity="info",
                    category="competitive",
                    url=SITE_URL,
                    recommendation=f"Implement '{benchmark}' to meet competitive SEO standards.",
                ))

        score = self.clamp_score(70, findings=findings)
        return self.result(score, findings, {
            "own_schema_types": list(own_schema_types),
            "blog_pages": len(blog_pages),
        })
