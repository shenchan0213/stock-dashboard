import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import twstock
import pytz

# --- 1. 頁面基礎設定 & CSS 注入 (軍規化核心) ---
st.set_page_config(page_title="Vesion XII - TACTICAL", layout="wide")

# 定義戰術風格 CSS
st.markdown("""
    <style>
        /* 全局字體：強制使用等寬字體，模擬終端機 */
        @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;700&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Roboto Mono', 'Consolas', 'Courier New', monospace;
        }

        /* 標題樣式：軍事印章感 */
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            font-weight: 700;
            color: #e0e0e0;
        }

        /* 關鍵指標 (Metrics)：CRT 螢幕發光效果 */
        div[data-testid="stMetricValue"] {
            color: #00ff41 !important; /* 駭客綠 */
            text-shadow: 0 0 10px rgba(0, 255, 65, 0.5);
            font-weight: bold;
        }
        
        div[data-testid="stMetricLabel"] {
            color: #888;
            font-size: 0.9rem;
        }

        /* 側邊欄：深色磨砂質感 */
        section[data-testid="stSidebar"] {
            background-color: #0b0c10;
            border-right: 1px solid #333;
        }

        /* 按鈕：戰術按鈕風格 */
        div.stButton > button {
            background-color: #1f2833;
            color: #66fcf1;
            border: 1px solid #45a29e;
            border-radius: 0px; /* 直角設計 */
        }
        div.stButton > button:hover {
            background-color: #45a29e;
            color: #0b0c10;
            border-color: #66fcf1;
        }
        
        /* 警告框樣式 */
        .stAlert {
            background-color: #1a1a1a;
            color: #e0e0e0;
            border: 1px solid #333;
        }
    </style>
""", unsafe_allow_html=True)

st.title(" 數據面板 SHEN XII version ")

# --- 定義期貨與大盤清單 ---
FUTURES_MAP = {
    "台指期 (TX)": "WTX=F",
    "微型台指 (Mini TX)": "WTX=F",
    "小道瓊 (YM)": "YM=F",
    "那斯達克 (NQ)": "NQ=F",
    "S&P 500 (ES)": "ES=F",
    "黃金 (Gold)": "GC=F",
    "原油 (Oil)": "CL=F",
    "比特幣 (BTC)": "BTC-USD",
    "美元指數 (DX)": "DX=F"
}

BENCHMARK_MAP = {
    "台灣加權指數 (TSE)": "^TWII",
    "S&P 500 (SPX)": "^GSPC",
    "那斯達克 (IXIC)": "^IXIC",
    "費城半導體 (SOX)": "^SOX",
    "台積電 (2330)": "2330.TW",
    "元大台灣50 (0050)": "0050.TW"
}

# --- 建立全台股代號清單 ---
if 'stock_map' not in st.session_state:
    st.session_state.stock_map = {f"{code} {info.name}": code for code, info in twstock.codes.items()}

# --- 側邊欄設定 ---
st.sidebar.markdown("### ⚙️ CONTROL CENTER")
market_type = st.sidebar.radio("TARGET MARKET", ["🇹🇼 台灣個股", " 全球期貨/外匯"])
st.sidebar.markdown("---")
# [修正] 移除 Emoji，回復純文字選項
mode = st.sidebar.radio("OPERATION MODE", ["即時走勢", "歷史K線 + RSI", "績效比較"])

# --- 輔助函數 ---
def find_name_by_code(target_code):
    for name_key, code_val in st.session_state.stock_map.items():
        if code_val == target_code:
            return name_key
    return f"CODE {target_code}"

# --- 技術指標計算函數 (RSI) ---
def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# --- 核心函數：抓取歷史資料 ---
@st.cache_data(ttl=300)
def get_history_data(ticker, period="6mo", interval="1d"):
    try:
        df = yf.Ticker(ticker).history(period=period, interval=interval)
        if df.empty: return None
        df.reset_index(inplace=True)
        if 'Datetime' in df.columns: df.rename(columns={'Datetime': 'Date'}, inplace=True)
        if pd.api.types.is_datetime64_any_dtype(df['Date']):
             df['Date'] = df['Date'].dt.tz_localize(None)
        
        # 計算技術指標
        if len(df) > 14:
            df['RSI'] = calculate_rsi(df)
            df['SMA5'] = df['Close'].rolling(5).mean()
            df['SMA20'] = df['Close'].rolling(20).mean()
            
        return df
    except:
        return None

