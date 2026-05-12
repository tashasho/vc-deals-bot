"""
slack_sender.py — Block Kit formatter + delivery for the VC deals digest.

The digest is two sections:
  💰 Today's Deals     — funded/acquired/IPO'd companies, structured per item
  📊 Market Pulse      — short macro/markets headlines
"""

import logging
from datetime import datetime
from typing import List

import requests

from .models import DealItem
from .config import Config

log = logging.getLogger(__name__)
SLACK_API = "https://slack.com/api"


def _deal_block(item: DealItem) -> dict:
    bits = []
    head = f"{item.emoji} *{item.title}*"
    bits.append(head)

    meta_pieces = []
    if item.amount:
        meta_pieces.append(f"💵 {item.amount}")
    if item.investors:
        meta_pieces.append("Led by " + ", ".join(item.investors[:3]))
    if item.sector:
        meta_pieces.append(f"`{item.sector}`")
    if meta_pieces:
        bits.append(" · ".join(meta_pieces))

    if item.summary:
        bits.append(item.summary)
    if item.why_interesting:
        bits.append(f"💡 _{item.why_interesting}_")
    bits.append(f"_{item.source}_")

    return {
        "type": "section",
        "text": {"type": "mrkdwn", "text": "\n".join(bits)},
        "accessory": {
            "type": "button",
            "text": {"type": "plain_text", "text": "Read →", "emoji": True},
            "url": item.url,
            "action_id": f"open_{item.id}",
        },
    }


def _market_block(item: DealItem) -> dict:
    line = f"{item.emoji} *<{item.url}|{item.title}>*"
    if item.summary:
        line += f"\n{item.summary}"
    if item.why_interesting:
        line += f"\n💡 _{item.why_interesting}_"
    line += f"\n_{item.source}_"
    return {"type": "section", "text": {"type": "mrkdwn", "text": line}}


def build_blocks(deals: List[DealItem], market: List[DealItem], title: str) -> list:
    today = datetime.now().strftime("%A, %B %-d")
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{title} — {today}", "emoji": True},
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"{len(deals)} deals · {len(market)} market updates · last 24–30h",
                }
            ],
        },
    ]

    if deals:
        blocks.append({"type": "divider"})
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*💰 Today's Deals*"}})
        for d in deals:
            blocks.append(_deal_block(d))
            blocks.append({"type": "divider"})

    if market:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*📊 Market Pulse*"}})
        for m in market:
            blocks.append(_market_block(m))

    blocks.append(
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "Summaries via OpenRouter · _vc-deals-bot_"}],
        }
    )
    return blocks


def send(deals: List[DealItem], market: List[DealItem], config: Config):
    config.require_slack()
    blocks = build_blocks(deals, market, config.digest_title)
    fallback = f"{config.digest_title}: {len(deals)} deals, {len(market)} market updates"

    if config.slack_webhook_url:
        _send_via_webhook(config.slack_webhook_url, fallback, blocks)
    else:
        _send_via_bot(config.slack_bot_token, config.slack_channel, fallback, blocks)


def _send_via_webhook(webhook_url: str, fallback: str, blocks: list):
    resp = requests.post(
        webhook_url, json={"text": fallback, "blocks": blocks}, timeout=15
    )
    if resp.status_code != 200 or resp.text.strip() != "ok":
        log.error(f"Webhook failed: {resp.status_code} {resp.text[:200]}")
        raise RuntimeError(f"Slack webhook returned non-ok: {resp.text!r}")
    log.info("Posted to Slack via webhook")


def _send_via_bot(token: str, channel: str, fallback: str, blocks: list):
    resp = requests.post(
        f"{SLACK_API}/chat.postMessage",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        json={
            "channel": channel,
            "text": fallback,
            "blocks": blocks,
            "unfurl_links": False,
            "unfurl_media": False,
        },
        timeout=15,
    )
    data = resp.json()
    if not data.get("ok"):
        log.error(f"Slack post failed: {data.get('error')}")
        raise RuntimeError(f"Slack chat.postMessage failed: {data.get('error')}")
    log.info(f"Posted to {channel} via bot token: ts={data['ts']}")
