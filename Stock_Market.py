"""
數據面板 SHEN XIV TACTICAL
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import base64
from analysis import get_financial_health

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


# ==================== 1. 頁面基礎設定 ====================

def setup_page():
    st.set_page_config(page_title="SHEN XIV - TACTICAL", layout="wide")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ==================== 2. 跑馬燈（修正版）====================

def _sparkline_svg(prices: list, is_up: bool) -> str:
    """產生純 SVG 迷你走勢圖"""
    if len(prices) < 2:
        return ""
    W, H = 80, 32
    mn, mx = min(prices), max(prices)
    rng = mx - mn if mx != mn else 1
    pts = []
    for i, p in enumerate(prices):
        x = i / (len(prices) - 1) * W
        y = H - ((p - mn) / rng) * (H - 2) - 1
        pts.append(f"{x:.1f},{y:.1f}")
    color = "#ff3b30" if is_up else "#34c759"
    poly  = " ".join(pts)
    fill_pts = f"0,{H} " + poly + f" {W},{H}"
    fill_color = "rgba(255,59,48,0.25)" if is_up else "rgba(52,199,89,0.25)"
    return (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">'
        f'<polygon points="{fill_pts}" fill="{fill_color}"/>'
        f'<polyline points="{poly}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round"/>'
        f'</svg>'
    )


def render_ticker_tape():
    """
    Yahoo Finance iOS 風格水平跑馬燈
    ▲ 紅漲 ▼ 綠跌（台灣慣例）
    使用 components.html() 避免 Streamlit markdown sanitizer 截斷 HTML
    """
    watchlist = [
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

    items_html = []
    for ticker, label in watchlist:
        try:
            df = get_history_data(ticker, period="5d", include_indicators=False)
            if df is None or df.empty or len(df) < 2:
                continue
            closes   = df["Close"].dropna().tolist()
            current  = closes[-1]
            prev     = closes[-2]
            chg_pct  = (current - prev) / prev * 100
            is_up    = chg_pct >= 0

            color = "#ff3b30" if is_up else "#34c759"
            arrow = "▲" if is_up else "▼"
            bg    = "rgba(255,59,48,0.12)" if is_up else "rgba(52,199,89,0.12)"

            # 格式化價格
            if current >= 10000:
                price_str = f"{current:,.0f}"
            elif current >= 100:
                price_str = f"{current:,.2f}"
            else:
                price_str = f"{current:.4f}"

            # SVG → base64 data URI（components.html 可正常顯示）
            svg     = _sparkline_svg(closes[-30:], is_up)
            svg_b64 = base64.b64encode(svg.encode()).decode()
            svg_uri = f"data:image/svg+xml;base64,{svg_b64}"

            items_html.append(f"""
            <div style="
                display:inline-flex;align-items:center;gap:10px;
                padding:5px 16px 5px 12px;margin:0 6px;
                background:{bg};border-radius:10px;
                border:1px solid {color}44;white-space:nowrap;">
              <div>
                <div style="font-size:0.7rem;color:#888;line-height:1.1;">{label}</div>
                <div style="font-size:1rem;font-weight:700;color:#fff;line-height:1.4;">{price_str}</div>
              </div>
              <img src="{svg_uri}" width="80" height="32" style="vertical-align:middle;"/>
              <div style="font-size:0.85rem;font-weight:700;color:{color};">
                {arrow} {abs(chg_pct):.2f}%
              </div>
            </div>""")
        except Exception:
            continue

    if not items_html:
        return

    content = "".join(items_html)
    # ▼ 關鍵：用 components.html() 渲染，完整支援 HTML/CSS，無 sanitize 問題
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
      body {{ margin:0; padding:0; background:#000; overflow:hidden; }}
      .wrap {{
        width:100%; overflow:hidden;
        background:#000;
        border-bottom:1px solid #1e1e1e;
        padding:7px 0;
      }}
      .track {{
        display:inline-flex;
        width:max-content;
        animation: scroll 55s linear infinite;
      }}
      .track:hover {{ animation-play-state:paused; cursor:default; }}
      @keyframes scroll {{
        0%   {{ transform: translateX(0); }}
        100% {{ transform: translateX(-50%); }}
      }}
    </style>
    </head>
    <body>
      <div class="wrap">
        <div class="track">
          {content}{content}
        </div>
      </div>
    </body>
    </html>
    """
    # height=60 讓跑馬燈只佔一行高度
    components.html(html, height=60, scrolling=False)


