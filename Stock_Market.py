import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import twstock
import pytz

# --- 頁面設定 ---
st.set_page_config(page_title="全球戰情室 Pro", layout="wide")
st.title("數據面板")

# --- 定義期貨與大盤清單 (擴充用於比較) ---
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
st.sidebar.header(" 控制中心")
market_type = st.sidebar.radio("選擇市場", ["🇹🇼 台灣個股", " 全球期貨/外匯"])
# 新增 "績效比較" 模式
mode = st.sidebar.radio("功能模式", [" 即時走勢", "📊 歷史K線 + RSI", "⚖️ 績效比較"])

# --- 輔助函數 ---
def find_name_by_code(target_code):
    for name_key, code_val in st.session_state.stock_map.items():
        if code_val == target_code:
            return name_key
    return f"代號 {target_code}"

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

# --- 核心函數：抓取即時走勢 (V9.1 修復版) ---
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

# --- 繪製走勢圖函數 ---
def plot_intraday_chart(df, title):
    df.reset_index(inplace=True)
    if "TW" in title or "台" in title:
        try:
            tw_tz = pytz.timezone('Asia/Taipei')
            df['Datetime'] = df['Datetime'].dt.tz_convert(tw_tz).dt.tz_localize(None)
        except:
            df['Datetime'] = df['Datetime'].dt.tz_localize(None)
    else:
         df['Datetime'] = df['Datetime'].dt.tz_localize(None)
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.7, 0.3])

    fig.add_trace(go.Scatter(x=df['Datetime'], y=df['Close'], 
                             mode='lines', name='成交價',
                             line=dict(color='#00ff00', width=2),
                             fill='tozeroy', fillcolor='rgba(0, 255, 0, 0.1)'),
                  row=1, col=1)
    
    df['Average'] = df['Close'].rolling(window=30).mean()
    fig.add_trace(go.Scatter(x=df['Datetime'], y=df['Average'], 
                             mode='lines', name='均價',
                             line=dict(color='orange', width=1, dash='dot')),
                  row=1, col=1)

    colors = ['red' if c >= o else 'green' for o, c in zip(df['Open'], df['Close'])]
    fig.add_trace(go.Bar(x=df['Datetime'], y=df['Volume'], name='量', marker_color=colors),
                  row=2, col=1)

    fig.update_layout(title=f"{title} 走勢", height=500, margin=dict(l=10, r=10, t=40, b=10),
                      xaxis_type="date", xaxis_rangeslider_visible=False, showlegend=False)
    fig.update_xaxes(tickformat="%H:%M", row=2, col=1)
    return fig

# --- 搜尋邏輯 ---
if market_type == "🇹🇼 台灣個股":
    search_list = list(st.session_state.stock_map.keys())
    col_s1, col_s2 = st.sidebar.columns([2, 1])
    with col_s1:
        search_selection = st.selectbox("搜尋股票", ["自訂輸入"] + search_list)
    with col_s2:
        default_input = "2330"
        if search_selection != "自訂輸入":
            default_input = st.session_state.stock_map[search_selection]
        manual_input = st.text_input("代號", value=default_input)
    
    stock_id = manual_input
    target_ticker = f"{stock_id}.TW"
    if stock_id in twstock.codes and twstock.codes[stock_id].market == '上櫃':
        target_ticker = f"{stock_id}.TWO"
        
    if search_selection != "自訂輸入":
        display_name = search_selection
    else:
        display_name = find_name_by_code(stock_id)

else:
    future_name = st.sidebar.selectbox("選擇商品", list(FUTURES_MAP.keys()))
    target_ticker = FUTURES_MAP[future_name]
    display_name = future_name
    stock_id = target_ticker 

# --- 側邊欄：顯示基本面資訊 ---
st.sidebar.markdown("---")
if mode != "⚖️ 績效比較": # 比較模式時隱藏，避免資訊過多
    st.sidebar.subheader("📊 基本面概況")
    if market_type == "🇹🇼 台灣個股":
        with st.spinner("抓取財報數據..."):
            info = get_fundamentals(target_ticker)
            if info:
                pe_ratio = info.get('trailingPE', 'N/A')
                dividend_yield = info.get('dividendYield', 0)
                eps = info.get('trailingEps', 'N/A')
                yield_str = f"{dividend_yield*100:.2f}%" if isinstance(dividend_yield, (int, float)) else "N/A"
                
                st.sidebar.metric("本益比 (PE)", f"{pe_ratio}")
                st.sidebar.metric("每股盈餘 (EPS)", f"{eps}")
                st.sidebar.metric("殖利率 (Yield)", f"{yield_str}")
            else:
                st.sidebar.info("無基本面資料")
    else:
        st.sidebar.info("期貨商品無基本面數據")


