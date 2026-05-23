#!/usr/bin/env python3
"""
SEO Autonomous Runtime — amulyagupta.in

Execution model:
  - Runs once per day via GitHub Actions (23:00 UTC = 04:30 IST)
  - Executes exactly ONE SEO skill per run from the enabled skill pool
  - Skills rotate sequentially; cycle restarts after all enabled skills complete
  - All site fixes are proposed via PR only — never auto-merged

Governance:
  - 7 mandatory Hard Stops enforced on every run (see governance.py)
  - Runtime validation layer before every skill execution
  - Graceful failure handler with operator email alert
  - State preserved on partial failure
  - No direct commits to main; no auto-merge authority
"""

import html as html_lib
import logging
import os
import sys
import time
import traceback
import uuid
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import crawler
import emailer
import governance
import memory
from governance import HardStopViolation
from sheets import SheetsClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("seo.runtime")

# ── Minimum healthy pages required to proceed (50 % of known pages) ──────────
MIN_HEALTHY_PAGES = max(1, len(config.SITE_PAGES) // 2)


# ─────────────────────────────────────────────────────────────────────────────
# Secrets Status Logger
# ─────────────────────────────────────────────────────────────────────────────

_SECRET_MAP = {
    "GOOGLE_SHEETS_SPREADSHEET_ID":       (config.GOOGLE_SHEETS_SPREADSHEET_ID,      "required",  "Google Sheets persistence"),
    "GOOGLE_SERVICE_ACCOUNT_JSON":        (config.GOOGLE_SERVICE_ACCOUNT_JSON,        "required",  "Google Sheets auth"),
    "GMAIL_SENDER":                       (config.GMAIL_SENDER,                       "required",  "Email delivery"),
    "GMAIL_APP_PASSWORD":                 (config.GMAIL_APP_PASSWORD,                 "required",  "Email delivery"),
    "PAGESPEED_API_KEY":                  (config.PAGESPEED_API_KEY,                  "optional",  "Skills 5 & 15 (CWV / PageSpeed)"),
    "GOOGLE_SEARCH_CONSOLE_CREDENTIALS":  (config.GOOGLE_SEARCH_CONSOLE_CREDENTIALS,  "optional",  "Skill 18 live GSC data"),
    "GOOGLE_ANALYTICS_CREDENTIALS":       (config.GOOGLE_ANALYTICS_CREDENTIALS,       "optional",  "Skill 19 live GA4 data"),
}


def log_secrets_status() -> bool:
    """
    Log which secrets are configured vs absent.
    Returns True if all *required* secrets are present.
    Runs at startup so every execution has a clear audit trail.
    """
    ok = True
    log.info("─" * 60)
    log.info("SECRETS STATUS")
    log.info("─" * 60)
    for name, (value, tier, purpose) in _SECRET_MAP.items():
        present = bool(value)
        icon = "✓" if present else ("✗" if tier == "required" else "–")
        level = logging.INFO if present else (logging.ERROR if tier == "required" else logging.WARNING)
        log.log(level, "  %s  %-45s  [%s]  %s", icon, name, tier, purpose)
        if not present and tier == "required":
            ok = False
    if not ok:
        log.error("One or more REQUIRED secrets are missing — platform will run in degraded mode")
    log.info("─" * 60)
    return ok


# ─────────────────────────────────────────────────────────────────────────────
# Validation Layer
# ─────────────────────────────────────────────────────────────────────────────

def validate_skill_id(skill_id: int, enabled_skills: list[int]) -> list[str]:
    errors: list[str] = []
    if not isinstance(skill_id, int) or not 1 <= skill_id <= 23:
        errors.append(f"skill_id {skill_id!r} is out of range 1–23")
    elif skill_id not in enabled_skills:
        errors.append(
            f"Skill {skill_id} is not in the current enabled group "
            f"(ENABLED_SKILL_GROUP={config.ENABLED_SKILL_GROUP}, "
            f"enabled={enabled_skills})"
        )
    return errors


def validate_crawl_results(pages: list[dict]) -> list[str]:
    errors: list[str] = []
    if not pages:
        errors.append("Crawl returned zero pages")
        return errors
    healthy = [p for p in pages if p.get("status") == 200 and p.get("soup")]
    if not healthy:
        errors.append(
            f"No healthy pages after crawl — all {len(pages)} pages "
            f"returned errors or empty HTML"
        )
    elif len(healthy) < MIN_HEALTHY_PAGES:
        errors.append(
            f"Only {len(healthy)}/{len(config.SITE_PAGES)} pages healthy "
            f"(minimum required: {MIN_HEALTHY_PAGES})"
        )
    return errors


def validate_skill_result(result) -> list[str]:
    errors: list[str] = []
    if result is None:
        errors.append("Skill returned None instead of SkillResult")
        return errors
    if not isinstance(result.score, int) or not 0 <= result.score <= 100:
        errors.append(f"Invalid score: {result.score!r}")
    if result.findings is None:
        errors.append("Skill returned findings=None")
    return errors


# ─────────────────────────────────────────────────────────────────────────────
# Failure Handler
# ─────────────────────────────────────────────────────────────────────────────

def handle_failure(
    sheets: SheetsClient,
    run_id: str,
    skill_id: int,
    error: str,
    phase: str = "runtime",
) -> None:
    """Log failure to Sheets and send operator alert email. Never raises."""
    log.error("[FAILURE] phase=%s skill=%d: %s", phase, skill_id, error)

    try:
        sheets.log_runtime(run_id, "CRITICAL", f"[{phase}] {error}"[:500], skill_id)
        sheets.append("seo_incidents", [
            str(uuid.uuid4())[:8],
            datetime.utcnow().isoformat(),
            "critical",
            phase,
            f"Runtime failure during {phase}",
            error[:500],
            "active",
            "",
            run_id,
        ])
    except Exception as e:
        log.error("Failed to log incident to Sheets: %s", e)

    try:
        skill_name = config.SKILL_NAMES[skill_id - 1] if 1 <= skill_id <= 23 else "Unknown"
        html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:32px;background:#0f172a;color:#f1f5f9;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <div style="max-width:600px;margin:0 auto;">
    <div style="background:#7f1d1d;border-radius:12px;padding:20px 24px;margin-bottom:20px;">
      <h2 style="margin:0;font-size:18px;">
        &#x26A0; SEO Runtime Failure — Immediate Attention Required
      </h2>
    </div>
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <tr><td style="padding:8px;color:#94a3b8;width:140px;">Run ID</td>
          <td style="padding:8px;font-family:monospace">{run_id}</td></tr>
      <tr><td style="padding:8px;color:#94a3b8;">Phase</td>
          <td style="padding:8px;">{phase}</td></tr>
      <tr><td style="padding:8px;color:#94a3b8;">Skill</td>
          <td style="padding:8px;">#{skill_id} — {skill_name}</td></tr>
      <tr><td style="padding:8px;color:#94a3b8;">Error</td>
          <td style="padding:8px;color:#fca5a5;">{html_lib.escape(error[:400])}</td></tr>
      <tr><td style="padding:8px;color:#94a3b8;">Time (UTC)</td>
          <td style="padding:8px;">{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
    </table>
    <p style="margin-top:20px;font-size:12px;color:#475569;">
      The runtime stopped safely. No site changes were made.
      Review the GitHub Actions log for the full stack trace.
    </p>
  </div>
</body></html>"""
        emailer.send_report(
            f"[SEO ALERT] Runtime failure — Skill {skill_id} | "
            f"{datetime.utcnow().strftime('%b %d %H:%M')} UTC",
            html,
            f"SEO Runtime Failure\n\nRun: {run_id}\nPhase: {phase}\n"
            f"Skill: {skill_id}\nError: {error}\n\nNo site changes were made.",
        )
    except Exception as e:
        log.error("Failed to send failure alert email: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# Main Runtime
# ─────────────────────────────────────────────────────────────────────────────

def run() -> None:
    run_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    now = datetime.utcnow()
    enabled_skills = config.get_enabled_skills()

    log.info("=" * 60)
    log.info("SEO Runtime  |  run_id=%s  |  %s UTC", run_id, now.isoformat())
    log.info("Site: %s", config.SITE_URL)
    log.info(
        "Skill group: %d  |  enabled skills: %s",
        config.ENABLED_SKILL_GROUP,
        enabled_skills,
    )
    log.info("=" * 60)

    # Log which secrets are configured — produces a clear audit trail on every run
    log_secrets_status()

    if not enabled_skills:
        log.error("No skills enabled — set ENABLED_SKILL_GROUP ≥ 1")
        sys.exit(1)

    # ── Hard Stop 2 + 6: branch protection checks at startup ─────────────────
    # These run before any work begins — if we're on main, abort immediately.
    try:
        governance.enforce_no_direct_push(config.GITHUB_REF)
        governance.assert_no_auto_merge_authority()
        governance.enforce_branch_isolation(config.GITHUB_REF, config.ENABLED_SKILL_GROUP)
    except HardStopViolation as exc:
        log.critical(str(exc))
        sys.exit(1)

    # ── Init Sheets ──────────────────────────────────────────────────────────
    sheets = SheetsClient()
    if not sheets.available:
        log.warning("Google Sheets unavailable — running without persistence")

    # ── Hard Stop 3: verify at least one persistence layer is available ───────
    try:
        governance.enforce_observability(config.DATA_DIR, sheets.available)
    except HardStopViolation as exc:
        handle_failure(sheets, run_id, 0, str(exc), phase="governance-hs3")
        log.critical(str(exc))
        sys.exit(1)

    # ── Determine skill ID ───────────────────────────────────────────────────
    override = config.SKILL_OVERRIDE.strip().lower()
    if override and override != "auto" and override.isdigit():
        skill_id = int(override)
        log.info("Skill override active: %d", skill_id)
    else:
        skill_id = memory.get_next_skill(sheets, enabled_skills)
        log.info("Next scheduled skill: %d", skill_id)

    # ── Hard Stop 1a: one skill per day (auto-rotation only) ─────────────────
    state = memory.load_json("state.json")
    try:
        governance.enforce_one_skill_per_day(
            last_run_date=state.get("last_run_date"),
            is_manual_dispatch=config.IS_MANUAL_DISPATCH,
        )
    except HardStopViolation as exc:
        handle_failure(sheets, run_id, skill_id, str(exc), phase="governance-hs1")
        log.critical(str(exc))
        sys.exit(1)

    # ── Validate skill selection (existing layer + Hard Stop 1b) ─────────────
    id_errors = validate_skill_id(skill_id, enabled_skills)
    if id_errors:
        msg = "; ".join(id_errors)
        handle_failure(sheets, run_id, skill_id, msg, phase="validation")
        log.error("Validation failed: %s", msg)
        sys.exit(1)

    try:
        governance.enforce_sequential_rotation(skill_id, enabled_skills)
    except HardStopViolation as exc:
        handle_failure(sheets, run_id, skill_id, str(exc), phase="governance-hs1b")
        log.critical(str(exc))
        sys.exit(1)

    skill_name = config.SKILL_NAMES[skill_id - 1]
    log.info("Running Skill %02d: %s", skill_id, skill_name)
    sheets.log_runtime(run_id, "INFO", f"Start — skill {skill_id}: {skill_name}", skill_id)

    # ── Crawl ────────────────────────────────────────────────────────────────
    log.info("Crawling %d pages…", len(config.SITE_PAGES))
    try:
        pages = crawler.crawl_all_pages(delay=0.5)
    except Exception as exc:
        msg = f"Crawl exception: {exc}"
        handle_failure(sheets, run_id, skill_id, msg, phase="crawl")
        sys.exit(1)

    crawl_errors = validate_crawl_results(pages)
    if crawl_errors:
        msg = "; ".join(crawl_errors)
        handle_failure(sheets, run_id, skill_id, msg, phase="crawl-validation")
        log.error("Crawl validation failed: %s", msg)
        sys.exit(1)

    healthy = sum(1 for p in pages if p.get("status") == 200)
    log.info("Crawl complete — %d/%d pages healthy", healthy, len(pages))

    # ── Governance Gate — all 7 Hard Stops in sequence ───────────────────────
    try:
        governance.run_all(
            skill_id=skill_id,
            enabled_skills=enabled_skills,
            site_url=config.SITE_URL,
            pages=pages,
            min_healthy=MIN_HEALTHY_PAGES,
            data_dir=config.DATA_DIR,
            sheets_available=sheets.available,
            github_ref=config.GITHUB_REF,
            enabled_skill_group=config.ENABLED_SKILL_GROUP,
            last_run_date=state.get("last_run_date"),
            is_manual_dispatch=config.IS_MANUAL_DISPATCH,
        )
    except HardStopViolation as exc:
        handle_failure(sheets, run_id, skill_id, str(exc), phase=f"governance-hs{exc.stop_id}")
        log.critical(str(exc))
        sys.exit(1)

    # ── Load skill ───────────────────────────────────────────────────────────
    try:
        from skills import SKILL_REGISTRY
        skill_cls = SKILL_REGISTRY[skill_id]
    except KeyError:
        handle_failure(sheets, run_id, skill_id, f"Skill {skill_id} not in registry", phase="load")
        sys.exit(1)

    # ── Hard Stop 7: enter execution mode (Caveman — suppress verbose context) ─
    governance.enter_execution_mode()

    try:
        result = skill_cls().run(pages)
    except Exception as exc:
        governance.exit_execution_mode()
        msg = f"Skill execution error: {exc}\n{traceback.format_exc()}"
        handle_failure(sheets, run_id, skill_id, msg, phase="execution")
        sys.exit(1)

    # ── Hard Stop 7: exit execution mode — Humaniser (reporting) now active ───
    governance.exit_execution_mode()

    # ── Validate skill output ────────────────────────────────────────────────
    result_errors = validate_skill_result(result)
    if result_errors:
        msg = "; ".join(result_errors)
        handle_failure(sheets, run_id, skill_id, msg, phase="result-validation")
        sys.exit(1)

    duration = int(time.time() - start_time)
    log.info(result.summary_line())
    log.info("Duration: %ds", duration)

    # ── Persist findings ─────────────────────────────────────────────────────
    findings_dicts = result.findings_as_dicts()

    for finding in findings_dicts:
        try:
            issue = memory.upsert_issue(skill_id, finding)
            sheets.append("seo_issues", [
                issue["issue_id"], issue["first_seen"], issue["last_seen"],
                issue["skill_id"], issue["severity"], issue["category"],
                issue["url"], issue["title"][:200], issue["description"][:500],
                issue["status"], issue["occurrences"],
            ])
            if finding.get("severity") == "critical":
                sheets.append("seo_incidents", [
                    str(uuid.uuid4())[:8], datetime.utcnow().isoformat(),
                    "critical", finding.get("category", ""),
                    finding.get("title", "")[:200],
                    finding.get("description", "")[:500],
                    "active", "", run_id,
                ])
        except Exception as e:
            log.warning("Failed to persist finding: %s", e)

    # ── Append run record ────────────────────────────────────────────────────
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
        "notes": f"Group {config.ENABLED_SKILL_GROUP} | skill {skill_id}/23",
    }
    memory.append_run(run_record)
    sheets.append("seo_runs", list(run_record.values()))

    # ── Score history ────────────────────────────────────────────────────────
    memory.append_score(skill_id, skill_name, result.score, run_id)
    scores = memory.load_score_history()
    sheets.append("seo_scores", [
        now.isoformat(), skill_id, skill_name, result.score,
        result.score, 0, config.ENABLED_SKILL_GROUP, run_id,
    ])

    # ── Specialty tracking ───────────────────────────────────────────────────
    if skill_id in (11, 23):
        for f in findings_dicts:
            sheets.append("seo_ai_visibility", [
                now.isoformat(), f.get("title", ""),
                f.get("severity", ""), result.score,
                f.get("description", "")[:300], run_id,
            ])
    if skill_id in (5, 15):
        for rec in result.metadata.get("cwv_records", []):
            for metric, key in [("lcp", "lcp_ms"), ("cls", "cls"), ("ttfb", "ttfb_ms")]:
                sheets.append("seo_cwv", [
                    now.isoformat(), rec.get("url", ""), metric,
                    rec.get(key, 0), "unknown", rec.get("strategy", "mobile"), run_id,
                ])
    if skill_id == 20:
        comp_meta = result.metadata
        for bench, val in [
            ("schema_types_found", len(comp_meta.get("own_schema_types", []))),
            ("blog_pages_count", comp_meta.get("blog_pages", 0)),
        ]:
            sheets.append("seo_competitors", [
                now.isoformat(), "self-benchmark", bench,
                val, val, 0,
                f"Skill 20 self-assessment: {bench}={val}",
                run_id,
            ])

    # ── Report archive ───────────────────────────────────────────────────────
    report_summary = (
        f"Score {result.score}/100 | Issues {len(findings_dicts)} | "
        f"Critical {result.critical_count} | Duration {duration}s"
    )
    sheets.append("seo_reports", [
        str(uuid.uuid4())[:8],
        now.isoformat(),
        skill_id,
        "daily_skill_audit",
        f"Skill {skill_id:02d}/23 — {skill_name}",
        report_summary,
        "",
        run_id,
    ])

    # ── Dashboard snapshot ───────────────────────────────────────────────────
    issues = memory.load_issues()
    snapshot = memory.build_dashboard_snapshot(run_record, findings_dicts, scores, issues)
    log.info("Dashboard snapshot written")

    # ── Build enriched intelligence for reporting ────────────────────────────
    runs_history = memory.load_runs()
    try:
        comparison = memory.get_historical_comparison(runs_history, scores)
        forecast = memory.build_predictive_forecast(scores)
        cycle_progress = memory.get_cycle_progress(runs_history, enabled_skills)
        recurring = memory.detect_recurring_issues(issues)
        log.info(
            "Intelligence: trend=%s 7d-proj=%s cycle=%d/%d recurring=%d",
            forecast.get("trend", "?"),
            forecast.get("projected_score_7d", "?"),
            cycle_progress.get("position", 0),
            cycle_progress.get("total", 23),
            len(recurring),
        )
    except Exception as e:
        log.warning("Intelligence enrichment failed (degraded mode): %s", e)
        comparison, forecast, cycle_progress, recurring = {}, {}, {}, []

    # ── Critical incident alert — send immediately if criticals found ─────────
    if result.critical_count > 0:
        governance.assert_humaniser_scope("emailer.build_critical_incident_alert")
        try:
            alert_html, alert_text = emailer.build_critical_incident_alert(
                run_id, skill_id, findings_dicts
            )
            emailer.send_report(
                f"[SEO CRITICAL] {result.critical_count} critical issue(s) — "
                f"Skill {skill_id} | {skill_name} | {now.strftime('%b %d')}",
                alert_html,
                alert_text,
            )
        except Exception as e:
            log.warning("Critical alert email failed: %s", e)

    # ── Email report — Humaniser layer (post-execution only) ─────────────────
    governance.assert_humaniser_scope("emailer.build_morning_brief")
    html, text = emailer.build_morning_brief(
        run_record, findings_dicts, skill_name, result.score,
        comparison=comparison,
        forecast=forecast,
        cycle_progress=cycle_progress,
        recurring=recurring,
    )
    status_icon = "✓" if result.score >= 80 else "⚠" if result.score >= 50 else "✗"
    subject = (
        f"[SEO {status_icon}] Skill {skill_id:02d}/23 — {skill_name} | "
        f"Score {result.score}/100 | {now.strftime('%b %d')}"
    )
    if result.critical_count > 0:
        subject = f"[SEO CRITICAL] " + subject.lstrip("[SEO ✗] ")
    email_ok = emailer.send_report(subject, html, text)
    sheets.append("seo_emails", [
        now.isoformat(), config.REPORT_EMAIL, subject,
        "sent" if email_ok else "failed",
        "" if email_ok else "Check GMAIL credentials",
        run_id,
    ])

    # ── Save state ───────────────────────────────────────────────────────────
    memory.save_run_state(skill_id, run_id)
    sheets.log_runtime(
        run_id, "INFO",
        f"Complete — score={result.score} issues={len(findings_dicts)} "
        f"crit={result.critical_count} duration={duration}s",
        skill_id,
    )

    log.info("=" * 60)
    log.info("COMPLETE  skill=%02d  score=%d  issues=%d  crit=%d  dur=%ds",
             skill_id, result.score, len(findings_dicts), result.critical_count, duration)
    log.info("=" * 60)


if __name__ == "__main__":
    run()