# ==================== 3. 側邊欄設定 ====================

def setup_sidebar() -> tuple[str, str, str, str]:
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
        futures_selection = st.sidebar.selectbox("SELECT FUTURES", list(FUTURES_MAP.keys()))
        target_ticker     = FUTURES_MAP[futures_selection]
        display_name      = futures_selection

    return market_type, mode, target_ticker, display_name


# ==================== 4. 核心功能模組 ====================

def display_fundamentals(info: dict, ticker: str):
    """高密度資訊面板"""
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
    pe       = info.get("trailingPE", 0) or 0
    eps      = info.get("trailingEps", 0) or 0

    change_pct, _ = calculate_percentage_change(current, previous)
    color = "normal" if change_pct >= 0 else "inverse"

    c1, c2 = st.columns([2, 4])
    with c1:
        st.metric(
            label="CURRENT PRICE",
            value=f"{current:,.2f}",
            delta=f"{change_pct:.2f}%",
            delta_color=color
        )

    st.markdown("###### MARKET DATA")
    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    r2c1, r2c2, r2c3, r2c4 = st.columns(4)

    r1c1.metric("開盤 (Open)",    f"{open_p:,.2f}")
    r1c2.metric("最高 (High)",    f"{day_high:,.2f}")
    r1c3.metric("最低 (Low)",     f"{day_low:,.2f}")
    r1c4.metric("市值 (Mkt Cap)", format_number(mkt_cap))

    r2c1.metric("成交量 (Vol)",   format_number(volume))
    r2c2.metric("本益比 (P/E)",   f"{pe:.2f}" if pe else "-")
    r2c3.metric("EPS",            f"{eps:.2f}" if eps else "-")
    r2c4.metric("昨收 (Prev)",    f"{previous:,.2f}")

    st.markdown("---")


def display_order_book(ticker: str, display_name: str):
    """台股五檔報價"""
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


def _display_health_panel(health_data: dict):
    """
    財務健康面板（共用，只呼叫一次）
    ⚠️ ROE 與 Profit Margin 在 analysis.py 的 _evaluate_metrics 中已乘以 100
    → 這裡直接顯示，不要再 *100
    """
    data  = health_data["data"]
    score = health_data.get("health_score", 0)
    color = (
        "#00ff41" if score >= 80 else
        "#00ccff" if score >= 65 else
        "#ffbf00" if score >= 50 else
        "#ff0055"
    )

    st.markdown(f"""
    <div style="text-align:center;padding:20px;background:#1a1a1a;
                border-radius:10px;border:2px solid {color};margin-bottom:12px;">
        <p style="margin:0;color:#aaa;font-size:0.85rem;letter-spacing:3px;">HEALTH SCORE</p>
        <h1 style="margin:6px 0 0;font-size:3.5rem;color:{color};">{score}</h1>
        <p style="margin:0;color:#555;">/ 100</p>
    </div>
    """, unsafe_allow_html=True)
    st.progress(int(score) / 100)
    st.info(f"💡 **洞察**：{health_data['insight']}")

    c1, c2, c3 = st.columns(3)
    with c1:
        pe_val = data.get("PE") or 0
        st.metric("本益比 (P/E)", f"{pe_val:.2f}", health_data["pe_status"], delta_color="inverse")
    with c2:
        roe_val = data.get("ROE") or 0          # ← 已是 % 值，不再 *100
        st.metric("ROE (權益報酬率)", f"{roe_val:.1f}%", health_data["roe_status"])
    with c3:
        pm_val = data.get("Profit Margin") or 0  # ← 已是 % 值，不再 *100
        st.metric("淨利率 (Net Margin)", f"{pm_val:.1f}%", health_data["margin_status"])

    with st.expander("📋 完整指標明細", expanded=False):
        st.json({
            "Forward PE": data.get("Forward PE"),
            "PEG Ratio":  data.get("PEG"),
            "Beta":       data.get("Beta"),
        })


