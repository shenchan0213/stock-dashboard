"""
數據面板 SHEN XIV TACTICAL - FMP 完整版
"""

import streamlit as st
import pandas as pd
from analysis import get_financial_health

from config import (
    FUTURES_MAP, BENCHMARK_MAP, LABELS,
    CUSTOM_CSS, ERROR_MESSAGES, COLORS,
)
from utils import (
    init_session_state,
    find_stock_name_by_code,
    get_history_data,
    get_fundamentals,
    get_intraday_data,
    get_watchlist_batch,
    format_number,
    calculate_percentage_change,
    calculate_returns,
)
from chart_components import (
    create_intraday_chart,
    create_candlestick_chart,
    create_comparison_chart,
    create_sparkline
)


# ==================== 1. 頁面設定 ====================
def setup_page():
    st.set_page_config(page_title="SHEN XIV - TACTICAL", layout="wide")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ==================== 2. GLOBAL WATCHLIST (FMP 版) ====================
def render_watchlist_header():
    """GLOBAL WATCHLIST - 已改用 FMP 批次查詢"""
    st.markdown("### 🌍 GLOBAL WATCHLIST")
    
    watchlist = [
        ("^TWII", "加權指數"),
        ("NVDA",  "NVDA"),
        ("TSM",   "TSM(ADR)"),
        ("AAPL",  "AAPL")
    ]
    
    batch_data = get_watchlist_batch(tuple(t[0] for t in watchlist))
    
    for ticker, name in watchlist:
        try:
            df = get_history_data(ticker, period="5d", include_indicators=False)
            info = batch_data.get(ticker, {})
            
            current = info.get("price") or (df["Close"].iloc[-1] if not df.empty else 0)
            prev = df["Close"].iloc[-2] if not df.empty and len(df) > 1 else current
            change_pct = ((current - prev) / prev * 100) if prev and prev != 0 else 0
            
            col1, col2, col3 = st.columns([1.8, 3, 2])
            with col1:
                st.markdown(f"**{name}**")
            with col2:
                if not df.empty:
                    fig = create_sparkline(df.set_index("Date"), name, change_pct)
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                else:
                    st.write("—")
            with col3:
                st.metric(
                    label="",
                    value=f"{current:,.2f}" if current else "N/A",
                    delta=f"{change_pct:+.2f}%"
                )
            st.markdown("---")
        except Exception:
            st.metric(name, "N/A")
    st.markdown("---")


# ==================== 3. 側邊欄 ====================
def setup_sidebar() -> tuple:
    st.sidebar.markdown(LABELS["sidebar_header"])

    market_type = st.sidebar.radio("TARGET MARKET", LABELS["market_types"])
    st.sidebar.markdown("---")

    mode = st.sidebar.radio("OPERATION MODE", LABELS["operation_modes"])
    st.sidebar.markdown("---")

    if market_type == "🇹🇼 台灣個股":
        target_input  = st.sidebar.text_input("STOCK CODE", value="2330", help="輸入台股代號（如: 2330）")
        target_ticker = f"{target_input}.TW"
        display_name  = find_stock_name_by_code(target_input)
    elif market_type == "🇺🇸 美股/ETF":
        target_input  = st.sidebar.text_input("STOCK CODE", value="NVDA", help="輸入美股代號 (如: NVDA, AAPL)")
        target_ticker = target_input.upper().strip()
        display_name  = target_ticker
    else:
        futures_sel   = st.sidebar.selectbox("SELECT FUTURES", list(FUTURES_MAP.keys()))
        target_ticker = FUTURES_MAP[futures_sel]
        display_name  = futures_sel

    auto_refresh = False
    if mode == "即時走勢":
        st.sidebar.markdown("---")
        auto_refresh = st.sidebar.toggle("⟳ 自動刷新 (60s)", value=False)

    st.sidebar.markdown("---")
    with st.sidebar.expander("⚙️ 自訂跑馬燈標的", expanded=False):
        current_list = st.session_state.get("watchlist", [])
        st.caption("目前：" + "、".join(l for _, l in current_list))
        new_ticker = st.text_input("新增代號 (如 MSFT)", key="add_ticker").upper().strip()
        new_label  = st.text_input("顯示名稱 (如 微軟)", key="add_label").strip()
        if st.button("➕ 新增", key="btn_add"):
            if new_ticker and new_label:
                if new_ticker not in [t for t, _ in current_list]:
                    st.session_state.watchlist.append((new_ticker, new_label))
                    st.rerun()
        remove_label = st.selectbox("移除標的", ["—"] + [l for _, l in current_list], key="remove_sel")
        if st.button("➖ 移除", key="btn_remove") and remove_label != "—":
            st.session_state.watchlist = [(t, l) for t, l in current_list if l != remove_label]
            st.rerun()

    return market_type, mode, target_ticker, display_name, auto_refresh


