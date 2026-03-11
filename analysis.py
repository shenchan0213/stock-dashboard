"""
analysis.py — SHEN XIV
財務健康分析引擎

關鍵修正：移除對 utils 的 retry_yfinance / _yf_session 依賴
utils 已全面遷移 FMP，不再有 yfinance。
analysis.py 自己管理 Yahoo session（台股 + FMP 備援用）。
"""

import yfinance as yf
import requests
import streamlit as st
from typing import Optional
from requests import Session
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception

# ── 自己的 yfinance session（不再從 utils import）─────────────
_yf_session = Session()
_yf_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/133.0.0.0 Safari/537.36"
    )
})

def _retry_yf(func):
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=10),
        retry=retry_if_exception(
            lambda e: any(k in str(e).lower() for k in ["rate limit", "429", "too many"])
        ),
        reraise=True,
    )(func)


# ==================== 產業別 PE 基準表 ====================
SECTOR_PE_BENCHMARKS = {
    "Technology": 32, "Communication Services": 28, "Consumer Cyclical": 22,
    "Healthcare": 25, "Financial Services": 14, "Industrials": 20,
    "Basic Materials": 16, "Consumer Defensive": 20, "Energy": 12,
    "Utilities": 17, "Real Estate": 30, "default": 20,
}
SECTOR_MARGIN_BENCHMARKS = {
    "Technology": 0.15, "Communication Services": 0.12, "Consumer Cyclical": 0.06,
    "Healthcare": 0.10, "Financial Services": 0.20, "Industrials": 0.08,
    "Basic Materials": 0.08, "Consumer Defensive": 0.05, "Energy": 0.08,
    "Utilities": 0.12, "Real Estate": 0.20, "default": 0.10,
}


# ==================== 主入口 ====================

def get_financial_health(ticker: str) -> Optional[dict]:
    api_key = st.secrets.get("FMP_API_KEY", "").strip()
    if ".TW" in ticker.upper():
        return _get_data_from_yahoo(ticker)
    if api_key:
        result = _try_fmp_api(ticker, api_key)
        if result:
            return result
    return _get_data_from_yahoo(ticker)


def _try_fmp_api(ticker: str, api_key: str) -> Optional[dict]:
    try:
        clean = ticker.replace("^", "").upper()
        m_resp = requests.get(
            f"https://financialmodelingprep.com/api/v3/key-metrics-ttm/{clean}?apikey={api_key}",
            timeout=7)
        p_resp = requests.get(
            f"https://financialmodelingprep.com/api/v3/profile/{clean}?apikey={api_key}",
            timeout=7)
        m_data = m_resp.json() if m_resp.ok else []
        p_data = p_resp.json() if p_resp.ok else []
        if not m_data or not isinstance(m_data, list):
            return None
        m = m_data[0]
        sector = p_data[0].get("sector", "default") if p_data else "default"
        return _evaluate_metrics({
            "sector": sector,
            "pe_status": "N/A", "roe_status": "N/A", "margin_status": "N/A",
            "debt_status": "N/A", "growth_status": "N/A",
            "health_score": 0, "insight": "",
            "data": {
                "PE": m.get("peRatioTTM"), "Forward PE": m.get("forwardPE"),
                "PEG": m.get("pegRatioTTM"), "ROE": m.get("roeTTM"),
                "Profit Margin": m.get("netProfitMarginTTM"),
                "Gross Margin": m.get("grossProfitMarginTTM"),
                "Beta": m.get("betaTTM", 0),
                "D/E Ratio": m.get("debtToEquityTTM"),
                "Current Ratio": m.get("currentRatioTTM"),
                "Revenue Growth": m.get("revenueGrowthTTM"),
            }
        })
    except Exception as e:
        print(f"⚠️ FMP 失敗 ({ticker}): {e}")
        return None


@_retry_yf
def _get_data_from_yahoo(ticker: str) -> Optional[dict]:
    try:
        stock = yf.Ticker(ticker, session=_yf_session)
        info  = stock.info or {}
        if not info or len(info) < 5:
            raise ValueError("Yahoo 回傳空資料")
        sector = info.get("sector", "default") or "default"
        return _evaluate_metrics({
            "sector": sector,
            "pe_status": "N/A", "roe_status": "N/A", "margin_status": "N/A",
            "debt_status": "N/A", "growth_status": "N/A",
            "health_score": 0, "insight": "",
            "data": {
                "PE": info.get("trailingPE"), "Forward PE": info.get("forwardPE"),
                "PEG": info.get("pegRatio"), "ROE": info.get("returnOnEquity"),
                "Profit Margin": info.get("profitMargins"),
                "Gross Margin": info.get("grossMargins"),
                "Beta": info.get("beta"),
                "D/E Ratio": info.get("debtToEquity"),
                "Current Ratio": info.get("currentRatio"),
                "Revenue Growth": info.get("revenueGrowth"),
            }
        })
    except Exception as e:
        print(f"❌ Yahoo 失敗 ({ticker}): {e}")
        return None


# ==================== 評分引擎 ====================

