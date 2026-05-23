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
    # Track cycle number — increments every time all 23 skills complete
    if skill_id == 23:
        state["cycle_number"] = state.get("cycle_number", 0) + 1
    save_json("state.json", state)


def get_cycle_number() -> int:
    state = load_json("state.json")
    return state.get("cycle_number", 1)


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
    state = load_json("state.json")
    actual_cycle = state.get("cycle_number", 1)
    prev = next((h["score"] for h in reversed(history) if h["skill_id"] == skill_id), None)
    delta = score - prev if prev is not None else 0
    history.append({
        "date": datetime.utcnow().isoformat(),
        "skill_id": skill_id,
        "skill_name": skill_name,
        "score": score,
        "prev_score": prev,
        "delta": delta,
        "cycle": actual_cycle,
        "run_id": run_id,
    })
    save_json("scores.json", history)
    return delta


def load_runs() -> list:
    return load_json("runs.json", [])


def append_run(run: dict):
    runs = load_runs()
    state = load_json("state.json")
    run["cycle"] = state.get("cycle_number", 1)
    runs.append(run)
    if len(runs) > 500:
        runs = runs[-500:]
    save_json("runs.json", runs)


# ─────────────────────────────────────────────────────────────────────────────
# Historical comparison — compare current run to previous execution of same skill
# ─────────────────────────────────────────────────────────────────────────────

