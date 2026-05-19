import hashlib
import json
import logging
import os
from datetime import datetime
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
    """Return the next skill ID to run from the enabled skill set.

    Cycles sequentially through enabled_skills. If the last-run skill is not
    in the enabled set (e.g. the group was just narrowed), starts from the
    beginning of the enabled list.
    """
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


def build_dashboard_snapshot(run: dict, findings: list, scores: list, issues: dict) -> dict:
    now = datetime.utcnow().isoformat()
    recent_runs = load_runs()[-30:]

    active_issues = [i for i in issues.values() if i.get("status") == "active"]
    critical_issues = [i for i in active_issues if i.get("severity") == "critical"]
    warning_issues = [i for i in active_issues if i.get("severity") == "warning"]

    avg_score = sum(s["score"] for s in scores[-23:]) / len(scores[-23:]) if scores else 0

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
        },
        "recent_runs": recent_runs,
        "latest_findings": findings[:50],
        "score_history": scores[-46:],
        "active_issues_list": sorted(active_issues, key=lambda x: x.get("severity", ""), reverse=True)[:50],
    }
    save_json("dashboard.json", snapshot)
    return snapshot
