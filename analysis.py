"""
analysis.py (Debug Version)
"""
import yfinance as yf
import pandas as pd
import streamlit as st # 引入 streamlit 以便顯示除錯訊息

def get_financial_health(ticker: str) -> dict:
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