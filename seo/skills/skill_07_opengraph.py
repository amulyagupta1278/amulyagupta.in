"""Skill 07 — OpenGraph Tags Validation"""
from bs4 import BeautifulSoup
from .base import BaseSkill

REQUIRED_OG = ["og:title", "og:description", "og:image", "og:url", "og:type"]


class OpenGraphSkill(BaseSkill):
    name = "OpenGraph Tags Validation"
    priority = "P6"
    skill_number = 7

    def run(self) -> dict:
        findings = []
        auto_fixes = []

        for f in self.html_files:
            soup = self.parse(f)
            page = str(f.relative_to(self.site_root))

            og_tags = {
                tag.get("property", ""): tag.get("content", "")
                for tag in soup.find_all("meta", property=True)
                if tag.get("property", "").startswith("og:")
            }

            missing = [prop for prop in REQUIRED_OG if prop not in og_tags]
            if missing:
                severity = "critical" if "og:title" in missing or "og:description" in missing else "warning"
                findings.append(self.finding(
                    "OG_001", f"Missing OG tags on {page}: {', '.join(missing)}",
                    severity, "P6",
                    f"OpenGraph properties missing: {', '.join(missing)}",
                    "Add missing OG tags for proper link previews on LinkedIn, Slack, and social media.",
                    "Missing og:image means no preview image on social shares — hurts click-through significantly.",
                    pages=[page]
                ))
                self._add_og_tags(f, soup, og_tags, missing, auto_fixes)

            # Check og:image is absolute
            if "og:image" in og_tags and og_tags["og:image"].startswith("/"):
                findings.append(self.finding(
                    "OG_002", f"og:image is relative URL on {page}", "warning", "P6",
                    f"og:image='{og_tags['og:image']}' should be an absolute URL.",
                    "Change og:image to use the full absolute URL: https://amulyagupta.in/...",
                    "Relative og:image URLs fail on external platforms (LinkedIn, Twitter, etc.).",
                    pages=[page]
                ))

            # og:url mismatch with canonical
            canonical = soup.find("link", rel="canonical")
            og_url = og_tags.get("og:url", "")
            if canonical and og_url and canonical.get("href", "") != og_url:
                findings.append(self.finding(
                    "OG_003", f"og:url doesn't match canonical on {page}", "info", "P6",
                    f"Canonical: {canonical.get('href')} | og:url: {og_url}",
                    "Make og:url identical to the canonical URL for consistency.",
                    pages=[page]
                ))

        if not findings:
            return self.result([], f"OpenGraph tags validated on all {len(self.html_files)} pages.", auto_fixes)

        return self.result(findings,
                           f"OG audit: {len(findings)} issue(s). {len(auto_fixes)} auto-fix(es) applied.",
                           auto_fixes,
                           ["Use https://developers.facebook.com/tools/debug/ to validate OG tags after changes."])

    def _add_og_tags(self, path, soup: BeautifulSoup, existing: dict, missing: list, auto_fixes: list):
        content = path.read_text(encoding="utf-8")
        head = soup.find("head")
        if not head:
            return
        page_url = self._expected_url(path)
        title = (soup.find("title") or {}).get_text(strip=True) if soup.find("title") else ""
        meta_desc = (soup.find("meta", attrs={"name": "description"}) or {})
        desc = meta_desc.get("content", "") if hasattr(meta_desc, "get") else ""
        image = "https://github.com/amulyagupta1278.png"

        additions = []
        tag_map = {
            "og:title": title or "Amulya Gupta | AI Systems Engineer",
            "og:description": desc or "AI Systems Engineer specializing in Agentic AI, LLM Pipelines, and MLOps.",
            "og:image": image,
            "og:url": page_url,
            "og:type": "website"
        }
        for prop in missing:
            val = tag_map.get(prop, "")
            if val:
                additions.append(f'<meta property="{prop}" content="{val}">')

        if additions:
            insert_point = "</head>"
            new_content = content.replace(insert_point, "\n    ".join([""] + additions) + "\n" + insert_point, 1)
            path.write_text(new_content, encoding="utf-8")
            auto_fixes.append(f"Added OG tags {missing} to {path.relative_to(self.site_root)}.")

    def _expected_url(self, path) -> str:
        rel = path.relative_to(self.site_root)
        parts = rel.parts
        if parts[-1] == "index.html":
            return self.site_url + ("/" if len(parts) == 1 else "/" + "/".join(parts[:-1]) + "/")
        return self.site_url + "/" + str(rel)
