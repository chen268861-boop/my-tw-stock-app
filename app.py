import streamlit as st
import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import warnings
import json
from streamlit_javascript import st_javascript  # 引入 JavaScript 原生瀏覽器記憶模組

warnings.filterwarnings('ignore')

# 網頁基礎設定 (優化手機窄螢幕顯示與視覺效果)
st.set_page_config(page_title="台股實時全資產損益選股系統", layout="centered")
st.title("🚀 台股全資產實時篩選 ✕ 庫存對帳診斷系統")

# ==========================================
# 📥 1. 超級記憶體：Browser LocalStorage 讀取機制
# ==========================================
# 透過原生 JS 語法現場向手機瀏覽器索取歷史持股記錄
stored_portfolio_js = st_javascript("localStorage.getItem('my_portfolio_data');")

# 確保 session_state 存在
if 'my_portfolio' not in st.session_state:
    st.session_state.my_portfolio = []

# 解析瀏覽器回傳的永久記憶數據
if stored_portfolio_js and stored_portfolio_js != "null":
    try:
        parsed_data = json.loads(stored_portfolio_js)
        if isinstance(parsed_data, list) and len(st.session_state.my_portfolio) == 0:
            st.session_state.my_portfolio = parsed_data
    except Exception as e:
        pass

def save_portfolio_to_browser():
    """將當前持股名單編碼為 JSON 字串，永久寫入手機瀏覽器底層"""
    json_str = json.dumps(st.session_state.my_portfolio)
    # 執行 JS 指令強行寫入本地保險箱
    st_javascript(f"localStorage.setItem('my_portfolio_data', '{json_str}');")

# ==========================================
# 🛠️ 2. 側邊欄 / 行動端頂部控制面板
# ==========================================
st.sidebar.header("⚙️ 專家級動態選股指標設定")
period = st.sidebar.radio("⏱️ 策略操作週期模板選擇", options=["短線", "中線", "長線"], index=2)

st.sidebar.markdown("---")
st.sidebar.subheader("🎛️ 濾網參數自由自訂")
use_short_ma = st.sidebar.checkbox("短線：必須站上 5MA 與 10MA", value=False)
use_mid_growth = st.sidebar.checkbox("中線：財報營收獲利雙正", value=False)
use_long_yield = st.sidebar.checkbox("長線：啟用最低殖利率過濾", value=False)
l_yield = st.sidebar.slider(" ↳ 殖利率下限要求 (%)", min_value=0.0, max_value=8.0, value=3.0, step=0.5)
use_long_pe = st.sidebar.checkbox("長線：啟用本益比上限過濾", value=False)
l_pe = st.sidebar.slider(" ↳ 本益比上限要求 (倍)", min_value=8.0, max_value=25.0, value=15.0, step=1.0)
l_sharpe = st.sidebar.slider("📈 最低夏普值要求 ( Sharpe )", min_value=-0.5, max_value=2.0, value=-0.5, step=0.1)
combo_beta = st.sidebar.slider("🛡️ 組合整體 Beta 風險上限", min_value=0.2, max_value=2.0, value=1.5, step=0.1)

# ==========================================
# ⚡ 3. 跨資產通用數據現場抓取核心
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
        if len(t) == 5 and t.endswith('T'): asset_type = 'REITs'
        elif len(t) == 6 and t.endswith('B'): asset_type = 'BOND_ETF'
        elif t.startswith('00') or len(t) == 5: asset_type = 'ETF'
        else: asset_type = 'EQUITY'
        raw_name = info.get('shortName', info.get('longName', f"台股 {t}"))
        tw_name_map = {
            "TSMC": "台積電", "HON HAI PRECISION": "鴻海", "MEDIATEK": "聯發科",
            "FUBON FINANCIAL": "富邦金", "DELTA ELECTRONICS": "台達電", "TAIWAN 50 ETF": "元大台灣50",
            "0050": "元大台灣50", "FT TW50": "富邦台50", "006208": "富邦台50",
            "CATHAY SUSTAINAB": "國泰永續高股息", "00878": "國泰永續高股息", "YUANTA HIGH DIVI": "元大高股息",
            "0056": "元大高股息", "CAPITAL GRAND DI": "群益台灣精選高息", "00919": "群益台灣精選高息"
        }
        name = tw_name_map.get(t, raw_name)
        for eng_k, chn_v in tw_name_map.items():
            if eng_k.lower() in raw_name.lower(): name = chn_v; break
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

