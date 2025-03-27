# StockAnalyzer
Calculate Stock Projections and Important Ratios


# **User Guide for Stock Analysis Script**

## **Overview**
This Python script retrieves and analyzes financial data for multiple stock tickers using the `yfinance` library. It calculates key financial metrics and saves the results in a JSON file while also displaying the data in a formatted table.

## **Installation**
Before running the script, ensure you have the required dependencies installed:

```bash
pip install yfinance texttable
```

## **How to Use the Script**
### **1. Input: Stock Tickers**
- The script takes a list of stock tickers as input via the `tickers` variable in the `main` method.
- Modify the `tickers` list with the symbols of the stocks you want to analyze.
- Example:

    ```python
    tickers = ["CDNS", "AMD", "INTC"]
    ```

- You can include as many stock symbols as needed.

### **2. Running the Script**
Run the script using:

```bash
python script_name.py
```

### **3. Output**
#### **JSON File**
The script generates a JSON file (`ticker_data.json`) containing stock analysis data for all tickers.

#### **Formatted Table**
The script prints a structured table comparing financial metrics for the given tickers.

## **Understanding the Output**
The output includes key metrics such as:
- **Company Name**
- **Current Price**
- **Market Cap**
- **Revenue Growth (CAGR)**
- **Earnings Per Share (EPS)**
- **PE Ratio, PEG Ratio**
- **Net & Gross Profit Margins**
- **Free Cash Flow Yield**
- **Total Debt**
- **Dividend Yield**
- **Shares Outstanding**

The table format allows for easy comparison of these metrics across different stocks.

## **Script Workflow**
1. **Retrieves stock data** asynchronously for each ticker.
2. **Calculates financial metrics** using the `Stock_Data` class.
3. **Writes the results to `ticker_data.json`**.
4. **Displays a comparison table** for quick reference.

## **Customization**
- Modify the `tickers` list to analyze different stocks.
- Add new financial metrics inside the `Stock_Data` class.
- Adjust the formatting or save the output in different formats (CSV, Excel).
