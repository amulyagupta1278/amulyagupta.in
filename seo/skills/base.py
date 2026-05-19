"""Base class for all SEO skills."""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
import requests
from bs4 import BeautifulSoup


class BaseSkill(ABC):
    name: str = "Base Skill"
    priority: str = "P0"
    skill_number: int = 0

    def __init__(self, site_url: str, site_root: Path):
        self.site_url = site_url.rstrip("/")
        self.site_root = Path(site_root)
        self._html_files: list[Path] | None = None
        self._parsed: dict[str, BeautifulSoup] = {}

    @property
    def html_files(self) -> list[Path]:
        if self._html_files is None:
            files: list[Path] = []
            for p in ["*.html", "blog/*.html"]:
                files.extend(self.site_root.glob(p))
            self._html_files = [f for f in files if "ironatlas" not in str(f)]
        return self._html_files

    def parse(self, path: Path) -> BeautifulSoup:
        key = str(path)
        if key not in self._parsed:
            self._parsed[key] = BeautifulSoup(
                path.read_text(encoding="utf-8", errors="replace"), "lxml"
            )
        return self._parsed[key]

    def page_url(self, path: Path) -> str:
        rel = path.relative_to(self.site_root)
        return f"{self.site_url}/{rel}"

    def fetch(self, url: str, timeout: int = 10) -> requests.Response | None:
        try:
            return requests.get(
                url, timeout=timeout, allow_redirects=True,
                headers={"User-Agent": "SEOAuditBot/1.0 (+https://amulyagupta.in)"}
            )
        except Exception:
            return None

    def finding(
        self, id: str, title: str, severity: str, priority: str,
        description: str, recommendation: str,
        impact: str = "", pages: list | None = None, auto_fixed: bool = False
    ) -> dict:
        return {
            "id": id, "title": title, "severity": severity, "priority": priority,
            "description": description, "recommendation": recommendation,
            "impact": impact, "pages_impacted": pages or [], "auto_fixed": auto_fixed
        }

    def score(self, findings: list) -> int:
        if not findings:
            return 100
        weights = {"critical": 25, "warning": 10, "info": 2}
        return max(0, 100 - sum(weights.get(f.get("severity", "info"), 0) for f in findings))

    def status(self, score: int) -> str:
        return "ok" if score >= 80 else "warning" if score >= 50 else "critical"

    def result(self, findings: list, summary: str, auto_fixes: list | None = None,
               recommendations: list | None = None) -> dict:
        s = self.score(findings)
        return {
            "skill_name": self.name,
            "skill_number": self.skill_number,
            "health_score": s,
            "status": self.status(s),
            "findings": findings,
            "summary": summary,
            "auto_fixes_applied": auto_fixes or [],
            "recommendations": recommendations or [],
        }

    @abstractmethod
    def run(self) -> dict[str, Any]:
        ...
