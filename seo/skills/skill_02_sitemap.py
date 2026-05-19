"""Skill 02 — XML Sitemap Integrity"""
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
import os
from .base import BaseSkill


class SitemapSkill(BaseSkill):
    name = "XML Sitemap Integrity"
    priority = "P1"
    skill_number = 2

    NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

    def run(self) -> dict:
        findings = []
        auto_fixes = []
        sitemap_path = self.site_root / "sitemap.xml"

        if not sitemap_path.exists():
            findings.append(self.finding(
                "SITEMAP_001", "sitemap.xml missing", "critical", "P1",
                "No sitemap.xml found at site root.",
                "Generate a complete XML sitemap and submit it in Google Search Console.",
                "Search engines can't efficiently discover all pages without a sitemap."
            ))
            self._create_sitemap(sitemap_path, auto_fixes)
            return self.result(findings, "sitemap.xml was missing and has been generated.", auto_fixes)

        # Parse XML
        try:
            tree = ET.parse(sitemap_path)
            root = tree.getroot()
        except ET.ParseError as e:
            findings.append(self.finding(
                "SITEMAP_002", "sitemap.xml is malformed XML", "critical", "P1",
                f"XML parse error: {e}",
                "Fix the XML syntax error. Validate at https://www.xml-sitemaps.com/validate-xml-sitemap.html",
                "Malformed sitemap will be ignored by all search engines."
            ))
            return self.result(findings, "sitemap.xml has XML syntax errors.", auto_fixes)

        urls_in_sitemap = []
        tag = lambda t: f"{{{self.NS}}}{t}"
        for url_el in root.findall(tag("url")):
            loc = url_el.findtext(tag("loc"))
            lastmod = url_el.findtext(tag("lastmod"))
            priority = url_el.findtext(tag("priority"))
            if loc:
                urls_in_sitemap.append({"loc": loc, "lastmod": lastmod, "priority": priority})

        # Check all HTML files are in sitemap
        sitemap_locs = {u["loc"] for u in urls_in_sitemap}
        missing_from_sitemap = []
        for f in self.html_files:
            url = self.page_url(f)
            url = url.replace("/index.html", "/").rstrip("/") or self.site_url
            # Normalize
            if url not in sitemap_locs and (url + "/") not in sitemap_locs:
                missing_from_sitemap.append(str(f.relative_to(self.site_root)))

        if missing_from_sitemap:
            findings.append(self.finding(
                "SITEMAP_003", f"{len(missing_from_sitemap)} page(s) missing from sitemap",
                "warning", "P1",
                f"Pages not in sitemap: {', '.join(missing_from_sitemap)}",
                "Add all public HTML pages to the sitemap with appropriate priority and changefreq.",
                "Uncrawled pages may not appear in search results."
            ))

        # Check lastmod staleness
        stale_urls = []
        today = datetime.now(timezone.utc).date()
        for u in urls_in_sitemap:
            if u["lastmod"]:
                try:
                    lm_date = datetime.fromisoformat(u["lastmod"]).date()
                    days_old = (today - lm_date).days
                    if days_old > 90:
                        stale_urls.append(u["loc"])
                except ValueError:
                    pass

        if stale_urls:
            findings.append(self.finding(
                "SITEMAP_004", f"{len(stale_urls)} URL(s) have stale lastmod dates (>90 days)",
                "warning", "P1",
                "Old lastmod dates signal to crawlers that content hasn't been updated recently.",
                "Update lastmod to actual file modification dates or content change dates.",
                "Fresh lastmod dates encourage more frequent crawling.",
                pages=stale_urls[:5]
            ))
            self._update_lastmod(sitemap_path, auto_fixes)

        # Check sitemap URL count
        if len(urls_in_sitemap) == 0:
            findings.append(self.finding(
                "SITEMAP_005", "Sitemap contains zero URLs", "critical", "P1",
                "The sitemap.xml file exists but contains no <url> entries.",
                "Populate the sitemap with all public pages.",
                "Empty sitemap provides no crawl guidance to search engines."
            ))

        # Check for missing priority tags
        no_priority = [u["loc"] for u in urls_in_sitemap if not u["priority"]]
        if no_priority:
            findings.append(self.finding(
                "SITEMAP_006", f"{len(no_priority)} URL(s) missing priority value",
                "info", "P1",
                "Priority helps signal page importance to crawlers.",
                "Add <priority> values: homepage=1.0, main pages=0.8, blog=0.7, posts=0.6.",
                pages=no_priority[:3]
            ))

        s = f"Sitemap reviewed: {len(urls_in_sitemap)} URLs indexed. {len(findings)} issue(s) found."
        return self.result(findings, s, auto_fixes,
                           ["Submit sitemap to Google Search Console and Bing Webmaster Tools.",
                            "Update sitemap lastmod when publishing new blog posts."])

    def _create_sitemap(self, path: Path, auto_fixes: list):
        today = datetime.now(timezone.utc).date().isoformat()
        pages = [
            ("https://amulyagupta.in/", "1.0", "weekly"),
            ("https://amulyagupta.in/about.html", "0.8", "monthly"),
            ("https://amulyagupta.in/projects.html", "0.8", "monthly"),
            ("https://amulyagupta.in/experience.html", "0.8", "monthly"),
            ("https://amulyagupta.in/contact.html", "0.7", "monthly"),
            ("https://amulyagupta.in/amulya-gupta.html", "0.7", "monthly"),
            ("https://amulyagupta.in/blog/", "0.8", "weekly"),
        ]
        entries = "\n".join(
            f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{today}</lastmod>\n"
            f"    <changefreq>{freq}</changefreq>\n    <priority>{pri}</priority>\n  </url>"
            for loc, pri, freq in pages
        )
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{entries}
</urlset>"""
        path.write_text(xml, encoding="utf-8")
        auto_fixes.append("Generated sitemap.xml with all known pages.")

    def _update_lastmod(self, path: Path, auto_fixes: list):
        today = datetime.now(timezone.utc).date().isoformat()
        content = path.read_text(encoding="utf-8")
        import re
        new_content = re.sub(r"<lastmod>[^<]+</lastmod>", f"<lastmod>{today}</lastmod>", content)
        if new_content != content:
            path.write_text(new_content, encoding="utf-8")
            auto_fixes.append(f"Updated all lastmod dates to {today}.")
