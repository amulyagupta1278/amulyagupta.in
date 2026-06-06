# Branch #15 Master Architecture Blueprint
## `branch-15-master` — Single Source of Truth for amulyagupta.in SEO Platform

**Date:** 2026-06-05  
**Status:** Implementation in progress  
**Replaces:** All prior feature branches (see Merge Strategy)

---

## 0. Executive Summary

This document is the authoritative design specification for `branch-15-master` — the production-grade, commercialization-ready version of the autonomous SEO platform for `amulyagupta.in`.

The platform as of 2026-06-05:
- **Score:** 60/100 (was 70+ before Skill 5 LCP failures)
- **Active issues:** 50 (4 critical CWV, 18 internal-linking, 20 meta, +8 other)
- **Runtime:** Dark for 8 days (YAML parse crash killed every cron since 2026-05-28)
- **Fixed in this branch:** YAML crash, relative-href crawl blindness, blocking fonts, missing OG tags, N+1 I/O, crawler relative href resolution, pre-flight secret logging

---

## 1. Recommended Folder Structure

```
amulyagupta.in/
├── .github/
│   └── workflows/
│       ├── deploy.yml              # GitHub Pages deployment (unchanged)
│       └── seo-runtime.yml         # SEO runtime — 3 jobs (YAML fixed)
│
├── blog/                           # Blog HTML pages (unchanged)
├── assets/                         # Static assets (unchanged)
│
├── seo/                            # SEO Platform root
│   ├── runtime.py                  # Main entrypoint — orchestrates daily run
│   ├── governance.py               # 7 Hard Stops — HardStopViolation exceptions
│   ├── memory.py                   # JSON persistence layer (+ batch_upsert_issues)
│   ├── crawler.py                  # HTTP crawler + BeautifulSoup (urljoin fixed)
│   ├── config.py                   # All env-var config in one place
│   ├── emailer.py                  # All email templates and SMTP delivery
│   ├── sheets.py                   # Google Sheets client (append-only)
│   ├── fixer.py                    # Auto-fixer: schema/sitemap/robots → PR
│   ├── notify_pr.py                # PR email notification (extracted from YAML)
│   ├── weekly_summary.py           # Weekly intelligence email
│   ├── requirements.txt            # Python dependencies
│   │
│   ├── skills/                     # 23 pluggable skill modules
│   │   ├── __init__.py             # SKILL_REGISTRY: {1: Skill01, ..., 23: Skill23}
│   │   ├── base.py                 # BaseSEOSkill, Finding, SkillResult
│   │   ├── skill_01_technical_crawl.py
│   │   ├── skill_02_robots_sitemap.py
│   │   ├── skill_03_canonical_redirects.py
│   │   ├── skill_04_structured_data.py
│   │   ├── skill_05_core_web_vitals.py
│   │   ├── skill_06_meta_tags_og.py
│   │   ├── skill_07_internal_linking.py
│   │   ├── skill_08_content_quality.py
│   │   ├── skill_09_duplicate_content.py
│   │   ├── skill_10_keyword_optimization.py
│   │   ├── skill_11_ai_search_readiness.py
│   │   ├── skill_12_heading_hierarchy.py
│   │   ├── skill_13_image_optimization.py
│   │   ├── skill_14_mobile_friendliness.py
│   │   ├── skill_15_page_speed.py
│   │   ├── skill_16_indexation.py
│   │   ├── skill_17_backlink_outbound.py
│   │   ├── skill_18_search_console.py
│   │   ├── skill_19_analytics_insights.py
│   │   ├── skill_20_competitor_analysis.py
│   │   ├── skill_21_semantic_coverage.py
│   │   ├── skill_22_anchor_text.py
│   │   └── skill_23_ai_citation_readiness.py
│   │
│   ├── data/                       # Runtime data (committed to repo for dashboard)
│   │   ├── dashboard.json          # Dashboard snapshot (latest run)
│   │   ├── runs.json               # Full run history
│   │   ├── scores.json             # Score history per skill per run
│   │   ├── issues.json             # Active issue registry (keyed by MD5 ID)
│   │   ├── state.json              # Scheduler state: next skill, cycle number
│   │   ├── email_log.json          # Email delivery log
│   │   └── pr_body.txt             # Latest fixer PR body (transient)
│   │
│   └── dashboard/
│       └── index.html              # PIN-gated dashboard (Chart.js, 8 tabs)
│
├── index.html                      # Portfolio homepage
├── about.html
├── projects.html
├── experience.html
├── contact.html
├── amulya-gupta.html
├── privacy.html
├── sitemap.xml
├── robots.txt
└── BRANCH_15_BLUEPRINT.md          # This document
```

