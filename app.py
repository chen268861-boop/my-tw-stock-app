import streamlit as st
import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import warnings
import json
from datetime import datetime
from streamlit_javascript import st_javascript  # 引入原生記憶模組

warnings.filterwarnings('ignore')

# 網頁基礎設定 (優化手機窄螢幕顯示與視覺效果)
st.set_page_config(page_title="台股實時全資產系統", layout="centered")

# ==========================================
# 📥 1. 超級記憶體：Browser LocalStorage 讀取機制
# ==========================================
stored_portfolio_js = st_javascript("localStorage.getItem('my_portfolio_data');")

if 'my_portfolio' not in st.session_state:
    st.session_state.my_portfolio = []

if stored_portfolio_js and stored_portfolio_js != "null":
    try:
        parsed_data = json.loads(stored_portfolio_js)
        if isinstance(parsed_data, list) and len(st.session_state.my_portfolio) == 0:
            st.session_state.my_portfolio = parsed_data
    except:
        pass

def save_portfolio_to_browser():
    """將當前持股名單永久寫入手機瀏覽器底層"""
    json_str = json.dumps(st.session_state.my_portfolio)
    st_javascript(f"localStorage.setItem('my_portfolio_data', '{json_str}');")

# ==========================================
# 🛠️ 2. 側邊欄 / 行動端頂部控制面板
# ==========================================
st.sidebar.markdown("<h4 style='font-size:16px;'>⚙️ 專家級動態選股指標</h4>", unsafe_allow_html=True)
period = st.sidebar.radio("⏱️ 策略操作週期模板選擇", options=["短線", "中線", "長線"], index=2)

st.sidebar.markdown("---")
st.sidebar.markdown("<h5 style='font-size:14px;'>🎛️ 濾網參數自由自訂 (皆為選擇)</h5>", unsafe_allow_html=True)

# 動態條件開關與數值滑桿
use_short_ma = st.sidebar.checkbox("短線：必須站上 5MA 與 10MA", value=False)
use_mid_growth = st.sidebar.checkbox("中線：財報營收獲利雙正", value=False)

use_long_yield = st.sidebar.checkbox("長線：啟用最低殖利率過濾", value=False)
l_yield = st.sidebar.slider(" ↳ 殖利率下限要求 (%)", min_value=0.0, max_value=8.0, value=3.0, step=0.5)

use_long_pe = st.sidebar.checkbox("長線：啟用本益比上限過濾", value=False)
l_pe = st.sidebar.slider(" ↳ 本益比上限要求 (倍)", min_value=8.0, max_value=25.0, value=15.0, step=1.0)

# 股價高低動態過濾開關
use_price_filter = st.sidebar.checkbox("💰 啟用股價區間過濾", value=False)
price_mode = st.sidebar.selectbox(" ↳ 價格限制方向:", options=["低於指定股價 (以下)", "高於指定股價 (以上)"])
target_price_limit = st.sidebar.slider(" ↳ 股價篩選門檻 (元)", min_value=10.0, max_value=1200.0, value=100.0, step=10.0)

l_sharpe = st.sidebar.slider("📈 最低夏普值要求 ( Sharpe )", min_value=-0.5, max_value=2.0, value=-0.5, step=0.1)
combo_beta = st.sidebar.slider("🛡️ 組合整體 Beta 風險上限", min_value=0.2, max_value=2.0, value=1.5, step=0.1)

