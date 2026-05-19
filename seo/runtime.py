#!/usr/bin/env python3
"""
SEO Autonomous Runtime — amulyagupta.in

Execution model:
  - Runs once per day via GitHub Actions (23:00 UTC = 04:30 IST)
  - Executes exactly ONE SEO skill per run from the enabled skill pool
  - Skills rotate sequentially; cycle restarts after all enabled skills complete
  - All site fixes are proposed via PR only — never auto-merged

Safety controls:
  - Runtime validation before every execution
  - Graceful failure handler with operator email alert
  - State preserved on partial failure
  - No direct commits to main; no auto-merge authority
"""

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
import memory
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
          <td style="padding:8px;color:#fca5a5;">{error[:400]}</td></tr>
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

    if not enabled_skills:
        log.error("No skills enabled — set ENABLED_SKILL_GROUP ≥ 1")
        sys.exit(1)

    # ── Init Sheets ──────────────────────────────────────────────────────────
    sheets = SheetsClient()
    if not sheets.available:
        log.warning("Google Sheets unavailable — running without persistence")

    # ── Determine skill ID ───────────────────────────────────────────────────
    override = config.SKILL_OVERRIDE.strip().lower()
    if override and override != "auto" and override.isdigit():
        skill_id = int(override)
        log.info("Skill override active: %d", skill_id)
    else:
        skill_id = memory.get_next_skill(sheets, enabled_skills)
        log.info("Next scheduled skill: %d", skill_id)

    # ── Validate skill selection ─────────────────────────────────────────────
    id_errors = validate_skill_id(skill_id, enabled_skills)
    if id_errors:
        msg = "; ".join(id_errors)
        handle_failure(sheets, run_id, skill_id, msg, phase="validation")
        log.error("Validation failed: %s", msg)
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

    # ── Load and execute skill ───────────────────────────────────────────────
    try:
        from skills import SKILL_REGISTRY
        skill_cls = SKILL_REGISTRY[skill_id]
    except KeyError:
        handle_failure(sheets, run_id, skill_id, f"Skill {skill_id} not in registry", phase="load")
        sys.exit(1)

    try:
        result = skill_cls().run(pages)
    except Exception as exc:
        msg = f"Skill execution error: {exc}\n{traceback.format_exc()}"
        handle_failure(sheets, run_id, skill_id, msg, phase="execution")
        sys.exit(1)

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

    # ── Dashboard snapshot ───────────────────────────────────────────────────
    issues = memory.load_issues()
    memory.build_dashboard_snapshot(run_record, findings_dicts, scores, issues)
    log.info("Dashboard snapshot written")

    # ── Email report ─────────────────────────────────────────────────────────
    html, text = emailer.build_morning_brief(run_record, findings_dicts, skill_name, result.score)
    subject = (
        f"[SEO] Group {config.ENABLED_SKILL_GROUP} | "
        f"Skill {skill_id}/23 — {skill_name} | "
        f"Score {result.score}/100 | {now.strftime('%b %d')}"
    )
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