# --- 核心函數：抓取基本面 ---
@st.cache_data(ttl=3600)
def get_fundamentals(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return info
    except:
        return {}

# --- 核心函數：抓取即時走勢 ---
def get_intraday_data(ticker):
    try:
        df = yf.Ticker(ticker).history(period='1d', interval='1m')
        if df.empty:
            df = yf.Ticker(ticker).history(period='5d', interval='1m')
            if not df.empty:
                last_date = df.index.max().date()
                df = df[df.index.date == last_date]
        return df
    except:
        return pd.DataFrame()

# --- 繪製走勢圖函數 (風格升級版) ---
def plot_intraday_chart(df, title):
    df.reset_index(inplace=True)
    # 時區處理
    if "TW" in title or "台" in title:
        try:
            tw_tz = pytz.timezone('Asia/Taipei')
            df['Datetime'] = df['Datetime'].dt.tz_convert(tw_tz).dt.tz_localize(None)
        except:
            df['Datetime'] = df['Datetime'].dt.tz_localize(None)
    else:
         df['Datetime'] = df['Datetime'].dt.tz_localize(None)
    
    # 配色方案：戰術綠
    line_color = '#00ff41' 
    fill_color = 'rgba(0, 255, 65, 0.1)'
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.03, row_heights=[0.75, 0.25])

    # 1. 價格線 (Line)
    fig.add_trace(go.Scatter(x=df['Datetime'], y=df['Close'], 
                             mode='lines', name='PRICE',
                             line=dict(color=line_color, width=2),
                             fill='tozeroy', fillcolor=fill_color),
                  row=1, col=1)
    
    # 2. 均價線 (Avg)
    df['Average'] = df['Close'].rolling(window=30).mean()
    fig.add_trace(go.Scatter(x=df['Datetime'], y=df['Average'], 
                             mode='lines', name='AVG',
                             line=dict(color='#ffbf00', width=1, dash='dot')), # 琥珀色
                  row=1, col=1)

    # 3. 成交量 (Volume)
    colors = ['#ff0055' if c < o else '#00ff41' for o, c in zip(df['Open'], df['Close'])] # 霓虹紅/綠
    fig.add_trace(go.Bar(x=df['Datetime'], y=df['Volume'], name='VOL', marker_color=colors),
                  row=2, col=1)

    # 4. 版面設定 (Layout) - 這是美感的關鍵
    fig.update_layout(
        title=dict(text=f"<b>{title} // INTRADAY</b>", font=dict(size=20, color='#e0e0e0')),
        height=500, 
        margin=dict(l=10, r=10, t=50, b=10),
        xaxis_type="date", 
        xaxis_rangeslider_visible=False, 
        showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)', # 透明背景
        plot_bgcolor='rgba(0,0,0,0)',  # 透明圖表區
        font=dict(family="Roboto Mono, monospace", color="#aaa") # 字體
    )
    
    # 座標軸設定：去除雜線，只留必要資訊
    fig.update_xaxes(showgrid=False, zeroline=False, row=1, col=1)
    fig.update_yaxes(showgrid=True, gridcolor='#333', gridwidth=1, row=1, col=1) # 只有Y軸留暗線
    fig.update_xaxes(showgrid=False, tickformat="%H:%M", row=2, col=1)
    fig.update_yaxes(showgrid=False, row=2, col=1)

    return fig

# --- 搜尋邏輯 ---
if market_type == "🇹🇼 台灣個股":
    search_list = list(st.session_state.stock_map.keys())
    col_s1, col_s2 = st.sidebar.columns([2, 1])
    with col_s1:
        search_selection = st.selectbox("SEARCH", ["自訂輸入"] + search_list)
    with col_s2:
        default_input = "2330"
        if search_selection != "自訂輸入":
            default_input = st.session_state.stock_map[search_selection]
        manual_input = st.text_input("CODE", value=default_input)
    
    stock_id = manual_input
    target_ticker = f"{stock_id}.TW"
    if stock_id in twstock.codes and twstock.codes[stock_id].market == '上櫃':
        target_ticker = f"{stock_id}.TWO"
        
    if search_selection != "自訂輸入":
        display_name = search_selection
    else:
        display_name = find_name_by_code(stock_id)

else:
    future_name = st.sidebar.selectbox("ASSET", list(FUTURES_MAP.keys()))
    target_ticker = FUTURES_MAP[future_name]
    display_name = future_name
    stock_id = target_ticker 

# --- 側邊欄：顯示基本面資訊 ---
st.sidebar.markdown("---")
# [修正] 這裡的文字判斷也移除 Emoji
if mode != "績效比較":
    st.sidebar.subheader(" FUNDAMENTALS")
    if market_type == "🇹🇼 台灣個股":
        with st.spinner("ACCESSING DATABASE..."):
            info = get_fundamentals(target_ticker)
            if info:
                pe_ratio = info.get('trailingPE', 'N/A')
                dividend_yield = info.get('dividendYield', 0)
                eps = info.get('trailingEps', 'N/A')
                yield_str = f"{dividend_yield*100:.2f}%" if isinstance(dividend_yield, (int, float)) else "N/A"
                
                # 使用 columns 讓資訊更緊湊
                c1, c2 = st.sidebar.columns(2)
                c1.metric("PE", f"{pe_ratio}")
                c2.metric("EPS", f"{eps}")
                st.sidebar.metric("Yield", f"{yield_str}")
            else:
                st.sidebar.info("NO DATA FOUND")
    else:
        st.sidebar.info("N/A FOR FUTURES")


