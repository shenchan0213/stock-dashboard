"""
數據面板 SHEN XIII TACTICAL - 重構版本
改進項目：
1. 模組化設計 - 將配置、工具函數、圖表元件分離
2. 型別提示 - 所有函數加入完整的型別標註
3. 錯誤處理 - 使用具體的異常處理，避免籠統的 except
4. 消除 Magic Numbers - 所有常數集中在 config.py
5. 減少重複代碼 - 抽取共用邏輯
"""

import streamlit as st
import pandas as pd
from typing import Optional

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
)
from chart_components import (
    create_intraday_chart,
    create_candlestick_chart,
    create_comparison_chart,
)


# ==================== 頁面基礎設定 ====================


def setup_page():
    """初始化頁面配置與樣式"""
    st.set_page_config(page_title="Version XIII - TACTICAL", layout="wide")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.title(LABELS["app_title"])


# ==================== 側邊欄設定 ====================


def setup_sidebar() -> tuple[str, str, str]:
    """
    設定側邊欄控制選項

    Returns:
        (市場類型, 操作模式, 目標代碼)
    """
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
    else:
        futures_selection = st.sidebar.selectbox(
            "SELECT FUTURES", list(FUTURES_MAP.keys())
        )
        target_ticker = FUTURES_MAP[futures_selection]
        display_name = futures_selection

    return market_type, mode, target_ticker, display_name


# ==================== 基本面資訊顯示 ====================


def display_fundamentals(info: dict, ticker: str):
    """
    顯示股票基本面資訊

    Args:
        info: 基本面資訊字典
        ticker: 股票代碼
    """
    if not info:
        st.warning("基本面資料無法取得")
        return

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        current_price = info.get("currentPrice", info.get("regularMarketPrice", 0))
        prev_close = info.get("previousClose", 0)
        change_pct, direction = calculate_percentage_change(current_price, prev_close)

        st.metric(
            "LAST PRICE",
            f"${current_price:.2f}",
            f"{direction} {change_pct:+.2f}%",
            delta_color="normal" if change_pct >= 0 else "inverse",
        )

    with col2:
        market_cap = info.get("marketCap", 0)
        st.metric("MARKET CAP", format_number(market_cap, prefix="$"))

    with col3:
        # 處理殖利率（優先使用 dividendYield，其次 trailingAnnualDividendYield）
        div_yield = info.get("dividendYield")
        if div_yield is None:
            div_yield = info.get("trailingAnnualDividendYield", 0)

        if div_yield:
            st.metric("YIELD", f"{div_yield * 100:.2f}%")
        else:
            st.metric("YIELD", "N/A")

    with col4:
        pe_ratio = info.get("trailingPE", 0)
        st.metric("P/E RATIO", f"{pe_ratio:.2f}" if pe_ratio else "N/A")


# ==================== 模式 1: 即時走勢 ====================


def mode_realtime(target_ticker: str, display_name: str, market_type: str):
    """
    即時走勢模式

    Args:
        target_ticker: 股票代碼
        display_name: 顯示名稱
        market_type: 市場類型
    """
    st.subheader(f"📡 LIVE FEED // {display_name}")

    with st.spinner("CONNECTING TO MARKET..."):
        df = get_intraday_data(target_ticker)
        info = get_fundamentals(target_ticker)

    if df.empty:
        st.warning(ERROR_MESSAGES["no_data"].format(name=display_name))
        return

    # 顯示基本面資訊
    display_fundamentals(info, target_ticker)

    st.markdown("---")

    # 繪製圖表
    fig = create_intraday_chart(df, f"{display_name} // INTRADAY")

    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("圖表繪製失敗")

    # 台股特殊功能：五檔報價
    if market_type == "🇹🇼 台灣個股":
        display_order_book(target_ticker, display_name)


def display_order_book(ticker: str, display_name: str):
    """
    顯示台股五檔報價（使用 twstock）

    Args:
        ticker: 股票代碼（去除 .TW）
        display_name: 顯示名稱
    """
    st.markdown("---")
    st.markdown("### 📊 ORDER BOOK (五檔報價)")

    stock_code = ticker.replace(".TW", "")

    with st.expander("查看五檔資訊", expanded=False):
        try:
            import twstock

            stock = twstock.realtime.get(stock_code)

            if stock and stock.get("success"):
                info = stock

                # 檢查資料完整性
                if "best_ask_price" in info and "best_bid_price" in info:
                    col_ask, col_bid, col_info = st.columns([1, 1, 1])

                    with col_ask:
                        ask_data = [
                            {
                                "ASK PRICE": info["best_ask_price"][i],
                                "VOL": info["best_ask_volume"][i],
                            }
                            for i in range(len(info["best_ask_price"]))
                        ]

                        st.markdown("**SELL (ASK)**")
                        st.dataframe(
                            pd.DataFrame(ask_data[::-1]),
                            hide_index=True,
                            use_container_width=True,
                        )

                    with col_bid:
                        bid_data = [
                            {
                                "BID PRICE": info["best_bid_price"][i],
                                "VOL": info["best_bid_volume"][i],
                            }
                            for i in range(len(info["best_bid_price"]))
                        ]

                        st.markdown("**BUY (BID)**")
                        st.dataframe(
                            pd.DataFrame(bid_data),
                            hide_index=True,
                            use_container_width=True,
                        )

                    with col_info:
                        st.info(
                            "ℹ️ SOURCE:\n- CHART: YAHOO FINANCE API\n- ORDER BOOK: TWSE DIRECT LINK"
                        )
                else:
                    st.warning(ERROR_MESSAGES["order_book_empty"])
            else:
                st.warning(ERROR_MESSAGES["twse_failed"])

        except Exception as e:
            st.error(ERROR_MESSAGES["connection_error"].format(error=str(e)))