---

## 2. Workflow Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  GitHub Actions: seo-runtime.yml                                    │
│                                                                     │
│  TRIGGERS                                                           │
│  ├─ schedule: "0 23 * * *"   → seo-runtime job (daily, all days)  │
│  ├─ schedule: "0 23 * * 0"   → weekly-summary job (Sundays only)  │
│  └─ workflow_dispatch          → both jobs (manual override)        │
│                                                                     │
│  ─────────────────────────────────────────────────────             │
│  JOB 1: seo-runtime  (45 min timeout)                              │
│                                                                     │
│  [Checkout] → [pip install] → [python runtime.py]                  │
│       │                              │                             │
│       │              ┌───────────────▼────────────────┐           │
│       │              │  runtime.py execution flow      │           │
│       │              │                                 │           │
│       │              │  preflight_log()                │           │
│       │              │  ↓                              │           │
│       │              │  Pre-crawl governance gate      │           │
│       │              │  (HS2, HS3, HS6 — fail fast)   │           │
│       │              │  ↓                              │           │
│       │              │  get_next_skill() / override   │           │
│       │              │  ↓                              │           │
│       │              │  HS1 one-per-day check          │           │
│       │              │  ↓                              │           │
│       │              │  crawl_all_pages() [11 pages]  │           │
│       │              │  ↓                              │           │
│       │              │  governance.run_all() [HS1-7]  │           │
│       │              │  ↓                              │           │
│       │              │  skill_cls().run(pages)         │           │
│       │              │  ↓                              │           │
│       │              │  batch_upsert_issues()  [O(1)] │           │
│       │              │  ↓                              │           │
│       │              │  append_run / append_score      │           │
│       │              │  ↓                              │           │
│       │              │  build_dashboard_snapshot()    │           │
│       │              │  ↓                              │           │
│       │              │  emailer.send_report()          │           │
│       │              └─────────────────────────────────┘           │
│       │                                                             │
│       ├─ [fixer.py] → exit 0: create seo-fix/run-N PR              │
│       │             → exit 2: skip (nothing to fix)                │
│       │             → exit 1: log error, skip                      │
│       │                                                             │
│       └─ [Commit dashboard data to main] (always, skip-ci)         │
│                                                                     │
│  JOB 2: weekly-summary  (20 min timeout, Sundays only)             │
│  [Checkout] → [pip install] → [python weekly_summary.py]           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  DATA FLOW                                                          │
│                                                                     │
│  skill result → batch_upsert_issues() → issues.json               │
│              → append_run()           → runs.json                 │
│              → append_score()         → scores.json               │
│              → build_dashboard_snapshot() → dashboard.json        │
│              → sheets.append() ×5     → Google Sheets             │
│              → emailer.send_report()  → Gmail → inbox             │
│                                                                     │
│  On failure: handle_failure() → sheets.log_runtime()              │
│                               → emailer.send_report() [alert]     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Communication / Template Architecture

The platform has **5 email template categories** all routed through `emailer.send_report()`:

