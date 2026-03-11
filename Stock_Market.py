"""
數據面板 SHEN XIV TACTICAL - 最終修復版
"""

import streamlit as st
import pandas as pd
from typing import Optional
from analysis import get_financial_health
import streamlit.components.v1 as components

# 自訂模組
from config import (
    FUTURES_MAP,
    BENCHMARK_MAP,
    LABELS,
    CUSTOM_CSS,
    ERROR_MESSAGES,
    COLORS,
)
from utils import (
    init_session_state,
    find_stock_name_by_code,
    get_history_data,
    get_fundamentals,
    get_intraday_data,
    format_number,
    calculate_percentage_change,
    calculate_returns,
    get_ticker_tape_data,
)
from chart_components import (
    create_intraday_chart,
    create_candlestick_chart,
    create_comparison_chart,
    create_sparkline,
)


# ==================== 1. 頁面基礎設定 ====================

def setup_page():
    """初始化頁面配置與樣式"""
    st.set_page_config(page_title="SHEN XIV - TACTICAL", layout="wide")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

def render_ticker_tape():
    """
    Yahoo Finance / iOS 風格水平跑馬燈
    - 紅漲綠跌（台灣慣例）
    - 含 Sparkline 迷你走勢圖
    - 無縫循環滾動動畫
    """
    watchlist = [
        ("^TWII",   "加權指數"),
        ("NVDA",    "NVDA"),
        ("TSM",     "TSM(ADR)"),
        ("AAPL",    "AAPL"),
        ("^GSPC",   "S&P500"),
        ("BTC-USD", "BTC"),
        ("^IXIC",   "NASDAQ"),
        ("^SOX",    "PHLX半導"),
        ("DX-Y.NYB","DXY"),
        ("GC=F",    "黃金"),
    ]

    import plotly.graph_objects as go
    import io, base64

    def sparkline_svg(prices, is_up: bool) -> str:
        """產生超輕量 SVG 迷你折線圖（不依賴 Plotly，速度快 10x）"""
        if len(prices) < 2:
            return ""
        W, H = 80, 32
        mn, mx = min(prices), max(prices)
        rng = mx - mn if mx != mn else 1
        pts = []
        for i, p in enumerate(prices):
            x = i / (len(prices) - 1) * W
            y = H - ((p - mn) / rng) * H
            pts.append(f"{x:.1f},{y:.1f}")
        color = "#ff3b30" if is_up else "#34c759"   # 紅漲綠跌（iOS 標準色）
        poly = " ".join(pts)
        # 填充區域
        fill_pts = f"0,{H} " + poly + f" {W},{H}"
        fill_color = "rgba(255,59,48,0.2)" if is_up else "rgba(52,199,89,0.2)"
        svg = (
            f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">'
            f'<polygon points="{fill_pts}" fill="{fill_color}"/>'
            f'<polyline points="{poly}" fill="none" stroke="{color}" stroke-width="1.8" stroke-linejoin="round"/>'
            f'</svg>'
        )
        return svg

    # ── 取得資料 ──────────────────────────────────────────
    items_html = []
    for ticker, label in watchlist:
        try:
            df = get_history_data(ticker, period="5d", include_indicators=False)
            if df is None or df.empty or len(df) < 2:
                continue
            closes = df["Close"].dropna().tolist()
            current = closes[-1]
            prev    = closes[-2]
            chg_pct = (current - prev) / prev * 100
            is_up   = chg_pct >= 0

            # 顏色（紅漲綠跌）
            color  = "#ff3b30" if is_up else "#34c759"
            arrow  = "▲" if is_up else "▼"
            bg     = "rgba(255,59,48,0.12)" if is_up else "rgba(52,199,89,0.12)"

            # 取最近 30 個收盤價做 Sparkline
            spark_prices = closes[-30:]
            svg = sparkline_svg(spark_prices, is_up)
            svg_b64 = base64.b64encode(svg.encode()).decode()
            svg_uri = f"data:image/svg+xml;base64,{svg_b64}"

            # 格式化價格
            if current >= 10000:
                price_str = f"{current:,.0f}"
            elif current >= 100:
                price_str = f"{current:,.2f}"
            else:
                price_str = f"{current:.4f}"

            item = f"""
            <div style="
                display:inline-flex; align-items:center; gap:10px;
                padding:6px 18px 6px 14px;
                margin:0 6px;
                background:{bg};
                border-radius:10px;
                border:1px solid {color}33;
                white-space:nowrap;
                vertical-align:middle;
            ">
                <!-- 名稱 -->
                <div>
                    <div style="font-size:0.75rem; color:#999; line-height:1;">{label}</div>
                    <div style="font-size:1.05rem; font-weight:700; color:#fff; line-height:1.4;">{price_str}</div>
                </div>
                <!-- Sparkline -->
                <img src="{svg_uri}" width="80" height="32" style="vertical-align:middle;"/>
                <!-- 漲跌幅 -->
                <div style="
                    font-size:0.9rem; font-weight:700; color:{color};
                    background:{bg}; padding:2px 8px; border-radius:6px;
                ">{arrow} {abs(chg_pct):.2f}%</div>
            </div>
            """
            items_html.append(item)
        except Exception:
            continue

    if not items_html:
        return  # 無資料時靜默跳過

    # ── 產生 HTML（雙份讓動畫無縫循環）──────────────────
    content = "".join(items_html)
    html = f"""
    <div style="
        width:100%; overflow:hidden;
        background:#000;
        border-bottom:1px solid #222;
        padding:8px 0;
        position:sticky; top:0; z-index:999;
    ">
        <div style="
            display:flex; width:max-content;
            animation: ticker_scroll 60s linear infinite;
        " id="ticker_inner">
            {content}{content}
        </div>
    </div>
    <style>
    @keyframes ticker_scroll {{
        0%   {{ transform: translateX(0); }}
        100% {{ transform: translateX(-50%); }}
    }}
    #ticker_inner:hover {{ animation-play-state: paused; }}
    </style>
    """
    st.markdown(html, unsafe_allow_html=True)

