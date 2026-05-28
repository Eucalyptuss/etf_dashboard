from __future__ import annotations

import io
import math
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

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
APP_VERSION = "v1.4.1"
BASE_DIR = Path(__file__).resolve().parent
PORTFOLIO_CSV_NAME = "portfolio.csv"
SAMPLE_CSV_NAME = "sample_portfolio.csv"
ET = ZoneInfo("America/New_York")
TODAY = datetime.now(ET).date()

TRANSACTION_TYPES = ["BUY", "SELL"]
REQUIRED_COLUMNS = ["transaction_date", "transaction_type", "ticker", "shares", "price"]
OPTIONAL_COLUMNS_DEFAULTS = {
    "fee": 0.0,
    "account": "Default",
    "note": "",
}
CANONICAL_COLUMNS = REQUIRED_COLUMNS + list(OPTIONAL_COLUMNS_DEFAULTS.keys())
LEGACY_REQUIRED_COLUMNS = ["ticker", "purchase_date", "shares", "buy_price"]

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

SAMPLE_CSV = """transaction_date,transaction_type,ticker,shares,price,fee,account,note
2025-03-12,BUY,SCHD,20,77.35,0,Fidelity,dividend core
2026-01-10,SELL,SCHD,5,82.00,0,Fidelity,partial sell example
2025-04-10,BUY,JEPI,15,56.20,0,Fidelity,income
2025-05-02,BUY,VOO,5,474.10,0,Robinhood,index core
2025-06-03,BUY,QQQ,3,455.00,0,Robinhood,closed position example
2026-02-15,SELL,QQQ,3,475.00,0,Robinhood,full sell example
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
            --cardbg: rgba(255,255,255,0.78);
            --border: rgba(148,163,184,0.35);
        }
        .main .block-container {
            padding-top: 1.2rem;
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
            background: linear-gradient(135deg, rgba(37,99,235,0.10), rgba(248,250,252,0.82));
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
            height: 148px;
            min-height: 148px;
            box-sizing: border-box;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        .kpi-label {
            color: #64748b;
            font-size: 0.80rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 0.45rem;
            line-height: 1.2;
            min-height: 1.95rem;
        }
        .kpi-value {
            color: #0f172a;
            font-size: 1.50rem;
            line-height: 1.15;
            font-weight: 850;
            white-space: nowrap;
        }
        .kpi-help {
            color: #64748b;
            font-size: 0.76rem;
            margin-top: 0.35rem;
            line-height: 1.2;
            min-height: 1.0rem;
        }
        .positive { color: var(--green) !important; }
        .negative { color: var(--red) !important; }
        .neutral { color: #0f172a !important; }
        .blue { color: var(--blue) !important; }
        .amber { color: var(--amber) !important; }
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


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


# ============================================================
# CSV loading and normalization
# ============================================================


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


def find_csv(filename: str) -> Optional[Path]:
    candidates = [BASE_DIR / filename, Path.cwd() / filename]
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
    portfolio_path = find_csv(PORTFOLIO_CSV_NAME)
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

    sample_path = find_csv(SAMPLE_CSV_NAME)
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


def standardize_raw_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().lower() for c in out.columns]
    return out


def migrate_legacy_schema(df: pd.DataFrame) -> Tuple[pd.DataFrame, bool]:
    """Convert the old buy-only schema to the BUY/SELL transaction ledger schema.

    Old supported columns:
    ticker,purchase_date,shares,buy_price,fee,account,note
    New columns:
    transaction_date,transaction_type,ticker,shares,price,fee,account,note
    """
    out = standardize_raw_columns(df)
    migrated = False

    has_new_core = {"transaction_date", "transaction_type", "ticker", "shares", "price"}.issubset(set(out.columns))
    has_legacy_core = {"ticker", "purchase_date", "shares", "buy_price"}.issubset(set(out.columns))

    if not has_new_core and has_legacy_core:
        out = out.rename(columns={"purchase_date": "transaction_date", "buy_price": "price"})
        if "transaction_type" not in out.columns:
            out["transaction_type"] = "BUY"
        migrated = True

    # Allow partial migration if the user manually renamed only some fields.
    if "purchase_date" in out.columns and "transaction_date" not in out.columns:
        out = out.rename(columns={"purchase_date": "transaction_date"})
        migrated = True
    if "buy_price" in out.columns and "price" not in out.columns:
        out = out.rename(columns={"buy_price": "price"})
        migrated = True
    if "transaction_type" not in out.columns and {"ticker", "transaction_date", "shares", "price"}.issubset(set(out.columns)):
        out["transaction_type"] = "BUY"
        migrated = True

    for col, default_value in OPTIONAL_COLUMNS_DEFAULTS.items():
        if col not in out.columns:
            out[col] = default_value

    for col in REQUIRED_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan

    return out[CANONICAL_COLUMNS], migrated


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


def clean_and_validate_transactions(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, bool]:
    issues: List[Dict[str, Any]] = []

    if df is None or df.empty:
        add_quality_issue(issues, "Error", "ALL", "CSV", "", "CSV is empty.")
        empty = pd.DataFrame(columns=["row_id"] + CANONICAL_COLUMNS)
        return empty, pd.DataFrame(issues), pd.Series(dtype=bool), False

    original_cols = [str(c).strip().lower() for c in df.columns]
    migrated = False
    has_new_core = all(col in original_cols for col in REQUIRED_COLUMNS)
    has_legacy_core = all(col in original_cols for col in LEGACY_REQUIRED_COLUMNS)
    if not has_new_core and not has_legacy_core:
        for col in REQUIRED_COLUMNS:
            if col not in original_cols:
                add_quality_issue(issues, "Error", "ALL", col, "Missing", f"Required column '{col}' is missing.")

    clean, migrated = migrate_legacy_schema(df)
    clean.insert(0, "row_id", range(1, len(clean) + 1))

    if migrated:
        add_quality_issue(
            issues,
            "Info",
            "ALL",
            "schema",
            "legacy",
            "Legacy buy-only CSV schema was converted to transaction ledger schema. Missing transaction_type defaults to BUY.",
        )

    clean["ticker"] = clean["ticker"].astype("string").fillna("").str.strip().str.upper()
    clean["transaction_type"] = clean["transaction_type"].astype("string").fillna("").str.strip().str.upper()
    clean["account"] = clean["account"].astype("string").fillna("Default").str.strip()
    clean["account"] = clean["account"].replace("", "Default")
    clean["note"] = clean["note"].astype("string").fillna("")

    raw_dates = clean["transaction_date"].copy()
    clean["transaction_date"] = pd.to_datetime(clean["transaction_date"], errors="coerce").dt.date

    for col in ["shares", "price", "fee"]:
        clean[col] = pd.to_numeric(clean[col], errors="coerce")

    valid_mask = pd.Series(True, index=clean.index)

    for idx, row in clean.iterrows():
        row_no = row["row_id"]
        if row["ticker"] == "" or pd.isna(row["ticker"]):
            add_quality_issue(issues, "Error", row_no, "ticker", row["ticker"], "Ticker is missing.")
            valid_mask.loc[idx] = False

        if row["transaction_type"] not in TRANSACTION_TYPES:
            add_quality_issue(
                issues,
                "Error",
                row_no,
                "transaction_type",
                row["transaction_type"],
                "transaction_type must be BUY or SELL.",
            )
            valid_mask.loc[idx] = False

        if pd.isna(row["transaction_date"]):
            add_quality_issue(
                issues,
                "Error",
                row_no,
                "transaction_date",
                raw_dates.loc[idx],
                "transaction_date format is invalid. Expected YYYY-MM-DD.",
            )
            valid_mask.loc[idx] = False
        elif row["transaction_date"] > TODAY:
            add_quality_issue(
                issues,
                "Warning",
                row_no,
                "transaction_date",
                row["transaction_date"],
                "Transaction date is in the future.",
            )

        if pd.isna(row["shares"]):
            add_quality_issue(issues, "Error", row_no, "shares", row["shares"], "shares must be numeric.")
            valid_mask.loc[idx] = False
        elif row["shares"] <= 0:
            add_quality_issue(
                issues,
                "Error",
                row_no,
                "shares",
                row["shares"],
                "shares must be greater than 0. Use transaction_type=SELL for sales; do not enter negative shares.",
            )
            valid_mask.loc[idx] = False

        if pd.isna(row["price"]):
            add_quality_issue(issues, "Error", row_no, "price", row["price"], "price must be numeric.")
            valid_mask.loc[idx] = False
        elif row["price"] <= 0:
            add_quality_issue(issues, "Error", row_no, "price", row["price"], "price must be greater than 0.")
            valid_mask.loc[idx] = False

        if pd.isna(row["fee"]):
            clean.loc[idx, "fee"] = 0.0
        elif row["fee"] < 0:
            add_quality_issue(issues, "Warning", row_no, "fee", row["fee"], "fee is negative. Check if this is intentional.")

    duplicate_cols = ["transaction_date", "transaction_type", "ticker", "shares", "price", "fee", "account", "note"]
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

    # Oversell validation by account and ticker. BUY/SELL rows use positive shares.
    available: Dict[Tuple[str, str], float] = defaultdict(float)
    valid_sorted = clean.loc[valid_mask].sort_values(["account", "ticker", "transaction_date", "row_id"]).copy()
    for idx, row in valid_sorted.iterrows():
        key = (str(row["account"]), str(row["ticker"]))
        shares = safe_float(row["shares"])
        if row["transaction_type"] == "BUY":
            available[key] += shares
        elif row["transaction_type"] == "SELL":
            if shares > available[key] + 1e-9:
                add_quality_issue(
                    issues,
                    "Error",
                    row["row_id"],
                    "shares",
                    row["shares"],
                    f"SELL exceeds available shares for {key[1]} in account {key[0]}. Available before this row: {available[key]:,.6f}.",
                )
                valid_mask.loc[idx] = False
            else:
                available[key] -= shares

    quality_df = pd.DataFrame(issues)
    return clean, quality_df, valid_mask, migrated


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

    tickers_to_fetch = sorted(set([str(t).upper().strip() for t in tickers if str(t).strip()]))
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
        "next_estimated_pay_date": None,
        "dividend_status": dividend_status,
        "confidence_note": confidence_note,
    }


def annual_dividend_per_share(analysis: Dict[str, Any], mode: str) -> float:
    if mode == "Recent Dividend × Frequency":
        recent = analysis.get("recent_dividend_per_share", 0.0) or 0.0
        frequency_count = analysis.get("frequency_count", 0) or 0
        return float(recent) * int(frequency_count)
    return float(analysis.get("last_12m_dividend_per_share", 0.0) or 0.0)


# ============================================================
# FIFO transaction processing and portfolio calculations
# ============================================================


def process_fifo_transactions(transactions: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return transaction detail, realized-lot matches, and open lots using FIFO by account+ticker.

    BUY fees are included in lot cost basis.
    SELL fees are subtracted from sale proceeds.
    """
    if transactions is None or transactions.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    tx = transactions.copy().sort_values(["account", "ticker", "transaction_date", "row_id"]).reset_index(drop=True)
    lots: Dict[Tuple[str, str], Deque[Dict[str, Any]]] = defaultdict(deque)
    realized_records: List[Dict[str, Any]] = []
    tx_records: List[Dict[str, Any]] = []

    for _, row in tx.iterrows():
        account = str(row["account"])
        ticker = str(row["ticker"])
        key = (account, ticker)
        tx_type = str(row["transaction_type"])
        tx_date = row["transaction_date"]
        shares = safe_float(row["shares"])
        price = safe_float(row["price"])
        fee = safe_float(row["fee"])
        row_id = row["row_id"]

        if tx_type == "BUY":
            total_cost = shares * price + fee
            unit_cost = total_cost / shares if shares else np.nan
            lot = {
                "Source Row": row_id,
                "Ticker": ticker,
                "Account": account,
                "Buy Date": tx_date,
                "Original Shares": shares,
                "Remaining Shares": shares,
                "Buy Price": price,
                "Buy Fee": fee,
                "Unit Cost": unit_cost,
                "Remaining Cost Basis": total_cost,
            }
            lots[key].append(lot)
            tx_records.append(
                {
                    "Row": row_id,
                    "Date": tx_date,
                    "Type": tx_type,
                    "Ticker": ticker,
                    "Account": account,
                    "Shares": shares,
                    "Price": price,
                    "Fee": fee,
                    "Gross Amount": shares * price,
                    "Net Cash Flow": -(shares * price + fee),
                    "Matched Cost Basis": np.nan,
                    "Realized P/L": np.nan,
                    "Status": "Open Lot Added",
                }
            )

        elif tx_type == "SELL":
            remaining_to_sell = shares
            gross_proceeds = shares * price
            net_proceeds = gross_proceeds - fee
            cost_sold = 0.0
            matched_rows: List[str] = []
            matches_for_this_sell: List[Dict[str, Any]] = []

            while remaining_to_sell > 1e-9 and lots[key]:
                lot = lots[key][0]
                qty = min(remaining_to_sell, safe_float(lot["Remaining Shares"]))
                lot_unit_cost = safe_float(lot["Unit Cost"])
                matched_cost = qty * lot_unit_cost
                cost_sold += matched_cost
                matched_rows.append(str(lot["Source Row"]))

                matches_for_this_sell.append(
                    {
                        "Sell Row": row_id,
                        "Ticker": ticker,
                        "Account": account,
                        "Buy Row": lot["Source Row"],
                        "Buy Date": lot["Buy Date"],
                        "Sell Date": tx_date,
                        "Shares Sold": qty,
                        "Buy Unit Cost": lot_unit_cost,
                        "Sell Price": price,
                        "Cost Basis Sold": matched_cost,
                    }
                )

                lot["Remaining Shares"] = safe_float(lot["Remaining Shares"]) - qty
                lot["Remaining Cost Basis"] = safe_float(lot["Remaining Shares"]) * lot_unit_cost
                remaining_to_sell -= qty

                if safe_float(lot["Remaining Shares"]) <= 1e-9:
                    lots[key].popleft()

            # Validation should prevent this branch. Keep a defensive fallback.
            if remaining_to_sell > 1e-9:
                status = "Unmatched SELL - excluded by validation expected"
            else:
                status = "Closed/Reduced FIFO Lots"

            realized_pl = net_proceeds - cost_sold
            sale_return_pct = realized_pl / cost_sold if cost_sold else np.nan

            for match in matches_for_this_sell:
                allocation_ratio = match["Shares Sold"] / shares if shares else 0.0
                allocated_gross = gross_proceeds * allocation_ratio
                allocated_fee = fee * allocation_ratio
                allocated_net = allocated_gross - allocated_fee
                match["Gross Proceeds"] = allocated_gross
                match["Allocated Sell Fee"] = allocated_fee
                match["Net Proceeds"] = allocated_net
                match["Realized P/L"] = allocated_net - match["Cost Basis Sold"]
                match["Realized Return %"] = (
                    match["Realized P/L"] / match["Cost Basis Sold"] if match["Cost Basis Sold"] else np.nan
                )
                realized_records.append(match)

            tx_records.append(
                {
                    "Row": row_id,
                    "Date": tx_date,
                    "Type": tx_type,
                    "Ticker": ticker,
                    "Account": account,
                    "Shares": shares,
                    "Price": price,
                    "Fee": fee,
                    "Gross Amount": gross_proceeds,
                    "Net Cash Flow": net_proceeds,
                    "Matched Cost Basis": cost_sold,
                    "Realized P/L": realized_pl,
                    "Status": status,
                    "Matched Buy Rows": ", ".join(matched_rows),
                    "Realized Return %": sale_return_pct,
                }
            )

    open_lot_records: List[Dict[str, Any]] = []
    for queue in lots.values():
        for lot in queue:
            if safe_float(lot["Remaining Shares"]) > 1e-9:
                open_lot_records.append(lot.copy())

    tx_detail_df = pd.DataFrame(tx_records)
    realized_df = pd.DataFrame(realized_records)
    open_lots_df = pd.DataFrame(open_lot_records)
    return tx_detail_df, realized_df, open_lots_df


