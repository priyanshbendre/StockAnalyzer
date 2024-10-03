import yfinance as yf
import sys
from texttable import Texttable
import json
import asyncio

class Stock_Data:
    def __init__(self, ticker):
        self.ticker = ticker
        self.stock = yf.Ticker(ticker)
        self.stock_info = self.stock.info
        self.quarterly_financials = self.stock.quarterly_financials
        self.annual_financials = self.stock.financials
        self.cashflow = self.stock.cashflow

    def get_net_margin(self):
        ttm_net_income = self.quarterly_financials.loc['Net Income'].iloc[:4].sum()
        ttm_revenue = self.stock_info.get('totalRevenue', None)
        
        if ttm_net_income is not None and ttm_revenue is not None:
            net_margin = (ttm_net_income / ttm_revenue) * 100
        else:
            net_margin = None
        
        return net_margin

    def get_gross_profit_margin(self):
        ttm_gross_profit = self.quarterly_financials.loc['Gross Profit'].iloc[:4].sum()
        ttm_revenue = self.quarterly_financials.loc['Total Revenue'].iloc[:4].sum()
        
        if ttm_gross_profit is not None and ttm_revenue is not None:
            gross_profit_margin = (ttm_gross_profit / ttm_revenue) * 100
        else:
            gross_profit_margin = None
        
        return gross_profit_margin

    def calc_cagr_equation(self, years, value_start, value_end):
        """Calculate the Compound Annual Growth Rate (CAGR)."""
        if value_start == 0 or years <= 0:
            raise ValueError("Check Past Value or number of years for CAGR")
        cagr = (value_end/value_start)**(1/years) - 1
        if isinstance(cagr, complex):
            return None
        else:
            return cagr

    def calc_cagr(self, row_label="Total Revenue"):
        """Calculate CAGR for a specified row in the annual financials."""
        try:
            values = self.annual_financials.loc[row_label].iloc[:3].values

            if len(values) < 3:
                raise ValueError("Not enough data to calculate CAGR.")
                return None
            
            value_start = values[-1]  # Oldest value
            value_end = values[0]     # Most recent value
            years = 3  # Number of years
            
            cagr = self.calc_cagr_equation(years, value_start, value_end)
            if cagr != None:
                return cagr * 100  # Convert to percentage
            else:
                return None
        except KeyError as e:
            print(f"Error calculating CAGR for '{row_label}': Row label not found.")
            print(f"Available row labels: \n{self.annual_financials.index}\n")
            sys.exit("Stopping Execution")  # Exit the program if the row label is not found
        except Exception as e:
            print(f"Error calculating CAGR for '{row_label}': {e}")
            return None

    def calc_cashflow_avg(self, row_label="Free Cash Flow"):
        """Calculate the average of a specified row in the cash flow statement over the past 3 years."""
        try:
            return self.cashflow.loc[row_label].iloc[:3].mean()
        except KeyError as e:
            print(f"Error calculating average for '{row_label}': Row label not found.")
            print(f"Available row labels: \n{self.cashflow.index}\n")
            sys.exit("Stopping Execution")  # Exit the program if the row label is not found
        except Exception as e:
            print(f"Error calculating average for '{row_label}': {e}")
            return None

    def ratio_pe(self):
        """Calculate the current Price-to-Earnings (PE) ratio."""
        try:
            pe_ratio = self.stock_info.get('trailingPE', None)
            # if pe_ratio is None:
            #     raise ValueError("PE ratio not available.")
            return pe_ratio
        except Exception as e:
            print(f"WARN: retrieving PE ratio: {e}")
            return None

    def ratio_free_cash_flow_yield(self):
        """Calculate the Free Cash Flow Yield."""
        try:
            free_cash_flow_ttm = self.cashflow.loc['Free Cash Flow'].iloc[:4].sum()
            market_cap = self.stock_info.get('marketCap', None)
            
            if free_cash_flow_ttm is not None and market_cap is not None:
                return (free_cash_flow_ttm / market_cap) * 100
            else:
                return None
        except Exception as e:
            print(f"Error calculating Free Cash Flow Yield: {e}")
            return None

    def ratio_peg(self):
        """Calculate the PEG (Price/Earnings to Growth) ratio."""
        try:
            pe_ratio = self.stock_info.get('trailingPE', None)
            cagr_eps = self.calc_cagr("Basic EPS")
            
            if pe_ratio is not None and cagr_eps is not None and cagr_eps != 0:
                peg_ratio = pe_ratio / cagr_eps
                return peg_ratio
            else:
                return None
        except Exception as e:
            print(f"Error calculating PEG ratio: {e}")
            return None

    def metric_avg_fcf_to_total_debt(self):
        """Calculate the ratio of average Free Cash Flow to Total Debt."""
        try:
            avg_free_cash_flow = self.calc_cashflow_avg()
            total_debt = self.stock_info.get('totalDebt', None)
            
            if avg_free_cash_flow is not None and total_debt is not None and total_debt != 0:
                return total_debt / avg_free_cash_flow
            else:
                return None
        except Exception as e:
            print(f"Error calculating Free Cash Flow to Total Debt ratio: {e}")
            return None

    def data_summary(self):
        """Generate and return a dictionary of the financial summary of the stock."""
        # divyield_percent = self.stock_info.get('dividendYield', None)
        # if divyield_percent == None:
        #     divyield_percent = 'N/A'
        # else:
        #     divyield_percent *= 100


        return {
            "company_name": self.stock_info.get('shortName', 'N/A'),
            "current_price": self.stock_info.get('currentPrice', None),
            "market_cap": self.stock_info.get('marketCap', None),
            "ttm_revenue": self.stock_info.get('totalRevenue', None),
            "eps": self.stock_info.get('trailingEps', None),
            "pe_ratio": self.ratio_pe(),
            "gross_profit_margin_in%": self.get_gross_profit_margin(),
            "net_margin_in%": self.get_net_margin(),
            
            "cagr_revenue_in%": self.calc_cagr(),
            "cagr_share_count_in%": self.calc_cagr("Diluted Average Shares"),
            "total_debt": self.stock_info.get('totalDebt', None),
            "avg_free_cash_flow": self.calc_cashflow_avg(),
            # "dividend_yield_in%": divyield_percent,
            "dividend_yield_in%": self.stock_info.get('dividendYield', None),            
            "fcf_yield_in%": self.ratio_free_cash_flow_yield(),
            "peg_ratio": self.ratio_peg(),
            "avg_fcf_to_total_debt": self.metric_avg_fcf_to_total_debt(),
            "shares_outstanding": self.stock_info.get('sharesOutstanding', None),
        }

