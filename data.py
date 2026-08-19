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


class StockData:
    def __init__(self, ticker: str):
        self.ticker = ticker
        self.stock = yf.Ticker(ticker)
        self.stock_info = retry_call(lambda: self.stock.info)
        self.quarterly_financials = retry_call(lambda: self.stock.quarterly_financials)
        self.annual_financials = retry_call(lambda: self.stock.financials)
        self.annual_cashflow = retry_call(lambda: self.stock.cashflow)
        self.quarterly_cashflow = retry_call(lambda: self.stock.quarterly_cashflow)

    def get_net_margin(self) -> float | None:
        """Calculate the trailing-twelve-month (TTM) net margin in percent."""
        try:
            ttm_net_income = self.quarterly_financials.loc['Net Income'].iloc[:TTM_QUARTERS].sum()
            ttm_revenue = self.stock_info.get('totalRevenue', None)
            if ttm_net_income is not None and ttm_revenue is not None:
                return (ttm_net_income / ttm_revenue) * 100
            return None
        except Exception as e:
            logger.warning("Error calculating net margin for %s: %s", self.ticker, e)
            return None

    def get_gross_profit_margin(self) -> float | None:
        """Calculate the TTM gross profit margin in percent."""
        try:
            ttm_gross_profit = self.quarterly_financials.loc['Gross Profit'].iloc[:TTM_QUARTERS].sum()
            ttm_revenue = self.quarterly_financials.loc['Total Revenue'].iloc[:TTM_QUARTERS].sum()
            if ttm_gross_profit is not None and ttm_revenue is not None:
                return (ttm_gross_profit / ttm_revenue) * 100
            return None
        except Exception as e:
            logger.warning("Error calculating gross profit margin for %s: %s", self.ticker, e)
            return None

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
        try:
            values = self.annual_financials.loc[row_label].iloc[:years].values
            if len(values) < years:
                logger.warning("Not enough data to calculate CAGR for '%s' for %s", row_label, self.ticker)
                return None
            value_start = values[-1]  # Oldest value
            value_end = values[0]     # Most recent value
            cagr = self.calc_cagr_equation(years, value_start, value_end)
            if cagr is not None:
                return cagr * 100  # Convert to percentage
            return None
        except KeyError:
            logger.warning("Row label '%s' not found in annual financials for %s", row_label, self.ticker)
            return None
        except Exception as e:
            logger.warning("Error calculating CAGR for '%s' for %s: %s", row_label, self.ticker, e)
            return None

    def calc_cashflow_avg(self, row_label: str = "Free Cash Flow", years: int = CAGR_YEARS) -> float | None:
        """Calculate the average of a specified row in the annual cash flow statement over the past N years."""
        try:
            return self.annual_cashflow.loc[row_label].iloc[:years].mean()
        except KeyError:
            logger.warning("Row label '%s' not found in cash flow for %s", row_label, self.ticker)
            return None
        except Exception as e:
            logger.warning("Error calculating average for '%s' for %s: %s", row_label, self.ticker, e)
            return None

    def ratio_free_cash_flow_yield(self) -> float | None:
        """Calculate the TTM Free Cash Flow Yield in percent."""
        try:
            free_cash_flow_ttm = self.quarterly_cashflow.loc['Free Cash Flow'].iloc[:TTM_QUARTERS].sum()
            market_cap = self.stock_info.get('marketCap', None)
            if free_cash_flow_ttm is not None and market_cap is not None:
                return (free_cash_flow_ttm / market_cap) * 100
            return None
        except Exception as e:
            logger.warning("Error calculating Free Cash Flow Yield for %s: %s", self.ticker, e)
            return None

    def metric_debt_to_avg_fcf(self) -> float | None:
        """Calculate Total Debt divided by average Free Cash Flow (years to pay off debt)."""
        try:
            avg_free_cash_flow = self.calc_cashflow_avg()
            total_debt = self.stock_info.get('totalDebt', None)
            if avg_free_cash_flow is not None and total_debt is not None and avg_free_cash_flow != 0:
                return total_debt / avg_free_cash_flow
            return None
        except Exception as e:
            logger.warning("Error calculating Debt to avg FCF for %s: %s", self.ticker, e)
            return None

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
    tasks = [_fetch_one(semaphore, ticker) for ticker in tickers]
    results = await asyncio.gather(*tasks)
    summary = {}
    for result in results:
        if result is not None:
            ticker, data = result
            summary[ticker] = data
    return summary