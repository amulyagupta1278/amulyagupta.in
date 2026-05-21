import os

SITE_URL = os.environ.get("SITE_URL", "https://amulyagupta.in").rstrip("/")
REPORT_EMAIL = os.environ.get("REPORT_EMAIL", "amulagupta2001@gmail.com")
GMAIL_SENDER = os.environ.get("GMAIL_SENDER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
PAGESPEED_API_KEY = os.environ.get("PAGESPEED_API_KEY", "")
GOOGLE_SHEETS_SPREADSHEET_ID = os.environ.get("GOOGLE_SHEETS_SPREADSHEET_ID", "")
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_SHEETS_API_KEY = os.environ.get("GOOGLE_SHEETS_API_KEY", "")
GOOGLE_SEARCH_CONSOLE_CREDENTIALS = os.environ.get("GOOGLE_SEARCH_CONSOLE_CREDENTIALS", "")
SKILL_OVERRIDE = os.environ.get("SKILL_OVERRIDE", "auto")
FORCE_INIT = os.environ.get("FORCE_INIT", "false").lower() == "true"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "")
GITHUB_REF = os.environ.get("GITHUB_REF", "")
IS_MANUAL_DISPATCH = os.environ.get("GITHUB_EVENT_NAME", "schedule") == "workflow_dispatch"

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

SITE_PAGES = [
    "/",
    "/about.html",
    "/projects.html",
    "/experience.html",
    "/amulya-gupta.html",
    "/contact.html",
    "/blog/index.html",
    "/blog/post-1-mlops-pipeline.html",
    "/blog/post-2-mlops-stack.html",
    "/blog/ai-ml-guide-2026.html",
    "/privacy.html",
]

SKILL_NAMES = [
    "Technical Crawl Audit",
    "Robots.txt & Sitemap Validation",
    "Canonical & Redirects Audit",
    "Structured Data Audit",
    "Core Web Vitals",
    "Meta Tags & Open Graph Audit",
    "Internal Linking Analysis",
    "Content Quality Audit",
    "Duplicate Content Detection",
    "Keyword Optimization Audit",
    "AI Search Readiness",
    "Heading Hierarchy Audit",
    "Image Optimization Audit",
    "Mobile Friendliness Audit",
    "Page Speed Deep Dive",
    "Indexation Coverage Audit",
    "Backlink & Outbound Link Audit",
    "Search Console Intelligence",
    "Analytics Insights",
    "Competitor SEO Analysis",
    "Semantic Coverage Audit",
    "Anchor Text Optimization",
    "AI Citation Readiness",
]

SHEET_NAMES = [
    "seo_runs",
    "seo_issues",
    "seo_scores",
    "seo_reports",
    "seo_incidents",
    "seo_ai_visibility",
    "seo_competitors",
    "seo_cwv",
    "seo_emails",
    "seo_runtime_logs",
]

SEO_SCORE_THRESHOLDS = {"good": 80, "needs_work": 50}
CWV_THRESHOLDS = {
    "lcp": {"good": 2500, "poor": 4000},
    "cls": {"good": 0.1, "poor": 0.25},
    "fid": {"good": 100, "poor": 300},
    "inp": {"good": 200, "poor": 500},
    "ttfb": {"good": 800, "poor": 1800},
}

# ---------------------------------------------------------------------------
# Incremental Skill Rollout — Phase-gated activation
#
# Group 1 — Safe Foundational (deploy first, validate before advancing)
#   Robots/Sitemap, Meta/OG, Internal Linking, Heading Hierarchy
#
# Group 2 — Technical SEO (deploy after Group 1 is stable)
#   Crawl Audit, Schema, Core Web Vitals, Images, Mobile, Page Speed
#
# Group 3 — Advanced Intelligence (deploy last)
#   Canonicals, Content Quality, Duplicate Content, Keywords, AI Readiness,
#   Indexation, Backlinks, Search Console, Analytics, Competitors,
#   Semantic Coverage, Anchor Text, AI Citations
#
# Set ENABLED_SKILL_GROUP env var to control which groups are active.
# All groups ≤ the configured number are activated cumulatively.
# ---------------------------------------------------------------------------
SKILL_GROUPS: dict[int, list[int]] = {
    1: [2, 6, 7, 12],                                   # Foundational
    2: [1, 4, 5, 13, 14, 15],                           # Technical SEO
    3: [3, 8, 9, 10, 11, 16, 17, 18, 19, 20, 21, 22, 23],  # Advanced
}

ENABLED_SKILL_GROUP = int(os.environ.get("ENABLED_SKILL_GROUP", "1"))


def get_enabled_skills() -> list[int]:
    """Return sorted skill IDs for all groups up to ENABLED_SKILL_GROUP."""
    enabled: list[int] = []
    for g in range(1, ENABLED_SKILL_GROUP + 1):
        enabled.extend(SKILL_GROUPS.get(g, []))
    return sorted(enabled)
