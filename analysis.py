"""
analysis.py (Debug Version)
"""
import yfinance as yf
import pandas as pd
import streamlit as st # 引入 streamlit 以便顯示除錯訊息
import requests

FMP_API_KEY = "2ct3aXGeISJuBjXuCX762wNcK2oNe4jD"  # 請替換為你的 FMP API 金鑰
def get_financial_health(ticker: str) -> dict:
    """
    優先使用 FMP API 獲取數據，失敗則退回 Yahoo Finance
    """
    # 1. 嘗試使用 FMP (針對美股特別強大)
    try:
        # FMP 不需要 .TW 後綴，也不需要 ^ 符號，需做簡單處理
        clean_ticker = ticker.replace(".TW", "").replace("^", "")
        
        url = f"https://financialmodelingprep.com/api/v3/key-metrics-ttm/{clean_ticker}?apikey={FMP_API_KEY}"
        response = requests.get(url, timeout=5)
        data = response.json()

        if data and isinstance(data, list):
            metrics = data[0]
            
            # 成功抓到 FMP 數據，進行分析
            analysis = {
                "pe_status": "N/A",
                "roe_status": "N/A",
                "margin_status": "N/A",
                "data": {
                    "PE": metrics.get("peRatioTTM"),
                    "Forward PE": 0, # FMP 免費版有些數據有限制
                    "PEG": metrics.get("pegRatioTTM"),
                    "ROE": metrics.get("roeTTM"),
                    "Profit Margin": metrics.get("netProfitMarginTTM"),
                    "Beta": 0 # 可另外呼叫 profile API 獲取
                }
            }
            
            # 進行評分邏輯 (復用之前的邏輯)
            return _evaluate_metrics(analysis)
            
    except Exception as e:
        print(f"FMP API Failed: {e}, Switching to Yahoo...")

    # 2. 如果 FMP 失敗或沒額度，退回使用 Yahoo Finance (原本的代碼)
    return _get_data_from_yahoo(ticker)

def _evaluate_metrics(analysis):
    # 將原本的 if-else 評分邏輯抽離出來放在這裡，避免代碼重複
    data = analysis["data"]
    
    if data["PE"]:
        if data["PE"] < 15: analysis["pe_status"] = "低估 (Undervalued)"
        elif data["PE"] > 35: analysis["pe_status"] = "高估 (Overvalued)"
        else: analysis["pe_status"] = "合理 (Fair)"
    
    if data["ROE"]:
        if data["ROE"] > 0.20: analysis["roe_status"] = "極優 (Excellent)"
        elif data["ROE"] > 0.15: analysis["roe_status"] = "良好 (Good)"
        else: analysis["roe_status"] = "普通 (Average)"

    if data["Profit Margin"]:
        if data["Profit Margin"] > 0.20: analysis["margin_status"] = "具壟斷力 (Moat)"
        else: analysis["margin_status"] = "競爭激烈 (Competitive)"
        
    return analysis
def _get_data_from_yahoo(ticker: str) -> dict:
    try:
        stock = yf.Ticker(ticker)
        
        # 嘗試獲取 info
        info = stock.info
        
        # 雲端除錯關鍵：如果 info 是空的，手動拋出錯誤
        if not info or len(info) < 5:
            raise ValueError("Yahoo Finance 回傳空數據 (可能被阻擋)")

        # ... (原本的提取數據邏輯保持不變) ...
        pe = info.get('trailingPE')
        forward_pe = info.get('forwardPE')
        peg = info.get('pegRatio')
        roe = info.get('returnOnEquity')
        profit_margin = info.get('profitMargins')
        beta = info.get('beta')
        
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

        # ... (原本的評分邏輯保持不變) ...
        if pe:
            if pe < 15: analysis["pe_status"] = "低估 (Undervalued)"
            elif pe > 35: analysis["pe_status"] = "高估 (Overvalued)"
            else: analysis["pe_status"] = "合理 (Fair)"
            
        if roe:
            if roe > 0.20: analysis["roe_status"] = "極優 (Excellent)"
            elif roe > 0.15: analysis["roe_status"] = "良好 (Good)"
            else: analysis["roe_status"] = "普通 (Average)"

        if profit_margin:
            if profit_margin > 0.20: analysis["margin_status"] = "具壟斷力 (Moat)"
            else: analysis["margin_status"] = "競爭激烈 (Competitive)"

        return analysis

    except Exception as e:
        # 在 Streamlit Cloud 的 Logs 中印出具體錯誤
        print(f"❌ [Error] {ticker} 基本面獲取失敗: {e}")
        return None