# ================= 模式 1: 即時走勢 =================
if mode == " 即時走勢":
    df_intraday = get_intraday_data(target_ticker)
    
    if not df_intraday.empty:
        last_price = df_intraday['Close'].iloc[-1]
        first_open = df_intraday['Open'].iloc[0]
        change = last_price - first_open
        last_time = df_intraday.index[-1]
        time_str = last_time.strftime('%Y-%m-%d %H:%M')
        
        col1, col2, col3 = st.columns(3)
        col1.metric(f"{display_name}", f"{last_price:.2f}", f"{change:.2f}")
        col2.metric("最高", f"{df_intraday['High'].max():.2f}")
        col3.metric("最低", f"{df_intraday['Low'].min():.2f}")
        
        st.caption(f"最後更新時間: {time_str}")
        
        st.markdown("### 📈 分時走勢圖")
        fig = plot_intraday_chart(df_intraday, display_name)
        st.plotly_chart(fig, use_container_width=True)

        if market_type == "🇹🇼 台灣個股":
            st.markdown("---")
            col_bidask, col_info = st.columns([1, 2])
            with col_bidask:
                st.markdown("###  五檔報價")
                try:
                    with st.spinner("連線證交所..."):
                        realtime_stock = twstock.realtime.get(stock_id)
                        if realtime_stock['success']:
                            info = realtime_stock['realtime']
                            ask_data = [{"委賣價": info['best_ask_price'][i], "張數": info['best_ask_volume'][i]} for i in range(len(info['best_ask_price']))]
                            bid_data = [{"委買價": info['best_bid_price'][i], "張數": info['best_bid_volume'][i]} for i in range(len(info['best_bid_price']))]
                            
                            st.markdown("**賣出**")
                            st.dataframe(pd.DataFrame(ask_data[::-1]), hide_index=True, use_container_width=True)
                            st.markdown("**買進**")
                            st.dataframe(pd.DataFrame(bid_data), hide_index=True, use_container_width=True)
                        else:
                            st.warning("無五檔資料")
                except:
                    st.error("連線逾時")
            with col_info:
                st.info("💡 提示：走勢圖使用 Yahoo Finance，五檔使用證交所直連。")
        else:
            st.info(f"💡 {display_name} 為國際商品，無五檔報價。")

    else:
        st.warning(f"目前抓不到 {display_name} 的即時資料。")

# ================= 模式 2: 歷史K線 + RSI =================
elif mode == "📊 歷史K線 + RSI":
    col_k1, col_k2 = st.sidebar.columns(2)
    with col_k1:
        period = st.selectbox("K線期間", ["3mo", "6mo", "1y", "3y", "5y"], index=1)
    with col_k2:
        interval_ui = st.selectbox("K線頻率", ["日K", "週K", "月K"], index=0)
    
    interval_map = {"日K": "1d", "週K": "1wk", "月K": "1mo"}
    interval = interval_map[interval_ui]
    
    with st.spinner("載入歷史數據..."):
        df = get_history_data(target_ticker, period, interval)
    
    if df is not None:
        st.subheader(f"{display_name} - 技術分析")
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.05, row_heights=[0.7, 0.3])
        
        fig.add_trace(go.Candlestick(x=df['Date'], open=df['Open'], high=df['High'],
                        low=df['Low'], close=df['Close'], name='K線'), row=1, col=1)
        
        fig.add_trace(go.Scatter(x=df['Date'], y=df['SMA5'], line=dict(color='orange', width=1), name='5MA'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['SMA20'], line=dict(color='purple', width=1), name='20MA'), row=1, col=1)

        if 'RSI' in df.columns:
            fig.add_trace(go.Scatter(x=df['Date'], y=df['RSI'], 
                                     line=dict(color='#00ccff', width=2), name='RSI (14)'), row=2, col=1)
            fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
            fig.add_hline(y=30, line_dash="dot", line_color="green", row=2, col=1)

        fig.update_layout(height=600, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)     
    else:
        st.error("查無歷史資料")

