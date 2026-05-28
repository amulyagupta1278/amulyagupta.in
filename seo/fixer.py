#!/usr/bin/env python3
"""
SEO Auto-Fixer — runs after each daily audit.

Reads seo/data/issues.json, generates concrete file fixes for automatable
issue categories (schema, sitemap, robots), writes them to the repo, and
prints a PR body to stdout for the workflow to capture.

All fixes are proposed-only — the workflow creates a PR; nothing auto-merges.

Exit codes:
  0 — fixes generated (workflow should create PR)
  2 — no fixable issues (workflow skips PR creation)
  1 — runtime error
"""

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# ── Categories the fixer can handle ──────────────────────────────────────────
FIXABLE_CATEGORIES = {"schema", "sitemap", "robots", "ai-crawlers"}


def load_issues() -> list[dict]:
    path = os.path.join(DATA_DIR, "issues.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        data = json.load(f)
    return [v for v in data.values() if v.get("status") == "active"]


def load_last_run() -> dict:
    path = os.path.join(DATA_DIR, "runs.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        runs = json.load(f)
    return runs[-1] if runs else {}


# ── Sitemap fixer ─────────────────────────────────────────────────────────────

def fix_sitemap(issues: list[dict]) -> tuple[bool, str]:
    sitemap_issues = [i for i in issues if i.get("category") == "sitemap"
                      and "missing from sitemap" in i.get("title", "").lower()]
    if not sitemap_issues:
        return False, ""

    sitemap_path = os.path.join(REPO_ROOT, "sitemap.xml")
    if not os.path.exists(sitemap_path):
        return False, "sitemap.xml not found"

    with open(sitemap_path) as f:
        content = f.read()

    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        return False, f"sitemap.xml parse error: {e}"

    ns = "http://www.sitemaps.org/schemas/sitemap/0.9"
    existing = {u.text.rstrip("/") for u in root.findall(f".//{{{ns}}}loc")}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    added = []
    for issue in sitemap_issues:
        url = issue.get("url", "").rstrip("/")
        if not url or url in existing:
            continue
        url_el = ET.SubElement(root, f"{{{ns}}}url")
        ET.SubElement(url_el, f"{{{ns}}}loc").text = url + "/"
        ET.SubElement(url_el, f"{{{ns}}}lastmod").text = today
        ET.SubElement(url_el, f"{{{ns}}}changefreq").text = "monthly"
        ET.SubElement(url_el, f"{{{ns}}}priority").text = "0.8"
        existing.add(url)
        added.append(url)

    if not added:
        return False, ""

    ET.indent(root, space="  ")
    new_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + ET.tostring(root, encoding="unicode", xml_declaration=False)
        + "\n"
    )
    with open(sitemap_path, "w") as f:
        f.write(new_xml)

    return True, "\n".join(f"  - Added `{u}` to sitemap.xml" for u in added)


# ── Schema fixer ──────────────────────────────────────────────────────────────

_SCHEMA_FIXES: dict[str, dict] = {
    "missing website schema: /": {
        "file": "index.html",
        "marker": "</head>",
        "block": """\
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "name": "Amulya Gupta",
    "url": "https://amulyagupta.in",
    "description": "AI Systems Engineer building agentic AI workflows, LLM pipelines, and production ML infrastructure.",
    "author": {"@type": "Person", "name": "Amulya Gupta"}
  }
  </script>
""",
    },
    "missing person schema: /contact.html": {
        "file": "contact.html",
        "marker": "</head>",
        "block": """\
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Person",
    "name": "Amulya Gupta",
    "jobTitle": "AI Systems Engineer",
    "url": "https://amulyagupta.in",
    "email": "amulyagupta2001@gmail.com",
    "sameAs": [
      "https://linkedin.com/in/amulya-gupta-bits-pilani",
      "https://github.com/amulyagupta1278"
    ]
  }
  </script>
""",
    },
    "missing blog schema: /blog/index.html": {
        "file": "blog/index.html",
        "marker": "</head>",
        "block": """\
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Blog",
    "name": "Amulya Gupta — AI & MLOps Blog",
    "url": "https://amulyagupta.in/blog/index.html",
    "author": {"@type": "Person", "name": "Amulya Gupta", "url": "https://amulyagupta.in"}
  }
  </script>
""",
    },
    "missing itemlist schema: /blog/index.html": {
        "file": "blog/index.html",
        "marker": "</head>",
        "block": """\
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "ItemList",
    "name": "Blog Posts by Amulya Gupta",
    "url": "https://amulyagupta.in/blog/index.html",
    "itemListElement": [
      {"@type": "ListItem", "position": 1, "name": "Building a Production MLOps Pipeline", "url": "https://amulyagupta.in/blog/post-1-mlops-pipeline.html"},
      {"@type": "ListItem", "position": 2, "name": "MLOps in 2025: The Stack I Actually Use", "url": "https://amulyagupta.in/blog/post-2-mlops-stack.html"},
      {"@type": "ListItem", "position": 3, "name": "AI/ML Roadmap 2026", "url": "https://amulyagupta.in/blog/ai-ml-guide-2026.html"}
    ]
  }
  </script>
""",
    },
}


def fix_schema(issues: list[dict]) -> tuple[bool, str]:
    schema_issues = [i for i in issues if i.get("category") == "schema"]
    if not schema_issues:
        return False, ""

    applied = []
    for issue in schema_issues:
        key = issue.get("title", "").lower()
        fix = _SCHEMA_FIXES.get(key)
        if not fix:
            continue

        file_path = os.path.join(REPO_ROOT, fix["file"])
        if not os.path.exists(file_path):
            continue

        with open(file_path) as f:
            content = f.read()

        # Check schema type not already present
        schema_type = re.search(r'"@type":\s*"(\w+)"', fix["block"])
        stype = schema_type.group(1) if schema_type else ""
        if stype and f'"@type": "{stype}"' in content:
            continue

        new_content = content.replace(fix["marker"], fix["block"] + fix["marker"], 1)
        if new_content == content:
            continue

        with open(file_path, "w") as f:
            f.write(new_content)
        applied.append(f"  - Added `{stype}` schema to `{fix['file']}`")

    if not applied:
        return False, ""
    return True, "\n".join(applied)


# ── Robots fixer ──────────────────────────────────────────────────────────────

_AI_BOTS = ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "OAI-SearchBot"]