# ==========================================
# 📊 4. 全台股智能三階段海選引擎 (精確限定最優5檔)
# ==========================================
def run_three_stage_universal_filter():
    try:
        url_twse = "https://twse.com.tw"
        res_twse = pd.read_json(url_twse)
        raw_twse = res_twse['data9'].values if 'data9' in res_twse.columns else []
        url_tpex = "https://tpex.org.tw"
        res_tpex = pd.read_json(url_tpex)
        raw_tpex = res_tpex['aaData'].values if 'aaData' in res_tpex.columns else []
        scanned_pool = []
        for row in raw_twse:
            if len(row) > 0 and row[0].isdigit() and len(row[0]) >= 4: scanned_pool.append(row[0])
        for row in raw_tpex:
            if len(row) > 0 and row[0].isdigit() and len(row[0]) >= 4: scanned_pool.append(row[0])
        user_portfolio_codes = [item["代號"] for item in st.session_state.my_portfolio]
        final_scanned_pool = list(set(scanned_pool[:30] + user_portfolio_codes))
        rows_scanned = []
        for ticker in final_scanned_pool:
            res_single = fetch_ticker_data_safely(ticker)
            if res_single: rows_scanned.append(res_single)
        if not rows_scanned: return pd.DataFrame()
        df_stage_b = pd.DataFrame(rows_scanned)
        df_filtered = df_stage_b.copy()
        if period == "短線" and use_short_ma:
            df_filtered = df_filtered[(df_filtered['即時價位'] >= df_filtered['5MA']) & (df_filtered['即時價位'] >= df_filtered['10MA'])]
        elif period == "中線" and use_mid_growth:
            df_filtered = df_filtered[(df_filtered['類別'] != 'EQUITY') | (df_filtered['營收獲利雙正'] == True)]
        elif period == "長線":
            if use_long_yield: df_filtered = df_filtered[df_filtered['現金殖利率(%)'] >= l_yield]
            if use_long_pe: df_filtered = df_filtered[(df_filtered['類別'] != 'EQUITY') | (df_filtered['本益比'] <= l_pe) | (df_filtered['本益比'].isna())]
        df_filtered = df_filtered[df_filtered['夏普值'] >= l_sharpe]
        df_filtered = df_filtered[df_filtered['Beta值'] <= combo_beta]
        if not df_filtered.empty:
            return df_filtered.sort_values(by='夏普值', ascending=False).head(5)
        else: return pd.DataFrame()
    except:
        user_portfolio_codes = [item["代號"] for item in st.session_state.my_portfolio]
        backup_rows = []
        for ticker in user_portfolio_codes:
            res_single = fetch_ticker_data_safely(ticker)
            if res_single: backup_rows.append(res_single)
        return pd.DataFrame(backup_rows)

# 啟動網上海選引擎
df_master_market = run_three_stage_universal_filter()

# ==========================================
# 🔍 區塊一：全台股三階段精選快篩池 (已對接最優 5 檔)
# ==========================================
st.header("🔍 全台股三階段精選快篩池")
if not df_master_market.empty:
    st.subheader(f"🏆 符合【{period} 自訂參數】全網夏普值最優 5 檔黃金清單")
    st.dataframe(df_master_market[['代號', '名稱', '類別', '即時價位', '漲跌幅(%)', '現金殖利率(%)', '夏普值', 'Beta值']], use_container_width=True, hide_index=True)
else:
    st.warning("⚠️ 全網海選完畢！目前設定的量化指標太過嚴苛，沒有標的能完全通過篩選。")

st.markdown("---")

# ==========================================
# 💼 區塊二：真實個人庫存記帳與資產對帳單 (結合永久記憶)
# ==========================================
st.header("💼 我的實時庫存記帳與配置優化")

with st.form("add_stock_form", clear_on_submit=True):
    col_t, col_s, col_c, col_b = st.columns([1.5, 1.5, 1.5, 1])
    add_ticker = col_t.text_input("➕ 輸入任意代號新增到帳戶庫存:", placeholder="例如: 00919、2317")
    add_shares = col_s.number_input("持有股數:", min_value=1, value=1000, step=100)
    add_cost = col_c.number_input("買入成本價:", min_value=0.1, value=100.0, step=1.0)
    submit_btn = col_b.form_submit_button("確認新增持股")
    
    if submit_btn and add_ticker:
        t_clean = add_ticker.strip().upper()
        with st.spinner("正在連網驗證..."):
            test_res = fetch_ticker_data_safely(t_clean)
        if test_res:
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
            
            # 觸發瀏覽器永久儲存保險箱
            save_portfolio_to_browser()
            st.success(f"✅ 成功將真實資產 {test_res['名稱']} 納入並儲存至本地瀏覽器！")
            st.rerun()
        else:
            st.error("❌ 查無此代號，請確認輸入是否有誤。")

if st.button("🗑️ 清空所有個人庫存數據"):
    st.session_state.my_portfolio = []
    st.javascript("localStorage.removeItem('my_portfolio_data');")
    st.success("🧹 瀏覽器本地記憶已全數清除。")
    st.rerun()

# ==========================================
# 📊 5. 庫存損益即時動態分析與海選快篩連動
# ==========================================
user_universe = [item['代號'] for item in st.session_state.my_portfolio]

