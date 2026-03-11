"""
analysis.py — SHEN XIV
財務健康分析引擎

修正與升級：
1. ROE threshold bug：原本用原始小數比較，但變數已乘以 100 → 修正為用 roe_pct 比較
2. PE 評分加入產業別基準（科技股 PE 30 不叫高估）
3. 新增指標：負債權益比(D/E)、流動比率、營收成長率、毛利率
4. 評分邏輯更細緻，避免零售業、低利率行業被誤判
5. FMP 的 roeTTM 與 Yahoo returnOnEquity 皆為小數，統一處理
"""

import yfinance as yf
import requests
import streamlit as st
from typing import Optional
from utils import retry_yfinance, _yf_session

# ==================== 產業別 PE 基準表 ====================
# 不同產業有不同合理 PE，用通用標準會誤判
SECTOR_PE_BENCHMARKS = {
    "Technology":              32,
    "Communication Services":  28,
    "Consumer Cyclical":       22,
    "Healthcare":              25,
    "Financial Services":      14,
    "Industrials":             20,
    "Basic Materials":         16,
    "Consumer Defensive":      20,
    "Energy":                  12,
    "Utilities":               17,
    "Real Estate":             30,   # REIT 的 PE 概念不同
    "default":                 20,
}

# 產業別淨利率基準（低利率行業不應被扣分）
SECTOR_MARGIN_BENCHMARKS = {
    "Technology":              0.15,
    "Communication Services":  0.12,
    "Consumer Cyclical":       0.06,
    "Healthcare":              0.10,
    "Financial Services":      0.20,
    "Industrials":             0.08,
    "Basic Materials":         0.08,
    "Consumer Defensive":      0.05,
    "Energy":                  0.08,
    "Utilities":               0.12,
    "Real Estate":             0.20,
    "default":                 0.10,
}


# ==================== 主入口 ====================

def get_financial_health(ticker: str) -> Optional[dict]:
    """
    主入口函數
    返回：{
        "pe_status", "roe_status", "margin_status",
        "debt_status", "growth_status",
        "health_score", "insight", "sector",
        "data": { PE, Forward PE, PEG, ROE, Profit Margin,
                  Gross Margin, Beta, D/E Ratio, Current Ratio,
                  Revenue Growth }
    }
    """
    api_key = st.secrets.get("FMP_API_KEY", "").strip()

    if ".TW" in ticker.upper():
        return _get_data_from_yahoo(ticker)

    if api_key:
        result = _try_fmp_api(ticker, api_key)
        if result:
            return result

    return _get_data_from_yahoo(ticker)


# ==================== 數據來源 ====================

def _try_fmp_api(ticker: str, api_key: str) -> Optional[dict]:
    """FMP API（美股，包含更多指標）"""
    try:
        clean = ticker.replace("^", "").upper()

        # 同時抓 key-metrics 和 profile（取得 sector）
        metrics_url = f"https://financialmodelingprep.com/api/v3/key-metrics-ttm/{clean}?apikey={api_key}"
        profile_url = f"https://financialmodelingprep.com/api/v3/profile/{clean}?apikey={api_key}"

        m_resp = requests.get(metrics_url, timeout=7)
        p_resp = requests.get(profile_url, timeout=7)

        m_data = m_resp.json() if m_resp.ok else []
        p_data = p_resp.json() if p_resp.ok else []

        if not m_data or not isinstance(m_data, list):
            return None

        m = m_data[0]
        sector = p_data[0].get("sector", "default") if p_data else "default"

        analysis = {
            "sector": sector,
            "pe_status":     "N/A",
            "roe_status":    "N/A",
            "margin_status": "N/A",
            "debt_status":   "N/A",
            "growth_status": "N/A",
            "health_score":  0,
            "insight":       "",
            "data": {
                "PE":             m.get("peRatioTTM"),
                "Forward PE":     m.get("forwardPE"),
                "PEG":            m.get("pegRatioTTM"),
                "ROE":            m.get("roeTTM"),
                "Profit Margin":  m.get("netProfitMarginTTM"),
                "Gross Margin":   m.get("grossProfitMarginTTM"),
                "Beta":           m.get("betaTTM", 0),
                "D/E Ratio":      m.get("debtToEquityTTM"),
                "Current Ratio":  m.get("currentRatioTTM"),
                "Revenue Growth": m.get("revenueGrowthTTM"),
            }
        }
        return _evaluate_metrics(analysis)

    except Exception as e:
        print(f"⚠️ FMP API 失敗 ({ticker}): {e}")
        return None


