import crawler
from base import BaseSEOSkill, Finding, SkillResult
from config import SITE_URL


class Skill11AISearchReadiness(BaseSEOSkill):
    SKILL_ID = 11
    SKILL_NAME = "AI Search Readiness"

    def run(self, pages: list[dict]) -> SkillResult:
        findings = []
        score = 100

        # llms.txt check
        llms = crawler.fetch(f"{SITE_URL}/llms.txt")
        if llms["status"] != 200:
            score -= 20
            findings.append(Finding(
                title="Missing llms.txt",
                description="No llms.txt file found — AI search engines cannot quickly parse site content.",
                severity="critical",
                category="ai-seo",
                url=f"{SITE_URL}/llms.txt",
                recommendation="Create /llms.txt with structured summary of site content for AI crawlers.",
            ))
        else:
            content = llms.get("html", "")
            if len(content) < 200:
                score -= 10
                findings.append(Finding(
                    title="llms.txt is too sparse",
                    description=f"llms.txt has only {len(content)} characters — insufficient for AI context.",
                    severity="warning",
                    category="ai-seo",
                    url=f"{SITE_URL}/llms.txt",
                    recommendation="Expand llms.txt with detailed summaries, skills, projects, and contact info.",
                ))

            # All sections required by the llms.txt spec for personal AI profiles
            required_sections = [
                ("## Professional Profile", "Needed so AI systems can locate canonical profile pages"),
                ("## Key Skills", "Required for AI engines to extract topical expertise signals"),
                ("## Technical Blog", "Needed for AI systems to discover and cite blog content"),
                ("## Contact", "Required for entity verification (LinkedIn, GitHub, email)"),
            ]
            for sec, reason in required_sections:
                if sec.lower() not in content.lower():
                    findings.append(Finding(
                        title=f"Missing section in llms.txt: {sec}",
                        description=f"llms.txt is missing '{sec}'. {reason}.",
                        severity="info",
                        category="ai-seo",
                        url=f"{SITE_URL}/llms.txt",
                        recommendation=f"Add a '{sec}' section to llms.txt with relevant links and summaries.",
                    ))

        # FAQ schema check on key pages
        for page in pages:
            url = page["url"]
            path = url.replace(SITE_URL, "")
            soup = page.get("soup")
            if not soup:
                continue

            schemas = crawler.extract_json_ld(soup)
            schema_types = []
            for s in schemas:
                if "@graph" in s:
                    schema_types.extend(item.get("@type", "") for item in (s["@graph"] if isinstance(s["@graph"], list) else [s["@graph"]]))
                else:
                    schema_types.append(s.get("@type", ""))

            # Blog posts should have FAQ schema
            if "blog/post" in path or "guide" in path:
                if "FAQPage" not in schema_types:
                    findings.append(Finding(
                        title=f"Missing FAQ schema on blog post: {path}",
                        description="Blog/guide pages benefit from FAQ schema for AI Overview inclusion.",
                        severity="warning",
                        category="ai-seo",
                        url=url,
                        recommendation="Add FAQPage JSON-LD schema with common questions and answers about the topic.",
                    ))

            # Check for speakable schema
            if path in ["/", "/amulya-gupta.html", "/about.html"]:
                if "Speakable" not in str(schema_types) and "speakable" not in str(schema_types).lower():
                    findings.append(Finding(
                        title=f"Missing Speakable schema: {path}",
                        description="Speakable schema helps voice search and AI assistants identify key content.",
                        severity="info",
                        category="ai-seo",
                        url=url,
                        recommendation="Add Speakable schema pointing to the most important content sections.",
                    ))

            # Check for structured entity signals (Person schema with sameAs)
            for s in schemas:
                if s.get("@type") == "Person":
                    if "sameAs" not in s:
                        findings.append(Finding(
                            title=f"Person schema missing sameAs: {path}",
                            description="sameAs links establish entity identity across the web.",
                            severity="warning",
                            category="ai-seo",
                            url=url,
                            recommendation="Add sameAs array with LinkedIn, GitHub, and other profile URLs to Person schema.",
                        ))
                    if "knowsAbout" not in s:
                        findings.append(Finding(
                            title=f"Person schema missing knowsAbout: {path}",
                            description="knowsAbout property tells AI engines your areas of expertise.",
                            severity="info",
                            category="ai-seo",
                            url=url,
                            recommendation="Add knowsAbout: ['AI Engineering', 'LLMs', 'MLOps'] to Person schema.",
                        ))

        # Check for AI crawler permissions in robots.txt
        # Priority bots: major LLM search engines & AI citation platforms
        AI_BOTS = [
            ("GPTBot", "ChatGPT Search"),
            ("OAI-SearchBot", "OpenAI SearchGPT"),
            ("ClaudeBot", "Claude / Anthropic"),
            ("Anthropic-AI", "Anthropic AI crawler"),
            ("Google-Extended", "Google AI Overviews / Gemini"),
            ("PerplexityBot", "Perplexity AI"),
            ("DuckAssistBot", "DuckDuckGo AI Chat"),
            ("Meta-ExternalAgent", "Meta AI / Llama"),
        ]
        robots = crawler.fetch(f"{SITE_URL}/robots.txt")
        if robots["status"] == 200:
            content = robots.get("html", "")
            for bot, platform in AI_BOTS:
                if bot.lower() not in content.lower():
                    findings.append(Finding(
                        title=f"AI crawler {bot} not explicitly permitted",
                        description=f"robots.txt has no explicit Allow for {bot} ({platform}).",
                        severity="info",
                        category="ai-seo",
                        url=f"{SITE_URL}/robots.txt",
                        recommendation=f"Add 'User-agent: {bot}\\nAllow: /' to robots.txt for {platform} coverage.",
                    ))

        score = self.clamp_score(score, findings=findings)
        return self.result(score, findings)
