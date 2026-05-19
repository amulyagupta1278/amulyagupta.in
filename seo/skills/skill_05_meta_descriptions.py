"""Skill 05 — Meta Description Quality Audit"""
from .base import BaseSkill

CTA_WORDS = ["learn", "discover", "explore", "read", "view", "check", "see", "get", "find", "build"]


class MetaDescriptionsSkill(BaseSkill):
    name = "Meta Description Quality"
    priority = "P6"
    skill_number = 5

    def run(self) -> dict:
        findings = []
        seen_descs: dict[str, str] = {}
        desc_data = []

        for f in self.html_files:
            soup = self.parse(f)
            page = str(f.relative_to(self.site_root))
            meta_desc = soup.find("meta", attrs={"name": "description"})
            desc = meta_desc.get("content", "").strip() if meta_desc else ""
            desc_data.append((page, desc))

            if not desc:
                findings.append(self.finding(
                    "DESC_001", f"Missing meta description: {page}", "critical", "P6",
                    f"{page} has no meta description tag.",
                    "Add a compelling 140–160 char description with primary keyword and CTA.",
                    "Google will auto-generate a snippet — often poorly chosen — hurting CTR.",
                    pages=[page]
                ))
                continue

            length = len(desc)
            if length < 100:
                findings.append(self.finding(
                    "DESC_002", f"Description too short ({length} chars): {page}", "warning", "P6",
                    f"Description on {page} is only {length} chars. Ideal: 140–160.",
                    "Expand with benefit statement + keyword + CTA to reach 140-160 chars.",
                    "Short descriptions leave SERP real estate unused; Google may rewrite them.",
                    pages=[page]
                ))
            elif length > 165:
                findings.append(self.finding(
                    "DESC_003", f"Description too long ({length} chars): {page}", "warning", "P6",
                    f"Description on {page} is {length} chars — Google truncates at ~160.",
                    "Trim to under 160 chars. Put the most compelling content first.",
                    "Truncated descriptions lose the CTA and reduce CTR.",
                    pages=[page]
                ))

            # CTA check
            desc_lower = desc.lower()
            has_cta = any(cta in desc_lower for cta in CTA_WORDS)
            if not has_cta:
                findings.append(self.finding(
                    "DESC_004", f"No CTA in description: {page}", "info", "P6",
                    f"Description on {page} lacks a call-to-action word.",
                    "Add a CTA like 'Explore', 'Read', 'Discover', or 'Learn more about...'",
                    "Descriptions with CTAs can improve click-through rate by 15–20%.",
                    pages=[page]
                ))

        # Duplicate check
        for page, desc in desc_data:
            if not desc:
                continue
            if desc in seen_descs:
                findings.append(self.finding(
                    "DESC_005", f"Duplicate meta description", "warning", "P6",
                    f"'{page}' and '{seen_descs[desc]}' share identical descriptions.",
                    "Write unique descriptions for each page based on its specific content.",
                    "Duplicate descriptions indicate thin content differentiation to search engines.",
                    pages=[page, seen_descs[desc]]
                ))
            else:
                seen_descs[desc] = page

        if not findings:
            return self.result([], f"All {len(self.html_files)} pages have quality meta descriptions.",
                               [], ["Review descriptions quarterly and test variations in Search Console."])

        recs = [
            "Lead with the most important keyword within the first 20 characters.",
            "Include a specific benefit or differentiator (years of experience, project metrics).",
            "End every description with an action verb to drive clicks."
        ]
        return self.result(findings, f"Description audit: {len(findings)} issue(s) found.", [], recs)
