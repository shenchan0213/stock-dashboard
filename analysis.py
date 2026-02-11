"""
analysis.py
負責財務數據分析與健康度評分邏輯
"""
import yfinance as yf
import pandas as pd

def get_financial_health(ticker: str) -> dict:
    """
    獲取並分析公司的財務健康度
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # 提取關鍵數據 (若無數據則給 None)
        pe = info.get('trailingPE')
        forward_pe = info.get('forwardPE')
        peg = info.get('pegRatio')
        roe = info.get('returnOnEquity')
        profit_margin = info.get('profitMargins')
        beta = info.get('beta')
        
        #  (Simple Valuation Logic)
        analysis = {
            "pe_status": "N/A",
            "roe_status": "N/A",
            "margin_status": "N/A",
            "data": {
                "PE": pe,
                "Forward PE": forward_pe,
                "PEG": peg,
                "ROE": roe,
                "Profit Margin": profit_margin,
                "Beta": beta
            }
        }

        # 1.  (PE & PEG)
        if pe:
            if pe < 15: analysis["pe_status"] = "低估 (Undervalued)"
            elif pe > 35: analysis["pe_status"] = "高估 (Overvalued)"
            else: analysis["pe_status"] = "合理 (Fair)"
            
        # 2. 獲利能力評估 (ROE) - 巴菲特指標 > 15%
        if roe:
            if roe > 0.20: analysis["roe_status"] = "極優 (Excellent)"
            elif roe > 0.15: analysis["roe_status"] = "良好 (Good)"
            else: analysis["roe_status"] = "普通 (Average)"

        # 3. 護城河評估 (Net Profit Margin)
        if profit_margin:
            if profit_margin > 0.20: analysis["margin_status"] = "具壟斷力 (Moat)"
            else: analysis["margin_status"] = "競爭激烈 (Competitive)"

        return analysis

    except Exception as e:
        return None