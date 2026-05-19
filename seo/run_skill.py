#!/usr/bin/env python3
"""SEO Daily Skill Orchestrator — amulyagupta.in
23-Day Rotational SEO Intelligence Cycle
"""
import os
import sys
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from skills.skill_01_robots_txt import RobotsTxtSkill
from skills.skill_02_sitemap import SitemapSkill
from skills.skill_03_canonical import CanonicalSkill
from skills.skill_04_meta_titles import MetaTitlesSkill
from skills.skill_05_meta_descriptions import MetaDescriptionsSkill
from skills.skill_06_header_hierarchy import HeaderHierarchySkill
from skills.skill_07_opengraph import OpenGraphSkill
from skills.skill_08_twitter_meta import TwitterMetaSkill
from skills.skill_09_https_check import HttpsCheckSkill
from skills.skill_10_redirects import RedirectsSkill
from skills.skill_11_internal_links import InternalLinksSkill
from skills.skill_12_external_links import ExternalLinksSkill
from skills.skill_13_schema import SchemaSkill
from skills.skill_14_mobile import MobileSkill
from skills.skill_15_core_web_vitals import CoreWebVitalsSkill
from skills.skill_16_js_blocking import JsBlockingSkill
from skills.skill_17_image_optimization import ImageOptimizationSkill
from skills.skill_18_font_optimization import FontOptimizationSkill
from skills.skill_19_semantic_seo import SemanticSeoSkill
from skills.skill_20_internal_anchors import InternalAnchorsSkill
from skills.skill_21_faq_opportunities import FaqOpportunitiesSkill
from skills.skill_22_ai_search import AiSearchSkill
from skills.skill_23_competitor_intelligence import CompetitorIntelligenceSkill
from report_generator import generate_report

SKILLS = [
    RobotsTxtSkill,           # Day 01 — P1: Crawlability
    SitemapSkill,             # Day 02 — P1: Indexation
    CanonicalSkill,           # Day 03 — P4: Canonicalization
    MetaTitlesSkill,          # Day 04 — P6: Metadata
    MetaDescriptionsSkill,    # Day 05 — P6: Metadata
    HeaderHierarchySkill,     # Day 06 — P6: On-Page Structure
    OpenGraphSkill,           # Day 07 — P6: Social Metadata
    TwitterMetaSkill,         # Day 08 — P6: Social Metadata
    HttpsCheckSkill,          # Day 09 — P1: Security
    RedirectsSkill,           # Day 10 — P3: Redirect Health
    InternalLinksSkill,       # Day 11 — P7: Internal Linking
    ExternalLinksSkill,       # Day 12 — P3: External Links
    SchemaSkill,              # Day 13 — P5: Structured Data
    MobileSkill,              # Day 14 — P0: Mobile-First
    CoreWebVitalsSkill,       # Day 15 — P2: Performance
    JsBlockingSkill,          # Day 16 — P2: Performance
    ImageOptimizationSkill,   # Day 17 — P2: Performance
    FontOptimizationSkill,    # Day 18 — P2: Performance
    SemanticSeoSkill,         # Day 19 — P9: Content Quality
    InternalAnchorsSkill,     # Day 20 — P7: Anchor Text
    FaqOpportunitiesSkill,    # Day 21 — P9: Rich Snippets
    AiSearchSkill,            # Day 22 — P9: AI Search
    CompetitorIntelligenceSkill,  # Day 23 — P10: Strategy
]

SITE_URL = os.environ.get("SITE_URL", "https://amulyagupta.in")
SITE_ROOT = Path(__file__).parent.parent
SEO_DIR = Path(__file__).parent


def load_state() -> dict:
    state_file = SEO_DIR / "history" / "state.json"
    if state_file.exists():
        try:
            return json.loads(state_file.read_text())
        except Exception:
            pass
    return {"day": 0, "cycle": 1, "total_executions": 0}


def save_state(state: dict):
    state_file = SEO_DIR / "history" / "state.json"
    state_file.parent.mkdir(exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2))


