import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from config import DATA_DIR

log = logging.getLogger(__name__)


def _data_path(name: str) -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, name)


def load_json(name: str, default=None):
    path = _data_path(name)
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception as e:
            log.warning("Load failed [%s]: %s", name, e)
    return default if default is not None else {}


def save_json(name: str, data):
    path = _data_path(name)
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        log.error("Save failed [%s]: %s", name, e)


def get_next_skill(sheets_client=None, enabled_skills: list[int] | None = None) -> int:
    """Return the next skill ID to run from the enabled skill set."""
    from config import get_enabled_skills
    pool = sorted(enabled_skills if enabled_skills is not None else get_enabled_skills())
    if not pool:
        log.warning("No skills enabled — defaulting to skill 1")
        return 1

    last_skill = 0
    if sheets_client and sheets_client.available:
        last = sheets_client.get_last_run()
        if last:
            last_skill = int(last.get("skill_id", 0))
    else:
        state = load_json("state.json")
        last_skill = state.get("last_skill_id", 0)

    try:
        idx = pool.index(last_skill)
        return pool[(idx + 1) % len(pool)]
    except ValueError:
        return pool[0]


def save_run_state(skill_id: int, run_id: str):
    state = load_json("state.json")
    state["last_skill_id"] = skill_id
    state["last_run_id"] = run_id
    state["last_run_date"] = datetime.utcnow().isoformat()
    save_json("state.json", state)


def make_issue_id(skill_id: int, category: str, url: str, title: str) -> str:
    key = f"{skill_id}:{category}:{url}:{title}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def load_issues() -> dict:
    return load_json("issues.json", {})


def save_issues(issues: dict):
    save_json("issues.json", issues)


def upsert_issue(skill_id: int, finding: dict) -> dict:
    issues = load_issues()
    iid = make_issue_id(skill_id, finding.get("category", ""), finding.get("url", ""), finding.get("title", ""))
    now = datetime.utcnow().isoformat()

    if iid in issues:
        issues[iid]["last_seen"] = now
        issues[iid]["occurrences"] = issues[iid].get("occurrences", 1) + 1
        issues[iid]["severity"] = finding.get("severity", issues[iid]["severity"])
        issues[iid]["status"] = "active"
    else:
        issues[iid] = {
            "issue_id": iid,
            "first_seen": now,
            "last_seen": now,
            "skill_id": skill_id,
            "severity": finding.get("severity", "info"),
            "category": finding.get("category", ""),
            "url": finding.get("url", ""),
            "title": finding.get("title", ""),
            "description": finding.get("description", ""),
            "status": "active",
            "occurrences": 1,
        }

    save_issues(issues)
    return issues[iid]


def load_score_history() -> list:
    return load_json("scores.json", [])


def append_score(skill_id: int, skill_name: str, score: int, run_id: str, cycle: int = 1):
    history = load_score_history()
    prev = next((h["score"] for h in reversed(history) if h["skill_id"] == skill_id), None)
    delta = score - prev if prev is not None else 0
    history.append({
        "date": datetime.utcnow().isoformat(),
        "skill_id": skill_id,
        "skill_name": skill_name,
        "score": score,
        "prev_score": prev,
        "delta": delta,
        "cycle": cycle,
        "run_id": run_id,
    })
    save_json("scores.json", history)
    return delta


def load_runs() -> list:
    return load_json("runs.json", [])


def append_run(run: dict):
    runs = load_runs()
    runs.append(run)
    if len(runs) > 200:
        runs = runs[-200:]
    save_json("runs.json", runs)


# ─────────────────────────────────────────────────────────────────────────────
# Cycle Tracking
# ─────────────────────────────────────────────────────────────────────────────

def get_current_cycle(enabled_skills: list[int]) -> int:
    """Count completed 23-day cycles based on run history."""
    runs = load_runs()
    if not runs or not enabled_skills:
        return 1
    skill_set = set(enabled_skills)
    seen_in_current: set[int] = set()
    completed_cycles = 0
    for run in runs:
        sid = run.get("skill_id")
        if sid in skill_set:
            seen_in_current.add(sid)
            if seen_in_current >= skill_set:
                completed_cycles += 1
                seen_in_current = set()
    return completed_cycles + 1


# ─────────────────────────────────────────────────────────────────────────────
# Regression Detection
# ─────────────────────────────────────────────────────────────────────────────

def detect_regressions(scores: list[dict]) -> list[dict]:
    """Identify skills where score dropped ≥5 points vs previous run."""
    if not scores:
        return []
    by_skill: dict[int, list[dict]] = {}
    for s in scores:
        sid = s.get("skill_id")
        if sid:
            by_skill.setdefault(sid, []).append(s)
    regressions = []
    for sid, skill_scores in by_skill.items():
        if len(skill_scores) >= 2:
            latest = skill_scores[-1]
            prev = skill_scores[-2]
            delta = (latest.get("score") or 0) - (prev.get("score") or 0)
            if delta <= -5:
                regressions.append({
                    "skill_id": sid,
                    "skill_name": latest.get("skill_name", ""),
                    "prev_score": prev.get("score", 0),
                    "current_score": latest.get("score", 0),
                    "delta": delta,
                    "date": latest.get("date", ""),
                })
    return sorted(regressions, key=lambda x: x["delta"])


