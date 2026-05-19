from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Finding:
    title: str
    description: str
    severity: str  # critical | warning | info
    category: str
    url: str = ""
    recommendation: str = ""
    evidence: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "category": self.category,
            "url": self.url,
            "recommendation": self.recommendation,
            "evidence": self.evidence[:500] if self.evidence else "",
        }


@dataclass
class SkillResult:
    skill_id: int
    skill_name: str
    score: int
    findings: list[Finding] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def critical_count(self):
        return sum(1 for f in self.findings if f.severity == "critical")

    @property
    def warning_count(self):
        return sum(1 for f in self.findings if f.severity == "warning")

    def findings_as_dicts(self):
        return [f.to_dict() for f in self.findings]

    def summary_line(self) -> str:
        return (f"[Skill {self.skill_id:02d}] {self.skill_name} — Score: {self.score}/100 "
                f"| Critical: {self.critical_count} | Warnings: {self.warning_count}")


class BaseSEOSkill:
    SKILL_ID: int = 0
    SKILL_NAME: str = ""

    def run(self, pages: list[dict]) -> SkillResult:
        raise NotImplementedError

    def result(self, score: int, findings: list[Finding], metadata: dict = None) -> SkillResult:
        return SkillResult(
            skill_id=self.SKILL_ID,
            skill_name=self.SKILL_NAME,
            score=max(0, min(100, score)),
            findings=findings,
            metadata=metadata or {},
        )

    def clamp_score(self, base: int, penalty_per_critical: int = 15,
                    penalty_per_warning: int = 5, findings: list = None) -> int:
        findings = findings or []
        score = base
        for f in findings:
            if f.severity == "critical":
                score -= penalty_per_critical
            elif f.severity == "warning":
                score -= penalty_per_warning
        return max(0, min(100, score))