def _evaluate_metrics(analysis: dict) -> dict:
    data   = analysis["data"]
    sector = analysis.get("sector", "default")
    pe_benchmark     = SECTOR_PE_BENCHMARKS.get(sector, 20)
    margin_benchmark = SECTOR_MARGIN_BENCHMARKS.get(sector, 0.10)
    scores = {}

    # 1. PE
    pe = data.get("PE")
    if pe is not None and pe > 0:
        r = pe / pe_benchmark
        if r < 0.7:   analysis["pe_status"] = "低估 (Undervalued)";    scores["pe"] = 90
        elif r < 1.2: analysis["pe_status"] = "合理 (Fair)";           scores["pe"] = 72
        elif r < 1.8: analysis["pe_status"] = "略高 (Slightly High)";  scores["pe"] = 50
        else:         analysis["pe_status"] = "高估 (Overvalued)";     scores["pe"] = 25
    else:
        analysis["pe_status"] = "N/A"; scores["pe"] = 50

    # 2. ROE
    roe = data.get("ROE")
    if roe is not None:
        roe_pct = roe * 100 if abs(roe) <= 5 else roe
        data["ROE"] = round(roe_pct, 2)
        if roe_pct >= 25:   analysis["roe_status"] = "極優 (Excellent ≥25%)"; scores["roe"] = 95
        elif roe_pct >= 15: analysis["roe_status"] = "良好 (Good ≥15%)";      scores["roe"] = 78
        elif roe_pct >= 8:  analysis["roe_status"] = "普通 (Average ≥8%)";    scores["roe"] = 55
        elif roe_pct >= 0:  analysis["roe_status"] = "偏低 (Low)";            scores["roe"] = 35
        else:               analysis["roe_status"] = "虧損 (Negative)";       scores["roe"] = 10
    else:
        analysis["roe_status"] = "N/A"; scores["roe"] = 40

    # 3. 淨利率
    margin = data.get("Profit Margin")
    if margin is not None:
        margin_pct = margin * 100 if abs(margin) <= 3 else margin
        data["Profit Margin"] = round(margin_pct, 2)
        r = (margin_pct / 100) / margin_benchmark
        if r >= 2.0:   analysis["margin_status"] = "具壟斷優勢 (Moat)";      scores["margin"] = 95
        elif r >= 1.2: analysis["margin_status"] = "優於同業 (Above Avg)";   scores["margin"] = 78
        elif r >= 0.7: analysis["margin_status"] = "符合同業 (In-line)";     scores["margin"] = 60
        elif r >= 0:   analysis["margin_status"] = "低於同業 (Below Avg)";   scores["margin"] = 35
        else:          analysis["margin_status"] = "虧損 (Loss)";            scores["margin"] = 8
    else:
        analysis["margin_status"] = "N/A"; scores["margin"] = 40

    # 4. D/E
    de = data.get("D/E Ratio")
    if de is not None:
        if de < 0.3:   analysis["debt_status"] = "極低負債 (Conservative)"; scores["debt"] = 95
        elif de < 1.0: analysis["debt_status"] = "健康範圍 (Healthy)";      scores["debt"] = 75
        elif de < 2.0: analysis["debt_status"] = "偏高 (Elevated)";         scores["debt"] = 45
        else:          analysis["debt_status"] = "高槓桿 (High Leverage)";  scores["debt"] = 20
    else:
        analysis["debt_status"] = "N/A"; scores["debt"] = 50

    # 5. 營收成長
    growth = data.get("Revenue Growth")
    if growth is not None:
        growth_pct = growth * 100 if abs(growth) <= 5 else growth
        data["Revenue Growth"] = round(growth_pct, 2)
        if growth_pct >= 20:   analysis["growth_status"] = "高速成長 (High Growth)"; scores["growth"] = 95
        elif growth_pct >= 10: analysis["growth_status"] = "穩定成長 (Steady)";      scores["growth"] = 78
        elif growth_pct >= 0:  analysis["growth_status"] = "緩步成長 (Slow)";        scores["growth"] = 55
        else:                  analysis["growth_status"] = "衰退 (Declining)";       scores["growth"] = 20
    else:
        analysis["growth_status"] = "N/A"; scores["growth"] = 45

    # 毛利率轉換
    gm = data.get("Gross Margin")
    if gm is not None and abs(gm) <= 3:
        data["Gross Margin"] = round(gm * 100, 2)

    # 加權分數 PE20 + ROE30 + Margin15 + Debt20 + Growth15
    analysis["health_score"] = round(
        scores["pe"] * 0.20 + scores["roe"] * 0.30 +
        scores["margin"] * 0.15 + scores["debt"] * 0.20 +
        scores["growth"] * 0.15
    )
    analysis["_scores"] = scores

    s = analysis["health_score"]
    if s >= 85:   analysis["insight"] = "💎 優質標的！基本面全面強健，長期持有勝率高"
    elif s >= 72: analysis["insight"] = "✅ 基本面穩健，可考慮逢低布局"
    elif s >= 58: analysis["insight"] = "⚖️ 基本面中等，建議搭配技術面確認進場點"
    elif s >= 40: analysis["insight"] = "⚠️ 基本面偏弱，部分指標有疑慮，需審慎評估"
    else:         analysis["insight"] = "🚨 基本面出現多項警訊，風險偏高"

    return analysis