| Template | Trigger | Builder | Subject Pattern |
|---|---|---|---|
| Daily brief | End of every skill run | `emailer.build_morning_brief()` | `[SEO] Skill XX/23 — Score Y/100` |
| Critical alert | Any critical finding | `emailer.build_critical_alert()` | `[SEO ALERT] N critical issues` |
| Runtime failure | `handle_failure()` | Inline in `runtime.py` | `[SEO ALERT] Runtime failure` |
| PR notification | After `seo-fix` PR created | `notify_pr.py` | `[SEO FIX PR] Auto-Fix Created` |
| Weekly summary | Sundays | `emailer.build_weekly_summary()` | `[SEO WEEKLY] Weekly Intelligence` |

**Consolidation needed (technical debt):**
- `handle_failure()` in `runtime.py` has an inline 40-line HTML template. Should be extracted to `emailer.build_failure_alert()` to centralize all HTML in `emailer.py`.
- All 5 templates share `_BASE_STYLES` CSS from `emailer.py` but `notify_pr.py` and `handle_failure()` each carry inline styles. Should import `_BASE_STYLES`.

**PR Body template** lives in `fixer.py:main()` — produces `seo/data/pr_body.txt`. Template is tightly coupled to fixer logic; acceptable for now.

---

## 4. Skill Execution Architecture

```
runtime.py
    │
    ├─ crawl_all_pages()           # 11 HTTP fetches, 0.5s delay each (~6s total)
    │       returns list[PageDict]  # {url, status, elapsed_ms, html, soup, ...}
    │
    ├─ SKILL_REGISTRY[skill_id]()  # instantiate skill class
    │
    └─ skill.run(pages) → SkillResult
              │
              ├─ BaseSEOSkill.clamp_score(base, findings)
              ├─ BaseSEOSkill.result(score, findings, metadata)
              └─ SkillResult {skill_id, skill_name, score, findings[], metadata{}}
                      │
                      └─ Finding {title, description, severity, category, url,
                                  recommendation, evidence}

Skill groups (phase gating via ENABLED_SKILL_GROUP):
  Group 1 (Foundational):  skills 2, 6, 7, 12
  Group 2 (+Technical):    + 1, 4, 5, 13, 14, 15
  Group 3 (All 23):        all skills active  ← CURRENT DEFAULT

Specialty sheet routing (hardcoded in runtime.py):
  skills 11, 23 → seo_ai_visibility sheet
  skills  5, 15 → seo_cwv sheet (reads metadata["cwv_records"])
  skill  20     → seo_competitors sheet

External API dependencies per skill:
  Skill 05, 15: PageSpeed API (PAGESPEED_API_KEY)  — 8 calls per skill run
  Skill 18:     Google Search Console API
  Skill 19:     Google Analytics API
  Skills 1-4,
  6-14, 16-17,
  20-23:        No external API — pure HTML/crawl analysis
```

---

## 5. Merge Strategy

### Branch Dependency Map

```
main (BROKEN — YAML crash)
  │
  ├─ claude/vibrant-maxwell-eYsY4  [YAML fix + HTML fixes + notify_pr.py]
  │     │
  │     └─ branch-15-master  [THIS BRANCH — all optimizations]
  │
  └─ seo-runtime-stable  [legacy, superseded]

seo-fix/run-N branches  [auto-generated by fixer, merge or close each]
```

### Recommended Merge Order

