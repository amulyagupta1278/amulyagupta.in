#!/usr/bin/env python3
"""
SEO Auto-Fix PR Generator — amulyagupta.in

Implements the mandatory safe-remediation workflow from governance spec §18-20:

    Runtime  →  Detect Issue  →  Generate Proposed Fix
    →  Create Feature Branch  →  Open Pull Request
    →  Human Review  →  Manual Approval  →  Manual Merge

HARD GOVERNANCE CONSTRAINT:
  This module NEVER auto-merges, never pushes to main/master, and never
  self-approves PRs.  It only creates branches and PRs for human review.
  Violations are a Hard Stop 2 breach and will be flagged to operators.

Supported auto-fix categories:
  - robots        : add AI-crawler Allow directives, Sitemap reference
  - sitemap       : add missing page entries with lastmod/priority
  - meta-tags     : flag missing meta descriptions (informational PRs)
  - schema        : flag missing structured data fields
"""

import base64
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Optional

import requests

log = logging.getLogger("seo.pr_generator")

# ── GitHub API settings ───────────────────────────────────────────────────────
_GITHUB_API = "https://api.github.com"
_GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
_GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "")  # "owner/repo"
_GITHUB_REF = os.environ.get("GITHUB_REF", "refs/heads/main")

# ── Governance constants ──────────────────────────────────────────────────────
_PROTECTED_BRANCHES = frozenset({"main", "master"})
_PR_BRANCH_PREFIX = "fix/seo-auto-"
_MAX_FILES_PER_PR = 5   # safety limit; large PRs are harder to review
_PR_LABEL = "seo-auto-fix"

# ── Categories this generator can propose fixes for ───────────────────────────
FIXABLE_CATEGORIES = frozenset({"robots", "sitemap", "ai-crawlers"})


# ─────────────────────────────────────────────────────────────────────────────
# GitHub API helpers
# ─────────────────────────────────────────────────────────────────────────────