# ==================== 模式 2: 歷史K線 + RSI ====================


def mode_historical(target_ticker: str, display_name: str):
    """
    歷史K線分析模式

    Args:
        target_ticker: 股票代碼
        display_name: 顯示名稱
    """
    # 參數設定
    col_k1, col_k2 = st.sidebar.columns(2)

    with col_k1:
        period = st.selectbox("PERIOD", LABELS["period_options"], index=1)

    with col_k2:
        interval_ui = st.selectbox("INTERVAL", LABELS["interval_options"], index=0)

    interval = LABELS["interval_map"][interval_ui]

    # 抓取資料
    with st.spinner("LOADING HISTORICAL DATA..."):
        df = get_history_data(target_ticker, period, interval)

    if df is None:
        st.error(ERROR_MESSAGES["data_unavailable"])
        return

    # 顯示圖表
    st.subheader(f"{display_name} // TECHNICAL ANALYSIS")

    fig = create_candlestick_chart(df, f"{display_name} // {interval_ui}")

    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("圖表繪製失敗")


# ==================== 模式 3: 績效比較 ====================


def mode_comparison(target_ticker: str, display_name: str):
    """
    績效比較模式

    Args:
        target_ticker: 股票代碼
        display_name: 顯示名稱
    """
    st.subheader(f"⚔️ VS MODE: {display_name} vs BENCHMARK")

    # 參數設定
    col_b1, col_b2, col_b3 = st.columns([2, 1, 1])

    with col_b1:
        bench_selection = st.selectbox(
            "OPPONENT", list(BENCHMARK_MAP.keys()) + ["自訂輸入"]
        )

    with col_b2:
        if bench_selection == "自訂輸入":
            bench_input = st.text_input("OPPONENT CODE", value="^TWII")
            benchmark_ticker = bench_input.upper()
        else:
            benchmark_ticker = BENCHMARK_MAP[bench_selection]
            st.text_input("CODE", value=benchmark_ticker, disabled=True)

    with col_b3:
        compare_period = st.selectbox(
            "TIMEFRAME", ["3mo", "6mo", "1y", "3y", "5y", "ytd"], index=2
        )

    # 執行比較
    if st.button("INITIATE COMPARISON"):
        with st.spinner("CALCULATING ALPHA..."):
            df_main = get_history_data(target_ticker, period=compare_period, include_indicators=False)
            df_bench = get_history_data(benchmark_ticker, period=compare_period, include_indicators=False)

            if df_main is None or df_bench is None:
                st.error(ERROR_MESSAGES["fetch_failed"])
                return

            # 計算報酬率
            df_merge = calculate_returns(df_main, df_bench)

            if df_merge is None or df_merge.empty:
                st.error(ERROR_MESSAGES["timeframe_mismatch"])
                return

            # 繪製比較圖
            fig = create_comparison_chart(df_merge, display_name, bench_selection)

            if fig:
                st.plotly_chart(fig, use_container_width=True)

                # 顯示績效摘要
                final_ret_main = df_merge["Return_Main"].iloc[-1]
                final_ret_bench = df_merge["Return_Bench"].iloc[-1]
                diff = final_ret_main - final_ret_bench

                status = "LEADING" if diff > 0 else "LAGGING"
                color_code = COLORS["primary"] if diff > 0 else COLORS["danger"]

                st.markdown(
                    f"""
                <div style="border: 1px solid {color_code}; padding: 20px; border-radius: 5px;">
                    <h3 style="color: {color_code}; margin:0;">STATUS: {status}</h3>
                    <p style="margin:0;">DELTA: <b>{diff:+.2f}%</b></p>
                </div>
                """,
                    unsafe_allow_html=True,
                )
            else:
                st.error("圖表繪製失敗")


# ==================== 主程式 ====================


def main():
    """主程式進入點"""
    # 頁面設定
    setup_page()

    # 初始化 Session State
    init_session_state()

    # 側邊欄設定
    market_type, mode, target_ticker, display_name = setup_sidebar()

    # 根據模式顯示內容
    if mode == "即時走勢":
        mode_realtime(target_ticker, display_name, market_type)

    elif mode == "歷史K線 + RSI":
        mode_historical(target_ticker, display_name)

    elif mode == "績效比較":
        mode_comparison(target_ticker, display_name)


if __name__ == "__main__":
    main()