# ==================== 5. 模式邏輯 ====================

def mode_realtime(target_ticker: str, display_name: str, market_type: str):
    """即時走勢模式"""
    st.subheader(f"📡 LIVE FEED // {display_name}")

    with st.spinner("CONNECTING TO MARKET..."):
        df   = get_intraday_data(target_ticker)
        info = get_fundamentals(target_ticker)

    if df.empty:
        st.warning(ERROR_MESSAGES["no_data"].format(name=display_name))
        return

    display_fundamentals(info, target_ticker)

    fig = create_intraday_chart(df, f"{display_name} // INTRADAY")
    if fig:
        st.plotly_chart(fig, use_container_width=True)

    if market_type == "🇹🇼 台灣個股":
        display_order_book(target_ticker, display_name)


def mode_historical(target_ticker: str, display_name: str):
    """歷史K線 + 財務健康分析"""
    # ▼ 選項放在側邊欄（修正：原本用 st.selectbox 跑到主畫面）
    col_k1, col_k2 = st.sidebar.columns(2)
    with col_k1:
        period = st.sidebar.selectbox("PERIOD", LABELS["period_options"], index=1)
    with col_k2:
        interval_ui = st.sidebar.selectbox("INTERVAL", LABELS["interval_options"], index=0)
    interval = LABELS["interval_map"][interval_ui]

    with st.spinner("LOADING HISTORICAL DATA..."):
        df = get_history_data(target_ticker, period, interval)

    if df is None:
        st.error(ERROR_MESSAGES["data_unavailable"])
        return

    st.subheader(f"📊 {display_name} // TECHNICAL ANALYSIS")
    fig = create_candlestick_chart(df, f"{display_name} // {interval_ui}")
    if fig:
        st.plotly_chart(fig, use_container_width=True)

    # ▼ 財務健康面板（只呼叫一次，修正原本重複顯示的 bug）
    st.markdown("---")
    st.subheader("🧠 STRATEGIC INTELLIGENCE // Financial Health")
    with st.spinner("ANALYZING FUNDAMENTALS..."):
        health_data = get_financial_health(target_ticker)

    if health_data:
        _display_health_panel(health_data)
    else:
        st.warning("⚠️ 無法獲取財務基本面數據（指數或期貨商品無基本面）")


def mode_comparison(target_ticker: str, display_name: str):
    """績效比較模式"""
    st.subheader(f"⚔️ VS MODE: {display_name} vs BENCHMARK")

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        bench_selection = st.selectbox("OPPONENT", list(BENCHMARK_MAP.keys()) + ["自訂輸入"])
    with c2:
        if bench_selection == "自訂輸入":
            bench_input      = st.text_input("OPPONENT CODE", value="^TWII")
            benchmark_ticker = bench_input.upper()
        else:
            benchmark_ticker = BENCHMARK_MAP[bench_selection]
            st.text_input("CODE", value=benchmark_ticker, disabled=True)
    with c3:
        compare_period = st.selectbox("TIMEFRAME", ["3mo", "6mo", "1y", "3y"], index=2)

    if st.button("INITIATE COMPARISON"):
        with st.spinner("CALCULATING ALPHA..."):
            df_main  = get_history_data(target_ticker,    period=compare_period, include_indicators=False)
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


# ==================== 6. 主程式入口 ====================

def main():
    setup_page()
    render_ticker_tape()        # components.html() → 不被 Streamlit sanitizer 截斷
    init_session_state()
    market_type, mode, target_ticker, display_name = setup_sidebar()

    if mode == "即時走勢":
        mode_realtime(target_ticker, display_name, market_type)
    elif mode == "歷史K線 + RSI":
        mode_historical(target_ticker, display_name)
    elif mode == "績效比較":
        mode_comparison(target_ticker, display_name)


if __name__ == "__main__":
    main()