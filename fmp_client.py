"""
fmp_client.py — FMP API 封裝（2026 穩定版）
支援 GLOBAL WATCHLIST、即時走勢、歷史K線、指數 (^TWII)
"""

import requests
import pandas as pd
import streamlit as st
from typing import Optional, List

API_KEY = st.secrets.get("FMP_API_KEY", "").strip()
BASE_URL = "https://financialmodelingprep.com/api/v3"
STABLE_URL = "https://financialmodelingprep.com/stable"

@st.cache_data(ttl=300)
def fmp_get(endpoint: str, params: dict = None) -> dict:
    """統一請求（自動加入 apikey）"""
    if not API_KEY:
        st.error("❌ FMP_API_KEY 未設定，請檢查 .streamlit/secrets.toml")
        return {}
    params = params or {}
    params["apikey"] = API_KEY
    try:
        resp = requests.get(f"{endpoint}", params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"FMP API 錯誤: {e}")
        return {}

# ==================== 1. Batch Watchlist（取代原 get_watchlist_batch） ====================
@st.cache_data(ttl=60)
def get_watchlist_batch_fmp(tickers: tuple) -> dict:
    """批次即時報價（一次請求多檔）"""
    symbols = ",".join(tickers)
    data = fmp_get(f"{BASE_URL}/quote/{symbols}")
    if not isinstance(data, list):
        return {}
    
    result = {}
    for item in data:
        sym = item.get("symbol")
        if sym:
            result[sym] = {
                "price": item.get("price"),
                "change_pct": item.get("changesPercentage"),
            }
    return result

# ==================== 2. 歷史K線與 Intraday ====================
def _fmp_to_df(records: List[dict]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    if "date" in df.columns:
        df["Date"] = pd.to_datetime(df["date"])
        df = df.rename(columns={
            "open": "Open", "high": "High", "low": "Low",
            "close": "Close", "volume": "Volume"
        })
        df = df[["Date", "Open", "High", "Low", "Close", "Volume"]]
    return df

@st.cache_data(ttl=300)
def get_history_data_fmp(ticker: str, period: str = "6mo", interval: str = "1d") -> Optional[pd.DataFrame]:
    """歷史K線（日/週/月）"""
    if ticker == "^TWII":
        endpoint = f"{BASE_URL}/historical-price-full/index/^TWII"
    elif interval == "1d":
        endpoint = f"{BASE_URL}/historical-price-full/{ticker}"
    else:
        endpoint = f"{STABLE_URL}/historical-chart/{interval}?symbol={ticker}"
    
    data = fmp_get(endpoint)
    records = data.get("historical") if isinstance(data, dict) else data
    return _fmp_to_df(records)

@st.cache_data(ttl=60)
def get_intraday_data_fmp(ticker: str) -> pd.DataFrame:
    """盤中 1 分 K"""
    endpoint = f"{STABLE_URL}/historical-chart/1min?symbol={ticker}"
    data = fmp_get(endpoint)
    return _fmp_to_df(data)

# ==================== 3. 基本面（已與 analysis.py 相容） ====================
@st.cache_data(ttl=600)
def get_fundamentals_fmp(ticker: str) -> dict:
    """即時報價 + 基本面"""
    quote = fmp_get(f"{BASE_URL}/quote/{ticker}")
    if isinstance(quote, list) and quote:
        q = quote[0]
        return {
            "currentPrice": q.get("price"),
            "previousClose": q.get("previousClose"),
            "open": q.get("open"),
            "dayHigh": q.get("dayHigh"),
            "dayLow": q.get("dayLow"),
            "volume": q.get("volume"),
            "marketCap": q.get("marketCap"),
        }
    return {}