#!/usr/bin/python3

import asyncio
import logging
import time

import yfinance as yf

logger = logging.getLogger(__name__)

CAGR_YEARS = 3
TTM_QUARTERS = 4
DEFAULT_CONCURRENCY = 5
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2.0


def retry_call(fn, retries=MAX_RETRIES, backoff=RETRY_BACKOFF_SECONDS):
    """Call fn with retries and exponential backoff."""
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:
            if attempt == retries - 1:
                raise
            wait = backoff * (2 ** attempt)
            logger.warning("Attempt %d failed (%s); retrying in %.1fs", attempt + 1, e, wait)
            time.sleep(wait)


def _safe(fn, ticker: str, label: str, default=None):
    """Run a metric calculation, logging and returning default instead of raising."""
    try:
        return fn()
    except Exception as e:
        logger.warning("Error calculating %s for %s: %s", label, ticker, e)
        return default


def _ttm_sum(frame, row_label: str):
    """Sum the most recent TTM_QUARTERS values of a statement row."""
    return frame.loc[row_label].iloc[:TTM_QUARTERS].sum()


def _ratio(numerator, denominator, pct: bool = True):
    """Divide two values, returning None when either is missing or the divisor is 0."""
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator * (100 if pct else 1)


class StockData:
    def __init__(self, ticker: str):
        self.ticker = ticker
        stock = yf.Ticker(ticker)
        self.stock_info = retry_call(lambda: stock.info)
        self.quarterly_financials = retry_call(lambda: stock.quarterly_financials)
        self.annual_financials = retry_call(lambda: stock.financials)
        self.annual_cashflow = retry_call(lambda: stock.cashflow)
        self.quarterly_cashflow = retry_call(lambda: stock.quarterly_cashflow)

    def get_net_margin(self) -> float | None:
        """Calculate the trailing-twelve-month (TTM) net margin in percent."""
        return _safe(lambda: _ratio(_ttm_sum(self.quarterly_financials, 'Net Income'),
                                    self.stock_info.get('totalRevenue', None)),
                     self.ticker, "net margin")

    def get_gross_profit_margin(self) -> float | None:
        """Calculate the TTM gross profit margin in percent."""
        return _safe(lambda: _ratio(_ttm_sum(self.quarterly_financials, 'Gross Profit'),
                                    _ttm_sum(self.quarterly_financials, 'Total Revenue')),
                     self.ticker, "gross profit margin")

    @staticmethod
    def calc_cagr_equation(years: int, value_start: float, value_end: float) -> float | None:
        """Calculate the Compound Annual Growth Rate (CAGR)."""
        if value_start == 0 or years <= 0:
            raise ValueError("Check Past Value or number of years for CAGR")
        cagr = (value_end / value_start) ** (1 / years) - 1
        if isinstance(cagr, complex):
            return None
        return cagr

    def calc_cagr(self, row_label: str = "Total Revenue", years: int = CAGR_YEARS) -> float | None:
        """Calculate CAGR in percent for a specified row in the annual financials."""

        def compute():
            values = self.annual_financials.loc[row_label].iloc[:years].values
            if len(values) < years:
                logger.warning("Not enough data to calculate CAGR for '%s' for %s", row_label, self.ticker)
                return None
            cagr = self.calc_cagr_equation(years, values[-1], values[0])  # oldest -> most recent
            return None if cagr is None else cagr * 100  # convert to percentage

        return _safe(compute, self.ticker, f"CAGR for '{row_label}'")

    def calc_cashflow_avg(self, row_label: str = "Free Cash Flow", years: int = CAGR_YEARS) -> float | None:
        """Calculate the average of a specified row in the annual cash flow statement over the past N years."""
        return _safe(lambda: self.annual_cashflow.loc[row_label].iloc[:years].mean(),
                     self.ticker, f"average for '{row_label}' in cash flow")

    def ratio_free_cash_flow_yield(self) -> float | None:
        """Calculate the TTM Free Cash Flow Yield in percent."""
        return _safe(lambda: _ratio(_ttm_sum(self.quarterly_cashflow, 'Free Cash Flow'),
                                    self.stock_info.get('marketCap', None)),
                     self.ticker, "Free Cash Flow Yield")

    def metric_debt_to_avg_fcf(self) -> float | None:
        """Calculate Total Debt divided by average Free Cash Flow (years to pay off debt)."""
        return _safe(lambda: _ratio(self.stock_info.get('totalDebt', None),
                                    self.calc_cashflow_avg(), pct=False),
                     self.ticker, "Debt to avg FCF")

    def data_summary(self) -> dict:
        """Generate and return a dictionary of the financial summary of the stock.

        Kept to the metrics with no stock-data MCP equivalent, plus the fields
        the projections stage consumes (ttm_revenue, current_price,
        shares_outstanding, net_margin_in%).
        """
        return {
            "ttm_revenue": self.stock_info.get('totalRevenue', None),
            "current_price": self.stock_info.get('currentPrice', None),
            "net_margin_in%": self.get_net_margin(),
            "gross_profit_margin_in%": self.get_gross_profit_margin(),
            "cagr_revenue_3y_in%": self.calc_cagr(),
            "cagr_share_count_3y_in%": self.calc_cagr("Diluted Average Shares"),
            "total_debt": self.stock_info.get('totalDebt', None),
            "avg_3y_free_cash_flow": self.calc_cashflow_avg(),
            "dividend_yield_in%": self.stock_info.get('dividendYield', None),
            "fcf_yield_in%": self.ratio_free_cash_flow_yield(),
            "debt_to_avg_fcf": self.metric_debt_to_avg_fcf(),
            "shares_outstanding": self.stock_info.get('sharesOutstanding', None),
        }


async def _fetch_one(semaphore, ticker: str):
    """Fetch the summary for a single ticker, returning (ticker, summary) or None on failure."""
    async with semaphore:
        logger.info("--- Analyzing %s ---", ticker)
        loop = asyncio.get_running_loop()
        try:
            stock_data = await loop.run_in_executor(None, StockData, ticker)
            return ticker, stock_data.data_summary()
        except Exception as e:
            logger.error("Failed to fetch data for %s: %s", ticker, e)
            return None


async def async_fetch_summaries(tickers: list[str], max_concurrent: int = DEFAULT_CONCURRENCY) -> dict:
    """Fetch summaries for all tickers concurrently, skipping individual failures."""
    semaphore = asyncio.Semaphore(max_concurrent)
    results = await asyncio.gather(*[_fetch_one(semaphore, ticker) for ticker in tickers])
    return {ticker: summary for ticker, summary in filter(None, results)}