def calculate_holdings(
    transactions: pd.DataFrame,
    online_data: Dict[str, Dict[str, Any]],
    dividend_mode: str,
    show_closed_positions: bool,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, Dict[str, Any]]]:
    tx_detail, realized_df, open_lots = process_fifo_transactions(transactions)

    traded_tickers = sorted(set(transactions["ticker"].dropna().astype(str))) if transactions is not None and not transactions.empty else []
    realized_by_ticker = (
        realized_df.groupby("Ticker", as_index=False)[["Realized P/L", "Cost Basis Sold", "Net Proceeds"]].sum()
        if realized_df is not None and not realized_df.empty
        else pd.DataFrame(columns=["Ticker", "Realized P/L", "Cost Basis Sold", "Net Proceeds"])
    )

    dividend_analysis: Dict[str, Dict[str, Any]] = {}
    for ticker in traded_tickers:
        div_df = online_data.get(ticker, {}).get("dividends", {}).get("dividends", pd.DataFrame())
        dividend_analysis[ticker] = analyze_dividend_history(div_df)

    active_rows: List[Dict[str, Any]] = []
    if open_lots is not None and not open_lots.empty:
        grouped = open_lots.groupby("Ticker", as_index=False).agg(
            Shares=("Remaining Shares", "sum"),
            Cost_Basis=("Remaining Cost Basis", "sum"),
            Accounts=("Account", lambda s: ", ".join(sorted(set([str(x) for x in s if pd.notna(x)])))),
            Open_Lots=("Source Row", "count"),
        )
        for _, row in grouped.iterrows():
            ticker = row["Ticker"]
            shares = safe_float(row["Shares"])
            cost_basis = safe_float(row["Cost_Basis"])
            current_price = online_data.get(ticker, {}).get("price", {}).get("price")
            market_value = shares * safe_float(current_price, np.nan) if current_price is not None else np.nan
            unrealized_pl = market_value - cost_basis if not pd.isna(market_value) else np.nan
            return_pct = unrealized_pl / cost_basis if cost_basis else np.nan
            realized_pl = 0.0
            if not realized_by_ticker.empty and ticker in realized_by_ticker["Ticker"].values:
                realized_pl = safe_float(realized_by_ticker.loc[realized_by_ticker["Ticker"] == ticker, "Realized P/L"].sum())
            div_analysis = dividend_analysis.get(ticker, {})
            annual_per_share = annual_dividend_per_share(div_analysis, dividend_mode)
            estimated_annual_dividend = annual_per_share * shares
            current_yield = annual_per_share / safe_float(current_price) if current_price and safe_float(current_price) > 0 else np.nan
            yield_on_cost = estimated_annual_dividend / cost_basis if cost_basis else np.nan

            active_rows.append(
                {
                    "Ticker": ticker,
                    "Holding Status": "Active",
                    "Shares": shares,
                    "Avg Cost / Share": cost_basis / shares if shares else np.nan,
                    "Current Price": current_price,
                    "Cost Basis": cost_basis,
                    "Market Value": market_value,
                    "Unrealized P/L": unrealized_pl,
                    "Realized P/L": realized_pl,
                    "Total P/L": safe_float(realized_pl) + safe_float(unrealized_pl),
                    "Return %": return_pct,
                    "Portfolio Weight %": np.nan,
                    "Last 12M Dividend / Share": div_analysis.get("last_12m_dividend_per_share", 0.0),
                    "Estimated Annual Dividend": estimated_annual_dividend,
                    "Yield on Cost": yield_on_cost,
                    "Current Yield": current_yield,
                    "Dividend Frequency": div_analysis.get("frequency", "Unknown"),
                    "Next Estimated Ex-Date": div_analysis.get("next_estimated_ex_date"),
                    "Next Estimated Pay Date": div_analysis.get("next_estimated_pay_date"),
                    "Dividend Status": div_analysis.get("dividend_status", "Unknown"),
                    "Confidence Note": div_analysis.get("confidence_note", ""),
                    "Accounts": row["Accounts"],
                    "Open Lots": int(row["Open_Lots"]),
                }
            )

    active_df = pd.DataFrame(active_rows)
    active_tickers = set(active_df["Ticker"].tolist()) if not active_df.empty else set()

    closed_rows: List[Dict[str, Any]] = []
    closed_tickers = [ticker for ticker in traded_tickers if ticker not in active_tickers]
    for ticker in closed_tickers:
        realized_pl = 0.0
        cost_basis_sold = 0.0
        net_proceeds = 0.0
        if not realized_by_ticker.empty and ticker in realized_by_ticker["Ticker"].values:
            r = realized_by_ticker[realized_by_ticker["Ticker"] == ticker]
            realized_pl = safe_float(r["Realized P/L"].sum())
            cost_basis_sold = safe_float(r["Cost Basis Sold"].sum())
            net_proceeds = safe_float(r["Net Proceeds"].sum())
        current_price = online_data.get(ticker, {}).get("price", {}).get("price")
        closed_rows.append(
            {
                "Ticker": ticker,
                "Holding Status": "Closed",
                "Shares": 0.0,
                "Avg Cost / Share": np.nan,
                "Current Price": current_price,
                "Cost Basis": 0.0,
                "Market Value": 0.0,
                "Unrealized P/L": 0.0,
                "Realized P/L": realized_pl,
                "Total P/L": realized_pl,
                "Return %": realized_pl / cost_basis_sold if cost_basis_sold else np.nan,
                "Portfolio Weight %": 0.0,
                "Last 12M Dividend / Share": 0.0,
                "Estimated Annual Dividend": 0.0,
                "Yield on Cost": np.nan,
                "Current Yield": np.nan,
                "Dividend Frequency": "Excluded - Closed",
                "Next Estimated Ex-Date": None,
                "Next Estimated Pay Date": None,
                "Dividend Status": "Excluded - Closed",
                "Confidence Note": "Closed position. Dividend projection is excluded because current shares are zero.",
                "Accounts": ", ".join(sorted(set(transactions.loc[transactions["ticker"] == ticker, "account"].astype(str)))) if transactions is not None and not transactions.empty else "",
                "Open Lots": 0,
                "Cost Basis Sold": cost_basis_sold,
                "Net Proceeds": net_proceeds,
            }
        )

    holdings = active_df.copy()
    if show_closed_positions and closed_rows:
        holdings = pd.concat([holdings, pd.DataFrame(closed_rows)], ignore_index=True)

    if not holdings.empty:
        active_market_value = holdings.loc[holdings["Holding Status"] == "Active", "Market Value"].sum(skipna=True)
        holdings["Portfolio Weight %"] = np.where(
            (holdings["Holding Status"] == "Active") & (active_market_value != 0),
            holdings["Market Value"] / active_market_value,
            0.0,
        )
        holdings = holdings.sort_values(["Holding Status", "Ticker"]).reset_index(drop=True)

    return holdings, tx_detail, realized_df, dividend_analysis