# ==================== 2. 側邊欄設定 ====================

def setup_sidebar() -> tuple[str, str, str, str]:
    """設定側邊欄控制選項"""
    st.sidebar.markdown(LABELS["sidebar_header"])

    # 市場選擇
    market_type = st.sidebar.radio("TARGET MARKET", LABELS["market_types"])
    st.sidebar.markdown("---")

    # 操作模式
    mode = st.sidebar.radio("OPERATION MODE", LABELS["operation_modes"])
    st.sidebar.markdown("---")

    # 標的選擇
    if market_type == "🇹🇼 台灣個股":
        target_input = st.sidebar.text_input(
            "STOCK CODE", value="2330", help="輸入台股代號（如: 2330）"
        )
        target_ticker = f"{target_input}.TW"
        display_name = find_stock_name_by_code(target_input)
    
    elif market_type == "🇺🇸 美股/ETF":
        target_input = st.sidebar.text_input(
            "STOCK CODE", value="NVDA", help="輸入美股代號 (如: NVDA, AAPL)"
        )
        target_ticker = target_input.upper().strip()
        display_name = target_ticker
        
    else:
        futures_selection = st.sidebar.selectbox(
            "SELECT FUTURES", list(FUTURES_MAP.keys())
        )
        target_ticker = FUTURES_MAP[futures_selection]
        display_name = futures_selection

    return market_type, mode, target_ticker, display_name


# ==================== 3. 核心功能模組 ====================

def display_fundamentals(info: dict, ticker: str):
    """
    高密度資訊面板 (仿 iOS 風格)
    """
    if not info:
        st.warning("基本面資料無法取得")
        return

    # 取得關鍵數據
    current = info.get("currentPrice", info.get("regularMarketPrice", 0))
    previous = info.get("previousClose", 0)
    open_p = info.get("open", 0)
    day_high = info.get("dayHigh", 0)
    day_low = info.get("dayLow", 0)
    volume = info.get("volume", 0)
    mkt_cap = info.get("marketCap", 0)
    pe = info.get("trailingPE", 0)
    eps = info.get("trailingEps", 0)
    
    change_pct, direction = calculate_percentage_change(current, previous)
    
    # 設定顏色
    color = "normal" if change_pct >= 0 else "inverse" 

    # --- 主價格區塊 (大字體) ---
    c1, c2 = st.columns([2, 4])
    with c1:
        st.metric(
            label="CURRENT PRICE",
            value=f"{current:,.2f}",
            delta=f"{change_pct:.2f}%",
            delta_color=color
        )
    
    # --- 詳細數據網格 (2x4 Grid) ---
    st.markdown("###### MARKET DATA")
    row1_c1, row1_c2, row1_c3, row1_c4 = st.columns(4)
    row2_c1, row2_c2, row2_c3, row2_c4 = st.columns(4)

    # 第一排
    row1_c1.metric("開盤 (Open)", f"{open_p:,.2f}")
    row1_c2.metric("最高 (High)", f"{day_high:,.2f}")
    row1_c3.metric("最低 (Low)", f"{day_low:,.2f}")
    row1_c4.metric("市值 (Mkt Cap)", format_number(mkt_cap))

    # 第二排
    row2_c1.metric("成交量 (Vol)", format_number(volume))
    row2_c2.metric("本益比 (P/E)", f"{pe:.2f}" if pe else "-")
    row2_c3.metric("EPS", f"{eps:.2f}" if eps else "-")
    row2_c4.metric("昨收 (Prev)", f"{previous:,.2f}")
    
    st.markdown("---")


