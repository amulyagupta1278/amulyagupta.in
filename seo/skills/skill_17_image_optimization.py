"""Skill 17 — Image Optimization Audit"""
from .base import BaseSkill


class ImageOptimizationSkill(BaseSkill):
    name = "Image Optimization Audit"
    priority = "P2"
    skill_number = 17

    def run(self) -> dict:
        findings = []
        auto_fixes = []

        for f in self.html_files:
            soup = self.parse(f)
            page = str(f.relative_to(self.site_root))
            imgs = soup.find_all("img")

            if not imgs:
                continue

            # Missing alt text
            no_alt = [img for img in imgs if not img.get("alt") and img.get("alt") != ""]
            decorative = [img for img in imgs if img.get("alt") == ""]
            if no_alt:
                findings.append(self.finding(
                    "IMG_001", f"{len(no_alt)} image(s) missing alt text on {page}", "warning", "P2",
                    f"{len(no_alt)} <img> elements have no alt attribute.",
                    "Add descriptive alt text to all content images. Use alt='' for decorative images.",
                    "Missing alt text fails WCAG accessibility and removes keyword opportunities for Google Images.",
                    pages=[page]
                ))
                self._add_alt_text(f, soup, no_alt, auto_fixes)

            # Missing lazy loading
            no_lazy = [img for img in imgs if not img.get("loading")]
            if len(no_lazy) > 1:
                findings.append(self.finding(
                    "IMG_002", f"{len(no_lazy)} image(s) without lazy loading on {page}", "info", "P2",
                    f"Images without loading='lazy' are eagerly loaded, increasing initial payload.",
                    "Add loading='lazy' to all images except the hero/LCP image above the fold.",
                    "Lazy loading reduces initial page weight by 30-50% on image-heavy pages.",
                    pages=[page]
                ))
                self._add_lazy(f, soup, no_lazy, auto_fixes)

            # Missing width/height (causes CLS)
            no_dimensions = [img for img in imgs
                             if not (img.get("width") and img.get("height"))
                             and not img.get("style")]
            if no_dimensions:
                findings.append(self.finding(
                    "IMG_003", f"{len(no_dimensions)} image(s) missing width/height on {page}", "warning", "P2",
                    "Images without explicit width/height attributes cause Cumulative Layout Shift (CLS).",
                    "Add width and height attributes matching the image's intrinsic size, or use CSS aspect-ratio.",
                    "CLS > 0.1 directly harms Core Web Vitals score and search ranking.",
                    pages=[page]
                ))

        # Check image file sizes
        img_dir = self.site_root / "assets" / "img"
        if img_dir.exists():
            large_images = []
            for img_file in img_dir.rglob("*"):
                if img_file.suffix.lower() in [".jpg", ".jpeg", ".png", ".gif", ".bmp"]:
                    size_kb = img_file.stat().st_size // 1024
                    if size_kb > 200:
                        large_images.append(f"{img_file.relative_to(self.site_root)} ({size_kb}KB)")
            if large_images:
                findings.append(self.finding(
                    "IMG_004", f"{len(large_images)} large image file(s) detected", "warning", "P2",
                    f"Images over 200KB: {', '.join(large_images[:5])}",
                    "Compress to WebP format with max 100KB per image. Use Squoosh.app or ImageOptim.",
                    "Large images are the #1 cause of poor LCP scores.",
                    pages=large_images[:3]
                ))

        if not findings:
            return self.result([], f"All images are optimized with alt text, lazy loading, and appropriate sizes.",
                               auto_fixes, ["Convert JPEG/PNG images to WebP for 25-35% smaller file sizes."])

        return self.result(findings, f"Image audit: {len(findings)} issue(s). {len(auto_fixes)} auto-fix(es).",
                           auto_fixes, ["Use next-gen formats (WebP, AVIF) for significant size reductions."])

    def _add_alt_text(self, path, soup, imgs: list, auto_fixes: list):
        content = path.read_text(encoding="utf-8")
        modified = False
        for img in imgs:
            src = img.get("src", "")
            # Generate contextual alt from src filename
            alt = src.split("/")[-1].split(".")[0].replace("-", " ").replace("_", " ").title()
            old_tag = str(img)
            if 'alt=' not in old_tag:
                new_tag = old_tag.replace("<img ", f'<img alt="{alt}" ', 1)
                if old_tag in content:
                    content = content.replace(old_tag, new_tag, 1)
                    modified = True
        if modified:
            path.write_text(content, encoding="utf-8")
            auto_fixes.append(f"Added alt text to {len(imgs)} image(s) on {path.relative_to(self.site_root)}.")

    def _add_lazy(self, path, soup, imgs: list, auto_fixes: list):
        content = path.read_text(encoding="utf-8")
        modified = False
        # Skip first image (likely LCP/hero image)
        for img in imgs[1:]:
            old_tag = str(img)
            if 'loading=' not in old_tag:
                new_tag = old_tag.replace("<img ", '<img loading="lazy" ', 1)
                if old_tag in content:
                    content = content.replace(old_tag, new_tag, 1)
                    modified = True
        if modified:
            path.write_text(content, encoding="utf-8")
            auto_fixes.append(f"Added loading='lazy' to images on {path.relative_to(self.site_root)}.")
