"""
chart_components.py
負責 Plotly 圖表的繪製邏輯 (包含動態面積圖與漲跌變色)
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
        hovermode="x unified"
    )
    return fig

def create_intraday_chart(df: pd.DataFrame, title: str) -> Optional[go.Figure]:
    if df.empty: return None
    
    df = df.copy()
    
    # 時區處理
    if pd.api.types.is_datetime64_any_dtype(df.index):
        if df.index.tz is not None:
            tw_tz = pytz.timezone("Asia/Taipei")
            df["Datetime"] = df.index.tz_convert(tw_tz).tz_localize(None)
        else:
            df["Datetime"] = df.index
    else:
        df["Datetime"] = pd.to_datetime(df.index)

    # === 動態漲跌變色與面積圖邏輯 ===
    start_price = df["Close"].iloc[0]
    end_price = df["Close"].iloc[-1]
    
    # 判斷漲跌顏色
    if end_price >= start_price:
        line_color = COLORS["primary"]   # 綠 (漲)
        fill_color = COLORS["fill_green"] # 半透明綠
    else:
        line_color = COLORS["danger"]    # 紅 (跌)
        fill_color = COLORS["fill_red"]   # 半透明紅

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.05, row_heights=[0.8, 0.2]
    )

    # 1. 價格線 (Area Chart) - 關鍵在 fill='tozeroy'
    fig.add_trace(go.Scatter(
        x=df["Datetime"], y=df["Close"],
        mode="lines", 
        name="PRICE",
        line=dict(color=line_color, width=2),
        fill='tozeroy',       # <--- 這裡讓它變成面積圖
        fillcolor=fill_color  # <--- 這裡設定填充顏色
    ), row=1, col=1)

    # 參考線：開盤價
    fig.add_hline(y=start_price, line_dash="dot", line_color="#666", row=1, col=1)

    # 2. 成交量
    colors = [COLORS["danger"] if c < o else COLORS["primary"] for o, c in zip(df["Open"], df["Close"])]
    fig.add_trace(go.Bar(
        x=df["Datetime"], y=df["Volume"],
        name="VOL", marker_color=colors
    ), row=2, col=1)

    fig.update_layout(title=dict(text=f"<b>{title}</b>", font=dict(size=18, color=COLORS["text"])))
    fig = _apply_common_layout(fig)
    
    # Y軸自動縮放優化
    min_val = df["Low"].min()
    max_val = df["High"].max()
    padding = (max_val - min_val) * 0.1 if max_val != min_val else max_val * 0.01
    fig.update_yaxes(range=[min_val - padding, max_val + padding], row=1, col=1, gridcolor=COLORS["grid"])
    fig.update_xaxes(showgrid=False, tickformat="%H:%M", row=2, col=1)
    
    return fig

def create_candlestick_chart(df: pd.DataFrame, title: str) -> Optional[go.Figure]:
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

    # MA 指標
    if "SMA5" in df.columns:
        fig.add_trace(go.Scatter(x=df["Date"], y=df["SMA5"], line=dict(color=COLORS["warning"], width=1), name="5MA"), row=1, col=1)
    if "SMA20" in df.columns:
        fig.add_trace(go.Scatter(x=df["Date"], y=df["SMA20"], line=dict(color=COLORS["info"], width=1), name="20MA"), row=1, col=1)
    
    # 布林通道
    if "BB_Upper" in df.columns:
        fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Upper'], line=dict(color='rgba(150, 150, 150, 0.3)', width=1, dash='dot'), showlegend=False), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Lower'], line=dict(color='rgba(150, 150, 150, 0.3)', width=1, dash='dot'), fill='tonexty', fillcolor='rgba(150, 150, 150, 0.05)', showlegend=False), row=1, col=1)

    # RSI
    if "RSI" in df.columns:
        fig.add_trace(go.Scatter(x=df["Date"], y=df["RSI"], line=dict(color="#bd00ff", width=2), name="RSI"), row=2, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color=COLORS["danger"], row=2, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color=COLORS["primary"], row=2, col=1)

    fig = _apply_common_layout(fig, height=700)
    fig.update_layout(title=dict(text=f"<b>{title}</b>", font=dict(size=18, color=COLORS["text"])))
    fig.update_yaxes(gridcolor=COLORS["grid"], row=1, col=1)
    fig.update_yaxes(range=[0, 100], row=2, col=1)
    
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
    
    fig.add_hline(y=0, line_dash="solid", line_color="#fff", opacity=0.3)
    
    fig = _apply_common_layout(fig)
    fig.update_layout(
        title="<b>PERFORMANCE DELTA (%)</b>",
        yaxis_title="RETURN (%)",
        hovermode="x unified"
    )
    fig.update_yaxes(gridcolor=COLORS["grid"])
    
    return fig