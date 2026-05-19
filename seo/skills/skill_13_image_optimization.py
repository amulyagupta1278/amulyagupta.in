import crawler
from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL


class Skill13ImageOptimization(BaseSEOSkill):
    SKILL_ID = 13
    SKILL_NAME = "Image Optimization Audit"

    def run(self, pages: list[dict]) -> SkillResult:
        findings = []
        total_images = 0
        issues = 0

        for page in pages:
            url = page["url"]
            path = url.replace(SITE_URL, "")
            soup = page.get("soup")
            if not soup or page.get("status") != 200:
                continue

            images = soup.find_all("img")
            for img in images:
                total_images += 1
                src = img.get("src", "")
                alt = img.get("alt", None)
                loading = img.get("loading", "")
                width = img.get("width", "")
                height = img.get("height", "")

                if alt is None:
                    issues += 1
                    findings.append(Finding(
                        title=f"Missing alt attribute: {path}",
                        description=f"Image '{src[:80]}' has no alt attribute.",
                        severity="critical",
                        category="images",
                        url=url,
                        recommendation="Add descriptive alt text to all images for accessibility and SEO.",
                        evidence=f"src='{src[:80]}'",
                    ))
                elif alt == "":
                    # Empty alt is OK for decorative images, but flag if non-decorative
                    if not any(dec in src.lower() for dec in ["bg", "background", "decor", "pattern"]):
                        findings.append(Finding(
                            title=f"Empty alt text on likely non-decorative image: {path}",
                            description=f"Image '{src[:80]}' has empty alt text. Decorative images should use alt='' intentionally.",
                            severity="info",
                            category="images",
                            url=url,
                            recommendation="Add descriptive alt text if image conveys information.",
                            evidence=f"src='{src[:80]}'",
                        ))

                if loading != "lazy" and src and not any(
                    above_fold in src.lower() for above_fold in ["hero", "profile", "avatar", "logo", "above"]
                ):
                    findings.append(Finding(
                        title=f"Image missing lazy loading: {path}",
                        description=f"Image '{src[:80]}' should use loading='lazy' for performance.",
                        severity="warning",
                        category="images",
                        url=url,
                        recommendation="Add loading='lazy' to below-fold images to improve LCP and page load speed.",
                        evidence=f"src='{src[:60]}'",
                    ))

                if not width or not height:
                    if src and not src.startswith("data:"):
                        findings.append(Finding(
                            title=f"Image missing width/height: {path}",
                            description=f"Image '{src[:80]}' lacks width/height attributes causing layout shift (CLS).",
                            severity="warning",
                            category="images",
                            url=url,
                            recommendation="Add explicit width and height attributes to all images to prevent layout shifts.",
                            evidence=f"src='{src[:60]}'",
                        ))

                # Check for non-optimized formats
                if src and any(src.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif"]):
                    if not src.lower().endswith(".gif"):
                        findings.append(Finding(
                            title=f"Non-modern image format: {path}",
                            description=f"Image '{src[:80]}' uses {src.split('.')[-1].upper()} — consider WebP/AVIF.",
                            severity="info",
                            category="images",
                            url=url,
                            recommendation="Convert images to WebP format for 25-35% file size reduction without quality loss.",
                            evidence=f"src='{src[:60]}'",
                        ))

        pct_ok = max(0, 100 - (issues / max(total_images, 1) * 100))
        score = self.clamp_score(int(pct_ok), findings=findings)
        return self.result(score, findings, {
            "total_images": total_images,
            "images_with_issues": issues,
        })
