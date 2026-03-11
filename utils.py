"""
utils.py — SHEN XIV（已全面遷移至 FMP）
資料獲取、計算與處理工具函數
"""

import streamlit as st
import pandas as pd
from typing import Optional, Tuple
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception

# ==================== 從 fmp_client 匯入 ====================
from fmp_client import (
    get_history_data_fmp,
    get_intraday_data_fmp,
    get_fundamentals_fmp,
    get_watchlist_batch_fmp
)

# ==================== Retry 裝飾器 ====================
_RETRY_CONDITION = retry_if_exception(
    lambda e: any(k in str(e).lower() for k in ["rate limit", "429", "too many", "connection"])
)

def retry_fmp(func):
    """最多重試 4 次，等待 1→3→7→15 秒"""
    return retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential_jitter(initial=1, max=15),
        retry=_RETRY_CONDITION,
        reraise=True,
    )(func)


# ==================== Session State 初始化 ====================

def init_session_state():
    """初始化 session state，建立台股代號雙向查詢表"""
    if "stock_map" not in st.session_state:
        import twstock
        st.session_state.stock_map = {
            f"{code} {info.name}": code
            for code, info in twstock.codes.items()
        }
    # 建立 reverse map（code → name）供快速查詢
    if "stock_reverse_map" not in st.session_state:
        st.session_state.stock_reverse_map = {
            code: name_key
            for name_key, code in st.session_state.stock_map.items()
        }
    # 自選股清單（預設跑馬燈標的）
    if "watchlist" not in st.session_state:
        st.session_state.watchlist = [
            ("^TWII",    "加權指數"),
            ("NVDA",     "NVDA"),
            ("TSM",      "TSM(ADR)"),
            ("AAPL",     "AAPL"),
            ("^GSPC",    "S&P500"),
            ("BTC-USD",  "BTC"),
            ("^IXIC",    "NASDAQ"),
            ("^SOX",     "PHLX半導"),
            ("DX-Y.NYB", "DXY"),
            ("GC=F",     "黃金"),
        ]


def find_stock_name_by_code(target_code: str) -> str:
    """O(1) 查詢（修正原本 O(N) 遍歷）"""
    if "stock_reverse_map" not in st.session_state:
        init_session_state()
    return st.session_state.stock_reverse_map.get(target_code, f"CODE {target_code}")


# ==================== 格式化工具 ====================

def format_number(number: float, prefix: str = "") -> str:
    if number is None or number == 0:
        return "N/A"
    abs_n = abs(number)
    if abs_n >= 1e12:
        return f"{prefix}{number/1e12:.2f}T"
    elif abs_n >= 1e9:
        return f"{prefix}{number/1e9:.2f}B"
    elif abs_n >= 1e6:
        return f"{prefix}{number/1e6:.2f}M"
    else:
        return f"{prefix}{number:,.0f}"


def calculate_percentage_change(current: float, previous: float) -> Tuple[float, str]:
    if not previous or previous == 0:
        return 0.0, "-"
    change    = ((current - previous) / previous) * 100
    direction = "▲" if change > 0 else "▼" if change < 0 else "-"
    return change, direction


# ==================== 技術指標計算 ====================

def _calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # RSI — Wilder's Smoothing（com=13 等同 alpha=1/14）
    delta    = df["Close"].diff()
    gain     = delta.where(delta > 0, 0)
    loss     = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(com=13, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(com=13, min_periods=14, adjust=False).mean()
    rs       = avg_gain / avg_loss.replace(0, float("nan"))
    df["RSI"] = (100 - (100 / (1 + rs))).fillna(50)

    # Moving Averages
    df["SMA5"]  = df["Close"].rolling(5).mean()
    df["SMA20"] = df["Close"].rolling(20).mean()

    # Bollinger Bands
    std          = df["Close"].rolling(20).std()
    df["BB_Upper"] = df["SMA20"] + std * 2
    df["BB_Lower"] = df["SMA20"] - std * 2

    # MACD（新增）
    ema12        = df["Close"].ewm(span=12, adjust=False).mean()
    ema26        = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"]   = ema12 - ema26
    df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()

    return df


# ==================== 公開資料獲取函數（已全面使用 FMP） ====================

@st.cache_data(ttl=300)
def get_history_data(
    ticker: str,
    period: str = "6mo",
    interval: str = "1d",
    include_indicators: bool = True,
) -> Optional[pd.DataFrame]:
    """歷史K線（呼叫 FMP）"""
    try:
        df = get_history_data_fmp(ticker, period, interval)
        if df is None or df.empty:
            return None

        if pd.api.types.is_datetime64_any_dtype(df["Date"]):
            df["Date"] = df["Date"].dt.tz_localize(None)

        if include_indicators and len(df) > 26:
            df = _calculate_indicators(df)

        return df
    except Exception as e:
        st.error(f"Data Fetch Error ({ticker}): {e}")
        return None


@st.cache_data(ttl=60)
def get_intraday_data(ticker: str) -> pd.DataFrame:
    """盤中走勢（呼叫 FMP）"""
    try:
        return get_intraday_data_fmp(ticker)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=600)
def get_fundamentals(ticker: str) -> dict:
    """基本面（呼叫 FMP）"""
    try:
        return get_fundamentals_fmp(ticker)
    except Exception:
        return {}


@st.cache_data(ttl=300)
def get_watchlist_batch(tickers: tuple) -> dict:
    """批次下載跑馬燈標的（呼叫 FMP）"""
    try:
        return get_watchlist_batch_fmp(tickers)
    except Exception as e:
        print(f"Batch download error: {e}")
        return {}


# ==================== 績效比較 ====================

def calculate_returns(
    df_main: pd.DataFrame, df_bench: pd.DataFrame
) -> Optional[pd.DataFrame]:
    try:
        df_merge = pd.merge(
            df_main[["Date", "Close"]],
            df_bench[["Date", "Close"]],
            on="Date",
            suffixes=("_Main", "_Bench"),
            how="inner",
        )
        if df_merge.empty:
            return None

        base_main  = df_merge["Close_Main"].iloc[0]
        base_bench = df_merge["Close_Bench"].iloc[0]
        if base_main == 0 or base_bench == 0:
            return None

        df_merge["Return_Main"]  = (df_merge["Close_Main"]  / base_main  - 1) * 100
        df_merge["Return_Bench"] = (df_merge["Close_Bench"] / base_bench - 1) * 100
        return df_merge
    except Exception as e:
        st.error(f"計算回報率時發生錯誤: {e}")
        return None