# ==================== 4. 資訊面板 ====================
def display_fundamentals(info: dict, ticker: str):
    if not info:
        st.warning("基本面資料無法取得")
        return

    current  = info.get("currentPrice", info.get("regularMarketPrice", 0)) or 0
    previous = info.get("previousClose", 0) or 0
    open_p   = info.get("open", 0) or 0
    day_high = info.get("dayHigh", 0) or 0
    day_low  = info.get("dayLow", 0) or 0
    volume   = info.get("volume", 0) or 0
    mkt_cap  = info.get("marketCap", 0) or 0

    change_pct, _ = calculate_percentage_change(current, previous)
    color = "normal" if change_pct >= 0 else "inverse"

    c1, _ = st.columns([2, 4])
    with c1:
        st.metric("CURRENT PRICE", f"{current:,.2f}",
                  delta=f"{change_pct:.2f}%", delta_color=color)

    st.markdown("###### MARKET DATA")
    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    r2c1, r2c2, r2c3, r2c4 = st.columns(4)
    r1c1.metric("開盤 Open",    f"{open_p:,.2f}")
    r1c2.metric("最高 High",    f"{day_high:,.2f}")
    r1c3.metric("最低 Low",     f"{day_low:,.2f}")
    r1c4.metric("市值 Mkt Cap", format_number(mkt_cap))
    r2c1.metric("成交量 Vol",   format_number(volume))
    r2c4.metric("昨收 Prev",    f"{previous:,.2f}")
    st.markdown("---")


def display_order_book(ticker: str):
    st.markdown("### 📊 ORDER BOOK (五檔報價)")
    code = ticker.replace(".TW", "")
    with st.expander("查看五檔資訊", expanded=False):
        try:
            import twstock
            stock = twstock.realtime.get(code)
            if stock and stock.get("success") and "best_ask_price" in stock:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**賣出 ASK**")
                    st.dataframe(pd.DataFrame([
                        {"PRICE": p, "VOL": v}
                        for p, v in zip(stock["best_ask_price"], stock["best_ask_volume"])
                    ][::-1]), hide_index=True, use_container_width=True)
                with c2:
                    st.markdown("**買進 BID**")
                    st.dataframe(pd.DataFrame([
                        {"PRICE": p, "VOL": v}
                        for p, v in zip(stock["best_bid_price"], stock["best_bid_volume"])
                    ]), hide_index=True, use_container_width=True)
            else:
                st.warning(ERROR_MESSAGES["order_book_empty"])
        except Exception as e:
            st.error(f"Order Book Error: {e}")


def _display_health_panel(health_data: dict):
    data   = health_data["data"]
    score  = health_data.get("health_score", 0)
    sector = health_data.get("sector", "—")
    scores = health_data.get("_scores", {})

    color = (
        "#00ff41" if score >= 85 else
        "#00ccff" if score >= 72 else
        "#ffbf00" if score >= 58 else
        "#ff6600" if score >= 40 else "#ff0055"
    )

    st.markdown(f"""
    <div style="text-align:center;padding:20px;background:#111;border-radius:12px;
                border:2px solid {color};margin-bottom:14px;">
      <p style="margin:0;color:#555;font-size:0.75rem;">HEALTH SCORE &nbsp;|&nbsp; {sector.upper()}</p>
      <h1 style="margin:8px 0 0;font-size:3.8rem;color:{color};">{score}</h1>
      <p style="margin:4px 0 0;color:#444;font-size:0.8rem;">/ 100</p>
    </div>
    """, unsafe_allow_html=True)
    st.progress(int(score) / 100)
    st.info(f"💡 **洞察**：{health_data.get('insight', '')}")

    if scores:
        st.markdown("##### 分項評分")
        # （您可在此貼上原版的分項進度條程式碼，若需我補充請告知）
        pass


