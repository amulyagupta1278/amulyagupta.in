#!/usr/bin/env python3
"""
SEO Auto-Fix PR Generator — amulyagupta.in

Detects auto-fixable SEO issues from skill findings and opens a GitHub PR with
proposed code changes. Every fix goes through:

  Runtime → Detect Issue → Generate Fix → Create PR → Human Review → Manual Merge

The runtime NEVER auto-merges. PRs are drafts until a human approves.

Auto-fixable categories
-----------------------
  canonical      → add/fix <link rel="canonical"> in HTML pages
  open-graph     → add missing og:url, og:title, og:description, og:image
  social         → add missing twitter:card / twitter:title / twitter:description
  ai-crawlers    → add missing AI bot directives to robots.txt
  sitemap        → add missing pages / missing lastmod to sitemap.xml
  mobile         → add missing <meta name="viewport">

Not auto-fixable (require human judgment)
-----------------------------------------
  content, keywords, schema, internal-linking, images (alt text), cwv, competitors,
  page-speed, duplicate-content, semantic, backlinks, analytics
"""

import base64
import json
import logging
import re
from datetime import datetime
from typing import Optional

import requests
from config import GITHUB_TOKEN, GITHUB_REPOSITORY, SITE_URL, SKILL_NAMES

log = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_BASE_BRANCH = "main"

# Categories the generator can fix deterministically (no human judgment needed)
_FIXABLE_CATEGORIES = frozenset({
    "canonical",
    "open-graph",
    "social",
    "ai-crawlers",
    "sitemap",
    "mobile",
})

# Map site URL paths to repo file paths
def _url_to_path(url: str) -> Optional[str]:
    path = url.replace(SITE_URL, "").lstrip("/")
    if not path:
        return "index.html"
    return path if path else None


# ─────────────────────────────────────────────────────────────────────────────
# GitHub REST client (API-based, no local git state required)
# ─────────────────────────────────────────────────────────────────────────────

class _GH:
    def __init__(self, token: str, repo: str):
        self.base = f"{_GITHUB_API}/repos/{repo.removeprefix('https://github.com/')}"
        self._h = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _get(self, path: str, **kw):
        return requests.get(f"{self.base}{path}", headers=self._h, timeout=30, **kw)

    def _post(self, path: str, data: dict):
        return requests.post(f"{self.base}{path}", headers=self._h, json=data, timeout=30)

    def _put(self, path: str, data: dict):
        return requests.put(f"{self.base}{path}", headers=self._h, json=data, timeout=30)

    def ref_sha(self, ref: str = f"heads/{_BASE_BRANCH}") -> Optional[str]:
        r = self._get(f"/git/ref/{ref}")
        return r.json()["object"]["sha"] if r.status_code == 200 else None

    def create_branch(self, branch: str, sha: str) -> bool:
        r = self._post("/git/refs", {"ref": f"refs/heads/{branch}", "sha": sha})
        if r.status_code in (200, 201):
            return True
        if r.status_code == 422 and "already exists" in r.text:
            return True
        log.error("create_branch %s: %s %s", branch, r.status_code, r.text[:200])
        return False

    def get_file(self, path: str, ref: str = _BASE_BRANCH) -> Optional[dict]:
        r = self._get(f"/contents/{path}", params={"ref": ref})
        if r.status_code == 200:
            d = r.json()
            return {
                "content": base64.b64decode(d["content"]).decode("utf-8", errors="replace"),
                "sha": d["sha"],
            }
        log.warning("get_file %s → %d", path, r.status_code)
        return None

    def update_file(self, path: str, content: str, sha: str, message: str, branch: str) -> bool:
        r = self._put(f"/contents/{path}", {
            "message": message,
            "content": base64.b64encode(content.encode()).decode("ascii"),
            "sha": sha,
            "branch": branch,
        })
        if r.status_code in (200, 201):
            return True
        log.error("update_file %s: %s %s", path, r.status_code, r.text[:300])
        return False

    def create_pr(self, title: str, body: str, head: str) -> Optional[str]:
        r = self._post("/pulls", {
            "title": title,
            "body": body,
            "head": head,
            "base": _BASE_BRANCH,
            "draft": True,
        })
        if r.status_code in (200, 201):
            return r.json().get("html_url")
        log.error("create_pr: %s %s", r.status_code, r.text[:300])
        return None

    def add_pr_labels(self, pr_number: int, labels: list[str]) -> None:
        self._post(f"/issues/{pr_number}/labels", {"labels": labels})


# ─────────────────────────────────────────────────────────────────────────────
# HTML patch helpers — insert tags without reformatting existing markup
# ─────────────────────────────────────────────────────────────────────────────

