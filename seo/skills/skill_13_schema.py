"""Skill 13 — Structured Data / Schema Validation"""
import json
from .base import BaseSkill

PERSON_REQUIRED = ["name", "jobTitle", "url", "email", "sameAs"]
BLOG_REQUIRED = ["headline", "author", "datePublished", "description"]


class SchemaSkill(BaseSkill):
    name = "Structured Data Schema Validation"
    priority = "P5"
    skill_number = 13

    def run(self) -> dict:
        findings = []
        auto_fixes = []

        for f in self.html_files:
            soup = self.parse(f)
            page = str(f.relative_to(self.site_root))
            scripts = soup.find_all("script", type="application/ld+json")

            if not scripts:
                # Blog posts should always have schema
                if "blog/" in page and page != "blog/index.html":
                    findings.append(self.finding(
                        "SCHEMA_001", f"No JSON-LD schema on blog post: {page}", "warning", "P5",
                        f"Blog post {page} has no structured data markup.",
                        "Add BlogPosting schema with headline, author, datePublished, description, url.",
                        "Blog posts with schema get rich snippets in search results — higher CTR.",
                        pages=[page]
                    ))
                    self._add_blog_schema(f, soup, auto_fixes)
                continue

            for script in scripts:
                try:
                    data = json.loads(script.string or "{}")
                except json.JSONDecodeError as e:
                    findings.append(self.finding(
                        "SCHEMA_002", f"Invalid JSON-LD on {page}", "critical", "P5",
                        f"JSON parse error: {e}",
                        "Fix the JSON syntax error in the schema markup.",
                        "Invalid JSON-LD is ignored entirely by search engines.",
                        pages=[page]
                    ))
                    continue

                schema_type = data.get("@type", "")

                if schema_type == "Person":
                    missing_props = [p for p in PERSON_REQUIRED if p not in data]
                    if missing_props:
                        findings.append(self.finding(
                            "SCHEMA_003", f"Person schema missing properties on {page}: {', '.join(missing_props)}",
                            "warning", "P5",
                            f"Person schema lacks: {', '.join(missing_props)}",
                            f"Add missing properties to the Person schema: {', '.join(missing_props)}",
                            "Incomplete Person schema reduces Knowledge Graph eligibility.",
                            pages=[page]
                        ))
                        self._fix_person_schema(f, data, missing_props, auto_fixes)

                elif schema_type in ["BlogPosting", "Article"]:
                    missing_props = [p for p in BLOG_REQUIRED if p not in data]
                    if missing_props:
                        findings.append(self.finding(
                            "SCHEMA_004", f"BlogPosting schema missing: {', '.join(missing_props)} on {page}",
                            "warning", "P5",
                            f"BlogPosting/Article schema lacks required: {', '.join(missing_props)}",
                            "Add missing properties for rich snippet eligibility.",
                            "Incomplete blog schema misses article rich results in search.",
                            pages=[page]
                        ))

                    # Check image
                    if "image" not in data:
                        findings.append(self.finding(
                            "SCHEMA_005", f"BlogPosting missing image on {page}", "info", "P5",
                            "Article schema should include an 'image' property for rich snippets.",
                            "Add 'image': 'https://github.com/amulyagupta1278.png' to blog post schema.",
                            pages=[page]
                        ))

                # Check @context
                context = data.get("@context", "")
                if context and "schema.org" not in context:
                    findings.append(self.finding(
                        "SCHEMA_006", f"Non-standard @context on {page}", "warning", "P5",
                        f"@context='{context}' — should be 'https://schema.org'.",
                        "Set '@context': 'https://schema.org' in all JSON-LD blocks.",
                        pages=[page]
                    ))

        if not findings:
            return self.result([], f"Schema markup validated on all {len(self.html_files)} pages.", auto_fixes,
                               ["Consider adding FAQ schema to blog posts with Q&A content.",
                                "Add HowTo schema to tutorial-style blog posts."])

        return self.result(findings, f"Schema audit: {len(findings)} issue(s). {len(auto_fixes)} auto-fix(es).", auto_fixes,
                           ["Validate schema at https://validator.schema.org/ and Google's Rich Results Test."])

    def _add_blog_schema(self, path, soup, auto_fixes: list):
        content = path.read_text(encoding="utf-8")
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else "Blog Post"
        meta_desc = soup.find("meta", attrs={"name": "description"})
        desc = meta_desc.get("content", "") if meta_desc else ""
        page_url = self.site_url + "/" + str(path.relative_to(self.site_root))

        schema = {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": title[:110],
            "description": desc[:300],
            "url": page_url,
            "author": {"@type": "Person", "name": "Amulya Gupta", "url": self.site_url},
            "publisher": {"@type": "Person", "name": "Amulya Gupta"},
            "image": "https://github.com/amulyagupta1278.png",
            "datePublished": "2025-01-01",
            "dateModified": "2025-01-01"
        }
        schema_tag = f'\n<script type="application/ld+json">\n{json.dumps(schema, indent=2)}\n</script>'
        new_content = content.replace("</head>", schema_tag + "\n</head>", 1)
        path.write_text(new_content, encoding="utf-8")
        auto_fixes.append(f"Added BlogPosting schema to {path.relative_to(self.site_root)}.")

    def _fix_person_schema(self, path, data: dict, missing: list, auto_fixes: list):
        content = path.read_text(encoding="utf-8")
        defaults = {
            "name": "Amulya Gupta",
            "jobTitle": "AI Systems Engineer",
            "url": self.site_url,
            "email": "amulya@amulyagupta.in",
            "sameAs": [
                "https://www.linkedin.com/in/amulyagupta1278/",
                "https://github.com/amulyagupta1278"
            ]
        }
        try:
            import re
            schema_str = json.dumps(data, indent=2)
            for prop in missing:
                if prop in defaults:
                    data[prop] = defaults[prop]
            new_schema = json.dumps(data, indent=2)
            new_content = content.replace(schema_str, new_schema, 1)
            if new_content != content:
                path.write_text(new_content, encoding="utf-8")
                auto_fixes.append(f"Added missing Person schema properties ({', '.join(missing)}) to {path.relative_to(self.site_root)}.")
        except Exception:
            pass
