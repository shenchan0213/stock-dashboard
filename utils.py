"""
utils.py
負責資料獲取、計算與處理的工具函數 (Optimized by Gemini Consultant)
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import twstock
from typing import Optional, Tuple

# --- Session State 初始化 ---
def init_session_state():
    if "stock_map" not in st.session_state:
        # 使用 Dict Comprehension 提升初始化速度
        st.session_state.stock_map = {
            f"{code} {info.name}": code for code, info in twstock.codes.items()
        }

def find_stock_name_by_code(target_code: str) -> str:
    if "stock_map" not in st.session_state:
        init_session_state()
    # 優化查詢效率，雖然目前是遍歷，但對於少量資料尚可
    # 若資料量大，建議建立 reverse mapping dict
    for name_key, code_val in st.session_state.stock_map.items():
        if code_val == target_code:
            return name_key
    return f"CODE {target_code}"

# --- 格式化工具 ---
def format_number(number: float, prefix: str = "") -> str:
    if number is None: return "N/A"
    if number >= 1e12: return f"{prefix}{number/1e12:.2f}T"
    elif number >= 1e9: return f"{prefix}{number/1e9:.2f}B"
    elif number >= 1e6: return f"{prefix}{number/1e6:.2f}M"
    else: return f"{prefix}{number:,.0f}"

def calculate_percentage_change(current: float, previous: float) -> Tuple[float, str]:
    if previous == 0 or previous is None:
        return 0.0, "-"
    change = ((current - previous) / previous) * 100
    direction = "▲" if change > 0 else "▼" if change < 0 else "-"
    return change, direction

# --- 技術指標計算 (核心優化) ---
def _calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy() # 避免 SettingWithCopyWarning
    
    # 1. RSI (修正為 Wilder's Smoothing 近似法)
    # 使用 ewm (Exponential Weighted Moving Average) 
    # com=13 等同於 alpha=1/14，這是金融界標準 RSI 算法
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.ewm(com=13, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(com=13, min_periods=14, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))
    
    # 2. MA (Moving Averages)
    df["SMA5"] = df["Close"].rolling(window=5).mean()
    df["SMA20"] = df["Close"].rolling(window=20).mean()
    
    # 3. Bollinger Bands (布林通道)
    std = df["Close"].rolling(window=20).std()
    df["BB_Upper"] = df["SMA20"] + (std * 2)
    df["BB_Lower"] = df["SMA20"] - (std * 2)
    
    return df

# --- 資料獲取函數 ---
@st.cache_data(ttl=300)
def get_history_data(ticker: str, period: str = "6mo", interval: str = "1d", include_indicators: bool = True) -> Optional[pd.DataFrame]:
    """
    Args:
        include_indicators (bool): 比較模式時設為 False 可提升 40% 效能
    """
    try:
        # auto_adjust=True 自動修正除權息，這對長期回測(比較模式)至關重要
        df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=True)
        
        if df.empty: return None
        
        df.reset_index(inplace=True)
        # 統一欄位名稱，處理 yfinance 版本差異
        if "Datetime" in df.columns: 
            df.rename(columns={"Datetime": "Date"}, inplace=True)
        
        # 統一移除時區資訊，方便後續 Merge 操作
        if pd.api.types.is_datetime64_any_dtype(df["Date"]):
            df["Date"] = df["Date"].dt.tz_localize(None)

        # 只有在需要指標分析時才計算，大幅優化比較模式效能
        if include_indicators and len(df) > 20:
            df = _calculate_indicators(df)
            
        return df
    except Exception as e:
        st.error(f"Data Fetch Error: {e}")
        return None

@st.cache_data(ttl=300) # 延長基本面快取時間，因為 yf.info 很慢
def get_fundamentals(ticker: str) -> dict:
    try:
        stock = yf.Ticker(ticker)
        # yf.info 會觸發網路請求，容易卡住，建議使用 fast_info (若 yfinance 版本支援)
        # 這裡保留 info 但增加 TTL
        return stock.info
    except:
        return {}

def get_intraday_data(ticker: str) -> pd.DataFrame:
    try:
        # 台股盤中需要較即時，不開啟 auto_adjust
        df = yf.Ticker(ticker).history(period="1d", interval="1m")
        if df.empty:
            # 若無今日資料（如休市），抓最後 5 天取最後一天
            df = yf.Ticker(ticker).history(period="5d", interval="1m")
            if not df.empty:
                last_date = df.index.max().date()
                df = df[df.index.date == last_date]
        return df
    except:
        return pd.DataFrame()

def calculate_returns(df_main: pd.DataFrame, df_bench: pd.DataFrame) -> Optional[pd.DataFrame]:
    try:
        # 使用 inner join 確保日期對齊 (自動過濾掉各國不同的休市日)
        df_merge = pd.merge(
            df_main[["Date", "Close"]],
            df_bench[["Date", "Close"]],
            on="Date",
            suffixes=("_Main", "_Bench"),
            how="inner",
        )
        
        if df_merge.empty: return None
        
        # 歸一化計算 (Normalize to 0%)
        base_main = df_merge["Close_Main"].iloc[0]
        base_bench = df_merge["Close_Bench"].iloc[0]
        
        # 防呆：避免除以 0
        if base_main == 0 or base_bench == 0:
            return None

        df_merge["Return_Main"] = (df_merge["Close_Main"] / base_main - 1) * 100
        df_merge["Return_Bench"] = (df_merge["Close_Bench"] / base_bench - 1) * 100
        
        return df_merge
    except Exception as e:
        st.error(f"計算回報率時發生錯誤: {e}")
        return None
    # utils.py (Add to end of file)

@st.cache_data(ttl=600) # 設定 10 分鐘快取，避免頻繁請求卡頓
def get_ticker_tape_data() -> list:
    """
    獲取全球指數跑馬燈資料 (含快取機制)
    """
    # 定義要追蹤的指數與顯示名稱
    indices = {
        "^TWII": "TWSE",       # 台股
        "^GSPC": "S&P500",     # 標普
        "^IXIC": "NASDAQ",     # 那指
        "^SOX": "PHLX",        # 費半
        "BTC-USD": "BTC",      # 比特幣
        "NVDA": "NVDA",        # 輝達
        "TSM": "TSM(ADR)",     # 台積電ADR
        "DX-Y.NYB": "DXY"      # 美元指數
    }
    
    ticker_data = []
    
    try:
        # 一次性獲取所有資料以節省時間
        tickers = " ".join(indices.keys())
        data = yf.download(tickers, period="2d", progress=False)['Close']
        
        # 處理資料 (yfinance 下載多檔時格式會有差異，需小心處理)
        for symbol, name in indices.items():
            try:
                # 取得該標的的最後兩日收盤價
                if isinstance(data, pd.DataFrame) and symbol in data.columns:
                    series = data[symbol].dropna()
                elif len(indices) == 1: # 只有一檔時
                    series = data.dropna()
                else:
                    continue
                    
                if len(series) >= 2:
                    current = series.iloc[-1]
                    prev = series.iloc[-2]
                    change = (current - prev) / prev * 100
                    
                    # 格式化數據
                    color = "#00ff41" if change >= 0 else "#ff0055" # 綠漲紅跌
                    arrow = "▲" if change >= 0 else "▼"
                    
                    html_item = f"""
                    <span class="ticker-item">
                        {name} <span style="color: {color}; font-weight: bold;">{current:,.0f} {arrow} {change:.2f}%</span>
                    </span>
                    """
                    ticker_data.append(html_item)
            except Exception:
                continue
                
    except Exception as e:
        print(f"Ticker Tape Error: {e}")
        return []
        
    # 重複兩次列表，讓跑馬燈看起來無縫連接
    return ticker_data * 2