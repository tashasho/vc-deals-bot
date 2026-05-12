"""
summarizer.py — extract structured VC-deal info from headlines + bodies via OpenRouter.

For each item we want:
  - company: who got funded / acquired
  - amount: the round size + stage
  - investors: lead/co-investors if mentioned
  - sector: 1-3 word industry label
  - summary: what happened, 1-2 sentences
  - why_interesting: why a VC associate should care
  - emoji: a single fitting emoji
"""

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from openai import OpenAI

from .models import DealItem
from .config import Config

log = logging.getLogger(__name__)

DEAL_PROMPT = """You are a senior VC analyst summarising fundraising news for a tech-savvy investor audience.
Read the headline + article excerpt and extract structured deal info.

Respond with ONLY a valid JSON object — no markdown, no commentary, no backticks. Keys:
  "company":         string, the company being funded/acquired (or "" if not a deal)
  "amount":          string, e.g. "$15M Series A", "$2B IPO", or "" if unknown
  "investors":       array of strings, lead + notable co-investors, [] if unknown
  "sector":          string, 1-4 words, e.g. "AI infra", "fintech", "climate"
  "summary":         string, ONE sentence: company + what + how much + who led
  "why_interesting": string, ONE sentence: why this matters to a VC right now
  "emoji":           single emoji that fits the sector or story

If the item is NOT actually a funding/M&A/IPO event, leave company/amount/investors empty
and put a 1-sentence factual summary anyway. Do not invent numbers."""

MARKET_PROMPT = """You are a markets desk analyst writing for a VC associate audience.
Summarise this market/macro headline.

Respond with ONLY a valid JSON object — no markdown, no commentary, no backticks. Keys:
  "summary":         string, ONE sentence: what happened
  "why_interesting": string, ONE sentence: implication for early-stage tech investors
  "sector":          string, 1-3 words, e.g. "rates", "ipo market", "AI sentiment"
  "emoji":           single emoji that fits the story
  (omit company/amount/investors)"""


def _extract_json(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)
    return json.loads(cleaned)


def _build_user_msg(item: DealItem) -> str:
    parts = [
        f"Source: {item.source}",
        f"Headline: {item.title}",
    ]
    if item.published:
        parts.append(f"Published: {item.published.isoformat()}")
    if item.description:
        parts.append(f"Excerpt: {item.description[:900]}")
    parts.append(f"URL: {item.url}")
    return "\n".join(parts)


def _enrich(item: DealItem, client: OpenAI, model: str) -> DealItem:
    raw = ""
    system = DEAL_PROMPT if item.category == "deal" else MARKET_PROMPT
    try:
        completion = client.chat.completions.create(
            model=model,
            max_tokens=450,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": _build_user_msg(item)},
            ],
        )
        raw = completion.choices[0].message.content or ""
        data = _extract_json(raw)

        item.summary = data.get("summary") or item.description or item.title
        item.why_interesting = data.get("why_interesting", "")
        item.sector = data.get("sector") or None
        item.emoji = data.get("emoji") or ("💸" if item.category == "deal" else "📊")
        if item.category == "deal":
            item.company = data.get("company") or None
            item.amount = data.get("amount") or None
            item.investors = data.get("investors") or []
    except json.JSONDecodeError as e:
        log.warning(f"JSON parse failed for {item.id}: {e} | raw: {raw[:200]}")
        item.summary = item.description or item.title
    except Exception as e:
        log.warning(f"Summarization failed for {item.id}: {e}")
        item.summary = item.description or item.title

    return item


def _client(config: Config) -> OpenAI:
    return OpenAI(
        api_key=config.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "https://github.com/local/vc-deals-bot",
            "X-Title": "vc-deals-bot",
        },
    )


def summarize_all(items: List[DealItem], config: Config) -> List[DealItem]:
    if not items:
        return []
    client = _client(config)
    enriched: List[DealItem] = [None] * len(items)  # type: ignore
    with ThreadPoolExecutor(max_workers=6) as pool:
        future_to_idx = {pool.submit(_enrich, it, client, config.model): i for i, it in enumerate(items)}
        for fut in as_completed(future_to_idx):
            i = future_to_idx[fut]
            enriched[i] = fut.result()
    return enriched
