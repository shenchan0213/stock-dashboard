"""
utils.py
負責資料獲取、計算與處理的工具函數
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import twstock
import pytz
from typing import Optional, Tuple

# --- Session State 初始化 ---
def init_session_state():
    if "stock_map" not in st.session_state:
        st.session_state.stock_map = {
            f"{code} {info.name}": code for code, info in twstock.codes.items()
        }

def find_stock_name_by_code(target_code: str) -> str:
    # 如果 session state 還沒初始化，先初始化
    if "stock_map" not in st.session_state:
        init_session_state()
        
    for name_key, code_val in st.session_state.stock_map.items():
        if code_val == target_code:
            return name_key
    return f"CODE {target_code}"

# --- 格式化工具 ---
def format_number(number: float, prefix: str = "") -> str:
    if number >= 1e12:
        return f"{prefix}{number/1e12:.2f}T"
    elif number >= 1e9:
        return f"{prefix}{number/1e9:.2f}B"
    elif number >= 1e6:
        return f"{prefix}{number/1e6:.2f}M"
    else:
        return f"{prefix}{number:,.0f}"

def calculate_percentage_change(current: float, previous: float) -> Tuple[float, str]:
    if previous == 0:
        return 0.0, ""
    change = ((current - previous) / previous) * 100
    direction = "▲" if change > 0 else "▼" if change < 0 else "-"
    return change, direction

# --- 技術指標計算 ---
def _calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    # RSI
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))
    
    # MA
    df["SMA5"] = df["Close"].rolling(5).mean()
    df["SMA20"] = df["Close"].rolling(20).mean()
    
    # Bollinger Bands
    std = df["Close"].rolling(20).std()
    df["BB_Upper"] = df["SMA20"] + (std * 2)
    df["BB_Lower"] = df["SMA20"] - (std * 2)
    return df

# --- 資料獲取函數 ---
@st.cache_data(ttl=300)
def get_history_data(ticker: str, period: str = "6mo", interval: str = "1d") -> Optional[pd.DataFrame]:
    try:
        df = yf.Ticker(ticker).history(period=period, interval=interval)
        if df.empty: return None
        
        df.reset_index(inplace=True)
        if "Datetime" in df.columns: df.rename(columns={"Datetime": "Date"}, inplace=True)
        
        # 移除時區
        if pd.api.types.is_datetime64_any_dtype(df["Date"]):
            df["Date"] = df["Date"].dt.tz_localize(None)

        if len(df) > 20:
            df = _calculate_indicators(df)
            
        return df
    except:
        return None

@st.cache_data(ttl=60)
def get_fundamentals(ticker: str) -> dict:
    try:
        stock = yf.Ticker(ticker)
        return stock.info
    except:
        return {}

def get_intraday_data(ticker: str) -> pd.DataFrame:
    try:
        df = yf.Ticker(ticker).history(period="1d", interval="1m")
        if df.empty:
            df = yf.Ticker(ticker).history(period="5d", interval="1m")
            if not df.empty:
                last_date = df.index.max().date()
                df = df[df.index.date == last_date]
        return df
    except:
        return pd.DataFrame()

def calculate_returns(df_main: pd.DataFrame, df_bench: pd.DataFrame) -> Optional[pd.DataFrame]:
    try:
        df_merge = pd.merge(
            df_main[["Date", "Close"]],
            df_bench[["Date", "Close"]],
            on="Date",
            suffixes=("_Main", "_Bench"),
            how="inner",
        )
        if df_merge.empty: return None
        
        base_main = df_merge["Close_Main"].iloc[0]
        base_bench = df_merge["Close_Bench"].iloc[0]
        
        df_merge["Return_Main"] = (df_merge["Close_Main"] / base_main - 1) * 100
        df_merge["Return_Bench"] = (df_merge["Close_Bench"] / base_bench - 1) * 100
        
        return df_merge
    except Exception as e:
        st.error(f"計算回報率時發生錯誤: {e}")
        return None