def calculate_summary(holdings: pd.DataFrame, realized_df: pd.DataFrame) -> Dict[str, float]:
    if holdings is None or holdings.empty:
        realized_pl = safe_float(realized_df["Realized P/L"].sum()) if realized_df is not None and not realized_df.empty else 0.0
        cost_sold = safe_float(realized_df["Cost Basis Sold"].sum()) if realized_df is not None and not realized_df.empty else 0.0
        return {
            "current_holdings_cost": 0.0,
            "current_value": 0.0,
            "unrealized_pl": 0.0,
            "realized_pl": realized_pl,
            "total_pl": realized_pl,
            "total_return_pct": realized_pl / cost_sold if cost_sold else np.nan,
            "estimated_annual_dividend": 0.0,
            "tracked_cost_basis": cost_sold,
        }

    active = holdings[holdings["Holding Status"] == "Active"].copy()
    current_holdings_cost = safe_float(active["Cost Basis"].sum()) if not active.empty else 0.0
    current_value = safe_float(active["Market Value"].sum()) if not active.empty else 0.0
    unrealized_pl = safe_float(active["Unrealized P/L"].sum()) if not active.empty else 0.0
    estimated_annual_dividend = safe_float(active["Estimated Annual Dividend"].sum()) if not active.empty else 0.0
    realized_pl = safe_float(realized_df["Realized P/L"].sum()) if realized_df is not None and not realized_df.empty else 0.0
    cost_sold = safe_float(realized_df["Cost Basis Sold"].sum()) if realized_df is not None and not realized_df.empty else 0.0
    total_pl = realized_pl + unrealized_pl
    tracked_cost_basis = current_holdings_cost + cost_sold
    total_return_pct = total_pl / tracked_cost_basis if tracked_cost_basis else np.nan
    return {
        "current_holdings_cost": current_holdings_cost,
        "current_value": current_value,
        "unrealized_pl": unrealized_pl,
        "realized_pl": realized_pl,
        "total_pl": total_pl,
        "total_return_pct": total_return_pct,
        "estimated_annual_dividend": estimated_annual_dividend,
        "tracked_cost_basis": tracked_cost_basis,
    }


