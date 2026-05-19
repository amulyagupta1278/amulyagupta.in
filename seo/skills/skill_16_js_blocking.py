"""Skill 16 — JavaScript Blocking Analysis"""
from .base import BaseSkill


class JsBlockingSkill(BaseSkill):
    name = "JavaScript Blocking Analysis"
    priority = "P2"
    skill_number = 16

    CRITICAL_SCRIPTS = ["analytics", "gtag", "ga(", "fbq", "clarity"]

    def run(self) -> dict:
        findings = []
        auto_fixes = []

        for f in self.html_files:
            soup = self.parse(f)
            page = str(f.relative_to(self.site_root))
            head = soup.find("head")
            body = soup.find("body")

            if not head:
                continue

            # Blocking scripts in head
            head_scripts = head.find_all("script", src=True)
            blocking = [s for s in head_scripts
                        if not s.get("defer") and not s.get("async")
                        and not any(c in (s.get("src", "") + s.get_text()).lower()
                                    for c in self.CRITICAL_SCRIPTS)]
            if blocking:
                urls = [s.get("src", "")[:60] for s in blocking[:3]]
                findings.append(self.finding(
                    "JSBLOCK_001", f"{len(blocking)} render-blocking script(s) in <head> on {page}",
                    "warning", "P2",
                    f"Scripts: {', '.join(urls)} block HTML parsing until downloaded and executed.",
                    "Add defer attribute or move scripts to end of <body>.",
                    "Each blocking script adds 50–300ms to page load time, directly increasing LCP.",
                    pages=[page]
                ))
                self._add_defer(f, blocking, auto_fixes)

            # Inline scripts analysis
            inline_scripts = head.find_all("script", src=False)
            large_inline = [s for s in inline_scripts
                            if len(s.get_text(strip=True)) > 500
                            and not any(c in s.get_text().lower() for c in self.CRITICAL_SCRIPTS)]
            if large_inline:
                findings.append(self.finding(
                    "JSBLOCK_002", f"{len(large_inline)} large inline script(s) in <head> on {page}",
                    "info", "P2",
                    f"Inline scripts larger than 500 bytes block rendering.",
                    "Move large inline scripts to external .js files with defer attribute.",
                    "Externalizing scripts allows browser caching and parallel downloads.",
                    pages=[page]
                ))

            # Total script count
            all_scripts = soup.find_all("script", src=True)
            if len(all_scripts) > 8:
                findings.append(self.finding(
                    "JSBLOCK_003", f"High script count ({len(all_scripts)}) on {page}", "info", "P2",
                    f"{len(all_scripts)} external scripts found. HTTP/2 helps, but each still has overhead.",
                    "Combine/bundle non-critical scripts. Lazy-load third-party scripts after page load.",
                    pages=[page]
                ))

        if not findings:
            return self.result([], f"JavaScript analysis: No blocking scripts detected. All pages optimized.", auto_fixes,
                               ["Review script loading strategy when adding new third-party tools."])

        return self.result(findings, f"JS audit: {len(findings)} issue(s). {len(auto_fixes)} auto-fix(es).",
                           auto_fixes, ["Use Chrome DevTools Network panel to identify script load times."])

    def _add_defer(self, path, scripts: list, auto_fixes: list):
        content = path.read_text(encoding="utf-8")
        modified = False
        for script in scripts:
            src = script.get("src", "")
            if src and 'defer' not in str(script) and 'async' not in str(script):
                old_tag = str(script)
                new_tag = old_tag.replace("<script ", '<script defer ', 1)
                if old_tag in content and old_tag != new_tag:
                    content = content.replace(old_tag, new_tag, 1)
                    modified = True
        if modified:
            path.write_text(content, encoding="utf-8")
            auto_fixes.append(f"Added defer attribute to {len(scripts)} blocking script(s) on {path.relative_to(self.site_root)}.")