def display_order_book(ticker: str, display_name: str):
    """顯示台股五檔報價"""
    st.markdown("### 📊 ORDER BOOK (五檔報價)")
    stock_code = ticker.replace(".TW", "")

    with st.expander("查看五檔資訊", expanded=False):
        try:
            import twstock
            stock = twstock.realtime.get(stock_code)

            if stock and stock.get("success"):
                info = stock
                if "best_ask_price" in info and "best_bid_price" in info:
                    col_ask, col_bid = st.columns(2)

                    with col_ask:
                        ask_data = [{"PRICE": p, "VOL": v} for p, v in zip(info["best_ask_price"], info["best_ask_volume"])]
                        st.markdown("**賣出 (ASK)**")
                        st.dataframe(pd.DataFrame(ask_data[::-1]), hide_index=True, use_container_width=True)

                    with col_bid:
                        bid_data = [{"PRICE": p, "VOL": v} for p, v in zip(info["best_bid_price"], info["best_bid_volume"])]
                        st.markdown("**買進 (BID)**")
                        st.dataframe(pd.DataFrame(bid_data), hide_index=True, use_container_width=True)
                else:
                    st.warning(ERROR_MESSAGES["order_book_empty"])
            else:
                st.warning(ERROR_MESSAGES["twse_failed"])
        except Exception as e:
            st.error(f"Order Book Error: {e}")


# ==================== 4. 模式邏輯 ====================

def mode_realtime(target_ticker: str, display_name: str, market_type: str):
    """即時走勢模式"""
    st.subheader(f" LIVE FEED // {display_name}")

    with st.spinner("CONNECTING TO MARKET..."):
        df = get_intraday_data(target_ticker)
        info = get_fundamentals(target_ticker)

    if df.empty:
        st.warning(ERROR_MESSAGES["no_data"].format(name=display_name))
        return

    # 顯示高密度資訊卡
    display_fundamentals(info, target_ticker)

    # 繪製圖表
    fig = create_intraday_chart(df, f"{display_name} // INTRADAY")
    if fig:
        st.plotly_chart(fig, use_container_width=True)

    # 台股才顯示五檔
    if market_type == "🇹🇼 台灣個股":
        display_order_book(target_ticker, display_name)