def build_upcoming_dividends(holdings: pd.DataFrame, dividend_analysis: Dict[str, Dict[str, Any]], days: int = 90) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    if holdings is None or holdings.empty:
        return pd.DataFrame()

    active = holdings[holdings["Holding Status"] == "Active"].copy()
    cutoff = TODAY + timedelta(days=days)

    for _, row in active.iterrows():
        ticker = row["Ticker"]
        analysis = dividend_analysis.get(ticker, {})
        next_ex_date = analysis.get("next_estimated_ex_date")
        if next_ex_date is None or pd.isna(next_ex_date):
            continue
        avg_interval = analysis.get("avg_interval_days")
        if pd.isna(avg_interval) or safe_float(avg_interval) <= 0:
            interval_days = None
        else:
            interval_days = max(1, int(round(float(avg_interval))))
        div_per_share = safe_float(analysis.get("recent_dividend_per_share", 0.0))
        shares = safe_float(row["Shares"])
        ex_date = pd.to_datetime(next_ex_date).date()
        while ex_date <= cutoff:
            rows.append(
                {
                    "Ticker": ticker,
                    "Estimated Ex-Date": ex_date,
                    "Estimated Pay Date": None,
                    "Estimated Dividend / Share": div_per_share,
                    "Shares": shares,
                    "Estimated Dividend Amount": div_per_share * shares,
                    "Status": analysis.get("dividend_status", "Unknown"),
                    "Confidence Note": analysis.get("confidence_note", ""),
                }
            )
            if not interval_days:
                break
            ex_date = ex_date + timedelta(days=interval_days)

    if not rows:
        return pd.DataFrame(columns=["Ticker", "Estimated Ex-Date", "Estimated Pay Date", "Estimated Dividend / Share", "Shares", "Estimated Dividend Amount", "Status", "Confidence Note"])
    return pd.DataFrame(rows).sort_values(["Estimated Ex-Date", "Ticker"]).reset_index(drop=True)


# ============================================================
# Plotly charts
# ============================================================


def get_history_df(online_data: Dict[str, Dict[str, Any]], ticker: str) -> pd.DataFrame:
    return online_data.get(ticker, {}).get("history", {}).get("history", pd.DataFrame()).copy()


def make_portfolio_value_trend(holdings: pd.DataFrame, online_data: Dict[str, Dict[str, Any]]) -> go.Figure:
    fig = go.Figure()
    active = holdings[holdings["Holding Status"] == "Active"].copy() if holdings is not None and not holdings.empty else pd.DataFrame()
    if active.empty:
        fig.update_layout(title="Portfolio Value Trend - Active Holdings", height=360)
        return fig

    frames = []
    for _, row in active.iterrows():
        ticker = row["Ticker"]
        shares = safe_float(row["Shares"])
        hist = get_history_df(online_data, ticker)
        if hist.empty or "Close" not in hist.columns:
            continue
        part = hist[["Date", "Close"]].copy()
        part["Value"] = part["Close"] * shares
        part["Ticker"] = ticker
        frames.append(part[["Date", "Ticker", "Value"]])

    if not frames:
        fig.update_layout(title="Portfolio Value Trend - Active Holdings", height=360)
        return fig

    combined = pd.concat(frames, ignore_index=True)
    trend = combined.groupby("Date", as_index=False)["Value"].sum()
    fig = px.line(trend, x="Date", y="Value", title="Portfolio Value Trend - Active Holdings")
    fig.update_traces(hovertemplate="%{x|%Y-%m-%d}<br>Value: $%{y:,.2f}<extra></extra>")
    fig.update_layout(height=380, yaxis_title="Portfolio Value ($)", xaxis_title="Date")
    return fig


def make_allocation_chart(holdings: pd.DataFrame) -> go.Figure:
    active = holdings[holdings["Holding Status"] == "Active"].copy() if holdings is not None and not holdings.empty else pd.DataFrame()
    if active.empty or active["Market Value"].dropna().empty:
        fig = go.Figure()
        fig.update_layout(title="Allocation by Active ETF", height=360)
        return fig
    fig = px.pie(active, names="Ticker", values="Market Value", title="Allocation by Active ETF", hole=0.48)
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(height=380)
    return fig


def make_gainers_losers_chart(holdings: pd.DataFrame) -> go.Figure:
    active = holdings[holdings["Holding Status"] == "Active"].copy() if holdings is not None and not holdings.empty else pd.DataFrame()
    if active.empty:
        fig = go.Figure()
        fig.update_layout(title="Top Gainers / Top Losers - Active Holdings", height=360)
        return fig
    data = active.sort_values("Return %", ascending=True).copy()
    fig = px.bar(
        data,
        x="Return %",
        y="Ticker",
        orientation="h",
        title="Top Gainers / Top Losers - Active Holdings",
        text=data["Return %"].map(lambda x: fmt_pct(x)),
    )
    fig.update_layout(height=380, xaxis_tickformat=".1%", xaxis_title="Unrealized Return", yaxis_title="ETF")
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
    fig = px.bar(data, x="DateLabel", y="Estimated Dividend Amount", color="Ticker", title=f"Upcoming Estimated Dividends in Next {days} Days")
    fig.update_layout(height=380, xaxis_title="Estimated Ex-Date", yaxis_title="Estimated Dividend ($)")
    fig.update_traces(hovertemplate="%{x}<br>$%{y:,.2f}<extra></extra>")
    return fig


