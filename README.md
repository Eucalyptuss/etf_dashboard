# US ETF Portfolio Dashboard

Prepared by **Eucalyptuss**  
Code Version: **v1.5.1**

This Streamlit dashboard manages a U.S. ETF portfolio using CSV files. It supports BUY/SELL transaction tracking, FIFO realized P/L, active and closed positions, estimated dividend projections from yfinance, and actual dividend cash-flow tracking from a separate dividend CSV.

This is not investment, tax, or financial advice. Data from yfinance can be delayed, incomplete, or inaccurate. Confirm all investment, dividend, and tax information independently.

---

## 1. Project Structure

```text
etf_dashboard/
├── app.py
├── portfolio.csv
├── dividends.csv
├── sample_portfolio.csv
├── sample_dividends.csv
├── requirements.txt
└── README.md
```

---

## 2. Installation

```bash
pip install -r requirements.txt
```

---

## 3. Run Locally

```bash
streamlit run app.py
```

The app reads `portfolio.csv` and `dividends.csv` from the same folder as `app.py` by default.

---

## 4. Portfolio Transaction CSV

`portfolio.csv` stores only BUY and SELL transactions.

```csv
transaction_date,transaction_type,ticker,shares,price,fee,account,note
2025-03-12,BUY,SCHD,20,77.35,0,Fidelity,dividend core
2026-01-10,SELL,SCHD,5,82.00,0,Fidelity,partial sell
```

Rules:

- `transaction_type` must be `BUY` or `SELL`.
- `shares` is always positive.
- Do not use negative shares for sales.
- SELL transactions are matched to BUY lots using FIFO within the same account and ticker.
- BUY fees are included in cost basis.
- SELL fees are subtracted from sale proceeds.
- Closed positions remain in the performance calculation even when hidden from Holdings.

Legacy buy-only CSV files with `purchase_date` and `buy_price` can still be loaded. They are converted in memory to the new transaction-ledger schema.

---

## 5. Actual Dividend CSV

`dividends.csv` stores actual dividend payments that were deposited into the account.

```csv
payment_date,ticker,net_amount,account,note
2026-01-15,SCHD,18.42,Fidelity,Q1 dividend
2026-01-20,JEPI,7.85,Fidelity,monthly dividend
```

Rules:

- `payment_date`, `ticker`, and `net_amount` are required.
- `account` defaults to `Default` if missing.
- `note` defaults to blank if missing.
- `net_amount` should usually be the actual net amount deposited after withholding.
- Dividends are not mixed into `portfolio.csv` because dividends are cash flows, not quantity-changing trades.

---

## 6. Main Features

### Portfolio and P/L

- Active holdings calculation
- Closed position handling when shares reach zero
- FIFO realized P/L
- Unrealized P/L
- Total P/L excluding dividends
- Total return percentage using tracked FIFO cost basis
- Buy and sell markers on price charts

### Actual Dividend Tracking

- `dividends.csv` automatic loading
- Actual dividends YTD
- Actual dividends last 12 months
- Actual dividends all-time
- Monthly actual dividend chart
- Cumulative actual dividend trend
- Actual dividend by ETF
- Actual dividend by account
- Estimated annual dividend vs actual last-12-month dividend comparison

### Dividend-Inclusive Performance

The dashboard calculates:

```text
Dividend-Inclusive Total P/L = Realized P/L + Unrealized P/L + Actual Dividends Received
Dividend-Adjusted Return % = Dividend-Inclusive Total P/L / Tracked FIFO Cost Basis
```

Closed position total performance includes actual dividends received while that ticker was held if those dividend rows exist in `dividends.csv`.

### Estimated Dividend Projection

Estimated dividends use yfinance historical dividends and a pattern-based frequency estimate. Future dividend dates are not treated as confirmed unless a reliable confirmed source is added in the future.

Status values include:

- Estimated
- Unknown
- No Dividend History
- Excluded - Closed

---

## 7. Data Manager

The Data Manager tab provides two editors:

1. Portfolio Transactions Manager
   - Edit BUY/SELL rows
   - Add new transactions
   - Download `portfolio.csv`
   - Save locally when running outside Streamlit Cloud

2. Dividend Payments Manager
   - Edit actual dividend payment rows
   - Add new dividend payments
   - Download `dividends.csv`
   - Save locally when running outside Streamlit Cloud

On Streamlit Community Cloud, local file writes are not permanent. Download the edited CSV and update the repository file manually.

---

## 8. Streamlit Cloud Deployment

1. Push this folder to GitHub.
2. Deploy with Streamlit Community Cloud.
3. Set `app.py` as the entry file.
4. Keep `portfolio.csv` and `dividends.csv` in the repository.
5. After editing data in the dashboard, download the updated CSV and commit it back to GitHub.

---

## 9. Data Source Limitations

- yfinance is used for current prices, historical prices, and historical dividend data.
- yfinance does not reliably provide confirmed future ETF dividend pay dates.
- Future dividend dates shown by the dashboard are estimates based on historical patterns.
- Actual dividend cash-flow numbers come only from `dividends.csv`.
- The dashboard does not calculate tax lots for tax filing and does not replace brokerage records.

---

## 10. Version Notes

### v1.5.1

- Improved spacing between the upper and lower Portfolio Summary KPI card rows.
- Added a dedicated KPI row spacer for cleaner dashboard readability.
- No calculation logic changes.

### v1.5.0

- Added `dividends.csv` support.
- Added `sample_dividends.csv`.
- Added actual dividend KPI cards.
- Added dividend-inclusive total return calculation.
- Added monthly actual dividend and cumulative dividend chart.
- Added actual dividend by ETF and by account charts.
- Added estimated annual dividend vs actual last-12-month dividend comparison.
- Added Dividend Payments Manager in the Data Manager tab.
- Preserved BUY/SELL FIFO logic and closed position handling from v1.4.x.

### v1.4.1

- Added explicit Streamlit chart keys to fix duplicate Plotly element ID errors.

### v1.4.0

- Added BUY/SELL transaction ledger support.
- Added FIFO realized P/L.
- Added closed position handling.