# ================= 模式 1: 即時走勢 =================
# [修正] 判斷式移除 Emoji，與選單對應
if mode == "即時走勢":
    df_intraday = get_intraday_data(target_ticker)
    
    if not df_intraday.empty:
        last_price = df_intraday['Close'].iloc[-1]
        first_open = df_intraday['Open'].iloc[0]
        change = last_price - first_open
        pct_change = (change / first_open) * 100
        last_time = df_intraday.index[-1]
        time_str = last_time.strftime('%H:%M:%S')
        
        # 抬頭顯示器 (HUD) 風格
        col1, col2, col3, col4 = st.columns(4)
        col1.metric(f"PRICE", f"{last_price:.2f}", f"{change:.2f}")
        col2.metric("CHANGE %", f"{pct_change:.2f}%")
        col3.metric("HIGH", f"{df_intraday['High'].max():.2f}")
        col4.metric("LOW", f"{df_intraday['Low'].min():.2f}")
        
        st.caption(f" LAST UPDATED: {time_str} | SYSTEM: ONLINE")
        
        st.markdown("---")
        fig = plot_intraday_chart(df_intraday, display_name)
        st.plotly_chart(fig, use_container_width=True)

        if market_type == "🇹🇼 台灣個股":
            st.markdown("###  ORDER BOOK (LEVEL 2)")
            col_bidask, col_info = st.columns([1.5, 1])
            with col_bidask:
                try:
                    with st.spinner("CONNECTING TWSE..."):
                        realtime_stock = twstock.realtime.get(stock_id)
                        if realtime_stock['success']:
                            info = realtime_stock['realtime']
                            # 重新組織五檔顯示，讓它看起來像報價機
                            ask_data = [{"ASK PRICE": info['best_ask_price'][i], "VOL": info['best_ask_volume'][i]} for i in range(len(info['best_ask_price']))]
                            bid_data = [{"BID PRICE": info['best_bid_price'][i], "VOL": info['best_bid_volume'][i]} for i in range(len(info['best_bid_price']))]
                            
                            # 合併顯示
                            st.markdown("**SELL (ASK)**")
                            st.dataframe(pd.DataFrame(ask_data[::-1]), hide_index=True, use_container_width=True)
                            st.markdown("**BUY (BID)**")
                            st.dataframe(pd.DataFrame(bid_data), hide_index=True, use_container_width=True)
                        else:
                            st.warning("DATA LINK FAILED")
                except:
                    st.error("CONNECTION TIMEOUT")
            with col_info:
                st.info("ℹ️ SOURCE:\n- CHART: YAHOO FINANCE API\n- ORDER BOOK: TWSE DIRECT LINK")
        else:
            st.info(f"ℹ️ {display_name} : INTERNATIONAL MARKET DATA ONLY")

    else:
        st.warning(f"⚠️ NO SIGNAL: {display_name}")

# ================= 模式 2: 歷史K線 + RSI =================
# [修正] 判斷式移除 Emoji
elif mode == "歷史K線 + RSI":
    col_k1, col_k2 = st.sidebar.columns(2)
    with col_k1:
        period = st.selectbox("PERIOD", ["3mo", "6mo", "1y", "3y", "5y"], index=1)
    with col_k2:
        interval_ui = st.selectbox("INTERVAL", ["日K", "週K", "月K"], index=0)
    
    interval_map = {"日K": "1d", "週K": "1wk", "月K": "1mo"}
    interval = interval_map[interval_ui]
    
    with st.spinner("LOADING HISTORICAL DATA..."):
        df = get_history_data(target_ticker, period, interval)
    
    if df is not None:
        st.subheader(f"{display_name} // TECHNICAL ANALYSIS")
        
        # K線圖設定
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.03, row_heights=[0.7, 0.3])
        
        # 蠟燭圖 (自訂顏色)
        fig.add_trace(go.Candlestick(x=df['Date'],
                        open=df['Open'], high=df['High'],
                        low=df['Low'], close=df['Close'],
                        name='OHLC',
                        increasing_line_color='#00ff41', increasing_fillcolor='rgba(0, 255, 65, 0.1)', # 漲：綠
                        decreasing_line_color='#ff0055', decreasing_fillcolor='rgba(255, 0, 85, 0.1)'  # 跌：紅
                        ), row=1, col=1)
        
        fig.add_trace(go.Scatter(x=df['Date'], y=df['SMA5'], line=dict(color='#ffbf00', width=1), name='5MA'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['SMA20'], line=dict(color='#00ccff', width=1), name='20MA'), row=1, col=1)

        if 'RSI' in df.columns:
            fig.add_trace(go.Scatter(x=df['Date'], y=df['RSI'], 
                                     line=dict(color='#bd00ff', width=2), name='RSI (14)'), row=2, col=1)
            fig.add_hline(y=70, line_dash="dot", line_color="#ff0055", row=2, col=1)
            fig.add_hline(y=30, line_dash="dot", line_color="#00ff41", row=2, col=1)

        # 戰術版面配置
        fig.update_layout(height=700, xaxis_rangeslider_visible=False,
                          paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                          font=dict(family="Roboto Mono, monospace", color="#ccc"),
                          showlegend=False)
        
        fig.update_xaxes(showgrid=False, row=1, col=1)
        fig.update_yaxes(showgrid=True, gridcolor='#333', row=1, col=1)
        fig.update_yaxes(showgrid=False, row=2, col=1)
        
        st.plotly_chart(fig, use_container_width=True)     
    else:
        st.error("DATA NOT AVAILABLE")

