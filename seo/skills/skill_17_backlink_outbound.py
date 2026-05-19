import crawler
from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL

TRUSTED_DOMAINS = {
    "github.com", "linkedin.com", "bits-pilani.ac.in", "hcltech.com",
    "arxiv.org", "pytorch.org", "tensorflow.org", "kubernetes.io",
    "mlflow.org", "huggingface.co", "langchain.com", "openai.com",
}

SUSPICIOUS_PATTERNS = ["casino", "pharma", "viagra", "loan", "crypto-pump"]


class Skill17BacklinkOutbound(BaseSEOSkill):
    SKILL_ID = 17
    SKILL_NAME = "Backlink & Outbound Link Audit"

    def run(self, pages: list[dict]) -> SkillResult:
        findings = []
        all_external = []

        for page in pages:
            url = page["url"]
            path = url.replace(SITE_URL, "")
            soup = page.get("soup")
            if not soup or page.get("status") != 200:
                continue

            links = crawler.get_all_links(soup)
            external = links["external"]
            all_external.extend({"from": url, **e} for e in external)

            # External links without rel="nofollow" or rel="noopener"
            for a_tag in soup.find_all("a", href=True):
                href = a_tag.get("href", "")
                rel = a_tag.get("rel", [])
                rel_str = " ".join(rel).lower() if isinstance(rel, list) else str(rel).lower()

                if href.startswith("http") and SITE_URL not in href:
                    domain = href.split("/")[2] if len(href.split("/")) > 2 else ""

                    # Suspicious external links
                    if any(p in href.lower() for p in SUSPICIOUS_PATTERNS):
                        findings.append(Finding(
                            title=f"Suspicious outbound link: {path}",
                            description=f"Link to potentially harmful domain: {href[:100]}",
                            severity="critical",
                            category="outbound-links",
                            url=url,
                            recommendation="Remove this link immediately — it may harm trust and rankings.",
                            evidence=f"href='{href[:100]}'",
                        ))

                    # Missing noopener on external links
                    if "noopener" not in rel_str and "noreferrer" not in rel_str:
                        findings.append(Finding(
                            title=f"External link missing rel=noopener: {path}",
                            description=f"Link to {domain} opens without rel='noopener noreferrer'.",
                            severity="info",
                            category="outbound-links",
                            url=url,
                            recommendation="Add rel='noopener noreferrer' to external links for security.",
                            evidence=f"href='{href[:80]}'",
                        ))

        # Check for broken external links (sample first 5 unique)
        unique_external = list({e["url"]: e for e in all_external}.values())[:5]
        broken_external = 0
        for ext in unique_external:
            result = crawler.fetch(ext["url"])
            if result["status"] in (404, 410, 0):
                broken_external += 1
                findings.append(Finding(
                    title=f"Broken external link: {ext['url'][:80]}",
                    description=f"External link returns HTTP {result['status']} from {ext['from'].replace(SITE_URL,'')}",
                    severity="warning",
                    category="outbound-links",
                    url=ext["from"],
                    recommendation="Remove or replace this broken external link.",
                    evidence=f"URL: {ext['url'][:100]}",
                ))

        # No external links at all
        if not all_external:
            findings.append(Finding(
                title="No external links found",
                description="Site has no outbound links to external resources.",
                severity="info",
                category="outbound-links",
                url=SITE_URL,
                recommendation="Link to authoritative external resources to add value and signal content quality.",
            ))

        score = self.clamp_score(100, findings=findings)
        return self.result(score, findings, {
            "total_external_links": len(all_external),
            "unique_external_domains": len(set(e.get("url", "").split("/")[2] for e in all_external if e.get("url", "").startswith("http"))),
            "broken_external": broken_external,
        })
