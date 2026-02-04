"""
chart_components.py
負責 Plotly 圖表的繪製邏輯
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
    )
    return fig

def create_intraday_chart(df: pd.DataFrame, title: str) -> Optional[go.Figure]:
    if df.empty: return None
    
    df = df.copy()
    df.reset_index(inplace=True)
    
    # 時區處理 (針對台股)
    if "TW" in title or "台" in title:
        try:
            tw_tz = pytz.timezone("Asia/Taipei")
            df["Datetime"] = df["Datetime"].dt.tz_convert(tw_tz).dt.tz_localize(None)
        except:
            df["Datetime"] = df["Datetime"].dt.tz_localize(None)
    else:
        df["Datetime"] = df["Datetime"].dt.tz_localize(None)

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.03, row_heights=[0.75, 0.25]
    )

    # 價格線
    fig.add_trace(go.Scatter(
        x=df["Datetime"], y=df["Close"],
        mode="lines", name="PRICE",
        line=dict(color=COLORS["primary"], width=2),
        fill='tozeroy',
        fillcolor=COLORS["fill_green"]
    ), row=1, col=1)

    # 均價線
    df["Average"] = df["Close"].rolling(window=30).mean()
    fig.add_trace(go.Scatter(
        x=df["Datetime"], y=df["Average"],
        mode="lines", name="AVG",
        line=dict(color=COLORS["warning"], width=1, dash="dot"),
    ), row=1, col=1)

    # 成交量
    colors = [COLORS["danger"] if c < o else COLORS["primary"] for o, c in zip(df["Open"], df["Close"])]
    fig.add_trace(go.Bar(
        x=df["Datetime"], y=df["Volume"],
        name="VOL", marker_color=colors
    ), row=2, col=1)

    fig.update_layout(title=dict(text=f"<b>{title}</b>", font=dict(size=18, color=COLORS["text"])))
    fig = _apply_common_layout(fig)
    
    fig.update_yaxes(autorange=True, fixedrange=False, row=1, col=1, gridcolor=COLORS["grid"])
    fig.update_xaxes(showgrid=False, row=1, col=1)
    fig.update_xaxes(showgrid=False, tickformat="%H:%M", row=2, col=1)
    
    return fig

def create_candlestick_chart(df: pd.DataFrame, title: str) -> Optional[go.Figure]:
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

    # MA & BB
    fig.add_trace(go.Scatter(x=df["Date"], y=df["SMA5"], line=dict(color=COLORS["warning"], width=1), name="5MA"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["Date"], y=df["SMA20"], line=dict(color=COLORS["info"], width=1), name="20MA"), row=1, col=1)
    
    if "BB_Upper" in df.columns:
        fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Upper'], line=dict(color='rgba(150, 150, 150, 0.3)', width=1, dash='dot')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Lower'], line=dict(color='rgba(150, 150, 150, 0.3)', width=1, dash='dot'), fill='tonexty', fillcolor='rgba(150, 150, 150, 0.05)'), row=1, col=1)

    # RSI
    if "RSI" in df.columns:
        fig.add_trace(go.Scatter(x=df["Date"], y=df["RSI"], line=dict(color="#bd00ff", width=2), name="RSI"), row=2, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color=COLORS["danger"], row=2, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color=COLORS["primary"], row=2, col=1)

    fig = _apply_common_layout(fig, height=700)
    fig.update_yaxes(gridcolor=COLORS["grid"], row=1, col=1)
    
    return fig

def create_comparison_chart(df: pd.DataFrame, name_main: str, name_bench: str) -> Optional[go.Figure]:
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
    
    fig.add_hline(y=0, line_dash="solid", line_color="#fff", opacity=0.2)
    
    fig = _apply_common_layout(fig)
    fig.update_layout(
        title="PERFORMANCE DELTA",
        yaxis_title="RETURN (%)",
        hovermode="x unified"
    )
    fig.update_yaxes(gridcolor=COLORS["grid"])
    
    return fig