import crawler
from base import BaseSEOSkill, Finding
from config import SITE_URL

TITLE_MIN, TITLE_MAX = 30, 60
DESC_MIN, DESC_MAX = 120, 160


class Skill06MetaTagsOG(BaseSEOSkill):
    SKILL_ID = 6
    SKILL_NAME = "Meta Tags & Open Graph Audit"

    def run(self, pages: list[dict]) -> SkillResult:
        from base import SkillResult
        findings = []
        seen_titles = {}
        seen_descs = {}

        for page in pages:
            url = page["url"]
            path = url.replace(SITE_URL, "")
            soup = page.get("soup")
            if not soup:
                continue

            meta = crawler.extract_meta(soup)
            title = meta.get("title", "")
            desc = meta.get("description", "")

            # Title
            if not title:
                findings.append(Finding(
                    title=f"Missing <title>: {path}",
                    description="Page has no <title> tag.",
                    severity="critical",
                    category="meta",
                    url=url,
                    recommendation="Add a descriptive <title> tag (30–60 characters) that includes the primary keyword.",
                ))
            else:
                if len(title) < TITLE_MIN:
                    findings.append(Finding(
                        title=f"Title too short ({len(title)} chars): {path}",
                        description=f"Title '{title}' is shorter than {TITLE_MIN} characters.",
                        severity="warning",
                        category="meta",
                        url=url,
                        recommendation=f"Expand the title to at least {TITLE_MIN} characters while keeping it under {TITLE_MAX}.",
                    ))
                elif len(title) > TITLE_MAX:
                    findings.append(Finding(
                        title=f"Title too long ({len(title)} chars): {path}",
                        description=f"Title '{title[:50]}...' exceeds {TITLE_MAX} characters and may be truncated in SERPs.",
                        severity="warning",
                        category="meta",
                        url=url,
                        recommendation=f"Shorten the title to under {TITLE_MAX} characters.",
                    ))

                # Duplicate titles
                if title in seen_titles:
                    findings.append(Finding(
                        title=f"Duplicate title: {path}",
                        description=f"Same title as {seen_titles[title]}: '{title}'",
                        severity="critical",
                        category="meta",
                        url=url,
                        recommendation="Make each page title unique to avoid keyword cannibalization.",
                    ))
                else:
                    seen_titles[title] = path

            # Description
            if not desc:
                findings.append(Finding(
                    title=f"Missing meta description: {path}",
                    description="No meta description found.",
                    severity="warning",
                    category="meta",
                    url=url,
                    recommendation=f"Add a compelling meta description ({DESC_MIN}–{DESC_MAX} chars) with primary keyword.",
                ))
            else:
                if len(desc) < DESC_MIN:
                    findings.append(Finding(
                        title=f"Short meta description ({len(desc)} chars): {path}",
                        description=f"Description is shorter than {DESC_MIN} characters.",
                        severity="warning",
                        category="meta",
                        url=url,
                        recommendation="Expand the description to 120–160 characters.",
                    ))
                elif len(desc) > DESC_MAX:
                    findings.append(Finding(
                        title=f"Long meta description ({len(desc)} chars): {path}",
                        description=f"Description exceeds {DESC_MAX} characters and will be truncated.",
                        severity="warning",
                        category="meta",
                        url=url,
                        recommendation="Shorten the description to under 160 characters.",
                    ))

                if desc in seen_descs:
                    findings.append(Finding(
                        title=f"Duplicate meta description: {path}",
                        description=f"Same description as {seen_descs[desc]}",
                        severity="warning",
                        category="meta",
                        url=url,
                        recommendation="Write unique meta descriptions for each page.",
                    ))
                else:
                    seen_descs[desc] = path

            # Open Graph
            og_title = meta.get("og:title", "")
            og_desc = meta.get("og:description", "")
            og_image = meta.get("og:image", "")
            og_url = meta.get("og:url", "")

            for og_key, label in [("og:title", og_title), ("og:description", og_desc),
                                   ("og:image", og_image), ("og:url", og_url)]:
                if not label:
                    sev = "warning" if og_key != "og:image" else "warning"
                    findings.append(Finding(
                        title=f"Missing {og_key}: {path}",
                        description=f"Open Graph tag '{og_key}' is missing.",
                        severity=sev,
                        category="open-graph",
                        url=url,
                        recommendation=f"Add <meta property='{og_key}' content='...'> for better social sharing.",
                    ))

            # Twitter Card
            tw_card = meta.get("twitter:card", "")
            if not tw_card:
                findings.append(Finding(
                    title=f"Missing Twitter Card: {path}",
                    description="No twitter:card meta tag found.",
                    severity="info",
                    category="social",
                    url=url,
                    recommendation="Add <meta name='twitter:card' content='summary_large_image'> for Twitter sharing.",
                ))

            # Viewport
            viewport = meta.get("viewport", "")
            if not viewport:
                findings.append(Finding(
                    title=f"Missing viewport meta: {path}",
                    description="No <meta name='viewport'> tag found.",
                    severity="critical",
                    category="mobile",
                    url=url,
                    recommendation="Add <meta name='viewport' content='width=device-width, initial-scale=1'>",
                ))

        score = self.clamp_score(100, findings=findings)
        return self.result(score, findings)
