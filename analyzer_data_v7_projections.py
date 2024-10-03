import json

class Stock_Projections:
    def __init__(self, stock_ticker):
        """
        Initialize Stock_Projections with the analysis summary and user assumptions.

        Parameters:
            analysis_summary (dict): Dictionary containing financial data for the stock.
            user_assumptions (dict): Dictionary containing user assumptions for projections.
        """
        self.stock_ticker = stock_ticker
        self.analysis_summary = self.read_analysis_summary()
        self.user_assumptions = self.user_assumptions_input()

    def read_analysis_summary(self):
        with open('ticker_data.json', 'r') as json_file:
            stock_data = json.load(json_file)
        return stock_data[self.stock_ticker]

    def user_assumptions_input(self):
        """
        Take user assumptions as input
        """
        user_assumptions={}
        user_assumptions['yoy_growth_revenue'] = 0.02 #expected growth yoy
        user_assumptions['num_of_years'] = 5 #Number of years of analysis
        user_assumptions['yoy_growth_shareCount'] = 0.05 #share count change in percent positive refers to dilution
        user_assumptions['Estimated_PE'] = 20 #Estimated PE at the end of number of years of analysis
        user_assumptions['net_margin'] = 0.10 #Net Margin average or consistent throughout the number of years of analysis
        return user_assumptions

    def calc_cagr_final_val(self, current_value, growth_rate, num_of_years):
        """
        Calculate the future value based on CAGR.

        Parameters:
            current_value (float): The current value of the metric (e.g., revenue, shares outstanding).
            growth_rate (float): The annual growth rate as a percentage.
            num_of_years (int): The number of years over which to project.

        Returns:
            float: The projected future value.
        """
        if current_value is None or growth_rate is None or num_of_years <= 0:
            return None
        future_value = current_value * (1 + growth_rate / 100) ** num_of_years
        return future_value

    def project_revenue(self):
        """
        Project future revenue based on user assumptions.

        Returns:
            float: Projected revenue after the specified number of years.
        """
        curr_revenue = self.analysis_summary.get('ttm_revenue', None)
        return self.calc_cagr_final_val(curr_revenue, self.user_assumptions['yoy_growth_revenue'], self.user_assumptions['num_of_years'])

    def project_net_income(self):
        """
        Project future net income based on user assumptions.

        Returns:
            float: Projected net income after the specified number of years.
        """
        projected_revenue = self.project_revenue()
        return self.user_assumptions['net_margin'] * projected_revenue

    def project_shares_outstanding(self):
        """
        Project future shares outstanding based on user assumptions.

        Returns:
            float: Projected shares outstanding after the specified number of years.
        """
        curr_shares_outstanding = self.analysis_summary.get('shares_outstanding', None)
        return self.calc_cagr_final_val(curr_shares_outstanding, self.user_assumptions['yoy_growth_shareCount'], self.user_assumptions['num_of_years'])

    def project_eps(self):
        return self.project_net_income()/self.project_shares_outstanding()

    def calc_stock_valuation(self):
        return self.user_assumptions['Estimated_PE']*self.project_eps()

    def calc_stock_market_cap(self):
        return self.calc_stock_valuation()*self.project_shares_outstanding()

    def calc_upside_downside_potential(self):
        return ((self.calc_stock_valuation() - self.analysis_summary.get('current_price', None))/(self.analysis_summary.get('current_price', None)))*100


#create class object
stock_tickers = ['CDNS', 'INTC']

print("Stock Projections:")
for tick in stock_tickers:
    projections = Stock_Projections(tick)

    print(f"\nCurrent Stock Data:")
    print(f"{projections.analysis_summary}")

    print(f"\nInput User Assumptions:\n{projections.user_assumptions_input()}")
    
    print(f"\nThe Projected Revenue is: ${projections.project_revenue():,.2f}")
    print(f"The Projected Net Income is: ${projections.project_net_income():,.2f}")
    print(f"The Projected Shares outstanding is: {projections.project_shares_outstanding():,.2f}")
    print(f"The Projected EPS is: ${projections.project_eps():,.2f}")
    print(f"The Projected Stock Price: ${projections.calc_stock_valuation():,.2f}")
    print(f"The Projected Market Cap: ${projections.calc_stock_market_cap():,.2f}")

    print(f"\nUpside/Downside Potential for stock price: {projections.calc_upside_downside_potential():,.2f}%")