def _insert_before_head_close(html: str, tag: str) -> str:
    """Insert tag on its own line just before </head>."""
    if "</head>" in html:
        return html.replace("</head>", f"  {tag}\n</head>", 1)
    return html  # no </head> found — skip


def _has_tag(html: str, *patterns: str) -> bool:
    """Return True if any pattern matches (case-insensitive)."""
    lower = html.lower()
    return any(p.lower() in lower for p in patterns)


def _fix_canonical(html: str, page_url: str) -> Optional[str]:
    if _has_tag(html, "rel=\"canonical\"", "rel='canonical'"):
        return None  # already present
    tag = f'<link rel="canonical" href="{page_url}" />'
    return _insert_before_head_close(html, tag)


def _fix_og_url(html: str, page_url: str) -> Optional[str]:
    if _has_tag(html, "property=\"og:url\"", "property='og:url'"):
        return None
    tag = f'<meta property="og:url" content="{page_url}" />'
    return _insert_before_head_close(html, tag)


def _fix_og_missing(html: str, og_key: str, content: str) -> Optional[str]:
    escaped_key = re.escape(og_key)
    if re.search(rf'property=["\']?{escaped_key}["\']?', html, re.IGNORECASE):
        return None
    tag = f'<meta property="{og_key}" content="{content}" />'
    return _insert_before_head_close(html, tag)


def _fix_twitter_card(html: str) -> Optional[str]:
    if _has_tag(html, "name=\"twitter:card\"", "name='twitter:card'"):
        return None
    tag = '<meta name="twitter:card" content="summary_large_image" />'
    return _insert_before_head_close(html, tag)


def _fix_twitter_title(html: str, title: str) -> Optional[str]:
    if _has_tag(html, "name=\"twitter:title\"", "name='twitter:title'"):
        return None
    safe = title.replace('"', "&quot;")[:70]
    tag = f'<meta name="twitter:title" content="{safe}" />'
    return _insert_before_head_close(html, tag)


def _fix_twitter_description(html: str, desc: str) -> Optional[str]:
    if _has_tag(html, "name=\"twitter:description\"", "name='twitter:description'"):
        return None
    safe = desc.replace('"', "&quot;")[:160]
    tag = f'<meta name="twitter:description" content="{safe}" />'
    return _insert_before_head_close(html, tag)


def _fix_viewport(html: str) -> Optional[str]:
    if _has_tag(html, "name=\"viewport\"", "name='viewport'"):
        return None
    tag = '<meta name="viewport" content="width=device-width, initial-scale=1" />'
    return _insert_before_head_close(html, tag)


def _fix_ai_crawlers(robots_content: str) -> Optional[str]:
    """Add missing AI crawler directives to robots.txt."""
    missing_bots = []
    ai_bots = ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "Applebot-Extended"]
    for bot in ai_bots:
        if bot.lower() not in robots_content.lower():
            missing_bots.append(bot)
    if not missing_bots:
        return None
    additions = "\n".join(
        f"User-agent: {bot}\nAllow: /" for bot in missing_bots
    )
    return robots_content.rstrip() + "\n\n" + additions + "\n"


def _fix_sitemap_lastmod(sitemap_content: str, today: str) -> Optional[str]:
    """Add lastmod to sitemap <url> entries that lack it."""
    # Find <url> blocks missing <lastmod>
    def add_lastmod(m: re.Match) -> str:
        block = m.group(0)
        if "<lastmod>" in block:
            return block
        return block.replace("</url>", f"    <lastmod>{today}</lastmod>\n  </url>")

    updated = re.sub(r"<url>.*?</url>", add_lastmod, sitemap_content, flags=re.DOTALL)
    return updated if updated != sitemap_content else None


# ─────────────────────────────────────────────────────────────────────────────
# Per-finding fix dispatcher
# ─────────────────────────────────────────────────────────────────────────────

