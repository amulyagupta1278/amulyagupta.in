import json
import crawler
from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL

EXPECTED_SCHEMAS = {
    "/": ["Person", "WebSite"],
    "/about.html": ["Person"],
    "/amulya-gupta.html": ["Person"],
    "/projects.html": ["ItemList"],
    "/experience.html": ["Person"],
    "/blog/post-1-mlops-pipeline.html": ["BlogPosting", "Article"],
    "/blog/post-2-mlops-stack.html": ["BlogPosting", "Article"],
    "/blog/ai-ml-guide-2026.html": ["BlogPosting", "Article"],
    "/blog/index.html": ["Blog", "ItemList"],
    "/contact.html": ["Person"],
}

REQUIRED_PROPS = {
    "Person": ["name", "url"],
    "BlogPosting": ["headline", "datePublished", "author"],
    "Article": ["headline", "author"],
    "WebSite": ["name", "url"],
    "ItemList": ["itemListElement"],
    "BreadcrumbList": ["itemListElement"],
}


def flatten_schemas(raw: list) -> list[dict]:
    flat = []
    for item in raw:
        if "@graph" in item:
            flat.extend(item["@graph"] if isinstance(item["@graph"], list) else [item["@graph"]])
        else:
            flat.append(item)
    return flat


class Skill04StructuredData(BaseSEOSkill):
    SKILL_ID = 4
    SKILL_NAME = "Structured Data Audit"

    def run(self, pages: list[dict]) -> SkillResult:
        findings = []
        pages_with_schema = 0
        schema_errors = 0

        for page in pages:
            url = page["url"]
            path = url.replace(SITE_URL, "")
            soup = page.get("soup")
            if not soup:
                continue

            raw = crawler.extract_json_ld(soup)
            schemas = flatten_schemas(raw)

            if not schemas:
                expected = EXPECTED_SCHEMAS.get(path, [])
                if expected:
                    findings.append(Finding(
                        title=f"Missing schema markup: {path}",
                        description=f"No structured data found. Expected: {', '.join(expected)}",
                        severity="warning",
                        category="schema",
                        url=url,
                        recommendation=f"Add JSON-LD structured data ({', '.join(expected)}) to this page.",
                    ))
                continue

            pages_with_schema += 1
            schema_types = [s.get("@type", "") for s in schemas]

            expected = EXPECTED_SCHEMAS.get(path, [])
            for exp in expected:
                if not any(exp.lower() in str(st).lower() for st in schema_types):
                    findings.append(Finding(
                        title=f"Missing {exp} schema: {path}",
                        description=f"Expected {exp} schema not found. Found: {schema_types}",
                        severity="warning",
                        category="schema",
                        url=url,
                        recommendation=f"Add {exp} JSON-LD schema to this page.",
                    ))

            for schema in schemas:
                s_type = schema.get("@type", "Unknown")
                required = REQUIRED_PROPS.get(s_type, [])
                for prop in required:
                    if prop not in schema:
                        findings.append(Finding(
                            title=f"Missing required property '{prop}' in {s_type}: {path}",
                            description=f"Schema type {s_type} is missing required property '{prop}'.",
                            severity="warning",
                            category="schema",
                            url=url,
                            recommendation=f"Add the '{prop}' property to the {s_type} schema.",
                        ))
                        schema_errors += 1

                if "@context" not in schema:
                    findings.append(Finding(
                        title=f"Missing @context in schema: {path}",
                        description="JSON-LD schema block is missing @context declaration.",
                        severity="warning",
                        category="schema",
                        url=url,
                        recommendation="Add '@context': 'https://schema.org' to all JSON-LD blocks.",
                    ))

                if s_type == "BlogPosting":
                    if "datePublished" in schema:
                        dp = schema["datePublished"]
                        if not str(dp)[:4].isdigit():
                            findings.append(Finding(
                                title=f"Invalid datePublished in BlogPosting: {path}",
                                description=f"datePublished '{dp}' is not a valid ISO 8601 date.",
                                severity="warning",
                                category="schema",
                                url=url,
                                recommendation="Use ISO 8601 format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ",
                            ))

        total = len([p for p in pages if p.get("soup")])
        coverage_pct = (pages_with_schema / total * 100) if total else 0
        score = min(100, int(coverage_pct) - schema_errors * 3)
        score = self.clamp_score(score, findings=findings)

        return self.result(score, findings, {
            "pages_with_schema": pages_with_schema,
            "total_pages": total,
            "coverage_pct": round(coverage_pct, 1),
            "schema_errors": schema_errors,
        })
