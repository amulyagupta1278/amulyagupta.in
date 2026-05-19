"""Skill 03 — Canonical Tag Consistency"""
from pathlib import Path
from bs4 import BeautifulSoup
from .base import BaseSkill


class CanonicalSkill(BaseSkill):
    name = "Canonical Tag Consistency"
    priority = "P4"
    skill_number = 3

    def run(self) -> dict:
        findings = []
        auto_fixes = []
        pages_missing = []
        pages_wrong = []

        for f in self.html_files:
            soup = self.parse(f)
            expected_url = self._expected_canonical(f)
            canonical_tag = soup.find("link", rel="canonical")

            if not canonical_tag:
                pages_missing.append(str(f.relative_to(self.site_root)))
                self._add_canonical(f, expected_url, auto_fixes)
            else:
                href = canonical_tag.get("href", "").rstrip("/")
                expected_clean = expected_url.rstrip("/")
                if href != expected_clean and href != expected_url:
                    pages_wrong.append(f"{f.relative_to(self.site_root)}: has '{href}', expected '{expected_url}'")

        if pages_missing:
            findings.append(self.finding(
                "CANON_001", f"{len(pages_missing)} page(s) missing canonical tag",
                "critical" if len(pages_missing) > 3 else "warning", "P4",
                f"No <link rel='canonical'> found on: {', '.join(pages_missing[:5])}",
                "Add self-referential canonical tags to every page to prevent duplicate content penalties.",
                "Without canonicals, search engines may index wrong URL variants or split link equity.",
                pages=pages_missing[:5], auto_fixed=bool(auto_fixes)
            ))

        if pages_wrong:
            findings.append(self.finding(
                "CANON_002", f"{len(pages_wrong)} page(s) have incorrect canonical URLs",
                "warning", "P4",
                f"Canonical URL mismatch on: {'; '.join(pages_wrong[:3])}",
                "Ensure canonical href exactly matches the intended indexable URL (include https, correct path).",
                "Incorrect canonicals confuse search engines and can cause indexation of wrong URLs.",
                pages=[p.split(":")[0] for p in pages_wrong[:5]]
            ))

        if not findings:
            return self.result([], f"All {len(self.html_files)} pages have correct canonical tags.",
                               auto_fixes, ["Review canonicals after any URL restructuring."])

        s = f"Canonical audit complete. {len(findings)} issue(s) across {len(self.html_files)} pages."
        return self.result(findings, s, auto_fixes)

    def _expected_canonical(self, path: Path) -> str:
        rel = path.relative_to(self.site_root)
        parts = rel.parts
        if parts[-1] == "index.html":
            if len(parts) == 1:
                return self.site_url + "/"
            return self.site_url + "/" + "/".join(parts[:-1]) + "/"
        return self.site_url + "/" + str(rel)

    def _add_canonical(self, path: Path, canonical_url: str, auto_fixes: list):
        content = path.read_text(encoding="utf-8")
        soup = BeautifulSoup(content, "lxml")
        if soup.find("link", rel="canonical"):
            return
        head = soup.find("head")
        if not head:
            return
        # Insert after existing meta charset
        charset = head.find("meta", charset=True) or head.find("meta")
        canonical_tag = soup.new_tag("link", rel="canonical", href=canonical_url)
        if charset:
            charset.insert_after(canonical_tag)
        else:
            head.insert(0, canonical_tag)
        path.write_text(str(soup), encoding="utf-8")
        auto_fixes.append(f"Added canonical tag to {path.relative_to(self.site_root)}: {canonical_url}")
