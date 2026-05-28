from __future__ import annotations

import io
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from zoneinfo import ZoneInfo

# ============================================================
# App configuration
# ============================================================

APP_TITLE = "US ETF Portfolio Dashboard"
CREATOR_NAME = "Eucalyptuss"
APP_VERSION = "v1.3.0"
BASE_DIR = Path(__file__).resolve().parent
PORTFOLIO_CSV_NAME = "portfolio.csv"
SAMPLE_CSV_NAME = "sample_portfolio.csv"
ET = ZoneInfo("America/New_York")
TODAY = datetime.now(ET).date()

REQUIRED_COLUMNS = ["ticker", "purchase_date", "shares", "buy_price"]
OPTIONAL_COLUMNS_DEFAULTS = {
    "fee": 0.0,
    "account": "Default",
    "note": "",
}
CANONICAL_COLUMNS = REQUIRED_COLUMNS + list(OPTIONAL_COLUMNS_DEFAULTS.keys())

PERIOD_MAP = {
    "1M": "1mo",
    "3M": "3mo",
    "6M": "6mo",
    "YTD": "ytd",
    "1Y": "1y",
    "3Y": "3y",
    "MAX": "max",
}

BENCHMARK_OPTIONS = ["None", "SPY", "QQQ", "DIA", "VTI", "SCHD"]
DIVIDEND_MODES = ["Last 12M", "Recent Dividend × Frequency", "Scenario"]

SAMPLE_CSV = """ticker,purchase_date,shares,buy_price,fee,account,note
SCHD,2025-03-12,20,77.35,0,Fidelity,dividend core
JEPI,2025-04-10,15,56.20,0,Fidelity,income
VOO,2025-05-02,5,474.10,0,Robinhood,index core
"""

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# Styling
# ============================================================

