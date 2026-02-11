"""
config.py
SHEN XIII TACTICAL 的全域配置參數
"""

# --- 色票系統 (Tactical Theme) ---
COLORS = {
    "primary": "#00ff41",    # 駭客綠 (上漲/主色)
    "danger": "#ff0055",     # 警告紅 (下跌)
    "warning": "#ffbf00",    # 警示黃 (均線/中立)
    "info": "#00ccff",       # 資訊藍 (MA20)
    "text": "#e0e0e0",       # 主要文字
    "grid": "#333333",       # 格線
    "bg_transparent": "rgba(0,0,0,0)",
    "fill_green": "rgba(0, 255, 65, 0.05)",
    "fill_red": "rgba(255, 0, 85, 0.05)",
}

# --- CSS 樣式 ---
CUSTOM_CSS = f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;700&display=swap');
        
        html, body, [class*="css"] {{
            font-family: 'Roboto Mono', 'Consolas', monospace;
            background-color: #0e0e0e;
            color: {COLORS['text']};
        }}

        h1, h2, h3 {{
            text-transform: uppercase;
            letter-spacing: 2px;
            font-weight: 700;
            color: {COLORS['text']};
            border-left: 5px solid {COLORS['primary']};
            padding-left: 10px;
        }}

        div[data-testid="stMetricValue"] {{
            color: {COLORS['primary']} !important;
            text-shadow: 0 0 10px rgba(0, 255, 65, 0.5);
            font-family: 'Roboto Mono', monospace;
        }}
        
        div.stButton > button {{
            background-color: #1f2833;
            color: #66fcf1;
            border: 1px solid #45a29e;
            border-radius: 2px; 
            transition: all 0.3s ease;
        }}
        div.stButton > button:hover {{
            background-color: #45a29e;
            color: #0b0c10;
            box-shadow: 0 0 10px #45a29e;
        }}
        
        .stAlert {{
            background-color: #1a1a1a;
            border: 1px solid #333;
            color: #e0e0e0;
        }}
    </style>
"""

# --- 映射表 ---
FUTURES_MAP = {
    "台指期 (TX)": "WTX=F",
    "微型台指 (Mini TX)": "WTX=F",
    "小道瓊 (YM)": "YM=F",
    "那斯達克 (NQ)": "NQ=F",
    "S&P 500 (ES)": "ES=F",
    "黃金 (Gold)": "GC=F",
    "原油 (Oil)": "CL=F",
    "比特幣 (BTC)": "BTC-USD",
    "美元指數 (DX)": "DX=F",
}

BENCHMARK_MAP = {
    "台灣加權指數 (TSE)": "^TWII",
    "S&P 500 (SPX)": "^GSPC",
    "那斯達克 (IXIC)": "^IXIC",
    "費城半導體 (SOX)": "^SOX",
    "台積電 (2330)": "2330.TW",
    "元大台灣50 (0050)": "0050.TW",
}

# --- 文字標籤 ---
LABELS = {
    "app_title": " 數據面板 SHEN XIV ",
    "sidebar_header": "### ⚙️ CONTROL CENTER",
    "market_types": ["🇹🇼 台灣個股", " 全球期貨/外匯"],
    "operation_modes": ["即時走勢", "歷史K線 + RSI", "績效比較"],
    "period_options": ["3mo", "6mo", "1y", "3y", "5y"],
    "interval_options": ["日K", "週K", "月K"],
    "interval_map": {"日K": "1d", "週K": "1wk", "月K": "1mo"}
}

# --- 錯誤訊息 ---
ERROR_MESSAGES = {
    "no_data": "⚠️ NO SIGNAL: {name} (請確認代號或市場開盤狀態)",
    "order_book_empty": "ORDER BOOK DATA EMPTY (MARKET CLOSED?)",
    "twse_failed": "DATA LINK FAILED (TWSE)",
    "connection_error": "CONNECTION ERROR: {error}",
    "data_unavailable": "DATA NOT AVAILABLE",
    "fetch_failed": "DATA FETCH FAILED (無法獲取資料)",
    "timeframe_mismatch": "TIMEFRAME MISMATCH ERROR (資料區間不匹配)"
}