@retry_yfinance
def _get_data_from_yahoo(ticker: str) -> Optional[dict]:
    """Yahoo Finance（台股 + FMP 失敗備援）"""
    try:
        stock = yf.Ticker(ticker, session=_yf_session)
        info  = stock.info or {}

        if not info or len(info) < 5:
            raise ValueError("Yahoo 回傳空資料")

        sector = info.get("sector", "default") or "default"

        analysis = {
            "sector":        sector,
            "pe_status":     "N/A",
            "roe_status":    "N/A",
            "margin_status": "N/A",
            "debt_status":   "N/A",
            "growth_status": "N/A",
            "health_score":  0,
            "insight":       "",
            "data": {
                "PE":             info.get("trailingPE"),
                "Forward PE":     info.get("forwardPE"),
                "PEG":            info.get("pegRatio"),
                "ROE":            info.get("returnOnEquity"),
                "Profit Margin":  info.get("profitMargins"),
                "Gross Margin":   info.get("grossMargins"),
                "Beta":           info.get("beta"),
                "D/E Ratio":      info.get("debtToEquity"),
                "Current Ratio":  info.get("currentRatio"),
                "Revenue Growth": info.get("revenueGrowth"),
            }
        }
        return _evaluate_metrics(analysis)

    except Exception as e:
        print(f"❌ Yahoo Finance 失敗 ({ticker}): {e}")
        return None


# ==================== 評分引擎 ====================

