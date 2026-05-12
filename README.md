# 💰 vc-deals-bot

Daily Slack digest of VC funding rounds, M&A, IPOs, and market headlines —
pulled from TechCrunch, Crunchbase News, Sifted, VentureBeat, CNBC, Reuters,
and Axios. Each item is structured by an LLM (via OpenRouter) into:

```
💸 Acme AI raises $24M Series A
   $24M Series A · Led by Sequoia, a16z · `AI infra`
   Acme AI announced a $24M Series A to scale its inference platform.
   💡 Validates that AI infra fundraising is still active despite Q1 cooldown.
   _TechCrunch_                                                  [Read →]
```

## Quick start

```bash
cd vc-deals-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Fill .env (OPENROUTER_API_KEY required; SLACK_* for posting)
cp .env.example .env

python main.py --dry-run   # preview in terminal
python main.py             # post to Slack
```

## Sources

| Feed | Category | URL |
|---|---|---|
| TechCrunch Venture | deals | techcrunch.com/category/venture |
| TechCrunch Startups | deals | techcrunch.com/category/startups |
| Crunchbase News | deals | news.crunchbase.com |
| Sifted (EU) | deals | sifted.eu |
| VentureBeat Funding | deals | venturebeat.com/category/venture |
| CNBC Top News | market | cnbc.com |
| Reuters Markets | market | reutersagency.com |
| Axios Business | market | axios.com/business |

To add a feed: append to `DEFAULT_FEEDS` in `src/config.py`.

## Deploy

GitHub Actions cron (free, see `.github/workflows/digest.yml`). Secrets needed:

- `OPENROUTER_API_KEY`
- `SLACK_BOT_TOKEN` (or `SLACK_WEBHOOK_URL`)

And the `SLACK_CHANNEL` variable (channel ID like `C0B3G54JR4H`).

## Files

```
vc-deals-bot/
├── main.py
├── src/
│   ├── config.py        # feeds + env vars
│   ├── models.py        # DealItem dataclass
│   ├── fetcher.py       # RSS via feedparser, deal/market keyword pre-filter
│   ├── summarizer.py    # OpenRouter, two prompts (deal vs market)
│   ├── slack_sender.py  # Block Kit, two-section digest
│   └── state.py         # dedup persistence (5000-cap FIFO)
├── data/seen.json
├── .env.example
└── .github/workflows/digest.yml
```
