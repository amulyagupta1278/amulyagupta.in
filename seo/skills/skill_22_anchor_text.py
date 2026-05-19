from collections import defaultdict
import crawler
from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL

GENERIC_ANCHORS = {
    "click here", "here", "read more", "learn more", "this", "link",
    "page", "more", "view", "see more", "go", "visit", "check out",
    "follow", "watch", "download", "get it", "find out",
}


class Skill22AnchorText(BaseSEOSkill):
    SKILL_ID = 22
    SKILL_NAME = "Anchor Text Optimization"

    def run(self, pages: list[dict]) -> SkillResult:
        findings = []

        anchor_to_urls = defaultdict(list)
        url_to_anchors = defaultdict(list)
        total_links = 0
        generic_count = 0

        for page in pages:
            url = page["url"]
            soup = page.get("soup")
            if not soup or page.get("status") != 200:
                continue

            links = crawler.get_all_links(soup)
            for link in links["internal"]:
                text = link["text"].strip().lower()
                target = link["url"]
                total_links += 1

                if text:
                    anchor_to_urls[text].append({"from": url, "to": target})
                    url_to_anchors[target].append(text)

                if text in GENERIC_ANCHORS:
                    generic_count += 1
                    path = url.replace(SITE_URL, "")
                    findings.append(Finding(
                        title=f"Generic anchor text: '{text}' on {path}",
                        description=f"Generic anchor '{text}' links to {target.replace(SITE_URL,'')}",
                        severity="info",
                        category="anchor-text",
                        url=url,
                        recommendation=f"Replace '{text}' with descriptive anchor text that includes the target page's topic/keyword.",
                        evidence=f"'{text}' → {target}",
                    ))

        # Same anchor text pointing to multiple different URLs (over-optimization signal)
        for anchor, targets in anchor_to_urls.items():
            target_urls = list(set(t["to"] for t in targets))
            if len(target_urls) > 1 and anchor not in GENERIC_ANCHORS and len(anchor) > 4:
                findings.append(Finding(
                    title=f"Same anchor points to multiple URLs: '{anchor}'",
                    description=f"Anchor '{anchor}' points to {len(target_urls)} different URLs — confusing for search engines.",
                    severity="warning",
                    category="anchor-text",
                    url=targets[0]["from"],
                    recommendation="Use distinct anchor text for each target page to clarify relevance.",
                    evidence=f"Targets: {', '.join(url.replace(SITE_URL,'') for url in target_urls[:3])}",
                ))

        # Pages with only one anchor text variation
        for target_url, anchors in url_to_anchors.items():
            unique_anchors = set(a for a in anchors if a and a not in GENERIC_ANCHORS)
            if len(unique_anchors) == 0 and len(anchors) > 2:
                path = target_url.replace(SITE_URL, "")
                findings.append(Finding(
                    title=f"No descriptive anchors pointing to: {path}",
                    description="All internal links use generic text — no keyword signals for this page.",
                    severity="warning",
                    category="anchor-text",
                    url=target_url,
                    recommendation="Add descriptive keyword-rich anchor text when linking to this page.",
                ))

        # Anchor text diversity analysis
        if total_links > 0:
            generic_pct = generic_count / total_links * 100
            if generic_pct > 30:
                findings.append(Finding(
                    title=f"High generic anchor text ratio: {generic_pct:.0f}%",
                    description=f"{generic_count} of {total_links} internal links use generic anchor text.",
                    severity="warning",
                    category="anchor-text",
                    url=SITE_URL,
                    recommendation="Replace generic anchors with descriptive keyword-rich text across the site.",
                ))

        score = max(0, 100 - generic_count * 5 - len(findings) * 3)
        score = self.clamp_score(score, findings=findings)
        return self.result(score, findings, {
            "total_internal_links": total_links,
            "generic_anchor_count": generic_count,
            "generic_pct": round(generic_count / max(total_links, 1) * 100, 1),
        })
