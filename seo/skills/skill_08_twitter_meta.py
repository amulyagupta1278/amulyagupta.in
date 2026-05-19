"""Skill 08 — Twitter / X Card Meta Tags"""
from .base import BaseSkill

REQUIRED_TWITTER = ["twitter:card", "twitter:title", "twitter:description", "twitter:image"]


class TwitterMetaSkill(BaseSkill):
    name = "Twitter / X Card Meta Tags"
    priority = "P6"
    skill_number = 8

    def run(self) -> dict:
        findings = []
        auto_fixes = []

        for f in self.html_files:
            soup = self.parse(f)
            page = str(f.relative_to(self.site_root))

            twitter_tags = {}
            for tag in soup.find_all("meta"):
                name = tag.get("name", "")
                if name.startswith("twitter:"):
                    twitter_tags[name] = tag.get("content", "")

            missing = [t for t in REQUIRED_TWITTER if t not in twitter_tags]
            if missing:
                severity = "warning" if "twitter:card" in missing else "info"
                findings.append(self.finding(
                    "TWITTER_001", f"Missing Twitter tags on {page}: {', '.join(missing)}",
                    severity, "P6",
                    f"Missing: {', '.join(missing)}. Required for proper X/Twitter link previews.",
                    "Add all four Twitter Card meta tags: card, title, description, image.",
                    "Posts shared without Twitter cards show plain text — dramatically lower engagement.",
                    pages=[page]
                ))
                self._add_twitter_tags(f, soup, missing, auto_fixes)

            # Card type check
            card_type = twitter_tags.get("twitter:card", "")
            if card_type and card_type not in ["summary", "summary_large_image", "app", "player"]:
                findings.append(self.finding(
                    "TWITTER_002", f"Invalid twitter:card type '{card_type}' on {page}", "warning", "P6",
                    f"twitter:card='{card_type}' is not a recognized card type.",
                    "Use 'summary_large_image' for portfolio/blog pages for maximum visual impact.",
                    pages=[page]
                ))

            # Description length
            tw_desc = twitter_tags.get("twitter:description", "")
            if tw_desc and len(tw_desc) > 200:
                findings.append(self.finding(
                    "TWITTER_003", f"twitter:description too long ({len(tw_desc)} chars) on {page}",
                    "info", "P6",
                    "Twitter truncates descriptions beyond 200 characters.",
                    "Keep twitter:description under 200 characters.",
                    pages=[page]
                ))

        if not findings:
            return self.result([], f"Twitter Card tags validated on all {len(self.html_files)} pages.", auto_fixes)

        return self.result(findings, f"Twitter meta audit: {len(findings)} issue(s). {len(auto_fixes)} auto-fix(es).",
                           auto_fixes,
                           ["Validate Twitter Cards at https://cards-dev.twitter.com/validator after changes."])

    def _add_twitter_tags(self, path, soup, missing: list, auto_fixes: list):
        content = path.read_text(encoding="utf-8")
        title = soup.find("title")
        title_text = title.get_text(strip=True) if title else "Amulya Gupta | AI Systems Engineer"
        meta_desc = soup.find("meta", attrs={"name": "description"})
        desc_text = meta_desc.get("content", "") if meta_desc else "AI Systems Engineer | Agentic AI | MLOps"
        image = "https://github.com/amulyagupta1278.png"

        tag_map = {
            "twitter:card": "summary_large_image",
            "twitter:title": title_text[:70],
            "twitter:description": desc_text[:200],
            "twitter:image": image,
        }
        additions = [f'<meta name="{t}" content="{tag_map[t]}">' for t in missing if t in tag_map]
        if additions:
            insert_before = "</head>"
            snippet = "\n    ".join([""] + additions) + "\n"
            new_content = content.replace(insert_before, snippet + insert_before, 1)
            path.write_text(new_content, encoding="utf-8")
            auto_fixes.append(f"Added Twitter tags {missing} to {path.relative_to(self.site_root)}.")
