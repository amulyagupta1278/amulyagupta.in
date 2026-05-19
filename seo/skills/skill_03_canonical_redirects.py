import crawler
from base import BaseSEOSkill, Finding
from config import SITE_URL


class Skill03CanonicalRedirects(BaseSEOSkill):
    SKILL_ID = 3
    SKILL_NAME = "Canonical & Redirects Audit"

    def run(self, pages: list[dict]) -> SkillResult:
        from base import SkillResult
        findings = []

        for page in pages:
            url = page["url"]
            path = url.replace(SITE_URL, "")
            soup = page.get("soup")
            status = page["status"]

            if status == 0 or not soup:
                continue

            # Canonical tag check
            canon_tag = soup.find("link", rel="canonical")
            if not canon_tag:
                findings.append(Finding(
                    title=f"Missing canonical tag: {path}",
                    description="No <link rel='canonical'> tag found.",
                    severity="warning",
                    category="canonical",
                    url=url,
                    recommendation=f"Add <link rel='canonical' href='{url}'> in the <head> section.",
                ))
            else:
                canon_href = canon_tag.get("href", "").strip()
                if not canon_href:
                    findings.append(Finding(
                        title=f"Empty canonical href: {path}",
                        description="Canonical tag exists but has an empty href attribute.",
                        severity="critical",
                        category="canonical",
                        url=url,
                        recommendation="Set the canonical href to the preferred URL of this page.",
                    ))
                elif not canon_href.startswith("https://"):
                    findings.append(Finding(
                        title=f"Non-HTTPS canonical: {path}",
                        description=f"Canonical points to non-HTTPS URL: {canon_href}",
                        severity="warning",
                        category="canonical",
                        url=url,
                        recommendation="Use the HTTPS version of the canonical URL.",
                    ))
                elif canon_href.rstrip("/") != url.rstrip("/"):
                    findings.append(Finding(
                        title=f"Cross-page canonical: {path}",
                        description=f"Canonical points to different URL: {canon_href}",
                        severity="info",
                        category="canonical",
                        url=url,
                        recommendation="Verify this cross-page canonical is intentional. Self-referencing is safest.",
                        evidence=f"Page: {url} → Canonical: {canon_href}",
                    ))

            # Multiple canonical tags
            all_canonicals = soup.find_all("link", rel="canonical")
            if len(all_canonicals) > 1:
                findings.append(Finding(
                    title=f"Multiple canonical tags: {path}",
                    description=f"Found {len(all_canonicals)} canonical tags — only one is allowed.",
                    severity="critical",
                    category="canonical",
                    url=url,
                    recommendation="Remove all but one canonical tag from this page.",
                ))

            # Check redirect chain
            if status in (301, 302):
                redirect_target = page.get("redirect_url", "")
                findings.append(Finding(
                    title=f"Redirect: {path}",
                    description=f"HTTP {status} redirect to {redirect_target}",
                    severity="warning",
                    category="redirects",
                    url=url,
                    recommendation="Ensure this redirect is intentional. Update internal links to point directly to the final URL.",
                ))

            # Check for noindex in robots meta
            robots_meta = soup.find("meta", attrs={"name": "robots"})
            if robots_meta:
                content = robots_meta.get("content", "").lower()
                if "noindex" in content:
                    findings.append(Finding(
                        title=f"noindex detected: {path}",
                        description="This page has a noindex directive — search engines will not index it.",
                        severity="critical" if path not in ["/privacy.html"] else "info",
                        category="indexation",
                        url=url,
                        recommendation="Remove noindex unless this page intentionally should not be indexed.",
                    ))

        score = self.clamp_score(100, findings=findings)
        return self.result(score, findings)
