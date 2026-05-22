import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from config import GMAIL_SENDER, GMAIL_APP_PASSWORD, REPORT_EMAIL

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Email Delivery
# ─────────────────────────────────────────────────────────────────────────────

def send_report(subject: str, html_body: str, text_body: str = "", attachments: list = None) -> bool:
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
# Style Helpers
# ─────────────────────────────────────────────────────────────────────────────

_BASE_STYLE = """
body{margin:0;padding:0;background:#f9fafb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
.wrap{max-width:680px;margin:0 auto;padding:24px}
.hero{background:linear-gradient(135deg,#1e293b,#334155);border-radius:12px;padding:32px;margin-bottom:24px}
.card{background:#fff;border-radius:12px;padding:24px;margin-bottom:16px;border:1px solid #e5e7eb}
.kpi-row{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}
.kpi{flex:1;min-width:120px;border-radius:8px;padding:16px;text-align:center}
.kpi-num{font-size:36px;font-weight:700;line-height:1}
.kpi-label{font-size:11px;color:#6b7280;margin-top:4px}
table{width:100%;border-collapse:collapse}
th{text-align:left;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.5px;
   color:#6b7280;padding:8px;border-bottom:2px solid #e5e7eb}
td{padding:8px;font-size:13px;border-bottom:1px solid #f1f5f9;vertical-align:top}
.sev{display:inline-block;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:700}
.sev-critical{background:#fef2f2;color:#dc2626}
.sev-warning{background:#fffbeb;color:#d97706}
.sev-info{background:#eff6ff;color:#2563eb}
.tag{display:inline-block;background:#f1f5f9;padding:2px 8px;border-radius:4px;font-size:11px;color:#475569}
.section-title{font-size:16px;font-weight:600;color:#1e293b;margin:0 0 12px}
.muted{color:#6b7280;font-size:12px}
.green{color:#16a34a} .red{color:#dc2626} .yellow{color:#d97706} .blue{color:#2563eb}
ul{margin:0;padding-left:18px} li{margin:4px 0;font-size:13px}
.footer{text-align:center;padding:16px;color:#94a3b8;font-size:11px}
"""


def _score_color(score: int) -> str:
    if score >= 80:
        return "#16a34a"
    elif score >= 50:
        return "#d97706"
    return "#dc2626"


def _score_label(score: int) -> str:
    if score >= 80:
        return "GOOD"
    elif score >= 50:
        return "NEEDS WORK"
    return "CRITICAL"


def _sev_badge(sev: str) -> str:
    return f'<span class="sev sev-{sev}">{sev.upper()}</span>'


# ─────────────────────────────────────────────────────────────────────────────
# Morning Brief
# ─────────────────────────────────────────────────────────────────────────────

def build_morning_brief(
    run_data: dict,
    findings: list[dict],
    skill_name: str,
    score: int,
    scores: list[dict] | None = None,
    regressions: list[dict] | None = None,
    cycle: int = 1,
) -> tuple[str, str]:
    date_str = datetime.utcnow().strftime("%B %d, %Y")
    sc = _score_color(score)
    sl = _score_label(score)
    scores = scores or []
    regressions = regressions or []

    critical = [f for f in findings if f.get("severity") == "critical"]
    warnings = [f for f in findings if f.get("severity") == "warning"]
    info = [f for f in findings if f.get("severity") == "info"]

    # Critical alert block
    critical_block = ""
    if critical:
        items = "".join(
            f"<p style='margin:4px 0;font-size:13px'>• {c.get('title','')}: {c.get('description','')[:120]}</p>"
            for c in critical
        )
        critical_block = f"""
        <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:12px;
                    padding:20px;margin-bottom:16px;">
          <h3 style="margin:0 0 8px;color:#dc2626;font-size:14px;font-weight:700">
            &#x26A0; CRITICAL — IMMEDIATE SEO INTERVENTION REQUIRED</h3>
          {items}
        </div>"""

    # Findings table (top 20)
    rows = ""
    for f in findings[:20]:
        sev = f.get("severity", "info")
        rows += f"""<tr>
          <td>{_sev_badge(sev)}</td>
          <td style="max-width:260px;word-break:break-word">{f.get('title','')}</td>
          <td style="font-size:11px;color:#6b7280">{(f.get('url','') or '—').replace('https://amulyagupta.in','') or '/'}</td>
        </tr>"""

    # Recommendations
    recs = [f["recommendation"] for f in findings if f.get("recommendation")]
    recs_html = ""
    if recs:
        recs_html = "<div class='card'><div class='section-title'>Top Recommendations</div><ul>"
        for r in recs[:10]:
            recs_html += f"<li>{r}</li>"
        recs_html += "</ul></div>"

    # Historical comparison
    hist_block = _build_historical_comparison(scores, run_data.get("skill_id", 0))

    # Regression alert
    reg_block = ""
    if regressions:
        reg_rows = "".join(
            f"<tr><td><span class='tag'>S{r['skill_id']}</span></td>"
            f"<td>{r['skill_name']}</td>"
            f"<td><span class='red'>{r['current_score']}</span></td>"
            f"<td><span class='tag'>{r['prev_score']}</span></td>"
            f"<td style='color:#dc2626;font-weight:600'>{r['delta']:+d}</td></tr>"
            for r in regressions[:5]
        )
        reg_block = f"""<div class="card">
          <div class="section-title" style="color:#dc2626">&#x25BC; Score Regressions Detected</div>
          <table>
            <thead><tr><th>Skill</th><th>Name</th><th>Now</th><th>Before</th><th>Delta</th></tr></thead>
            <tbody>{reg_rows}</tbody>
          </table>
        </div>"""

    # Predictive forecast
    forecast_block = _build_forecast_section(scores, regressions)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>{_BASE_STYLE}</style>
