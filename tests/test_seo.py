import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "seo"), str(ROOT / "seo" / "skills")]

from bs4 import BeautifulSoup
import memory
from skill_04_structured_data import has_schema_type
from skill_10_keyword_optimization import FINDING_CATEGORY, Skill10KeywordOptimization, matches_topic
from skill_14_mobile_friendliness import Skill14MobileFriendliness


class SiteFixtureTests(unittest.TestCase):
    pages = [
        "index.html", "about.html", "projects.html", "experience.html",
        "amulya-gupta.html", "contact.html", "blog/index.html",
        "blog/post-1-mlops-pipeline.html", "blog/post-2-mlops-stack.html",
        "blog/ai-ml-guide-2026.html", "privacy.html",
    ]

    def test_pages_have_unique_titles_and_valid_json_ld(self):
        titles = []
        for relative in self.pages:
            soup = BeautifulSoup((ROOT / relative).read_text(encoding="utf-8"), "lxml")
            self.assertIsNotNone(soup.find("main") or soup.find("article"), relative)
            self.assertEqual(1, len(soup.find_all("h1")), relative)
            titles.append(soup.title.get_text(strip=True))
            for script in soup.find_all("script", type="application/ld+json"):
                json.loads(script.string)
        self.assertEqual(len(titles), len(set(titles)))

    def test_blogposting_satisfies_article(self):
        self.assertTrue(has_schema_type(["BlogPosting"], "Article"))

    def test_topic_matching_normalizes_punctuation(self):
        self.assertTrue(matches_topic("AI/ML Roadmap 2026", ["ai ml roadmap"]))

    def test_keyword_findings_use_dashboard_category(self):
        html = """<html><head><title>Unrelated</title><meta name="description" content="Unrelated"></head>
        <body><main><h1>Unrelated</h1><p>Unrelated copy.</p></main></body></html>"""
        page = {"url": "https://amulyagupta.in/contact.html", "status": 200,
                "html": html, "soup": BeautifulSoup(html, "lxml")}
        findings = Skill10KeywordOptimization().run([page]).findings
        self.assertTrue(findings)
        self.assertEqual({FINDING_CATEGORY}, {finding.category for finding in findings})

    def test_max_width_is_not_a_mobile_failure(self):
        html = '<meta name="viewport" content="width=device-width, initial-scale=1"><main style="max-width:760px"></main>'
        page = {"url": "https://amulyagupta.in/", "status": 200,
                "html": html, "soup": BeautifulSoup(html, "lxml")}
        self.assertEqual([], Skill14MobileFriendliness().run([page]).findings)


class IssueLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous = memory.DATA_DIR
        memory.DATA_DIR = self.temp.name

    def tearDown(self):
        memory.DATA_DIR = self.previous
        self.temp.cleanup()

    def test_issue_resolves_and_reopens_without_losing_history(self):
        finding = {"category": "schema", "url": "https://example.test/",
                   "title": "Missing schema", "severity": "warning"}
        first = memory.reconcile_skill_issues(4, [finding], "run-1")
        issue = first["active"][0]
        self.assertEqual("active", issue["state"])

        second = memory.reconcile_skill_issues(4, [], "run-2")
        self.assertEqual("resolved", second["resolved"][0]["state"])

        third = memory.reconcile_skill_issues(4, [finding], "run-3")
        reopened = third["active"][0]
        self.assertEqual("active", reopened["state"])
        self.assertEqual(2, reopened["occurrences"])
        self.assertEqual(1, reopened["consecutive_occurrences"])
        self.assertEqual(issue["first_seen"], reopened["first_seen"])

    def test_unverified_run_does_not_resolve_issue(self):
        finding = {"category": "crawl", "url": "https://example.test/",
                   "title": "Temporary failure", "severity": "warning"}
        memory.reconcile_skill_issues(1, [finding], "run-1")
        result = memory.reconcile_skill_issues(1, [], "run-2", verified=False)
        self.assertEqual([], result["resolved"])
        self.assertEqual("active", next(iter(memory.load_issues().values()))["state"])

    def test_false_positive_can_be_invalidated(self):
        finding = {"category": "schema", "url": "https://example.test/",
                   "title": "False positive", "severity": "warning"}
        issue = memory.reconcile_skill_issues(4, [finding], "run-1")["active"][0]
        invalid = memory.invalidate_issue(issue["issue_id"], "Rule corrected", "run-2")
        self.assertEqual("invalid", invalid["state"])
        self.assertEqual("Rule corrected", invalid["resolution_reason"])

    def test_score_history_preserves_previous_score_and_delta(self):
        memory.append_score(10, "Keyword Optimization", 60, "run-1")
        memory.append_score(10, "Keyword Optimization", 100, "run-2")
        latest = memory.load_score_history()[-1]
        self.assertEqual(60, latest["prev_score"])
        self.assertEqual(40, latest["delta"])

    def test_cwv_summary_uses_raw_records_and_survives_other_runs(self):
        records = [{"url": "https://example.test/", "strategy": "mobile",
                    "lcp_ms": 2400, "cls": 0.08, "inp_ms": 180, "ttfb_ms": 500}]
        measured = memory.build_cwv_summary(records)
        self.assertEqual(2400, measured["lcp_avg"])
        memory.save_json("dashboard.json", {"cwv_summary": measured})
        snapshot = memory.build_dashboard_snapshot({}, [], [], {}, cwv_records=[])
        self.assertEqual(measured, snapshot["cwv_summary"])


if __name__ == "__main__":
    unittest.main()
