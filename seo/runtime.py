#!/usr/bin/env python3
"""
SEO Autonomous Runtime — amulyagupta.in
Runs daily via GitHub Actions. Executes one SEO skill per day across a 23-day cycle.
Persists intelligence in Google Sheets. Sends email reports.
"""

import logging
import os
import sys
import time
import uuid
from datetime import datetime

# Ensure skills/ dir is on the path when running from seo/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "skills"))
sys.path.insert(0, os.path.dirname(__file__))

import config
import crawler
import emailer
import memory
from sheets import SheetsClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("seo.runtime")


def run():
    run_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    now = datetime.utcnow()

    log.info("=" * 60)
    log.info("SEO Runtime starting | run_id=%s | %s UTC", run_id, now.isoformat())
    log.info("Site: %s", config.SITE_URL)
    log.info("=" * 60)

    # Init sheets
    sheets = SheetsClient()
    if not sheets.available:
        log.warning("Running without Google Sheets persistence.")

    # Determine which skill to run
    override = config.SKILL_OVERRIDE.strip().lower()
    if override and override != "auto" and override.isdigit():
        skill_id = int(override)
        log.info("Skill override: %d", skill_id)
    else:
        skill_id = memory.get_next_skill(sheets)
        log.info("Next scheduled skill: %d", skill_id)

    if not 1 <= skill_id <= 23:
        log.error("Invalid skill_id %d — aborting", skill_id)
        sys.exit(1)

    skill_name = config.SKILL_NAMES[skill_id - 1]
    log.info("Running Skill %02d: %s", skill_id, skill_name)

    # Log execution start
    sheets.log_runtime(run_id, "INFO", f"Starting skill {skill_id}: {skill_name}", skill_id)

    # Crawl all site pages
    log.info("Crawling %d pages...", len(config.SITE_PAGES))
    try:
        pages = crawler.crawl_all_pages(delay=0.5)
        log.info("Crawl complete. Pages: %d", len(pages))
    except Exception as e:
        log.error("Crawl failed: %s", e)
        sheets.log_runtime(run_id, "ERROR", f"Crawl failed: {e}", skill_id)
        _write_incident(sheets, run_id, "critical", "crawl", "Crawl failure", str(e))
        sys.exit(1)

    # Load skill
    from skills import SKILL_REGISTRY
    skill_cls = SKILL_REGISTRY.get(skill_id)
    if not skill_cls:
        log.error("Skill %d not found in registry", skill_id)
        sys.exit(1)

    skill = skill_cls()
    log.info("Executing skill...")

    try:
        result = skill.run(pages)
    except Exception as e:
        import traceback
        log.error("Skill %d failed: %s\n%s", skill_id, e, traceback.format_exc())
        sheets.log_runtime(run_id, "ERROR", f"Skill {skill_id} failed: {e}", skill_id)
        _write_incident(sheets, run_id, "critical", "runtime", f"Skill {skill_id} execution failed", str(e))
        sys.exit(1)

    duration = int(time.time() - start_time)
    log.info(result.summary_line())
    log.info("Duration: %ds", duration)

    findings_dicts = result.findings_as_dicts()

    # Update issue registry
    log.info("Updating issue registry...")
    for finding in findings_dicts:
        issue = memory.upsert_issue(skill_id, finding)
        sheets.append("seo_issues", [
            issue["issue_id"], issue["first_seen"], issue["last_seen"],
            issue["skill_id"], issue["severity"], issue["category"],
            issue["url"], issue["title"][:200], issue["description"][:500],
            issue["status"], issue["occurrences"],
        ])

        if finding.get("severity") == "critical":
            _write_incident(sheets, run_id, "critical", finding.get("category", ""),
                           finding.get("title", ""), finding.get("description", ""),
                           finding.get("url", ""))

    # Append run record
    run_record = {
        "run_id": run_id,
        "date": now.isoformat(),
        "skill_id": skill_id,
        "skill_name": skill_name,
        "score": result.score,
        "issues_found": len(findings_dicts),
        "issues_critical": result.critical_count,
        "duration_s": duration,
        "status": "completed",
        "notes": f"Cycle run {skill_id}/23",
    }
    memory.append_run(run_record)
    sheets.append("seo_runs", list(run_record.values()))

    # Append score
    scores = memory.load_score_history()
    delta = memory.append_score(skill_id, skill_name, result.score, run_id)
    sheets.append("seo_scores", [
        now.isoformat(), skill_id, skill_name, result.score,
        result.score - delta, delta, 1, run_id,
    ])
    scores = memory.load_score_history()

    # AI visibility tracking
    if skill_id in [11, 23]:
        for finding in findings_dicts:
            sheets.append("seo_ai_visibility", [
                now.isoformat(), finding.get("title", ""),
                finding.get("severity", ""), result.score,
                finding.get("description", "")[:300], run_id,
            ])

    # CWV tracking
    if skill_id in [5, 15]:
        cwv_records = result.metadata.get("cwv_records", [])
        for rec in cwv_records:
            for metric, key in [("lcp", "lcp_ms"), ("cls", "cls"), ("ttfb", "ttfb_ms")]:
                sheets.append("seo_cwv", [
                    now.isoformat(), rec.get("url", ""), metric,
                    rec.get(key, 0), "unknown", rec.get("strategy", "mobile"), run_id,
                ])

    # Build dashboard snapshot
    issues = memory.load_issues()
    snapshot = memory.build_dashboard_snapshot(run_record, findings_dicts, scores, issues)
    log.info("Dashboard snapshot saved.")

    # Generate and send email report
    log.info("Sending email report...")
    html, text = emailer.build_morning_brief(run_record, findings_dicts, skill_name, result.score)
    subject = f"[SEO] Day {skill_id}/23 — {skill_name} | Score: {result.score}/100 | {now.strftime('%b %d')}"
    email_sent = emailer.send_report(subject, html, text)

    email_status = "sent" if email_sent else "failed"
    email_error = "" if email_sent else "Check GMAIL credentials"
    sheets.append("seo_emails", [
        now.isoformat(), config.REPORT_EMAIL, subject, email_status, email_error, run_id
    ])

    # Save run state
    memory.save_run_state(skill_id, run_id)

    sheets.log_runtime(run_id, "INFO", f"Run complete. Score: {result.score} | Issues: {len(findings_dicts)}", skill_id)

    # Summary
    log.info("=" * 60)
    log.info("RUN COMPLETE")
    log.info("  Skill: %02d / %s", skill_id, skill_name)
    log.info("  Score: %d/100", result.score)
    log.info("  Issues: %d (critical: %d)", len(findings_dicts), result.critical_count)
    log.info("  Email: %s", email_status)
    log.info("  Duration: %ds", duration)
    log.info("=" * 60)


def _write_incident(sheets, run_id, severity, category, title, description, url=""):
    incident_id = str(uuid.uuid4())[:8]
    sheets.append("seo_incidents", [
        incident_id, datetime.utcnow().isoformat(), severity,
        category, title[:200], description[:500], "active", "", run_id,
    ])


if __name__ == "__main__":
    run()
