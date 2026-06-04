#!/usr/bin/env python3
"""
PR notification email — invoked by the SEO runtime workflow after an
auto-fix PR is created.

Extracted from an inline `python3 -c "..."` block in seo-runtime.yml.
Embedding multi-line Python inside a YAML `run: |` scalar repeatedly broke
the workflow parser (the heredoc body sat at column 0, terminating the block
scalar). Keeping it in a real file makes it parseable, testable, and escapable.

Reads:
  PR_URL env var          — the URL of the created pull request (required)
  seo/data/pr_body.txt    — the PR body text (optional)
  seo/data/runs.json      — to reference the latest run (optional)

Never raises — PR notification is non-critical; failures are logged and the
process exits 0 so it cannot fail the workflow.
"""

import html as html_lib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import emailer
import memory


def main() -> int:
    pr_url = os.environ.get("PR_URL", "").strip()
    if not pr_url:
        print("notify_pr: PR_URL not set — skipping notification.")
        return 0

    runs = memory.load_runs()
    last = runs[-1] if runs else {}

    pr_body_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "pr_body.txt")
    try:
        with open(pr_body_path) as f:
            pr_body = f.read()
    except OSError:
        pr_body = "(PR body unavailable)"

    run_id = html_lib.escape(str(last.get("run_id", "?")))
    skill_id = html_lib.escape(str(last.get("skill_id", "?")))
    skill_name = html_lib.escape(str(last.get("skill_name", "")))
    pr_url_safe = html_lib.escape(pr_url, quote=True)
    pr_body_html = html_lib.escape(pr_body[:1200])

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:32px;background:#f1f5f9;font-family:-apple-system,sans-serif;">
<div style="max-width:640px;margin:0 auto;">
  <div style="background:linear-gradient(135deg,#0f172a,#1e3a5f);border-radius:14px;padding:28px;margin-bottom:20px;">
    <h1 style="color:#fff;margin:0 0 6px;font-size:20px;">&#x2705; SEO Auto-Fix PR Created</h1>
    <p style="color:#94a3b8;margin:0;font-size:13px;">Run #{run_id} &middot; Skill {skill_id}/23 &middot; {skill_name}</p>
  </div>
  <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:22px;margin-bottom:16px;">
    <p style="margin:0 0 16px;font-size:14px;color:#1e293b;">The SEO Auto-Fixer generated fixes and opened a pull request. <strong>Human review and manual merge required.</strong></p>
    <a href="{pr_url_safe}" style="display:inline-block;background:#0284c7;color:#fff;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:600;font-size:13px;">&#x1F517; Review PR on GitHub</a>
  </div>
  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:18px;">
    <pre style="margin:0;font-size:11px;color:#475569;white-space:pre-wrap;font-family:monospace;">{pr_body_html}</pre>
  </div>
  <p style="text-align:center;color:#94a3b8;font-size:11px;margin-top:16px;">SEO Runtime Bot 2.0 &middot; amulyagupta.in</p>
</div></body></html>"""

    text = (
        f"SEO Auto-Fix PR created: {pr_url}\n\n"
        f"Review and merge required.\n\n"
        f"{pr_body[:500]}"
    )

    try:
        ok = emailer.send_report(
            f"[SEO FIX PR] Auto-Fix Created — Run #{last.get('run_id', '?')} | Review Required",
            html,
            text,
        )
        print("PR notification email sent." if ok else "PR notification email failed (non-fatal).")
    except Exception as e:  # never fail the workflow over a notification
        print(f"PR notification email error (non-fatal): {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
