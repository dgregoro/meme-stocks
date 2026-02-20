"""CLI command implementations. Each cmd_* calls the API and formats output."""

from __future__ import annotations

import sys

from backend.cli import client, output


def health_cmd(*, base_url: str) -> None:
    resp = client.get("/health", base_url=base_url)
    data = resp.json()
    print(f"Status: {data.get('status', 'unknown')}")


def analysis_cmd(*, base_url: str, output_fmt: str) -> None:
    resp = client.get("/api/analysis/daily", base_url=base_url)
    data = resp.json()
    if output_fmt == "json":
        output.print_json(data)
        return
    headers = ["symbol", "sentiment_score", "mention_count", "price_trend", "composite_score"]
    rows = [
        [
            r["symbol"],
            r["sentiment_score"] if r["sentiment_score"] is not None else "-",
            r["mention_count"],
            r["price_trend"],
            f"{r['composite_score']:.4f}",
        ]
        for r in data
    ]
    output.print_table(headers, rows)


def portfolio_cmd(*, base_url: str, output_fmt: str) -> None:
    resp = client.get("/api/portfolio", base_url=base_url)
    data = resp.json()
    if output_fmt == "json":
        output.print_json(data)
        return
    for k, v in data.items():
        if v is not None and isinstance(v, float) and k in ("win_rate",):
            print(f"  {k}: {v:.1%}")
        elif v is not None:
            print(f"  {k}: {v}")
        else:
            print(f"  {k}: -")


def notifications_cmd(*, base_url: str, output_fmt: str) -> None:
    resp = client.get("/api/notifications", base_url=base_url)
    data = resp.json()
    if output_fmt == "json":
        output.print_json(data)
        return
    if not data:
        print("No unread notifications.")
        return
    headers = ["id", "stock_symbol", "type", "severity", "message"]
    rows = [[n["id"], n["stock_symbol"], n["type"], n["severity"], (n["message"] or "")[:50]] for n in data]
    output.print_table(headers, rows)


def sentiment_cmd(*, symbol: str, base_url: str, output_fmt: str) -> None:
    resp = client.get(f"/api/stocks/{symbol}/sentiment", base_url=base_url)
    data = resp.json()
    if output_fmt == "json":
        output.print_json(data)
        return
    for k, v in data.items():
        print(f"  {k}: {v}")


def prices_cmd(*, symbol: str, base_url: str, output_fmt: str) -> None:
    resp = client.get(f"/api/stocks/{symbol}/prices", base_url=base_url)
    data = resp.json()
    if output_fmt == "json":
        output.print_json(data)
        return
    if not data:
        print("No price data.")
        return
    headers = ["date", "open", "high", "low", "close", "volume"]
    rows = [[p["date"], p["open"], p["high"], p["low"], p["close"], p["volume"]] for p in data[:30]]
    output.print_table(headers, rows)


def stocks_list_cmd(*, base_url: str, output_fmt: str) -> None:
    resp = client.get("/api/stocks", base_url=base_url)
    data = resp.json()
    if output_fmt == "json":
        output.print_json(data)
        return
    if not data:
        print("No stocks tracked.")
        return
    headers = ["symbol", "name", "sector", "market_cap"]
    rows = [[s["symbol"], s["name"], s["sector"] or "-", s["market_cap"] if s["market_cap"] else "-"] for s in data]
    output.print_table(headers, rows)


def stocks_show_cmd(*, symbol: str, base_url: str, output_fmt: str) -> None:
    resp = client.get(f"/api/stocks/{symbol}", base_url=base_url)
    data = resp.json()
    if output_fmt == "json":
        output.print_json(data)
        return
    for k, v in data.items():
        print(f"  {k}: {v}")


def stocks_add_cmd(*, symbol: str, name: str, base_url: str, output_fmt: str) -> None:
    resp = client.post("/api/stocks", json={"symbol": symbol, "name": name}, base_url=base_url)
    data = resp.json()
    if output_fmt == "json":
        output.print_json(data)
        return
    print(f"Added stock: {data['symbol']} - {data['name']}")


