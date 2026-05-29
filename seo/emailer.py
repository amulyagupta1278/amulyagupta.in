import smtplib
import logging
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from config import GMAIL_SENDER, GMAIL_APP_PASSWORD, REPORT_EMAIL, SKILL_NAMES

log = logging.getLogger(__name__)

_SCORE_COLOR = {
    "good": "#22c55e",
    "warn": "#f59e0b",
    "bad": "#ef4444",
}

_BASE_STYLES = """
<style>
  body { margin:0; padding:0; background:#f1f5f9;
         font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }
  .wrap { max-width:700px; margin:0 auto; padding:24px; }
  .header { background:linear-gradient(135deg,#0f172a,#1e3a5f); border-radius:14px;
             padding:32px; margin-bottom:20px; }
  .header h1 { color:#fff; margin:0 0 6px; font-size:22px; font-weight:700; }
  .header p  { color:#94a3b8; margin:0; font-size:13px; }
  .card { background:#fff; border:1px solid #e2e8f0; border-radius:12px;
           padding:22px; margin-bottom:16px; }
  .card-title { font-size:13px; font-weight:700; text-transform:uppercase;
                letter-spacing:.6px; color:#64748b; margin-bottom:14px; }
  .kpi-row { display:flex; gap:12px; flex-wrap:wrap; }
  .kpi { flex:1; min-width:110px; background:#f8fafc; border-radius:10px;
          padding:14px; text-align:center; }
  .kpi-val { font-size:32px; font-weight:700; line-height:1; }
  .kpi-lbl { font-size:11px; color:#64748b; margin-top:4px; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th { text-align:left; padding:8px 10px; font-size:11px; font-weight:600;
       text-transform:uppercase; color:#64748b; border-bottom:2px solid #e2e8f0; }
  td { padding:9px 10px; border-bottom:1px solid #f1f5f9; vertical-align:middle; }
  .badge { display:inline-block; padding:2px 8px; border-radius:4px;
            font-size:10px; font-weight:700; letter-spacing:.3px; }
  .badge-crit { background:#fee2e2; color:#dc2626; }
  .badge-warn { background:#fef9c3; color:#b45309; }
  .badge-info { background:#dbeafe; color:#1d4ed8; }
  .badge-good { background:#dcfce7; color:#15803d; }
  .section-divider { border:none; border-top:1px solid #e2e8f0; margin:20px 0; }
  .critical-block { background:#fef2f2; border:1px solid #fecaca; border-radius:12px;
                     padding:18px; margin-bottom:16px; }
  .critical-block h3 { color:#dc2626; margin:0 0 10px; font-size:14px; }
  .forecast-block { background:#f0f9ff; border:1px solid #bae6fd; border-radius:12px;
                     padding:18px; margin-bottom:16px; }
  .trend-up { color:#15803d; font-weight:600; }
  .trend-down { color:#dc2626; font-weight:600; }
  .trend-flat { color:#b45309; font-weight:600; }
  .footer { text-align:center; padding:16px; color:#94a3b8; font-size:11px; }
  a { color:#0284c7; text-decoration:none; }
</style>
"""


def _score_color(score: int) -> str:
    return _SCORE_COLOR["good"] if score >= 80 else _SCORE_COLOR["warn"] if score >= 50 else _SCORE_COLOR["bad"]


def _score_label(score: int) -> str:
    return "GOOD" if score >= 80 else "NEEDS WORK" if score >= 50 else "CRITICAL"