# ==========================================
# ⚡ 3. 跨資產通用數據現場抓取核心 (完全去除內建個股字串)
# ==========================================
def fetch_ticker_data_safely(t):
    info = {}
    ticker_obj = None
    hist_daily = pd.DataFrame()
    for suffix in ['.TW', '.TWO', '']:
        try:
            ticker_obj = yf.Ticker(f"{t}{suffix}" if suffix not in t else t)
            hist_daily = ticker_obj.history(period="1y")
            if not hist_daily.empty:
                try: info = ticker_obj.info
                except: info = {}
                break
        except: continue
    if hist_daily.empty: return None
    try:
        current_price = hist_daily['Close'].iloc[-1]
        prev_close = hist_daily['Close'].iloc[-2] if len(hist_daily) > 1 else current_price
        change_pct = ((current_price - prev_close) / prev_close) * 100
        ma5 = hist_daily['Close'].iloc[-5:].mean() if len(hist_daily) >= 5 else current_price
        ma10 = hist_daily['Close'].iloc[-10:].mean() if len(hist_daily) >= 10 else current_price
        ma20 = hist_daily['Close'].iloc[-20:].mean() if len(hist_daily) >= 20 else current_price
        ma60 = hist_daily['Close'].iloc[-60:].mean() if len(hist_daily) >= 60 else current_price
        
        # 智能資產類別辨識
        if len(t) == 5 and t.endswith('T'): asset_type = 'REITs'
        elif len(t) == 6 and t.endswith('B'): asset_type = 'BOND_ETF'
        elif t.startswith('00') or len(t) == 5: asset_type = 'ETF'
        else: asset_type = 'EQUITY'
        
        # 【全自動穿透中文翻譯】完全移除任何固定的個股或 ETF 對照表字串
        name = info.get('shortName', info.get('longName', f"台股 {t}"))
        
        div_yield = info.get('dividendYield', 0.0)
        if not div_yield and info.get('trailingAnnualDividendYield'): div_yield = info.get('trailingAnnualDividendYield', 0.0)
        div_yield = div_yield * 100 if div_yield else 0.0
        
        pe_ratio = info.get('trailingPE', np.nan) if asset_type == 'EQUITY' else np.nan
        rev_growth = info.get('revenueGrowth', 0.0) >= 0 if 'revenueGrowth' in info else True
        earning_growth = info.get('earningsGrowth', 0.0) >= 0 if 'earningsGrowth' in info else True
        returns = hist_daily['Close'].pct_change().dropna()
        sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if len(returns) > 0 and returns.std() > 0 else 0.0
        beta = info.get('beta', 1.0)
        if beta is None: beta = 1.0
        return {
            '代號': t.replace('.TW','').replace('.TWO','').upper(), '名稱': name, '類別': asset_type,
            '即時價位': round(current_price, 2), '漲跌幅(%)': round(change_pct, 2),
            '5MA': ma5, '10MA': ma10, '20MA': ma20, '60MA': ma60,
            '本益比': pe_ratio, '現金殖利率(%)': round(div_yield, 2),
            '營收獲利雙正': (rev_growth and earning_growth), '夏普值': round(sharpe, 2), 'Beta值': round(beta, 2),
            '歷史日線': hist_daily
        }
    except: return None

# 讀取目前使用者自己建立的庫存清單作為唯一的資料庫骨幹
user_universe = [item['代號'] for item in st.session_state.my_portfolio]

# ==========================================
# 💼 區塊一：個人庫存記帳與資產對帳單 (100% 乾淨全空)
# ==========================================
st.markdown("<h3 style='font-size:18px; font-weight:bold; margin-bottom:5px;'>💼 我的實時庫存記帳與優化</h3>", unsafe_allow_html=True)

with st.form("add_stock_form", clear_on_submit=True):
    st.markdown("<p style='font-size:11px; margin-bottom:-5px;'>➕ 增持登錄面板：</p>", unsafe_allow_html=True)
    col_t, col_s, col_c = st.columns(3)
    add_ticker = col_t.text_input("代號", placeholder="例如: 00919")
    add_shares = col_s.number_input("股數", min_value=1, value=1000, step=100)
    add_cost = col_c.number_input("成本價", min_value=0.1, value=100.0, step=1.0)
    submit_btn = st.form_submit_button("確認新增持股")
    
    if submit_btn and add_ticker:
        t_clean = add_ticker.strip().upper()
        with st.spinner("連網中..."):
            test_res = fetch_ticker_data_safely(t_clean)
        if test_res is not None:
            std_code = test_res['代號']
            existing = False
            for item in st.session_state.my_portfolio:
                if item["代號"] == std_code:
                    total_shares = item["股數"] + add_shares
                    item["成本"] = round(((item["成本"] * item["股數"]) + (add_cost * add_shares)) / total_shares, 2)
                    item["股數"] = total_shares
                    existing = True
                    break
            if not existing:
                st.session_state.my_portfolio.append({"代號": std_code, "股數": add_shares, "成本": round(add_cost, 2)})
            
            save_portfolio_to_browser()
            st.success(f"已儲存：{test_res['名稱']}")
            st.rerun()
        else:
            st.error("查過交易所，查無此代號。")

