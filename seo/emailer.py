import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from config import GMAIL_SENDER, GMAIL_APP_PASSWORD, REPORT_EMAIL

log = logging.getLogger(__name__)


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


def build_morning_brief(run_data: dict, findings: list[dict], skill_name: str, score: int) -> tuple[str, str]:
    date_str = datetime.utcnow().strftime("%B %d, %Y")
    score_color = "#22c55e" if score >= 80 else "#f59e0b" if score >= 50 else "#ef4444"
    score_label = "GOOD" if score >= 80 else "NEEDS WORK" if score >= 50 else "CRITICAL"

    critical = [f for f in findings if f.get("severity") == "critical"]
    warnings = [f for f in findings if f.get("severity") == "warning"]
    info = [f for f in findings if f.get("severity") == "info"]

    issues_html = ""
    for f in findings[:20]:
        sev = f.get("severity", "info")
        color = {"critical": "#ef4444", "warning": "#f59e0b", "info": "#3b82f6"}.get(sev, "#6b7280")
        issues_html += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #e5e7eb;">
            <span style="display:inline-block;padding:2px 8px;border-radius:4px;
              background:{color};color:#fff;font-size:11px;font-weight:600;">
              {sev.upper()}
            </span>
          </td>
          <td style="padding:8px;border-bottom:1px solid #e5e7eb;font-size:13px;">{f.get('title','')}</td>
          <td style="padding:8px;border-bottom:1px solid #e5e7eb;font-size:12px;color:#6b7280;">{f.get('url','—')}</td>
        </tr>"""

    recs_html = ""
    for f in findings:
        if f.get("recommendation"):
            recs_html += f"<li style='margin:4px 0;font-size:13px;'>{f['recommendation']}</li>"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<div style="max-width:680px;margin:0 auto;padding:24px;">

  <div style="background:linear-gradient(135deg,#1e293b,#334155);border-radius:12px;padding:32px;margin-bottom:24px;">
    <h1 style="color:#fff;margin:0 0 8px;font-size:24px;">SEO Runtime — Morning Brief</h1>
    <p style="color:#94a3b8;margin:0;font-size:14px;">{date_str} · amulyagupta.in</p>
  </div>

  <div style="background:#fff;border-radius:12px;padding:24px;margin-bottom:16px;border:1px solid #e5e7eb;">
    <h2 style="margin:0 0 16px;font-size:18px;color:#1e293b;">Today's Skill: {skill_name}</h2>
    <div style="display:flex;gap:16px;flex-wrap:wrap;">
      <div style="flex:1;min-width:140px;background:#f8fafc;border-radius:8px;padding:16px;text-align:center;">
        <div style="font-size:40px;font-weight:700;color:{score_color};">{score}</div>
        <div style="font-size:12px;color:#6b7280;margin-top:4px;">SEO Score</div>
        <div style="font-size:11px;font-weight:600;color:{score_color};">{score_label}</div>
      </div>
      <div style="flex:1;min-width:140px;background:#fef2f2;border-radius:8px;padding:16px;text-align:center;">
        <div style="font-size:40px;font-weight:700;color:#ef4444;">{len(critical)}</div>
        <div style="font-size:12px;color:#6b7280;margin-top:4px;">Critical Issues</div>
      </div>
      <div style="flex:1;min-width:140px;background:#fffbeb;border-radius:8px;padding:16px;text-align:center;">
        <div style="font-size:40px;font-weight:700;color:#f59e0b;">{len(warnings)}</div>
        <div style="font-size:12px;color:#6b7280;margin-top:4px;">Warnings</div>
      </div>
      <div style="flex:1;min-width:140px;background:#eff6ff;border-radius:8px;padding:16px;text-align:center;">
        <div style="font-size:40px;font-weight:700;color:#3b82f6;">{len(info)}</div>
        <div style="font-size:12px;color:#6b7280;margin-top:4px;">Informational</div>
      </div>
    </div>
  </div>

  {'<div style="background:#fef2f2;border:1px solid #fecaca;border-radius:12px;padding:20px;margin-bottom:16px;"><h3 style="margin:0 0 8px;color:#dc2626;font-size:15px;">CRITICAL — IMMEDIATE SEO INTERVENTION REQUIRED</h3>' + ''.join(f"<p style='margin:4px 0;font-size:13px;'>• {f.get(\"title\",\"\")}: {f.get(\"description\",\"\")[:150]}</p>" for f in critical) + '</div>' if critical else ""}

  <div style="background:#fff;border-radius:12px;padding:24px;margin-bottom:16px;border:1px solid #e5e7eb;">
    <h2 style="margin:0 0 16px;font-size:18px;color:#1e293b;">Findings ({len(findings)} total)</h2>
    <table style="width:100%;border-collapse:collapse;">
      <thead><tr style="background:#f8fafc;">
        <th style="padding:8px;text-align:left;font-size:12px;color:#6b7280;">Severity</th>
        <th style="padding:8px;text-align:left;font-size:12px;color:#6b7280;">Issue</th>
        <th style="padding:8px;text-align:left;font-size:12px;color:#6b7280;">URL</th>
      </tr></thead>
      <tbody>{issues_html}</tbody>
    </table>
  </div>

  {'<div style="background:#fff;border-radius:12px;padding:24px;margin-bottom:16px;border:1px solid #e5e7eb;"><h2 style="margin:0 0 12px;font-size:18px;color:#1e293b;">Recommendations</h2><ul style="margin:0;padding-left:20px;">' + recs_html + '</ul></div>' if recs_html else ""}

  <div style="text-align:center;padding:16px;color:#94a3b8;font-size:11px;">
    SEO Runtime Bot · amulyagupta.in · Auto-generated report · Do not reply
  </div>
</div>
</body></html>"""

    text = f"SEO Runtime — Morning Brief\n{date_str}\n\nSkill: {skill_name}\nScore: {score}/100\n\nCritical: {len(critical)} | Warnings: {len(warnings)} | Info: {len(info)}\n\nFindings:\n"
    for f in findings[:15]:
        text += f"[{f.get('severity','').upper()}] {f.get('title','')} — {f.get('url','')}\n"

    return html, text
