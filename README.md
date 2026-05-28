# US ETF Portfolio Dashboard

A Streamlit-based dashboard for monitoring a U.S. ETF portfolio from a CSV transaction ledger.

The app combines:

- User-managed ETF purchase records from CSV
- Latest price lookup through `yfinance`
- Historical price charts
- Historical dividend analysis
- Estimated annual dividend projections
- Estimated upcoming dividend calendar
- CSV editing and download through Streamlit

> This project is for portfolio monitoring and data organization only. It is not investment advice. Always verify market prices, dividend dates, and dividend amounts from official broker, fund sponsor, or exchange sources before making decisions.

---

## 1. Project Structure

```text
etf_dashboard/
├── app.py
├── requirements.txt
├── portfolio.csv
├── sample_portfolio.csv
└── README.md
```

---

## 2. Installation

Create a virtual environment, install the dependencies, and run Streamlit.

```bash
cd etf_dashboard
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

---

## 3. Run

```bash
streamlit run app.py
```

---

## 4. Default Portfolio File

The app now reads `portfolio.csv` from the same folder as `app.py` on startup. This file is the default transaction ledger.

Behavior:

- If `portfolio.csv` exists next to `app.py`, the app loads it automatically on startup.
- If `portfolio.csv` exists in the current working directory, the app can also load it as a secondary fallback.
- If `portfolio.csv` is missing or unreadable, the app falls back to `sample_portfolio.csv`.
- If the app is still in default mode, changes to `portfolio.csv` are detected by file size/modified-time signature and reloaded.
- If you upload a CSV from the sidebar, the uploaded file overrides `portfolio.csv` for the current session only.
- Clicking `Reload portfolio.csv` resets the uploader state and forces the app back to `portfolio.csv`.
- The Data Manager tab can download the edited ledger as `portfolio.csv`.
- In local execution, the Data Manager tab also includes `Save to local portfolio.csv`.
- In Streamlit Community Cloud, local writes may not persist after restart or redeployment, so download `portfolio.csv` and commit/replace it in the repository if you want it to load by default.

---

## 5. CSV Format

Required columns:

```csv
ticker,purchase_date,shares,buy_price
```

Optional columns:

```csv
fee,account,note
```

Full example:

```csv
ticker,purchase_date,shares,buy_price,fee,account,note
SCHD,2025-03-12,20,77.35,0,Fidelity,dividend core
JEPI,2025-04-10,15,56.20,0,Fidelity,income
VOO,2025-05-02,5,474.10,0,Robinhood,index core
```

If optional columns are missing, the app creates them automatically:

- `fee`: `0`
- `account`: `Default`
- `note`: empty string

---

## 6. Main Features

### Overview

- Total invested
- Current market value
- Unrealized profit/loss
- Portfolio return percentage
- Estimated annual dividend
- Estimated dividend amount in the next 30 days
- Portfolio value trend
- Allocation by ETF
- Top gainers / losers
- Upcoming estimated dividends

### Holdings

- Shares
- Average buy price
- Current price
- Cost basis
- Market value
- Unrealized P/L
- Return %
- Portfolio weight
- Last 12-month dividend per share
- Estimated annual dividend
- Yield on cost
- Current yield
- Dividend frequency
- Next estimated ex-date
- Next estimated pay date
- Dividend status

### Dividend

- Monthly estimated dividend calendar
- Upcoming dividend table
- Annual dividend projection by ETF
- Dividend yield comparison
- Dividend history chart
- Dividend data confidence table
- Conservative / Base / Optimistic scenario projection

### Price Trend

- Selected ETF price chart
- 20-day and 60-day moving averages
- Buy date markers
- Average buy price line
- Current price line
- Normalized performance comparison
- Benchmark comparison
- Drawdown chart

### Data Manager

- Edit current CSV data with `st.data_editor`
- Add or delete transaction rows
- Download edited CSV
- View data quality issues
- View normalized CSV

---

## 7. Dividend Calculation Methods

### Mode 1: Last 12M

Uses the sum of dividends per share over the last 12 months.

```text
estimated_annual_dividend = last_12m_dividend_per_share × total_shares
```

### Mode 2: Recent Dividend × Frequency

Uses the most recent dividend per share and an estimated frequency inferred from historical dividend intervals.

```text
estimated_annual_dividend = recent_dividend_per_share × estimated_frequency × total_shares
```

### Mode 3: Scenario

Uses the last 12-month dividend as the base case.

```text
Conservative = Last 12M Dividend × 90%
Base = Last 12M Dividend
Optimistic = Last 12M Dividend × 110%
```

---

## 8. Dividend Data Status Policy

Dividend accuracy is intentionally conservative.

- `Confirmed`: Reserved for explicitly confirmed data. The MVP generally does not mark yfinance-derived future dividend dates as confirmed.
- `Estimated`: Future date inferred from historical dividend intervals.
- `Unknown`: Not enough data to infer a date.
- `No Dividend History`: No dividend history returned by yfinance.

Important: yfinance historical dividend data generally gives historical dividend events, but it does not reliably provide future confirmed ex-dates or pay dates for every ETF. Therefore, the app does not present estimated future dates as confirmed.

---

## 9. Data Source Limitations

The MVP uses `yfinance` as the default data source.

Limitations:

- Price data may be delayed or unavailable.
- Dividend history may be incomplete.
- Future dividend dates are usually not confirmed.
- Pay dates are not reliably available from the default yfinance dividend series.
- ETF distributions can change based on fund policy, market conditions, and fund holdings.

For production-grade use, consider adding official ETF sponsor data, broker data, Nasdaq dividend calendar data, or another paid market data API.

---

## 10. Streamlit Community Cloud Deployment

1. Push the `etf_dashboard` folder to a GitHub repository.
2. Go to Streamlit Community Cloud.
3. Create a new app from the repository.
4. Set the main file path to:

```text
app.py
```

or, if the app is inside a folder:

```text
etf_dashboard/app.py
```

5. Streamlit will install dependencies from `requirements.txt`.

---

## 11. Notes and Warnings

- This app does not store edited CSV data permanently on Streamlit Cloud.
- Download the edited CSV as `portfolio.csv` after making changes.
- For default startup loading, keep `portfolio.csv` in the same folder as `app.py`.
- Online data lookup failures are shown in the Data Quality section.
- The app continues running with valid rows even if some rows or tickers fail validation.
- This is not investment, tax, or legal advice.
