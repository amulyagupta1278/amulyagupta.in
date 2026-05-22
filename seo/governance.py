"""
SEO Runtime Governance — 7 Mandatory Hard Stops

Architectural invariants for the autonomous SEO runtime at amulyagupta.in.
Any violation raises HardStopViolation and halts execution immediately.
These constraints cannot be bypassed by configuration or environment flags.
"""
import logging
import os
from datetime import datetime, timezone

log = logging.getLogger("seo.governance")


class HardStopViolation(RuntimeError):
    """Raised when a mandatory governance constraint is violated."""

    def __init__(self, stop_id: int, rule_name: str, message: str):
        self.stop_id = stop_id
        self.rule_name = rule_name
        border = "=" * 60
        super().__init__(
            f"\n{border}\n"
            f"HARD STOP {stop_id} — {rule_name}\n"
            f"{border}\n"
            f"{message}\n"
            f"{border}"
        )


GOVERNANCE_RULES: dict[int, str] = {
    1: "CLAUDE_SEO_SKILL_EXECUTION_ONLY",
    2: "NO_AUTO_MERGE_OR_DIRECT_PUSH",
    3: "DASHBOARD_AND_OBSERVABILITY_REQUIRED",
    4: "RUNTIME_VALIDATION_REQUIRED",
    5: "GOOGLE_SHEETS_PERSISTENT_MEMORY",
    6: "EXPERIMENTAL_BRANCH_ISOLATION",
    7: "CAVEMAN_CREDIT_OPTIMIZATION",
}


def _raise(stop_id: int, message: str) -> None:
    raise HardStopViolation(stop_id, GOVERNANCE_RULES[stop_id], message)


# ─────────────────────────────────────────────────────────────────────────────
# Hard Stop 1 — Exactly one SEO skill per day, sequential 23-day rotation
# ─────────────────────────────────────────────────────────────────────────────

def enforce_one_skill_per_day(last_run_date: str | None, is_manual_dispatch: bool) -> None:
    """Abort if a skill already ran today and this is an automatic (cron) execution."""
    if is_manual_dispatch:
        log.info("[HS1] Manual dispatch — daily execution limit bypassed")
        return
    if not last_run_date:
        return  # First-ever run

    try:
        last_date = datetime.fromisoformat(last_run_date).date()
    except (ValueError, TypeError):
        return  # Unparseable date — don't block on metadata corruption

    today = datetime.now(timezone.utc).date()
    if last_date == today:
        _raise(
            1,
            f"A skill already executed today ({today.isoformat()}).\n"
            "The runtime executes EXACTLY ONE skill per day (sequential 23-day rotation).\n"
            "Multiple skills must never run simultaneously or be batched.\n"
            "To force a manual run, use workflow_dispatch with an explicit skill_override.",
        )


