#!/usr/bin/env python3
"""Weekly SEO summary email — invoked by the weekly-summary workflow job."""
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import memory
import emailer


def collect_git_activity() -> dict:
    """Gather branch name, commits from the past 7 days, and file change stats."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def run(cmd):
        try:
            return subprocess.check_output(cmd, cwd=repo_root, stderr=subprocess.DEVNULL, text=True).strip()
        except Exception:
            return ""

    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    remote_url = run(["git", "remote", "get-url", "origin"])

    # Commits in the last 7 days: hash | author | date | subject
    log_raw = run([
        "git", "log",
        f"--since={since}",
        "--pretty=format:%H|%an|%ad|%s",
        "--date=format:%b %d %H:%M",
    ])

    commits = []
    for line in log_raw.splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            commits.append({
                "hash": parts[0][:7],
                "author": parts[1],
                "date": parts[2],
                "subject": parts[3],
            })

    # Files changed in the last 7 days (across all commits)
    diff_stat = ""
    if commits:
        oldest_hash = commits[-1]["hash"]
        diff_stat = run(["git", "diff", "--stat", f"{oldest_hash}^", "HEAD"])

    # Insertions/deletions summary
    shortstat = ""
    if commits:
        shortstat = run(["git", "diff", "--shortstat", f"{commits[-1]['hash']}^", "HEAD"])

    return {
        "branch": branch,
        "remote_url": remote_url,
        "commits": commits,
        "diff_stat": diff_stat,
        "shortstat": shortstat,
        "period_days": 7,
    }


runs = memory.load_runs()
issues = memory.load_issues()
scores = memory.load_score_history()
forecast = memory.build_predictive_forecast(scores)
comparison = memory.get_historical_comparison(runs, scores)
recurring = memory.detect_recurring_issues(issues)
git_activity = collect_git_activity()

html, text = emailer.build_weekly_summary(
    runs, issues, scores, forecast, comparison, recurring,
    git_activity=git_activity,
)
ok = emailer.send_report(
    "[SEO WEEKLY] amulyagupta.in — Weekly Intelligence Summary",
    html,
    text,
)
if ok:
    print("Weekly summary sent.")
else:
    print("Weekly summary email delivery failed.", file=sys.stderr)
    sys.exit(1)
