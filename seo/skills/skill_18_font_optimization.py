"""Skill 18 — Font Loading Optimization"""
from .base import BaseSkill


class FontOptimizationSkill(BaseSkill):
    name = "Font Loading Optimization"
    priority = "P2"
    skill_number = 18

    def run(self) -> dict:
        findings = []
        auto_fixes = []

        for f in self.html_files:
            soup = self.parse(f)
            page = str(f.relative_to(self.site_root))
            head = soup.find("head")
            if not head:
                continue

            content = f.read_text(encoding="utf-8")

            # Google Fonts links
            gf_links = [l for l in head.find_all("link")
                        if "fonts.googleapis.com" in l.get("href", "")]

            if not gf_links:
                continue

            # Check for preconnect
            preconnects = [l.get("href", "") for l in head.find_all("link", rel="preconnect")]
            has_gf_preconnect = any("fonts.googleapis.com" in p for p in preconnects)
            has_gstatic_preconnect = any("fonts.gstatic.com" in p for p in preconnects)

            if not has_gf_preconnect:
                findings.append(self.finding(
                    "FONT_001", f"Missing Google Fonts preconnect on {page}", "warning", "P2",
                    "Google Fonts loaded without preconnect hint — adds DNS lookup delay.",
                    "Add before your fonts link: <link rel='preconnect' href='https://fonts.googleapis.com'>",
                    "Preconnect saves ~100-200ms per Google Fonts request.",
                    pages=[page]
                ))
                self._add_preconnect(f, auto_fixes)

            if not has_gstatic_preconnect:
                findings.append(self.finding(
                    "FONT_002", f"Missing fonts.gstatic.com preconnect on {page}", "info", "P2",
                    "Font file origin (fonts.gstatic.com) needs a separate preconnect.",
                    "Add: <link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>",
                    pages=[page]
                ))

            # Check for font-display: swap in CSS
            css_files = self.site_root.glob("assets/css/*.css")
            for css_file in css_files:
                css_content = css_file.read_text(encoding="utf-8", errors="replace")
                if "@font-face" in css_content and "font-display" not in css_content:
                    findings.append(self.finding(
                        "FONT_003", f"Missing font-display in {css_file.name}", "warning", "P2",
                        "@font-face rules without font-display:swap cause invisible text during load (FOIT).",
                        "Add 'font-display: swap;' to all @font-face rules in CSS.",
                        "font-display:swap shows fallback text immediately — eliminates FOIT and improves LCP.",
                    ))
                    break

            # Check if display=swap is in Google Fonts URL
            for link in gf_links:
                href = link.get("href", "")
                if "display=swap" not in href:
                    findings.append(self.finding(
                        "FONT_004", f"Google Fonts URL missing display=swap on {page}", "warning", "P2",
                        f"Font URL: {href[:80]}... doesn't include &display=swap",
                        "Append &display=swap to your Google Fonts URL to enable font-display:swap.",
                        "Without display=swap, text is invisible until fonts load — hurts FCP and LCP.",
                        pages=[page]
                    ))
                    self._fix_font_display(f, href, auto_fixes)

            # Count font variants (each variant = separate HTTP request)
            for link in gf_links:
                href = link.get("href", "")
                weights = href.count("wght@") or href.count("wght") or href.count(":")
                if "family=" in href:
                    families = href.count("family=")
                    if families > 2:
                        findings.append(self.finding(
                            "FONT_005", f"Many font families loaded ({families}) on {page}", "info", "P2",
                            f"Loading {families} Google Font families increases initial load time.",
                            "Limit to 2 font families maximum. Use system fonts as fallback stack.",
                            pages=[page]
                        ))

        if not findings:
            return self.result([], f"Font loading is optimized on all pages.", auto_fixes,
                               ["Consider self-hosting fonts for maximum performance (removes Google dependency)."])

        return self.result(findings, f"Font audit: {len(findings)} issue(s). {len(auto_fixes)} auto-fix(es).",
                           auto_fixes)

    def _add_preconnect(self, path, auto_fixes: list):
        content = path.read_text(encoding="utf-8")
        preconnect_tags = (
            '\n    <link rel="preconnect" href="https://fonts.googleapis.com">'
            '\n    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        )
        # Insert after <head>
        if "fonts.googleapis.com" in content and "preconnect" not in content:
            new_content = content.replace("<head>", "<head>" + preconnect_tags, 1)
            if new_content != content:
                path.write_text(new_content, encoding="utf-8")
                auto_fixes.append(f"Added Google Fonts preconnect hints to {path.relative_to(self.site_root)}.")

    def _fix_font_display(self, path, old_href: str, auto_fixes: list):
        content = path.read_text(encoding="utf-8")
        new_href = old_href + ("&display=swap" if "?" in old_href else "?display=swap")
        new_content = content.replace(old_href, new_href, 1)
        if new_content != content:
            path.write_text(new_content, encoding="utf-8")
            auto_fixes.append(f"Added display=swap to Google Fonts URL on {path.relative_to(self.site_root)}.")
