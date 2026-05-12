"""
config.py — env-driven settings for the VC deals bot.
"""

import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


# Curated, free RSS feeds covering venture funding + macro/markets.
DEFAULT_FEEDS: List[dict] = [
    # ── Venture funding ──
    {"name": "TechCrunch Venture", "url": "https://techcrunch.com/category/venture/feed/", "category": "deal"},
    {"name": "TechCrunch Startups", "url": "https://techcrunch.com/category/startups/feed/", "category": "deal"},
    {"name": "Crunchbase News", "url": "https://news.crunchbase.com/feed/", "category": "deal"},
    {"name": "Sifted", "url": "https://sifted.eu/feed", "category": "deal"},
    {"name": "VentureBeat Funding", "url": "https://venturebeat.com/category/venture/feed/", "category": "deal"},
    # ── Markets / macro ──
    {"name": "CNBC Top News", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114", "category": "market"},
    {"name": "Reuters Markets", "url": "https://www.reutersagency.com/feed/?best-topics=markets&post_type=best", "category": "market"},
    {"name": "Axios Business", "url": "https://api.axios.com/feed/business", "category": "market"},
]


@dataclass
class Config:
    # ── LLM (OpenRouter) ──
    openrouter_api_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"))

    # ── Slack delivery ──
    slack_bot_token: str = field(default_factory=lambda: os.getenv("SLACK_BOT_TOKEN", ""))
    slack_channel: str = field(default_factory=lambda: os.getenv("SLACK_CHANNEL", "vc-deals"))
    slack_webhook_url: str = field(default_factory=lambda: os.getenv("SLACK_WEBHOOK_URL", ""))

    # ── Behaviour ──
    deals_per_digest: int = field(default_factory=lambda: int(os.getenv("DEALS_PER_DIGEST", "8")))
    market_per_digest: int = field(default_factory=lambda: int(os.getenv("MARKET_PER_DIGEST", "3")))
    daily_post_time: str = field(default_factory=lambda: os.getenv("DAILY_POST_TIME", "09:00"))
    digest_title: str = field(default_factory=lambda: os.getenv("DIGEST_TITLE", "💰 VC Deals & Market Pulse"))
    lookback_hours: int = field(default_factory=lambda: int(os.getenv("LOOKBACK_HOURS", "30")))

    # ── State ──
    state_file: str = field(default_factory=lambda: os.getenv("STATE_FILE", "data/seen.json"))

    def feeds(self) -> List[dict]:
        return DEFAULT_FEEDS

    def require_llm(self):
        if not self.openrouter_api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. Get a key at https://openrouter.ai/keys"
            )

    def require_slack(self):
        if not self.slack_bot_token and not self.slack_webhook_url:
            raise RuntimeError(
                "Set SLACK_WEBHOOK_URL or SLACK_BOT_TOKEN+SLACK_CHANNEL. "
                "Or use --dry-run."
            )