if st.button("🗑️ 清空所有庫存數據"):
    st.session_state.my_portfolio = []
    st.javascript("localStorage.removeItem('my_portfolio_data');")
    st.rerun()

# 渲染實時庫存對帳明細與總損益
if len(st.session_state.my_portfolio) > 0:
    portfolio_rows = []
    total_market_value = 0
    total_cost_value = 0
    
    for item in st.session_state.my_portfolio:
        r_info = fetch_ticker_data_safely(item['代號'])
        if r_info is not None:
            m_val = r_info['即時價位'] * item['股數']
            c_val = item['成本'] * item['股數']
            profit = m_val - c_val
            roi = (profit / c_val) * 100 if c_val > 0 else 0.0
            total_market_value += m_val
            total_cost_value += c_val
            portfolio_rows.append({
                "代號": item['代號'], "名稱": r_info['名稱'], "買入成本": item['成本'], "即時市價": r_info['即時價位'],
                "currently_shares": item['股數'], "currently_market_val": round(m_val, 0), "unrealized_profit": round(profit, 0),
                "roi_pct": round(roi, 2), "sharpe": r_info['夏普值'], "beta": r_info['Beta值']
            })
            
    if portfolio_rows:
        df_p_summary = pd.DataFrame(portfolio_rows)
        df_p_summary["資產權重 (%)"] = round((df_p_summary["currently_market_val"] / total_market_value) * 100, 1)
        
        st.markdown(f"<p style='font-size:12px; color:gray;'>📊 即時對帳單摘要：</p>", unsafe_allow_html=True)
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.markdown(f"<div style='font-size:11px;color:gray;'>總市值</div><div style='font-size:13px;font-weight:bold;'>${int(total_market_value):,}</div>", unsafe_allow_html=True)
        col_m2.markdown(f"<div style='font-size:11px;color:gray;'>總損益</div><div style='font-size:13px;font-weight:bold;color:{'red' if (total_market_value-total_cost_value)>=0 else 'green'}'>${int(total_market_value-total_cost_value):,} ({round(((total_market_value-total_cost_value)/total_cost_value)*100,1)}%)</div>", unsafe_allow_html=True)
        col_m3.markdown(f"<div style='font-size:11px;color:gray;'>投入本金</div><div style='font-size:13px;font-weight:bold;'>${int(total_cost_value):,}</div>", unsafe_allow_html=True)
        
        # 重新對齊中文表格欄位
        df_display_output = df_p_summary.rename(columns={
            "currently_shares": "目前股數", "currently_market_val": "目前市值 (元)", 
            "unrealized_profit": "未實現損益", "roi_pct": "報酬率 (%)"
        })
        st.dataframe(df_display_output[["代號", "名稱", "買入成本", "即時市價", "目前股數", "目前市值 (元)", "未實現損益", "報酬率 (%)"]], use_container_width=True, hide_index=True)
        
        fig_p, ax_p = plt.subplots(figsize=(5, 2.2))
        ax_p.pie(df_p_summary["currently_market_val"], labels=df_p_summary["名稱"], autopct='%1.1f%%', startangle=90, textprops={'fontsize': 8})
        ax_p.axis('equal')
        st.pyplot(fig_p)
else:
    st.info("💡 庫存保險箱目前完全清空。請在上方欄位輸入您實際持有的任意代號、股數與成本建立真實數據庫。")

st.markdown("<hr style='margin:10px 0px;'>", unsafe_allow_html=True)

# ==========================================
# 🔍 區塊二：台股選股篩選器 (100% 由您的自建池動態連動)
# ==========================================
st.markdown("<h3 style='font-size:18px; font-weight:bold; margin-bottom:5px;'>🔍 全台股智能多功能快篩池</h3>", unsafe_allow_html=True)