# ==================== 5. 操作模式 ====================
def mode_realtime(target_ticker: str, display_name: str, market_type: str, auto_refresh: bool):
    st.subheader(f"📡 LIVE FEED // {display_name}")

    with st.spinner("CONNECTING TO MARKET..."):
        df = get_intraday_data(target_ticker)
        info = get_fundamentals(target_ticker)

    if info:
        display_fundamentals(info, target_ticker)
    else:
        st.warning("🛑 市場已收盤，目前顯示最後交易日數據")

    if not df.empty:
        fig = create_intraday_chart(df, f"{display_name} // INTRADAY")
        if fig:
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("📅 非交易時間，無法顯示即時走勢圖")

    if market_type == "🇹🇼 台灣個股":
        display_order_book(target_ticker)


def mode_historical(target_ticker: str, display_name: str):
    col1, col2 = st.sidebar.columns(2)
    with col1:
        period = st.sidebar.selectbox("PERIOD", LABELS["period_options"], index=1)
    with col2:
        interval_ui = st.sidebar.selectbox("INTERVAL", LABELS["interval_options"], index=0)
    interval = LABELS["interval_map"][interval_ui]

    with st.spinner("LOADING HISTORICAL DATA..."):
        df = get_history_data(target_ticker, period, interval)

    if df is None or df.empty:
        st.error(ERROR_MESSAGES["data_unavailable"])
        return

    st.subheader(f"📊 {display_name} // TECHNICAL ANALYSIS")
    fig = create_candlestick_chart(df, f"{display_name} // {interval_ui}")
    if fig:
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("🧠 STRATEGIC INTELLIGENCE // Financial Health")
    with st.spinner("ANALYZING FUNDAMENTALS..."):
        health_data = get_financial_health(target_ticker)
    if health_data:
        _display_health_panel(health_data)
    else:
        st.warning("⚠️ 無法獲取財務基本面數據")


def mode_comparison(target_ticker: str, display_name: str):
    st.subheader(f"⚔️ VS MODE: {display_name} vs BENCHMARK")

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        bench_sel = st.selectbox("OPPONENT", list(BENCHMARK_MAP.keys()) + ["自訂輸入"])
    with c2:
        if bench_sel == "自訂輸入":
            bench_input = st.text_input("OPPONENT CODE", value="^TWII")
            benchmark_ticker = bench_input.upper()
        else:
            benchmark_ticker = BENCHMARK_MAP[bench_sel]
            st.text_input("CODE", value=benchmark_ticker, disabled=True)
    with c3:
        compare_period = st.selectbox("TIMEFRAME", ["3mo", "6mo", "1y", "3y"], index=2)

    if st.button("⚔️ INITIATE COMPARISON"):
        with st.spinner("CALCULATING ALPHA..."):
            df_main  = get_history_data(target_ticker, compare_period, include_indicators=False)
            df_bench = get_history_data(benchmark_ticker, compare_period, include_indicators=False)

            if df_main is not None and df_bench is not None:
                df_merge = calculate_returns(df_main, df_bench)
                if df_merge is not None:
                    final_main  = df_merge["Return_Main"].iloc[-1]
                    final_bench = df_merge["Return_Bench"].iloc[-1]
                    alpha       = final_main - final_bench

                    m1, m2, m3 = st.columns(3)
                    m1.metric(display_name, f"{final_main:.2f}%")
                    m2.metric(bench_sel, f"{final_bench:.2f}%")
                    m3.metric("Alpha 超額報酬", f"{alpha:.2f}%", delta=f"{alpha:+.2f}%")

                    fig = create_comparison_chart(df_merge, display_name, bench_sel)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    st.error(ERROR_MESSAGES["timeframe_mismatch"])
            else:
                st.error(ERROR_MESSAGES["fetch_failed"])


# ==================== 6. 主程式入口 ====================
def main():
    setup_page()
    init_session_state()
    render_watchlist_header()                     # ← 已修正為單一括號

    market_type, mode, target_ticker, display_name, auto_refresh = setup_sidebar()

    if mode == "即時走勢":
        mode_realtime(target_ticker, display_name, market_type, auto_refresh)
    elif mode == "歷史K線 + RSI":
        mode_historical(target_ticker, display_name)
    elif mode == "績效比較":
        mode_comparison(target_ticker, display_name)


if __name__ == "__main__":
    main()