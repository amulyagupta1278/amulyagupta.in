#!/usr/bin/env python3
"""Run all SEO skills without persistence, email, or rotation side effects."""

import argparse
import importlib
import inspect
import json
import os
import sys
from pathlib import Path

SKILL_MODULES = {
    1: "technical_crawl", 2: "robots_sitemap", 3: "canonical_redirects",
    4: "structured_data", 5: "core_web_vitals", 6: "meta_tags_og",
    7: "internal_linking", 8: "content_quality", 9: "duplicate_content",
    10: "keyword_optimization", 11: "ai_search_readiness",
    12: "heading_hierarchy", 13: "image_optimization",
    14: "mobile_friendliness", 15: "page_speed", 16: "indexation",
    17: "backlink_outbound", 18: "search_console", 19: "analytics_insights",
    20: "competitor_analysis", 21: "semantic_coverage", 22: "anchor_text",
    23: "ai_citation_readiness",
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default="https://amulyagupta.in")
    parser.add_argument("--fetch-origin", help="Fetch from this origin while validating canonical production URLs")
    parser.add_argument("--json", dest="json_path")
    parser.add_argument("--markdown", dest="markdown_path")
    parser.add_argument("--fail-on", choices=("critical", "warning", "none"), default="critical")
    return parser.parse_args()


def markdown_report(report: dict) -> str:
    lines = [f"# SEO validation — {report['target']}", ""]
    for result in report["results"]:
        lines += [f"## {result['skill_id']:02d}. {result['skill_name']}", "",
                  f"Score: **{result['score']}/100** · Findings: **{len(result['findings'])}**", ""]
        for finding in result["findings"]:
            lines.append(f"- **{finding['severity'].upper()}** — {finding['title']}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    os.environ["SITE_URL"] = args.target.rstrip("/")
    root = Path(__file__).resolve().parent
    sys.path[:0] = [str(root), str(root / "skills")]
    import crawler
    from base import BaseSEOSkill

    if args.fetch_origin:
        original_fetch = crawler.fetch
        canonical = args.target.rstrip("/")
        fetch_origin = args.fetch_origin.rstrip("/")

        def fetch_from_origin(url, timeout=15):
            if not url.startswith(canonical):
                return original_fetch(url, timeout)
            local_url = fetch_origin + url.removeprefix(canonical)
            result = original_fetch(local_url, timeout)
            try:
                result["html"] = result["html"].encode("latin-1").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
            result["url"] = url
            result["redirect_url"] = None
            return result

        crawler.fetch = fetch_from_origin

    pages = crawler.crawl_all_pages(delay=0)
    unhealthy = [page for page in pages if page.get("status") != 200 or not page.get("soup")]
    if unhealthy:
        print(json.dumps({"error": "crawl_failed", "pages": unhealthy}, default=str))
        return 2

    results = []
    for skill_id, suffix in SKILL_MODULES.items():
        module = importlib.import_module(f"skill_{skill_id:02d}_{suffix}")
        skill_class = next(
            cls for _, cls in inspect.getmembers(module, inspect.isclass)
            if issubclass(cls, BaseSEOSkill) and cls is not BaseSEOSkill
        )
        result = skill_class().run(pages)
        results.append({
            "skill_id": result.skill_id,
            "skill_name": result.skill_name,
            "score": result.score,
            "findings": result.findings_as_dicts(),
            "metadata": result.metadata,
        })

    report = {"target": args.target.rstrip("/"), "fetch_origin": args.fetch_origin,
              "pages": len(pages), "results": results}
    rendered_json = json.dumps(report, indent=2, ensure_ascii=False, default=str)
    rendered_markdown = markdown_report(report)
    if args.json_path:
        Path(args.json_path).write_text(rendered_json + "\n", encoding="utf-8")
    if args.markdown_path:
        Path(args.markdown_path).write_text(rendered_markdown + "\n", encoding="utf-8")
    if not args.json_path and not args.markdown_path:
        print(rendered_markdown)

    severities = {f["severity"] for r in results for f in r["findings"]}
    if args.fail_on == "critical" and "critical" in severities:
        return 1
    if args.fail_on == "warning" and severities.intersection({"critical", "warning"}):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
