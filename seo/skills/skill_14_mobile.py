"""Skill 14 — Mobile-First Readiness"""
from .base import BaseSkill


class MobileSkill(BaseSkill):
    name = "Mobile-First Readiness"
    priority = "P0"
    skill_number = 14

    def run(self) -> dict:
        findings = []
        auto_fixes = []

        for f in self.html_files:
            soup = self.parse(f)
            page = str(f.relative_to(self.site_root))
            content = f.read_text(encoding="utf-8")

            # Viewport meta
            viewport = soup.find("meta", attrs={"name": "viewport"})
            if not viewport:
                findings.append(self.finding(
                    "MOBILE_001", f"Missing viewport meta tag: {page}", "critical", "P0",
                    f"{page} has no <meta name='viewport'> tag.",
                    "Add: <meta name='viewport' content='width=device-width, initial-scale=1.0'>",
                    "Without viewport meta, mobile browsers render at desktop width — site appears zoomed-out and unusable.",
                    pages=[page]
                ))
                self._add_viewport(f, auto_fixes)
            else:
                vp_content = viewport.get("content", "")
                if "width=device-width" not in vp_content:
                    findings.append(self.finding(
                        "MOBILE_002", f"Incorrect viewport configuration: {page}", "warning", "P0",
                        f"viewport content='{vp_content}' doesn't include width=device-width.",
                        "Update viewport to: content='width=device-width, initial-scale=1.0'",
                        "Incorrect viewport breaks responsive rendering on mobile devices.",
                        pages=[page]
                    ))

            # Check for fixed-width elements (common mobile issue)
            if 'width="' in content or "width: 1" in content:
                fixed_px = [line.strip() for line in content.splitlines()
                            if ("width:" in line and "px" in line and
                                any(f"{n}px" in line for n in range(600, 2000)))]
                if fixed_px:
                    findings.append(self.finding(
                        "MOBILE_003", f"Fixed-width CSS elements detected on {page}", "info", "P0",
                        f"Found large fixed-width values that may overflow on mobile screens.",
                        "Replace fixed pixel widths with percentage, max-width, or CSS Grid/Flexbox.",
                        pages=[page]
                    ))

            # Check touch targets (buttons/links should be ≥48px)
            small_targets = []
            for a in soup.find_all(["a", "button"]):
                style = a.get("style", "")
                if "padding: 0" in style or "padding:0" in style:
                    small_targets.append(str(a)[:50])
            if len(small_targets) > 3:
                findings.append(self.finding(
                    "MOBILE_004", f"Potential small touch targets on {page}", "info", "P0",
                    "Elements with zero padding may create touch targets smaller than 48px.",
                    "Ensure all interactive elements have at least 48x48px clickable area.",
                    "Small touch targets cause tap errors on mobile — Google uses this in mobile usability scoring.",
                    pages=[page]
                ))

            # Check font size (should be readable at 16px+)
            if "font-size: 1" in content or "font-size:1" in content:
                tiny_fonts = [l.strip() for l in content.splitlines()
                              if "font-size:" in l and
                              any(f"font-size: {n}px" in l or f"font-size:{n}px" in l
                                  for n in range(1, 12))]
                if tiny_fonts:
                    findings.append(self.finding(
                        "MOBILE_005", f"Tiny font sizes detected on {page}", "warning", "P0",
                        "Font sizes below 12px are flagged by Google mobile usability checker.",
                        "Minimum readable font size is 16px for body text, 12px for captions.",
                        pages=[page]
                    ))

        if not findings:
            return self.result([], f"All {len(self.html_files)} pages pass mobile-first readiness checks.", auto_fixes,
                               ["Test with Google's Mobile-Friendly Test tool after any CSS changes.",
                                "Run Lighthouse mobile audit monthly."])

        return self.result(findings, f"Mobile audit: {len(findings)} issue(s). {len(auto_fixes)} auto-fix(es).", auto_fixes)

    def _add_viewport(self, path, auto_fixes: list):
        content = path.read_text(encoding="utf-8")
        new_content = content.replace(
            "<head>",
            '<head>\n    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
            1
        )
        if new_content != content:
            path.write_text(new_content, encoding="utf-8")
            auto_fixes.append(f"Added viewport meta tag to {path.relative_to(self.site_root)}.")
