#!/usr/bin/python3

DEFAULT_ASSUMPTIONS = {
    "yoy_growth_revenue": 0.02,          # fallback yoy revenue growth (percent)
    "num_of_years": 5,                   # number of years of analysis
    "yoy_growth_share_count": 0.05,      # fallback share count change per year in percent (positive = dilution)
    "estimated_pe": 20,                  # estimated PE at the end of the analysis period (static default)
    "net_margin": 0.10,                  # fallback net margin used throughout the analysis period (fraction)
}

DEFAULT_HAIRCUT = 0.8

# Assumptions derived from the stock's own data: assumption key -> (summary key, divisor).
# estimated_pe is intentionally absent: it has no data equivalent, so it stays at its static default.
# Note the units differ: the growth keys are percents, while net_margin is a fraction (hence /100).
DERIVED_ASSUMPTIONS = {
    "yoy_growth_revenue": ("cagr_revenue_3y_in%", 1),
    "yoy_growth_share_count": ("cagr_share_count_3y_in%", 1),
    "net_margin": ("net_margin_in%", 100),
}


def derive_assumptions(analysis_summary: dict, user_assumptions: dict | None = None) -> dict:
    """Build the effective assumptions.

    Static defaults are overridden by user config, then by 80% of the stock's
    own current values where the config did not specify a value and the data is
    available.
    """
    user_assumptions = user_assumptions or {}
    assumptions = dict(DEFAULT_ASSUMPTIONS)
    assumptions.update(user_assumptions)

    for key, (summary_key, divisor) in DERIVED_ASSUMPTIONS.items():
        if key not in user_assumptions:
            value = analysis_summary.get(summary_key)
            if value is not None:
                assumptions[key] = DEFAULT_HAIRCUT * value / divisor

    return assumptions


class StockProjections:
    def __init__(self, analysis_summary: dict, user_assumptions: dict | None = None):
        self.analysis_summary = analysis_summary
        self.user_assumptions = derive_assumptions(analysis_summary, user_assumptions)

    @staticmethod
    def calc_future_value(current_value: float | None, growth_rate: float | None, num_of_years: int) -> float | None:
        """Calculate the future value of a metric growing at a rate over N years."""
        if current_value is None or growth_rate is None or num_of_years <= 0:
            return None
        return current_value * (1 + growth_rate / 100) ** num_of_years

    def _project(self, summary_key: str, growth_key: str) -> float | None:
        """Grow a summary metric at its assumption's rate over num_of_years."""
        return self.calc_future_value(
            self.analysis_summary.get(summary_key, None),
            self.user_assumptions[growth_key],
            self.user_assumptions['num_of_years'],
        )

    def project_revenue(self) -> float | None:
        """Project future revenue based on user assumptions."""
        return self._project('ttm_revenue', 'yoy_growth_revenue')

    def project_shares_outstanding(self) -> float | None:
        """Project future shares outstanding based on user assumptions."""
        return self._project('shares_outstanding', 'yoy_growth_share_count')

    def project_net_income(self) -> float | None:
        """Project future net income based on user assumptions."""
        projected_revenue = self.project_revenue()
        if projected_revenue is None:
            return None
        return self.user_assumptions['net_margin'] * projected_revenue

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