def mode_historical(target_ticker: str, display_name: str):
    """歷史K線分析模式（財務報告）"""
    col_k1, col_k2 = st.sidebar.columns(2)
    with col_k1:
        period = st.selectbox("PERIOD", LABELS["period_options"], index=1)
    with col_k2:
        interval_ui = st.selectbox("INTERVAL", LABELS["interval_options"], index=0)
    interval = LABELS["interval_map"][interval_ui]

    with st.spinner("LOADING HISTORICAL DATA..."):
        df = get_history_data(target_ticker, period, interval)

    if df is None:
        st.error(ERROR_MESSAGES["data_unavailable"])
        return

    st.subheader(f"{display_name} // TECHNICAL ANALYSIS")
    fig = create_candlestick_chart(df, f"{display_name} // {interval_ui}")
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    
    # ==================== 全新財務健康報告面板 ====================
    st.markdown("---")
    st.subheader("STRATEGIC INTELLIGENCE // Financial Health")
    
    with st.spinner("ANALYZING FUNDAMENTALS..."):
        health_data = get_financial_health(target_ticker)
        
    if health_data:
        data = health_data["data"]
        
        # 主視覺：綜合健康分數（彩色大字 + 進度條）
        score = health_data.get("health_score", 0)
        color = "#00ff41" if score >= 80 else "#00ccff" if score >= 65 else "#ffbf00" if score >= 50 else "#ff0055"
        
        st.markdown(f"""
        <div style="text-align:center; padding:20px; background-color:#1a1a1a; border-radius:10px; border:2px solid {color};">
            <h2 style="margin:0; color:{color};">HEALTH SCORE</h2>
            <h1 style="margin:10px 0 0 0; font-size:3.5rem; color:{color};">{score}</h1>
            <p style="margin:0; color:#aaa;">/ 100</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.progress(score / 100)
        
        # 投資洞察（醒目提示框）
        st.info(f"** 洞察**：{health_data['insight']}")
        
        # 三項核心指標（高密度）
        c1, c2, c3 = st.columns(3)
        with c1:
            pe_val = data.get('PE', 0) or 0
            st.metric(
                label="本益比 (P/E)", 
                value=f"{pe_val:.2f}", 
                delta=health_data["pe_status"],
                delta_color="inverse"
            )
        with c2:
            roe_val = data.get('ROE', 0) or 0
            st.metric(
                label="ROE (權益報酬率)", 
                value=f"{roe_val:.1f}%", 
                delta=health_data["roe_status"]
            )
        with c3:
            pm_val = data.get('Profit Margin', 0) or 0
            st.metric(
                label="淨利率 (Net Margin)", 
                value=f"{pm_val:.1f}%", 
                delta=health_data["margin_status"]
            )
        
        # 額外數據（折疊顯示）
        with st.expander(" 完整指標明細", expanded=False):
            st.json({
                "Forward PE": data.get("Forward PE"),
                "PEG Ratio": data.get("PEG"),
                "Beta": data.get("Beta")
            })
            
    else:
        st.warning("⚠️ 無法獲取財務基本面數據（指數或期貨商品無基本面）")
    # 戰略情報區塊
    st.markdown("---")
    st.subheader(f" STRATEGIC INTELLIGENCE // Inform")
    
    with st.spinner("ANALYZING FUNDAMENTALS..."):
        health_data = get_financial_health(target_ticker)
        
    if health_data:
        data = health_data["data"]
        with st.expander("查看財務健康度報告 (Financial Health Report)", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                pe_val = data['PE'] if data['PE'] else 0
                st.metric("本益比 (P/E)", f"{pe_val:.2f}", health_data["pe_status"], delta_color="inverse")
            with c2:
                roe_val = data['ROE'] * 100 if data['ROE'] else 0
                st.metric("ROE (權益報酬率)", f"{roe_val:.2f}%", health_data["roe_status"])
            with c3:
                pm_val = data['Profit Margin'] * 100 if data['Profit Margin'] else 0
                st.metric("淨利率 (Net Margin)", f"{pm_val:.2f}%", health_data["margin_status"])
            
            st.info(f"💡 顧問洞察：ROE 為 **{roe_val:.1f}%**，評級：**{health_data['roe_status']}**。")
    else:
        st.warning("⚠️ 無法獲取財務基本面數據 (可能為指數或期貨商品)")


def mode_comparison(target_ticker: str, display_name: str):
    """績效比較模式"""
    st.subheader(f"⚔️ VS MODE: {display_name} vs BENCHMARK")
    
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        bench_selection = st.selectbox("OPPONENT", list(BENCHMARK_MAP.keys()) + ["自訂輸入"])
    with c2:
        if bench_selection == "自訂輸入":
            bench_input = st.text_input("OPPONENT CODE", value="^TWII")
            benchmark_ticker = bench_input.upper()
        else:
            benchmark_ticker = BENCHMARK_MAP[bench_selection]
            st.text_input("CODE", value=benchmark_ticker, disabled=True)
    with c3:
        compare_period = st.selectbox("TIMEFRAME", ["3mo", "6mo", "1y", "3y"], index=2)

    if st.button("INITIATE COMPARISON"):
        with st.spinner("CALCULATING ALPHA..."):
            df_main = get_history_data(target_ticker, period=compare_period, include_indicators=False)
            df_bench = get_history_data(benchmark_ticker, period=compare_period, include_indicators=False)

            if df_main is not None and df_bench is not None:
                df_merge = calculate_returns(df_main, df_bench)
                if df_merge is not None:
                    fig = create_comparison_chart(df_merge, display_name, bench_selection)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.error(ERROR_MESSAGES["timeframe_mismatch"])
            else:
                st.error(ERROR_MESSAGES["fetch_failed"])


# ==================== 5. 主程式入口 ====================

def main():
    """Main Entry Point"""
    # 1. 頁面設定
    setup_page()
    
    # 2. 渲染跑馬燈 (必須在 setup_page 之後)
    render_ticker_tape()

    # 3. 初始化狀態
    init_session_state()

    # 4. 側邊欄互動
    market_type, mode, target_ticker, display_name = setup_sidebar()

    # 5. 模式路由
    if mode == "即時走勢":
        mode_realtime(target_ticker, display_name, market_type)
    elif mode == "歷史K線 + RSI":
        mode_historical(target_ticker, display_name)
    elif mode == "績效比較":
        mode_comparison(target_ticker, display_name)

if __name__ == "__main__":
    main()