import re
import crawler
from base import BaseSEOSkill, Finding
from config import SITE_URL


class Skill14MobileFriendliness(BaseSEOSkill):
    SKILL_ID = 14
    SKILL_NAME = "Mobile Friendliness Audit"

    def run(self, pages: list[dict]) -> SkillResult:
        from base import SkillResult
        findings = []
        ok_count = 0
        total = 0

        for page in pages:
            url = page["url"]
            path = url.replace(SITE_URL, "")
            soup = page.get("soup")
            if not soup or page.get("status") != 200:
                continue

            total += 1
            page_ok = True
            meta = crawler.extract_meta(soup)
            html_raw = page.get("html", "")

            # Viewport meta tag
            viewport = meta.get("viewport", "")
            if not viewport:
                page_ok = False
                findings.append(Finding(
                    title=f"Missing viewport meta tag: {path}",
                    description="No viewport meta tag — page will not display correctly on mobile.",
                    severity="critical",
                    category="mobile",
                    url=url,
                    recommendation="Add <meta name='viewport' content='width=device-width, initial-scale=1'> in <head>.",
                ))
            else:
                if "width=device-width" not in viewport:
                    findings.append(Finding(
                        title=f"Incorrect viewport: {path}",
                        description=f"Viewport '{viewport}' missing 'width=device-width'.",
                        severity="warning",
                        category="mobile",
                        url=url,
                        recommendation="Set viewport to 'width=device-width, initial-scale=1'.",
                    ))
                if "user-scalable=no" in viewport:
                    findings.append(Finding(
                        title=f"Zoom disabled: {path}",
                        description="viewport has 'user-scalable=no' which prevents zoom — bad for accessibility.",
                        severity="warning",
                        category="mobile",
                        url=url,
                        recommendation="Remove 'user-scalable=no' to allow users to zoom on mobile.",
                    ))

            # Fixed-width CSS detection
            if re.search(r'width\s*:\s*\d{3,}px', html_raw):
                findings.append(Finding(
                    title=f"Fixed-width CSS detected: {path}",
                    description="Page may contain fixed pixel widths that break on narrow screens.",
                    severity="warning",
                    category="mobile",
                    url=url,
                    recommendation="Use relative units (%, vw, rem) instead of fixed px widths for responsive layouts.",
                ))

            # Font size check
            if re.search(r'font-size\s*:\s*([89]|1[01])px', html_raw):
                findings.append(Finding(
                    title=f"Small font sizes detected: {path}",
                    description="Font sizes below 12px are hard to read on mobile.",
                    severity="warning",
                    category="mobile",
                    url=url,
                    recommendation="Use minimum 16px font size for body text on mobile.",
                ))

            # Horizontal overflow
            if "overflow-x" not in html_raw and re.search(r'min-width\s*:\s*[5-9]\d{2}px', html_raw):
                findings.append(Finding(
                    title=f"Potential horizontal scroll: {path}",
                    description="Min-width CSS may cause horizontal scrolling on mobile.",
                    severity="info",
                    category="mobile",
                    url=url,
                    recommendation="Remove or reduce min-width constraints, use max-width instead.",
                ))

            # Touch targets
            buttons = soup.find_all(["button", "a"])
            tiny_targets = 0
            for btn in buttons:
                style = btn.get("style", "")
                if re.search(r'(width|height)\s*:\s*([1-3][0-9])px', style):
                    tiny_targets += 1

            if tiny_targets > 3:
                findings.append(Finding(
                    title=f"Small touch targets: {path}",
                    description=f"Detected {tiny_targets} elements with potentially small touch targets.",
                    severity="warning",
                    category="mobile",
                    url=url,
                    recommendation="Ensure touch targets are at least 44x44px for comfortable mobile tapping.",
                ))

            if page_ok:
                ok_count += 1

        score = int(ok_count / total * 100) if total else 50
        score = self.clamp_score(score, findings=findings)
        return self.result(score, findings, {"pages_ok": ok_count, "total": total})