def _apply_fix(finding: dict, file_content: str) -> Optional[str]:
    """
    Return updated file content if a fix can be applied, or None if unfixable/already-fixed.
    Operates on a single finding. Caller accumulates changes across findings for the same file.
    """
    category = finding.get("category", "")
    url = finding.get("url", "")
    title = finding.get("title", "")

    if category == "canonical":
        if "missing" in title.lower() or "no canonical" in title.lower():
            return _fix_canonical(file_content, url)

    elif category == "open-graph":
        og_title_m = re.search(r"og:(url|title|description|image)", title, re.IGNORECASE)
        if og_title_m:
            og_key = f"og:{og_title_m.group(1).lower()}"
            # Derive sensible placeholder content for missing OG tags
            if og_key == "og:url":
                return _fix_og_url(file_content, url)
            elif og_key == "og:title":
                # Extract existing <title> from file as fallback
                m = re.search(r"<title>(.*?)</title>", file_content, re.IGNORECASE | re.DOTALL)
                content = m.group(1).strip() if m else "Amulya Gupta | AI Systems Engineer"
                return _fix_og_missing(file_content, og_key, content[:70])
            elif og_key == "og:description":
                m = re.search(r'content=["\']([^"\']{80,160})["\']', file_content)
                content = m.group(1) if m else "AI Systems Engineer — Agentic AI, LLM Pipelines, MLOps."
                return _fix_og_missing(file_content, og_key, content)
            elif og_key == "og:image":
                return _fix_og_missing(
                    file_content, og_key,
                    "https://github.com/amulyagupta1278.png",
                )

    elif category == "social":
        if "twitter:card" in title.lower() or "twitter card" in title.lower():
            return _fix_twitter_card(file_content)
        elif "twitter:title" in title.lower():
            m = re.search(r"<title>(.*?)</title>", file_content, re.IGNORECASE | re.DOTALL)
            t = m.group(1).strip() if m else "Amulya Gupta"
            return _fix_twitter_title(file_content, t)
        elif "twitter:description" in title.lower():
            m = re.search(r'name=["\']description["\'][^>]*content=["\']([^"\']+)["\']',
                          file_content, re.IGNORECASE)
            d = m.group(1) if m else "AI Systems Engineer — Agentic AI, LLM Pipelines, MLOps."
            return _fix_twitter_description(file_content, d)

    elif category == "mobile":
        if "viewport" in title.lower():
            return _fix_viewport(file_content)

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Core PR generation logic
# ─────────────────────────────────────────────────────────────────────────────

def _group_by_file(findings: list[dict]) -> dict[str, list[dict]]:
    """Group fixable findings by target file path."""
    groups: dict[str, list[dict]] = {}
    for f in findings:
        if f.get("category") not in _FIXABLE_CATEGORIES:
            continue
        url = f.get("url", "")
        path = _url_to_path(url)
        if not path:
            continue
        groups.setdefault(path, []).append(f)
    return groups


def _pr_body(run_id: str, skill_id: int, skill_name: str, fixes_applied: list[dict],
              unfixable_count: int, total_findings: int) -> str:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    lines = [
        "## SEO Auto-Fix Proposal",
        "",
        f"**Run:** `{run_id}` | **Skill:** {skill_id:02d}/23 — {skill_name} | **Date:** {today}",
        "",
        "> This PR was generated automatically by the SEO Runtime. **Human review and manual merge required.**",
        "> The runtime has no auto-merge authority. Review each change before merging.",
        "",
        f"### Summary",
        f"- Total findings this run: **{total_findings}**",
        f"- Auto-fixable findings applied: **{len(fixes_applied)}**",
        f"- Findings requiring human action: **{unfixable_count}**",
        "",
        "### Changes in this PR",
        "",
    ]
    for fix in fixes_applied:
        badge = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(fix["severity"], "⚪")
        lines.append(f"#### {badge} {fix['title']}")
        lines.append(f"- **File:** `{fix['file']}`")
        lines.append(f"- **Category:** `{fix['category']}`")
        lines.append(f"- **Description:** {fix['description']}")
        lines.append(f"- **Fix applied:** {fix['recommendation']}")
        lines.append("")

    lines += [
        "### Validation Checklist",
        "- [ ] Review each changed file in the diff",
        "- [ ] Verify meta tags render correctly in browser dev tools",
        "- [ ] Confirm no existing markup was unintentionally altered",
        "- [ ] Run the SEO skill again after merging to validate improvement",
        "",
        "### SEO Impact",
        "Fixing these issues will improve:",
        "- Search engine indexation",
        "- Social sharing previews (OG / Twitter Card)",
        "- AI search crawler accessibility",
        "- SERP snippet quality",
        "",
        "---",
        f"*Generated by SEO Runtime · Skill {skill_id:02d}/23 · Run `{run_id}`*",
        f"*Dashboard: https://amulyagupta.in/seo/dashboard/*",
    ]
    return "\n".join(lines)