def make_realized_pl_chart(realized_df: pd.DataFrame) -> go.Figure:
    if realized_df is None or realized_df.empty:
        fig = go.Figure()
        fig.update_layout(title="Realized P/L by ETF", height=360)
        return fig
    data = realized_df.groupby("Ticker", as_index=False)["Realized P/L"].sum().sort_values("Realized P/L")
    fig = px.bar(data, x="Realized P/L", y="Ticker", orientation="h", title="Realized P/L by ETF")
    fig.update_layout(height=380, xaxis_title="Realized P/L ($)", yaxis_title="ETF")
    fig.update_traces(hovertemplate="%{y}<br>Realized P/L: $%{x:,.2f}<extra></extra>")
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
    active = holdings[holdings["Holding Status"] == "Active"].copy() if holdings is not None and not holdings.empty else pd.DataFrame()
    if active.empty:
        fig = go.Figure()
        fig.update_layout(title="Annual Dividend Projection by Active ETF", height=360)
        return fig
    data = active.sort_values("Estimated Annual Dividend", ascending=False)
    fig = px.bar(data, x="Ticker", y="Estimated Annual Dividend", title="Annual Dividend Projection by Active ETF")
    fig.update_layout(height=380, yaxis_title="Estimated Annual Dividend ($)")
    fig.update_traces(hovertemplate="%{x}<br>$%{y:,.2f}<extra></extra>")
    return fig


def make_yield_comparison_chart(holdings: pd.DataFrame) -> go.Figure:
    active = holdings[holdings["Holding Status"] == "Active"].copy() if holdings is not None and not holdings.empty else pd.DataFrame()
    if active.empty:
        fig = go.Figure()
        fig.update_layout(title="Dividend Yield Comparison", height=360)
        return fig
    data = active[["Ticker", "Yield on Cost", "Current Yield"]].melt(id_vars="Ticker", var_name="Yield Type", value_name="Yield")
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


def make_selected_price_chart(ticker: str, tx: pd.DataFrame, holdings: pd.DataFrame, online_data: Dict[str, Dict[str, Any]]) -> go.Figure:
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

    ticker_tx = tx[tx["ticker"] == ticker].copy() if tx is not None and not tx.empty else pd.DataFrame()
    if not ticker_tx.empty:
        buys = ticker_tx[ticker_tx["transaction_type"] == "BUY"]
        sells = ticker_tx[ticker_tx["transaction_type"] == "SELL"]
        if not buys.empty:
            fig.add_trace(
                go.Scatter(
                    x=pd.to_datetime(buys["transaction_date"]),
                    y=buys["price"],
                    mode="markers",
                    marker=dict(size=10, symbol="triangle-up"),
                    name="BUY",
                    hovertemplate="BUY: %{x|%Y-%m-%d}<br>Price: $%{y:,.2f}<extra></extra>",
                )
            )
        if not sells.empty:
            fig.add_trace(
                go.Scatter(
                    x=pd.to_datetime(sells["transaction_date"]),
                    y=sells["price"],
                    mode="markers",
                    marker=dict(size=10, symbol="triangle-down"),
                    name="SELL",
                    hovertemplate="SELL: %{x|%Y-%m-%d}<br>Price: $%{y:,.2f}<extra></extra>",
                )
            )

    holding_row = holdings[holdings["Ticker"] == ticker] if holdings is not None and not holdings.empty else pd.DataFrame()
    if not holding_row.empty and holding_row["Holding Status"].iloc[0] == "Active":
        avg_cost = float(holding_row["Avg Cost / Share"].iloc[0])
        current_price = holding_row["Current Price"].iloc[0]
        if not pd.isna(avg_cost):
            fig.add_hline(y=avg_cost, line_dash="dash", annotation_text=f"Avg Cost {fmt_currency(avg_cost)}")
        if current_price is not None and not pd.isna(current_price):
            fig.add_hline(y=float(current_price), line_dash="dot", annotation_text=f"Current {fmt_currency(current_price)}")

    fig.update_layout(title=f"{ticker} Price Chart with MA 20D / 60D and Buy/Sell Markers", height=500, yaxis_title="Price ($)", xaxis_title="Date")
    return fig


def make_normalized_performance_chart(tickers: List[str], online_data: Dict[str, Dict[str, Any]], benchmark: str) -> go.Figure:
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
        part["Cumulative Max"] = part["Close"].cummax()
        part["Drawdown"] = part["Close"] / part["Cumulative Max"] - 1
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
# Display helpers
# ============================================================


