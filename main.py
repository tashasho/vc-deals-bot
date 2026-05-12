"""
vc-deals-bot — daily VC funding rounds + market pulse digest, posted to Slack.

Usage:
    python main.py             # fetch + summarize + post to Slack
    python main.py --dry-run   # print to terminal, don't post
    python main.py --loop      # daily schedule
"""

import argparse
import logging
import sys
import time

import schedule

from src.config import Config
from src.fetcher import fetch_all, split_and_rank
from src.summarizer import summarize_all
from src.slack_sender import send
from src.state import SeenState

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def run(dry_run: bool = False):
    log.info("Starting VC deals run...")
    config = Config()
    config.require_llm()
    if not dry_run:
        config.require_slack()

    state = SeenState(config.state_file)

    log.info("Fetching feeds...")
    items = fetch_all(config)
    log.info(f"Fetched {len(items)} total candidate items")

    fresh = [i for i in items if not state.has_seen(i.id)]
    log.info(f"{len(fresh)} fresh after dedup")

    deals, market = split_and_rank(fresh, config.deals_per_digest, config.market_per_digest)
    log.info(f"Picked {len(deals)} deals + {len(market)} market updates")

    if not deals and not market:
        log.info("Nothing new to share. Skipping.")
        return

    log.info(f"Summarizing with {config.model}...")
    enriched = summarize_all(deals + market, config)
    deals_out = [i for i in enriched if i.category == "deal"]
    market_out = [i for i in enriched if i.category == "market"]

    if dry_run:
        _print(deals_out, market_out)
    else:
        send(deals_out, market_out, config)

    for it in enriched:
        state.mark_seen(it.id)
    state.save()
    log.info("Done.")


def _print(deals, market):
    print("\n" + "═" * 70)
    print(" 💰 DEALS ".center(70, "═"))
    print("═" * 70)
    for d in deals:
        meta = []
        if d.amount: meta.append(d.amount)
        if d.investors: meta.append("led by " + ", ".join(d.investors[:2]))
        if d.sector: meta.append(d.sector)
        meta_str = " · ".join(meta) if meta else "-"
        print(f"\n{d.emoji} {d.title}")
        print(f"   {meta_str}")
        if d.summary: print(f"   📝 {d.summary}")
        if d.why_interesting: print(f"   💡 {d.why_interesting}")
        print(f"   🔗 {d.url}  [{d.source}]")

    print("\n" + "═" * 70)
    print(" 📊 MARKET PULSE ".center(70, "═"))
    print("═" * 70)
    for m in market:
        print(f"\n{m.emoji} {m.title}")
        if m.summary: print(f"   📝 {m.summary}")
        if m.why_interesting: print(f"   💡 {m.why_interesting}")
        print(f"   🔗 {m.url}  [{m.source}]")
    print()


def main():
    parser = argparse.ArgumentParser(description="VC Deals & Market Pulse Bot")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()

    if args.loop:
        config = Config()
        log.info(f"Scheduling daily digest at {config.daily_post_time}")
        schedule.every().day.at(config.daily_post_time).do(run, dry_run=args.dry_run)
        while True:
            schedule.run_pending()
            time.sleep(30)
    else:
        try:
            run(dry_run=args.dry_run)
        except RuntimeError as e:
            log.error(str(e))
            sys.exit(1)


if __name__ == "__main__":
    main()