if len(st.session_state.my_portfolio) > 0 and not df_master_market.empty:
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
                "目前股數": item['股數'], "目前市值 (元)": round(m_val, 0), "未實現損益": round(profit, 0),
                "報酬率 (%)": round(roi, 2), "夏普值": r_info['夏普值'], "Beta值": r_info['Beta值']
            })
            
    if portfolio_rows:
        df_p_summary = pd.DataFrame(portfolio_rows)
        df_p_summary["資產權重 (%)"] = round((df_p_summary["目前市值 (元)"] / total_market_value) * 100, 1)
        st.subheader("💰 您的資產綜合即時對帳單")
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("庫存總市值", f"${int(total_market_value):,} 元")
        col_m2.metric("總未實現損益", f"+${int(total_market_value-total_cost_value):,}" if (total_market_value-total_cost_value) >= 0 else f"-${int(abs(total_market_value-total_cost_value)):,}", f"{round(((total_market_value-total_cost_value)/total_cost_value)*100, 2)}%")
        col_m3.metric("投入總本金", f"${int(total_cost_value):,} 元")
        
        st.dataframe(df_p_summary[["代號", "名稱", "買入成本", "即時市價", "目前股數", "目前市值 (元)", "未實現損益", "報酬率 (%)", "資產權重 (%)"]], use_container_width=True, hide_index=True)
        
        fig_p, ax_p = plt.subplots(figsize=(6, 3))
        ax_p.pie(df_p_summary["目前市值 (元)"], labels=df_p_summary["名稱"], autopct='%1.1f%%', startangle=90)
        ax_p.axis('equal')
        st.pyplot(fig_p)
else:
    st.info("💡 目前您的個人庫存箱是空的。")

st.markdown("---")

# ==========================================
# 🔍 區塊二：台股選股篩選器與趨勢畫布
# ==========================================
st.header("🔍 多功能智能策略快篩池")

if user_universe:
    rows_market = []
    for ticker_item in user_universe:
        res_single = fetch_ticker_data_safely(ticker_item)
        if res_single: rows_market.append(res_single)
        
    if rows_market:
        df_all_market = pd.DataFrame(rows_market)
        df_filtered = df_all_market.copy()

        if period == "短線" and use_short_ma:
            df_filtered = df_filtered[(df_filtered['即時價位'] >= df_filtered['5MA']) & (df_filtered['即時價位'] >= df_filtered['10MA'])]
        elif period == "中線" and use_mid_growth:
            df_filtered = df_filtered[(df_filtered['類別'] != 'EQUITY') | (df_filtered['營收獲利雙正'] == True)]
        elif period == "長線":
            if use_long_yield: df_filtered = df_filtered[df_filtered['現金殖利率(%)'] >= l_yield]
            if use_long_pe: df_filtered = df_filtered[(df_filtered['類別'] != 'EQUITY') | (df_filtered['本益比'] <= l_pe) | (df_filtered['本益比'].isna())]

        df_filtered = df_filtered[df_filtered['夏普值'] >= l_sharpe]
        df_filtered = df_filtered[df_filtered['Beta值'] <= combo_beta]

        st.subheader(f"🎯 當前符合【{period} 自訂參數】的自選股篩選結果")
        if df_filtered.empty:
            st.warning("⚠️ 目前設定的量化條件較嚴格，您的持股中暫無相符標的。可嘗試放寬指標。")
        else:
            st.dataframe(
                df_filtered[['代號', '名稱', '類別', '即時價位', '漲跌幅(%)', '現金殖利率(%)', '夏普值', 'Beta值']], 
                use_container_width=True, hide_index=True
            )

        st.markdown("---")

        # 📌 區塊三：個人庫存個股焦點技術指標 K 線圖
        st.subheader("📈 焦點技術指標均線圖")
        code_view = st.selectbox("選擇一檔資產繪製均線走勢圖:", options=user_universe)
        target_stock_df = df_all_market[df_all_market['代號'] == code_view]
        if not target_stock_df.empty:
            hist_data = target_stock_df['歷史日線'].values
            stock_name = target_stock_df['名稱'].values
            if hist_data is not None and not hist_data.empty:
                hist_tail = hist_data.tail(40)
                fig, ax = plt.subplots(figsize=(10, 4))
                ax.plot(hist_tail.index, hist_tail['Close'], label='最新成交價', color='#1f77b4', linewidth=2.5)
                ax.plot(hist_tail.index, hist_tail['Close'].rolling(5).mean(), label='5 MA', color='#ff7f0e', linestyle='--')
                ax.plot(hist_tail.index, hist_tail['Close'].rolling(10).mean(), label='10 MA', color='#2ca02c', linestyle=':')
                ax.set_title(f"【{code_view} {stock_name}】近 40 日均線形態")
                ax.grid(True, alpha=0.3)
                ax.legend(loc="upper left")
                st.pyplot(fig)
else:
    st.warning("🔍 策略快篩池與K線圖目前處於隱藏狀態。請先在上方輸入並新增至少一檔真實庫存標的，系統將自動啟動追蹤！")
