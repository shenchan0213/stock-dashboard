"""
analysis.py (2026 重構優化版)
- 穩定性大幅提升
- 台股/美股自動選擇最佳來源
- 新增綜合健康分數與投資洞察
"""

import yfinance as yf
import requests
import streamlit as st
from typing import Optional
from utils import retry_yfinance

def get_financial_health(ticker: str) -> dict | None:
    """
    主入口函數
    返回格式：{"pe_status": , "roe_status": , "margin_status": , "health_score": , "insight": , "data": {...}}
    """
    api_key = st.secrets.get("FMP_API_KEY", "").strip()
    
    # 1. 台股直接走 Yahoo（FMP 免費版幾乎無數據）
    if ".TW" in ticker.upper():
        return _get_data_from_yahoo(ticker)

    # 2. 美股優先使用 FMP
    if api_key:
        fmp_result = _try_fmp_api(ticker, api_key)
        if fmp_result:
            return fmp_result

    # 3. FMP 失敗或無金鑰 → 退回 Yahoo
    return _get_data_from_yahoo(ticker)


def _try_fmp_api(ticker: str, api_key: str) -> Optional[dict]:
    """嘗試 FMP API（美股專用）"""
    try:
        clean_ticker = ticker.replace("^", "").upper()
        
        # key-metrics-ttm 是 FMP 最強大的免費 TTM 指標端點
        url = f"https://financialmodelingprep.com/api/v3/key-metrics-ttm/{clean_ticker}?apikey={api_key}"
        
        resp = requests.get(url, timeout=7)
        resp.raise_for_status()
        data = resp.json()

        if not data or not isinstance(data, list) or len(data) == 0:
            return None

        metrics = data[0]

        analysis = {
            "pe_status": "N/A",
            "roe_status": "N/A",
            "margin_status": "N/A",
            "health_score": 0,
            "insight": "",
            "data": {
                "PE": metrics.get("peRatioTTM"),
                "Forward PE": metrics.get("forwardPE"),
                "PEG": metrics.get("pegRatioTTM"),
                "ROE": metrics.get("roeTTM"),
                "Profit Margin": metrics.get("netProfitMarginTTM"),
                "Beta": metrics.get("beta", 0),           # FMP 直接提供
            }
        }
        return _evaluate_metrics(analysis)

    except Exception as e:
        print(f"⚠️ FMP API 失敗 ({ticker}): {e}")
        return None

@retry_yfinance
def _get_data_from_yahoo(ticker: str) -> dict | None:
    """Yahoo Finance 備用路徑（全市場通用）"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        if not info or len(info) < 5:
            raise ValueError("Yahoo 回傳空資料")

        analysis = {
            "pe_status": "N/A",
            "roe_status": "N/A",
            "margin_status": "N/A",
            "health_score": 0,
            "insight": "",
            "data": {
                "PE": info.get("trailingPE"),
                "Forward PE": info.get("forwardPE"),
                "PEG": info.get("pegRatio"),
                "ROE": info.get("returnOnEquity"),
                "Profit Margin": info.get("profitMargins"),
                "Beta": info.get("beta"),
            }
        }
        return _evaluate_metrics(analysis)

    except Exception as e:
        print(f"❌ Yahoo Finance 失敗 ({ticker}): {e}")
        return None


def _evaluate_metrics(analysis: dict) -> dict:
    """統一評分邏輯 + 計算綜合健康分數"""
    data = analysis["data"]

    # 1. PE 評分
    pe = data.get("PE")
    if pe is not None:
        if pe < 15:
            analysis["pe_status"] = "低估 (Undervalued)"
            pe_score = 90
        elif pe > 35:
            analysis["pe_status"] = "高估 (Overvalued)"
            pe_score = 30
        else:
            analysis["pe_status"] = "合理 (Fair)"
            pe_score = 70
    else:
        pe_score = 50

    # 2. ROE 評分（轉為百分比顯示）
    roe = data.get("ROE")
    if roe is not None:
        roe_pct = roe * 100
        data["ROE"] = roe_pct
        if roe > 0.20:
            analysis["roe_status"] = "極優 (Excellent)"
            roe_score = 95
        elif roe > 0.15:
            analysis["roe_status"] = "良好 (Good)"
            roe_score = 75
        else:
            analysis["roe_status"] = "普通 (Average)"
            roe_score = 45
    else:
        roe_score = 40

    # 3. 淨利率評分
    margin = data.get("Profit Margin")
    if margin is not None:
        margin_pct = margin * 100
        data["Profit Margin"] = margin_pct
        if margin > 0.20:
            analysis["margin_status"] = "具壟斷力 (Moat)"
            margin_score = 90
        else:
            analysis["margin_status"] = "競爭激烈 (Competitive)"
            margin_score = 50
    else:
        margin_score = 40

    # 4. 綜合健康分數（加權平均）
    analysis["health_score"] = round((pe_score * 0.4 + roe_score * 0.4 + margin_score * 0.2), 0)

    # 5. 簡短投資洞察
    score = analysis["health_score"]
    if score >= 85:
        analysis["insight"] = "💎 優質標的！建議長期持有"
    elif score >= 70:
        analysis["insight"] = "✅ 基本面穩健，可考慮布局"
    elif score >= 50:
        analysis["insight"] = "⚖️ 基本面普通，需搭配技術面"
    else:
        analysis["insight"] = "⚠️ 基本面偏弱，風險較高"

    return analysis