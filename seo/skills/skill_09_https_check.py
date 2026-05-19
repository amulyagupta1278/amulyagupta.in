"""Skill 09 — HTTPS Enforcement Check"""
import re
from .base import BaseSkill


class HttpsCheckSkill(BaseSkill):
    name = "HTTPS Enforcement Check"
    priority = "P1"
    skill_number = 9

    HTTP_ATTR_RE = re.compile(r'(href|src|action|content)=["\']http://[^"\']+["\']', re.IGNORECASE)
    HTTP_URL_RE = re.compile(r'http://amulyagupta\.in', re.IGNORECASE)

    def run(self) -> dict:
        findings = []
        auto_fixes = []

        for f in self.html_files:
            content = f.read_text(encoding="utf-8")
            page = str(f.relative_to(self.site_root))

            # Find HTTP links to own domain
            own_http = self.HTTP_URL_RE.findall(content)
            if own_http:
                findings.append(self.finding(
                    "HTTPS_001", f"Self-referencing HTTP URLs on {page}", "critical", "P1",
                    f"Found {len(own_http)} HTTP reference(s) to amulyagupta.in on {page}.",
                    "Replace all 'http://amulyagupta.in' with 'https://amulyagupta.in'.",
                    "HTTP self-links create mixed-content warnings and undermine HTTPS authority signals.",
                    pages=[page]
                ))
                new_content = self.HTTP_URL_RE.sub("https://amulyagupta.in", content)
                if new_content != content:
                    f.write_text(new_content, encoding="utf-8")
                    content = new_content
                    auto_fixes.append(f"Fixed HTTP→HTTPS self-references on {page}.")

            # Find HTTP external resources (src/href to other domains)
            http_attrs = self.HTTP_ATTR_RE.findall(content)
            # Filter out false positives (mailto:, etc.)
            real_http = [m for m in self.HTTP_ATTR_RE.finditer(content)
                         if "mailto:" not in m.group() and "javascript:" not in m.group()
                         and "amulyagupta.in" not in m.group()]
            if real_http:
                urls = [m.group()[:80] for m in real_http[:5]]
                findings.append(self.finding(
                    "HTTPS_002", f"{len(real_http)} HTTP external resource(s) on {page}", "warning", "P1",
                    f"External HTTP references found: {'; '.join(urls)}",
                    "Update external resource URLs to HTTPS versions.",
                    "HTTP resources on HTTPS pages trigger browser mixed-content warnings and can block loading.",
                    pages=[page]
                ))

        # Check CNAME (domain config)
        cname_path = self.site_root / "CNAME"
        if cname_path.exists():
            cname = cname_path.read_text(encoding="utf-8").strip()
            if cname and not cname.startswith("https://"):
                findings.append(self.finding(
                    "HTTPS_003", "CNAME file contains domain without HTTPS prefix", "info", "P1",
                    f"CNAME contains '{cname}'. This is correct — CNAME stores domain only.",
                    "Ensure HTTPS is enforced via GitHub Pages settings (Settings → Pages → Enforce HTTPS).",
                    "GitHub Pages auto-provisions SSL, but Enforce HTTPS must be enabled in settings."
                ))

        if not findings:
            return self.result([], f"All pages are HTTPS-clean. No mixed content detected.", auto_fixes,
                               ["Run a periodic mixed-content audit when adding new third-party resources."])

        return self.result(findings, f"HTTPS audit: {len(findings)} issue(s). {len(auto_fixes)} auto-fix(es) applied.",
                           auto_fixes)