def get_historical_comparison(runs: list, scores: list) -> dict:
    """Compare the most recent run to the previous run of the same skill."""
    if not runs:
        return {}

    current = runs[-1]
    skill_id = current.get("skill_id")

    # Find previous run of the same skill
    prev_same_skill = next(
        (r for r in reversed(runs[:-1]) if r.get("skill_id") == skill_id), None
    )

    # Find all scores for this skill
    skill_scores = [s for s in scores if s.get("skill_id") == skill_id]

    # Week-over-week: runs from the last 7 days vs runs from 7-14 days ago
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    def _parse_date(d):
        try:
            return datetime.fromisoformat(d)
        except Exception:
            return None

    last_week_scores = []
    prev_week_scores = []
    for s in scores:
        d = _parse_date(s.get("date", ""))
        if d is None:
            continue
        if week_ago <= d <= now:
            last_week_scores.append(s["score"])
        elif two_weeks_ago <= d < week_ago:
            prev_week_scores.append(s["score"])

    avg_last_week = sum(last_week_scores) / len(last_week_scores) if last_week_scores else None
    avg_prev_week = sum(prev_week_scores) / len(prev_week_scores) if prev_week_scores else None
    week_delta = (
        round(avg_last_week - avg_prev_week, 1)
        if avg_last_week is not None and avg_prev_week is not None
        else None
    )

    # Score trend for this skill (last 3 cycles)
    skill_trend = [s["score"] for s in skill_scores[-3:]] if skill_scores else []
    trend_direction = "improving" if len(skill_trend) >= 2 and skill_trend[-1] > skill_trend[-2] else (
        "declining" if len(skill_trend) >= 2 and skill_trend[-1] < skill_trend[-2] else "stable"
    )

    prev_score = prev_same_skill.get("score") if prev_same_skill else None
    prev_issues = prev_same_skill.get("issues_found") if prev_same_skill else None

    return {
        "current_skill_id": skill_id,
        "current_score": current.get("score", 0),
        "prev_score": prev_score,
        "score_delta": (current.get("score", 0) - prev_score) if prev_score is not None else None,
        "prev_run_date": prev_same_skill.get("date") if prev_same_skill else None,
        "prev_issues_found": prev_issues,
        "current_issues_found": current.get("issues_found", 0),
        "issue_delta": (current.get("issues_found", 0) - prev_issues) if prev_issues is not None else None,
        "skill_trend": skill_trend,
        "trend_direction": trend_direction,
        "avg_score_last_7d": round(avg_last_week, 1) if avg_last_week is not None else None,
        "avg_score_prev_7d": round(avg_prev_week, 1) if avg_prev_week is not None else None,
        "week_over_week_delta": week_delta,
        "total_runs_completed": len(runs),
        "cycle_number": get_cycle_number(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Recurring issue detection — issues appearing in 3+ consecutive runs
# ─────────────────────────────────────────────────────────────────────────────

def detect_recurring_issues(issues: dict) -> list[dict]:
    """Return issues that have appeared 3+ times and are still active."""
    recurring = []
    for iid, issue in issues.items():
        if issue.get("status") == "active" and issue.get("occurrences", 1) >= 3:
            issue_copy = dict(issue)
            issue_copy["issue_id"] = iid
            issue_copy["recurring"] = True
            recurring.append(issue_copy)
    return sorted(recurring, key=lambda x: (-x.get("occurrences", 0), x.get("severity", "info")))


# ─────────────────────────────────────────────────────────────────────────────
# Predictive SEO forecasting — trend-based projection
# ─────────────────────────────────────────────────────────────────────────────

def build_predictive_forecast(scores: list) -> dict:
    """
    Simple linear trend forecast for overall SEO health score.
    Uses the last 23 data points (one full cycle).
    """
    recent = scores[-23:] if len(scores) >= 23 else scores
    if len(recent) < 3:
        return {
            "trend": "insufficient_data",
            "projected_score_7d": None,
            "projected_score_30d": None,
            "confidence": "low",
            "momentum": "neutral",
            "risk_level": "unknown",
        }

    score_vals = [s["score"] for s in recent]
    n = len(score_vals)

    # Linear regression
    x_mean = (n - 1) / 2
    y_mean = sum(score_vals) / n
    numerator = sum((i - x_mean) * (score_vals[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    slope = numerator / denominator if denominator else 0

    current = score_vals[-1]
    projected_7d = min(100, max(0, round(current + slope * 7, 1)))
    projected_30d = min(100, max(0, round(current + slope * 30, 1)))

    # Momentum: average of last 5 deltas
    deltas = [score_vals[i] - score_vals[i - 1] for i in range(1, len(score_vals))]
    recent_deltas = deltas[-5:] if len(deltas) >= 5 else deltas
    avg_delta = sum(recent_deltas) / len(recent_deltas) if recent_deltas else 0

    momentum = "positive" if avg_delta > 1 else "negative" if avg_delta < -1 else "neutral"
    trend = "improving" if slope > 0.2 else "declining" if slope < -0.2 else "stable"
    confidence = "high" if n >= 20 else "medium" if n >= 10 else "low"

    # Risk level
    critical_ratio = sum(1 for s in recent if s["score"] < 50) / n
    risk_level = "high" if critical_ratio > 0.3 else "medium" if critical_ratio > 0.1 else "low"

    # Category scores if available
    score_by_category = {}
    for s in recent:
        sid = s.get("skill_id")
        if sid:
            score_by_category[sid] = s["score"]

    lowest_skills = sorted(score_by_category.items(), key=lambda x: x[1])[:3]
    highest_skills = sorted(score_by_category.items(), key=lambda x: x[1], reverse=True)[:3]

    return {
        "trend": trend,
        "slope_per_day": round(slope, 3),
        "current_score": current,
        "projected_score_7d": projected_7d,
        "projected_score_30d": projected_30d,
        "avg_delta_recent": round(avg_delta, 2),
        "confidence": confidence,
        "momentum": momentum,
        "risk_level": risk_level,
        "data_points": n,
        "lowest_scoring_skills": lowest_skills,
        "highest_scoring_skills": highest_skills,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Cycle progress — track position within the 23-day rotation
# ─────────────────────────────────────────────────────────────────────────────

def get_cycle_progress(runs: list, enabled_skills: list) -> dict:
    """Return current position in the 23-skill cycle."""
    if not runs:
        return {"position": 0, "total": len(enabled_skills), "percent": 0, "cycle": 1}

    current_skill = runs[-1].get("skill_id", 0)
    current_cycle = runs[-1].get("cycle", 1)

    try:
        position = enabled_skills.index(current_skill) + 1
    except ValueError:
        position = 0

    percent = round(position / len(enabled_skills) * 100) if enabled_skills else 0

    # Skills completed in current cycle
    skills_done = set()
    for r in reversed(runs):
        if r.get("cycle", 1) == current_cycle:
            skills_done.add(r.get("skill_id"))
        else:
            break

    return {
        "position": position,
        "total": len(enabled_skills),
        "percent": percent,
        "cycle": current_cycle,
        "current_skill_id": current_skill,
        "skills_completed_this_cycle": len(skills_done),
        "next_skill_id": enabled_skills[(enabled_skills.index(current_skill) + 1) % len(enabled_skills)]
                         if current_skill in enabled_skills else (enabled_skills[0] if enabled_skills else None),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Weekly summary data aggregation
# ─────────────────────────────────────────────────────────────────────────────

def build_weekly_summary_data(runs: list, scores: list, issues: dict) -> dict:
    """Aggregate last 7 days of data for the weekly summary email."""
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    def _parse_date(d):
        try:
            return datetime.fromisoformat(d)
        except Exception:
            return None

    this_week_runs = []
    prev_week_runs = []
    for r in runs:
        d = _parse_date(r.get("date", ""))
        if d is None:
            continue
        if d >= week_ago:
            this_week_runs.append(r)
        elif two_weeks_ago <= d < week_ago:
            prev_week_runs.append(r)

    this_week_scores = [r["score"] for r in this_week_runs if r.get("score") is not None]
    prev_week_scores = [r["score"] for r in prev_week_runs if r.get("score") is not None]

    avg_this = round(sum(this_week_scores) / len(this_week_scores), 1) if this_week_scores else 0
    avg_prev = round(sum(prev_week_scores) / len(prev_week_scores), 1) if prev_week_scores else 0

    active_issues = [i for i in issues.values() if i.get("status") == "active"]
    new_this_week = []
    for i in active_issues:
        d = _parse_date(i.get("first_seen", ""))
        if d is not None and d >= week_ago:
            new_this_week.append(i)
    critical_issues = [i for i in active_issues if i.get("severity") == "critical"]
    recurring = detect_recurring_issues(issues)

    # Skills run this week
    skills_run = [{"skill_id": r["skill_id"], "skill_name": r.get("skill_name", ""), "score": r["score"]}
                  for r in this_week_runs]

    # Top improvements and regressions (delta=0 is neutral, not a regression)
    score_changes = [(s, s.get("delta", 0)) for s in scores[-7:] if s.get("delta") is not None]
    improvements = [(s["skill_name"], d) for s, d in score_changes if d > 0]
    regressions = [(s["skill_name"], d) for s, d in score_changes if d < 0]

    return {
        "period_start": week_ago.strftime("%b %d"),
        "period_end": now.strftime("%b %d, %Y"),
        "runs_this_week": len(this_week_runs),
        "avg_score_this_week": avg_this,
        "avg_score_prev_week": avg_prev,
        "score_delta": round(avg_this - avg_prev, 1),
        "active_issues_total": len(active_issues),
        "new_issues_this_week": len(new_this_week),
        "critical_issues": len(critical_issues),
        "recurring_issues": len(recurring),
        "skills_run": skills_run,
        "top_improvements": improvements[:3],
        "regressions": regressions[:3],
        "critical_issue_list": critical_issues[:5],
        "recurring_issue_list": recurring[:5],
    }


def build_dashboard_snapshot(run: dict, findings: list, scores: list, issues: dict) -> dict:
    now = datetime.utcnow().isoformat()
    recent_runs = load_runs()[-30:]

    active_issues = [i for i in issues.values() if i.get("status") == "active"]
    critical_issues = [i for i in active_issues if i.get("severity") == "critical"]
    warning_issues = [i for i in active_issues if i.get("severity") == "warning"]

    avg_score = sum(s["score"] for s in scores[-23:]) / len(scores[-23:]) if scores else 0

    # Cycle progress
    from config import get_enabled_skills
    enabled = get_enabled_skills()
    cycle_progress = get_cycle_progress(recent_runs, enabled)

    # Recurring issues
    recurring = detect_recurring_issues(issues)

    # Predictive forecast
    forecast = build_predictive_forecast(scores)

    # Historical comparison
    comparison = get_historical_comparison(recent_runs, scores)

    # Email delivery stats from run history
    all_runs = load_runs()
    email_sent = sum(1 for r in all_runs if r.get("email_sent") is True)
    email_total = sum(1 for r in all_runs if "email_sent" in r)
    email_rate = round(email_sent / email_total * 100) if email_total > 0 else None

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
            "recurring_issues": len(recurring),
            "cycle_number": cycle_progress.get("cycle", 1),
            "cycle_percent": cycle_progress.get("percent", 0),
            "email_delivery_rate": email_rate,
            "github_issues_created": sum(1 for r in all_runs if r.get("github_issue")),
        },
        "recent_runs": recent_runs,
        "latest_findings": findings[:50],
        "score_history": scores[-46:],
        "active_issues_list": sorted(active_issues, key=lambda x: x.get("severity", ""), reverse=True)[:50],
        "recurring_issues": recurring[:20],
        "cycle_progress": cycle_progress,
        "forecast": forecast,
        "historical_comparison": comparison,
    }
    save_json("dashboard.json", snapshot)
    return snapshot