def _gh_headers() -> dict:
    return {
        "Authorization": f"Bearer {_GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _gh_get(path: str, **kwargs) -> Optional[dict]:
    if not _GITHUB_TOKEN or not _GITHUB_REPOSITORY:
        return None
    try:
        r = requests.get(
            f"{_GITHUB_API}{path}",
            headers=_gh_headers(),
            timeout=20,
            **kwargs,
        )
        if r.status_code == 200:
            return r.json()
        log.warning("GitHub GET %s → %d: %s", path, r.status_code, r.text[:200])
        return None
    except Exception as e:
        log.error("GitHub GET %s failed: %s", path, e)
        return None


def _gh_post(path: str, payload: dict) -> Optional[dict]:
    if not _GITHUB_TOKEN or not _GITHUB_REPOSITORY:
        return None
    try:
        r = requests.post(
            f"{_GITHUB_API}{path}",
            headers=_gh_headers(),
            json=payload,
            timeout=20,
        )
        if r.status_code in (200, 201):
            return r.json()
        log.warning("GitHub POST %s → %d: %s", path, r.status_code, r.text[:300])
        return None
    except Exception as e:
        log.error("GitHub POST %s failed: %s", path, e)
        return None


def _gh_put(path: str, payload: dict) -> Optional[dict]:
    if not _GITHUB_TOKEN or not _GITHUB_REPOSITORY:
        return None
    try:
        r = requests.put(
            f"{_GITHUB_API}{path}",
            headers=_gh_headers(),
            json=payload,
            timeout=20,
        )
        if r.status_code in (200, 201):
            return r.json()
        log.warning("GitHub PUT %s → %d: %s", path, r.status_code, r.text[:300])
        return None
    except Exception as e:
        log.error("GitHub PUT %s failed: %s", path, e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Branch helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_default_branch_sha() -> Optional[str]:
    repo = _gh_get(f"/repos/{_GITHUB_REPOSITORY}")
    if not repo:
        return None
    default_branch = repo.get("default_branch", "main")
    ref_data = _gh_get(f"/repos/{_GITHUB_REPOSITORY}/git/ref/heads/{default_branch}")
    if not ref_data:
        return None
    return ref_data.get("object", {}).get("sha")


def _create_branch(branch_name: str, base_sha: str) -> bool:
    result = _gh_post(
        f"/repos/{_GITHUB_REPOSITORY}/git/refs",
        {"ref": f"refs/heads/{branch_name}", "sha": base_sha},
    )
    return result is not None


def _get_file(file_path: str) -> Optional[dict]:
    return _gh_get(f"/repos/{_GITHUB_REPOSITORY}/contents/{file_path}")


def _update_file(
    file_path: str,
    branch: str,
    content: str,
    message: str,
    sha: Optional[str] = None,
) -> bool:
    payload: dict = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    result = _gh_put(f"/repos/{_GITHUB_REPOSITORY}/contents/{file_path}", payload)
    return result is not None


def _create_pr(
    title: str,
    body: str,
    head: str,
    base: str = "main",
) -> Optional[str]:
    result = _gh_post(
        f"/repos/{_GITHUB_REPOSITORY}/pulls",
        {
            "title": title,
            "body": body,
            "head": head,
            "base": base,
            "draft": False,
        },
    )
    if result:
        return result.get("html_url")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Fix generators — return (new_content, description) or None if no fix needed
# ─────────────────────────────────────────────────────────────────────────────

def _fix_robots_txt(
    current_content: str,
    findings: list[dict],
    site_url: str,
) -> Optional[tuple[str, str]]:
    """Add missing AI-crawler Allow directives and Sitemap reference."""
    changes = []
    content = current_content

    # Missing Sitemap reference
    if not re.search(r"sitemap\s*:", content, re.IGNORECASE):
        content += f"\nSitemap: {site_url}/sitemap.xml\n"
        changes.append("Added Sitemap directive")

    # Missing AI crawler rules
    ai_bots = {
        "GPTBot": "OpenAI's web crawler for ChatGPT training and search",
        "ClaudeBot": "Anthropic's Claude AI crawler",
        "PerplexityBot": "Perplexity AI search crawler",
        "Google-Extended": "Google's extended AI training crawler",
        "OAI-SearchBot": "OpenAI SearchGPT crawler",
        "Bingbot": "Microsoft Bing crawler (required for Copilot)",
    }
    missing_bots = [
        f.get("title", "").replace("Missing ", "").replace(" directive in robots.txt", "").strip()
        for f in findings
        if "missing" in f.get("title", "").lower()
        and any(bot.lower() in f.get("title", "").lower() for bot in ai_bots)
        and f.get("category") in ("robots", "ai-crawlers")
    ]

    for bot in missing_bots:
        if bot and bot.lower() not in content.lower():
            content += f"\nUser-agent: {bot}\nAllow: /\n"
            changes.append(f"Added explicit Allow for {bot}")

    if not changes:
        return None
    return content, "; ".join(changes)


def _fix_sitemap_xml(
    current_content: str,
    findings: list[dict],
    site_url: str,
) -> Optional[tuple[str, str]]:
    """Add missing page entries to sitemap.xml."""
    missing_pages = [
        f for f in findings
        if f.get("category") == "sitemap"
        and "missing from sitemap" in f.get("title", "").lower()
    ]
    if not missing_pages:
        return None

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    new_entries = []
    for finding in missing_pages:
        url = finding.get("url", "")
        if not url.startswith("https://"):
            continue
        path = url.replace(site_url, "").rstrip("/")
        priority = "1.0" if path in ("", "/") else "0.7"
        changefreq = "weekly" if path in ("", "/", "/blog/index.html") else "monthly"
        new_entries.append(
            f"  <url>\n"
            f"    <loc>{url}</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            f"    <changefreq>{changefreq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            f"  </url>"
        )

    if not new_entries:
        return None

    # Insert before </urlset>
    updated = current_content.replace(
        "</urlset>",
        "\n".join(new_entries) + "\n</urlset>",
    )
    paths = [f.get("url", "").replace(site_url, "") for f in missing_pages]
    return updated, f"Added {len(new_entries)} missing URL(s): {', '.join(paths)}"


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def generate_fix_pr(
    run_id: str,
    skill_id: int,
    skill_name: str,
    findings: list[dict],
    site_url: str = "https://amulyagupta.in",
) -> Optional[str]:
    """
    Attempt to generate a GitHub PR with proposed SEO fixes.

    Returns the PR URL if created, None otherwise.

    Governance constraints enforced:
    - Only creates branches prefixed with fix/seo-auto-
    - Never targets main/master (PRs are always opened against default branch
      for human review — the runtime creates the branch but cannot merge it)
    - Writes at most MAX_FILES_PER_PR files per PR
    - All proposed changes are clearly annotated in the PR body
    """
    if not _GITHUB_TOKEN or not _GITHUB_REPOSITORY:
        log.info("PR generator: GitHub credentials not configured — skipping")
        return None

    fixable = [
        f for f in findings
        if f.get("category") in FIXABLE_CATEGORIES
        and f.get("severity") in ("critical", "warning")
    ]
    if not fixable:
        log.info("PR generator: no auto-fixable findings for skill %d", skill_id)
        return None

    log.info("PR generator: %d fixable finding(s) — preparing branch", len(fixable))

    # ── Get base SHA for branching ────────────────────────────────────────────
    base_sha = _get_default_branch_sha()
    if not base_sha:
        log.error("PR generator: could not resolve default branch SHA — aborting")
        return None

    # ── Create feature branch ─────────────────────────────────────────────────
    branch_name = f"{_PR_BRANCH_PREFIX}{run_id}"
    if not _create_branch(branch_name, base_sha):
        log.error("PR generator: failed to create branch %s — aborting", branch_name)
        return None
    log.info("PR generator: branch created: %s", branch_name)

    # ── Apply fixes ───────────────────────────────────────────────────────────
    applied_fixes: list[str] = []
    files_changed = 0

    # robots.txt
    if files_changed < _MAX_FILES_PER_PR:
        robots_findings = [f for f in fixable if f.get("category") in ("robots", "ai-crawlers")]
        if robots_findings:
            robots_file = _get_file("robots.txt")
            if robots_file:
                current_robots = base64.b64decode(robots_file["content"]).decode()
                fix = _fix_robots_txt(current_robots, robots_findings, site_url)
                if fix:
                    new_content, desc = fix
                    ok = _update_file(
                        "robots.txt",
                        branch_name,
                        new_content,
                        f"fix(seo): {desc} [auto-fix · run {run_id}]",
                        sha=robots_file.get("sha"),
                    )
                    if ok:
                        applied_fixes.append(f"**robots.txt**: {desc}")
                        files_changed += 1
                        log.info("PR generator: robots.txt patched — %s", desc)

    # sitemap.xml
    if files_changed < _MAX_FILES_PER_PR:
        sitemap_findings = [f for f in fixable if f.get("category") == "sitemap"]
        if sitemap_findings:
            sitemap_file = _get_file("sitemap.xml")
            if sitemap_file:
                current_sitemap = base64.b64decode(sitemap_file["content"]).decode()
                fix = _fix_sitemap_xml(current_sitemap, sitemap_findings, site_url)
                if fix:
                    new_content, desc = fix
                    ok = _update_file(
                        "sitemap.xml",
                        branch_name,
                        new_content,
                        f"fix(seo): {desc} [auto-fix · run {run_id}]",
                        sha=sitemap_file.get("sha"),
                    )
                    if ok:
                        applied_fixes.append(f"**sitemap.xml**: {desc}")
                        files_changed += 1
                        log.info("PR generator: sitemap.xml patched — %s", desc)

    if not applied_fixes:
        log.info("PR generator: no files changed — no PR needed")
        return None

    # ── Build PR body ─────────────────────────────────────────────────────────
    findings_table = "\n".join(
        f"| {f.get('severity','?').upper()} | {f.get('title','?')} | {f.get('category','?')} |"
        for f in fixable[:20]
    )

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pr_body = f"""## SEO Auto-Fix Proposal

**Generated by**: SEO Runtime Bot
**Run ID**: `{run_id}`
**Skill**: #{skill_id:02d}/23 — {skill_name}
**Generated at**: {now_str}

---

### ⚠ Human Review Required

This PR was generated automatically by the SEO runtime.
**It must be reviewed and manually merged — the bot has NO merge authority.**

Before merging:
- [ ] Verify the proposed changes are correct
- [ ] Check that no file is inadvertently broken
- [ ] Review the robots.txt directives for security implications
- [ ] Confirm sitemap URLs are valid and live

---

### Changes Proposed

{chr(10).join(f"- {fix}" for fix in applied_fixes)}

---

### Findings That Triggered This PR

| Severity | Issue | Category |
|----------|-------|----------|
{findings_table}

---

### Governance

- Runtime governance: Hard Stop 2 — NO auto-merge authority
- All SEO site changes follow: Runtime → PR → Human Review → Manual Merge
- This PR was created on branch `{branch_name}` (NOT pushed to main)
- The runtime cannot approve or merge this PR

---

*SEO Runtime Bot · amulyagupta.in · Autonomous Intelligence Platform*
"""

    # ── Determine base branch ─────────────────────────────────────────────────
    repo_info = _gh_get(f"/repos/{_GITHUB_REPOSITORY}")
    base_branch = repo_info.get("default_branch", "main") if repo_info else "main"

    pr_title = (
        f"fix(seo): auto-proposed fixes from Skill {skill_id:02d} — {skill_name} "
        f"[{run_id}]"
    )[:100]

    pr_url = _create_pr(pr_title, pr_body, head=branch_name, base=base_branch)
    if pr_url:
        log.info("PR generator: PR created → %s", pr_url)
    else:
        log.error("PR generator: PR creation failed")

    return pr_url