# def get_summary_for_tickers(tickers):
#     summary = {}
#     for ticker in tickers:
#         print(f"--- Analyzing {ticker} ---")
#         stock_data = Stock_Data(ticker)
#         summary[ticker] = stock_data.data_summary()

#     return summary

def convert_to_human_readable(number):
    """Convert a number to a human-readable format (K, M, B, T)."""
    if isinstance(number, (int, float)):  # Ensure number is an int or float
        for unit in ['', 'K', 'M', 'B', 'T']:
            if abs(number) < 1000:
                return f"{number:.2f}{unit}".rstrip('0').rstrip('.')
            number /= 1000
        return f"{number:.2f}T".rstrip('0').rstrip('.')
    return number  # Return the original value if it's not a number

def merge_dict_values(data):
    """Merge values of all parent keys in the dictionary into a list of lists."""
    # Extract the keys (metrics) from the first sub-dictionary
    metrics = list(data[next(iter(data))].keys())
    
    # Initialize an empty list to store the result
    merged_list = []
    
    # Iterate through each metric
    for metric in metrics:
        # Start each sublist with the metric name
        metric_values = [metric]
        
        # Append the value from each parent key to the sublist, formatting if necessary
        for parent_key in data:
            value = data[parent_key][metric]
            formatted_value = convert_to_human_readable(value) if isinstance(value, (int, float)) else value
            metric_values.append(formatted_value)
        
        # Add the sublist to the merged list
        merged_list.append(metric_values)
    
    return merged_list

async def async_get_stock_data_async(semaphore, ticker):
    async with semaphore:
        print(f"--- Analyzing {ticker} ---")
        loop = asyncio.get_event_loop()
        stock_data = await loop.run_in_executor(None, Stock_Data, ticker)
        return ticker, stock_data.data_summary()

async def async_get_summary_for_tickers(tickers, max_concurrent=5):
    semaphore = asyncio.Semaphore(max_concurrent)
    tasks = []
    for ticker in tickers:
        task = async_get_stock_data_async(semaphore, ticker)
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    
    summary = {}
    for ticker, data in results:
        summary[ticker] = data
    return summary


if __name__ == "__main__":
    # Example usage
    tickers = ["CDNS", "AMD", "INTC"]
    #analysis_summary = get_summary_for_tickers(tickers) #replaced with async API call
    analysis_summary = asyncio.run(async_get_summary_for_tickers(tickers))
    # print(analysis_summary) #write to CSV

    file_path = "./ticker_data.json"
    print("Writing JSON file now...")
    with open(file_path, 'w') as file:
        json.dump(analysis_summary, file, indent=4)
    print(f"Data has been written to {file_path}\n")

    #print table
    table = Texttable()
    #columns
    list_table_header = ["metrics"] + tickers
    table.header(list_table_header)
    list_width = len(tickers)*[12]
    table.set_cols_width([30]+list_width)
    # table.set_cols_width([10, 20, 30, 40, 50])
    #rows
    analysis_summary_table_data = merge_dict_values(analysis_summary)
    for i in range(len(analysis_summary_table_data)):
        table.add_row(analysis_summary_table_data[i])
    print(table.draw())