</head>
<body><div class="wrap">

  <div class="hero">
    <h1 style="color:#fff;margin:0 0 4px;font-size:22px">SEO Runtime — Morning Brief</h1>
    <p style="color:#94a3b8;margin:0;font-size:13px">{date_str} · amulyagupta.in · Cycle {cycle}</p>
  </div>

  <div class="card">
    <div class="section-title">Today's Skill: {skill_name} (#{run_data.get('skill_id', '?')}/23)</div>
    <div class="kpi-row">
      <div class="kpi" style="background:#f8fafc">
        <div class="kpi-num" style="color:{sc}">{score}</div>
        <div class="kpi-label">SEO Score</div>
        <div style="font-size:10px;font-weight:700;color:{sc}">{sl}</div>
      </div>
      <div class="kpi" style="background:#fef2f2">
        <div class="kpi-num" style="color:#dc2626">{len(critical)}</div>
        <div class="kpi-label">Critical</div>
      </div>
      <div class="kpi" style="background:#fffbeb">
        <div class="kpi-num" style="color:#d97706">{len(warnings)}</div>
        <div class="kpi-label">Warnings</div>
      </div>
      <div class="kpi" style="background:#eff6ff">
        <div class="kpi-num" style="color:#2563eb">{len(info)}</div>
        <div class="kpi-label">Info</div>
      </div>
      <div class="kpi" style="background:#f0fdf4">
        <div class="kpi-num" style="color:#15803d">{run_data.get('duration_s', 0)}s</div>
        <div class="kpi-label">Duration</div>
      </div>
    </div>
  </div>

  {critical_block}
  {reg_block}

  <div class="card">
    <div class="section-title">Findings ({len(findings)} total)</div>
    <table>
      <thead><tr><th>Severity</th><th>Issue</th><th>URL</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    {"<p class='muted' style='margin-top:8px'>+ " + str(len(findings)-20) + " more findings</p>" if len(findings) > 20 else ""}
  </div>

  {recs_html}
  {hist_block}
  {forecast_block}

  <div class="footer">
    SEO Runtime Bot · amulyagupta.in · Automated intelligence report · Cycle {cycle} · Do not reply
  </div>
