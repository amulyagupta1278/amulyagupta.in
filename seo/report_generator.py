"""Report generator — HTML email + Markdown reports."""
from pathlib import Path
from datetime import datetime, timezone


def generate_report(result: dict, site_root: Path):
    reports_dir = Path(site_root) / "seo" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    html = _html_report(result)
    md = _md_report(result)

    (reports_dir / "latest_email.html").write_text(html, encoding="utf-8")
    (reports_dir / "latest_report.md").write_text(md, encoding="utf-8")

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    sn = result.get("skill_number", 0)
    (reports_dir / f"report_{ts}_skill_{sn:02d}.md").write_text(md, encoding="utf-8")


def _sev_color(s: str) -> str:
    return {"critical": "#dc3545", "warning": "#e67e22", "info": "#3498db", "ok": "#27ae60"}.get(s, "#7f8c8d")


def _html_report(r: dict) -> str:
    name = r.get("skill_name", "Unknown")
    num = r.get("skill_number", 0)
    score = r.get("health_score", 0)
    status = r.get("status", "unknown")
    findings = r.get("findings", [])
    fixes = r.get("auto_fixes_applied", [])
    recs = r.get("recommendations", [])
    summary = r.get("summary", "")
    ts = r.get("executed_at", "")[:16].replace("T", " ")
    cycle = r.get("cycle", 1)
    day = r.get("day_in_cycle", 1)

    score_color = "#27ae60" if score >= 80 else "#e67e22" if score >= 50 else "#dc3545"
    status_color = {"ok": "#27ae60", "warning": "#e67e22", "critical": "#dc3545"}.get(status, "#7f8c8d")

    crits = [f for f in findings if f.get("severity") == "critical"]
    warns = [f for f in findings if f.get("severity") == "warning"]
    infos = [f for f in findings if f.get("severity") == "info"]

    findings_html = ""
    for f in findings:
        sev = f.get("severity", "info")
        col = _sev_color(sev)
        badge = ""
        if f.get("auto_fixed"):
            badge = '<span style="background:#27ae60;color:white;padding:1px 6px;border-radius:3px;font-size:10px;margin-left:8px;">AUTO-FIXED</span>'
        pages = f.get("pages_impacted", [])
        pg_str = ", ".join(str(p) for p in pages[:3]) + (f" +{len(pages)-3} more" if len(pages) > 3 else "")
        findings_html += f"""
<div style="border-left:4px solid {col};padding:12px 14px;margin:8px 0;background:#fafafa;border-radius:0 4px 4px 0;">
  <div style="margin-bottom:5px;">
    <span style="background:{col};color:white;padding:1px 7px;border-radius:3px;font-size:10px;font-weight:bold;text-transform:uppercase;">{sev}</span>
    <span style="font-weight:600;margin-left:8px;color:#2c3e50;font-size:13px;">[{f.get('priority','')}] {f.get('id','')}: {f.get('title','')}</span>{badge}
  </div>
  <p style="color:#555;font-size:12px;margin:4px 0;"><strong>Issue:</strong> {f.get('description','')}</p>
  <p style="color:#2980b9;font-size:12px;margin:4px 0;"><strong>Fix:</strong> {f.get('recommendation','')}</p>
  {"<p style='color:#777;font-size:11px;margin:3px 0;'><strong>Impact:</strong> " + f.get('impact','') + "</p>" if f.get('impact') else ""}
  {"<p style='color:#999;font-size:11px;margin:3px 0;'><strong>Pages:</strong> " + pg_str + "</p>" if pg_str else ""}
</div>"""

    fixes_html = ""
    if fixes:
        items = "".join(f"<li style='color:#555;font-size:12px;padding:2px 0;'>✅ {fx}</li>" for fx in fixes)
        fixes_html = f'<h3 style="color:#27ae60;font-size:14px;">Auto-Fixes Applied ({len(fixes)})</h3><ul style="padding-left:18px;">{items}</ul>'

    recs_html = ""
    if recs:
        items = "".join(f"<li style='color:#555;font-size:12px;padding:2px 0;'>💡 {rc}</li>" for rc in recs)
        recs_html = f'<h3 style="color:#8e44ad;font-size:14px;">Strategic Recommendations</h3><ul style="padding-left:18px;">{items}</ul>'

    critical_alert = ""
    if crits:
        critical_alert = f"""
<div style="background:#fdf2f2;border:2px solid #dc3545;border-radius:6px;padding:14px;margin-bottom:16px;">
  <strong style="color:#dc3545;font-size:14px;">🚨 CRITICAL — IMMEDIATE SEO INTERVENTION REQUIRED</strong>
  <p style="color:#dc3545;font-size:12px;margin:6px 0 0;">{len(crits)} critical issue(s) detected requiring immediate action.</p>
</div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SEO Report #{num:02d} — {name}</title></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:680px;margin:0 auto;padding:16px;background:#f0f2f5;color:#2c3e50;">
<div style="background:white;border-radius:10px;padding:28px;box-shadow:0 2px 12px rgba(0,0,0,0.1);">

<div style="border-bottom:2px solid #ecf0f1;padding-bottom:18px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:10px;">
  <div>
    <h1 style="margin:0;font-size:20px;color:#1a252f;">🔍 SEO Daily Audit</h1>
    <p style="margin:4px 0 0;color:#7f8c8d;font-size:12px;">amulyagupta.in · Cycle {cycle}, Day {day}/23 · {ts} UTC</p>
  </div>
  <div style="text-align:right;">
    <div style="font-size:38px;font-weight:700;color:{score_color};line-height:1;">{score}</div>
    <div style="font-size:10px;color:#7f8c8d;text-transform:uppercase;letter-spacing:0.8px;">Health Score</div>
  </div>
</div>

<div style="background:#f8f9fa;border-radius:6px;padding:14px;margin-bottom:16px;">
  <table style="width:100%;border-collapse:collapse;">
    <tr><td style="color:#7f8c8d;font-size:12px;padding:3px 0;width:35%;">Skill</td>
        <td style="font-weight:600;color:#2c3e50;font-size:13px;">#{num:02d}/23: {name}</td></tr>
    <tr><td style="color:#7f8c8d;font-size:12px;padding:3px 0;">Status</td>
        <td><span style="background:{status_color};color:white;padding:1px 8px;border-radius:3px;font-size:11px;font-weight:bold;text-transform:uppercase;">{status}</span></td></tr>
    <tr><td style="color:#7f8c8d;font-size:12px;padding:3px 0;">Run Time</td>
        <td style="font-size:12px;color:#555;">{ts} UTC</td></tr>
  </table>
</div>

<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px;">
  <div style="background:#fdf2f2;border:1px solid #f5c6cb;border-radius:6px;padding:10px;text-align:center;">
    <div style="font-size:22px;font-weight:700;color:#dc3545;">{len(crits)}</div>
    <div style="font-size:10px;color:#dc3545;text-transform:uppercase;">Critical</div>
  </div>
  <div style="background:#fff9f0;border:1px solid #f5cba7;border-radius:6px;padding:10px;text-align:center;">
    <div style="font-size:22px;font-weight:700;color:#e67e22;">{len(warns)}</div>
    <div style="font-size:10px;color:#e67e22;text-transform:uppercase;">Warnings</div>
  </div>
  <div style="background:#eaf4fe;border:1px solid #aed6f1;border-radius:6px;padding:10px;text-align:center;">
    <div style="font-size:22px;font-weight:700;color:#3498db;">{len(infos)}</div>
    <div style="font-size:10px;color:#3498db;text-transform:uppercase;">Info</div>
  </div>
  <div style="background:#eafaf1;border:1px solid #a9dfbf;border-radius:6px;padding:10px;text-align:center;">
    <div style="font-size:22px;font-weight:700;color:#27ae60;">{len(fixes)}</div>
    <div style="font-size:10px;color:#27ae60;text-transform:uppercase;">Auto-Fixed</div>
  </div>
</div>

{critical_alert}

{"<div style='background:#eaf4fe;border-radius:6px;padding:12px;margin-bottom:14px;'><p style='margin:0;color:#2980b9;font-size:13px;'>" + summary + "</p></div>" if summary else ""}

{fixes_html}

<h3 style="color:#2c3e50;font-size:14px;border-bottom:1px solid #ecf0f1;padding-bottom:6px;margin-top:20px;">📋 Detailed Findings ({len(findings)})</h3>
{findings_html or "<p style='color:#27ae60;font-size:13px;'>✅ All checks passed — no issues detected.</p>"}

{recs_html}

<div style="border-top:1px solid #ecf0f1;margin-top:24px;padding-top:14px;text-align:center;color:#95a5a6;font-size:10px;">
  <p style="margin:0;">SEO Automation Framework · amulyagupta.in · 23-Day Rotational Intelligence Cycle</p>
  <p style="margin:4px 0 0;">Skill {num}/23 · Cycle {cycle} · Day {day}/23</p>
</div>

</div>
</body>
</html>"""


