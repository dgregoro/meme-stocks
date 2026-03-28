"""CLI to run causal analysis via API. Requires a running backend.

Usage:
    python -m backend.app.scripts.run_causal --symbol GME --days 90 --freq 1h
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run causal analysis for a single symbol.")

    parser.add_argument("--symbol", required=True, help="Ticker symbol (e.g. GME)")
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--freq", default="1h")
    parser.add_argument("--max-lag", type=int, default=12)
    parser.add_argument(
        "--host",
        default="http://127.0.0.1:8000",
        help="Base URL of running API server",
    )
    parser.add_argument(
        "--output",
        help="Optional path to save full JSON result",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    url = (
        f"{args.host}/api/analysis/causal/{args.symbol}"
        f"?days={args.days}"
        f"&freq={args.freq}"
        f"&max_lag={args.max_lag}"
        f"&include_placebo=true"
    )

    print(f"\nCalling: {url}\n")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            print(
                f"ERROR: 404 Not Found. Symbol {args.symbol!r} may not be tracked.\n"
                "Add the stock first: POST /api/stocks or meme-stocks stocks add ..."
            )
        else:
            print(f"ERROR: Failed to call causal endpoint: {e}")
        sys.exit(1)
    except requests.RequestException as e:
        print(f"ERROR: Failed to call causal endpoint: {e}")
        sys.exit(1)

    data = response.json()

    # Insufficient data response (reason, buckets_available, min_required)
    if "reason" in data:
        print("INSUFFICIENT DATA")
        print(f"  Symbol: {data['symbol']}")
        print(f"  Freq: {data['freq']}")
        print(f"  Reason: {data['reason']}")
        print(f"  Buckets available: {data['buckets_available']}")
        print(f"  Min required: {data['min_required']}")
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(data, indent=2))
            print(f"  Full JSON saved to: {output_path}")
        sys.exit(1)

    if data.get("sample_size", 0) == 0:
        print("WARNING: Sample size is zero. Insufficient data?")
        sys.exit(1)

    print("=== CAUSAL ANALYSIS SUMMARY ===")
    print(f"Symbol: {data['symbol']}")
    print(f"Sample size: {data['sample_size']}")
    print(f"Frequency: {data['freq']}")
    print()

    def print_top_lags(name: str, values: list) -> None:
        print(f"Top {name} Lags (by absolute correlation):")
        sorted_vals = sorted(values, key=lambda x: abs(x["corr"]), reverse=True)
        for v in sorted_vals[:5]:
            print(f"  lag={v['lag']:>3} corr={v['corr']:+.4f} n={v['n']}")
        print()

    print_top_lags("Mention", data.get("mention_xcorr", []))
    print_top_lags("Sentiment", data.get("sentiment_xcorr", []))

    print("Predictive Metrics:")
    for p in data.get("predictive", []):
        print(f"  {p['metric']}: {p['value']:+.4f}")
    print()

    print("Placebo Metrics:")
    for p in data.get("placebo", []):
        print(f"  {p['metric']}: {p['value']:+.4f}")
    print()

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(data, indent=2))
        print(f"Full JSON saved to: {output_path}")


if __name__ == "__main__":
    main()
