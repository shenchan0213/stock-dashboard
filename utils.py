"""
utils.py — SHEN XIV
資料獲取、計算與處理工具函數

修正項目：
1. 裝飾器順序錯誤：cache 應在外、retry 在內（原本反了導致 retry 失效）
2. get_intraday_data 沒有快取 → 加 ttl=60
3. yf session 注入方式錯誤 → 改用正確的 yf.Ticker(session=) 方式
4. find_stock_name_by_code 每次都全部遍歷 → 改用 reverse dict
5. 移除無效的 yf.utils.get_yf_data 注入
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import twstock
from typing import Optional, Tuple
from requests import Session
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception

# ==================== Session 設定（正確注入方式）====================
_yf_session = Session()
_yf_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/133.0.0.0 Safari/537.36"
    )
})

# ==================== Retry 裝飾器 ====================
_RETRY_CONDITION = retry_if_exception(
    lambda e: any(k in str(e).lower() for k in ["rate limit", "429", "too many", "connection"])
)

def retry_yfinance(func):
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
        st.session_state.stock_map = {
            f"{code} {info.name}": code
            for code, info in twstock.codes.items()
        }
    # 建立 reverse map（code → name）供快速查詢，原本是 O(N) 遍歷
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


# ==================== 內部 fetch 函數（含 retry）====================
# 正確架構：cache 在外層，retry 在內層 fetch 函數
# 原本 @retry_yfinance 在 @st.cache_data 外面，導致 retry 根本沒機會觸發

@retry_yfinance
def _fetch_history(ticker: str, period: str, interval: str) -> Optional[pd.DataFrame]:
    """實際發出 yfinance 請求（retry 在這層）"""
    df = yf.Ticker(ticker, session=_yf_session).history(
        period=period, interval=interval, auto_adjust=True
    )
    return None if df.empty else df


@retry_yfinance
def _fetch_intraday(ticker: str) -> pd.DataFrame:
    """盤中 1 分 K（retry 在這層）"""
    df = yf.Ticker(ticker, session=_yf_session).history(
        period="1d", interval="1m"
    )
    if df.empty:
        df = yf.Ticker(ticker, session=_yf_session).history(
            period="5d", interval="1m"
        )
        if not df.empty:
            last_date = df.index.max().date()
            df = df[df.index.date == last_date]
    return df


@retry_yfinance
def _fetch_fundamentals(ticker: str) -> dict:
    return yf.Ticker(ticker, session=_yf_session).info or {}


# ==================== 公開資料獲取函數（cache 在最外層）====================

@st.cache_data(ttl=300)
def get_history_data(
    ticker: str,
    period: str = "6mo",
    interval: str = "1d",
    include_indicators: bool = True,
) -> Optional[pd.DataFrame]:
    try:
        df = _fetch_history(ticker, period, interval)
        if df is None:
            return None

        df.reset_index(inplace=True)
        if "Datetime" in df.columns:
            df.rename(columns={"Datetime": "Date"}, inplace=True)
        if pd.api.types.is_datetime64_any_dtype(df["Date"]):
            df["Date"] = df["Date"].dt.tz_localize(None)

        if include_indicators and len(df) > 26:
            df = _calculate_indicators(df)

        return df
    except Exception as e:
        st.error(f"Data Fetch Error ({ticker}): {e}")
        return None


@st.cache_data(ttl=60)      # 盤中每 60 秒更新一次
def get_intraday_data(ticker: str) -> pd.DataFrame:
    """盤中走勢（加上快取，避免每次 rerun 都重新抓）"""
    try:
        return _fetch_intraday(ticker)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=600)     # 基本面 10 分鐘更新一次
def get_fundamentals(ticker: str) -> dict:
    try:
        return _fetch_fundamentals(ticker)
    except Exception:
        return {}


@st.cache_data(ttl=300)     # 跑馬燈 5 分鐘更新一次（批次下載，速度快）
def get_watchlist_batch(tickers: tuple) -> dict:
    """
    批次下載所有跑馬燈標的（一次請求取代原本的 N 次串行請求）
    用 tuple 而非 list 作參數，因為 st.cache_data 需要 hashable 參數
    """
    try:
        symbols = " ".join(tickers)
        data = yf.download(
            symbols,
            period="1mo",       # 抓一個月，sparkline 才有足夠資料
            progress=False,
            session=_yf_session,
            auto_adjust=True,
        )["Close"]

        result = {}
        for sym in tickers:
            try:
                series = (data[sym] if isinstance(data, pd.DataFrame)
                          else data).dropna()
                if len(series) >= 2:
                    result[sym] = series.tolist()
            except Exception:
                continue
        return result
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