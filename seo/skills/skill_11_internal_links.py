"""Skill 11 — Internal Link Architecture"""
from pathlib import Path
from urllib.parse import urlparse, urljoin
from .base import BaseSkill


class InternalLinksSkill(BaseSkill):
    name = "Internal Link Architecture"
    priority = "P7"
    skill_number = 11

    def run(self) -> dict:
        findings = []
        link_map: dict[str, list[str]] = {}  # page → [links to other pages]
        inbound: dict[str, list[str]] = {}   # page → [pages linking to it]

        page_paths = {str(f.relative_to(self.site_root)): f for f in self.html_files}

        for rel_path, f in page_paths.items():
            soup = self.parse(f)
            links = []
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                # Normalize
                if href.startswith("http") and "amulyagupta.in" not in href:
                    continue  # external
                if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
                    continue
                # Resolve relative
                if href.startswith("http"):
                    parsed = urlparse(href)
                    path = parsed.path.lstrip("/")
                else:
                    path = href.lstrip("/")
                if path.endswith("/"):
                    path += "index.html"
                if path and path in page_paths:
                    links.append(path)
                    inbound.setdefault(path, [])
                    if rel_path not in inbound[path]:
                        inbound[path].append(rel_path)
            link_map[rel_path] = links

        # Orphan pages (no inbound links, excluding index pages)
        for rel_path in page_paths:
            if rel_path == "index.html":
                continue
            if len(inbound.get(rel_path, [])) == 0:
                findings.append(self.finding(
                    "ILINKS_001", f"Orphan page (no inbound links): {rel_path}", "warning", "P7",
                    f"{rel_path} has no internal pages linking to it — crawlers may not discover it.",
                    "Add at least 2–3 internal links to this page from relevant high-traffic pages.",
                    "Orphan pages receive no PageRank from internal links and may not be crawled regularly.",
                    pages=[rel_path]
                ))

        # Crawl depth (pages more than 3 clicks from homepage)
        depth = self._bfs_depth(link_map)
        deep_pages = [(p, d) for p, d in depth.items() if d > 3]
        if deep_pages:
            pages_str = [f"{p} (depth {d})" for p, d in deep_pages[:5]]
            findings.append(self.finding(
                "ILINKS_002", f"{len(deep_pages)} page(s) more than 3 clicks from homepage",
                "warning", "P7",
                f"Deep pages: {', '.join(pages_str)}",
                "Restructure navigation or add hub pages to bring all content within 3 clicks of homepage.",
                "Pages >3 clicks deep receive less crawl attention and lower PageRank.",
                pages=[p for p, _ in deep_pages[:5]]
            ))

        # Check for broken internal links (missing target pages)
        for from_page, f in page_paths.items():
            soup = self.parse(f)
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if href.startswith("http") or href.startswith("#") or href.startswith("mailto:"):
                    continue
                path = href.lstrip("/")
                if path and path not in page_paths and not (self.site_root / path).exists():
                    findings.append(self.finding(
                        "ILINKS_003", f"Broken internal link on {from_page}: /{path}", "critical", "P7",
                        f"Link '/{path}' on {from_page} points to a non-existent page.",
                        "Fix or remove this broken link immediately.",
                        "Broken internal links waste crawl budget and create poor user experience.",
                        pages=[from_page]
                    ))

        if not findings:
            return self.result([], f"Internal link structure is healthy across {len(self.html_files)} pages.",
                               [], ["Build topic cluster links: from blog posts back to main project/skill pages."])

        recs = [
            "Create a content hub linking all blog posts, projects, and skill pages together.",
            "Add 'Related Articles' sections to each blog post.",
            "Link from the homepage to all key portfolio pages explicitly."
        ]
        return self.result(findings, f"Internal links: {len(findings)} issue(s) found.", [], recs)

    def _bfs_depth(self, link_map: dict) -> dict[str, int]:
        from collections import deque
        depth = {"index.html": 0}
        q = deque(["index.html"])
        while q:
            current = q.popleft()
            for target in link_map.get(current, []):
                if target not in depth:
                    depth[target] = depth[current] + 1
                    q.append(target)
        return depth
