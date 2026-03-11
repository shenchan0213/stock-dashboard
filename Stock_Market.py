"""
數據面板 SHEN XIV TACTICAL
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import base64
import time
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
)


# ==================== 1. 頁面設定 ====================

def setup_page():
    st.set_page_config(page_title="SHEN XIV - TACTICAL", layout="wide")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ==================== 2. 水平跑馬燈 ====================

def _sparkline_svg(prices: list, is_up: bool) -> str:
    if len(prices) < 2:
        return ""
    W, H = 80, 32
    mn, mx = min(prices), max(prices)
    rng = mx - mn if mx != mn else 1
    pts = []
    for i, p in enumerate(prices):
        x = i / (len(prices) - 1) * W
        y = H - ((p - mn) / rng) * (H - 4) - 2
        pts.append(f"{x:.1f},{y:.1f}")
    color      = "#ff3b30" if is_up else "#34c759"
    poly       = " ".join(pts)
    fill_pts   = f"0,{H} " + poly + f" {W},{H}"
    fill_color = "rgba(255,59,48,0.25)" if is_up else "rgba(52,199,89,0.25)"
    return (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">'
        f'<polygon points="{fill_pts}" fill="{fill_color}"/>'
        f'<polyline points="{poly}" fill="none" stroke="{color}" '
        f'stroke-width="2" stroke-linejoin="round"/>'
        f'</svg>'
    )


def render_ticker_tape():
    """
    iOS / Yahoo Finance 風格水平跑馬燈
    - get_watchlist_batch 回傳 {sym: {"price": x, "change_pct": y}} (FMP 格式)
    - sparkline 用 get_history_data 的收盤價繪製
    - components.html() 避免 Streamlit sanitizer 截斷
    """
    watchlist = st.session_state.get("watchlist", [])
    if not watchlist:
        return

    tickers   = tuple(t for t, _ in watchlist)
    label_map = {t: l for t, l in watchlist}
    batch     = get_watchlist_batch(tickers)   # FMP 批次報價

    items_html = []
    for ticker, label in watchlist:
        try:
            info    = batch.get(ticker, {})
            current = info.get("price", 0) or 0
            chg_pct = info.get("change_pct", 0) or 0
            if current == 0:
                continue

            is_up  = chg_pct >= 0
            color  = "#ff3b30" if is_up else "#34c759"
            arrow  = "▲" if is_up else "▼"
            bg     = "rgba(255,59,48,0.12)" if is_up else "rgba(52,199,89,0.12)"

            if current >= 10000:
                price_str = f"{current:,.0f}"
            elif current >= 100:
                price_str = f"{current:,.2f}"
            else:
                price_str = f"{current:.4f}"

            # Sparkline：另外抓歷史收盤（已快取，不會重複請求）
            svg_uri = ""
            try:
                df_hist = get_history_data(ticker, period="1mo", include_indicators=False)
                if df_hist is not None and not df_hist.empty:
                    closes  = df_hist["Close"].dropna().tolist()
                    svg     = _sparkline_svg(closes[-20:], is_up)
                    svg_b64 = base64.b64encode(svg.encode()).decode()
                    svg_uri = f"data:image/svg+xml;base64,{svg_b64}"
            except Exception:
                pass

            spark_tag = f'<img src="{svg_uri}" width="80" height="32" style="vertical-align:middle;"/>' if svg_uri else ""

            items_html.append(f"""
            <div style="display:inline-flex;align-items:center;gap:10px;
                        padding:5px 16px 5px 12px;margin:0 6px;
                        background:{bg};border-radius:10px;
                        border:1px solid {color}44;white-space:nowrap;">
              <div>
                <div style="font-size:0.7rem;color:#888;line-height:1.1;">{label}</div>
                <div style="font-size:1rem;font-weight:700;color:#fff;line-height:1.4;">{price_str}</div>
              </div>
              {spark_tag}
              <div style="font-size:0.85rem;font-weight:700;color:{color};">
                {arrow} {abs(chg_pct):.2f}%
              </div>
            </div>""")
        except Exception:
            continue

    if not items_html:
        return

    content = "".join(items_html)
    html = f"""<!DOCTYPE html><html><head><style>
      body{{margin:0;padding:0;background:#000;overflow:hidden;}}
      .wrap{{width:100%;overflow:hidden;background:#000;
             border-bottom:1px solid #1e1e1e;padding:7px 0;}}
      .track{{display:inline-flex;width:max-content;
              animation:scroll 55s linear infinite;}}
      .track:hover{{animation-play-state:paused;cursor:default;}}
      @keyframes scroll{{0%{{transform:translateX(0);}}100%{{transform:translateX(-50%);}}}}
    </style></head><body>
      <div class="wrap"><div class="track">{content}{content}</div></div>
    </body></html>"""
    components.html(html, height=60, scrolling=False)


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

    # 自動刷新
    auto_refresh = False
    if mode == "即時走勢":
        st.sidebar.markdown("---")
        auto_refresh = st.sidebar.toggle("⟳ 自動刷新 (60s)", value=False)

    # 自訂跑馬燈
    st.sidebar.markdown("---")
    with st.sidebar.expander("⚙️ 自訂跑馬燈標的", expanded=False):
        current_list = st.session_state.get("watchlist", [])
        st.caption("目前：" + "、".join(l for _, l in current_list))
        new_ticker = st.text_input("新增代號 (如 MSFT)", key="add_ticker").upper().strip()
        new_label  = st.text_input("顯示名稱 (如 微軟)", key="add_label").strip()
        if st.button("➕ 新增", key="btn_add"):
            if new_ticker and new_label and new_ticker not in [t for t, _ in current_list]:
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
    pe       = info.get("trailingPE", 0) or 0
    eps      = info.get("trailingEps", 0) or 0

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
    r2c2.metric("本益比 P/E",   f"{pe:.2f}" if pe else "—")
    r2c3.metric("EPS",          f"{eps:.2f}" if eps else "—")
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
    """財務健康面板（5 指標 + 產業別評分 + 分項進度條）"""
    data   = health_data["data"]
    score  = health_data.get("health_score", 0)
    sector = health_data.get("sector", "—")
    scores = health_data.get("_scores", {})

    color = (
        "#00ff41" if score >= 85 else
        "#00ccff" if score >= 72 else
        "#ffbf00" if score >= 58 else
        "#ff6600" if score >= 40 else
        "#ff0055"
    )

    # 主視覺
    st.markdown(f"""
    <div style="text-align:center;padding:20px 20px 16px;background:#111;
                border-radius:12px;border:2px solid {color};margin-bottom:14px;">
      <p style="margin:0;color:#555;font-size:0.75rem;letter-spacing:3px;">
        HEALTH SCORE &nbsp;|&nbsp; {sector.upper()}
      </p>
      <h1 style="margin:8px 0 0;font-size:3.8rem;color:{color};line-height:1;">{score}</h1>
      <p style="margin:4px 0 0;color:#444;font-size:0.8rem;">/ 100</p>
    </div>
    """, unsafe_allow_html=True)
    st.progress(int(score) / 100)
    st.info(f"💡 **洞察**：{health_data.get('insight', '')}")

    # ── 分項進度條（這是原本 pass 的地方，現在補完整）──
    if scores:
        st.markdown("##### 分項評分")
        score_items = [
            ("PE 估值（產業調整）", scores.get("pe",     50), health_data["pe_status"]),
            ("ROE 股東權益報酬",    scores.get("roe",    50), health_data["roe_status"]),
            ("淨利率（產業調整）",  scores.get("margin", 50), health_data["margin_status"]),
            ("負債結構",            scores.get("debt",   50), health_data["debt_status"]),
            ("營收成長率",          scores.get("growth", 50), health_data["growth_status"]),
        ]
        for label, s, status in score_items:
            bar_color = "#00ff41" if s >= 75 else "#ffbf00" if s >= 50 else "#ff0055"
            st.markdown(f"""
            <div style="margin-bottom:10px;">
              <div style="display:flex;justify-content:space-between;
                          font-size:0.8rem;color:#aaa;margin-bottom:3px;">
                <span>{label}</span>
                <span style="color:{bar_color};">{status} &nbsp;&nbsp; {s} / 100</span>
              </div>
              <div style="background:#1e1e1e;border-radius:4px;height:7px;">
                <div style="width:{s}%;background:{bar_color};border-radius:4px;height:7px;"></div>
              </div>
            </div>
            """, unsafe_allow_html=True)

    # 關鍵數據 grid
    st.markdown("##### 關鍵數據")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("本益比 P/E",     f"{data.get('PE') or 0:.1f}",           health_data["pe_status"],     delta_color="off")
        st.metric("負債權益比 D/E", f"{data.get('D/E Ratio') or 0:.2f}",    health_data["debt_status"],   delta_color="off")
    with c2:
        st.metric("ROE",            f"{data.get('ROE') or 0:.1f}%",          health_data["roe_status"],    delta_color="off")
        cr = data.get("Current Ratio") or 0
        st.metric("流動比率",       f"{cr:.2f}" if cr else "—",              "流動性")
    with c3:
        st.metric("淨利率",         f"{data.get('Profit Margin') or 0:.1f}%", health_data["margin_status"], delta_color="off")
        gr = data.get("Revenue Growth") or 0
        st.metric("營收成長率",     f"{gr:.1f}%",                            health_data["growth_status"], delta_color="off")

    with st.expander("📋 完整指標明細", expanded=False):
        gm = data.get("Gross Margin")
        st.json({
            "Sector":         health_data.get("sector"),
            "PE (TTM)":       data.get("PE"),
            "Forward PE":     data.get("Forward PE"),
            "PEG Ratio":      data.get("PEG"),
            "Gross Margin %": f"{gm:.1f}" if gm else None,
            "Beta":           data.get("Beta"),
        })


# ==================== 5. 模式邏輯 ====================

def mode_realtime(target_ticker: str, display_name: str,
                  market_type: str, auto_refresh: bool):
    st.subheader(f"📡 LIVE FEED // {display_name}")

    if auto_refresh:
        st.info("⟳ 自動刷新已啟用，每 60 秒更新一次")
        time.sleep(60)
        st.rerun()

    with st.spinner("CONNECTING TO MARKET..."):
        df   = get_intraday_data(target_ticker)
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
        period      = st.sidebar.selectbox("PERIOD",   LABELS["period_options"],   index=1)
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

    # MACD 面板
    if "MACD" in df.columns:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        hist     = df["MACD"] - df["Signal"]
        fig_macd = make_subplots(rows=1, cols=1)
        fig_macd.add_trace(go.Scatter(x=df["Date"], y=df["MACD"],
            line=dict(color="#00ccff", width=1.5), name="MACD"))
        fig_macd.add_trace(go.Scatter(x=df["Date"], y=df["Signal"],
            line=dict(color="#ffbf00", width=1.5, dash="dot"), name="Signal"))
        fig_macd.add_trace(go.Bar(x=df["Date"], y=hist,
            marker_color=["#00ff41" if v >= 0 else "#ff0055" for v in hist],
            name="Histogram"))
        fig_macd.update_layout(
            height=180, margin=dict(l=10, r=10, t=25, b=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#aaa"), title="MACD", showlegend=True,
            hovermode="x unified", yaxis=dict(gridcolor="#333"))
        st.plotly_chart(fig_macd, use_container_width=True)

    # 財務健康
    st.markdown("---")
    st.subheader("🧠 STRATEGIC INTELLIGENCE // Financial Health")
    with st.spinner("ANALYZING FUNDAMENTALS..."):
        health_data = get_financial_health(target_ticker)
    if health_data:
        _display_health_panel(health_data)
    else:
        st.warning("⚠️ 無法獲取財務基本面數據（指數或期貨商品無此資料）")


def mode_comparison(target_ticker: str, display_name: str):
    st.subheader(f"⚔️ VS MODE: {display_name} vs BENCHMARK")

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        bench_sel = st.selectbox("OPPONENT", list(BENCHMARK_MAP.keys()) + ["自訂輸入"])
    with c2:
        if bench_sel == "自訂輸入":
            bench_input      = st.text_input("OPPONENT CODE", value="^TWII")
            benchmark_ticker = bench_input.upper()
        else:
            benchmark_ticker = BENCHMARK_MAP[bench_sel]
            st.text_input("CODE", value=benchmark_ticker, disabled=True)
    with c3:
        compare_period = st.selectbox("TIMEFRAME", ["3mo", "6mo", "1y", "3y"], index=2)

    if st.button("⚔️ INITIATE COMPARISON"):
        with st.spinner("CALCULATING ALPHA..."):
            df_main  = get_history_data(target_ticker,    period=compare_period, include_indicators=False)
            df_bench = get_history_data(benchmark_ticker, period=compare_period, include_indicators=False)

            if df_main is not None and df_bench is not None:
                df_merge = calculate_returns(df_main, df_bench)
                if df_merge is not None:
                    final_main  = df_merge["Return_Main"].iloc[-1]
                    final_bench = df_merge["Return_Bench"].iloc[-1]
                    alpha       = final_main - final_bench

                    m1, m2, m3 = st.columns(3)
                    m1.metric(display_name,    f"{final_main:.2f}%")
                    m2.metric(bench_sel,       f"{final_bench:.2f}%")
                    m3.metric("Alpha 超額報酬", f"{alpha:.2f}%",
                              delta=f"{alpha:+.2f}%",
                              delta_color="normal" if alpha >= 0 else "inverse")

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
    render_ticker_tape()

    market_type, mode, target_ticker, display_name, auto_refresh = setup_sidebar()

    if mode == "即時走勢":
        mode_realtime(target_ticker, display_name, market_type, auto_refresh)
    elif mode == "歷史K線 + RSI":
        mode_historical(target_ticker, display_name)
    elif mode == "績效比較":
        mode_comparison(target_ticker, display_name)


if __name__ == "__main__":
    main()