def _evaluate_metrics(analysis: dict) -> dict:
    """
    統一評分邏輯
    所有 score 介於 0~100，最終加權平均
    """
    data   = analysis["data"]
    sector = analysis.get("sector", "default")

    # 取產業基準
    pe_benchmark     = SECTOR_PE_BENCHMARKS.get(sector, SECTOR_PE_BENCHMARKS["default"])
    margin_benchmark = SECTOR_MARGIN_BENCHMARKS.get(sector, SECTOR_MARGIN_BENCHMARKS["default"])

    scores = {}

    # ── 1. PE（與產業基準相對比較）────────────────────────
    pe = data.get("PE")
    if pe is not None and pe > 0:
        ratio = pe / pe_benchmark          # 與同產業基準的比值
        if ratio < 0.7:
            analysis["pe_status"] = "低估 (Undervalued)"
            scores["pe"] = 90
        elif ratio < 1.2:
            analysis["pe_status"] = "合理 (Fair)"
            scores["pe"] = 72
        elif ratio < 1.8:
            analysis["pe_status"] = "略高 (Slightly High)"
            scores["pe"] = 50
        else:
            analysis["pe_status"] = "高估 (Overvalued)"
            scores["pe"] = 25
    else:
        analysis["pe_status"] = "N/A"
        scores["pe"] = 50   # 無法判斷給中性分

    # ── 2. ROE ────────────────────────────────────────────
    # 注意：Yahoo 與 FMP 的 ROE 皆為小數（0.25 = 25%）
    # _evaluate_metrics 裡轉換為 % 後，threshold 用 roe_pct 比較
    roe = data.get("ROE")
    if roe is not None:
        roe_pct        = roe * 100 if abs(roe) <= 5 else roe   # 防止 FMP 部分欄位已是百分比
        data["ROE"]    = round(roe_pct, 2)
        if roe_pct >= 25:
            analysis["roe_status"] = "極優 (Excellent ≥25%)"
            scores["roe"] = 95
        elif roe_pct >= 15:
            analysis["roe_status"] = "良好 (Good ≥15%)"
            scores["roe"] = 78
        elif roe_pct >= 8:
            analysis["roe_status"] = "普通 (Average ≥8%)"
            scores["roe"] = 55
        elif roe_pct >= 0:
            analysis["roe_status"] = "偏低 (Low)"
            scores["roe"] = 35
        else:
            analysis["roe_status"] = "虧損 (Negative)"
            scores["roe"] = 10
    else:
        analysis["roe_status"] = "N/A"
        scores["roe"] = 40

    # ── 3. 淨利率（與產業基準相對比較）──────────────────────
    margin = data.get("Profit Margin")
    if margin is not None:
        margin_pct           = margin * 100 if abs(margin) <= 3 else margin
        data["Profit Margin"] = round(margin_pct, 2)
        ratio                = (margin_pct / 100) / margin_benchmark
        if ratio >= 2.0:
            analysis["margin_status"] = "具壟斷優勢 (Moat)"
            scores["margin"] = 95
        elif ratio >= 1.2:
            analysis["margin_status"] = "優於同業 (Above Avg)"
            scores["margin"] = 78
        elif ratio >= 0.7:
            analysis["margin_status"] = "符合同業 (In-line)"
            scores["margin"] = 60
        elif ratio >= 0:
            analysis["margin_status"] = "低於同業 (Below Avg)"
            scores["margin"] = 35
        else:
            analysis["margin_status"] = "虧損 (Loss)"
            scores["margin"] = 8
    else:
        analysis["margin_status"] = "N/A"
        scores["margin"] = 40

    # ── 4. 負債權益比 D/E（越低越穩健）──────────────────────
    de = data.get("D/E Ratio")
    if de is not None:
        if de < 0.3:
            analysis["debt_status"] = "極低負債 (Conservative)"
            scores["debt"] = 95
        elif de < 1.0:
            analysis["debt_status"] = "健康範圍 (Healthy)"
            scores["debt"] = 75
        elif de < 2.0:
            analysis["debt_status"] = "偏高 (Elevated)"
            scores["debt"] = 45
        else:
            analysis["debt_status"] = "高槓桿 (High Leverage)"
            scores["debt"] = 20
    else:
        analysis["debt_status"] = "N/A"
        scores["debt"] = 50

    # ── 5. 營收成長率 ────────────────────────────────────────
    growth = data.get("Revenue Growth")
    if growth is not None:
        growth_pct            = growth * 100 if abs(growth) <= 5 else growth
        data["Revenue Growth"] = round(growth_pct, 2)
        if growth_pct >= 20:
            analysis["growth_status"] = "高速成長 (High Growth)"
            scores["growth"] = 95
        elif growth_pct >= 10:
            analysis["growth_status"] = "穩定成長 (Steady)"
            scores["growth"] = 78
        elif growth_pct >= 0:
            analysis["growth_status"] = "緩步成長 (Slow)"
            scores["growth"] = 55
        else:
            analysis["growth_status"] = "衰退 (Declining)"
            scores["growth"] = 20
    else:
        analysis["growth_status"] = "N/A"
        scores["growth"] = 45

    # ── 毛利率轉換（顯示用，不計分）─────────────────────────
    gm = data.get("Gross Margin")
    if gm is not None and abs(gm) <= 3:
        data["Gross Margin"] = round(gm * 100, 2)

    # ── 綜合健康分數（加權）──────────────────────────────────
    # PE 20% + ROE 30% + 淨利率 15% + 負債 20% + 成長 15%
    total = (
        scores["pe"]     * 0.20 +
        scores["roe"]    * 0.30 +
        scores["margin"] * 0.15 +
        scores["debt"]   * 0.20 +
        scores["growth"] * 0.15
    )
    analysis["health_score"] = round(total)
    analysis["_scores"]      = scores   # 保留分項分數供顯示

    # ── 投資洞察 ─────────────────────────────────────────────
    score = analysis["health_score"]
    if score >= 85:
        analysis["insight"] = "💎 優質標的！基本面全面強健，長期持有勝率高"
    elif score >= 72:
        analysis["insight"] = "✅ 基本面穩健，可考慮逢低布局"
    elif score >= 58:
        analysis["insight"] = "⚖️ 基本面中等，建議搭配技術面確認進場點"
    elif score >= 40:
        analysis["insight"] = "⚠️ 基本面偏弱，部分指標有疑慮，需審慎評估"
    else:
        analysis["insight"] = "🚨 基本面出現多項警訊，風險偏高"

    return analysis