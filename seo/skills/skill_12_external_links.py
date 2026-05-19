"""Skill 12 — External Link Health Check"""
from .base import BaseSkill


class ExternalLinksSkill(BaseSkill):
    name = "External Link Health Check"
    priority = "P3"
    skill_number = 12

    def run(self) -> dict:
        findings = []
        all_external: dict[str, list[str]] = {}  # url → [source pages]

        for f in self.html_files:
            soup = self.parse(f)
            page = str(f.relative_to(self.site_root))
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if href.startswith("http") and "amulyagupta.in" not in href:
                    all_external.setdefault(href, [])
                    if page not in all_external[href]:
                        all_external[href].append(page)

        broken = []
        unchecked = []
        checked = 0

        for url, source_pages in list(all_external.items())[:40]:  # Limit to 40 for speed
            r = self.fetch(url, timeout=8)
            checked += 1
            if r is None:
                unchecked.append((url, source_pages))
            elif r.status_code in [404, 410]:
                broken.append((url, r.status_code, source_pages))
            elif r.status_code >= 500:
                unchecked.append((url, source_pages))

        if broken:
            for url, code, pages in broken:
                findings.append(self.finding(
                    "EXTLINK_001", f"Broken external link ({code}): {url[:70]}", "warning", "P3",
                    f"URL returns HTTP {code}: {url}",
                    "Remove or replace this broken external link.",
                    "Broken outbound links hurt user experience and may signal low content quality.",
                    pages=pages[:3]
                ))

        if unchecked and len(unchecked) > 3:
            findings.append(self.finding(
                "EXTLINK_002", f"{len(unchecked)} external link(s) timed out or unreachable",
                "info", "P3",
                f"Could not verify: {'; '.join(u for u, _ in unchecked[:3])}...",
                "Manually verify these links are still active.",
                pages=[]
            ))

        # Check for norel on external links
        for f in self.html_files:
            soup = self.parse(f)
            page = str(f.relative_to(self.site_root))
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if href.startswith("http") and "amulyagupta.in" not in href:
                    rel = a.get("rel", [])
                    if isinstance(rel, str):
                        rel = [rel]
                    if "noopener" not in rel:
                        findings.append(self.finding(
                            "EXTLINK_003", f"External link missing rel='noopener' on {page}",
                            "info", "P3",
                            f"Link to {href[:60]} lacks rel='noopener noreferrer' for security.",
                            "Add rel='noopener noreferrer' to all external links opening in new tabs.",
                            pages=[page]
                        ))
                        break  # One finding per page is enough

        total_ext = len(all_external)
        if not findings:
            return self.result([], f"Checked {checked} external links. All healthy.",
                               [], ["Schedule monthly external link audits as third-party sites change."])

        return self.result(findings, f"External link audit: {len(findings)} issue(s) from {total_ext} unique links checked.",
                           [], ["Use rel='noopener noreferrer' on ALL external links for security and SEO hygiene."])
