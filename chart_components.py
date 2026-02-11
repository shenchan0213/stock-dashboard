"""
chart_components.py
負責 Plotly 圖表的繪製邏輯 (Optimized)
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import pytz
from typing import Optional
from config import COLORS

def _apply_common_layout(fig, height=500):
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor=COLORS["bg_transparent"],
        plot_bgcolor=COLORS["bg_transparent"],
        font=dict(family="Roboto Mono, monospace", color="#aaa"),
        xaxis_rangeslider_visible=False,
        showlegend=False,
        hovermode="x unified" # 統一顯示 Hover 資訊，提升閱讀體驗
    )
    return fig

def create_intraday_chart(df: pd.DataFrame, title: str) -> Optional[go.Figure]:
    if df.empty: return None
    
    df = df.copy()
    
    # 時區處理優化：不依賴 title 字串判斷，避免誤判
    # yfinance intraday 通常帶有時區，若無則假設為 UTC
    if pd.api.types.is_datetime64_any_dtype(df.index):
        if df.index.tz is not None:
             # 如果原始資料有時區，轉換為台北時間顯示 (User Experience)
            tw_tz = pytz.timezone("Asia/Taipei")
            df["Datetime"] = df.index.tz_convert(tw_tz).tz_localize(None)
        else:
            df["Datetime"] = df.index
    else:
        df["Datetime"] = pd.to_datetime(df.index)

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.03, row_heights=[0.75, 0.25]
    )

    # 1. 價格線 (Area Chart 風格)
    fig.add_trace(go.Scatter(
        x=df["Datetime"], y=df["Close"],
        mode="lines", name="PRICE",
        line=dict(color=COLORS["primary"], width=2),
        fill='tozeroy',
        fillcolor=COLORS["fill_green"]
    ), row=1, col=1)

    # 2. 均價線 (Intraday VWAP 概念，這裡簡化為 MA)
    # 增加檢查，避免資料不足時報錯
    if len(df) > 30:
        df["Average"] = df["Close"].rolling(window=30).mean()
        fig.add_trace(go.Scatter(
            x=df["Datetime"], y=df["Average"],
            mode="lines", name="AVG (30m)",
            line=dict(color=COLORS["warning"], width=1, dash="dot"),
        ), row=1, col=1)

    # 3. 成交量
    colors = [COLORS["danger"] if c < o else COLORS["primary"] for o, c in zip(df["Open"], df["Close"])]
    fig.add_trace(go.Bar(
        x=df["Datetime"], y=df["Volume"],
        name="VOL", marker_color=colors
    ), row=2, col=1)

    fig.update_layout(title=dict(text=f"<b>{title}</b>", font=dict(size=18, color=COLORS["text"])))
    fig = _apply_common_layout(fig)
    
    # 讓 Y 軸自動適應數據範圍，避免被極端值拉平
    fig.update_yaxes(autorange=True, fixedrange=False, row=1, col=1, gridcolor=COLORS["grid"])
    fig.update_xaxes(showgrid=False, row=1, col=1)
    # 分鐘圖顯示小時:分鐘
    fig.update_xaxes(showgrid=False, tickformat="%H:%M", row=2, col=1)
    
    return fig

def create_candlestick_chart(df: pd.DataFrame, title: str) -> Optional[go.Figure]:
    # 確保資料足夠
    if df.empty: return None

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.03, row_heights=[0.7, 0.3]
    )

    # K線
    fig.add_trace(go.Candlestick(
        x=df["Date"], open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name="OHLC",
        increasing_line_color=COLORS["primary"], increasing_fillcolor=COLORS["fill_green"],
        decreasing_line_color=COLORS["danger"], decreasing_fillcolor=COLORS["fill_red"],
    ), row=1, col=1)

    # MA 指標 (存在才畫)
    if "SMA5" in df.columns:
        fig.add_trace(go.Scatter(x=df["Date"], y=df["SMA5"], line=dict(color=COLORS["warning"], width=1), name="5MA"), row=1, col=1)
    if "SMA20" in df.columns:
        fig.add_trace(go.Scatter(x=df["Date"], y=df["SMA20"], line=dict(color=COLORS["info"], width=1), name="20MA"), row=1, col=1)
    
    # 布林通道
    if "BB_Upper" in df.columns:
        fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Upper'], line=dict(color='rgba(150, 150, 150, 0.3)', width=1, dash='dot'), showlegend=False), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Lower'], line=dict(color='rgba(150, 150, 150, 0.3)', width=1, dash='dot'), fill='tonexty', fillcolor='rgba(150, 150, 150, 0.05)', showlegend=False), row=1, col=1)

    # RSI (放在子圖 2)
    if "RSI" in df.columns:
        fig.add_trace(go.Scatter(x=df["Date"], y=df["RSI"], line=dict(color="#bd00ff", width=2), name="RSI"), row=2, col=1)
        # 增加 70/30 參考線
        fig.add_shape(type="line", x0=df["Date"].iloc[0], x1=df["Date"].iloc[-1], y0=70, y1=70, line=dict(color=COLORS["danger"], width=1, dash="dot"), row=2, col=1)
        fig.add_shape(type="line", x0=df["Date"].iloc[0], x1=df["Date"].iloc[-1], y0=30, y1=30, line=dict(color=COLORS["primary"], width=1, dash="dot"), row=2, col=1)

    fig = _apply_common_layout(fig, height=700)
    fig.update_layout(title=dict(text=f"<b>{title}</b>", font=dict(size=18, color=COLORS["text"])))
    fig.update_yaxes(gridcolor=COLORS["grid"], row=1, col=1)
    fig.update_yaxes(range=[0, 100], row=2, col=1) # 固定 RSI 範圍
    
    return fig

def create_comparison_chart(df: pd.DataFrame, name_main: str, name_bench: str) -> Optional[go.Figure]:
    if df.empty: return None

    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df["Date"], y=df["Return_Main"],
        mode="lines", name=name_main,
        line=dict(color=COLORS["primary"], width=3)
    ))
    
    fig.add_trace(go.Scatter(
        x=df["Date"], y=df["Return_Bench"],
        mode="lines", name=name_bench,
        line=dict(color="#666", width=2, dash="dot")
    ))
    
    # 零軸參考線
    fig.add_hline(y=0, line_dash="solid", line_color="#fff", opacity=0.3)
    
    fig = _apply_common_layout(fig)
    fig.update_layout(
        title="<b>PERFORMANCE DELTA (%)</b>",
        yaxis_title="RETURN (%)",
        hovermode="x unified"
    )
    fig.update_yaxes(gridcolor=COLORS["grid"])
    
    return fig