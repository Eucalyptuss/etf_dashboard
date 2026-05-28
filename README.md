# US ETF Portfolio Dashboard

Code Version: `v1.4.0`  
Prepared by: `Eucalyptuss`

## 1. Project Description

This is a Python Streamlit dashboard for managing a US ETF portfolio from a CSV transaction ledger.

Version `v1.4.0` upgrades the previous buy-only structure to a full transaction-ledger model that supports both BUY and SELL transactions. SELL transactions are matched to BUY lots using FIFO by account and ticker. If a position is fully sold and the remaining shares become zero, the ticker is treated as a `Closed Position`.

The dashboard shows:

- Active ETF holdings
- Closed positions
- FIFO realized gains/losses
- Unrealized gains/losses
- Total P/L
- Estimated annual dividend
- Estimated upcoming dividend dates
- Price trend, moving averages, buy/sell markers, benchmark comparison, and drawdown
- CSV editing and download
- Data quality validation

## 2. Folder Structure

```text
etf_dashboard/
├── app.py
├── requirements.txt
├── portfolio.csv
├── sample_portfolio.csv
└── README.md
```

## 3. Installation

```bash
pip install -r requirements.txt
```

## 4. Run

```bash
streamlit run app.py
```

## 5. CSV Format

The default data file is `portfolio.csv`. Place it in the same folder as `app.py`.

### New BUY/SELL transaction ledger schema

```csv
transaction_date,transaction_type,ticker,shares,price,fee,account,note
2025-03-12,BUY,SCHD,20,77.35,0,Fidelity,dividend core
2026-01-10,SELL,SCHD,5,82.00,0,Fidelity,partial sell
```

### Column Definitions

| Column | Required | Description |
|---|---:|---|
| transaction_date | Yes | Transaction date in `YYYY-MM-DD` format |
| transaction_type | Yes | `BUY` or `SELL` |
| ticker | Yes | ETF ticker symbol |
| shares | Yes | Positive share quantity. Do not use negative shares for SELL. |
| price | Yes | Transaction price per share |
| fee | No | Transaction fee. Defaults to `0` |
| account | No | Account name. Defaults to `Default` |
| note | No | Free-text note |

## 6. Legacy CSV Compatibility

The app still accepts the older buy-only CSV format:

```csv
ticker,purchase_date,shares,buy_price,fee,account,note
SCHD,2025-03-12,20,77.35,0,Fidelity,dividend core
```

When detected, the app converts it in memory to:

```csv
transaction_date,transaction_type,ticker,shares,price,fee,account,note
2025-03-12,BUY,SCHD,20,77.35,0,Fidelity,dividend core
```

Download the edited CSV from the Data Manager tab to permanently migrate to the new schema.

## 7. SELL and Closed Position Logic

SELL transactions must be entered with positive `shares` and `transaction_type=SELL`.

Example:

```csv
transaction_date,transaction_type,ticker,shares,price,fee,account,note
2025-03-12,BUY,SCHD,20,77.35,0,Fidelity,buy
2026-01-10,SELL,SCHD,20,82.00,0,Fidelity,full sell
```

The app calculates:

```text
Current shares = BUY shares - SELL shares
Realized P/L = net sell proceeds - FIFO matched cost basis
Unrealized P/L = current market value - remaining open-lot cost basis
Total P/L = Realized P/L + Unrealized P/L
```

If current shares become zero:

- Holding Status becomes `Closed`
- Market Value becomes `$0.00`
- Unrealized P/L becomes `$0.00`
- Realized P/L remains visible
- Dividend projection is excluded
- The ticker is hidden from Holdings by default
- Enable `Show Closed Positions` in the Sidebar to display it

## 8. Dividend Calculation

Dividend estimates are based on yfinance historical dividends.

Supported modes:

1. `Last 12M`  
   Uses the last 12 months of dividend-per-share history.

2. `Recent Dividend × Frequency`  
   Uses the most recent dividend and inferred annual frequency.

3. `Scenario`  
   Shows Conservative/Base/Optimistic projections using 90%/100%/110% of Last 12M dividends.

Dividend frequency is inferred from historical dividend intervals:

| Average Interval | Frequency |
|---:|---|
| 20-40 days | Monthly |
| 70-110 days | Quarterly |
| 150-220 days | Semi-Annual |
| 300+ days | Annual |
| Insufficient data | Unknown |

Future dividend dates are shown as `Estimated` unless directly confirmed. This app does not treat pattern-based estimates as confirmed dividend announcements.

## 9. Data Sources and Limits

- Current price: yfinance
- Historical price: yfinance
- Historical dividends: yfinance
- Future dividend dates: historical pattern estimate only

Important limitations:

- yfinance data can be delayed, incomplete, or unavailable.
- Dividend estimates are not official announcements.
- Pay dates are generally marked `Unknown` unless reliable data is available.
- This app does not calculate tax lots for tax filing.
- FIFO is used for dashboard-level performance tracking, not official tax advice.

## 10. Streamlit Community Cloud Deployment

1. Push this folder to GitHub.
2. Make sure these files are included:
   - `app.py`
   - `requirements.txt`
   - `portfolio.csv`
   - `README.md`
3. Deploy the repository from Streamlit Community Cloud.
4. Set the main file path to:

```text
app.py
```

For persistent portfolio updates on Streamlit Cloud, download the edited `portfolio.csv` from the Data Manager tab and commit it back to GitHub. Local file writes on Streamlit Cloud should not be treated as permanent storage.

## 11. Disclaimer

This dashboard is for portfolio monitoring and personal recordkeeping only. It is not investment, tax, accounting, or legal advice. Verify all price, dividend, and tax-lot information before making investment or reporting decisions.