def generate_and_open_pr(
    run_id: str,
    skill_id: int,
    skill_name: str,
    findings: list[dict],
    *,
    dry_run: bool = False,
) -> Optional[str]:
    """
    Main entry point. Returns PR URL on success, None if no fixable issues or on failure.

    Args:
        run_id: Short run identifier (e.g. "a1b2c3d4").
        skill_id: The skill that generated the findings.
        skill_name: Human-readable skill name.
        findings: List of finding dicts from skill execution.
        dry_run: If True, compute fixes but do not call GitHub API (for testing).
    """
    if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
        log.info("PR generator: GITHUB_TOKEN or GITHUB_REPOSITORY not set — skipping")
        return None

    fixable = [f for f in findings if f.get("category") in _FIXABLE_CATEGORIES]
    if not fixable:
        log.info("PR generator: no fixable findings in this run (skill %d)", skill_id)
        return None

    log.info("PR generator: %d fixable findings detected", len(fixable))
    gh = _GH(GITHUB_TOKEN, GITHUB_REPOSITORY)

    # Get current HEAD SHA
    head_sha = gh.ref_sha()
    if not head_sha:
        log.error("PR generator: failed to get HEAD SHA")
        return None

    # Create fix branch
    date_str = datetime.utcnow().strftime("%Y%m%d")
    branch = f"seo-fix/{date_str}-skill{skill_id:02d}-{run_id}"

    if not dry_run and not gh.create_branch(branch, head_sha):
        log.error("PR generator: failed to create branch %s", branch)
        return None

    # Collect and apply fixes file-by-file
    fixes_applied: list[dict] = []
    file_groups = _group_by_file(fixable)
    today = datetime.utcnow().strftime("%Y-%m-%d")

    for file_path, file_findings in file_groups.items():
        # Special handling for robots.txt and sitemap.xml
        if file_path == "robots.txt":
            file_data = gh.get_file(file_path) if not dry_run else {"content": "", "sha": ""}
            if not file_data:
                continue
            current = file_data["content"]
            updated = _fix_ai_crawlers(current)
            if updated and not dry_run:
                message = f"fix(seo): add missing AI crawler directives to robots.txt [skill {skill_id}]"
                if gh.update_file(file_path, updated, file_data["sha"], message, branch):
                    for ff in file_findings:
                        fixes_applied.append({**ff, "file": file_path})
            elif updated:
                for ff in file_findings:
                    fixes_applied.append({**ff, "file": file_path})
            continue

        if file_path == "sitemap.xml":
            file_data = gh.get_file(file_path) if not dry_run else {"content": "", "sha": ""}
            if not file_data:
                continue
            current = file_data["content"]
            updated = _fix_sitemap_lastmod(current, today)
            if updated and not dry_run:
                message = f"fix(seo): add missing lastmod dates to sitemap.xml [skill {skill_id}]"
                if gh.update_file(file_path, updated, file_data["sha"], message, branch):
                    for ff in file_findings:
                        fixes_applied.append({**ff, "file": file_path})
            elif updated:
                for ff in file_findings:
                    fixes_applied.append({**ff, "file": file_path})
            continue

        # HTML file fixes — accumulate all changes before committing
        if not file_path.endswith(".html"):
            log.debug("PR generator: skipping non-HTML, non-robots, non-sitemap: %s", file_path)
            continue

        file_data = gh.get_file(file_path) if not dry_run else {"content": "", "sha": ""}
        if not file_data:
            log.warning("PR generator: could not fetch %s — skipping", file_path)
            continue

        current_content = file_data["content"]
        applied_for_file: list[dict] = []

        for ff in file_findings:
            fixed = _apply_fix(ff, current_content)
            if fixed is not None:
                current_content = fixed
                applied_for_file.append(ff)

        if applied_for_file:
            if not dry_run:
                titles = ", ".join(f.get("title", "")[:40] for f in applied_for_file[:3])
                message = (
                    f"fix(seo): {len(applied_for_file)} SEO fix(es) in {file_path} "
                    f"[skill {skill_id}] — {titles}"
                )
                if gh.update_file(file_path, current_content, file_data["sha"], message, branch):
                    for ff in applied_for_file:
                        fixes_applied.append({**ff, "file": file_path})
                    log.info("PR generator: committed %d fixes to %s", len(applied_for_file), file_path)
                else:
                    log.error("PR generator: failed to commit fixes for %s", file_path)
            else:
                for ff in applied_for_file:
                    fixes_applied.append({**ff, "file": file_path})

    if not fixes_applied:
        log.info("PR generator: no fixes could be applied (all already present or unfixable)")
        if not dry_run:
            # Delete the empty branch to avoid clutter
            try:
                requests.delete(
                    f"{gh.base}/git/refs/heads/{branch}",
                    headers=gh._h, timeout=10,
                )
            except Exception:
                pass
        return None

    # Open the PR
    unfixable = len(findings) - len(fixes_applied)
    pr_title = (
        f"[SEO Fix] Skill {skill_id:02d} — {len(fixes_applied)} auto-fix(es) | {skill_name}"
    )
    pr_body = _pr_body(run_id, skill_id, skill_name, fixes_applied, unfixable, len(findings))

    if dry_run:
        log.info("PR generator (dry run): would create PR '%s' with %d fixes", pr_title, len(fixes_applied))
        return f"https://github.com/{GITHUB_REPOSITORY}/pulls (dry-run)"

    pr_url = gh.create_pr(pr_title, pr_body, branch)
    if pr_url:
        log.info("PR generator: PR created → %s", pr_url)
    else:
        log.error("PR generator: PR creation failed for branch %s", branch)

    return pr_url