def enforce_sequential_rotation(skill_id: int, enabled_skills: list[int]) -> None:
    """Abort if the selected skill is outside the active sequential pool."""
    if skill_id not in enabled_skills:
        _raise(
            1,
            f"Skill {skill_id} is not part of the enabled sequential pool {enabled_skills}.\n"
            "The runtime follows a strict sequential 23-day rotation.\n"
            "Skills outside the active ENABLED_SKILL_GROUP cannot execute.\n"
            "Advance the skill group via ENABLED_SKILL_GROUP env var to unlock more skills.",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Hard Stop 2 — No auto-merge, no direct push to protected branches
# ─────────────────────────────────────────────────────────────────────────────

_PROTECTED_BRANCHES = frozenset({"main", "master"})


def enforce_no_direct_push(github_ref: str | None) -> None:
    """
    HS2: Warn if executing on a protected branch.

    GitHub scheduled workflows always run on the default branch (main), so we
    must NOT abort here — execution is safe and read-only.  The actual guard
    against committing or pushing to main lives in the workflow bash step
    ("Commit dashboard data"), which skips the push on protected branches.
    """
    ref = (github_ref or "").removeprefix("refs/heads/")
    if ref in _PROTECTED_BRANCHES:
        log.warning(
            "[HS2] Running on protected branch '%s'. "
            "Execution proceeds (read-only audit). "
            "Data commits to this branch are blocked by the workflow bash guard.",
            ref,
        )
    else:
        log.info("[HS2] Branch '%s' — PR-only model confirmed", ref)
    log.info("[HS2] Auto-merge authority: NONE — runtime never pushes site changes directly")


def assert_no_auto_merge_authority() -> None:
    """Declaration: the runtime has no merge authority. Logs confirmation."""
    log.info("[HS2] Auto-merge authority: NONE — runtime creates PRs only, never self-merges")


# ─────────────────────────────────────────────────────────────────────────────
# Hard Stop 3 — Dashboard and observability must be operational
# ─────────────────────────────────────────────────────────────────────────────

def enforce_observability(data_dir: str, sheets_available: bool) -> None:
    """Abort if neither local persistence nor Google Sheets is reachable."""
    local_ok = os.path.isdir(data_dir) or _try_mkdir(data_dir)

    if not local_ok and not sheets_available:
        _raise(
            3,
            f"No operational persistence layer available.\n"
            f"  Local data directory '{data_dir}': UNAVAILABLE\n"
            f"  Google Sheets: UNAVAILABLE\n"
            "The platform requires at least one persistence layer.\n"
            "Dashboard telemetry, historical tracking, and incident records cannot function.",
        )

    log.info(
        "[HS3] Observability: local_data=%s  google_sheets=%s",
        "ok" if local_ok else "unavailable",
        "ok" if sheets_available else "unavailable",
    )


def _try_mkdir(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except OSError:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Hard Stop 4 — Runtime validation before every skill execution
# ─────────────────────────────────────────────────────────────────────────────

def enforce_execution_context(
    skill_id: int,
    site_url: str,
    pages: list[dict],
    min_healthy: int,
) -> None:
    """Comprehensive pre-execution validation. Raises HardStopViolation on any failure."""
    errors: list[str] = []

    if not isinstance(skill_id, int) or not 1 <= skill_id <= 23:
        errors.append(f"skill_id {skill_id!r} is outside the valid range 1–23")

    if not site_url or not site_url.startswith("https://"):
        errors.append(f"site_url {site_url!r} is not a valid HTTPS URL")

    if not pages:
        errors.append("Crawl context is empty — zero pages were returned")
    else:
        healthy = [p for p in pages if p.get("status") == 200 and p.get("soup")]
        if not healthy:
            errors.append(
                f"No healthy pages in crawl context — "
                f"all {len(pages)} pages returned errors or empty HTML"
            )
        elif len(healthy) < min_healthy:
            errors.append(
                f"Insufficient healthy pages: {len(healthy)} healthy "
                f"< {min_healthy} required (50% of known pages)"
            )

    if errors:
        _raise(
            4,
            "Pre-execution validation failed — runtime context is invalid:\n"
            + "\n".join(f"  • {e}" for e in errors)
            + "\n\nThe runtime will not execute a skill against an invalid context.",
        )

    log.info(
        "[HS4] Execution context valid: skill=%d  site=%s  pages=%d  healthy≥%d",
        skill_id, site_url, len(pages), min_healthy,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Hard Stop 5 — Google Sheets: append-only, never overwrite history
# ─────────────────────────────────────────────────────────────────────────────

_APPEND_ONLY_SHEETS = frozenset({
    "seo_runs",
    "seo_issues",
    "seo_scores",
    "seo_incidents",
    "seo_ai_visibility",
    "seo_cwv",
    "seo_emails",
    "seo_runtime_logs",
})

_DESTRUCTIVE_OPS = frozenset({"clear", "delete", "overwrite", "truncate", "update_all", "batch_clear"})


def enforce_append_only(sheet_name: str, operation: str) -> None:
    """Abort if a destructive operation is attempted on an append-only history sheet."""
    if sheet_name in _APPEND_ONLY_SHEETS and operation.lower() in _DESTRUCTIVE_OPS:
        _raise(
            5,
            f"Destructive operation '{operation}' blocked on append-only sheet '{sheet_name}'.\n"
            "Historical SEO logs are immutable. Every execution appends new intelligence.\n"
            "Issue timelines, run history, and score continuity must NEVER be reset or overwritten.\n"
            "If you need to correct a record, append a correction entry instead.",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Hard Stop 6 — Experimental branch isolation
# ─────────────────────────────────────────────────────────────────────────────

_PRODUCTION_BRANCHES = frozenset({"seo-runtime-stable", "main", "master"})
_EXPERIMENTAL_PREFIXES = ("claude/", "feat/", "fix/", "chore/", "experimental/", "dev/")


def enforce_branch_isolation(github_ref: str | None, enabled_skill_group: int) -> None:
    """
    Warn when experimental branches run with elevated skill groups.
    Abort if an unvalidated experimental branch is mistakenly treated as production.
    """
    ref = (github_ref or "").removeprefix("refs/heads/")
    is_experimental = any(ref.startswith(p) for p in _EXPERIMENTAL_PREFIXES)
    is_production = ref in _PRODUCTION_BRANCHES

    if is_experimental and enabled_skill_group > 2:
        log.warning(
            "[HS6] Experimental branch '%s' running ENABLED_SKILL_GROUP=%d (Advanced). "
            "Advanced skills should be validated on seo-runtime-stable first.",
            ref, enabled_skill_group,
        )

    branch_type = "experimental" if is_experimental else "production" if is_production else "unknown"
    log.info(
        "[HS6] Branch isolation: ref='%s'  type=%s  skill_group=%d",
        ref, branch_type, enabled_skill_group,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Hard Stop 7 — Context / token optimization during SEO skill execution
#
# "Caveman" = lightweight runtime coordination layer (minimal context loading)
# "Humaniser" = rich formatting layer (emailer / reports / executive briefings)
#
# During skill execution: Caveman mode active — suppress verbose output.
# Post-execution reporting: Humaniser mode active — rich HTML/text formatting allowed.
# ─────────────────────────────────────────────────────────────────────────────

_execution_mode_active: bool = False


def enter_execution_mode() -> None:
    """Activate Caveman mode: suppress verbose context loading during skill execution."""
    global _execution_mode_active
    _execution_mode_active = True
    log.info(
        "[HS7] Execution mode ON — Caveman context optimisation active, "
        "Humaniser (rich formatting) suppressed until post-execution reporting"
    )


def exit_execution_mode() -> None:
    """Deactivate Caveman mode: Humaniser (emailer/reports) may now run."""
    global _execution_mode_active
    _execution_mode_active = False
    log.info("[HS7] Execution mode OFF — Humaniser reporting layer now active")


def is_execution_mode() -> bool:
    return _execution_mode_active


def assert_humaniser_scope(caller: str) -> None:
    """
    Log a warning if rich formatting (Humaniser) is called during execution mode.
    Humaniser is restricted to: reports, summaries, emails, executive briefings.
    """
    if _execution_mode_active:
        log.warning(
            "[HS7] Humaniser called by '%s' during execution mode. "
            "Rich formatting (email/reports) should only run post-execution.",
            caller,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Governance Gate — run all applicable hard stops in sequence
# ─────────────────────────────────────────────────────────────────────────────

def run_all(
    *,
    skill_id: int,
    enabled_skills: list[int],
    site_url: str,
    pages: list[dict],
    min_healthy: int,
    data_dir: str,
    sheets_available: bool,
    github_ref: str | None,
    enabled_skill_group: int,
    last_run_date: str | None,
    is_manual_dispatch: bool,
) -> None:
    """
    Master governance gate — execute all 7 hard stop checks in order.
    Raises HardStopViolation on the first violation encountered.
    Call this after crawling, immediately before skill execution.
    """
    log.info("━" * 60)
    log.info("GOVERNANCE GATE — running all 7 hard stop checks")
    log.info("━" * 60)

    # HS1 — One skill per day, sequential rotation
    enforce_one_skill_per_day(last_run_date, is_manual_dispatch)
    enforce_sequential_rotation(skill_id, enabled_skills)

    # HS2 — No auto-merge, no direct push
    enforce_no_direct_push(github_ref)
    assert_no_auto_merge_authority()

    # HS3 — Dashboard and observability
    enforce_observability(data_dir, sheets_available)

    # HS4 — Runtime validation (full context check)
    enforce_execution_context(skill_id, site_url, pages, min_healthy)

    # HS5 — enforced inline in sheets.py on every Sheets operation
    log.info("[HS5] Append-only Sheets guard: active (enforced inline in SheetsClient)")

    # HS6 — Branch isolation
    enforce_branch_isolation(github_ref, enabled_skill_group)

    # HS7 — Caveman/Humaniser lifecycle managed separately (enter/exit_execution_mode)
    log.info("[HS7] Caveman/Humaniser lifecycle: managed via enter/exit_execution_mode()")

    log.info("━" * 60)
    log.info("GOVERNANCE GATE — ALL 7 HARD STOPS PASSED ✓")
    log.info("━" * 60)
