import os

SITE_URL = os.environ.get("SITE_URL", "https://amulyagupta.in").rstrip("/")
REPORT_EMAIL = os.environ.get("REPORT_EMAIL", "amulagupta2001@gmail.com")
GMAIL_SENDER = os.environ.get("GMAIL_SENDER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
PAGESPEED_API_KEY = os.environ.get("PAGESPEED_API_KEY", "")
GOOGLE_SHEETS_SPREADSHEET_ID = os.environ.get("GOOGLE_SHEETS_SPREADSHEET_ID", "")
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_SHEETS_API_KEY = os.environ.get("GOOGLE_SHEETS_API_KEY", "")
SKILL_OVERRIDE = os.environ.get("SKILL_OVERRIDE", "auto")
FORCE_INIT = os.environ.get("FORCE_INIT", "false").lower() == "true"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "")

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