# ================= 模式 3: 績效比較 (Benchmark) =================
# [修正] 判斷式移除 Emoji
elif mode == "績效比較":
    st.subheader(f"⚔️ VS MODE: {display_name} vs BENCHMARK")
    
    col_b1, col_b2, col_b3 = st.columns([2, 1, 1])
    with col_b1:
        bench_selection = st.selectbox("OPPONENT", ["台灣加權指數 (TSE)", "S&P 500 (SPX)", "自訂輸入"])
    
    with col_b2:
        if bench_selection == "自訂輸入":
            bench_input = st.text_input("OPPONENT CODE", value="^TWII")
            benchmark_ticker = bench_input.upper()
        else:
            benchmark_ticker = BENCHMARK_MAP[bench_selection]
            st.text_input("CODE", value=benchmark_ticker, disabled=True)
            
    with col_b3:
        compare_period = st.selectbox("TIMEFRAME", ["3mo", "6mo", "1y", "3y", "5y", "ytd"], index=2)

    if st.button("INITIATE COMPARISON"):
        with st.spinner("CALCULATING ALPHA..."):
            df_main = get_history_data(target_ticker, period=compare_period)
            df_bench = get_history_data(benchmark_ticker, period=compare_period)
            
            if df_main is not None and df_bench is not None:
                df_merge = pd.merge(df_main[['Date', 'Close']], df_bench[['Date', 'Close']], 
                                    on='Date', suffixes=('_Main', '_Bench'), how='inner')
                
                if not df_merge.empty:
                    base_price_main = df_merge['Close_Main'].iloc[0]
                    base_price_bench = df_merge['Close_Bench'].iloc[0]
                    
                    df_merge['Return_Main'] = (df_merge['Close_Main'] / base_price_main - 1) * 100
                    df_merge['Return_Bench'] = (df_merge['Close_Bench'] / base_price_bench - 1) * 100
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=df_merge['Date'], y=df_merge['Return_Main'],
                                             mode='lines', name=f"{display_name}",
                                             line=dict(color='#00ff41', width=3))) # 主角：亮綠
                    fig.add_trace(go.Scatter(x=df_merge['Date'], y=df_merge['Return_Bench'],
                                             mode='lines', name=f"BENCHMARK",
                                             line=dict(color='#666', width=2, dash='dot'))) # 對手：暗灰
                    fig.add_hline(y=0, line_dash="solid", line_color="#fff", opacity=0.2)

                    final_ret_main = df_merge['Return_Main'].iloc[-1]
                    final_ret_bench = df_merge['Return_Bench'].iloc[-1]
                    
                    # 戰術版面
                    fig.update_layout(title=f"PERFORMANCE DELTA",
                                      yaxis_title="RETURN (%)", height=500, hovermode="x unified",
                                      paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                      font=dict(family="Roboto Mono, monospace", color="#ccc"),
                                      xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='#333'))
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    diff = final_ret_main - final_ret_bench
                    status = "LEADING" if diff > 0 else "LAGGING"
                    color_code = "#00ff41" if diff > 0 else "#ff0055" # 綠 / 紅
                    
                    # 結論區塊
                    st.markdown(f"""
                    <div style="border: 1px solid {color_code}; padding: 20px; border-radius: 5px;">
                        <h3 style="color: {color_code}; margin:0;">STATUS: {status}</h3>
                        <p style="margin:0;">DELTA: <b>{diff:+.2f}%</b></p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.error("TIMEFRAME MISMATCH ERROR")
            else:
                st.error("DATA FETCH FAILED")