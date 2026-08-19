#!/usr/bin/python3

import logging

logger = logging.getLogger(__name__)

DEFAULT_ASSUMPTIONS = {
    "yoy_growth_revenue": 0.02,          # fallback yoy revenue growth (percent)
    "num_of_years": 5,                   # number of years of analysis
    "yoy_growth_share_count": 0.05,      # fallback share count change per year in percent (positive = dilution)
    "estimated_pe": 20,                  # estimated PE at the end of the analysis period (static default)
    "net_margin": 0.10,                  # fallback net margin used throughout the analysis period (fraction)
}

DEFAULT_HAIRCUT = 0.8


def derive_assumptions(analysis_summary: dict, user_assumptions: dict | None = None) -> dict:
    """Build the effective assumptions.

    Static defaults are overridden by user config, then by 80% of the stock's
    own current values where the config did not specify a value and the data is
    available. Note that units differ: yoy_growth_revenue and
    yoy_growth_share_count are percents, while net_margin is a fraction (hence
    the /100). estimated_pe stays at its static default unless user-set.
    """
    user_assumptions = user_assumptions or {}
    assumptions = dict(DEFAULT_ASSUMPTIONS)
    assumptions.update(user_assumptions)

    if "yoy_growth_revenue" not in user_assumptions:
        cagr = analysis_summary.get("cagr_revenue_3y_in%")
        if cagr is not None:
            assumptions["yoy_growth_revenue"] = DEFAULT_HAIRCUT * cagr

    if "yoy_growth_share_count" not in user_assumptions:
        cagr = analysis_summary.get("cagr_share_count_3y_in%")
        if cagr is not None:
            assumptions["yoy_growth_share_count"] = DEFAULT_HAIRCUT * cagr

    if "net_margin" not in user_assumptions:
        margin = analysis_summary.get("net_margin_in%")
        if margin is not None:
            assumptions["net_margin"] = DEFAULT_HAIRCUT * margin / 100

    return assumptions


class StockProjections:
    def __init__(self, stock_ticker: str, analysis_summary: dict, user_assumptions: dict | None = None):
        self.stock_ticker = stock_ticker
        self.analysis_summary = analysis_summary
        self.user_assumptions = derive_assumptions(analysis_summary, user_assumptions)

    @staticmethod
    def calc_future_value(current_value: float | None, growth_rate: float | None, num_of_years: int) -> float | None:
        """Calculate the future value of a metric growing at a rate over N years."""
        if current_value is None or growth_rate is None or num_of_years <= 0:
            return None
        return current_value * (1 + growth_rate / 100) ** num_of_years

    def project_revenue(self) -> float | None:
        """Project future revenue based on user assumptions."""
        curr_revenue = self.analysis_summary.get('ttm_revenue', None)
        return self.calc_future_value(
            curr_revenue,
            self.user_assumptions['yoy_growth_revenue'],
            self.user_assumptions['num_of_years'],
        )

    def project_net_income(self) -> float | None:
        """Project future net income based on user assumptions."""
        projected_revenue = self.project_revenue()
        if projected_revenue is None:
            return None
        return self.user_assumptions['net_margin'] * projected_revenue

    def project_shares_outstanding(self) -> float | None:
        """Project future shares outstanding based on user assumptions."""
        curr_shares_outstanding = self.analysis_summary.get('shares_outstanding', None)
        return self.calc_future_value(
            curr_shares_outstanding,
            self.user_assumptions['yoy_growth_share_count'],
            self.user_assumptions['num_of_years'],
        )

    def project_eps(self) -> float | None:
        net_income = self.project_net_income()
        shares = self.project_shares_outstanding()
        if net_income is None or shares in (None, 0):
            return None
        return net_income / shares

    def calc_stock_valuation(self) -> float | None:
        eps = self.project_eps()
        if eps is None:
            return None
        return self.user_assumptions['estimated_pe'] * eps

    def calc_stock_market_cap(self) -> float | None:
        valuation = self.calc_stock_valuation()
        shares = self.project_shares_outstanding()
        if valuation is None or shares is None:
            return None
        return valuation * shares

    def calc_upside_downside_potential(self) -> float | None:
        valuation = self.calc_stock_valuation()
        current_price = self.analysis_summary.get('current_price', None)
        if valuation is None or current_price in (None, 0):
            return None
        return ((valuation - current_price) / current_price) * 100