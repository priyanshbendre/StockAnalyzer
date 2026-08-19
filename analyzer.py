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


def convert_to_human_readable(number):
    """Convert a number to a human-readable format (K, M, B, T)."""
    if isinstance(number, (int, float)):
        for unit in ['', 'K', 'M', 'B', 'T']:
            if abs(number) < 1000:
                return f"{number:.2f}".rstrip('0').rstrip('.') + unit
            number /= 1000
        return f"{number:.2f}".rstrip('0').rstrip('.') + 'T'
    return number


def merge_dict_values(data: dict) -> list:
    """Merge values of all parent keys in the dictionary into a list of lists."""
    if not data:
        return []
    metrics = list(data[next(iter(data))].keys())
    merged_list = []
    for metric in metrics:
        metric_values = [metric]
        for parent_key in data:
            value = data[parent_key][metric]
            formatted_value = convert_to_human_readable(value) if isinstance(value, (int, float)) else value
            metric_values.append(formatted_value)
        merged_list.append(metric_values)
    return merged_list


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
    list_width = len(tickers) * [12]
    table.set_cols_width([30] + list_width)
    for row in merge_dict_values(data):
        table.add_row(row)
    print(table.draw())


def load_summary(data_path: str) -> dict:
    with open(data_path, 'r') as file:
        return json.load(file)


_JSONC_LINE_COMMENT = re.compile(r'^\s*//.*$', re.MULTILINE)
_JSONC_TRAILING_COMMENT = re.compile(r'//.*$', re.MULTILINE)


def _strip_jsonc_comments(text: str) -> str:
    """Remove // line comments from JSONC text (full-line and trailing)."""
    text = _JSONC_LINE_COMMENT.sub('', text)
    return _JSONC_TRAILING_COMMENT.sub('', text)


def load_assumptions(config_path: str | None) -> dict:
    """Load user assumptions from a JSONC config file, or an empty dict when omitted.

    JSONC // comments are stripped before parsing. Static/derived defaults are
    applied per-ticker inside StockProjections.
    """
    if config_path is None:
        return {}
    with open(config_path, 'r') as file:
        content = file.read()
    return json.loads(_strip_jsonc_comments(content))


def print_projections(ticker: str, summary: dict, assumptions: dict):
    projections = StockProjections(ticker, summary, assumptions)
    print(f"\nProjections for {ticker} ({summary.get('company_name', 'N/A')}):")
    print(f"  Current Stock Data: {summary}")
    print(f"  Input User Assumptions: {projections.user_assumptions}")
    print(f"  Projected Revenue:            {fmt(projections.project_revenue(), prefix='$')}")
    print(f"  Projected Net Income:         {fmt(projections.project_net_income(), prefix='$')}")
    print(f"  Projected Shares Outstanding: {fmt(projections.project_shares_outstanding())}")
    print(f"  Projected EPS:                {fmt(projections.project_eps(), prefix='$')}")
    print(f"  Projected Stock Price:        {fmt(projections.calc_stock_valuation(), prefix='$')}")
    print(f"  Projected Market Cap:         {fmt(projections.calc_stock_market_cap(), prefix='$')}")
    print(f"  Upside/Downside Potential:    {fmt(projections.calc_upside_downside_potential(), suffix='%')}")


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
    summary = load_summary(args.output)
    assumptions = load_assumptions(args.config)
    for ticker in args.tickers:
        if ticker not in summary:
            logger.warning("No data found for %s; skipping", ticker)
            continue
        print_projections(ticker, summary[ticker], assumptions)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="analyzer",
        description="Fetch stock fundamentals and project future valuations.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="enable debug logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser("collect", help="fetch financial data for tickers and save to JSON")
    collect.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS, help="stock tickers (default: %(default)s)")
    collect.add_argument("--output", default=DEFAULT_OUTPUT, help="output JSON file (default: %(default)s)")
    collect.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                         help="max concurrent fetches (default: %(default)s)")
    collect.set_defaults(func=cmd_collect)

    project = subparsers.add_parser("project", help="project valuations from saved JSON data")
    project.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS, help="stock tickers (default: %(default)s)")
    project.add_argument("--data", default=DEFAULT_OUTPUT, help="input JSON data file (default: %(default)s)")
    project.add_argument("--config", default=None, help="assumptions JSON file (optional; uses defaults if omitted)")
    project.set_defaults(func=cmd_project)

    analyze = subparsers.add_parser("analyze", help="collect data, then project valuations")
    analyze.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS, help="stock tickers (default: %(default)s)")
    analyze.add_argument("--output", default=DEFAULT_OUTPUT, help="output JSON file (default: %(default)s)")
    analyze.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                         help="max concurrent fetches (default: %(default)s)")
    analyze.add_argument("--config", default=None, help="assumptions JSON file (optional; uses defaults if omitted)")
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