def render_kpi_card(label: str, value: str, help_text: str = "", color_class: str = "neutral") -> None:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div>
                <div class="kpi-label">{label}</div>
                <div class="kpi-value {color_class}">{value}</div>
            </div>
            <div class="kpi-help">{help_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def style_holdings_table(df: pd.DataFrame) -> Any:
    if df is None or df.empty:
        return df
    display = df.copy()
    date_cols = ["Next Estimated Ex-Date", "Next Estimated Pay Date"]
    for col in date_cols:
        if col in display.columns:
            display[col] = display[col].map(fmt_date)

    def color_pl(value: Any) -> str:
        val = safe_float(value, np.nan)
        if pd.isna(val):
            return ""
        if val > 0:
            return "color: #16a34a; font-weight: 700;"
        if val < 0:
            return "color: #dc2626; font-weight: 700;"
        return ""

    def color_status(value: Any) -> str:
        text = str(value)
        if text == "Estimated":
            return "background-color: rgba(217,119,6,0.16); color: #92400e; font-weight: 700;"
        if text in ["Unknown", "Excluded - Closed"]:
            return "background-color: rgba(107,114,128,0.15); color: #4b5563; font-weight: 700;"
        if text == "No Dividend History":
            return "background-color: rgba(229,231,235,0.65); color: #6b7280; font-weight: 700;"
        return ""

    def color_holding_status(value: Any) -> str:
        if str(value) == "Closed":
            return "background-color: rgba(107,114,128,0.12); color: #374151; font-weight: 800;"
        return "background-color: rgba(22,163,74,0.10); color: #166534; font-weight: 800;"

    currency_cols = ["Avg Cost / Share", "Current Price", "Cost Basis", "Market Value", "Unrealized P/L", "Realized P/L", "Total P/L", "Last 12M Dividend / Share", "Estimated Annual Dividend"]
    pct_cols = ["Return %", "Portfolio Weight %", "Yield on Cost", "Current Yield"]
    style = display.style
    for col in ["Unrealized P/L", "Realized P/L", "Total P/L", "Return %"]:
        if col in display.columns:
            style = style.map(color_pl, subset=[col])
    if "Dividend Status" in display.columns:
        style = style.map(color_status, subset=["Dividend Status"])
    if "Holding Status" in display.columns:
        style = style.map(color_holding_status, subset=["Holding Status"])
    formatter = {col: fmt_currency for col in currency_cols if col in display.columns}
    formatter.update({col: fmt_pct for col in pct_cols if col in display.columns})
    formatter.update({"Shares": lambda v: fmt_number(v, 4)})
    return style.format(formatter)


def render_meta(source: str, last_refresh: str, dividend_accuracy: str) -> None:
    st.markdown(
        f"""
        <div class="meta-box">
            <b>Source:</b> {source}<br>
            <b>Last Online Refresh:</b> {last_refresh}<br>
            <b>Price Source:</b> yfinance<br>
            <b>Dividend Source:</b> yfinance historical dividends + estimated pattern<br>
            <b>Dividend Accuracy:</b> {dividend_accuracy}<br>
            <b>Code Version:</b> {APP_VERSION}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_version_banner() -> None:
    st.markdown(
        f"""
        <div class="version-banner">
            <div class="version-banner-title">Prepared by: {CREATOR_NAME}</div>
            <div class="version-banner-meta">Code Version: {APP_VERSION}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# Session state and sidebar
# ============================================================


def initialize_session_state() -> None:
    if "upload_widget_key" not in st.session_state:
        st.session_state.upload_widget_key = 0
    if "last_online_refresh" not in st.session_state:
        st.session_state.last_online_refresh = now_et_str()
    if "active_upload_token" not in st.session_state:
        st.session_state.active_upload_token = None

    default_df, source, source_type, signature = load_default_portfolio_df()

    if "portfolio_df" not in st.session_state:
        st.session_state.portfolio_df = default_df
        st.session_state.portfolio_source = source
        st.session_state.portfolio_source_type = source_type
        st.session_state.portfolio_signature = signature
        return

    # Auto-reload portfolio.csv if it changed and the active source is not an uploaded CSV.
    if st.session_state.get("portfolio_source_type") != "uploaded":
        if signature and signature != st.session_state.get("portfolio_signature"):
            st.session_state.portfolio_df = default_df
            st.session_state.portfolio_source = source
            st.session_state.portfolio_source_type = source_type
            st.session_state.portfolio_signature = signature


def load_portfolio_file_into_session() -> None:
    df, source, source_type, signature = load_default_portfolio_df()
    st.session_state.portfolio_df = df
    st.session_state.portfolio_source = source
    st.session_state.portfolio_source_type = source_type
    st.session_state.portfolio_signature = signature
    st.session_state.active_upload_token = None
    st.session_state.upload_widget_key += 1


def sidebar_controls(clean_df: pd.DataFrame) -> Dict[str, Any]:
    with st.sidebar:
        st.markdown(f"**{APP_TITLE}**")
        st.caption(f"Prepared by {CREATOR_NAME} · {APP_VERSION}")

        refresh_clicked = st.button("Refresh Online Data", type="primary", use_container_width=True)
        if refresh_clicked:
            st.cache_data.clear()
            st.session_state.last_online_refresh = now_et_str()
            st.rerun()

        st.divider()
        uploaded_file = st.file_uploader(
            "Upload portfolio CSV",
            type=["csv"],
            key=f"portfolio_upload_{st.session_state.upload_widget_key}",
            help="Supports both the new BUY/SELL transaction ledger schema and the legacy buy-only schema.",
        )
        if uploaded_file is not None:
            token = f"{getattr(uploaded_file, 'name', 'uploaded')}::{getattr(uploaded_file, 'size', 'unknown')}"
            if token != st.session_state.get("active_upload_token"):
                try:
                    uploaded_file.seek(0)
                    uploaded_df = pd.read_csv(uploaded_file)
                    st.session_state.portfolio_df = uploaded_df
                    st.session_state.portfolio_source = f"uploaded CSV ({getattr(uploaded_file, 'name', 'uploaded')})"
                    st.session_state.portfolio_source_type = "uploaded"
                    st.session_state.portfolio_signature = token
                    st.session_state.active_upload_token = token
                    st.rerun()
                except Exception as exc:
                    st.error(f"Uploaded CSV could not be read: {exc}")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Reload portfolio.csv", use_container_width=True):
                load_portfolio_file_into_session()
                st.rerun()
        with c2:
            if st.button("Use sample", use_container_width=True):
                st.session_state.portfolio_df = load_sample_df()
                st.session_state.portfolio_source = "embedded sample_portfolio.csv"
                st.session_state.portfolio_source_type = "sample"
                st.session_state.portfolio_signature = "embedded"
                st.session_state.active_upload_token = None
                st.session_state.upload_widget_key += 1
                st.rerun()

        st.divider()
        show_closed = st.checkbox("Show Closed Positions", value=False, help="Closed positions have zero current shares but keep realized P/L in performance metrics.")

        account_options = sorted(clean_df["account"].dropna().astype(str).unique().tolist()) if clean_df is not None and not clean_df.empty and "account" in clean_df.columns else []
        ticker_options = sorted(clean_df["ticker"].dropna().astype(str).unique().tolist()) if clean_df is not None and not clean_df.empty and "ticker" in clean_df.columns else []

        selected_accounts = st.multiselect("Account Filter", account_options, default=account_options)
        selected_tickers = st.multiselect("Ticker Filter", ticker_options, default=ticker_options)
        period = st.selectbox("Price History Period", list(PERIOD_MAP.keys()), index=4)
        benchmark = st.selectbox("Benchmark", BENCHMARK_OPTIONS, index=0)
        dividend_mode = st.selectbox("Dividend Calculation Mode", DIVIDEND_MODES, index=0)

    return {
        "accounts": selected_accounts,
        "tickers": selected_tickers,
        "period": period,
        "benchmark": benchmark,
        "dividend_mode": dividend_mode,
        "show_closed": show_closed,
    }


# ============================================================
# Main app
# ============================================================


def main() -> None:
    inject_css()
    initialize_session_state()

    st.markdown(f'<div class="dashboard-title">{APP_TITLE}</div>', unsafe_allow_html=True)

    raw_df = st.session_state.get("portfolio_df", load_sample_df())
    clean_df, data_quality, valid_mask, migrated = clean_and_validate_transactions(raw_df)

    controls = sidebar_controls(clean_df)

    filtered_mask = valid_mask.copy()
    if not clean_df.empty:
        if controls["accounts"]:
            filtered_mask &= clean_df["account"].astype(str).isin(controls["accounts"])
        else:
            filtered_mask &= False
        if controls["tickers"]:
            filtered_mask &= clean_df["ticker"].astype(str).isin(controls["tickers"])
        else:
            filtered_mask &= False

    filtered_tx = clean_df.loc[filtered_mask].copy() if not clean_df.empty and not filtered_mask.empty else pd.DataFrame(columns=["row_id"] + CANONICAL_COLUMNS)
    tickers_for_fetch = sorted(filtered_tx["ticker"].dropna().astype(str).unique().tolist()) if not filtered_tx.empty else []

    with st.spinner("Loading online price and dividend data..."):
        online_data, online_quality = fetch_all_online_data(tickers_for_fetch, controls["period"], controls["benchmark"])

    if not online_quality.empty:
        data_quality = pd.concat([data_quality, online_quality], ignore_index=True) if not data_quality.empty else online_quality

    holdings, tx_detail, realized_df, dividend_analysis = calculate_holdings(
        filtered_tx,
        online_data,
        controls["dividend_mode"],
        controls["show_closed"],
    )
    summary = calculate_summary(holdings, realized_df)
    upcoming = build_upcoming_dividends(holdings, dividend_analysis, days=90)
    next_30_div = 0.0
    if upcoming is not None and not upcoming.empty:
        next_30 = upcoming[pd.to_datetime(upcoming["Estimated Ex-Date"]).dt.date <= TODAY + timedelta(days=30)]
        next_30_div = safe_float(next_30["Estimated Dividend Amount"].sum()) if not next_30.empty else 0.0

    dividend_statuses = []
    if holdings is not None and not holdings.empty:
        active = holdings[holdings["Holding Status"] == "Active"]
        dividend_statuses = active["Dividend Status"].dropna().astype(str).unique().tolist() if not active.empty else []
    dividend_accuracy = "Estimated / Unknown"
    if dividend_statuses and all(s == "No Dividend History" for s in dividend_statuses):
        dividend_accuracy = "No Dividend History"
    elif dividend_statuses and all(s == "Estimated" for s in dividend_statuses):
        dividend_accuracy = "Estimated"
    elif dividend_statuses:
        dividend_accuracy = "Estimated / Unknown / No Dividend History"

    render_meta(st.session_state.get("portfolio_source", "unknown"), st.session_state.get("last_online_refresh", now_et_str()), dividend_accuracy)

    if migrated:
        st.info("Legacy buy-only CSV columns were detected and converted to the new transaction ledger schema in memory. Download the edited CSV from Data Manager to save the new schema.")

    if data_quality is not None and not data_quality.empty and (data_quality["Severity"] == "Error").any():
        st.warning("Some transaction rows have validation errors. The dashboard uses only valid rows where possible.")

    tabs = st.tabs(["Overview", "Holdings", "Realized P/L", "Dividend", "Price Trend", "Data Manager"])

    # --------------------------------------------------------
    # Overview
    # --------------------------------------------------------
    with tabs[0]:
        render_version_banner()
        st.markdown("### Portfolio Summary")
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            render_kpi_card("Current Holdings Cost", fmt_currency(summary["current_holdings_cost"]), "Open FIFO lots only")
        with c2:
            render_kpi_card("Current Value", fmt_currency(summary["current_value"]), "Active holdings", "blue")
        with c3:
            color = "positive" if summary["unrealized_pl"] > 0 else "negative" if summary["unrealized_pl"] < 0 else "neutral"
            render_kpi_card("Unrealized P/L", fmt_currency(summary["unrealized_pl"]), "Active holdings", color)
        with c4:
            color = "positive" if summary["realized_pl"] > 0 else "negative" if summary["realized_pl"] < 0 else "neutral"
            render_kpi_card("Realized P/L", fmt_currency(summary["realized_pl"]), "Closed/reduced lots", color)
        with c5:
            color = "positive" if summary["total_pl"] > 0 else "negative" if summary["total_pl"] < 0 else "neutral"
            render_kpi_card("Total P/L", fmt_currency(summary["total_pl"]), fmt_pct(summary["total_return_pct"]), color)
        with c6:
            render_kpi_card("Est. Annual Dividend", fmt_currency(summary["estimated_annual_dividend"]), f"Next 30D: {fmt_currency(next_30_div)}", "blue")

        st.markdown(
            '<div class="small-note">Total Return % uses FIFO tracked cost basis: current open-lot cost basis plus cost basis of sold lots. It is not an IRR or tax calculation.</div>',
            unsafe_allow_html=True,
        )

        r1c1, r1c2 = st.columns(2)
        with r1c1:
            st.plotly_chart(make_portfolio_value_trend(holdings, online_data), use_container_width=True, key="overview_portfolio_value_trend")
        with r1c2:
            st.plotly_chart(make_allocation_chart(holdings), use_container_width=True, key="overview_allocation_chart")
        r2c1, r2c2 = st.columns(2)
        with r2c1:
            st.plotly_chart(make_gainers_losers_chart(holdings), use_container_width=True, key="overview_gainers_losers_chart")
        with r2c2:
            st.plotly_chart(make_realized_pl_chart(realized_df), use_container_width=True, key="overview_realized_pl_chart", theme="streamlit")
        st.plotly_chart(make_upcoming_dividend_chart(upcoming, days=30), use_container_width=True, key="overview_upcoming_dividend_30d_chart")

    # --------------------------------------------------------
    # Holdings
    # --------------------------------------------------------
    with tabs[1]:
        st.markdown("### Holdings")
        st.caption("Default view shows active holdings only. Use Sidebar → Show Closed Positions to include zero-share closed positions.")
        if holdings is None or holdings.empty:
            st.info("No holdings to display for the current filter.")
        else:
            columns_to_show = [
                "Ticker",
                "Holding Status",
                "Shares",
                "Avg Cost / Share",
                "Current Price",
                "Cost Basis",
                "Market Value",
                "Unrealized P/L",
                "Realized P/L",
                "Total P/L",
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
                "Accounts",
                "Open Lots",
            ]
            display_cols = [c for c in columns_to_show if c in holdings.columns]
            st.dataframe(style_holdings_table(holdings[display_cols]), use_container_width=True, height=520)

        st.markdown("### Open FIFO Lots")
        _, _, open_lots = process_fifo_transactions(filtered_tx)
        if open_lots is None or open_lots.empty:
            st.info("No open lots. This can happen when all selected positions are fully sold.")
        else:
            open_display = open_lots.copy()
            open_display["Buy Date"] = open_display["Buy Date"].map(fmt_date)
            st.dataframe(
                open_display[["Ticker", "Account", "Source Row", "Buy Date", "Remaining Shares", "Unit Cost", "Remaining Cost Basis", "Buy Price", "Buy Fee"]],
                use_container_width=True,
                height=360,
            )

    # --------------------------------------------------------
    # Realized P/L
    # --------------------------------------------------------
    with tabs[2]:
        st.markdown("### Realized P/L")
        st.caption("SELL transactions are matched to BUY lots using FIFO by account and ticker. Full sells that reduce shares to zero remain as Closed Positions when enabled.")
        st.plotly_chart(make_realized_pl_chart(realized_df), use_container_width=True, key="realized_tab_realized_pl_chart", theme="streamlit")
        if realized_df is None or realized_df.empty:
            st.info("No realized gains/losses found for the selected transactions.")
        else:
            realized_display = realized_df.copy()
            for col in ["Buy Date", "Sell Date"]:
                realized_display[col] = realized_display[col].map(fmt_date)
            st.dataframe(
                realized_display.style.format(
                    {
                        "Shares Sold": lambda v: fmt_number(v, 4),
                        "Buy Unit Cost": fmt_currency,
                        "Sell Price": fmt_currency,
                        "Cost Basis Sold": fmt_currency,
                        "Gross Proceeds": fmt_currency,
                        "Allocated Sell Fee": fmt_currency,
                        "Net Proceeds": fmt_currency,
                        "Realized P/L": fmt_currency,
                        "Realized Return %": fmt_pct,
                    }
                ),
                use_container_width=True,
                height=500,
            )

    # --------------------------------------------------------
    # Dividend
    # --------------------------------------------------------
    with tabs[3]:
        st.markdown("### Dividend")
        st.markdown(
            '<div class="warning-box"><b>Important:</b> Future dividend dates shown here are Estimated unless explicitly marked otherwise. Closed positions are excluded from dividend projections because current shares are zero.</div>',
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(make_monthly_dividend_calendar(upcoming), use_container_width=True, key="dividend_monthly_calendar_chart")
        with c2:
            st.plotly_chart(make_dividend_projection_chart(holdings), use_container_width=True, key="dividend_projection_by_etf_chart")
        c3, c4 = st.columns(2)
        with c3:
            st.plotly_chart(make_yield_comparison_chart(holdings), use_container_width=True, key="dividend_yield_comparison_chart")
        with c4:
            st.plotly_chart(make_dividend_history_chart(online_data, tickers_for_fetch), use_container_width=True, key="dividend_history_chart")

        st.markdown("### Upcoming Dividend Table - Next 90 Days")
        if upcoming is None or upcoming.empty:
            st.info("No upcoming estimated dividends found for active holdings.")
        else:
            display = upcoming.copy()
            display["Estimated Ex-Date"] = display["Estimated Ex-Date"].map(fmt_date)
            display["Estimated Pay Date"] = display["Estimated Pay Date"].map(fmt_date)
            st.dataframe(
                display.style.format(
                    {
                        "Estimated Dividend / Share": fmt_currency,
                        "Shares": lambda v: fmt_number(v, 4),
                        "Estimated Dividend Amount": fmt_currency,
                    }
                ),
                use_container_width=True,
                height=360,
            )

        st.markdown("### Dividend Data Confidence Table")
        if holdings is None or holdings.empty:
            st.info("No dividend confidence data to display.")
        else:
            confidence_cols = ["Ticker", "Holding Status", "Shares", "Dividend Status", "Dividend Frequency", "Next Estimated Ex-Date", "Next Estimated Pay Date", "Confidence Note"]
            display = holdings[[c for c in confidence_cols if c in holdings.columns]].copy()
            for col in ["Next Estimated Ex-Date", "Next Estimated Pay Date"]:
                if col in display.columns:
                    display[col] = display[col].map(fmt_date)
            st.dataframe(display, use_container_width=True, height=360)

        if controls["dividend_mode"] == "Scenario" and holdings is not None and not holdings.empty:
            st.markdown("### Scenario Projection")
            active = holdings[holdings["Holding Status"] == "Active"].copy()
            scenario = active[["Ticker", "Shares", "Last 12M Dividend / Share"]].copy() if not active.empty else pd.DataFrame()
            if not scenario.empty:
                scenario["Conservative"] = scenario["Last 12M Dividend / Share"] * scenario["Shares"] * 0.90
                scenario["Base"] = scenario["Last 12M Dividend / Share"] * scenario["Shares"]
                scenario["Optimistic"] = scenario["Last 12M Dividend / Share"] * scenario["Shares"] * 1.10
                st.dataframe(
                    scenario.style.format(
                        {
                            "Shares": lambda v: fmt_number(v, 4),
                            "Last 12M Dividend / Share": fmt_currency,
                            "Conservative": fmt_currency,
                            "Base": fmt_currency,
                            "Optimistic": fmt_currency,
                        }
                    ),
                    use_container_width=True,
                )

    # --------------------------------------------------------
    # Price Trend
    # --------------------------------------------------------
    with tabs[4]:
        st.markdown("### Price Trend")
        if not tickers_for_fetch:
            st.info("No tickers selected.")
        else:
            selected_ticker = st.selectbox("Selected ETF", tickers_for_fetch)
            st.plotly_chart(make_selected_price_chart(selected_ticker, filtered_tx, holdings, online_data), use_container_width=True, key=f"price_selected_chart_{selected_ticker}")
            st.plotly_chart(make_normalized_performance_chart(tickers_for_fetch, online_data, controls["benchmark"]), use_container_width=True, key="price_normalized_performance_chart")
            st.plotly_chart(make_drawdown_chart(tickers_for_fetch, online_data), use_container_width=True, key="price_drawdown_chart")

    # --------------------------------------------------------
    # Data Manager
    # --------------------------------------------------------
    with tabs[5]:
        st.markdown("### Data Manager")
        st.caption("Use BUY/SELL transaction ledger format. SELL quantity must be positive; the transaction_type identifies it as a sale.")
        st.code("transaction_date,transaction_type,ticker,shares,price,fee,account,note", language="text")

        editable_base, _, _, _ = clean_and_validate_transactions(st.session_state.portfolio_df)
        editable = editable_base[CANONICAL_COLUMNS].copy() if not editable_base.empty else pd.DataFrame(columns=CANONICAL_COLUMNS)
        edited = st.data_editor(
            editable,
            use_container_width=True,
            num_rows="dynamic",
            height=420,
            column_config={
                "transaction_date": st.column_config.DateColumn("transaction_date", format="YYYY-MM-DD"),
                "transaction_type": st.column_config.SelectboxColumn("transaction_type", options=TRANSACTION_TYPES, required=True),
                "ticker": st.column_config.TextColumn("ticker", required=True),
                "shares": st.column_config.NumberColumn("shares", min_value=0.000001, step=1.0, format="%.6f"),
                "price": st.column_config.NumberColumn("price", min_value=0.000001, step=0.01, format="%.4f"),
                "fee": st.column_config.NumberColumn("fee", step=0.01, format="%.4f"),
                "account": st.column_config.TextColumn("account"),
                "note": st.column_config.TextColumn("note"),
            },
            key="transaction_editor",
        )

        b1, b2, b3 = st.columns([1, 1, 1])
        with b1:
            if st.button("Apply Edited Data", type="primary", use_container_width=True):
                normalized, _ = migrate_legacy_schema(edited)
                normalized["ticker"] = normalized["ticker"].astype("string").fillna("").str.strip().str.upper()
                normalized["transaction_type"] = normalized["transaction_type"].astype("string").fillna("BUY").str.strip().str.upper()
                normalized["account"] = normalized["account"].astype("string").fillna("Default").replace("", "Default")
                st.session_state.portfolio_df = normalized
                st.session_state.portfolio_source = "edited in Data Manager"
                st.session_state.portfolio_source_type = "edited"
                st.session_state.portfolio_signature = f"edited::{datetime.now(ET).timestamp()}"
                st.success("Edited data applied to the current session.")
                st.rerun()
        with b2:
            st.download_button(
                "Download Edited CSV",
                data=to_csv_bytes(edited),
                file_name=PORTFOLIO_CSV_NAME,
                mime="text/csv",
                use_container_width=True,
            )
        with b3:
            if st.button("Save to local portfolio.csv", use_container_width=True):
                try:
                    save_path = BASE_DIR / PORTFOLIO_CSV_NAME
                    edited.to_csv(save_path, index=False, encoding="utf-8-sig")
                    st.success(f"Saved to {save_path}")
                    load_portfolio_file_into_session()
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not save local portfolio.csv: {exc}")

        st.markdown("### Add New Transaction")
        with st.form("add_transaction_form", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                new_date = st.date_input("Date", value=TODAY)
                new_type = st.selectbox("Type", TRANSACTION_TYPES)
            with c2:
                new_ticker = st.text_input("Ticker", value="")
                new_account = st.text_input("Account", value="Default")
            with c3:
                new_shares = st.number_input("Shares", min_value=0.000001, value=1.0, step=1.0, format="%.6f")
                new_price = st.number_input("Price", min_value=0.000001, value=1.0, step=0.01, format="%.4f")
            with c4:
                new_fee = st.number_input("Fee", value=0.0, step=0.01, format="%.4f")
                new_note = st.text_input("Note", value="")
            submitted = st.form_submit_button("Add Transaction", type="primary")
            if submitted:
                new_row = pd.DataFrame(
                    [
                        {
                            "transaction_date": new_date,
                            "transaction_type": new_type,
                            "ticker": new_ticker.strip().upper(),
                            "shares": new_shares,
                            "price": new_price,
                            "fee": new_fee,
                            "account": new_account.strip() or "Default",
                            "note": new_note,
                        }
                    ]
                )
                current, _ = migrate_legacy_schema(st.session_state.portfolio_df)
                st.session_state.portfolio_df = pd.concat([current, new_row], ignore_index=True)
                st.session_state.portfolio_source = "edited in Data Manager"
                st.session_state.portfolio_source_type = "edited"
                st.session_state.portfolio_signature = f"edited::{datetime.now(ET).timestamp()}"
                st.success("New transaction added to current session.")
                st.rerun()

        st.markdown("### Transaction Detail")
        if tx_detail is None or tx_detail.empty:
            st.info("No valid transaction details available.")
        else:
            tx_display = tx_detail.copy()
            tx_display["Date"] = tx_display["Date"].map(fmt_date)
            st.dataframe(
                tx_display.style.format(
                    {
                        "Shares": lambda v: fmt_number(v, 4),
                        "Price": fmt_currency,
                        "Fee": fmt_currency,
                        "Gross Amount": fmt_currency,
                        "Net Cash Flow": fmt_currency,
                        "Matched Cost Basis": fmt_currency,
                        "Realized P/L": fmt_currency,
                        "Realized Return %": fmt_pct,
                    }
                ),
                use_container_width=True,
                height=360,
            )

        st.markdown("### Data Quality")
        if data_quality is None or data_quality.empty:
            st.success("No data quality issues detected.")
        else:
            st.dataframe(data_quality, use_container_width=True, height=420)

        st.markdown("### Migration Notes")
        st.markdown(
            """
            - New schema: `transaction_date, transaction_type, ticker, shares, price, fee, account, note`
            - `transaction_type` must be `BUY` or `SELL`.
            - `shares` is always positive. Do not enter negative shares for a sale.
            - SELL transactions are matched to BUY lots by FIFO within the same account and ticker.
            - If a SELL reduces remaining shares to zero, the ticker becomes a Closed Position.
            - Closed Positions are hidden from Holdings by default, excluded from dividend projections, and still included in Realized P/L and Total P/L.
            """
        )


if __name__ == "__main__":
    main()
