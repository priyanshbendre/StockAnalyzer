# StockAnalyzer

Calculate stock projections and important financial ratios using Yahoo Finance data.

This project is a two-stage analysis pipeline:

1. **`analyzer_data_v7_data.py`** — fetches financial data for a list of tickers, computes key metrics, saves them to `ticker_data.json`, and prints a comparison table.
2. **`analyzer_data_v7_projections.py`** — reads `ticker_data.json` and projects future revenue, net income, EPS, stock price, and market cap based on user assumptions.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### 1. Fetch stock data

Edit the `tickers` list in `analyzer_data_v7_data.py` (`__main__`) to choose which stocks to analyze:

```python
tickers = ["CAVA", "AMZN", "SPGI", "ADBE"]
```

Then run:

```bash
python analyzer_data_v7_data.py
```

Outputs:

- **`ticker_data.json`** — per-ticker financial summary, used by the projections script.
- **Formatted table** — printed to the console comparing metrics across tickers.

### 2. Generate projections

Edit the `stock_tickers` list and the user assumptions in `analyzer_data_v7_projections.py` (inside `Stock_Projections.user_assumptions_input()`), then run:

```bash
python analyzer_data_v7_projections.py
```

## Metrics computed by the data script

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
- FCF yield (%)
- PEG ratio (trailing PE / EPS CAGR)
- Avg FCF to total debt
- Shares outstanding

## Projection assumptions

The projection script takes the following inputs (editable in `user_assumptions_input()`):

- YoY revenue growth
- Number of years to project
- YoY share count growth (positive = dilution)
- Estimated exit PE multiple
- Net margin

## Script workflow

1. `analyzer_data_v7_data.py` asynchronously fetches stock data (max 5 concurrent tickers) using `yfinance`.
2. Metrics are calculated in the `Stock_Data` class.
3. Results are written to `ticker_data.json`.
4. `analyzer_data_v7_projections.py` loads the JSON, applies assumptions, and prints projected revenue, net income, shares outstanding, EPS, stock price, market cap, and upside/downside potential.

## Customization

- Change the `tickers` / `stock_tickers` lists to analyze different stocks.
- Add new metrics inside the `Stock_Data` class in `analyzer_data_v7_data.py`.
- Adjust the assumptions in `Stock_Projections.user_assumptions_input()`.