def fix_robots(issues: list[dict]) -> tuple[bool, str]:
    bot_issues = [i for i in issues if i.get("category") == "ai-crawlers"
                  and "missing" in i.get("title", "").lower()]
    if not bot_issues:
        return False, ""

    robots_path = os.path.join(REPO_ROOT, "robots.txt")
    if not os.path.exists(robots_path):
        return False, "robots.txt not found"

    with open(robots_path) as f:
        content = f.read()

    added = []
    for issue in bot_issues:
        for bot in _AI_BOTS:
            if bot.lower() in issue.get("title", "").lower() and bot.lower() not in content.lower():
                content += f"\nUser-agent: {bot}\nAllow: /\n"
                added.append(f"  - Added `{bot}` directive to robots.txt")

    if not added:
        return False, ""

    with open(robots_path, "w") as f:
        f.write(content)
    return True, "\n".join(added)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    issues = load_issues()
    last_run = load_last_run()
    run_id = last_run.get("run_id", "unknown")
    skill_id = last_run.get("skill_id", 0)
    skill_name = last_run.get("skill_name", "Unknown Skill")
    score = last_run.get("score", 0)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    fixable = [i for i in issues if i.get("category") in FIXABLE_CATEGORIES]
    if not fixable:
        print(f"No fixable issues in current issue set ({len(issues)} total active issues).")
        return 2

    sitemap_ok, sitemap_notes = fix_sitemap(issues)
    schema_ok, schema_notes = fix_schema(issues)
    robots_ok, robots_notes = fix_robots(issues)

    any_fixed = sitemap_ok or schema_ok or robots_ok
    if not any_fixed:
        print("All fixable issues already resolved — no changes generated.")
        return 2

    sections = []
    if sitemap_ok:
        sections.append(f"### Sitemap\n{sitemap_notes}")
    if schema_ok:
        sections.append(f"### Structured Data\n{schema_notes}")
    if robots_ok:
        sections.append(f"### Robots.txt\n{robots_notes}")

    critical_count = sum(1 for i in issues if i.get("severity") == "critical")
    warning_count = sum(1 for i in issues if i.get("severity") == "warning")

    pr_body = f"""## SEO Auto-Fix — Skill {skill_id:02d}/23 · {skill_name}

**Run ID:** `{run_id}` · **Date:** {date_str} · **Score:** {score}/100

### Issues Addressed
{chr(10).join(sections)}

### Current Issue Summary
| Severity | Count |
|----------|-------|
| Critical | {critical_count} |
| Warning  | {warning_count} |
| Total active | {len(issues)} |

### Review Checklist
- [ ] Verify schema additions render correctly in [Rich Results Test](https://search.google.com/test/rich-results)
- [ ] Check sitemap at [Google Search Console → Sitemaps](https://search.google.com/search-console)
- [ ] Confirm no visual regressions on affected pages

> ⚠️ This PR was auto-generated by the SEO Runtime. **Human review and manual merge required** — the runtime has no auto-merge authority.

https://amulyagupta.in/admin/seo/
"""

    # Write PR body to file for workflow to read
    pr_body_path = os.path.join(DATA_DIR, "pr_body.txt")
    with open(pr_body_path, "w") as f:
        f.write(pr_body)

    print(pr_body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
