# SEO Autonomous Intelligence Platform — amulyagupta.in

An autonomous SEO cloud runtime that executes one of 23 SEO skills every morning, persists findings to Google Sheets, emails executive reports, and proposes fixes via GitHub pull requests — all without human intervention.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Quick Start](#quick-start)
3. [GitHub Secrets Configuration](#github-secrets-configuration)
4. [Google Sheets Setup](#google-sheets-setup)
5. [Email Configuration](#email-configuration)
6. [Google Search Console Integration](#google-search-console-integration)
7. [PageSpeed Insights API](#pagespeed-insights-api)
8. [Dashboard Access](#dashboard-access)
9. [The 23-Skill Rotation System](#the-23-skill-rotation-system)
10. [Governance & Safety Rules](#governance--safety-rules)
11. [Safe Remediation Workflow](#safe-remediation-workflow)
12. [Daily Execution Schedule](#daily-execution-schedule)
13. [Manual Dispatch](#manual-dispatch)
14. [Data Persistence Layer](#data-persistence-layer)
15. [Incident Escalation](#incident-escalation)
16. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
GitHub Actions Scheduler (23:00 UTC = 04:30 IST)
        │
        ▼
seo/runtime.py  ─── Governance Gate (7 Hard Stops)
        │
        ├── seo/crawler.py         → Fetch all 11 site pages
        ├── seo/skills/skill_NN_*  → Execute 1 skill (day N of 23)
        ├── seo/memory.py          → Write local JSON telemetry
        ├── seo/sheets.py          → Append to Google Sheets (10 tabs)
        ├── seo/emailer.py         → Send HTML executive report
        └── seo/fixer.py           → Generate fixes → open GitHub PR
                                                          │
                                              Human Review Required
                                                          │
                                                    Manual Merge
```

**Persistence layer:**
- `seo/data/` — local JSON (committed by bot after every run)
- Google Sheets — cloud operational database (append-only, never overwritten)

**Dashboard:** `https://amulyagupta.in/seo/dashboard/` (PIN-protected static HTML, reads `seo/data/dashboard.json`)

---

## Quick Start

### Step 1 — Fork / clone the repository

The platform lives inside the main website repo. No separate repository needed.

### Step 2 — Configure GitHub Secrets

See [GitHub Secrets Configuration](#github-secrets-configuration) below.

### Step 3 — Create a Google Spreadsheet

1. Go to [Google Sheets](https://sheets.google.com) and create a new spreadsheet
2. Name it `SEO Intelligence — amulyagupta.in`
3. Copy the spreadsheet ID from the URL: `https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit`

### Step 4 — Create a Google Service Account

1. Open [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project (or use an existing one)
3. Enable **Google Sheets API** and **Google Drive API**
4. Go to **IAM & Admin → Service Accounts** → Create service account
5. Download the JSON key file
6. Share the Google Spreadsheet with the service account email (Editor access)
7. Add the JSON key content as the `GOOGLE_SERVICE_ACCOUNT_JSON` secret

### Step 5 — Initialize Sheets structure

Run this once after adding secrets:

```bash
export GOOGLE_SERVICE_ACCOUNT_JSON='<paste json key content>'
export GOOGLE_SHEETS_SPREADSHEET_ID='<your spreadsheet id>'
python seo/setup/init_sheets.py
```

Or trigger via workflow dispatch with `force_init: true`.

### Step 6 — Configure Gmail

See [Email Configuration](#email-configuration) below.

### Step 7 — Trigger the first run

Go to **Actions → SEO Autonomous Runtime → Run workflow** and click **Run workflow**.

---

## GitHub Secrets Configuration

Navigate to: `Settings → Secrets and variables → Actions → New repository secret`

| Secret | Required | Description |
|--------|----------|-------------|
| `GOOGLE_SHEETS_SPREADSHEET_ID` | ✅ Yes | ID from the Google Sheets URL |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | ✅ Yes | Full JSON key for the service account (paste raw JSON) |
| `EMAIL_USERNAME` | ✅ Yes | Gmail address used as sender (e.g. `yourname@gmail.com`) |
| `EMAIL_PASSWORD` | ✅ Yes | Gmail App Password (not your regular password — see below) |
| `PAGESPEEDKEY` | Recommended | Google PageSpeed Insights API key |
| `GOOGLE_SEARCH_CONSOLE_CREDENTIALS` | Optional | Service account JSON with GSC property access |
| `GOOGLE_ANALYTICS_CREDENTIALS` | Optional | Service account JSON with GA4 property access |

> **Security:** Secrets are never logged or printed. They are injected as environment variables only during workflow execution.

---

## Google Sheets Setup

The platform creates and maintains 10 sheets automatically:

| Sheet | Purpose | Append-Only? |
|-------|---------|-------------|
| `seo_runs` | Daily execution history | ✅ Yes |
| `seo_issues` | Issue lifecycle tracking | ✅ Yes |
| `seo_scores` | SEO score progression | ✅ Yes |
| `seo_reports` | Report archive | ✅ Yes |
| `seo_incidents` | Critical issue log | ✅ Yes |
| `seo_ai_visibility` | AI search tracking | ✅ Yes |
| `seo_competitors` | Competitor intelligence | ✅ Yes |
| `seo_cwv` | Core Web Vitals history | ✅ Yes |
| `seo_emails` | Email delivery log | ✅ Yes |
| `seo_runtime_logs` | Runtime telemetry | ✅ Yes |

**Hard Stop 5** enforces append-only writes at the code level — no row can ever be deleted or overwritten.

### Resetting the spreadsheet (emergency only)

If you need to start fresh:
1. Delete all rows in each sheet (but keep the header row)
2. Delete `seo/data/*.json` locally and commit
3. Re-run initialization

---

## Email Configuration

The platform sends daily HTML reports to `amulyagupta2001@gmail.com` using Gmail SMTP.

### Getting a Gmail App Password

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** (required for App Passwords)
3. Go to **App Passwords** → Select app: `Mail` → Select device: `Other (Custom name)` → Name it `SEO Runtime`
4. Copy the 16-character password
5. Add it as `EMAIL_PASSWORD` in GitHub Secrets
6. Add your Gmail address as `EMAIL_USERNAME`

### Email types sent

| Email | Trigger | Content |
|-------|---------|---------|
| Daily Morning Brief | Every run | Skill results, score, findings, forecast |
| Critical Alert | When critical issues found | Immediate escalation email |
| PR Notification | When fixer creates a PR | Link to review the PR |
| Weekly Summary | Every Sunday | 7-day aggregated intelligence |
| Cycle Completion | After skill 23 runs | Full 23-day cycle analytics |
| Runtime Failure Alert | On any failure | Error details, no site changes made |

---

## Google Search Console Integration

Skill 18 (`Search Console Intelligence`) supports live GSC data when credentials are configured.

### Setup

1. In [Google Cloud Console](https://console.cloud.google.com):
   - Enable the **Google Search Console API**
2. Use your existing service account or create a new one
3. Go to [Google Search Console](https://search.google.com/search-console)
4. Add the service account email as a **verified owner** of your property
5. Download the service account JSON key
6. Add as `GOOGLE_SEARCH_CONSOLE_CREDENTIALS` secret

---

## PageSpeed Insights API

Skills 5 (`Core Web Vitals`) and 15 (`Page Speed Deep Dive`) use the PageSpeed Insights API.

### Getting an API key

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Enable the **PageSpeed Insights API**
3. Create an API key under **APIs & Services → Credentials**
4. Add as `PAGESPEEDKEY` secret

> Without an API key, these skills fall back to HTML-based performance analysis. The API key removes the rate limit (100 requests/day free tier vs. 25,000/day with key).

---

## Dashboard Access

**URL:** `https://amulyagupta.in/seo/dashboard/`

**Access:** PIN-protected (set your own PIN on first visit — any 4+ character string)

**Data source:** `seo/data/dashboard.json` — updated after every daily run and committed to the repo. The dashboard reads this JSON file directly (no server required).

### Dashboard sections

| Tab | What it shows |
|-----|---------------|
| **Overview** | SEO health score, AI visibility, cycle progress, critical alerts, KPI grid |
| **Runtime** | 30-day run history, skill rotation progress, score trend chart |
| **Issues** | Full issue lifecycle table — first seen, severity, occurrences, status |
| **AI Visibility** | AI search readiness checks, llms.txt status, entity optimization |
| **Intelligence** | Predictive forecast, historical comparison, competitor analysis |
| **Reports** | Archive of all generated reports |
| **Memory** | Raw dashboard.json snapshot for debugging |

### Refreshing the dashboard

The dashboard auto-reads the latest `seo/data/dashboard.json` committed to the repo. Click **↺ Refresh** to reload. Data is updated every morning after the daily run.

---

## The 23-Skill Rotation System

The platform executes exactly **one skill per day** in a sequential 23-day cycle. After skill 23, the cycle restarts.

### Skill registry

| # | Skill | What it audits |
|---|-------|----------------|
| 1 | Technical Crawl Audit | HTTP status, crawl depth, page load, timeouts |
| 2 | Robots.txt & Sitemap Validation | robots.txt syntax, sitemap structure, URL coverage |
| 3 | Canonical & Redirects Audit | Canonical tags, redirect chains, self-referencing |
| 4 | Structured Data Audit | JSON-LD schema completeness and correctness |
| 5 | Core Web Vitals | LCP, CLS, INP, TTFB via PageSpeed Insights API |
| 6 | Meta Tags & Open Graph | Title/description uniqueness, length, OG tags |
| 7 | Internal Linking Analysis | Orphan pages, link depth, anchor text distribution |
| 8 | Content Quality Audit | Word count, readability, thin content detection |
| 9 | Duplicate Content Detection | Near-duplicate titles, descriptions, body content |
| 10 | Keyword Optimization Audit | Target keyword presence, density, placement |
| 11 | AI Search Readiness | llms.txt, entity markup, conversational optimization |
| 12 | Heading Hierarchy Audit | H1-H6 structure, missing/duplicate H1s |
| 13 | Image Optimization Audit | Alt text, lazy loading, WebP/AVIF format usage |
| 14 | Mobile Friendliness Audit | Viewport, touch targets, responsive design |
| 15 | Page Speed Deep Dive | Resource size, render-blocking, compression |
| 16 | Indexation Coverage Audit | Noindex tags, X-Robots-Tag, index coverage gaps |
| 17 | Backlink & Outbound Link Audit | External link quality, broken links |
| 18 | Search Console Intelligence | GSC index status, sitemap submission |
| 19 | Analytics Insights | Tracking implementation, GA4 setup |
| 20 | Competitor SEO Analysis | SERP overlap, semantic gaps |
| 21 | Semantic Coverage Audit | Topical authority, content gaps |
| 22 | Anchor Text Optimization | Internal anchor text diversity, over-optimization |
| 23 | AI Citation Readiness | AI overview signals, FAQ schema, citation structure |

### Skill groups (phase-gated rollout)

| Group | Skills | Use case |
|-------|--------|----------|
| `1` | Foundational (2, 6, 7, 12) | First deploy — safe, non-destructive |
| `2` | Technical SEO (1, 4, 5, 13, 14, 15) + Group 1 | After validating Group 1 |
| `3` | All 23 skills | Full platform — default |

Set `ENABLED_SKILL_GROUP` in workflow inputs. Default is `3` (all skills).

---

## Governance & Safety Rules

7 mandatory Hard Stops are enforced in `seo/governance.py`. They cannot be bypassed by configuration.

| # | Rule | Enforced Where |
|---|------|----------------|
| HS1 | Exactly one skill per day, sequential rotation | `runtime.py`, `governance.py` |
| HS2 | No auto-merge, no direct push to main | `workflow`, `governance.py` |
| HS3 | Dashboard + observability must be operational | `governance.py` |
| HS4 | Pre-execution context validation | `governance.py` |
| HS5 | Google Sheets append-only — no history overwrite | `sheets.py`, `governance.py` |
| HS6 | Experimental branch isolation warnings | `governance.py` |
| HS7 | Caveman/Humaniser lifecycle separation | `governance.py`, `runtime.py` |

Any violation raises `HardStopViolation`, halts execution immediately, and sends a failure alert email. No site changes are made on failure.

---

## Safe Remediation Workflow

The runtime **never** auto-deploys fixes. All proposed changes follow this path:

```
SEO Runtime detects issue
         │
         ▼
seo/fixer.py generates fix file(s)
         │
         ▼
GitHub Actions creates a Pull Request
  branch: seo-fix/run-<number>
  base:   main
         │
         ▼
  ⚠ HUMAN REVIEW REQUIRED ⚠
         │
         ▼
   Manual approval
         │
         ▼
   Manual merge
```

### Protected file types

These files **never** auto-deploy without human approval:

- `robots.txt`
- `sitemap.xml`
- Canonical tags in HTML pages
- Schema / JSON-LD markup
- Meta tags

### Fixable issue categories

The auto-fixer handles:
- `schema` — adds missing JSON-LD blocks
- `sitemap` — adds missing URLs to sitemap.xml
- `robots` — fixes missing AI crawler allowances
- `ai-crawlers` — adds AI bot rules to robots.txt

---

## Daily Execution Schedule

| Time | Schedule |
|------|---------|
| 04:30 AM IST | Daily SEO skill execution (23:00 UTC) |
| 04:30 AM IST Monday | Weekly summary email (Sunday 23:00 UTC) |

### Cron expressions

```yaml
- cron: '0 23 * * *'    # Daily runtime
- cron: '0 23 * * 0'    # Sunday weekly summary
```

### Execution window: 04:30–07:00 IST

The workflow has a 45-minute timeout. Typical runtime is 3–8 minutes.

---

## Manual Dispatch

Go to **Actions → SEO Autonomous Runtime → Run workflow** to trigger manually.

### Options

| Input | Default | Description |
|-------|---------|-------------|
| `skill_override` | `auto` | Force a specific skill (1–23) or leave blank for sequential rotation |
| `enabled_skill_group` | `3` | `1`=Foundational, `2`=+Technical, `3`=All 23 |
| `force_init` | `false` | Re-initialize Google Sheets structure (first deploy only) |
| `send_weekly_summary` | `false` | Send weekly summary in addition to daily brief |

### Forcing a specific skill

Set `skill_override` to `1`–`23` to run a specific skill regardless of rotation.  
Manual dispatch bypasses the one-skill-per-day governance rule (Hard Stop 1).

---

## Data Persistence Layer

### Local JSON (`seo/data/`)

Committed to the repository by the `SEO Runtime Bot` after every run:

| File | Contents |
|------|---------|
| `dashboard.json` | Full dashboard snapshot for the live dashboard |
| `runs.json` | Array of all execution records (capped at 500) |
| `issues.json` | Dict of all detected issues with lifecycle data |
| `scores.json` | Array of all skill scores across all cycles |
| `state.json` | Current cycle position: `last_skill_id`, `last_run_date`, `cycle_number` |

### Google Sheets (cloud)

Same data appended to 10 sheets — provides long-term historical persistence beyond the local JSON cap.

### Issue lifecycle tracking

Each issue is tracked by a stable ID derived from `skill_id + category + url + title`:

```python
issue = {
    "issue_id": "abc123def456",
    "first_seen": "2026-05-01T00:00:00",
    "last_seen": "2026-05-28T18:13:32",
    "skill_id": 4,
    "severity": "critical",
    "category": "schema",
    "url": "https://amulyagupta.in/",
    "title": "Missing WebSite schema",
    "status": "active",
    "occurrences": 7
}
```

Issues with `occurrences >= 3` are flagged as **recurring** in the dashboard and weekly summary.

---

## Incident Escalation

Critical incidents trigger:

1. An immediate critical alert email (before the daily brief)
2. An entry in `seo_incidents` Google Sheet
3. A red `CRITICAL — IMMEDIATE SEO INTERVENTION REQUIRED` banner in the dashboard

### Critical escalation triggers

- Deindexation risks (`noindex` on important pages)
- `robots.txt` blocking Googlebot
- Sitemap returning non-200 status
- Core Web Vitals LCP > 4000ms
- Structured data parse errors
- All pages returning errors (crawl failure)
- Runtime execution failure

---

## Troubleshooting

### Email not being sent

1. Check `EMAIL_USERNAME` and `EMAIL_PASSWORD` are set in GitHub Secrets
2. Ensure it's a **Gmail App Password**, not your regular Gmail password
3. Ensure 2-Step Verification is enabled on the Gmail account
4. Check the `seo_emails` sheet for delivery status and error messages

### Google Sheets not receiving data

1. Verify `GOOGLE_SHEETS_SPREADSHEET_ID` is correct (just the ID, not the full URL)
2. Ensure the service account email has **Editor** access to the spreadsheet
3. Verify the service account JSON is pasted as raw JSON in the secret (not base64 encoded)
4. Check the GitHub Actions log for `Google Sheets init failed:` messages

### Dashboard showing stale data

The dashboard reads `seo/data/dashboard.json` from the repository. If the file hasn't been updated:
1. Check the **Commit dashboard data** step in the workflow run log
2. If the push failed, re-run the workflow
3. Clear browser cache and reload

### Skill execution failing

1. Check the **Run SEO Runtime** step in the workflow log
2. Look for `HARD STOP` messages — these are governance violations with clear descriptions
3. Check if the site is reachable: `curl -I https://amulyagupta.in`
4. For crawl failures, the runtime sends a failure alert email automatically

### PR not being created after fixer runs

- Check if an open `seo-fix/*` PR already exists — the fixer skips duplicate PRs
- Close or merge the existing PR, then re-run the workflow
- Check the **Run SEO Fixer** step for the exit code: `0`=fixes generated, `2`=nothing to fix, `1`=error

### `FORCE_INIT` — when to use it

Use `force_init: true` in workflow dispatch **only on first deploy** to initialize Google Sheets tabs. Running it again is safe but unnecessary — it recreates missing sheets without touching existing data.

---

## File Reference

```
seo/
├── runtime.py              Main orchestrator
├── config.py               Environment config, skill names, sheet names
├── governance.py           7 Hard Stops enforcement
├── memory.py               Local JSON persistence + intelligence functions
├── sheets.py               Google Sheets client (append-only)
├── emailer.py              HTML email builder + SMTP delivery
├── crawler.py              Site page fetcher
├── fixer.py                Auto-fix generator → PR creator
├── weekly_summary.py       Sunday weekly digest sender
├── requirements.txt        Python dependencies
├── skills/
│   ├── base.py             BaseSEOSkill, Finding, SkillResult
│   ├── skill_01_*.py  …   23 individual skill implementations
│   └── skill_23_*.py
├── setup/
│   └── init_sheets.py      One-time Google Sheets initializer
├── data/                   Runtime telemetry (committed by bot)
│   ├── dashboard.json
│   ├── runs.json
│   ├── issues.json
│   ├── scores.json
│   └── state.json
└── dashboard/
    └── index.html          Live SEO Command Center (static HTML)

.github/workflows/
└── seo-runtime.yml         GitHub Actions workflow

admin/seo/
└── index.html              /admin/seo/ redirect to dashboard

docs/seo-platform/
└── README.md               This file
```

---

## Security Notes

- The dashboard is PIN-protected client-side. The PIN is stored in `localStorage`. Do not share the dashboard URL publicly.
- `meta name="robots" content="noindex, nofollow"` prevents search engines from indexing the dashboard.
- GitHub Secrets are never logged. The workflow prints a credential check warning if `EMAIL_USERNAME` or `EMAIL_PASSWORD` are missing, but never prints their values.
- The runtime never has write access to the production site beyond `seo/data/` JSON telemetry. All site-content changes go through the PR → human review → manual merge path.

---

*Built and maintained autonomously by the SEO Runtime Bot · amulyagupta.in*