if user_universe:
    rows_market = []
    for ticker_item in user_universe:
        res_single = fetch_ticker_data_safely(ticker_item)
        if res_single: rows_market.append(res_single)
        
    if rows_market:
        df_master_market = pd.DataFrame(rows_market)
        df_filtered = df_master_market.copy()

        # 1. 特定股號查詢 (選擇性打勾)
        col_f1, col_f2 = st.columns(2)
        use_search_filter = col_f1.checkbox("🎯 格式化特定股號查詢", value=False)
        search_ticker_code = col_f1.text_input(" ↳ 輸入查詢代號:", placeholder="例如: 00919", label_visibility="collapsed")
        
        if use_search_filter and search_ticker_code:
            df_filtered = df_filtered[df_filtered['代號'] == search_ticker_code.strip().upper()]

        # 2. 股價範圍高低快查 (選擇性打勾)
        if use_price_filter:
            if price_mode == "低於指定股價 (以下)":
                df_filtered = df_filtered[df_filtered['即時價位'] <= target_price_limit]
            else:
                df_filtered = df_filtered[df_filtered['即時價位'] >= target_price_limit]

        # 3. 基礎操作週期模板快查過濾
        if period == "短線" and use_short_ma:
            df_filtered = df_filtered[(df_filtered['即時價位'] >= df_filtered['5MA']) & (df_filtered['即時價位'] >= df_filtered['10MA'])]
        elif period == "中線" and use_mid_growth:
            df_filtered = df_filtered[(df_filtered['類別'] != 'EQUITY') | (df_filtered['營收獲利雙正'] == True)]
        elif period == "長線":
            if use_long_yield: df_filtered = df_filtered[df_filtered['現金殖利率(%)'] >= l_yield]
            if use_long_pe: df_filtered = df_filtered[(df_filtered['類別'] != 'EQUITY') | (df_filtered['本益比'] <= l_pe) | (df_filtered['本益比'].isna())]

        # 4. 品質與風險敏感度連動
        df_filtered = df_filtered[df_filtered['夏普值'] >= l_sharpe]
        df_filtered = df_filtered[df_filtered['Beta值'] <= combo_beta]

        # 自動截取最優前5檔
        df_top_5 = df_filtered.sort_values(by='夏普值', ascending=False).head(5)

        st.markdown(f"<p style='font-size:12px; color:gray;'>🏆 通過左側指標與上方條件篩選之黃金資產：</p>", unsafe_allow_html=True)
        if df_top_5.empty:
            st.warning("⚠️ 自訂過濾條件較嚴格，目前持股池中暫無相符資產。請放寬左側滑桿。")
        else:
            st.dataframe(df_top_5[['代號', '名稱', '類別', '即時價位', '漲跌幅(%)', '現金殖利率(%)', '夏普值', 'Beta值']], use_container_width=True, hide_index=True)

        st.markdown("<hr style='margin:10px 0px;'>", unsafe_allow_html=True)

        # ==========================================
        # 📈 區塊三：全資產焦點技術指標均線線圖 (微型 UI)
        # ==========================================
        st.markdown("<h4 style='font-size:14px; font-weight:bold;'>📈 庫存形態均線K線圖</h4>", unsafe_allow_html=True)
        code_view = st.selectbox("選擇資產", options=user_universe, label_visibility="collapsed")
        
        target_stock_res = fetch_ticker_data_safely(code_view)
        if target_stock_res is not None:
            hist_data = target_stock_res['歷史日線']
            stock_name = target_stock_res['名稱']
            if not hist_data.empty:
                hist_tail = hist_data.tail(40)
                fig, ax = plt.subplots(figsize=(10, 3.8))
                ax.plot(hist_tail.index, hist_tail['Close'], label='市價', color='#1f77b4', linewidth=2)
                ax.plot(hist_tail.index, hist_tail['Close'].rolling(5).mean(), label='5 MA', color='#ff7f0e', linestyle='--')
                ax.plot(hist_tail.index, hist_tail['Close'].rolling(10).mean(), label='10 MA', color='#2ca02c', linestyle=':')
                ax.grid(True, alpha=0.3)
                plt.xticks(fontsize=8)
                plt.yticks(fontsize=8)
                st.pyplot(fig)
else:
    st.warning("🔍 智能快篩池與K線均線通道目前處於隱藏安全模式。請先在上方手動登錄至少一檔您持有的真實代號，系統將自動為您開啟即時追蹤！")
