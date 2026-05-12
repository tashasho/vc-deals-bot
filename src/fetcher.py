"""
fetcher.py — pull recent VC deals + market headlines from RSS feeds.

We use feedparser because RSS is messy: TechCrunch is RSS 2.0, Axios is Atom,
some publish dates as RFC 822, some as ISO 8601, etc. feedparser normalizes it.
"""

import logging
import re
import time
from datetime import datetime, timezone
from typing import List

import feedparser
import requests

from .models import DealItem
from .config import Config

log = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 vc-deals-bot/1.0"
)


def _parse_published(entry) -> datetime | None:
    if getattr(entry, "published_parsed", None):
        return datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
    if getattr(entry, "updated_parsed", None):
        return datetime.fromtimestamp(time.mktime(entry.updated_parsed), tz=timezone.utc)
    return None


def _strip_html(text: str) -> str:
    """RSS summaries often contain HTML tags. Strip them."""
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _stable_id(url: str) -> str:
    return f"feed-{abs(hash(url))}"


def fetch_feed(feed: dict, lookback_hours: int) -> List[DealItem]:
    """Fetch and parse a single RSS/Atom feed.

    Use requests (bundles certifi) to fetch the bytes, then hand them to
    feedparser. This avoids macOS Python.org SSL CA issues that bite
    feedparser's default urllib transport.
    """
    cutoff = datetime.now(timezone.utc).timestamp() - lookback_hours * 3600
    try:
        resp = requests.get(feed["url"], headers={"User-Agent": UA}, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        log.warning(f"Feed {feed['name']} HTTP fetch failed: {e}")
        return []

    parsed = feedparser.parse(resp.content)

    if parsed.bozo and not parsed.entries:
        log.warning(f"Feed {feed['name']} parse failed: {parsed.bozo_exception}")
        return []

    items: List[DealItem] = []
    for entry in parsed.entries[:50]:
        url = getattr(entry, "link", None)
        title = getattr(entry, "title", "").strip()
        if not url or not title:
            continue

        published = _parse_published(entry)
        if published and published.timestamp() < cutoff:
            continue

        # Prefer summary/description; fall back to content if present.
        raw_desc = getattr(entry, "summary", "") or ""
        if hasattr(entry, "content") and entry.content:
            raw_desc = entry.content[0].get("value", raw_desc)

        items.append(
            DealItem(
                id=_stable_id(url),
                source=feed["name"],
                category=feed["category"],
                title=title,
                url=url,
                published=published,
                description=_strip_html(raw_desc)[:1200],
            )
        )

    log.info(f"  {feed['name']}: {len(items)} items in last {lookback_hours}h")
    return items


def fetch_all(config: Config) -> List[DealItem]:
    items: List[DealItem] = []
    for feed in config.feeds():
        try:
            items += fetch_feed(feed, config.lookback_hours)
        except Exception as e:
            log.warning(f"Feed {feed['name']} failed entirely: {e}")
    return items


# ────────────────────────────────────────────
# Lightweight pre-filtering before LLM enrichment
# ────────────────────────────────────────────

DEAL_KEYWORDS = re.compile(
    r"\b(raise[sd]?|raising|funding|seed|series\s+[a-h]|"
    r"pre-seed|pre-series|venture|valuation|valued|"
    r"acquir(?:e[sd]?|ing|isition)|merger|"
    r"close[sd]?\s+\$?\d|secured\s+\$?\d|"
    r"\$\s?\d+\s?(?:m|million|b|billion|k))\b",
    re.IGNORECASE,
)

MARKET_KEYWORDS = re.compile(
    r"\b(market[s]?|stock[s]?|S&P|Nasdaq|Dow|treasur(?:y|ies)|"
    r"yield[s]?|fed|rate[s]?|inflation|cpi|gdp|recession|"
    r"earnings|ipo|listing|shares|equity)\b",
    re.IGNORECASE,
)


def looks_like_deal(item: DealItem) -> bool:
    text = f"{item.title} {item.description or ''}"
    return bool(DEAL_KEYWORDS.search(text))


def looks_like_market(item: DealItem) -> bool:
    text = f"{item.title} {item.description or ''}"
    return bool(MARKET_KEYWORDS.search(text))


def split_and_rank(items: List[DealItem], max_deals: int, max_market: int):
    """Sort items into deal vs market buckets, deduped, capped."""
    deals: List[DealItem] = []
    market: List[DealItem] = []

    seen_titles = set()
    for it in sorted(items, key=lambda x: x.published or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
        title_key = re.sub(r"\W+", "", it.title.lower())[:80]
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)

        if it.category == "deal" and looks_like_deal(it) and len(deals) < max_deals:
            deals.append(it)
        elif it.category == "market" and looks_like_market(it) and len(market) < max_market:
            market.append(it)
        elif len(deals) < max_deals and looks_like_deal(it):
            # cross-category fallback: a "market" feed item that's clearly a deal
            it.category = "deal"
            deals.append(it)

    return deals, market