def trades_list_cmd(*, base_url: str, output_fmt: str) -> None:
    resp = client.get("/api/trades", base_url=base_url)
    data = resp.json()
    if output_fmt == "json":
        output.print_json(data)
        return
    if not data:
        print("No trades.")
        return
    headers = ["id", "symbol", "type", "action", "qty", "entry", "exit"]
    rows = []
    for t in data:
        typ = t.get("instrument_type") or "stock"
        rows.append(
            [
                t["id"],
                t["stock_symbol"],
                typ,
                t["action"],
                t["quantity"],
                t["entry_price"],
                t["exit_price"] if t["exit_price"] is not None else "-",
            ]
        )
    output.print_table(headers, rows)


def trades_create_cmd(
    *,
    symbol: str,
    action: str,
    quantity: int,
    price: float,
    base_url: str,
    output_fmt: str,
) -> None:
    if action not in ("buy", "sell"):
        print("Error: action must be 'buy' or 'sell'", file=sys.stderr)
        sys.exit(client.EXIT_CLIENT_ERROR)
    resp = client.post(
        "/api/trades",
        json={"stock_symbol": symbol, "action": action, "quantity": quantity, "price": price},
        base_url=base_url,
    )
    data = resp.json()
    if output_fmt == "json":
        output.print_json(data)
        return
    print(f"Created trade: id={data['id']} {action} {quantity} {symbol} @ {price}")


def trades_close_cmd(
    *,
    trade_id: int,
    exit_price: float,
    base_url: str,
    output_fmt: str,
) -> None:
    resp = client.post(
        f"/api/trades/{trade_id}/close",
        json={"exit_price": exit_price},
        base_url=base_url,
    )
    data = resp.json()
    if output_fmt == "json":
        output.print_json(data)
        return
    print(f"Closed trade {trade_id} at {exit_price}")


def symbols_refresh_cmd(*, base_url: str, output_fmt: str) -> None:
    resp = client.post("/api/symbol-universe/refresh", base_url=base_url)
    data = resp.json()
    if output_fmt == "json":
        output.print_json(data)
        return
    print(
        f"Refresh: inserted={data.get('inserted', 0)}, updated={data.get('updated', 0)}, total={data.get('total', 0)}"
    )


def symbols_stats_cmd(*, base_url: str, output_fmt: str) -> None:
    resp = client.get("/api/symbol-universe/stats", base_url=base_url)
    data = resp.json()
    if output_fmt == "json":
        output.print_json(data)
        return
    for k, v in data.items():
        print(f"  {k}: {v}")


def jobs_reddit_cmd(*, base_url: str, output_fmt: str) -> None:
    resp = client.post("/api/jobs/reddit-collection", base_url=base_url)
    data = resp.json()
    if output_fmt == "json":
        output.print_json(data)
        return
    print(f"Reddit collection: {data.get('status', 'done')}")
    if data.get("stats"):
        print(f"  Stats: {data['stats']}")


def jobs_prices_cmd(*, base_url: str, output_fmt: str) -> None:
    resp = client.post("/api/jobs/price-collection", base_url=base_url)
    data = resp.json()
    if output_fmt == "json":
        output.print_json(data)
        return
    print(f"Price collection: {data.get('status', 'done')}")


def jobs_notifications_cmd(*, base_url: str, output_fmt: str) -> None:
    resp = client.post("/api/jobs/notification-check", base_url=base_url)
    data = resp.json()
    if output_fmt == "json":
        output.print_json(data)
        return
    print(f"Notification check: {data.get('status', 'done')}")


def jobs_recent_posts_cmd(*, limit: int, base_url: str, output_fmt: str) -> None:
    resp = client.get("/api/jobs/reddit-collection/recent", params={"limit": limit}, base_url=base_url)
    data = resp.json()
    if output_fmt == "json":
        output.print_json(data)
        return
    if not data:
        print("No recent posts.")
        return
    headers = ["id", "symbol", "subreddit", "title", "upvotes"]
    rows = [
        [p["id"], p.get("stock_symbol", "") or "-", p["subreddit"], (p["title"] or "")[:40], p["upvotes"]]
        for p in data
    ]
    output.print_table(headers, rows)