</div></body></html>"""

    text = (
        f"SEO Runtime — Morning Brief\n{date_str}\n\n"
        f"Skill: {skill_name} (#{run_data.get('skill_id','?')}/23)\n"
        f"Score: {score}/100 ({sl}) | Cycle: {cycle}\n"
        f"Critical: {len(critical)} | Warnings: {len(warnings)} | Info: {len(info)}\n"
        f"Duration: {run_data.get('duration_s', 0)}s\n\n"
        f"Regressions detected: {len(regressions)}\n\n"
        f"Findings:\n"
    )
    for f in findings[:15]:
        text += f"[{f.get('severity','').upper()}] {f.get('title','')} — {f.get('url','')}\n"

    return html, text


def _build_historical_comparison(scores: list[dict], skill_id: int) -> str:
    """Compare current score with previous runs of the same skill."""
    if not scores or not skill_id:
        return ""
    skill_history = [s for s in scores if s.get("skill_id") == skill_id]
    if len(skill_history) < 2:
        return ""

    last3 = skill_history[-3:]
    rows = ""
    for i, s in enumerate(last3):
        sc = s.get("score", 0)
        delta = s.get("delta", 0) or 0
        label = "← current" if i == len(last3) - 1 else ""
        arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "—")
        color = "#16a34a" if delta > 0 else ("#dc2626" if delta < 0 else "#6b7280")
        d = (s.get("date") or "")[:10]
        rows += f"""<tr>
          <td style="font-size:11px;color:#6b7280">{d}</td>
          <td style="font-weight:600;color:{_score_color(sc)}">{sc}</td>
          <td style="color:{color}">{arrow} {delta:+d}</td>
          <td style="font-size:11px;color:#6b7280">{label}</td>
        </tr>"""

    return f"""<div class="card">
      <div class="section-title">Historical Comparison — Skill #{skill_id}</div>
      <table>
        <thead><tr><th>Date</th><th>Score</th><th>Delta</th><th></th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>"""


def _build_forecast_section(scores: list[dict], regressions: list[dict]) -> str:
    """Generate a simple predictive SEO forecast."""
    if not scores:
        return ""

    last10 = scores[-10:]
    if len(last10) < 3:
        return ""

    avg = sum(s.get("score", 0) for s in last10) / len(last10)
    trend_vals = [s.get("score", 0) for s in last10]
    slope = (trend_vals[-1] - trend_vals[0]) / max(len(trend_vals) - 1, 1)

    # Predict next 7 days (1 skill/day)
    forecast_7d = round(avg + slope * 7)
    forecast_7d = max(0, min(100, forecast_7d))

    direction = "improving" if slope > 0.5 else ("declining" if slope < -0.5 else "stable")
    dir_color = "#16a34a" if direction == "improving" else ("#dc2626" if direction == "declining" else "#d97706")

    risks = []
    if len(regressions) >= 2:
        risks.append("Multiple regressions detected — technical debt accumulating")
    if avg < 60:
        risks.append("Average score below 60 — significant SEO issues present")
    if slope < -2:
        risks.append("Negative score trajectory — immediate intervention recommended")

    risk_html = ""
    if risks:
        risk_html = "<ul>" + "".join(f"<li style='color:#dc2626'>{r}</li>" for r in risks) + "</ul>"

    return f"""<div class="card">
      <div class="section-title">Predictive SEO Forecast</div>
      <div style="display:flex;gap:24px;margin-bottom:12px;flex-wrap:wrap">
        <div>
          <div style="font-size:11px;color:#6b7280;margin-bottom:2px">7-Day Forecast Score</div>
          <div style="font-size:28px;font-weight:700;color:{_score_color(forecast_7d)}">{forecast_7d}</div>
        </div>
        <div>
          <div style="font-size:11px;color:#6b7280;margin-bottom:2px">Trajectory</div>
          <div style="font-size:22px;font-weight:700;color:{dir_color}">{direction.upper()}</div>
          <div style="font-size:11px;color:#6b7280">slope: {slope:+.2f} pts/day</div>
        </div>
        <div>
          <div style="font-size:11px;color:#6b7280;margin-bottom:2px">10-Day Avg Score</div>
          <div style="font-size:22px;font-weight:700;color:{_score_color(int(avg))}">{avg:.1f}</div>
        </div>
      </div>
      {risk_html if risk_html else "<p class='muted'>No significant risk signals detected.</p>"}
    </div>"""


# ─────────────────────────────────────────────────────────────────────────────
# Weekly Summary
# ─────────────────────────────────────────────────────────────────────────────

def build_weekly_summary(
    weekly: dict,
    monthly: dict,
    scores: list[dict],
    issues: dict,
    regressions: list[dict],
) -> tuple[str, str]:
    date_str = datetime.utcnow().strftime("%B %d, %Y")
    week_of = (datetime.utcnow()).strftime("Week of %b %d")

    active_issues = [i for i in issues.values() if i.get("status") == "active"]
    critical_count = sum(1 for i in active_issues if i.get("severity") == "critical")
    warning_count = sum(1 for i in active_issues if i.get("severity") == "warning")

    # Skills executed this week
    skills_done = weekly.get("skills_completed", [])
    from config import SKILL_NAMES
    skills_html = ""
    for sid in skills_done:
        sname = SKILL_NAMES[sid - 1] if 1 <= sid <= 23 else str(sid)
        # Find score for this skill
        sk_scores = [s for s in scores if s.get("skill_id") == sid]
        sc = sk_scores[-1].get("score", 0) if sk_scores else 0
        skills_html += f"<tr><td><span class='tag'>S{sid}</span></td><td>{sname}</td><td style='color:{_score_color(sc)};font-weight:600'>{sc}</td></tr>"

    avg_score = weekly.get("avg_score", 0)

    # Top issues this week
    top_issues = sorted(active_issues, key=lambda x: (x.get("severity", "z"), -x.get("occurrences", 0)))[:10]
    issues_rows = ""
    for i in top_issues:
        occ = i.get("occurrences", 1)
        recurring = " ↻" if occ >= 3 else ""
        issues_rows += f"<tr><td>{_sev_badge(i.get('severity','info'))}</td><td>{i.get('title','')}{recurring}</td><td style='text-align:center'>{occ}</td></tr>"

    # Regression section
    reg_rows = ""
    for r in regressions[:5]:
        reg_rows += f"<tr><td><span class='tag'>S{r['skill_id']}</span></td><td>{r['skill_name']}</td><td style='color:#dc2626;font-weight:600'>{r['delta']:+d}</td></tr>"

    reg_block = ""
    if regressions:
        reg_block = f"""<div class="card">
          <div class="section-title" style="color:#dc2626">Score Regressions This Week</div>
          <table><thead><tr><th>Skill</th><th>Name</th><th>Score Delta</th></tr></thead>
          <tbody>{reg_rows}</tbody></table>
        </div>"""

    # Monthly trend
    m_trend = monthly.get("score_trend", "stable")
    m_color = "#16a34a" if m_trend == "improving" else ("#dc2626" if m_trend == "declining" else "#d97706")

    forecast_block = _build_forecast_section(scores, regressions)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>{_BASE_STYLE}</style>
</head>
<body><div class="wrap">

  <div class="hero">
    <h1 style="color:#fff;margin:0 0 4px;font-size:22px">SEO Weekly Intelligence Report</h1>
    <p style="color:#94a3b8;margin:0;font-size:13px">{week_of} · {date_str} · amulyagupta.in</p>
  </div>

  <!-- Weekly KPIs -->
  <div class="card">
    <div class="section-title">Weekly Performance Summary</div>
    <div class="kpi-row">
      <div class="kpi" style="background:#f8fafc">
        <div class="kpi-num" style="color:{_score_color(int(avg_score))}">{avg_score}</div>
        <div class="kpi-label">Avg Score</div>
      </div>
      <div class="kpi" style="background:#eff6ff">
        <div class="kpi-num" style="color:#2563eb">{weekly.get('runs', 0)}</div>
        <div class="kpi-label">Skills Run</div>
      </div>
      <div class="kpi" style="background:#fef2f2">
        <div class="kpi-num" style="color:#dc2626">{critical_count}</div>
        <div class="kpi-label">Critical Issues</div>
      </div>
      <div class="kpi" style="background:#fffbeb">
        <div class="kpi-num" style="color:#d97706">{warning_count}</div>
        <div class="kpi-label">Warnings</div>
      </div>
      <div class="kpi" style="background:#f0fdf4">
        <div class="kpi-num" style="color:{m_color}">{m_trend[:3].upper()}</div>
        <div class="kpi-label">30d Trend</div>
      </div>
    </div>
  </div>

  <!-- Skills executed -->
  <div class="card">
    <div class="section-title">Skills Executed This Week</div>
    {"<table><thead><tr><th>Skill</th><th>Name</th><th>Score</th></tr></thead><tbody>" + skills_html + "</tbody></table>" if skills_html else "<p class='muted'>No skills executed this week.</p>"}
  </div>

  <!-- Active issues -->
  <div class="card">
    <div class="section-title">Top Active Issues ({len(active_issues)} total)</div>
    <table>
      <thead><tr><th>Severity</th><th>Issue</th><th style="text-align:center">Occurrences</th></tr></thead>
      <tbody>{issues_rows if issues_rows else '<tr><td colspan="3" style="color:#6b7280;text-align:center">No active issues</td></tr>'}</tbody>
    </table>
  </div>

  {reg_block}

  <!-- Monthly context -->
  <div class="card">
    <div class="section-title">30-Day Context</div>
    <table>
      <thead><tr><th>Metric</th><th>Value</th></tr></thead>
      <tbody>
        <tr><td>Total runs</td><td style="font-weight:600">{monthly.get('runs', 0)}</td></tr>
        <tr><td>Avg score</td><td style="font-weight:600;color:{_score_color(int(monthly.get('avg_score', 0)))}">{monthly.get('avg_score', 0)}</td></tr>
        <tr><td>Total issues found</td><td>{monthly.get('total_issues', 0)}</td></tr>
        <tr><td>Critical issues found</td><td style="color:#dc2626">{monthly.get('critical_count', 0)}</td></tr>
        <tr><td>Skills audited</td><td>{monthly.get('skills_audited', 0)}/23</td></tr>
        <tr><td>Score trend</td><td style="color:{m_color};font-weight:600">{m_trend.upper()}</td></tr>
      </tbody>
    </table>
  </div>

  {forecast_block}

  <div class="footer">
    SEO Runtime Bot · amulyagupta.in · Weekly Intelligence Report · Do not reply
  </div>
</div></body></html>"""

    text = (
        f"SEO Weekly Report — {week_of}\n\n"
        f"Weekly Stats:\n"
        f"  Skills run: {weekly.get('runs', 0)}\n"
        f"  Avg score: {avg_score}\n"
        f"  Critical issues: {critical_count}\n"
        f"  Warnings: {warning_count}\n"
        f"  30-day trend: {m_trend.upper()}\n\n"
        f"Active Issues: {len(active_issues)}\n"
        f"Regressions: {len(regressions)}\n\n"
        "Review the HTML report for full details."
    )

    return html, text