def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --green: #16a34a;
            --red: #dc2626;
            --blue: #2563eb;
            --amber: #d97706;
            --gray: #6b7280;
            --lightgray: #e5e7eb;
            --cardbg: rgba(255,255,255,0.74);
            --border: rgba(148,163,184,0.35);
        }
        .main .block-container {
            padding-top: 1.3rem;
            padding-bottom: 2rem;
        }
        .dashboard-title {
            font-size: 2.05rem;
            font-weight: 800;
            line-height: 1.15;
            letter-spacing: -0.02em;
            margin-bottom: 0.2rem;
        }
        .dashboard-subtitle {
            color: #64748b;
            font-size: 0.96rem;
            margin-bottom: 1rem;
        }
        .meta-box {
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 0.8rem 1rem;
            background: rgba(248,250,252,0.72);
            margin-bottom: 1rem;
            font-size: 0.92rem;
        }
        .version-banner {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
            border: 1px solid rgba(37, 99, 235, 0.22);
            border-radius: 16px;
            padding: 0.75rem 1rem;
            background: linear-gradient(135deg, rgba(37,99,235,0.10), rgba(248,250,252,0.78));
            margin: 0.15rem 0 0.9rem 0;
            box-shadow: 0 6px 18px rgba(15,23,42,0.04);
        }
        .version-banner-title {
            font-weight: 800;
            color: #0f172a;
            letter-spacing: -0.01em;
        }
        .version-banner-meta {
            color: #475569;
            font-size: 0.9rem;
            font-weight: 650;
            white-space: nowrap;
        }
        .kpi-card {
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 1rem 1rem;
            background: var(--cardbg);
            box-shadow: 0 8px 22px rgba(15,23,42,0.06);
            height: 142px;
            min-height: 142px;
            box-sizing: border-box;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .kpi-label {
            color: #64748b;
            font-size: 0.82rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 0.45rem;
            line-height: 1.2;
            min-height: 2.0rem;
        }
        .kpi-value {
            color: #0f172a;
            font-size: 1.55rem;
            line-height: 1.15;
            font-weight: 800;
            white-space: nowrap;
        }
        .kpi-help {
            color: #64748b;
            font-size: 0.78rem;
            margin-top: 0.35rem;
            line-height: 1.2;
            min-height: 1.0rem;
        }
        .positive { color: var(--green) !important; }
        .negative { color: var(--red) !important; }
        .neutral { color: #0f172a !important; }
        .blue { color: var(--blue) !important; }
        .warning-box {
            border-left: 4px solid var(--amber);
            background: rgba(251,191,36,0.10);
            padding: 0.75rem 1rem;
            border-radius: 12px;
            margin: 0.6rem 0 1rem 0;
        }
        .small-note {
            color: #64748b;
            font-size: 0.86rem;
        }
        div[data-testid="stMetric"] {
            border: 1px solid rgba(148,163,184,0.28);
            border-radius: 16px;
            padding: 0.75rem 0.9rem;
            background: rgba(248,250,252,0.55);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# Formatting helpers
# ============================================================

def fmt_currency(value: Any, decimals: int = 2) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    try:
        return f"${float(value):,.{decimals}f}"
    except Exception:
        return "N/A"


def fmt_number(value: Any, decimals: int = 2) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    try:
        return f"{float(value):,.{decimals}f}"
    except Exception:
        return "N/A"


def fmt_pct(value: Any, decimals: int = 2, signed: bool = True) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    try:
        sign = "+" if signed and float(value) > 0 else ""
        return f"{sign}{float(value) * 100:.{decimals}f}%"
    except Exception:
        return "N/A"


def fmt_date(value: Any) -> str:
    if value is None or pd.isna(value):
        return "Unknown"
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return "Unknown"


def now_et_str() -> str:
    return datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


# ============================================================
# CSV loading and validation
# ============================================================

def load_csv_from_upload(uploaded_file: Any) -> Tuple[pd.DataFrame, str]:
    if uploaded_file is None:
        return pd.read_csv(io.StringIO(SAMPLE_CSV)), "sample_portfolio.csv"
    try:
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file)
        source = getattr(uploaded_file, "name", "uploaded CSV")
        return df, source
    except Exception as exc:
        st.error(f"CSV file could not be read: {exc}")
        return pd.DataFrame(columns=CANONICAL_COLUMNS), "CSV read failed"


def load_sample_df() -> pd.DataFrame:
    return pd.read_csv(io.StringIO(SAMPLE_CSV))


def _csv_signature(path: Path) -> str:
    try:
        stat = path.stat()
        return f"{path.resolve()}::{stat.st_mtime_ns}::{stat.st_size}"
    except Exception:
        return ""


def _read_csv_path(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def find_portfolio_csv() -> Optional[Path]:
    candidates = [
        BASE_DIR / PORTFOLIO_CSV_NAME,
        Path.cwd() / PORTFOLIO_CSV_NAME,
    ]
    seen = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def find_sample_csv() -> Optional[Path]:
    candidates = [
        BASE_DIR / SAMPLE_CSV_NAME,
        Path.cwd() / SAMPLE_CSV_NAME,
    ]
    seen = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def load_default_portfolio_df() -> Tuple[pd.DataFrame, str, str, str]:
    """Load portfolio.csv first. Fallback to sample CSV only when portfolio.csv is unavailable."""
    portfolio_path = find_portfolio_csv()
    if portfolio_path is not None:
        try:
            return (
                _read_csv_path(portfolio_path),
                f"{PORTFOLIO_CSV_NAME} ({portfolio_path})",
                "portfolio_file",
                _csv_signature(portfolio_path),
            )
        except Exception as exc:
            st.warning(f"portfolio.csv could not be read. Falling back to sample data. Error: {exc}")

    sample_path = find_sample_csv()
    if sample_path is not None:
        try:
            return (
                _read_csv_path(sample_path),
                f"{SAMPLE_CSV_NAME} ({sample_path})",
                "sample_file",
                _csv_signature(sample_path),
            )
        except Exception as exc:
            st.warning(f"sample_portfolio.csv could not be read. Falling back to embedded sample data. Error: {exc}")

    return load_sample_df(), "embedded sample_portfolio.csv", "embedded_sample", "embedded"


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().lower() for c in out.columns]
    for col, default_value in OPTIONAL_COLUMNS_DEFAULTS.items():
        if col not in out.columns:
            out[col] = default_value
    for col in REQUIRED_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan
    return out[CANONICAL_COLUMNS]


def add_quality_issue(
    issues: List[Dict[str, Any]],
    severity: str,
    row_index: Any,
    column: str,
    raw_value: Any,
    issue: str,
) -> None:
    issues.append(
        {
            "Severity": severity,
            "Row": row_index,
            "Column": column,
            "Raw Value": "" if raw_value is None else str(raw_value),
            "Issue": issue,
        }
    )


def clean_and_validate_portfolio(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    issues: List[Dict[str, Any]] = []

    if df is None or df.empty:
        add_quality_issue(issues, "Error", "ALL", "CSV", "", "CSV is empty.")
        empty = pd.DataFrame(columns=CANONICAL_COLUMNS + ["row_id"])
        return empty, pd.DataFrame(issues), pd.Series(dtype=bool)

    original_cols = [str(c).strip().lower() for c in df.columns]
    for col in REQUIRED_COLUMNS:
        if col not in original_cols:
            add_quality_issue(issues, "Error", "ALL", col, "Missing", f"Required column '{col}' is missing.")

    clean = normalize_columns(df)
    clean.insert(0, "row_id", range(1, len(clean) + 1))

    # Ticker cleanup
    clean["ticker"] = clean["ticker"].astype("string").fillna("").str.strip().str.upper()
    clean["account"] = clean["account"].astype("string").fillna("Default").str.strip()
    clean["account"] = clean["account"].replace("", "Default")
    clean["note"] = clean["note"].astype("string").fillna("")

    # Date and numeric cleanup
    raw_purchase_dates = clean["purchase_date"].copy()
    clean["purchase_date"] = pd.to_datetime(clean["purchase_date"], errors="coerce").dt.date

    for col in ["shares", "buy_price", "fee"]:
        clean[col] = pd.to_numeric(clean[col], errors="coerce")

    valid_mask = pd.Series(True, index=clean.index)

    for idx, row in clean.iterrows():
        row_no = row["row_id"]
        if row["ticker"] == "" or pd.isna(row["ticker"]):
            add_quality_issue(issues, "Error", row_no, "ticker", row["ticker"], "Ticker is missing.")
            valid_mask.loc[idx] = False

        if pd.isna(row["purchase_date"]):
            add_quality_issue(
                issues,
                "Error",
                row_no,
                "purchase_date",
                raw_purchase_dates.loc[idx],
                "purchase_date format is invalid. Expected YYYY-MM-DD.",
            )
            valid_mask.loc[idx] = False
        elif row["purchase_date"] > TODAY:
            add_quality_issue(
                issues,
                "Warning",
                row_no,
                "purchase_date",
                row["purchase_date"],
                "Purchase date is in the future.",
            )

        if pd.isna(row["shares"]):
            add_quality_issue(issues, "Error", row_no, "shares", row["shares"], "shares must be numeric.")
            valid_mask.loc[idx] = False
        elif row["shares"] <= 0:
            add_quality_issue(issues, "Error", row_no, "shares", row["shares"], "shares must be greater than 0.")
            valid_mask.loc[idx] = False

        if pd.isna(row["buy_price"]):
            add_quality_issue(issues, "Error", row_no, "buy_price", row["buy_price"], "buy_price must be numeric.")
            valid_mask.loc[idx] = False
        elif row["buy_price"] <= 0:
            add_quality_issue(issues, "Error", row_no, "buy_price", row["buy_price"], "buy_price must be greater than 0.")
            valid_mask.loc[idx] = False

        if pd.isna(row["fee"]):
            clean.loc[idx, "fee"] = 0.0
        elif row["fee"] < 0:
            add_quality_issue(issues, "Warning", row_no, "fee", row["fee"], "fee is negative. Check if this is intentional.")

    duplicate_cols = ["ticker", "purchase_date", "shares", "buy_price", "fee", "account", "note"]
    duplicated = clean.duplicated(subset=duplicate_cols, keep=False)
    if duplicated.any():
        for _, row in clean.loc[duplicated].iterrows():
            add_quality_issue(
                issues,
                "Warning",
                row["row_id"],
                "duplicate row",
                row["ticker"],
                "Potential duplicate transaction row.",
            )

    # If required columns are missing, no row can be fully trusted.
    if any(col not in original_cols for col in REQUIRED_COLUMNS):
        valid_mask[:] = False

    quality_df = pd.DataFrame(issues)
    return clean, quality_df, valid_mask


# ============================================================
# Online market data functions
# ============================================================

@dataclass
class PriceResult:
    ticker: str
    price: Optional[float]
    currency: str
    as_of: str
    error: Optional[str] = None


@st.cache_data(ttl=15 * 60, show_spinner=False)
def fetch_current_price(ticker: str) -> Dict[str, Any]:
    result = PriceResult(ticker=ticker, price=None, currency="USD", as_of=now_et_str(), error=None)
    try:
        ticker_obj = yf.Ticker(ticker)

        # Try fast_info first. Some yfinance versions expose dict-like access; others expose attributes.
        try:
            fast_info = ticker_obj.fast_info
            for key in ["last_price", "regular_market_price", "previous_close", "lastPrice"]:
                value = None
                try:
                    if hasattr(fast_info, "get"):
                        value = fast_info.get(key)
                except Exception:
                    value = None
                if value is None:
                    try:
                        value = getattr(fast_info, key)
                    except Exception:
                        value = None
                if value is not None and not pd.isna(value) and float(value) > 0:
                    result.price = float(value)
                    break

            try:
                currency = fast_info.get("currency") if hasattr(fast_info, "get") else getattr(fast_info, "currency", None)
                if currency:
                    result.currency = str(currency)
            except Exception:
                pass
        except Exception:
            pass

        # Fallback: latest close from short history.
        if result.price is None:
            hist = ticker_obj.history(period="5d", auto_adjust=False)
            if hist is not None and not hist.empty and "Close" in hist.columns:
                close = hist["Close"].dropna()
                if not close.empty and float(close.iloc[-1]) > 0:
                    result.price = float(close.iloc[-1])

        if result.price is None:
            result.error = "No current price returned by yfinance."
    except Exception as exc:
        result.error = f"Current price lookup failed: {exc}"

    return result.__dict__


@st.cache_data(ttl=60 * 60, show_spinner=False)
def fetch_price_history(ticker: str, period: str) -> Dict[str, Any]:
    try:
        yf_period = PERIOD_MAP.get(period, "1y")
        hist = yf.Ticker(ticker).history(period=yf_period, auto_adjust=False)
        if hist is None or hist.empty:
            return {"ticker": ticker, "history": pd.DataFrame(), "error": "No historical price data returned."}
        hist = hist.reset_index()
        date_col = "Date" if "Date" in hist.columns else hist.columns[0]
        hist = hist.rename(columns={date_col: "Date"})
        hist["Date"] = pd.to_datetime(hist["Date"], errors="coerce").dt.tz_localize(None)
        keep_cols = [c for c in ["Date", "Open", "High", "Low", "Close", "Volume", "Dividends", "Stock Splits"] if c in hist.columns]
        hist = hist[keep_cols].dropna(subset=["Date"])
        return {"ticker": ticker, "history": hist, "error": None}
    except Exception as exc:
        return {"ticker": ticker, "history": pd.DataFrame(), "error": f"Historical price lookup failed: {exc}"}


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_dividend_history(ticker: str) -> Dict[str, Any]:
    try:
        div = yf.Ticker(ticker).dividends
        if div is None or len(div) == 0:
            return {"ticker": ticker, "dividends": pd.DataFrame(columns=["Date", "Dividend"]), "error": None, "info": "No dividend history."}
        div_df = div.reset_index()
        div_df.columns = ["Date", "Dividend"]
        div_df["Date"] = pd.to_datetime(div_df["Date"], errors="coerce").dt.tz_localize(None)
        div_df["Dividend"] = pd.to_numeric(div_df["Dividend"], errors="coerce")
        div_df = div_df.dropna(subset=["Date", "Dividend"])
        return {"ticker": ticker, "dividends": div_df, "error": None, "info": None}
    except Exception as exc:
        return {"ticker": ticker, "dividends": pd.DataFrame(columns=["Date", "Dividend"]), "error": f"Dividend lookup failed: {exc}", "info": None}


def fetch_all_online_data(tickers: List[str], period: str, benchmark: str) -> Tuple[Dict[str, Dict[str, Any]], pd.DataFrame]:
    online: Dict[str, Dict[str, Any]] = {}
    quality: List[Dict[str, Any]] = []

    tickers_to_fetch = sorted(set([t for t in tickers if t]))
    if benchmark and benchmark != "None":
        tickers_to_fetch = sorted(set(tickers_to_fetch + [benchmark]))

    for ticker in tickers_to_fetch:
        price = fetch_current_price(ticker)
        history = fetch_price_history(ticker, period)
        dividends = fetch_dividend_history(ticker)
        online[ticker] = {"price": price, "history": history, "dividends": dividends}

        if price.get("error"):
            add_quality_issue(quality, "Warning", "ONLINE", ticker, ticker, price["error"])
        if history.get("error"):
            add_quality_issue(quality, "Warning", "ONLINE", ticker, ticker, history["error"])
        if dividends.get("error"):
            add_quality_issue(quality, "Warning", "ONLINE", ticker, ticker, dividends["error"])
        elif dividends.get("info"):
            add_quality_issue(quality, "Info", "ONLINE", ticker, ticker, dividends["info"])

    return online, pd.DataFrame(quality)


# ============================================================
# Dividend analysis
# ============================================================

def infer_dividend_frequency(div_df: pd.DataFrame) -> Dict[str, Any]:
    if div_df is None or div_df.empty or len(div_df) < 2:
        return {
            "frequency": "Unknown",
            "frequency_count": 0,
            "avg_interval_days": np.nan,
            "confidence_note": "Insufficient dividend history to infer frequency.",
        }

    dates = pd.to_datetime(div_df["Date"]).sort_values().dropna()
    intervals = dates.diff().dt.days.dropna()
    if intervals.empty:
        return {
            "frequency": "Unknown",
            "frequency_count": 0,
            "avg_interval_days": np.nan,
            "confidence_note": "Insufficient dividend intervals.",
        }

    recent_intervals = intervals.tail(8)
    avg_interval = float(recent_intervals.mean())

    if 20 <= avg_interval <= 40:
        frequency = "Monthly"
        count = 12
    elif 70 <= avg_interval <= 110:
        frequency = "Quarterly"
        count = 4
    elif 150 <= avg_interval <= 220:
        frequency = "Semi-Annual"
        count = 2
    elif avg_interval >= 300:
        frequency = "Annual"
        count = 1
    else:
        frequency = "Unknown"
        count = 0

    return {
        "frequency": frequency,
        "frequency_count": count,
        "avg_interval_days": avg_interval,
        "confidence_note": f"Estimated from average historical dividend interval of {avg_interval:.0f} days.",
    }


def analyze_dividend_history(div_df: pd.DataFrame) -> Dict[str, Any]:
    if div_df is None or div_df.empty:
        return {
            "last_12m_dividend_per_share": 0.0,
            "recent_dividend_per_share": 0.0,
            "frequency": "Unknown",
            "frequency_count": 0,
            "avg_interval_days": np.nan,
            "next_estimated_ex_date": None,
            "next_estimated_pay_date": None,
            "dividend_status": "No Dividend History",
            "confidence_note": "No historical dividend data found from yfinance.",
        }

    div = div_df.copy()
    div["Date"] = pd.to_datetime(div["Date"], errors="coerce")
    div["Dividend"] = pd.to_numeric(div["Dividend"], errors="coerce")
    div = div.dropna(subset=["Date", "Dividend"]).sort_values("Date")

    if div.empty:
        return {
            "last_12m_dividend_per_share": 0.0,
            "recent_dividend_per_share": 0.0,
            "frequency": "Unknown",
            "frequency_count": 0,
            "avg_interval_days": np.nan,
            "next_estimated_ex_date": None,
            "next_estimated_pay_date": None,
            "dividend_status": "No Dividend History",
            "confidence_note": "Dividend data was returned but could not be parsed.",
        }

    twelve_months_ago = pd.Timestamp(TODAY - timedelta(days=365))
    last_12m = float(div.loc[div["Date"] >= twelve_months_ago, "Dividend"].sum())
    recent = float(div["Dividend"].iloc[-1])
    freq = infer_dividend_frequency(div)
    last_date = pd.to_datetime(div["Date"].iloc[-1]).date()

    next_estimated_ex_date = None
    dividend_status = "Unknown"
    confidence_note = freq["confidence_note"]

    avg_interval = freq["avg_interval_days"]
    if freq["frequency"] != "Unknown" and not pd.isna(avg_interval):
        interval_days = max(1, int(round(float(avg_interval))))
        next_date = last_date + timedelta(days=interval_days)
        while next_date < TODAY:
            next_date = next_date + timedelta(days=interval_days)
        next_estimated_ex_date = next_date
        dividend_status = "Estimated"
        confidence_note += " Next ex-date is an estimate, not a confirmed company announcement."
    else:
        dividend_status = "Unknown"
        confidence_note += " Next dividend date is unknown."

    return {
        "last_12m_dividend_per_share": last_12m,
        "recent_dividend_per_share": recent,
        "frequency": freq["frequency"],
        "frequency_count": freq["frequency_count"],
        "avg_interval_days": freq["avg_interval_days"],
        "next_estimated_ex_date": next_estimated_ex_date,
        "next_estimated_pay_date": None,  # yfinance dividend series does not reliably provide pay dates.
        "dividend_status": dividend_status,
        "confidence_note": confidence_note,
    }


def annual_dividend_per_share(analysis: Dict[str, Any], mode: str) -> float:
    if mode == "Recent Dividend × Frequency":
        recent = analysis.get("recent_dividend_per_share", 0.0) or 0.0
        frequency_count = analysis.get("frequency_count", 0) or 0
        return float(recent) * int(frequency_count)
    # Scenario mode uses the base Last 12M value for portfolio-level KPI; scenario range appears in Dividend tab.
    return float(analysis.get("last_12m_dividend_per_share", 0.0) or 0.0)


# ============================================================
# Portfolio calculations
# ============================================================

def calculate_holdings(
    portfolio_df: pd.DataFrame,
    valid_mask: pd.Series,
    online_data: Dict[str, Dict[str, Any]],
    dividend_mode: str,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Dict[str, Any]]]:
    if portfolio_df.empty or valid_mask.empty or not valid_mask.any():
        return pd.DataFrame(), pd.DataFrame(), {}

    tx = portfolio_df.loc[valid_mask].copy()
    tx["cost_basis"] = tx["shares"] * tx["buy_price"] + tx["fee"].fillna(0.0)
    tx["current_price"] = tx["ticker"].map(lambda t: online_data.get(t, {}).get("price", {}).get("price"))
    tx["current_value"] = tx["shares"] * tx["current_price"]
    tx["unrealized_pl"] = tx["current_value"] - tx["cost_basis"]
    tx["return_pct"] = np.where(tx["cost_basis"] != 0, tx["unrealized_pl"] / tx["cost_basis"], np.nan)

    dividend_analysis: Dict[str, Dict[str, Any]] = {}
    for ticker in sorted(tx["ticker"].dropna().unique()):
        div_df = online_data.get(ticker, {}).get("dividends", {}).get("dividends", pd.DataFrame())
        dividend_analysis[ticker] = analyze_dividend_history(div_df)

    grouped = tx.groupby("ticker", as_index=False).agg(
        Shares=("shares", "sum"),
        Cost_Basis=("cost_basis", "sum"),
        Accounts=("account", lambda s: ", ".join(sorted(set([str(x) for x in s if pd.notna(x)])))),
    )
    grouped["Avg_Buy_Price"] = grouped["Cost_Basis"] / grouped["Shares"]
    grouped["Current_Price"] = grouped["ticker"].map(lambda t: online_data.get(t, {}).get("price", {}).get("price"))
    grouped["Market_Value"] = grouped["Shares"] * grouped["Current_Price"]
    grouped["Unrealized_PL"] = grouped["Market_Value"] - grouped["Cost_Basis"]
    grouped["Return_Pct"] = grouped["Unrealized_PL"] / grouped["Cost_Basis"]

    total_market_value = grouped["Market_Value"].sum(skipna=True)
    grouped["Portfolio_Weight_Pct"] = np.where(total_market_value > 0, grouped["Market_Value"] / total_market_value, np.nan)

    for col in [
        "Last_12M_Dividend_Per_Share",
        "Recent_Dividend_Per_Share",
        "Estimated_Annual_Dividend",
        "Yield_on_Cost",
        "Current_Yield",
    ]:
        grouped[col] = np.nan
    grouped["Dividend_Frequency"] = "Unknown"
    grouped["Next_Estimated_Ex_Date"] = None
    grouped["Next_Estimated_Pay_Date"] = None
    grouped["Dividend_Status"] = "Unknown"
    grouped["Dividend_Confidence_Note"] = ""

    for idx, row in grouped.iterrows():
        ticker = row["ticker"]
        analysis = dividend_analysis.get(ticker, {})
        per_share = annual_dividend_per_share(analysis, dividend_mode)
        grouped.loc[idx, "Last_12M_Dividend_Per_Share"] = analysis.get("last_12m_dividend_per_share", 0.0)
        grouped.loc[idx, "Recent_Dividend_Per_Share"] = analysis.get("recent_dividend_per_share", 0.0)
        grouped.loc[idx, "Estimated_Annual_Dividend"] = per_share * row["Shares"]
        grouped.loc[idx, "Yield_on_Cost"] = per_share / row["Avg_Buy_Price"] if row["Avg_Buy_Price"] else np.nan
        grouped.loc[idx, "Current_Yield"] = per_share / row["Current_Price"] if row["Current_Price"] and not pd.isna(row["Current_Price"]) else np.nan
        grouped.loc[idx, "Dividend_Frequency"] = analysis.get("frequency", "Unknown")
        grouped.loc[idx, "Next_Estimated_Ex_Date"] = analysis.get("next_estimated_ex_date")
        grouped.loc[idx, "Next_Estimated_Pay_Date"] = analysis.get("next_estimated_pay_date")
        grouped.loc[idx, "Dividend_Status"] = analysis.get("dividend_status", "Unknown")
        grouped.loc[idx, "Dividend_Confidence_Note"] = analysis.get("confidence_note", "")

    grouped = grouped.rename(columns={"ticker": "Ticker"})
    return tx, grouped.sort_values("Market_Value", ascending=False), dividend_analysis


def portfolio_summary(holdings: pd.DataFrame) -> Dict[str, Any]:
    if holdings is None or holdings.empty:
        return {
            "total_invested": 0.0,
            "current_value": 0.0,
            "total_pl": 0.0,
            "portfolio_return_pct": np.nan,
            "estimated_annual_dividend": 0.0,
        }
    total_invested = float(holdings["Cost_Basis"].sum(skipna=True))
    current_value = float(holdings["Market_Value"].sum(skipna=True))
    total_pl = current_value - total_invested
    portfolio_return_pct = total_pl / total_invested if total_invested else np.nan
    estimated_annual_dividend = float(holdings["Estimated_Annual_Dividend"].sum(skipna=True))
    return {
        "total_invested": total_invested,
        "current_value": current_value,
        "total_pl": total_pl,
        "portfolio_return_pct": portfolio_return_pct,
        "estimated_annual_dividend": estimated_annual_dividend,
    }


# ============================================================
# Dividend schedule builder
# ============================================================

def build_upcoming_dividends(
    holdings: pd.DataFrame,
    dividend_analysis: Dict[str, Dict[str, Any]],
    horizon_days: int = 365,
) -> pd.DataFrame:
    if holdings is None or holdings.empty:
        return pd.DataFrame()

    rows: List[Dict[str, Any]] = []
    horizon_end = TODAY + timedelta(days=horizon_days)

    for _, h in holdings.iterrows():
        ticker = h["Ticker"]
        analysis = dividend_analysis.get(ticker, {})
        status = analysis.get("dividend_status", "Unknown")
        next_ex = analysis.get("next_estimated_ex_date")
        avg_interval = analysis.get("avg_interval_days", np.nan)
        recent_div = float(analysis.get("recent_dividend_per_share", 0.0) or 0.0)
        shares = float(h.get("Shares", 0.0) or 0.0)

        if status != "Estimated" or next_ex is None or pd.isna(avg_interval) or recent_div <= 0:
            continue

        interval_days = max(1, int(round(float(avg_interval))))
        ex_date = pd.to_datetime(next_ex).date()
        while ex_date < TODAY:
            ex_date += timedelta(days=interval_days)

        while ex_date <= horizon_end:
            rows.append(
                {
                    "Ticker": ticker,
                    "Estimated Ex-Date": ex_date,
                    "Estimated Pay Date": None,
                    "Estimated Dividend / Share": recent_div,
                    "Shares": shares,
                    "Estimated Dividend Amount": recent_div * shares,
                    "Status": "Estimated",
                    "Confidence Note": analysis.get("confidence_note", "Estimated from historical pattern."),
                }
            )
            ex_date += timedelta(days=interval_days)

    if not rows:
        return pd.DataFrame(
            columns=[
                "Ticker",
                "Estimated Ex-Date",
                "Estimated Pay Date",
                "Estimated Dividend / Share",
                "Shares",
                "Estimated Dividend Amount",
                "Status",
                "Confidence Note",
            ]
        )

    out = pd.DataFrame(rows).sort_values(["Estimated Ex-Date", "Ticker"])
    return out


# ============================================================
# Chart helpers
# ============================================================

def get_history_df(online_data: Dict[str, Dict[str, Any]], ticker: str) -> pd.DataFrame:
    return online_data.get(ticker, {}).get("history", {}).get("history", pd.DataFrame()).copy()


def make_portfolio_value_trend(holdings: pd.DataFrame, online_data: Dict[str, Dict[str, Any]]) -> go.Figure:
    fig = go.Figure()
    if holdings is None or holdings.empty:
        fig.update_layout(title="Portfolio Value Trend", height=360)
        return fig

    frames = []
    for _, row in holdings.iterrows():
        ticker = row["Ticker"]
        shares = row["Shares"]
        hist = get_history_df(online_data, ticker)
        if hist.empty or "Close" not in hist.columns:
            continue
        part = hist[["Date", "Close"]].copy()
        part["Value"] = part["Close"] * shares
        part["Ticker"] = ticker
        frames.append(part[["Date", "Ticker", "Value"]])

    if not frames:
        fig.update_layout(title="Portfolio Value Trend", height=360)
        return fig

    combined = pd.concat(frames, ignore_index=True)
    trend = combined.groupby("Date", as_index=False)["Value"].sum()
    fig = px.line(trend, x="Date", y="Value", title="Portfolio Value Trend")
    fig.update_traces(hovertemplate="%{x|%Y-%m-%d}<br>Value: $%{y:,.2f}<extra></extra>")
    fig.update_layout(height=380, yaxis_title="Portfolio Value ($)", xaxis_title="Date")
    return fig


def make_allocation_chart(holdings: pd.DataFrame) -> go.Figure:
    if holdings is None or holdings.empty or holdings["Market_Value"].dropna().empty:
        fig = go.Figure()
        fig.update_layout(title="Allocation by ETF", height=360)
        return fig
    fig = px.pie(
        holdings,
        names="Ticker",
        values="Market_Value",
        title="Allocation by ETF",
        hole=0.48,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(height=380)
    return fig


def make_gainers_losers_chart(holdings: pd.DataFrame) -> go.Figure:
    if holdings is None or holdings.empty:
        fig = go.Figure()
        fig.update_layout(title="Top Gainers / Top Losers", height=360)
        return fig
    data = holdings.sort_values("Return_Pct", ascending=True).copy()
    fig = px.bar(
        data,
        x="Return_Pct",
        y="Ticker",
        orientation="h",
        title="Top Gainers / Top Losers",
        text=data["Return_Pct"].map(lambda x: fmt_pct(x)),
    )
    fig.update_layout(height=380, xaxis_tickformat=".1%", xaxis_title="Return", yaxis_title="ETF")
    fig.update_traces(hovertemplate="%{y}<br>Return: %{x:.2%}<extra></extra>")
    return fig


def make_upcoming_dividend_chart(upcoming: pd.DataFrame, days: int = 30) -> go.Figure:
    cutoff = TODAY + timedelta(days=days)
    if upcoming is None or upcoming.empty:
        fig = go.Figure()
        fig.update_layout(title=f"Upcoming Estimated Dividends in Next {days} Days", height=360)
        return fig
    data = upcoming.copy()
    data = data[pd.to_datetime(data["Estimated Ex-Date"]).dt.date <= cutoff]
    if data.empty:
        fig = go.Figure()
        fig.update_layout(title=f"Upcoming Estimated Dividends in Next {days} Days", height=360)
        return fig
    data["DateLabel"] = pd.to_datetime(data["Estimated Ex-Date"]).dt.strftime("%Y-%m-%d")
    fig = px.bar(
        data,
        x="DateLabel",
        y="Estimated Dividend Amount",
        color="Ticker",
        title=f"Upcoming Estimated Dividends in Next {days} Days",
    )
    fig.update_layout(height=380, xaxis_title="Estimated Ex-Date", yaxis_title="Estimated Dividend ($)")
    fig.update_traces(hovertemplate="%{x}<br>$%{y:,.2f}<extra></extra>")
    return fig


def make_monthly_dividend_calendar(upcoming: pd.DataFrame) -> go.Figure:
    if upcoming is None or upcoming.empty:
        fig = go.Figure()
        fig.update_layout(title="Monthly Estimated Dividend Calendar", height=360)
        return fig
    data = upcoming.copy()
    data["Month"] = pd.to_datetime(data["Estimated Ex-Date"]).dt.to_period("M").astype(str)
    monthly = data.groupby("Month", as_index=False)["Estimated Dividend Amount"].sum()
    fig = px.bar(monthly, x="Month", y="Estimated Dividend Amount", title="Monthly Estimated Dividend Calendar")
    fig.update_layout(height=380, xaxis_title="Month", yaxis_title="Estimated Dividend ($)")
    fig.update_traces(hovertemplate="%{x}<br>$%{y:,.2f}<extra></extra>")
    return fig


def make_dividend_projection_chart(holdings: pd.DataFrame) -> go.Figure:
    if holdings is None or holdings.empty:
        fig = go.Figure()
        fig.update_layout(title="Annual Dividend Projection by ETF", height=360)
        return fig
    data = holdings.sort_values("Estimated_Annual_Dividend", ascending=False)
    fig = px.bar(data, x="Ticker", y="Estimated_Annual_Dividend", title="Annual Dividend Projection by ETF")
    fig.update_layout(height=380, yaxis_title="Estimated Annual Dividend ($)")
    fig.update_traces(hovertemplate="%{x}<br>$%{y:,.2f}<extra></extra>")
    return fig


def make_yield_comparison_chart(holdings: pd.DataFrame) -> go.Figure:
    if holdings is None or holdings.empty:
        fig = go.Figure()
        fig.update_layout(title="Dividend Yield Comparison", height=360)
        return fig
    data = holdings[["Ticker", "Yield_on_Cost", "Current_Yield"]].melt(
        id_vars="Ticker", var_name="Yield Type", value_name="Yield"
    )
    data["Yield Type"] = data["Yield Type"].replace({"Yield_on_Cost": "Yield on Cost", "Current_Yield": "Current Yield"})
    fig = px.bar(data, x="Ticker", y="Yield", color="Yield Type", barmode="group", title="Dividend Yield Comparison")
    fig.update_layout(height=380, yaxis_tickformat=".2%", yaxis_title="Yield")
    return fig


def make_dividend_history_chart(online_data: Dict[str, Dict[str, Any]], tickers: List[str]) -> go.Figure:
    frames = []
    for ticker in tickers:
        div = online_data.get(ticker, {}).get("dividends", {}).get("dividends", pd.DataFrame())
        if div is None or div.empty:
            continue
        part = div.copy()
        part["Ticker"] = ticker
        frames.append(part)
    if not frames:
        fig = go.Figure()
        fig.update_layout(title="Dividend History Chart", height=360)
        return fig
    data = pd.concat(frames, ignore_index=True)
    fig = px.bar(data, x="Date", y="Dividend", color="Ticker", title="Dividend History Chart", barmode="group")
    fig.update_layout(height=420, yaxis_title="Dividend / Share ($)")
    return fig


def make_selected_price_chart(
    ticker: str,
    tx: pd.DataFrame,
    holdings: pd.DataFrame,
    online_data: Dict[str, Dict[str, Any]],
) -> go.Figure:
    hist = get_history_df(online_data, ticker)
    fig = go.Figure()
    if hist.empty or "Close" not in hist.columns:
        fig.update_layout(title=f"{ticker} Price Chart", height=470)
        return fig

    hist = hist.sort_values("Date").copy()
    hist["MA20"] = hist["Close"].rolling(20).mean()
    hist["MA60"] = hist["Close"].rolling(60).mean()

    fig.add_trace(go.Scatter(x=hist["Date"], y=hist["Close"], mode="lines", name="Close"))
    fig.add_trace(go.Scatter(x=hist["Date"], y=hist["MA20"], mode="lines", name="MA 20D"))
    fig.add_trace(go.Scatter(x=hist["Date"], y=hist["MA60"], mode="lines", name="MA 60D"))

    ticker_tx = tx[tx["ticker"] == ticker] if tx is not None and not tx.empty else pd.DataFrame()
    if not ticker_tx.empty:
        fig.add_trace(
            go.Scatter(
                x=pd.to_datetime(ticker_tx["purchase_date"]),
                y=ticker_tx["buy_price"],
                mode="markers",
                marker=dict(size=10, symbol="triangle-up"),
                name="Buy Date / Buy Price",
                hovertemplate="Buy date: %{x|%Y-%m-%d}<br>Buy price: $%{y:,.2f}<extra></extra>",
            )
        )

    holding_row = holdings[holdings["Ticker"] == ticker] if holdings is not None and not holdings.empty else pd.DataFrame()
    if not holding_row.empty:
        avg_buy_price = float(holding_row["Avg_Buy_Price"].iloc[0])
        current_price = holding_row["Current_Price"].iloc[0]
        fig.add_hline(y=avg_buy_price, line_dash="dash", annotation_text=f"Avg Buy {fmt_currency(avg_buy_price)}")
        if current_price is not None and not pd.isna(current_price):
            fig.add_hline(y=float(current_price), line_dash="dot", annotation_text=f"Current {fmt_currency(current_price)}")

    fig.update_layout(
        title=f"{ticker} Price Chart with MA 20D / 60D and Buy Markers",
        height=500,
        yaxis_title="Price ($)",
        xaxis_title="Date",
    )
    return fig


def make_normalized_performance_chart(
    tickers: List[str],
    online_data: Dict[str, Dict[str, Any]],
    benchmark: str,
) -> go.Figure:
    selected = list(tickers)
    if benchmark and benchmark != "None":
        selected.append(benchmark)
    frames = []
    for ticker in sorted(set(selected)):
        hist = get_history_df(online_data, ticker)
        if hist.empty or "Close" not in hist.columns:
            continue
        part = hist[["Date", "Close"]].dropna().sort_values("Date").copy()
        if part.empty:
            continue
        first = part["Close"].iloc[0]
        if first == 0 or pd.isna(first):
            continue
        part["Normalized"] = part["Close"] / first * 100
        part["Ticker"] = ticker
        frames.append(part)
    if not frames:
        fig = go.Figure()
        fig.update_layout(title="Normalized Performance Comparison", height=420)
        return fig
    data = pd.concat(frames, ignore_index=True)
    fig = px.line(data, x="Date", y="Normalized", color="Ticker", title="Normalized Performance Comparison")
    fig.update_layout(height=460, yaxis_title="Start = 100", xaxis_title="Date")
    return fig


def make_drawdown_chart(tickers: List[str], online_data: Dict[str, Dict[str, Any]]) -> go.Figure:
    frames = []
    for ticker in tickers:
        hist = get_history_df(online_data, ticker)
        if hist.empty or "Close" not in hist.columns:
            continue
        part = hist[["Date", "Close"]].dropna().sort_values("Date").copy()
        if part.empty:
            continue
        part["Cumulative_Max"] = part["Close"].cummax()
        part["Drawdown"] = part["Close"] / part["Cumulative_Max"] - 1
        part["Ticker"] = ticker
        frames.append(part)
    if not frames:
        fig = go.Figure()
        fig.update_layout(title="Drawdown Chart", height=420)
        return fig
    data = pd.concat(frames, ignore_index=True)
    fig = px.line(data, x="Date", y="Drawdown", color="Ticker", title="Drawdown Chart")
    fig.update_layout(height=460, yaxis_tickformat=".1%", yaxis_title="Drawdown", xaxis_title="Date")
    return fig


# ============================================================
# Styled dataframe helpers
# ============================================================

def style_holdings_df(df: pd.DataFrame):
    display = rename_holdings_for_display(df.copy())
    for col in ["Next Estimated Ex-Date", "Next Estimated Pay Date"]:
        if col in display.columns:
            display[col] = display[col].map(fmt_date)

    requested_order = [
        "Ticker",
        "Shares",
        "Avg Buy Price",
        "Current Price",
        "Cost Basis",
        "Market Value",
        "Unrealized P/L",
        "Return %",
        "Portfolio Weight %",
        "Last 12M Dividend / Share",
        "Estimated Annual Dividend",
        "Yield on Cost",
        "Current Yield",
        "Dividend Frequency",
        "Next Estimated Ex-Date",
        "Next Estimated Pay Date",
        "Dividend Status",
        "Confidence Note",
    ]
    display = display[[c for c in requested_order if c in display.columns]]

    def color_pl(val: Any) -> str:
        try:
            if pd.isna(val):
                return ""
            return "color: #16a34a; font-weight: 700;" if float(val) >= 0 else "color: #dc2626; font-weight: 700;"
        except Exception:
            return ""

    def color_status(val: Any) -> str:
        value = str(val)
        if value == "Estimated":
            return "background-color: rgba(245, 158, 11, 0.18); color: #92400e; font-weight: 700;"
        if value == "Unknown":
            return "background-color: rgba(107, 114, 128, 0.16); color: #374151; font-weight: 700;"
        if value == "No Dividend History":
            return "background-color: rgba(229, 231, 235, 0.75); color: #6b7280; font-weight: 700;"
        if value == "Confirmed":
            return "background-color: rgba(22, 163, 74, 0.15); color: #166534; font-weight: 700;"
        return ""

    styled = display.style.format(
        {
            "Shares": "{:,.4g}",
            "Avg Buy Price": "${:,.2f}",
            "Current Price": "${:,.2f}",
            "Cost Basis": "${:,.2f}",
            "Market Value": "${:,.2f}",
            "Unrealized P/L": "${:,.2f}",
            "Return %": "{:+.2%}",
            "Portfolio Weight %": "{:.2%}",
            "Last 12M Dividend / Share": "${:,.4f}",
            "Estimated Annual Dividend": "${:,.2f}",
            "Yield on Cost": "{:.2%}",
            "Current Yield": "{:.2%}",
        },
        na_rep="N/A",
    )
    for col in ["Unrealized P/L", "Return %"]:
        if col in display.columns:
            styled = styled.map(color_pl, subset=[col])
    if "Dividend Status" in display.columns:
        styled = styled.map(color_status, subset=["Dividend Status"])
    return styled

def style_quality_df(df: pd.DataFrame):
    if df is None or df.empty:
        return pd.DataFrame(columns=["Severity", "Row", "Column", "Raw Value", "Issue"])

    def color_severity(val: Any) -> str:
        value = str(val)
        if value == "Error":
            return "background-color: rgba(220, 38, 38, 0.15); color: #991b1b; font-weight: 700;"
        if value == "Warning":
            return "background-color: rgba(245, 158, 11, 0.18); color: #92400e; font-weight: 700;"
        if value == "Info":
            return "background-color: rgba(37, 99, 235, 0.13); color: #1e40af; font-weight: 700;"
        return ""

    return df.style.map(color_severity, subset=["Severity"])


def rename_holdings_for_display(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(
        columns={
            "Avg_Buy_Price": "Avg Buy Price",
            "Current_Price": "Current Price",
            "Cost_Basis": "Cost Basis",
            "Market_Value": "Market Value",
            "Unrealized_PL": "Unrealized P/L",
            "Return_Pct": "Return %",
            "Portfolio_Weight_Pct": "Portfolio Weight %",
            "Last_12M_Dividend_Per_Share": "Last 12M Dividend / Share",
            "Estimated_Annual_Dividend": "Estimated Annual Dividend",
            "Yield_on_Cost": "Yield on Cost",
            "Current_Yield": "Current Yield",
            "Dividend_Frequency": "Dividend Frequency",
            "Next_Estimated_Ex_Date": "Next Estimated Ex-Date",
            "Next_Estimated_Pay_Date": "Next Estimated Pay Date",
            "Dividend_Status": "Dividend Status",
            "Dividend_Confidence_Note": "Confidence Note",
        }
    )


# ============================================================
# UI helpers
# ============================================================

def render_kpi_card(label: str, value: str, helper: str = "", tone: str = "neutral") -> None:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value {tone}">{value}</div>
            <div class="kpi-help">{helper}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_meta(source_name: str, last_refresh: str) -> None:
    st.markdown(
        f"""
        <div class="meta-box">
            <b>Source:</b> {source_name} &nbsp; | &nbsp;
            <b>Last Online Refresh:</b> {last_refresh} &nbsp; | &nbsp;
            <b>Price Source:</b> yfinance &nbsp; | &nbsp;
            <b>Dividend Source:</b> yfinance historical dividends + estimated pattern &nbsp; | &nbsp;
            <b>Dividend Accuracy:</b> Confirmed only if explicitly available; otherwise Estimated / Unknown &nbsp; | &nbsp;
            <b>Code Version:</b> {APP_VERSION}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_version_banner() -> None:
    st.markdown(
        f"""
        <div class="version-banner">
            <div class="version-banner-title">US ETF Portfolio Dashboard</div>
            <div class="version-banner-meta">Prepared by: {CREATOR_NAME} &nbsp; | &nbsp; Code Version: {APP_VERSION}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def data_quality_counts(df: pd.DataFrame) -> Tuple[int, int, int]:
    if df is None or df.empty:
        return 0, 0, 0
    return (
        int((df["Severity"] == "Error").sum()),
        int((df["Severity"] == "Warning").sum()),
        int((df["Severity"] == "Info").sum()),
    )


# ============================================================
# Main application
# ============================================================

def initialize_session_state() -> None:
    if "last_refresh" not in st.session_state:
        st.session_state.last_refresh = now_et_str()
    if "uploaded_signature" not in st.session_state:
        st.session_state.uploaded_signature = None
    if "upload_widget_key" not in st.session_state:
        st.session_state.upload_widget_key = 0
    if "data_source_kind" not in st.session_state:
        st.session_state.data_source_kind = None
    if "source_signature" not in st.session_state:
        st.session_state.source_signature = None

    default_path = find_portfolio_csv()
    default_signature = _csv_signature(default_path) if default_path is not None else None

    should_load_default = "portfolio_df" not in st.session_state
    portfolio_file_changed = (
        st.session_state.data_source_kind == "portfolio_file"
        and default_signature is not None
        and st.session_state.source_signature != default_signature
    )

    if should_load_default or portfolio_file_changed:
        df, source_name, source_kind, source_signature = load_default_portfolio_df()
        st.session_state.portfolio_df = df
        st.session_state.source_name = source_name
        st.session_state.data_source_kind = source_kind
        st.session_state.source_signature = source_signature


def reload_portfolio_csv() -> None:
    df, source_name, source_kind, source_signature = load_default_portfolio_df()
    st.session_state.portfolio_df = df
    st.session_state.source_name = source_name
    st.session_state.data_source_kind = source_kind
    st.session_state.source_signature = source_signature
    st.session_state.uploaded_signature = None
    st.session_state.upload_widget_key += 1


def sidebar_controls() -> Dict[str, Any]:
    if st.sidebar.button("Refresh Online Data", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.session_state.last_refresh = now_et_str()
        st.rerun()

    st.sidebar.caption("Refreshes cached yfinance price, history, and dividend data.")
    st.sidebar.caption(f"Code Version: {APP_VERSION}")
    st.sidebar.divider()

    st.sidebar.header("Portfolio Input")
    uploaded = st.sidebar.file_uploader(
        "Upload portfolio CSV",
        type=["csv"],
        key=f"portfolio_file_uploader_{st.session_state.upload_widget_key}",
    )

    if uploaded is not None:
        uploaded_bytes = uploaded.getvalue()
        signature = f"{uploaded.name}-{len(uploaded_bytes)}"
        if st.session_state.uploaded_signature != signature:
            df, source = load_csv_from_upload(uploaded)
            st.session_state.portfolio_df = df
            st.session_state.source_name = source
            st.session_state.data_source_kind = "uploaded"
            st.session_state.source_signature = signature
            st.session_state.uploaded_signature = signature
            st.rerun()

    if st.sidebar.button("Reload portfolio.csv", use_container_width=True):
        reload_portfolio_csv()
        st.rerun()

    if st.sidebar.button("Use Sample CSV", use_container_width=True):
        sample_path = find_sample_csv()
        if sample_path is not None:
            try:
                st.session_state.portfolio_df = _read_csv_path(sample_path)
                st.session_state.source_name = f"{SAMPLE_CSV_NAME} ({sample_path})"
                st.session_state.data_source_kind = "sample_file"
                st.session_state.source_signature = _csv_signature(sample_path)
            except Exception:
                st.session_state.portfolio_df = load_sample_df()
                st.session_state.source_name = "embedded sample_portfolio.csv"
                st.session_state.data_source_kind = "embedded_sample"
                st.session_state.source_signature = "embedded"
        else:
            st.session_state.portfolio_df = load_sample_df()
            st.session_state.source_name = "embedded sample_portfolio.csv"
            st.session_state.data_source_kind = "embedded_sample"
            st.session_state.source_signature = "embedded"
        st.session_state.uploaded_signature = None
        st.session_state.upload_widget_key += 1
        st.rerun()

    clean_preview, _, _ = clean_and_validate_portfolio(st.session_state.portfolio_df)
    accounts = sorted(clean_preview["account"].dropna().astype(str).unique().tolist()) if not clean_preview.empty else []
    tickers = sorted(clean_preview["ticker"].dropna().astype(str).unique().tolist()) if not clean_preview.empty else []
    tickers = [t for t in tickers if t]

    st.sidebar.divider()
    st.sidebar.header("Filters")
    selected_accounts = st.sidebar.multiselect("Account filter", options=accounts, default=accounts)
    selected_tickers = st.sidebar.multiselect("Ticker filter", options=tickers, default=tickers)
    period = st.sidebar.selectbox("Period", options=list(PERIOD_MAP.keys()), index=4)
    benchmark = st.sidebar.selectbox("Benchmark", options=BENCHMARK_OPTIONS, index=0)
    dividend_mode = st.sidebar.selectbox("Dividend Calculation Mode", options=DIVIDEND_MODES, index=0)

    return {
        "selected_accounts": selected_accounts,
        "selected_tickers": selected_tickers,
        "period": period,
        "benchmark": benchmark,
        "dividend_mode": dividend_mode,
    }

def apply_filters(df: pd.DataFrame, valid_mask: pd.Series, accounts: List[str], tickers: List[str]) -> Tuple[pd.DataFrame, pd.Series]:
    if df.empty:
        return df, valid_mask
    filtered_mask = valid_mask.copy()
    if accounts:
        filtered_mask &= df["account"].astype(str).isin(accounts)
    if tickers:
        filtered_mask &= df["ticker"].astype(str).isin(tickers)
    return df, filtered_mask


def render_overview_tab(
    holdings: pd.DataFrame,
    tx: pd.DataFrame,
    online_data: Dict[str, Dict[str, Any]],
    upcoming: pd.DataFrame,
) -> None:
    render_version_banner()
    summary = portfolio_summary(holdings)
    next_30_cutoff = TODAY + timedelta(days=30)
    next_30_div = 0.0
    if upcoming is not None and not upcoming.empty:
        next_30 = upcoming[pd.to_datetime(upcoming["Estimated Ex-Date"]).dt.date <= next_30_cutoff]
        next_30_div = float(next_30["Estimated Dividend Amount"].sum()) if not next_30.empty else 0.0

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        render_kpi_card("Total Invested", fmt_currency(summary["total_invested"]), "Cost basis")
    with col2:
        render_kpi_card("Current Value", fmt_currency(summary["current_value"]), "Market value")
    with col3:
        tone = "positive" if summary["total_pl"] >= 0 else "negative"
        render_kpi_card("Unrealized P/L", fmt_currency(summary["total_pl"]), "Open gain/loss", tone)
    with col4:
        tone = "positive" if (not pd.isna(summary["portfolio_return_pct"]) and summary["portfolio_return_pct"] >= 0) else "negative"
        render_kpi_card("Portfolio Return %", fmt_pct(summary["portfolio_return_pct"]), "P/L ÷ cost basis", tone)
    with col5:
        render_kpi_card("Estimated Annual Dividend", fmt_currency(summary["estimated_annual_dividend"]), "Estimated, not guaranteed", "blue")
    with col6:
        render_kpi_card("Next 30 Days Estimated Dividend", fmt_currency(next_30_div), "Based on historical pattern", "blue")

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(make_portfolio_value_trend(holdings, online_data), use_container_width=True)
    with c2:
        st.plotly_chart(make_allocation_chart(holdings), use_container_width=True)
    c3, c4 = st.columns(2)
    with c3:
        st.plotly_chart(make_gainers_losers_chart(holdings), use_container_width=True)
    with c4:
        st.plotly_chart(make_upcoming_dividend_chart(upcoming, days=30), use_container_width=True)


def render_holdings_tab(holdings: pd.DataFrame) -> None:
    st.subheader("Holdings")
    if holdings is None or holdings.empty:
        st.info("No valid holdings to display.")
        return

    st.dataframe(style_holdings_df(holdings.copy()), use_container_width=True, hide_index=True)


def render_dividend_tab(
    holdings: pd.DataFrame,
    upcoming: pd.DataFrame,
    online_data: Dict[str, Dict[str, Any]],
    dividend_analysis: Dict[str, Dict[str, Any]],
) -> None:
    st.subheader("Dividend Analysis")
    st.markdown(
        "<div class='warning-box'><b>Dividend date policy:</b> Dates derived from historical dividend intervals are labeled <b>Estimated</b>. Pay dates are shown as <b>Unknown</b> unless a reliable source is available.</div>",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(make_monthly_dividend_calendar(upcoming), use_container_width=True)
    with c2:
        st.plotly_chart(make_dividend_projection_chart(holdings), use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        st.plotly_chart(make_yield_comparison_chart(holdings), use_container_width=True)
    with c4:
        tickers = holdings["Ticker"].tolist() if holdings is not None and not holdings.empty else []
        st.plotly_chart(make_dividend_history_chart(online_data, tickers), use_container_width=True)

    st.markdown("### Upcoming Dividend Table: Next 90 Days")
    if upcoming is None or upcoming.empty:
        st.info("No estimated upcoming dividend events. This usually means dividend history is unavailable or frequency cannot be inferred.")
    else:
        next_90 = upcoming[pd.to_datetime(upcoming["Estimated Ex-Date"]).dt.date <= TODAY + timedelta(days=90)].copy()
        if next_90.empty:
            st.info("No estimated dividend events within the next 90 days.")
        else:
            next_90["Estimated Ex-Date"] = next_90["Estimated Ex-Date"].map(fmt_date)
            next_90["Estimated Pay Date"] = next_90["Estimated Pay Date"].map(fmt_date)
            st.dataframe(
                next_90.style.format(
                    {
                        "Estimated Dividend / Share": "${:,.4f}",
                        "Shares": "{:,.4g}",
                        "Estimated Dividend Amount": "${:,.2f}",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("### Scenario Projection")
    if holdings is None or holdings.empty:
        st.info("No holdings available for scenario projection.")
    else:
        scenario = holdings[["Ticker", "Shares", "Last_12M_Dividend_Per_Share"]].copy()
        scenario["Conservative"] = scenario["Last_12M_Dividend_Per_Share"] * 0.90 * scenario["Shares"]
        scenario["Base"] = scenario["Last_12M_Dividend_Per_Share"] * scenario["Shares"]
        scenario["Optimistic"] = scenario["Last_12M_Dividend_Per_Share"] * 1.10 * scenario["Shares"]
        st.dataframe(
            scenario.style.format(
                {
                    "Shares": "{:,.4g}",
                    "Last_12M_Dividend_Per_Share": "${:,.4f}",
                    "Conservative": "${:,.2f}",
                    "Base": "${:,.2f}",
                    "Optimistic": "${:,.2f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("### Dividend Data Confidence Table")
    confidence_rows = []
    for ticker, analysis in dividend_analysis.items():
        confidence_rows.append(
            {
                "Ticker": ticker,
                "Dividend Status": analysis.get("dividend_status", "Unknown"),
                "Frequency": analysis.get("frequency", "Unknown"),
                "Last 12M Dividend / Share": analysis.get("last_12m_dividend_per_share", 0.0),
                "Recent Dividend / Share": analysis.get("recent_dividend_per_share", 0.0),
                "Next Estimated Ex-Date": fmt_date(analysis.get("next_estimated_ex_date")),
                "Next Estimated Pay Date": fmt_date(analysis.get("next_estimated_pay_date")),
                "Confidence Note": analysis.get("confidence_note", ""),
            }
        )
    confidence_df = pd.DataFrame(confidence_rows)
    if confidence_df.empty:
        st.info("No dividend confidence data available.")
    else:
        st.dataframe(
            confidence_df.style.format(
                {
                    "Last 12M Dividend / Share": "${:,.4f}",
                    "Recent Dividend / Share": "${:,.4f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )


def render_price_trend_tab(
    tx: pd.DataFrame,
    holdings: pd.DataFrame,
    online_data: Dict[str, Dict[str, Any]],
    benchmark: str,
) -> None:
    st.subheader("Price Trend")
    if holdings is None or holdings.empty:
        st.info("No valid holdings to display.")
        return

    tickers = holdings["Ticker"].tolist()
    selected = st.selectbox("Selected ETF", options=tickers, index=0)
    st.plotly_chart(make_selected_price_chart(selected, tx, holdings, online_data), use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(make_normalized_performance_chart(tickers, online_data, benchmark), use_container_width=True)
    with c2:
        st.plotly_chart(make_drawdown_chart(tickers, online_data), use_container_width=True)

    if benchmark and benchmark != "None":
        st.markdown(f"### Benchmark Comparison: {benchmark}")
        st.plotly_chart(make_normalized_performance_chart(tickers, online_data, benchmark), use_container_width=True)


def render_data_manager_tab(raw_df: pd.DataFrame, quality_df: pd.DataFrame) -> None:
    st.subheader("Data Manager")
    st.markdown(
        "Use the editor below to correct transactions or add rows. Changes are applied to the in-session dataframe and can be downloaded as CSV."
    )

    editable = normalize_columns(raw_df)
    edited = st.data_editor(
        editable,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "ticker": st.column_config.TextColumn("ticker", help="ETF ticker, converted to uppercase"),
            "purchase_date": st.column_config.TextColumn("purchase_date", help="YYYY-MM-DD"),
            "shares": st.column_config.NumberColumn("shares", min_value=0.0, step=0.0001),
            "buy_price": st.column_config.NumberColumn("buy_price", min_value=0.0, step=0.01),
            "fee": st.column_config.NumberColumn("fee", step=0.01, help="Negative fee is allowed but will be flagged as Warning."),
            "account": st.column_config.TextColumn("account"),
            "note": st.column_config.TextColumn("note"),
        },
        key="portfolio_data_editor",
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("Apply Edited Data", type="primary", use_container_width=True):
            st.session_state.portfolio_df = normalize_columns(edited)
            st.session_state.source_name = "edited in Data Manager"
            st.success("Edited data applied to the current session.")
            st.rerun()
    with c2:
        st.download_button(
            "Download Edited CSV",
            data=to_csv_bytes(normalize_columns(edited)),
            file_name=PORTFOLIO_CSV_NAME,
            mime="text/csv",
            use_container_width=True,
        )

    st.markdown("### Data Quality")
    if quality_df is None or quality_df.empty:
        st.success("No data quality issues detected.")
    else:
        st.dataframe(style_quality_df(quality_df), use_container_width=True, hide_index=True)

    st.markdown("### Normalized Current CSV")
    st.dataframe(normalize_columns(edited), use_container_width=True, hide_index=True)


def main() -> None:
    inject_css()
    initialize_session_state()

    controls = sidebar_controls()

    st.markdown(f"<div class='dashboard-title'>{APP_TITLE}</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='dashboard-subtitle'>CSV transaction ledger + online ETF price/dividend data. Dividend dates are separated into Estimated / Unknown to avoid false certainty.</div>",
        unsafe_allow_html=True,
    )
    render_meta(st.session_state.source_name, st.session_state.last_refresh)

    cleaned_df, base_quality_df, valid_mask = clean_and_validate_portfolio(st.session_state.portfolio_df)
    filtered_df, filtered_valid_mask = apply_filters(
        cleaned_df,
        valid_mask,
        controls["selected_accounts"],
        controls["selected_tickers"],
    )

    valid_tickers = sorted(filtered_df.loc[filtered_valid_mask, "ticker"].dropna().astype(str).unique().tolist())

    with st.spinner("Loading online price and dividend data..."):
        online_data, online_quality_df = fetch_all_online_data(
            valid_tickers,
            controls["period"],
            controls["benchmark"],
        )

    quality_df = pd.concat([base_quality_df, online_quality_df], ignore_index=True)
    errors, warnings, infos = data_quality_counts(quality_df)

    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Valid Transactions", int(filtered_valid_mask.sum()))
    q2.metric("Errors", errors)
    q3.metric("Warnings", warnings)
    q4.metric("Info", infos)

    if errors > 0:
        st.warning("Errors exist in the CSV. The dashboard continues with valid rows only.")
    if not valid_tickers:
        st.error("No valid tickers available after validation and filtering. Check the CSV and filters.")

    tx, holdings, dividend_analysis = calculate_holdings(
        filtered_df,
        filtered_valid_mask,
        online_data,
        controls["dividend_mode"],
    )
    upcoming = build_upcoming_dividends(holdings, dividend_analysis, horizon_days=365)

    tab_overview, tab_holdings, tab_dividend, tab_price, tab_data = st.tabs(
        ["Overview", "Holdings", "Dividend", "Price Trend", "Data Manager"]
    )

    with tab_overview:
        render_overview_tab(holdings, tx, online_data, upcoming)

    with tab_holdings:
        render_holdings_tab(holdings)

    with tab_dividend:
        render_dividend_tab(holdings, upcoming, online_data, dividend_analysis)

    with tab_price:
        render_price_trend_tab(tx, holdings, online_data, controls["benchmark"])

    with tab_data:
        render_data_manager_tab(st.session_state.portfolio_df, quality_df)

    st.caption(
        "This dashboard is for portfolio monitoring and data organization only. It is not financial advice. Verify all market and dividend data before making investment decisions."
    )


if __name__ == "__main__":
    main()