def append_log(entry: dict):
    log_file = SEO_DIR / "history" / "log.jsonl"
    log_file.parent.mkdir(exist_ok=True)
    with log_file.open("a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def set_output(name: str, value: str):
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"{name}={value}\n")
    print(f"OUTPUT: {name}={value}")


def print_banner(skill_class, cycle: int, day: int):
    print("\n" + "=" * 65)
    print("  SEO AUTOMATION FRAMEWORK — amulyagupta.in")
    print(f"  Cycle {cycle} | Day {day}/23")
    print(f"  Skill #{skill_class.skill_number:02d}: {skill_class.name}")
    print(f"  Priority: {skill_class.priority} | Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 65 + "\n")


def main():
    state = load_state()

    # Resolve skill index
    override = os.environ.get("SKILL_OVERRIDE", "").strip()
    if override and override.isdigit():
        idx = int(override) - 1
        if not 0 <= idx < 23:
            print(f"Invalid SKILL_OVERRIDE={override}. Must be 1-23.")
            sys.exit(1)
    else:
        idx = state["day"] % 23

    skill_class = SKILLS[idx]
    day_in_cycle = idx + 1

    print_banner(skill_class, state["cycle"], day_in_cycle)

    # Execute skill
    try:
        skill = skill_class(site_url=SITE_URL, site_root=SITE_ROOT)
        result = skill.run()
    except Exception as e:
        print(f"[ERROR] Skill execution failed: {e}")
        traceback.print_exc()
        result = {
            "skill_name": skill_class.name,
            "skill_number": skill_class.skill_number,
            "health_score": 0,
            "status": "error",
            "findings": [{
                "id": "SYS_001",
                "title": "Skill Execution Error",
                "severity": "critical",
                "priority": "P0",
                "description": str(e),
                "recommendation": "Check skill code for Python errors or network issues.",
                "impact": "Audit incomplete — SEO issues may go undetected.",
                "pages_impacted": [],
                "auto_fixed": False
            }],
            "summary": f"Skill failed to execute: {e}",
            "auto_fixes_applied": [],
            "recommendations": []
        }

    # Enrich result
    result.update({
        "skill_number": skill_class.skill_number,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "cycle": state["cycle"],
        "day_in_cycle": day_in_cycle,
    })

    # Update state
    new_day = (state["day"] + 1) % 23
    completed_cycle = new_day == 0
    if completed_cycle:
        state["cycle"] += 1
    state["day"] = new_day
    state["total_executions"] = state.get("total_executions", 0) + 1
    state["last_execution"] = result["executed_at"]
    state["last_skill"] = skill_class.name
    save_state(state)

    # Log
    append_log(result)

    # Generate reports
    generate_report(result, SITE_ROOT)

    # Summary output
    findings = result.get("findings", [])
    crits = sum(1 for f in findings if f.get("severity") == "critical")
    warns = sum(1 for f in findings if f.get("severity") == "warning")
    fixes = len(result.get("auto_fixes_applied", []))

    print("\n" + "-" * 65)
    print(f"  RESULT: {result.get('status', 'unknown').upper()} | Score: {result.get('health_score', 0)}/100")
    print(f"  Findings: {len(findings)} total | Critical: {crits} | Warnings: {warns}")
    print(f"  Auto-fixes applied: {fixes}")
    if completed_cycle:
        print(f"  ✅ Cycle {state['cycle'] - 1} complete! Starting Cycle {state['cycle']}.")
    print("-" * 65 + "\n")

    if crits > 0:
        print("🚨 CRITICAL — IMMEDIATE SEO INTERVENTION REQUIRED")
        for f in findings:
            if f.get("severity") == "critical":
                print(f"   [{f.get('id')}] {f.get('title')}")
        print()

    # GitHub Actions outputs
    set_output("skill_name", skill_class.name)
    set_output("skill_number", str(skill_class.skill_number))
    set_output("health_score", str(result.get("health_score", 0)))
    set_output("status", result.get("status", "unknown"))

    if result.get("status") == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()
