# Using the Meme Stocks App

This guide describes how to use the application once it is running. For setup and deployment, see [GETTING_STARTED.md](GETTING_STARTED.md) and [DEPLOYMENT.md](DEPLOYMENT.md).

---

## How the app works

- **Data collection** runs in the background: Reddit posts and Yahoo Finance prices are fetched on a schedule. Stocks are either added by you or auto-discovered when mentioned in Reddit posts.
- **Daily analysis** ranks tracked stocks by a composite score (sentiment + price trend + volume).
- **Notifications** alert you to unusual activity (volume spikes, price moves, sentiment shifts).
- **Paper trading** lets you record hypothetical buys/sells and track portfolio performance without real money.

You use the app to view analysis, check notifications, and manage paper trades. The app does not execute real trades or connect to a broker.

---

## Web UI

Open the app in your browser (e.g. `http://localhost:8000` locally or `http://<VPS_HOST>:8000` when deployed). The frontend has four main areas:

| Tab | What you can do |
|-----|-----------------|
| **Dashboard** | View the daily ranked analysis: stocks with composite score, sentiment, mention count, and price trend. |
| **Stocks** | List tracked stocks, add a stock by symbol, and (per stock) view sentiment, recent Reddit mentions (with source: subreddit and link), and price history. |
| **Notifications** | See unread alerts for unusual activity (volume spike, price movement, sentiment shift). |
| **Paper Trading** | Create paper trades (buy/sell a symbol at a price and quantity), list trades, close positions, and view portfolio summary (P/L, win rate). |

**API docs**: Open `http://<backend>:8000/docs` to try any API endpoint from the browser.

---

## CLI

The CLI talks to the same backend over HTTP. From the project root, with the backend running:

```bash
# Use default backend (http://127.0.0.1:8000)
python -m backend.cli.main <command> ...

# Point at a different backend (e.g. deployed VPS)
export MEME_STOCKS_API_URL=http://meme-stocks-vps:8000
python -m backend.cli.main <command> ...
```

Or pass the URL per run: `python -m backend.cli.main --base-url http://meme-stocks-vps:8000 <command> ...`

### Common commands

| Task | Command |
|------|---------|
| Check backend is up | `python -m backend.cli.main health` |
| List tracked stocks | `python -m backend.cli.main stocks list` |
| Add a stock | `python -m backend.cli.main stocks add GME --name "GameStop"` |
| Show one stock | `python -m backend.cli.main stocks show GME` |
| Sentiment for a symbol | `python -m backend.cli.main sentiment GME` |
| Price history for a symbol | `python -m backend.cli.main prices GME` |
| Daily ranked analysis | `python -m backend.cli.main analysis` |
| Notifications | `python -m backend.cli.main notifications` |
| List paper trades | `python -m backend.cli.main trades list` |
| Create paper trade | `python -m backend.cli.main trades create GME buy 10 25.50` |
| Close a trade | `python -m backend.cli.main trades close <trade_id> 28.00` |
| Portfolio summary | `python -m backend.cli.main portfolio` |

Use `--output json` for machine-readable output (e.g. `python -m backend.cli.main analysis --output json`). Run `python -m backend.cli.main --help` and `python -m backend.cli.main <command> --help` for full options.

### Jobs (optional)

You can trigger data collection and see job history from the CLI:

| Task | Command |
|------|---------|
| Trigger Reddit collection | `python -m backend.cli.main jobs reddit` |
| Trigger price collection | `python -m backend.cli.main jobs prices` |
| Trigger notification check | `python -m backend.cli.main jobs notifications` |
| Job run history | `python -m backend.cli.main jobs runs reddit-collection` |
| Recent Reddit posts (with subreddit, url) | `python -m backend.cli.main jobs recent-posts --limit 20` |
| Reddit mentions for a symbol (source: subreddit, url) | `python -m backend.cli.main stocks mentions SYMBOL [--limit 20]` |

---

## Key concepts

- **Tracked stocks**: The list of symbols the app collects prices and Reddit sentiment for. Add symbols manually (Stocks tab or `stocks add`), or let the app discover them from Reddit posts.
- **Daily analysis**: A ranked list combining sentiment score, mention count, price trend (uptrend/downtrend/sideways), and composite score. Generated on a schedule (default once per day); also available on demand via the Dashboard or `analysis` command.
- **Notifications**: Alerts created when the app detects volume spikes, significant price moves, or sentiment shifts for a tracked stock. Stored until read; no push to email or other channels in the current version.
- **Paper trades**: Simulated positions. Create a trade (symbol, action buy/sell, quantity, price); close it later with an exit price. Portfolio and trade list show realized and unrealized P/L. Options (calls/puts) are supported with `--option`, `--strike`, and `--expiry`.

---

## Related docs

- [GETTING_STARTED.md](GETTING_STARTED.md) — Setup, configuration, running locally or in containers
- [DEPLOYMENT.md](DEPLOYMENT.md) — Deploy to a VPS, view logs and activity
- [PRD.md](PRD.md) — Product requirements and full API/CLI reference (Appendix A, FR-8)
