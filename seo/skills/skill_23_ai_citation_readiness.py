import crawler
from base import BaseSEOSkill, Finding
from config import SITE_URL

CITATION_SIGNALS = [
    "author", "datePublished", "dateModified", "publisher", "citation",
    "isPartOf", "about", "mentions", "citation", "creditsTo",
]

AUTHORITATIVE_CLAIMS = [
    "years of experience", "worked at", "published", "contributed to",
    "built", "developed", "designed", "led", "architected",
]


class Skill23AICitationReadiness(BaseSEOSkill):
    SKILL_ID = 23
    SKILL_NAME = "AI Citation Readiness"

    def run(self, pages: list[dict]) -> SkillResult:
        from base import SkillResult
        findings = []
        citation_score = 100

        for page in pages:
            url = page["url"]
            path = url.replace(SITE_URL, "")
            soup = page.get("soup")
            if not soup or page.get("status") != 200:
                continue

            schemas = crawler.extract_json_ld(soup)
            flat_schemas = []
            for s in schemas:
                if "@graph" in s:
                    flat_schemas.extend(s["@graph"] if isinstance(s["@graph"], list) else [s["@graph"]])
                else:
                    flat_schemas.append(s)

            # Author attribution on blog posts
            if "blog/post" in path or "guide" in path:
                has_author = any(
                    "author" in s for s in flat_schemas
                ) or bool(soup.find(attrs={"rel": "author"}) or soup.find(class_=lambda c: c and "author" in c.lower()))

                if not has_author:
                    citation_score -= 15
                    findings.append(Finding(
                        title=f"Missing author attribution: {path}",
                        description="AI systems need clear author attribution to cite content credibly.",
                        severity="critical",
                        category="citation",
                        url=url,
                        recommendation="Add Author schema and visible byline ('By Amulya Gupta') to all blog posts.",
                    ))

                has_date = any("datePublished" in s for s in flat_schemas)
                if not has_date:
                    citation_score -= 10
                    findings.append(Finding(
                        title=f"Missing publication date: {path}",
                        description="AI systems require publication dates to assess content freshness and cite correctly.",
                        severity="warning",
                        category="citation",
                        url=url,
                        recommendation="Add datePublished in ISO 8601 format to BlogPosting schema and visibly on page.",
                    ))

            # Person schema quality (for identity/citation)
            person_schemas = [s for s in flat_schemas if s.get("@type") == "Person"]
            if person_schemas:
                ps = person_schemas[0]
                for field in ["name", "url", "sameAs", "jobTitle", "alumniOf", "worksFor", "knowsAbout"]:
                    if field not in ps:
                        findings.append(Finding(
                            title=f"Person schema missing '{field}': {path}",
                            description=f"AI citation systems use Person schema fields to build entity knowledge.",
                            severity="info" if field in ["knowsAbout", "alumniOf"] else "warning",
                            category="citation",
                            url=url,
                            recommendation=f"Add '{field}' to Person schema to improve AI entity recognition.",
                        ))

            # Check for structured fact statements (definition lists, key stats)
            dl = soup.find_all("dl")
            blockquotes = soup.find_all("blockquote")
            stats = soup.find_all(class_=lambda c: c and any(k in c.lower() for k in ["stat", "fact", "metric", "highlight"]))

            if not dl and not stats and path in ["/", "/about.html", "/amulya-gupta.html"]:
                findings.append(Finding(
                    title=f"No structured fact markup: {path}",
                    description="AI systems prefer structured facts (definition lists, highlighted stats) for citations.",
                    severity="info",
                    category="citation",
                    url=url,
                    recommendation="Add structured fact markup: use <dl> for skills/facts, highlight key stats with semantic classes.",
                ))

            # Check for canonical source signals
            body_text = soup.get_text(separator=" ", strip=True).lower()
            if not any(claim in body_text for claim in AUTHORITATIVE_CLAIMS):
                if path in ["/", "/about.html", "/amulya-gupta.html", "/experience.html"]:
                    findings.append(Finding(
                        title=f"Weak authority signals: {path}",
                        description="Page lacks explicit authority signals (experience years, specific achievements).",
                        severity="info",
                        category="citation",
                        url=url,
                        recommendation="Add quantified achievements: 'X years experience', 'Built system for Y users', 'Led team of Z'.",
                    ))

        # llms.txt citation readiness
        llms = crawler.fetch(f"{SITE_URL}/llms.txt")
        if llms["status"] == 200:
            content = llms.get("html", "")
            if "github.com" not in content or "linkedin.com" not in content:
                findings.append(Finding(
                    title="llms.txt missing authoritative profile links",
                    description="llms.txt should link to GitHub and LinkedIn for cross-reference verification.",
                    severity="warning",
                    category="citation",
                    url=f"{SITE_URL}/llms.txt",
                    recommendation="Add GitHub, LinkedIn, and email links to llms.txt for AI entity verification.",
                ))

        score = self.clamp_score(citation_score, findings=findings)
        return self.result(score, findings, {"citation_score": citation_score})