def _md_report(r: dict) -> str:
    name = r.get("skill_name", "Unknown")
    num = r.get("skill_number", 0)
    score = r.get("health_score", 0)
    status = r.get("status", "unknown").upper()
    findings = sorted(r.get("findings", []),
                      key=lambda f: {"critical": 0, "warning": 1, "info": 2}.get(f.get("severity", "info"), 3))
    fixes = r.get("auto_fixes_applied", [])
    recs = r.get("recommendations", [])
    ts = r.get("executed_at", "")[:10]
    cycle = r.get("cycle", 1)
    day = r.get("day_in_cycle", 1)

    crits = [f for f in findings if f.get("severity") == "critical"]
    warns = [f for f in findings if f.get("severity") == "warning"]
    infos = [f for f in findings if f.get("severity") == "info"]

    lines = [
        f"# SEO Audit Report — {name}",
        "",
        f"**Date:** {ts} | **Cycle:** {cycle} | **Day:** {day}/23 | **Score:** {score}/100 | **Status:** {status}",
        "",
        f"## Executive Summary",
        "",
        r.get("summary", ""),
        "",
        "## Findings Overview",
        "",
        "| Severity | Count |",
        "|----------|-------|",
        f"| 🔴 Critical | {len(crits)} |",
        f"| 🟡 Warning | {len(warns)} |",
        f"| 🔵 Info | {len(infos)} |",
        f"| ✅ Auto-Fixed | {len(fixes)} |",
        "",
    ]

    if crits:
        lines += ["## 🚨 CRITICAL — IMMEDIATE SEO INTERVENTION REQUIRED", ""]

    if fixes:
        lines += ["## Auto-Fixes Applied", ""]
        lines += [f"- ✅ {fx}" for fx in fixes]
        lines += [""]

    if findings:
        lines += ["## Detailed Findings", ""]
        icons = {"critical": "🔴", "warning": "🟡", "info": "🔵"}
        for f in findings:
            sev = f.get("severity", "info")
            icon = icons.get(sev, "ℹ️")
            fixed = " ✅ AUTO-FIXED" if f.get("auto_fixed") else ""
            lines += [
                f"### {icon} {f.get('id','')}: {f.get('title','')}{fixed}",
                "",
                f"**Priority:** {f.get('priority','')} | **Severity:** {sev.upper()}",
                "",
                f"**Issue:** {f.get('description','')}",
                "",
                f"**Fix:** {f.get('recommendation','')}",
            ]
            if f.get("impact"):
                lines += ["", f"**Ranking Impact:** {f.get('impact','')}"]
            pages = f.get("pages_impacted", [])
            if pages:
                lines += ["", f"**Pages:** {', '.join(str(p) for p in pages[:5])}"]
            lines += [""]

    if recs:
        lines += ["## Strategic Recommendations", ""]
        lines += [f"- 💡 {rc}" for rc in recs]
        lines += [""]

    lines += ["---", f"*SEO Automation Framework · amulyagupta.in · Skill {num}/23*"]
    return "\n".join(lines)