# ================= 模式 3: 績效比較 (Benchmark) =================
elif mode == "⚖️ 績效比較":
    st.subheader(f"⚖️ 績效比較：{display_name} vs 對照組")
    
    col_b1, col_b2, col_b3 = st.columns([2, 1, 1])
    with col_b1:
        # 讓使用者選擇常見對照組，或手動輸入
        bench_selection = st.selectbox("選擇對照組", ["台灣加權指數 (TSE)", "S&P 500 (SPX)", "自訂輸入"])
    
    with col_b2:
        if bench_selection == "自訂輸入":
            bench_input = st.text_input("輸入對照代號 (如 2330.TW)", value="^TWII")
            benchmark_ticker = bench_input.upper()
        else:
            benchmark_ticker = BENCHMARK_MAP[bench_selection]
            st.text_input("對照代號", value=benchmark_ticker, disabled=True)
            
    with col_b3:
        compare_period = st.selectbox("比較期間", ["3mo", "6mo", "1y", "3y", "5y", "ytd"], index=2)

    if st.button("開始比較"):
        with st.spinner("抓取雙方數據並計算績效..."):
            # 1. 抓取主要股票數據
            df_main = get_history_data(target_ticker, period=compare_period)
            # 2. 抓取對照組數據
            df_bench = get_history_data(benchmark_ticker, period=compare_period)
            
            if df_main is not None and df_bench is not None:
                # 3. 資料合併與對齊 (只保留兩者都有交易的日期)
                df_merge = pd.merge(df_main[['Date', 'Close']], df_bench[['Date', 'Close']], 
                                    on='Date', suffixes=('_Main', '_Bench'), how='inner')
                
                if not df_merge.empty:
                    # 4. 計算歸一化報酬率 (Normalized Return)
                    # 公式：(當前價格 / 第一天價格) - 1
                    base_price_main = df_merge['Close_Main'].iloc[0]
                    base_price_bench = df_merge['Close_Bench'].iloc[0]
                    
                    df_merge['Return_Main'] = (df_merge['Close_Main'] / base_price_main - 1) * 100
                    df_merge['Return_Bench'] = (df_merge['Close_Bench'] / base_price_bench - 1) * 100
                    
                    # 5. 繪圖
                    fig = go.Figure()
                    
                    # 主要股票線圖
                    fig.add_trace(go.Scatter(
                        x=df_merge['Date'], y=df_merge['Return_Main'],
                        mode='lines', name=f"{display_name}",
                        line=dict(color='#00ff00', width=2)
                    ))
                    
                    # 對照組線圖
                    fig.add_trace(go.Scatter(
                        x=df_merge['Date'], y=df_merge['Return_Bench'],
                        mode='lines', name=f"{bench_selection if bench_selection != '自訂輸入' else benchmark_ticker}",
                        line=dict(color='gray', width=2, dash='dot')
                    ))
                    
                    # 零軸線 (損益兩平線)
                    fig.add_hline(y=0, line_dash="solid", line_color="white", opacity=0.3)

                    # 找出最後績效以顯示在標題
                    final_ret_main = df_merge['Return_Main'].iloc[-1]
                    final_ret_bench = df_merge['Return_Bench'].iloc[-1]
                    
                    fig.update_layout(
                        title=f"績效比較 (區間累計報酬率): {display_name} [{final_ret_main:+.2f}%] vs 對照組 [{final_ret_bench:+.2f}%]",
                        xaxis_title="日期",
                        yaxis_title="累計報酬率 (%)",
                        height=500,
                        hovermode="x unified" # 游標移上去會同時顯示兩個數值
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # 額外數據分析
                    diff = final_ret_main - final_ret_bench
                    status = "領先" if diff > 0 else "落後"
                    color = "green" if diff > 0 else "red"
                    st.markdown(f"### 📊 結論：{display_name} 目前 :{color}[**{status}**] 對照組 **{abs(diff):.2f}%**")
                    
                else:
                    st.error("日期無法對齊，可能是其中一檔股票該區間無交易資料。")
            else:
                st.error("抓取資料失敗，請確認代號是否正確。")