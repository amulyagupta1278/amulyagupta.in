import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from config import GMAIL_SENDER, GMAIL_APP_PASSWORD, REPORT_EMAIL, SKILL_NAMES

log = logging.getLogger(__name__)

DASHBOARD_URL = "https://amulyagupta.in/admin/seo/"


def send_report(subject: str, html_body: str, text_body: str = "", attachments: list = None) -> bool:
    if not GMAIL_SENDER or not GMAIL_APP_PASSWORD:
        log.warning("Gmail not configured — email skipped")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_SENDER
    msg["To"] = REPORT_EMAIL
    msg["X-Mailer"] = "SEO Runtime Bot 1.0"

    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    for path in (attachments or []):
        try:
            with open(path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={path.split('/')[-1]}")
            msg.attach(part)
        except Exception as e:
            log.warning("Attachment error: %s", e)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
            smtp.sendmail(GMAIL_SENDER, REPORT_EMAIL, msg.as_string())
        log.info("Email sent: %s → %s", subject, REPORT_EMAIL)
        return True
    except Exception as e:
        log.error("Email send failed: %s", e)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Historical intelligence helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_history():
    try:
        import memory
        return memory.load_runs(), memory.load_score_history(), memory.load_issues()
    except Exception:
        return [], [], {}


def _prev_same_skill(score_history: list, skill_id: int, current_run_id: str) -> dict | None:
    matches = [
        h for h in score_history
        if h.get("skill_id") == skill_id and h.get("run_id") != current_run_id
    ]
    return matches[-1] if matches else None


def _cycle_position(runs: list, enabled_skills: list) -> tuple[int, int]:
    if not enabled_skills:
        return 1, 23
    skill_ids_seen = [r.get("skill_id") for r in runs if r.get("skill_id") in enabled_skills]
    total_cycle = len(enabled_skills)
    if not skill_ids_seen:
        return 1, total_cycle
    last = skill_ids_seen[-1]
    pos = (enabled_skills.index(last) + 1) if last in enabled_skills else 1
    return pos, total_cycle


def _score_trend(score_history: list, window: int = 5) -> str:
    recent = [h["score"] for h in score_history[-window:] if "score" in h]
    if len(recent) < 2:
        return "insufficient data"
    delta = recent[-1] - recent[0]
    if delta >= 5:
        return f"↑ improving (+{delta:.0f} pts over last {len(recent)} runs)"
    if delta <= -5:
        return f"↓ declining ({delta:.0f} pts over last {len(recent)} runs)"
    return f"→ stable ({delta:+.0f} pts over last {len(recent)} runs)"


def _predict_next(score_history: list, skill_id: int) -> str:
    matches = [h for h in score_history if h.get("skill_id") == skill_id and "score" in h]
    if len(matches) < 2:
        return "Not enough history for prediction"
    deltas = [matches[i]["score"] - matches[i - 1]["score"] for i in range(1, len(matches))]
    avg_delta = sum(deltas) / len(deltas)
    last = matches[-1]["score"]
    predicted = max(0, min(100, last + avg_delta))
    direction = "up" if avg_delta > 0 else "down" if avg_delta < 0 else "flat"
    return (
        f"Based on {len(matches)} historical runs, next cycle score likely "
        f"{'improves' if direction == 'up' else 'declines' if direction == 'down' else 'stays flat'} "
        f"to ~{predicted:.0f}/100 (avg Δ {avg_delta:+.1f}/run)"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Morning Brief builder
# ─────────────────────────────────────────────────────────────────────────────

def build_morning_brief(
    run_data: dict,
    findings: list[dict],
    skill_name: str,
    score: int,
) -> tuple[str, str]:
    date_str = datetime.utcnow().strftime("%B %d, %Y")
    utc_time = datetime.utcnow().strftime("%H:%M UTC")
    score_color = "#22c55e" if score >= 80 else "#f59e0b" if score >= 50 else "#ef4444"
    score_label = "GOOD" if score >= 80 else "NEEDS WORK" if score >= 50 else "CRITICAL"

    skill_id = run_data.get("skill_id", 0)
    run_id = run_data.get("run_id", "")
    duration_s = run_data.get("duration_s", 0)

    critical = [f for f in findings if f.get("severity") == "critical"]
    warnings = [f for f in findings if f.get("severity") == "warning"]
    info = [f for f in findings if f.get("severity") == "info"]

    # Historical intelligence
    runs, score_history, issues = _load_history()
    prev = _prev_same_skill(score_history, skill_id, run_id)
    trend = _score_trend(score_history)
    prediction = _predict_next(score_history, skill_id)
    avg_score = (
        sum(h["score"] for h in score_history[-23:]) / len(score_history[-23:])
        if score_history else 0
    )

    # Cycle progress
    try:
        from config import get_enabled_skills
        enabled = get_enabled_skills()
    except Exception:
        enabled = list(range(1, 24))
    cycle_pos, cycle_total = _cycle_position(runs, enabled)
    cycle_pct = int((cycle_pos / cycle_total) * 100)

    # Score delta vs previous same-skill run
    if prev:
        delta = score - prev["score"]
        delta_color = "#22c55e" if delta >= 0 else "#ef4444"
        delta_str = f"{delta:+d}" if delta != 0 else "±0"
        vs_prev_html = (
            f'<span style="color:{delta_color};font-size:14px;font-weight:600;">'
            f'{delta_str} vs. last {skill_name} run</span>'
        )
    else:
        vs_prev_html = '<span style="color:#6b7280;font-size:13px;">First run for this skill</span>'

    # Issues table
    issues_html = ""
    for f in findings[:20]:
        sev = f.get("severity", "info")
        color = {"critical": "#ef4444", "warning": "#f59e0b", "info": "#3b82f6"}.get(sev, "#6b7280")
        issues_html += (
            f'<tr><td style="padding:8px;border-bottom:1px solid #e5e7eb;">'
            f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
            f'background:{color};color:#fff;font-size:11px;font-weight:600;">'
            f'{sev.upper()}</span></td>'
            f'<td style="padding:8px;border-bottom:1px solid #e5e7eb;font-size:13px;">'
            f'{f.get("title", "")}</td>'
            f'<td style="padding:8px;border-bottom:1px solid #e5e7eb;font-size:12px;color:#6b7280;">'
            f'{f.get("url", "—")}</td></tr>'
        )

    # Recommendations
    recs_html = "".join(
        f"<li style='margin:6px 0;font-size:13px;'>{f['recommendation']}</li>"
        for f in findings
        if f.get("recommendation")
    )

    # Active issues count
    active_issues = sum(1 for i in issues.values() if i.get("status") == "active")
    critical_issues = sum(1 for i in issues.values() if i.get("status") == "active" and i.get("severity") == "critical")

    # ── Conditional HTML blocks ───────────────────────────────────────────────
    critical_block = ""
    if critical:
        items = "".join(
            f"<p style='margin:4px 0;font-size:13px;'>&#x26A0; "
            f"<strong>{c.get('title','')}</strong>: {c.get('description','')[:160]}</p>"
            for c in critical
        )
        critical_block = (
            '<div style="background:#fef2f2;border:1px solid #fecaca;border-radius:12px;'
            'padding:20px;margin-bottom:16px;">'
            '<h3 style="margin:0 0 10px;color:#dc2626;font-size:15px;font-weight:700;">'
            "&#x1F6A8; CRITICAL — IMMEDIATE SEO INTERVENTION REQUIRED</h3>"
            + items + "</div>"
        )

    recs_block = ""
    if recs_html:
        recs_block = (
            '<div style="background:#fff;border-radius:12px;padding:24px;margin-bottom:16px;'
            'border:1px solid #e5e7eb;">'
            '<h2 style="margin:0 0 12px;font-size:17px;color:#1e293b;">&#x1F4CC; Recommendations</h2>'
            '<ul style="margin:0;padding-left:20px;">' + recs_html + "</ul></div>"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<div style="max-width:700px;margin:0 auto;padding:24px;">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 100%);border-radius:16px;padding:32px;margin-bottom:20px;">
    <table style="width:100%;"><tr>
      <td>
        <div style="color:#60a5fa;font-size:12px;font-weight:600;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px;">SEO Autonomous Runtime</div>
        <h1 style="color:#fff;margin:0 0 6px;font-size:22px;font-weight:700;">Morning Intelligence Brief</h1>
        <p style="color:#94a3b8;margin:0;font-size:13px;">{date_str} · {utc_time} · amulyagupta.in</p>
      </td>
      <td style="text-align:right;vertical-align:top;">
        <a href="{DASHBOARD_URL}" style="display:inline-block;background:#3b82f6;color:#fff;padding:8px 16px;border-radius:8px;text-decoration:none;font-size:12px;font-weight:600;">View Dashboard</a>
      </td>
    </tr></table>
  </div>

  <!-- Executive Summary Row -->
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px;">
    <div style="background:#fff;border-radius:12px;padding:16px;text-align:center;border:1px solid #e2e8f0;">
      <div style="font-size:36px;font-weight:700;color:{score_color};">{score}</div>
      <div style="font-size:11px;color:#6b7280;margin-top:3px;">Skill Score</div>
      <div style="font-size:10px;font-weight:600;color:{score_color};">{score_label}</div>
    </div>
    <div style="background:#fff;border-radius:12px;padding:16px;text-align:center;border:1px solid #e2e8f0;">
      <div style="font-size:36px;font-weight:700;color:#ef4444;">{len(critical)}</div>
      <div style="font-size:11px;color:#6b7280;margin-top:3px;">Critical</div>
      <div style="font-size:10px;font-weight:600;color:#6b7280;">today</div>
    </div>
    <div style="background:#fff;border-radius:12px;padding:16px;text-align:center;border:1px solid #e2e8f0;">
      <div style="font-size:36px;font-weight:700;color:#f59e0b;">{len(warnings)}</div>
      <div style="font-size:11px;color:#6b7280;margin-top:3px;">Warnings</div>
      <div style="font-size:10px;font-weight:600;color:#6b7280;">today</div>
    </div>
    <div style="background:#fff;border-radius:12px;padding:16px;text-align:center;border:1px solid #e2e8f0;">
      <div style="font-size:36px;font-weight:700;color:#8b5cf6;">{critical_issues}</div>
      <div style="font-size:11px;color:#6b7280;margin-top:3px;">Open Critical</div>
      <div style="font-size:10px;font-weight:600;color:#6b7280;">all-time</div>
    </div>
  </div>

  <!-- Skill Context -->
  <div style="background:#fff;border-radius:12px;padding:20px;margin-bottom:16px;border:1px solid #e2e8f0;">
    <table style="width:100%;"><tr>
      <td>
        <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;">Today's SEO Skill</div>
        <div style="font-size:17px;font-weight:700;color:#0f172a;">#{skill_id} — {skill_name}</div>
        <div style="margin-top:6px;">{vs_prev_html}</div>
      </td>
      <td style="text-align:right;vertical-align:top;">
        <div style="font-size:11px;color:#6b7280;">Duration: {duration_s}s</div>
        <div style="font-size:11px;color:#6b7280;margin-top:2px;">Run: {run_id}</div>
        <div style="font-size:11px;color:#6b7280;margin-top:2px;">Avg score: {avg_score:.0f}/100</div>
      </td>
    </tr></table>

    <!-- 23-day cycle progress bar -->
    <div style="margin-top:16px;">
      <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
        <span style="font-size:12px;color:#6b7280;">23-Day Cycle Progress — Skill {cycle_pos}/{cycle_total}</span>
        <span style="font-size:12px;font-weight:600;color:#0f172a;">{cycle_pct}%</span>
      </div>
      <div style="background:#f1f5f9;border-radius:100px;height:8px;">
        <div style="background:linear-gradient(90deg,#3b82f6,#8b5cf6);height:8px;border-radius:100px;width:{cycle_pct}%;"></div>
      </div>
    </div>
  </div>

  {critical_block}

  <!-- Findings Table -->
  <div style="background:#fff;border-radius:12px;padding:20px;margin-bottom:16px;border:1px solid #e2e8f0;">
    <h2 style="margin:0 0 14px;font-size:16px;color:#0f172a;font-weight:700;">Findings — {len(findings)} total</h2>
    <table style="width:100%;border-collapse:collapse;">
      <thead><tr style="background:#f8fafc;">
        <th style="padding:8px;text-align:left;font-size:11px;color:#6b7280;text-transform:uppercase;">Sev</th>
        <th style="padding:8px;text-align:left;font-size:11px;color:#6b7280;text-transform:uppercase;">Issue</th>
        <th style="padding:8px;text-align:left;font-size:11px;color:#6b7280;text-transform:uppercase;">URL</th>
      </tr></thead>
      <tbody>{issues_html or '<tr><td colspan="3" style="padding:16px;text-align:center;color:#6b7280;font-size:13px;">No issues detected ✓</td></tr>'}</tbody>
    </table>
    {"<p style='margin:8px 0 0;font-size:12px;color:#6b7280;'>… and " + str(len(findings) - 20) + " more. View full list in the dashboard.</p>" if len(findings) > 20 else ""}
  </div>

  {recs_block}

  <!-- Historical Comparison -->
  <div style="background:#fff;border-radius:12px;padding:20px;margin-bottom:16px;border:1px solid #e2e8f0;">
    <h2 style="margin:0 0 14px;font-size:16px;color:#0f172a;font-weight:700;">&#x1F4CA; Historical Comparison</h2>
    <table style="width:100%;font-size:13px;">
      <tr style="border-bottom:1px solid #f1f5f9;">
        <td style="padding:8px 4px;color:#6b7280;width:180px;">Score trend (all skills)</td>
        <td style="padding:8px 4px;color:#0f172a;font-weight:500;">{trend}</td>
      </tr>
      <tr style="border-bottom:1px solid #f1f5f9;">
        <td style="padding:8px 4px;color:#6b7280;">Lifetime avg score</td>
        <td style="padding:8px 4px;color:#0f172a;font-weight:500;">{avg_score:.1f}/100</td>
      </tr>
      <tr style="border-bottom:1px solid #f1f5f9;">
        <td style="padding:8px 4px;color:#6b7280;">Total runs completed</td>
        <td style="padding:8px 4px;color:#0f172a;font-weight:500;">{len(runs)}</td>
      </tr>
      <tr>
        <td style="padding:8px 4px;color:#6b7280;">Open issues (all time)</td>
        <td style="padding:8px 4px;color:#0f172a;font-weight:500;">{active_issues} active / {len(issues)} total</td>
      </tr>
    </table>
  </div>

  <!-- Predictive Forecasting -->
  <div style="background:linear-gradient(135deg,#eff6ff,#f5f3ff);border:1px solid #ddd6fe;border-radius:12px;padding:20px;margin-bottom:16px;">
    <h2 style="margin:0 0 10px;font-size:16px;color:#4c1d95;font-weight:700;">&#x1F52E; Predictive SEO Forecast</h2>
    <p style="margin:0;font-size:13px;color:#3730a3;line-height:1.6;">{prediction}</p>
  </div>

  <!-- Footer -->
  <div style="text-align:center;padding:16px 0;color:#94a3b8;font-size:11px;">
    SEO Runtime Bot · amulyagupta.in · Auto-generated · Do not reply ·
    <a href="{DASHBOARD_URL}" style="color:#3b82f6;text-decoration:none;">View full dashboard</a>
  </div>

</div>
</body></html>"""

    text = (
        f"SEO Runtime — Morning Brief\n"
        f"{date_str} {utc_time}\n"
        f"{'=' * 50}\n\n"
        f"Skill #{skill_id}: {skill_name}\n"
        f"Score: {score}/100 ({score_label})\n"
        f"Cycle: {cycle_pos}/{cycle_total}\n\n"
        f"Critical: {len(critical)} | Warnings: {len(warnings)} | Info: {len(info)}\n"
        f"Open issues (all-time): {active_issues} active\n\n"
        f"Trend: {trend}\n"
        f"Avg score: {avg_score:.1f}/100\n\n"
        f"Forecast: {prediction}\n\n"
        f"Findings:\n"
        + "\n".join(
            f"  [{f.get('severity', '').upper()}] {f.get('title', '')} — {f.get('url', '')}"
            for f in findings[:15]
        )
        + f"\n\nDashboard: {DASHBOARD_URL}\n"
    )

    return html, text
