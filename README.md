# StockAnalyzer

Fetch stock fundamentals from Yahoo Finance and project future valuations.

A two-stage pipeline:

1. **collect** — fetch financial data for a list of tickers, compute key metrics, save them to `ticker_data.json`, and print a comparison table.
2. **project** — read the collected data and project future revenue, net income, EPS, stock price, and market cap based on user assumptions.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python analyzer.py collect --tickers CAVA AMZN SPGI ADBE
python analyzer.py project --tickers CAVA AMZN
python analyzer.py analyze --tickers CAVA AMZN   # collect + project in one step
```

If `--tickers` is omitted, the default list is used: `CAVA, AMZN, SPGI, ADBE`.

### `collect`

Fetches data asynchronously (5 concurrent by default) and writes `ticker_data.json`:

```bash
python analyzer.py collect --tickers CAVA AMZN --output ticker_data.json --concurrency 5
```

### `project`

Reads a JSON data file and prints projections:

```bash
python analyzer.py project --tickers CAVA AMZN --data ticker_data.json --config assumptions.jsonc
```

### `analyze`

Runs collect then project in one command:

```bash
python analyzer.py analyze --tickers CAVA AMZN --config assumptions.jsonc
```

## Assumptions config file

Projection assumptions live in a **JSONC** config file (`//` comments allowed; a template is at `assumptions.example.jsonc`). Any key you omit falls back to a **derived default** — 80% of the stock's own current value from `ticker_data.json`. Example:

```jsonc
{
    "yoy_growth_revenue": 2.0,
    "num_of_years": 5,
    "yoy_growth_share_count": 5.0,
    "estimated_pe": 20,
    "net_margin": 0.10
}
```

| Key | Meaning | Derived default (80% of current value) |
|---|---|---|
| `yoy_growth_revenue` | Expected year-over-year revenue growth (percent) | 0.8 × revenue CAGR (3y) |
| `num_of_years` | Number of years to project (static) | 5 |
| `yoy_growth_share_count` | Year-over-year share count change (percent; positive = dilution) | 0.8 × share-count CAGR (3y) |
| `estimated_pe` | Estimated PE multiple at the end of the projection (static) | 20 |
| `net_margin` | Net margin used for the projection (fraction) | 0.8 × current net margin / 100 |

Units note: `yoy_growth_revenue`, `yoy_growth_share_count` use the same units as their source data (percent). `estimated_pe` is a static multiple (default 20). `net_margin` is a **fraction** (e.g. `0.10` = 10%), so its derived default divides the percentage by 100.

## Metrics computed by `collect`

- Company name
- Current price
- Market cap
- TTM revenue
- EPS
- PE ratio
- Gross profit margin (%)
- Net margin (%)
- Revenue CAGR (3-year)
- Share count CAGR (3-year)
- Total debt
- Average 3-year free cash flow
- Dividend yield (%)
- FCF yield (%) — TTM free cash flow / market cap
- PEG ratio (trailing PE / EPS CAGR)
- Debt to avg FCF (years to pay off debt)
- Shares outstanding

## Project layout

```
StockAnalyzer/
├── analyzer.py          # CLI entry point (collect / project / analyze)
├── data.py              # StockData: yfinance fetch + metric calculations
├── projections.py       # StockProjections: future-value projections
├── tests/test_core.py   # unit tests for the pure math (no network)
├── requirements.txt
└── ticker_data.json     # generated output
```

## Tests

```bash
python -m unittest discover tests
```

## Notes on robustness

- Missing financial rows (row labels vary between tickers and yfinance versions) are logged and skipped — one bad ticker does not abort the run.
- Network calls are retried with exponential backoff.
- Projection math returns `N/A` when required inputs are missing.