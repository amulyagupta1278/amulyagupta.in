#!/usr/bin/env python3
"""Weekly SEO summary email — invoked by the weekly-summary workflow job."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import memory
import emailer

runs = memory.load_runs()
issues = memory.load_issues()
scores = memory.load_score_history()
forecast = memory.build_predictive_forecast(scores)
comparison = memory.get_historical_comparison(runs, scores)
recurring = memory.detect_recurring_issues(issues)
html, text = emailer.build_weekly_summary(runs, issues, scores, forecast, comparison, recurring)
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
