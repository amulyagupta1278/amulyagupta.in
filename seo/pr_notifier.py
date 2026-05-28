#!/usr/bin/env python3
"""
Send a PR-created notification email.

Usage: python seo/pr_notifier.py <pr_url>

Reads the last run from seo/data/runs.json and pr body from seo/data/pr_body.txt,
then sends a styled HTML email via Gmail. Exits 0 on success, 1 on failure (non-fatal
— caller should not abort if this fails).
"""

import os
import sys

# Allow imports from seo/ when invoked from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import emailer
import memory


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("pr_notifier: no PR URL supplied — skipping notification.", flush=True)
        return 0

    pr_url = sys.argv[1].strip()

    runs = memory.load_runs()
    last = runs[-1] if runs else {}

    pr_body_path = os.path.join(os.path.dirname(__file__), "data", "pr_body.txt")
    try:
        pr_body = open(pr_body_path).read()
    except OSError:
        pr_body = "(PR body not available)"

    run_id = last.get("run_id", "?")
    skill_id = last.get("skill_id", "?")
    skill_name = last.get("skill_name", "")

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:32px;background:#f1f5f9;font-family:-apple-system,sans-serif;">
<div style="max-width:640px;margin:0 auto;">

  <div style="background:linear-gradient(135deg,#0f172a,#1e3a5f);border-radius:14px;
              padding:28px;margin-bottom:20px;">
    <h1 style="color:#fff;margin:0 0 6px;font-size:20px;">&#x2705; SEO Auto-Fix PR Created</h1>
    <p style="color:#94a3b8;margin:0;font-size:13px;">
      Run #{run_id} &middot; Skill {skill_id}/23 &middot; {skill_name}
    </p>
  </div>

  <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;
              padding:22px;margin-bottom:16px;">
    <p style="margin:0 0 16px;font-size:14px;color:#1e293b;">
      The SEO Auto-Fixer generated fixes and opened a pull request.
      <strong>Human review and manual merge required — the runtime has no auto-merge authority.</strong>
    </p>
    <a href="{pr_url}"
       style="display:inline-block;background:#0284c7;color:#fff;padding:10px 20px;
              border-radius:8px;text-decoration:none;font-weight:600;font-size:13px;">
      &#x1F517; Review PR on GitHub
    </a>
  </div>

  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:18px;">
    <pre style="margin:0;font-size:11px;color:#475569;white-space:pre-wrap;
                font-family:monospace;">{pr_body[:1200]}</pre>
  </div>

  <p style="text-align:center;color:#94a3b8;font-size:11px;margin-top:16px;">
    SEO Runtime Bot 2.0 &middot; amulyagupta.in
  </p>

</div>
</body>
</html>"""

    text = (
        f"SEO Auto-Fix PR Created — Run #{run_id}\n\n"
        f"Review and merge required.\n\n"
        f"PR: {pr_url}\n\n"
        f"{pr_body[:500]}"
    )

    subject = f"[SEO FIX PR] Auto-Fix Created — Run #{run_id} | Review Required"
    ok = emailer.send_report(subject, html, text)
    if ok:
        print("PR notification email sent.", flush=True)
    else:
        print("PR notification email failed (non-fatal).", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