def send_report(
    subject: str,
    html_body: str,
    text_body: str = "",
    attachments: list = None,
) -> bool:
    if not GMAIL_SENDER or not GMAIL_APP_PASSWORD:
        log.warning("Gmail not configured — email skipped")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_SENDER
    msg["To"] = REPORT_EMAIL
    msg["X-Mailer"] = "SEO Runtime Bot 2.0"

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

    for attempt in range(3):
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
                smtp.sendmail(GMAIL_SENDER, REPORT_EMAIL, msg.as_string())
            log.info("Email sent: %s → %s", subject, REPORT_EMAIL)
            return True
        except Exception as e:
            log.warning("Email attempt %d failed: %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(2 ** attempt)  # 1s, 2s

    log.error("Email delivery failed after 3 attempts")
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Section builders
# ─────────────────────────────────────────────────────────────────────────────

def _build_findings_table(findings: list, max_rows: int = 25) -> str:
    rows = ""
    for f in findings[:max_rows]:
        sev = f.get("severity", "info")
        badge_cls = {"critical": "badge-crit", "warning": "badge-warn", "info": "badge-info"}.get(sev, "badge-info")
        url_short = (f.get("url") or "—").replace("https://amulyagupta.in", "")
        rec = f.get("recommendation", "")
        rec_html = f'<div style="font-size:11px;color:#64748b;margin-top:3px">{rec[:120]}…</div>' if rec else ""
        rows += f"""<tr>
          <td><span class="badge {badge_cls}">{sev.upper()}</span></td>
          <td style="max-width:280px;word-break:break-word">
            {f.get('title', '')}
            {rec_html}
          </td>
          <td><code style="font-size:11px;background:#f8fafc;padding:1px 4px;border-radius:3px">{url_short or '/'}</code></td>
        </tr>"""
    return f"""<table>
      <thead><tr>
        <th>Severity</th><th>Issue &amp; Fix</th><th>URL</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>"""


def _build_historical_comparison_section(comparison: dict) -> str:
    if not comparison or comparison.get("prev_score") is None:
        return """<div class="card">
          <div class="card-title">Historical Comparison</div>
          <p style="color:#64748b;font-size:13px">No previous run of this skill found yet.
          Comparison data will appear after the second full 23-day cycle.</p>
        </div>"""

    delta = comparison.get("score_delta", 0)
    delta_color = "#15803d" if delta > 0 else "#dc2626" if delta < 0 else "#b45309"
    delta_arrow = "&#x2191;" if delta > 0 else "&#x2193;" if delta < 0 else "&#x2192;"
    issue_delta = comparison.get("issue_delta", 0)
    i_arrow = "&#x2193;" if issue_delta < 0 else "&#x2191;" if issue_delta > 0 else "&#x2192;"
    i_color = "#15803d" if issue_delta < 0 else "#dc2626" if issue_delta > 0 else "#b45309"

    trend_map = {"improving": "trend-up", "declining": "trend-down", "stable": "trend-flat"}
    trend_cls = trend_map.get(comparison.get("trend_direction", "stable"), "trend-flat")

    wow = comparison.get("week_over_week_delta")
    wow_html = ""
    if wow is not None:
        wow_color = "#15803d" if wow > 0 else "#dc2626" if wow < 0 else "#b45309"
        wow_html = f'<tr><td style="color:#64748b">Week-over-week avg</td><td style="font-weight:600;color:{wow_color}">{wow:+.1f} pts</td></tr>'

    prev_date = comparison.get("prev_run_date", "")
    prev_date_str = ""
    if prev_date:
        try:
            prev_date_str = datetime.fromisoformat(prev_date).strftime("%b %d, %Y")
        except Exception:
            prev_date_str = prev_date[:10]

    return f"""<div class="card">
      <div class="card-title">Historical Comparison — Skill {comparison.get('current_skill_id')}</div>
      <table style="margin-bottom:12px">
        <tr>
          <td style="color:#64748b;width:200px">Previous run score</td>
          <td style="font-weight:600">{comparison.get('prev_score', '—')}/100
            <span style="color:#94a3b8;font-size:11px">({prev_date_str})</span></td>
        </tr>
        <tr>
          <td style="color:#64748b">Current run score</td>
          <td style="font-weight:600;color:{delta_color}">{comparison.get('current_score', 0)}/100
            <span style="font-size:12px">{delta_arrow} {abs(delta)} pts</span></td>
        </tr>
        <tr>
          <td style="color:#64748b">Issues found</td>
          <td style="font-weight:600;color:{i_color}">{comparison.get('current_issues_found', 0)}
            <span style="font-size:12px">{i_arrow} {abs(issue_delta)} vs last run</span></td>
        </tr>
        {wow_html}
        <tr>
          <td style="color:#64748b">Skill trend</td>
          <td><span class="{trend_cls}">{comparison.get('trend_direction', 'stable').upper()}</span>
            — scores: {" → ".join(str(s) for s in comparison.get('skill_trend', []))}</td>
        </tr>
      </table>
    </div>"""


def _build_predictive_forecast_section(forecast: dict) -> str:
    trend = forecast.get("trend") if forecast else None

    # Not enough data or still in the first cycle — show factual cycle info only
    if not forecast or trend in ("insufficient_data", "first_cycle_in_progress"):
        cycle_status = (forecast or {}).get("cycle_status", "")
        cycle_msg = (
            f"<br><span style='color:#0369a1;font-weight:600'>{cycle_status}</span>"
            if cycle_status else ""
        )
        lowest = (forecast or {}).get("lowest_scoring_skills", [])
        lowest_html = ""
        if lowest:
            from config import SKILL_NAMES as _NAMES
            items = [
                f"<li style='margin:3px 0;font-size:12px'>"
                f"{_NAMES[int(sid) - 1] if 1 <= int(sid) <= 23 else f'Skill {sid}'}: "
                f"<strong style='color:#dc2626'>{sc}/100</strong></li>"
                for sid, sc in lowest
            ]
            lowest_html = (
                "<p style='font-weight:600;font-size:12px;color:#0369a1;margin:10px 0 4px'>"
                "Priority skills to improve:</p>"
                f"<ul style='margin:0;padding-left:18px'>{''.join(items)}</ul>"
            )
        return f"""<div class="forecast-block">
          <div class="card-title" style="color:#0369a1">SEO Forecast</div>
          <p style="color:#0c4a6e;font-size:13px">
            Trend analysis requires the same skill to be audited at least twice (cycle 2+).
            Cross-skill score comparisons are not a valid trend signal.{cycle_msg}
          </p>
          {lowest_html}
        </div>"""

    trend_map = {"improving": "trend-up", "declining": "trend-down", "stable": "trend-flat"}
    trend_cls = trend_map.get(trend, "trend-flat")

    p7 = forecast.get("projected_score_7d")
    p30 = forecast.get("projected_score_30d")
    momentum = forecast.get("momentum", "neutral")
    risk = forecast.get("risk_level", "unknown")
    risk_color = "#15803d" if risk == "low" else "#b45309" if risk == "medium" else "#dc2626"

    lowest = forecast.get("lowest_scoring_skills", [])
    lowest_html = ""
    if lowest:
        from config import SKILL_NAMES as _NAMES
        items = [
            f"<li style='margin:3px 0;font-size:12px'>"
            f"{_NAMES[int(sid) - 1] if 1 <= int(sid) <= 23 else f'Skill {sid}'}: "
            f"<strong style='color:#dc2626'>{sc}/100</strong></li>"
            for sid, sc in lowest
        ]
        lowest_html = f"<ul style='margin:8px 0 0;padding-left:18px'>{''.join(items)}</ul>"

    avg_delta = forecast.get("avg_delta_per_cycle", 0)

    return f"""<div class="forecast-block">
      <div class="card-title" style="color:#0369a1">Predictive SEO Forecast
        <span style="font-weight:400;color:#64748b;font-size:11px">
          ({forecast.get('confidence','').upper()} confidence · {forecast.get('data_points',0)} data points)
        </span>
      </div>
      <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:14px">
        <div style="flex:1;min-width:120px;background:#fff;border-radius:8px;padding:14px;text-align:center;border:1px solid #bae6fd">
          <div style="font-size:28px;font-weight:700;color:{_score_color(p7 or 0)}">{p7 if p7 is not None else '—'}</div>
          <div style="font-size:11px;color:#64748b">7-day projection</div>
        </div>
        <div style="flex:1;min-width:120px;background:#fff;border-radius:8px;padding:14px;text-align:center;border:1px solid #bae6fd">
          <div style="font-size:28px;font-weight:700;color:{_score_color(p30 or 0)}">{p30 if p30 is not None else '—'}</div>
          <div style="font-size:11px;color:#64748b">30-day projection</div>
        </div>
        <div style="flex:1;min-width:120px;background:#fff;border-radius:8px;padding:14px;text-align:center;border:1px solid #bae6fd">
          <div style="font-size:18px;font-weight:700"><span class="{trend_cls}">{trend.upper()}</span></div>
          <div style="font-size:11px;color:#64748b">Overall trend</div>
        </div>
        <div style="flex:1;min-width:120px;background:#fff;border-radius:8px;padding:14px;text-align:center;border:1px solid #bae6fd">
          <div style="font-size:18px;font-weight:700;color:{risk_color}">{risk.upper()}</div>
          <div style="font-size:11px;color:#64748b">Risk level</div>
        </div>
      </div>
      <table>
        <tr><td style="color:#64748b;width:160px">Avg change/cycle</td>
            <td style="font-weight:600">{avg_delta:+.2f} pts/cycle &nbsp;·&nbsp; {forecast.get('slope_per_day',0):+.3f} pts/day</td></tr>
        <tr><td style="color:#64748b">Momentum</td>
            <td>{momentum.title()}</td></tr>
      </table>
      {f'<div style="margin-top:10px"><strong style="font-size:12px;color:#0369a1">Lowest-scoring skills (priority targets):</strong>{lowest_html}</div>' if lowest_html else ""}
    </div>"""


def _build_ai_visibility_section(findings: list, skill_id: int) -> str:
    ai_findings = [f for f in findings if f.get("category") in ("ai-seo", "ai-crawlers", "entity")]
    if skill_id not in (11, 23) and not ai_findings:
        return ""

    items = ""
    for f in ai_findings[:10]:
        sev = f.get("severity", "info")
        badge_cls = {"critical": "badge-crit", "warning": "badge-warn", "info": "badge-info"}.get(sev, "badge-info")
        items += f"""<tr>
          <td><span class="badge {badge_cls}">{sev.upper()}</span></td>
          <td style="font-size:13px">{f.get('title','')}</td>
          <td style="font-size:11px;color:#64748b">{(f.get('recommendation',''))[:100]}</td>
        </tr>"""

    if not items:
        items = '<tr><td colspan="3" style="color:#64748b;font-style:italic">No AI-specific issues detected.</td></tr>'

    return f"""<div class="card">
      <div class="card-title">AI Search Visibility — AI Overview / ChatGPT / Perplexity</div>
      <table>
        <thead><tr><th>Status</th><th>Signal</th><th>Recommendation</th></tr></thead>
        <tbody>{items}</tbody>
      </table>
    </div>"""


def _build_cycle_progress_section(cycle_progress: dict) -> str:
    pos = cycle_progress.get("position", 0)
    total = cycle_progress.get("total", 23)
    pct = cycle_progress.get("percent", 0)
    cycle = cycle_progress.get("cycle", 1)
    next_skill = cycle_progress.get("next_skill_id")
    next_name = SKILL_NAMES[next_skill - 1] if next_skill and 1 <= next_skill <= 23 else "—"

    bar_filled = round(pct / 100 * 20)
    bar = "█" * bar_filled + "░" * (20 - bar_filled)

    return f"""<div class="card">
      <div class="card-title">23-Day SEO Skill Cycle — Cycle #{cycle}</div>
      <div style="font-family:monospace;font-size:14px;letter-spacing:1px;
                  color:#0284c7;margin-bottom:10px">[{bar}] {pct}%</div>
      <table>
        <tr><td style="color:#64748b;width:180px">Cycle position</td>
            <td style="font-weight:600">Skill {pos}/{total}</td></tr>
        <tr><td style="color:#64748b">Current cycle #</td>
            <td style="font-weight:600">{cycle}</td></tr>
        <tr><td style="color:#64748b">Skills completed</td>
            <td>{cycle_progress.get('skills_completed_this_cycle', 0)} this cycle</td></tr>
        <tr><td style="color:#64748b">Next skill</td>
            <td>#{next_skill} — {next_name}</td></tr>
      </table>
    </div>"""


def _build_recurring_issues_section(recurring: list) -> str:
    if not recurring:
        return ""

    rows = ""
    for issue in recurring[:8]:
        sev = issue.get("severity", "info")
        badge_cls = {"critical": "badge-crit", "warning": "badge-warn", "info": "badge-info"}.get(sev, "badge-info")
        rows += f"""<tr>
          <td><span class="badge {badge_cls}">{sev.upper()}</span></td>
          <td style="font-size:13px">{issue.get('title','')}</td>
          <td style="text-align:center;font-weight:600;color:#dc2626">{issue.get('occurrences',0)}</td>
          <td style="font-size:11px;color:#64748b">{(issue.get('first_seen',''))[:10]}</td>
        </tr>"""

    return f"""<div class="card" style="border-left:3px solid #f59e0b">
      <div class="card-title">Recurring Issues — Persistent SEO Debt ({len(recurring)} issues)</div>
      <p style="font-size:12px;color:#64748b;margin-bottom:12px">
        These issues have appeared in 3+ consecutive runs and require immediate resolution.
      </p>
      <table>
        <thead><tr><th>Severity</th><th>Issue</th><th>Seen</th><th>Since</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""


# ─────────────────────────────────────────────────────────────────────────────
# Morning Brief — primary daily email
# ─────────────────────────────────────────────────────────────────────────────

def build_morning_brief(
    run_data: dict,
    findings: list[dict],
    skill_name: str,
    score: int,
    comparison: dict = None,
    forecast: dict = None,
    cycle_progress: dict = None,
    recurring: list = None,
) -> tuple[str, str]:
    date_str = datetime.utcnow().strftime("%A, %B %d, %Y")
    run_id = run_data.get("run_id", "—")
    skill_id = run_data.get("skill_id", 0)
    duration = run_data.get("duration_s", 0)

    critical = [f for f in findings if f.get("severity") == "critical"]
    warnings = [f for f in findings if f.get("severity") == "warning"]
    info = [f for f in findings if f.get("severity") == "info"]

    # Critical alert block
    critical_block = ""
    if critical:
        items_html = "".join(
            f"<p style='margin:4px 0;font-size:13px;color:#fca5a5'>• {c.get('title','')} "
            f"<span style='font-size:11px'>({c.get('url','').replace('https://amulyagupta.in','')})</span></p>"
            for c in critical
        )
        critical_block = f"""<div class="critical-block">
          <h3>&#x26A0; CRITICAL — IMMEDIATE SEO INTERVENTION REQUIRED</h3>
          {items_html}
        </div>"""

    # Historical comparison section
    comparison_html = _build_historical_comparison_section(comparison or {})

    # Predictive forecast section
    forecast_html = _build_predictive_forecast_section(forecast or {})

    # AI visibility section
    ai_html = _build_ai_visibility_section(findings, skill_id)

    # Cycle progress section
    cycle_html = _build_cycle_progress_section(cycle_progress or {"position": 0, "total": 23, "percent": 0, "cycle": 1})

    # Recurring issues section
    recurring_html = _build_recurring_issues_section(recurring or [])

    # Findings table
    findings_html = _build_findings_table(findings, max_rows=25)

    # Recommendations list
    recs = [f["recommendation"] for f in findings if f.get("recommendation")]
    recs_html = ""
    if recs:
        items = "".join(f"<li style='margin:5px 0;font-size:13px'>{r}</li>" for r in recs[:10])
        recs_html = f"""<div class="card">
          <div class="card-title">Strategic Recommendations</div>
          <ul style="margin:0;padding-left:20px">{items}</ul>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">{_BASE_STYLES}</head>
<body><div class="wrap">

  <div class="header">
    <h1>SEO Runtime — Daily Intelligence Brief</h1>
    <p>{date_str} &nbsp;·&nbsp; amulyagupta.in &nbsp;·&nbsp; Run ID: {run_id} &nbsp;·&nbsp; {duration}s</p>
  </div>

  <!-- Executive KPIs -->
  <div class="card">
    <div class="card-title">Today's Skill: {skill_id:02d}/23 — {skill_name}</div>
    <div class="kpi-row">
      <div class="kpi">
        <div class="kpi-val" style="color:{_score_color(score)}">{score}</div>
        <div class="kpi-lbl">SEO Score<br><strong>{_score_label(score)}</strong></div>
      </div>
      <div class="kpi">
        <div class="kpi-val" style="color:#dc2626">{len(critical)}</div>
        <div class="kpi-lbl">Critical<br>Issues</div>
      </div>
      <div class="kpi">
        <div class="kpi-val" style="color:#d97706">{len(warnings)}</div>
        <div class="kpi-lbl">Warnings</div>
      </div>
      <div class="kpi">
        <div class="kpi-val" style="color:#0284c7">{len(info)}</div>
        <div class="kpi-lbl">Info</div>
      </div>
      <div class="kpi">
        <div class="kpi-val" style="color:#64748b">{len(findings)}</div>
        <div class="kpi-lbl">Total<br>Findings</div>
      </div>
    </div>
  </div>

  {critical_block}

  <!-- Historical Comparison -->
  {comparison_html}

  <!-- Cycle Progress -->
  {cycle_html}

  <!-- Findings Table -->
  <div class="card">
    <div class="card-title">Findings — All {len(findings)} Issues Detected</div>
    {findings_html}
  </div>

  <!-- Recurring Issues -->
  {recurring_html}

  <!-- AI Search Visibility -->
  {ai_html}

  <!-- Predictive Forecast -->
  {forecast_html}

  <!-- Recommendations -->
  {recs_html}

  <div class="footer">
    SEO Runtime Bot 2.0 &nbsp;·&nbsp; amulyagupta.in &nbsp;·&nbsp;
    <a href="https://amulyagupta.in/admin/seo/">Dashboard</a> &nbsp;·&nbsp;
    Automated Report — Do Not Reply
  </div>
</div></body></html>"""

    text = (
        f"SEO Runtime — Daily Intelligence Brief\n"
        f"{date_str}\n"
        f"{'='*60}\n\n"
        f"Skill {skill_id:02d}/23 — {skill_name}\n"
        f"Score: {score}/100 ({_score_label(score)})\n"
        f"Critical: {len(critical)} | Warnings: {len(warnings)} | Info: {len(info)}\n\n"
    )
    if critical:
        text += "CRITICAL ISSUES:\n"
        for c in critical:
            text += f"  • {c.get('title','')} — {c.get('url','')}\n"
        text += "\n"
    text += "ALL FINDINGS:\n"
    for f in findings[:20]:
        text += f"  [{f.get('severity','').upper()}] {f.get('title','')} — {f.get('url','')}\n"
    if forecast:
        trend_val = forecast.get("trend", "?")
        # Only show projections for actionable trends — cycle 1 has no valid projections
        if trend_val not in ("insufficient_data", "first_cycle_in_progress"):
            p7 = forecast.get("projected_score_7d")
            p30 = forecast.get("projected_score_30d")
            text += (
                f"\nFORECAST:\n"
                f"  Trend: {trend_val.upper()}\n"
                f"  7-day projection: {p7 if p7 is not None else 'N/A'}/100\n"
                f"  30-day projection: {p30 if p30 is not None else 'N/A'}/100\n"
            )
        else:
            cycle_status = forecast.get("cycle_status", "Cycle 1 in progress")
            text += f"\nFORECAST: {cycle_status} — projections available in cycle 2+\n"

    return html, text


# ─────────────────────────────────────────────────────────────────────────────
# Weekly Summary Email
# ─────────────────────────────────────────────────────────────────────────────

def build_weekly_summary(
    runs: list,
    issues: dict,
    scores: list,
    forecast: dict,
    comparison: dict,
    recurring: list,
) -> tuple[str, str]:
    import memory
    summary = memory.build_weekly_summary_data(runs, scores, issues)

    date_str = datetime.utcnow().strftime("%B %d, %Y")
    period = f"{summary.get('period_start','')} – {summary.get('period_end','')}"
    avg = summary.get("avg_score_this_week", 0)
    prev_avg = summary.get("avg_score_prev_week", 0)
    delta = summary.get("score_delta", 0)
    delta_color = "#15803d" if delta > 0 else "#dc2626" if delta < 0 else "#b45309"
    delta_str = f"+{delta}" if delta > 0 else str(delta)

    # Skills run this week table
    skills_html = ""
    for s in summary.get("skills_run", []):
        sc = s.get("score", 0)
        skills_html += f"""<tr>
          <td>#{s.get('skill_id')}</td>
          <td>{s.get('skill_name','')}</td>
          <td style="font-weight:600;color:{_score_color(sc)}">{sc}/100</td>
        </tr>"""

    if not skills_html:
        skills_html = '<tr><td colspan="3" style="color:#64748b">No runs this week</td></tr>'

    # Improvements
    impr_html = ""
    for name, d in summary.get("top_improvements", []):
        impr_html += f"<li style='color:#15803d;margin:3px 0'><strong>{name}:</strong> +{d} pts</li>"

    # Regressions
    regr_html = ""
    for name, d in summary.get("regressions", []):
        regr_html += f"<li style='color:#dc2626;margin:3px 0'><strong>{name}:</strong> {d} pts</li>"

    # Critical issues
    crit_html = ""
    for issue in summary.get("critical_issue_list", []):
        crit_html += f"<p style='margin:4px 0;font-size:13px;color:#fca5a5'>• {issue.get('title','')}</p>"

    critical_block = ""
    if crit_html:
        critical_block = f"""<div class="critical-block">
          <h3>&#x26A0; CRITICAL — IMMEDIATE SEO INTERVENTION REQUIRED</h3>
          {crit_html}
        </div>"""

    forecast_html = _build_predictive_forecast_section(forecast)
    recurring_html = _build_recurring_issues_section(recurring)

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">{_BASE_STYLES}</head>
<body><div class="wrap">

  <div class="header">
    <h1>SEO Weekly Intelligence Summary</h1>
    <p>{date_str} &nbsp;·&nbsp; amulyagupta.in &nbsp;·&nbsp; Period: {period}</p>
  </div>

  <!-- Weekly KPIs -->
  <div class="card">
    <div class="card-title">Weekly Performance Overview</div>
    <div class="kpi-row">
      <div class="kpi">
        <div class="kpi-val" style="color:{_score_color(int(avg))}">{avg}</div>
        <div class="kpi-lbl">Avg Score<br>This Week</div>
      </div>
      <div class="kpi">
        <div class="kpi-val" style="color:{delta_color}">{delta_str}</div>
        <div class="kpi-lbl">vs Last Week<br>({prev_avg} prev)</div>
      </div>
      <div class="kpi">
        <div class="kpi-val" style="color:#0284c7">{summary.get('runs_this_week',0)}</div>
        <div class="kpi-lbl">Skills Run<br>This Week</div>
      </div>
      <div class="kpi">
        <div class="kpi-val" style="color:#dc2626">{summary.get('critical_issues',0)}</div>
        <div class="kpi-lbl">Critical<br>Issues</div>
      </div>
      <div class="kpi">
        <div class="kpi-val" style="color:#d97706">{summary.get('recurring_issues',0)}</div>
        <div class="kpi-lbl">Recurring<br>Issues</div>
      </div>
      <div class="kpi">
        <div class="kpi-val" style="color:#64748b">{summary.get('new_issues_this_week',0)}</div>
        <div class="kpi-lbl">New Issues<br>This Week</div>
      </div>
    </div>
  </div>

  {critical_block}

  <!-- Skills run this week -->
  <div class="card">
    <div class="card-title">Skills Executed This Week</div>
    <table>
      <thead><tr><th>#</th><th>Skill</th><th>Score</th></tr></thead>
      <tbody>{skills_html}</tbody>
    </table>
  </div>

  <!-- Improvements & regressions -->
  <div class="card">
    <div class="card-title">Week-over-Week Changes</div>
    <div style="display:flex;gap:24px;flex-wrap:wrap">
      <div style="flex:1;min-width:200px">
        <strong style="color:#15803d">Improvements</strong>
        <ul style="margin:8px 0 0;padding-left:18px">
          {impr_html or '<li style="color:#64748b">None recorded</li>'}
        </ul>
      </div>
      <div style="flex:1;min-width:200px">
        <strong style="color:#dc2626">Regressions</strong>
        <ul style="margin:8px 0 0;padding-left:18px">
          {regr_html or '<li style="color:#64748b">None recorded</li>'}
        </ul>
      </div>
    </div>
  </div>

  <!-- Recurring issues -->
  {recurring_html}

  <!-- Predictive Forecast -->
  {forecast_html}

  <div class="footer">
    SEO Runtime Bot 2.0 &nbsp;·&nbsp; amulyagupta.in &nbsp;·&nbsp; Weekly Summary
  </div>
</div></body></html>"""

    text = (
        f"SEO Weekly Intelligence Summary\n"
        f"Period: {period}\n"
        f"{'='*60}\n\n"
        f"Avg Score This Week: {avg}/100 (vs {prev_avg} last week, {delta_str})\n"
        f"Skills Run: {summary.get('runs_this_week',0)}\n"
        f"Critical Issues: {summary.get('critical_issues',0)}\n"
        f"Recurring Issues: {summary.get('recurring_issues',0)}\n\n"
        f"Forecast Trend: {forecast.get('trend','?').upper() if forecast else 'N/A'}\n"
    )

    return html, text


# ─────────────────────────────────────────────────────────────────────────────
# Critical Incident Alert
# ─────────────────────────────────────────────────────────────────────────────

def build_critical_incident_alert(run_id: str, skill_id: int, findings: list) -> tuple[str, str]:
    date_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    skill_name = SKILL_NAMES[skill_id - 1] if 1 <= skill_id <= 23 else f"Skill {skill_id}"
    critical = [f for f in findings if f.get("severity") == "critical"]

    items_html = "".join(
        f"""<tr>
          <td style="padding:8px;border-bottom:1px solid #fee2e2">
            {f.get('title','')}
          </td>
          <td style="padding:8px;border-bottom:1px solid #fee2e2;font-size:11px;color:#6b7280">
            {f.get('url','').replace('https://amulyagupta.in','')}
          </td>
        </tr>"""
        for f in critical
    )

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">{_BASE_STYLES}</head>
<body><div class="wrap">
  <div class="header" style="background:linear-gradient(135deg,#7f1d1d,#991b1b)">
    <h1>&#x26A0; CRITICAL SEO INCIDENT ALERT</h1>
    <p>{date_str} &nbsp;·&nbsp; Skill #{skill_id} — {skill_name} &nbsp;·&nbsp; Run: {run_id}</p>
  </div>
  <div class="critical-block">
    <h3>CRITICAL — IMMEDIATE SEO INTERVENTION REQUIRED</h3>
    <p style="font-size:13px;color:#fca5a5;margin-bottom:12px">
      {len(critical)} critical issue(s) detected requiring immediate action.
      No site changes have been made — the runtime operates in read-only mode.
    </p>
    <table style="width:100%"><thead>
      <tr><th style="color:#fca5a5">Issue</th><th style="color:#fca5a5">URL</th></tr>
    </thead><tbody>{items_html}</tbody></table>
  </div>
  <div class="card">
    <div class="card-title">Next Steps</div>
    <ol style="font-size:13px;line-height:1.8">
      <li>Review the full audit in the SEO Dashboard</li>
      <li>Prioritize resolution of critical issues above</li>
      <li>The runtime will generate a PR with proposed fixes (human review required)</li>
      <li>Check Google Search Console for crawl errors</li>
    </ol>
  </div>
  <div class="footer">SEO Runtime Bot 2.0 · amulyagupta.in · Critical Alert</div>
</div></body></html>"""

    text = (
        f"CRITICAL SEO INCIDENT ALERT\n{date_str}\n"
        f"Skill #{skill_id} — {skill_name}\n{'='*50}\n\n"
        f"{len(critical)} CRITICAL ISSUES:\n"
        + "".join(f"  • {f.get('title','')} — {f.get('url','')}\n" for f in critical)
    )

    return html, text


# ─────────────────────────────────────────────────────────────────────────────
# Cycle Completion Report
# ─────────────────────────────────────────────────────────────────────────────

def build_cycle_completion_email(
    cycle_number: int,
    runs: list,
    scores: list,
    issues: dict,
) -> tuple[str, str]:
    """Full 23-skill cycle summary sent when Skill 23 completes."""
    date_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # ── Aggregate cycle stats ─────────────────────────────────────────────────
    cycle_runs = [r for r in runs if r.get("cycle") == cycle_number]
    cycle_scores = [s for s in scores if s.get("cycle") == cycle_number]

    total_runs = len(cycle_runs)
    avg_score = round(
        sum(r.get("score", 0) for r in cycle_runs) / total_runs, 1
    ) if total_runs else 0
    total_issues = sum(r.get("issues_found", 0) for r in cycle_runs)
    total_critical = sum(r.get("issues_critical", 0) for r in cycle_runs)

    # Best and worst performing skills
    sorted_runs = sorted(cycle_runs, key=lambda r: r.get("score", 0))
    worst_3 = sorted_runs[:3]
    best_3 = sorted_runs[-3:][::-1]

    # Active issues at cycle end
    active_issues = [i for i in issues.values() if i.get("status") == "active"]
    critical_issues = [i for i in active_issues if i.get("severity") == "critical"]

    score_color = _score_color(avg_score)
    score_icon = "✓" if avg_score >= 80 else "⚠" if avg_score >= 50 else "✗"

    def run_row(r: dict) -> str:
        sc = r.get("score", 0)
        col = _score_color(sc)
        return (
            f"<tr>"
            f"<td style='padding:7px 10px'>{r.get('skill_id','')}</td>"
            f"<td style='padding:7px 10px'>{r.get('skill_name','')}</td>"
            f"<td style='padding:7px 10px;font-weight:700;color:{col}'>{sc}/100</td>"
            f"<td style='padding:7px 10px;color:#6b7280'>{r.get('issues_found',0)}</td>"
            f"</tr>"
        )

    best_rows = "".join(run_row(r) for r in best_3)
    worst_rows = "".join(run_row(r) for r in worst_3)

    critical_html = "".join(
        f"<li style='margin-bottom:5px'><strong>{i.get('title','')}</strong>"
        f"<span style='color:#6b7280;font-size:11px'> · {i.get('url','')}</span></li>"
        for i in critical_issues[:8]
    ) or "<li style='color:#22c55e'>No critical issues — excellent!</li>"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">{_BASE_STYLES}</head>
<body><div class="wrap">
  <div class="header">
    <h1>🔁 SEO Cycle {cycle_number} Complete — All 23 Skills Executed</h1>
    <p>{date_str} &nbsp;·&nbsp; Full 23-day rotation cycle finished</p>
  </div>

  <div class="card">
    <div class="card-title">Cycle {cycle_number} Executive Summary</div>
    <div class="kpi-row">
      <div class="kpi">
        <div class="kpi-val" style="color:{score_color}">{avg_score}</div>
        <div class="kpi-lbl">Avg SEO Score {score_icon}</div>
      </div>
      <div class="kpi">
        <div class="kpi-val" style="color:#f59e0b">{total_issues}</div>
        <div class="kpi-lbl">Total Issues</div>
      </div>
      <div class="kpi">
        <div class="kpi-val" style="color:#ef4444">{total_critical}</div>
        <div class="kpi-lbl">Critical Findings</div>
      </div>
      <div class="kpi">
        <div class="kpi-val" style="color:#38bdf8">{total_runs}</div>
        <div class="kpi-lbl">Skills Audited</div>
      </div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Top Performing Skills</div>
    <table style="width:100%;border-collapse:collapse;font-size:13px">
      <thead><tr style="border-bottom:2px solid #e2e8f0">
        <th style="padding:7px 10px;text-align:left;color:#64748b">#</th>
        <th style="padding:7px 10px;text-align:left;color:#64748b">Skill</th>
        <th style="padding:7px 10px;text-align:left;color:#64748b">Score</th>
        <th style="padding:7px 10px;text-align:left;color:#64748b">Issues</th>
      </tr></thead>
      <tbody>{best_rows}</tbody>
    </table>
  </div>

  <div class="card">
    <div class="card-title">Skills Needing Attention (Lowest Scores)</div>
    <table style="width:100%;border-collapse:collapse;font-size:13px">
      <thead><tr style="border-bottom:2px solid #e2e8f0">
        <th style="padding:7px 10px;text-align:left;color:#64748b">#</th>
        <th style="padding:7px 10px;text-align:left;color:#64748b">Skill</th>
        <th style="padding:7px 10px;text-align:left;color:#64748b">Score</th>
        <th style="padding:7px 10px;text-align:left;color:#64748b">Issues</th>
      </tr></thead>
      <tbody>{worst_rows}</tbody>
    </table>
  </div>

  <div class="card">
    <div class="card-title">Open Critical Issues — End of Cycle {cycle_number}</div>
    <ul style="font-size:13px;line-height:1.9;padding-left:18px">{critical_html}</ul>
  </div>

  <div class="card">
    <div class="card-title">What Happens Next</div>
    <ul style="font-size:13px;line-height:1.9;padding-left:18px">
      <li>Cycle {cycle_number + 1} begins automatically with Skill 1 (Technical Crawl Audit)</li>
      <li>Historical comparison will track improvement vs Cycle {cycle_number}</li>
      <li>Recurring issues from this cycle are flagged for priority resolution</li>
      <li>Review proposed fixes (PRs) before the next cycle completes</li>
    </ul>
  </div>

  <div class="footer">
    <a href="https://amulyagupta.in/admin/seo/">Dashboard</a> &nbsp;·&nbsp;
    SEO Runtime Bot · amulyagupta.in · Cycle {cycle_number} Completion Report
  </div>
</div></body></html>"""

    text = (
        f"SEO CYCLE {cycle_number} COMPLETE — All 23 Skills Executed\n"
        f"{date_str}\n{'='*55}\n\n"
        f"Avg Score:      {avg_score}/100\n"
        f"Total Issues:   {total_issues}\n"
        f"Critical:       {total_critical}\n"
        f"Skills Audited: {total_runs}\n\n"
        f"OPEN CRITICAL ISSUES:\n"
        + "".join(f"  • {i.get('title','')} — {i.get('url','')}\n" for i in critical_issues[:8])
        + (f"\n  (none)\n" if not critical_issues else "")
        + f"\nCycle {cycle_number + 1} begins with Skill 1 automatically.\n"
    )

    return html, text
