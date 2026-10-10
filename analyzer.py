#!/usr/bin/python3

import argparse
import asyncio
import json
import logging
import re

from texttable import Texttable

from data import DEFAULT_CONCURRENCY, async_fetch_summaries
from projections import StockProjections

logger = logging.getLogger(__name__)

DEFAULT_TICKERS = ["CAVA", "AMZN", "SPGI", "ADBE"]
DEFAULT_OUTPUT = "ticker_data.json"

# Shared argparse specs, so the same flag is defined identically for every command.
TICKERS_ARG = {"nargs": "+", "default": DEFAULT_TICKERS, "help": "stock tickers (default: %(default)s)"}
OUTPUT_ARG = {"default": DEFAULT_OUTPUT, "help": "output JSON file (default: %(default)s)"}
DATA_ARG = {"default": DEFAULT_OUTPUT, "help": "input JSON data file (default: %(default)s)"}
CONCURRENCY_ARG = {"type": int, "default": DEFAULT_CONCURRENCY,
                   "help": "max concurrent fetches (default: %(default)s)"}
CONFIG_ARG = {"default": None, "help": "assumptions JSON file (optional; uses defaults if omitted)"}

# label, StockProjections method, value prefix, value suffix
PROJECTION_ROWS = (
    ("Projected Revenue", "project_revenue", "$", ""),
    ("Projected Net Income", "project_net_income", "$", ""),
    ("Projected Shares Outstanding", "project_shares_outstanding", "", ""),
    ("Projected EPS", "project_eps", "$", ""),
    ("Projected Stock Price", "calc_stock_valuation", "$", ""),
    ("Projected Market Cap", "calc_stock_market_cap", "$", ""),
    ("Upside/Downside Potential", "calc_upside_downside_potential", "", "%"),
)

_JSONC_COMMENT = re.compile(r'//.*$', re.MULTILINE)


def convert_to_human_readable(number):
    """Convert a number to a human-readable format (K, M, B, T)."""
    if not isinstance(number, (int, float)):
        return number
    for unit in ("", "K", "M", "B", "T"):
        if abs(number) < 1000:
            return f"{number:.2f}".rstrip('0').rstrip('.') + unit
        number /= 1000
    return f"{number:.2f}".rstrip('0').rstrip('.') + 'T'


def merge_dict_values(data: dict) -> list:
    """Merge values of all parent keys in the dictionary into a list of lists."""
    if not data:
        return []
    metrics = list(next(iter(data.values())).keys())
    return [[metric] + [convert_to_human_readable(data[ticker][metric]) for ticker in data]
            for metric in metrics]


def fmt(value, prefix: str = "", suffix: str = "", decimals: int = 2) -> str:
    """Format a number with thousands separators, or N/A when None."""
    if value is None:
        return "N/A"
    return f"{prefix}{value:,.{decimals}f}{suffix}"


def write_json(data: dict, file_path: str):
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)
    logger.info("Data has been written to %s", file_path)


def print_table(data: dict, tickers: list[str]):
    if not data:
        logger.warning("No data to display.")
        return
    table = Texttable()
    table.header(["metrics"] + tickers)
    table.set_cols_width([30] + [12] * len(tickers))
    for row in merge_dict_values(data):
        table.add_row(row)
    print(table.draw())


def load_summary(data_path: str) -> dict:
    try:
        with open(data_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        raise SystemExit(f"No data file at {data_path}. Run 'python analyzer.py collect' first to generate it.")


def load_assumptions(config_path: str | None) -> dict:
    """Load user assumptions from a JSONC config file, or an empty dict when omitted.

    JSONC // comments are stripped before parsing. Static/derived defaults are
    applied per-ticker inside StockProjections.
    """
    if config_path is None:
        return {}
    with open(config_path, 'r') as file:
        content = file.read()
    # Full-line comments leave behind blank lines, which JSON tolerates.
    return json.loads(_JSONC_COMMENT.sub('', content))


def print_projections(ticker: str, summary: dict, assumptions: dict):
    projections = StockProjections(summary, assumptions)
    width = max(len(label) for label, _, _, _ in PROJECTION_ROWS) + 1
    print(f"\nProjections for {ticker}:")
    print(f"  Current Stock Data: {summary}")
    print(f"  Input User Assumptions: {projections.user_assumptions}")
    for label, method, prefix, suffix in PROJECTION_ROWS:
        value = fmt(getattr(projections, method)(), prefix=prefix, suffix=suffix)
        print(f"  {label + ':':<{width}} {value}")


def cmd_collect(args):
    logger.info("Collecting data for %s", args.tickers)
    summary = asyncio.run(async_fetch_summaries(args.tickers, max_concurrent=args.concurrency))
    write_json(summary, args.output)
    print_table(summary, args.tickers)


def cmd_project(args):
    summary = load_summary(args.data)
    assumptions = load_assumptions(args.config)
    logger.info("Using assumptions: %s", assumptions)
    for ticker in args.tickers:
        if ticker not in summary:
            logger.warning("No data found for %s in %s; skipping", ticker, args.data)
            continue
        print_projections(ticker, summary[ticker], assumptions)


def cmd_analyze(args):
    cmd_collect(args)
    args.data = args.output  # project reads back exactly what collect just wrote
    cmd_project(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="analyzer",
        description="Fetch stock fundamentals and project future valuations.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="enable debug logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser("collect", help="fetch financial data for tickers and save to JSON")
    collect.add_argument("--tickers", **TICKERS_ARG)
    collect.add_argument("--output", **OUTPUT_ARG)
    collect.add_argument("--concurrency", **CONCURRENCY_ARG)
    collect.set_defaults(func=cmd_collect)

    project = subparsers.add_parser("project", help="project valuations from saved JSON data")
    project.add_argument("--tickers", **TICKERS_ARG)
    project.add_argument("--data", **DATA_ARG)
    project.add_argument("--config", **CONFIG_ARG)
    project.set_defaults(func=cmd_project)

    analyze = subparsers.add_parser("analyze", help="collect data, then project valuations")
    analyze.add_argument("--tickers", **TICKERS_ARG)
    analyze.add_argument("--output", **OUTPUT_ARG)
    analyze.add_argument("--concurrency", **CONCURRENCY_ARG)
    analyze.add_argument("--config", **CONFIG_ARG)
    analyze.set_defaults(func=cmd_analyze)

    return parser


def main():
    args = build_parser().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    args.func(args)


if __name__ == "__main__":
    main()