1. **Merge branch-15-master → main** (via PR, human review)  
   This absorbs everything from `claude/vibrant-maxwell-eYsY4` (PR #15 content).  
   After merge: close PR #15 as superseded.

2. **Close `seo-runtime-stable`** — fully superseded, no unique content.

3. **Clear stale `seo-fix/run-N` branches** — merge or close all open ones before merging branch-15-master to avoid conflicts on `seo/data/` files.

4. **After merge to main:** trigger `workflow_dispatch` with `skill_override=8` to resume from Skill 8 (Content Quality Audit), skipping the 8-day gap.

---

## 6. Migration Plan

### Pre-merge Checklist
- [ ] Confirm PR #15 has no merge conflicts with main
- [ ] Close or merge all open `seo-fix/run-N` PRs
- [ ] Verify `seo/data/state.json` has `next_skill: 8` (resume after last run was Skill 7)
- [ ] Confirm all 7 GitHub Secrets are set: `GOOGLE_SHEETS_SPREADSHEET_ID`, `GOOGLE_SERVICE_ACCOUNT_JSON`, `EMAIL_USERNAME`, `EMAIL_PASSWORD`, `PAGESPEEDKEY`, `GOOGLE_SEARCH_CONSOLE_CREDENTIALS`, `GOOGLE_ANALYTICS_CREDENTIALS`

### Post-merge Steps (day of merge)
1. Merge branch-15-master → main via GitHub PR
2. Verify GitHub Pages redeploys (deploy.yml triggers on push to main)
3. Trigger `workflow_dispatch` → `skill_override=8`, `enabled_skill_group=3`
4. Confirm email arrives at `amulyagupta2001@gmail.com`
5. Check dashboard at `https://amulyagupta.in/seo/dashboard/index.html` (PIN: 1278) shows Run 8

### Skill Resume Schedule (post-migration)
Skills 1–7 already ran. Remaining 16 skills need 16 days to complete cycle 1:
- Day 1 (post-merge): Skill 08 — Content Quality Audit
- Day 2: Skill 09 — Duplicate Content
- Day 3: Skill 10 — Keyword Optimization
- ... (daily until Skill 23)
- Cycle completion email triggers on Skill 23

---

## 7. Release Plan

### v1.0 — Production Stable (branch-15-master, THIS RELEASE)
**Status:** Ready to merge  
**Scope:**
- YAML workflow fix (resumes 8-day outage)
- 11 HTML pages: absolute nav hrefs, non-blocking fonts, privacy.html OG tags
- `crawler.py`: urljoin relative href resolution (fixes Skill 7 permanently)
- `memory.py`: `batch_upsert_issues()` — O(1) I/O
- `runtime.py`: pre-flight secret logging, batched persistence
- `notify_pr.py`: extracted PR email notification module

**Expected score improvement:** 60 → 75–80 after Skill 7 re-runs with urljoin fix

### v1.1 — Monitoring & Observability (next sprint, ~2 weeks)
- `governance.py`: Split `run_all()` into `run_pre_crawl()` + `run_post_crawl()` to eliminate duplicate governance checks
- `runtime.py`: Per-skill execution timing (`skill_duration_ms` in run record)
- `emailer.py`: Extract `handle_failure()` inline HTML to `build_failure_alert()`
- `sheets.py`: Batch cell updates via `batch_update()` instead of per-cell `update_cell()`
- Add staleness warning to dashboard when last run > 48h ago

### v1.2 — Reliability & Retry (sprint 2)
- `crawler.py`: Retry logic (3 attempts, exponential backoff) on fetch failures
- `fixer.py`: Schema fix via category-based matching instead of brittle title string
- `memory.py`: JSON schema validation on `load_issues()` / `load_runs()`
- `config.py`: Cross-validate `state.json` skill_id against `runs.json` last skill at startup

### v2.0 — Commercialization (future)
See Section 10.

---

## 8. Risk Analysis

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| `governance.run_all()` still duplicates pre-crawl checks | High (currently) | Low — only wasted CPU, no correctness issue | v1.1 split |
| `seo-fix/run-N` branch pile-up | High | Low — manual cleanup needed monthly | Add branch auto-cleanup to fixer workflow |
| PageSpeed API quota exhaustion | Medium | Medium — Skill 5/15 silently return 50 | Pre-flight now logs missing key; v1.2 quota check |
| Google Sheets API rate limit | Low | Low — JSON fallback exists | Sheets `available` flag prevents crash |
| cron delay/skip (GitHub Actions backlog) | Medium | Low — run just retries next day | No action; HS1 allows `is_manual_dispatch` bypass |
| `state.json` corruption | Low | Medium — wrong skill runs | v1.2 cross-validation |
| `issues.json` partial write (power loss mid-save) | Very Low | High — data loss | v1.2 atomic write (write to `.tmp` then `rename`) |
| GitHub Pages deploy fails after merge | Low | High — site down | deploy.yml has retry; monitor post-merge |

---

## 9. Technical Debt Cleanup Plan

### Priority 1 — Fix NOW (in branch-15-master)
| Item | File | Status |
|---|---|---|
| `crawler.get_all_links()` ignores relative hrefs | `crawler.py:53-65` | **FIXED** (urljoin) |
| `upsert_issue()` O(N) file I/O in loop | `memory.py:88-114` | **FIXED** (batch_upsert_issues) |
| Runtime.py uses loop instead of batch | `runtime.py:334-352` | **FIXED** |
| No pre-flight secret visibility | `runtime.py` | **FIXED** (preflight_log) |
| YAML parse crash (notify_pr inline Python) | `seo-runtime.yml` | **FIXED** (notify_pr.py) |
| All 11 HTML nav hrefs relative | all HTML files | **FIXED** (absolute paths) |
| Blocking Google Fonts | all HTML files | **FIXED** (preload+onload) |
| privacy.html missing OG/Twitter tags | `privacy.html` | **FIXED** |

### Priority 2 — v1.1 Sprint
| Item | File | Debt Type |
|---|---|---|
| Duplicate governance: individual calls + `run_all()` | `runtime.py:195-296` | Duplication |
| `handle_failure()` inline HTML email template | `runtime.py:130-164` | Duplication (vs emailer.py) |
| `build_dashboard_snapshot()` recomputes forecast already computed 30 lines earlier | `runtime.py:412-428` | Redundant computation |
| `append_email_log()` load+save per email | `memory.py` | O(N) I/O pattern |
| `sheets.update_issue_status()` one `update_cell` per row | `sheets.py:129-148` | N Sheets API calls |
| `load_runs()` called twice per execution | `runtime.py:367,417` | Redundant I/O |

### Priority 3 — v1.2 Sprint
| Item | File | Debt Type |
|---|---|---|
| No retry on crawler fetch failures | `crawler.py:12-32` | Missing fallback |
| `fixer.py` schema matching by exact title string | `fixer.py:103-174` | Brittleness |
| `_execution_mode_active` global not thread-safe | `governance.py` | Latent bug |
| Hardcoded skill-ID dispatch for specialty sheets | `runtime.py:379-401` | Violates open/closed |
| No atomic writes for JSON files | `memory.py:save_json` | Data loss risk |
| Missing score-range validation in validate_skill_result | `runtime.py:86-95` | Missing validation |

### Won't Fix / Accept
- `weekly_summary.py` recomputes forecast/comparison independently — acceptable; runs in a separate job once a week, isolation is a feature
- `parse()` ignores `base_url` parameter — no callers pass base_url other than SITE_URL; dead param acceptable
- HS7 global state not thread-safe — sequential single-process execution by design; would only matter if parallelism is added

---

## 10. Commercialization Readiness Assessment

### Current State: Developer Tool → NOT YET Commercial

The platform is a personal-use SEO audit system. To sell or license it requires:

#### What's Already Production-Grade
- ✅ Modular 23-skill architecture (clean `BaseSEOSkill` interface, easy to add skills)
- ✅ Governance hard stops (audit trail, no auto-merge, append-only history)
- ✅ Dual persistence (JSON + Google Sheets) — survives credential failures
- ✅ Full observability: runs, scores, issues, emails, incidents all tracked
- ✅ Clean separation: crawler / governance / memory / skills / emailer are independent modules
- ✅ Email reporting with HTML templates (professional appearance)

#### What Needs to Change for Commercialization

**Multi-tenancy** (biggest gap):
- Everything is hardcoded to `amulyagupta.in` in `config.py` (`SITE_URL`, `SITE_PAGES`, email addresses, fixer schema fixes)
- Commercial version needs: `TenantConfig` object, dynamic `SITE_PAGES` discovery, per-tenant Google Sheets, per-tenant email
- Estimated effort: 2–3 weeks to extract tenant config; 2 weeks to build onboarding flow

**SaaS infrastructure:**
- Currently runs as GitHub Actions on a personal repo — not scalable for 100+ tenants
- Commercial version: hosted worker (Cloud Run / AWS Lambda), per-tenant cron scheduling, centralized results DB (Postgres/Supabase)
- `fixer.py` creates PRs via `gh` CLI — needs GitHub App authentication for multi-tenant PR creation
- Estimated effort: 4–6 weeks for infrastructure

**Billing & access control:**
- No auth layer on dashboard (PIN-only, trivial to bypass)
- No skill tier gating beyond the 3 groups
- Commercial version: JWT/OAuth dashboard, skill groups map to pricing tiers (Starter/Pro/Enterprise)

**AI-enhanced reporting (differentiator):**
- Currently pure rule-based audits — no LLM
- Adding Claude API calls for: natural-language issue descriptions, prioritized fix recommendations, competitive narrative
- Estimated effort: 1–2 weeks per skill for AI enhancement
- Cost at scale: ~$0.001–0.005 per skill run with haiku; $0.02–0.10 with sonnet

**Legal & compliance:**
- Privacy policy already exists (`privacy.html`) — good start
- Need ToS, data processing agreement, GDPR data deletion for EU customers
- SEO audit tools that crawl third-party sites need robots.txt compliance (already has `SEO-Runtime-Bot` UA)

#### Commercialization Readiness Score: 3/10

| Dimension | Score | Blocker |
|---|---|---|
| Core audit logic | 8/10 | None — production ready |
| Multi-tenancy | 1/10 | Complete rearchitecture needed |
| Infrastructure | 2/10 | GitHub Actions not scalable |
| Dashboard UX | 5/10 | PIN auth too weak for SaaS |
| Reporting quality | 7/10 | HTML emails are solid |
| AI differentiation | 0/10 | No LLM integration yet |
| Billing/Auth | 0/10 | Not implemented |
| Legal | 3/10 | Basic privacy policy only |

#### Recommended Commercialization Path (12-month)

```
Month 1-2:  Ship v1.0 (this branch) + v1.1 monitoring
Month 3-4:  Extract TenantConfig, add SITE_PAGES auto-discovery
Month 5-6:  Build SaaS API layer (FastAPI), per-tenant scheduling
Month 7-8:  Dashboard auth (Supabase Auth), skill tier gating
Month 9-10: Add Claude API for AI-enhanced reporting (haiku, 3 skills first)
Month 11:   Billing integration (Stripe), onboarding flow
Month 12:   Beta launch with 10 paying customers
```

---

## Appendix: Issues Fixed in This Branch

### Critical Fixes
1. **YAML parse crash** — `seo-runtime.yml` inline Python at column 0 terminated YAML block scalar. Fixed: extracted to `seo/notify_pr.py`. Unblocks 8 days of dark runtime.

2. **Crawler relative href blindness** — `get_all_links()` only matched `href.startswith("/")`. All relative hrefs (`about.html`, `../index.html`) were invisible, making every page appear orphaned. Fixed: `urllib.parse.urljoin()` resolves all hrefs correctly.

3. **Blocking Google Fonts** — LCP 4108–4691ms on 4 mobile pages. Fixed: `preload+onload` pattern with `<noscript>` fallback on all 11 HTML pages.

4. **N+1 file I/O in issue persistence** — 20 findings = 40 file ops. Fixed: `batch_upsert_issues()` does 1 load + 1 save for any number of findings.

### Improvements
5. **Pre-flight secret logging** — `preflight_log()` logs availability of all 5 optional secrets at run start. Diagnoses silent skill degradation in CI logs.

6. **privacy.html OG/Twitter tags** — Added `og:title`, `og:description`, `og:url`, `og:image`, `twitter:card`, `twitter:title`, `twitter:description`, `twitter:image`.

7. **Absolute nav hrefs** — All 11 HTML pages: relative hrefs → absolute paths starting with `/`.

---

*Blueprint generated by Claude Code (claude-sonnet-4-6) on branch-15-master.*
*Next action: merge to main, trigger workflow_dispatch with skill_override=8.*