# ─────────────────────────────────────────────────────────────────────────────
# Weekly / Monthly Aggregates
# ─────────────────────────────────────────────────────────────────────────────

def load_weekly_aggregate() -> dict:
    """Aggregate run data for the past 7 days."""
    runs = load_runs()
    cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
    recent = [r for r in runs if (r.get("date") or "") >= cutoff]
    if not recent:
        return {"runs": 0, "avg_score": 0, "total_issues": 0, "critical_count": 0, "skills_completed": []}
    return {
        "runs": len(recent),
        "avg_score": round(sum(r.get("score") or 0 for r in recent) / len(recent), 1),
        "total_issues": sum(r.get("issues_found") or 0 for r in recent),
        "critical_count": sum(r.get("issues_critical") or 0 for r in recent),
        "skills_completed": sorted(set(r.get("skill_id") for r in recent if r.get("skill_id"))),
        "runs_detail": recent,
    }


def load_monthly_aggregate() -> dict:
    """Aggregate run data for the past 30 days."""
    runs = load_runs()
    cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()
    recent = [r for r in runs if (r.get("date") or "") >= cutoff]
    if not recent:
        return {"runs": 0, "avg_score": 0, "total_issues": 0, "critical_count": 0, "cycles_completed": 0}
    scores = load_score_history()
    recent_scores = [s for s in scores if (s.get("date") or "") >= cutoff]
    score_trend = "improving" if len(recent_scores) >= 2 and recent_scores[-1].get("score", 0) > recent_scores[0].get("score", 0) else "declining"
    return {
        "runs": len(recent),
        "avg_score": round(sum(r.get("score") or 0 for r in recent) / len(recent), 1),
        "total_issues": sum(r.get("issues_found") or 0 for r in recent),
        "critical_count": sum(r.get("issues_critical") or 0 for r in recent),
        "score_trend": score_trend,
        "skills_audited": len(set(r.get("skill_id") for r in recent if r.get("skill_id"))),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Specialty Data Stores
# ─────────────────────────────────────────────────────────────────────────────

def append_ai_visibility(entry: dict):
    data = load_json("ai_visibility.json", [])
    data.append(entry)
    if len(data) > 100:
        data = data[-100:]
    save_json("ai_visibility.json", data)


def append_cwv_record(record: dict):
    data = load_json("cwv.json", [])
    data.append(record)
    if len(data) > 200:
        data = data[-200:]
    save_json("cwv.json", data)


def append_competitor_record(record: dict):
    data = load_json("competitors.json", [])
    data.append(record)
    if len(data) > 100:
        data = data[-100:]
    save_json("competitors.json", data)


def append_report(report: dict):
    data = load_json("reports.json", [])
    data.append(report)
    if len(data) > 500:
        data = data[-500:]
    save_json("reports.json", data)


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard Snapshot
# ─────────────────────────────────────────────────────────────────────────────

def build_dashboard_snapshot(run: dict, findings: list, scores: list, issues: dict) -> dict:
    now = datetime.utcnow().isoformat()
    recent_runs = load_runs()[-30:]

    active_issues = [i for i in issues.values() if i.get("status") == "active"]
    critical_issues = [i for i in active_issues if i.get("severity") == "critical"]
    warning_issues = [i for i in active_issues if i.get("severity") == "warning"]

    avg_score = sum(s["score"] for s in scores[-23:]) / len(scores[-23:]) if scores else 0

    # Categorise active issues
    categories: dict[str, int] = {}
    for i in active_issues:
        cat = i.get("category", "other")
        categories[cat] = categories.get(cat, 0) + 1

    # Detect recurring issues (seen 3+ times)
    recurring = [i for i in active_issues if i.get("occurrences", 1) >= 3]

    # Regressions
    regressions = detect_regressions(scores)

    # AI visibility and CWV history
    ai_visibility = load_json("ai_visibility.json", [])
    cwv_history = load_json("cwv.json", [])
    competitor_data = load_json("competitors.json", [])
    reports = load_json("reports.json", [])

    # Weekly stats
    weekly = load_weekly_aggregate()

    # Score trend direction (last 5 scores)
    last5 = [s.get("score", 0) for s in scores[-5:]]
    if len(last5) >= 2:
        trend = "up" if last5[-1] > last5[0] else "down" if last5[-1] < last5[0] else "flat"
    else:
        trend = "flat"

    snapshot = {
        "generated_at": now,
        "site_url": "https://amulyagupta.in",
        "current_run": run,
        "summary": {
            "avg_score": round(avg_score, 1),
            "active_issues": len(active_issues),
            "critical_issues": len(critical_issues),
            "warning_issues": len(warning_issues),
            "total_runs": len(recent_runs),
            "score_trend": trend,
            "recurring_issues": len(recurring),
        },
        "recent_runs": recent_runs,
        "latest_findings": findings[:50],
        "score_history": scores[-46:],
        "active_issues_list": sorted(
            active_issues,
            key=lambda x: (x.get("severity", "z"), -x.get("occurrences", 0)),
        )[:60],
        "issue_categories": categories,
        "recurring_issues": recurring[:20],
        "regressions": regressions,
        "ai_visibility": ai_visibility[-20:],
        "cwv_history": cwv_history[-30:],
        "competitor_data": competitor_data[-20:],
        "reports": reports[-30:],
        "weekly": weekly,
    }
    save_json("dashboard.json", snapshot)
    return snapshot
