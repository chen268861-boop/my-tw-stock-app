import streamlit as st
import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# 網頁基礎設定 (優化手機窄螢幕顯示與視覺效果)
st.set_page_config(page_title="台股實時全資產損益選股系統", layout="centered")
st.title("🚀 台股全資產實時篩選 ✕ 庫存對帳診斷系統")

# ==========================================
# 📥 1. 初始化個人庫存紀錄（一開機完全乾淨零假資料）
# ==========================================
if 'my_portfolio' not in st.session_state:
    st.session_state.my_portfolio = [] 

# ==========================================
# 🛠️ 2. 側邊欄 / 行動端頂部控制面板
# ==========================================
st.sidebar.header("⚙️ 專家級動態選股指標設定")

# 策略操作週期
period = st.sidebar.radio("⏱️ 策略操作週期模板選擇", options=["短線", "中線", "長線"], index=2)

st.sidebar.markdown("---")
st.sidebar.subheader("🎛️ 濾網參數自由自訂")

# 動態條件開關與數值滑桿
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
    
    # yfinance自動尾碼容錯檢索
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
        
        # 技術均線
        ma5 = hist_daily['Close'].iloc[-5:].mean() if len(hist_daily) >= 5 else current_price
        ma10 = hist_daily['Close'].iloc[-10:].mean() if len(hist_daily) >= 10 else current_price
        ma20 = hist_daily['Close'].iloc[-20:].mean() if len(hist_daily) >= 20 else current_price
        ma60 = hist_daily['Close'].iloc[-60:].mean() if len(hist_daily) >= 60 else current_price
        
        # 暴力識別資產類別 (個股/ETF/債券/REITs)
        raw_type = info.get('quoteType', '')
        if len(t) == 5 and t.endswith('T'): asset_type = 'REITs'
        elif len(t) == 6 and t.endswith('B'): asset_type = 'BOND_ETF'
        elif t.startswith('00') or len(t) == 5: asset_type = 'ETF'
        else: asset_type = 'EQUITY'
            
        name = info.get('shortName', info.get('longName', f"資產 {t}"))
        
        # 殖利率通用對接
        div_yield = info.get('dividendYield', 0.0)
        if not div_yield and info.get('trailingAnnualDividendYield'):
            div_yield = info.get('trailingAnnualDividendYield', 0.0)
        div_yield = div_yield * 100 if div_yield else 0.0
        
        pe_ratio = info.get('trailingPE', np.nan) if asset_type == 'EQUITY' else np.nan
        rev_growth = info.get('revenueGrowth', 0.0) >= 0 if 'revenueGrowth' in info else True
        earning_growth = info.get('earningsGrowth', 0.0) >= 0 if 'earningsGrowth' in info else True
        
        # 風險質量
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

## ==========================================
# 📊 4. 全市場高效率篩選核心
# ==========================================

# 1. 讀取全台股列表 (請建立一個包含兩列: 'Ticker' 的 CSV 檔)
# 格式範例: 2330.TW, 2317.TW, ...
@st.cache_data(ttl=86400) # 快取一天，避免重複抓取
def get_all_tickers():
    # 這裡若無 CSV，可先用 yf 抓取部分代表性清單
    # 實務上請準備一個 full_list.csv 放在同目錄
    return ['2330.TW', '2317.TW', '2454.TW', '0050.TW', '00878.TW'] 

all_tickers = get_all_tickers()

with st.spinner("⏳ 正在進行全市場高速掃描..."):
    # 批次下載價格數據
    price_df = yf.download(all_tickers, period="3mo", group_by='ticker', progress=False)
    
    # 計算初步技術指標 (技術面篩選)
    candidates = []
    for ticker in all_tickers:
        try:
            # 提取該檔股票的歷史數據
            stock_data = price_df[ticker]
            close = stock_data['Close']
            ma5 = close.rolling(5).mean().iloc[-1]
            ma10 = close.rolling(10).mean().iloc[-1]
            
            # 初步篩選：例如必須站上 5MA
            if close.iloc[-1] > ma5:
                candidates.append(ticker.replace('.TW', '').replace('.TWO', ''))
        except: continue

# 2. 針對篩選出的「候選清單」補齊財報 (只抓 20-50 檔，速度極快)
st.write(f"已篩選出 {len(candidates)} 檔候選標的，正在補齊財務數據...")

refined_market_data = []
for ticker in candidates:
    res = fetch_ticker_data_safely(ticker) # 此處呼叫您原有的財報抓取函式
    if res: refined_market_data.append(res)

df_master_market = pd.DataFrame(refined_market_data)

# ==========================================
# 🔍 區塊一：多功能智能策略快篩池（已全面自動聯動）
# ==========================================
st.header("🔍 多功能智能策略快篩池")

if not df_master_market.empty:
    df_filtered = df_master_market.copy()

    # 執行短/中/長線動態過濾
    if period == "短線" and use_short_ma:
        df_filtered = df_filtered[(df_filtered['即時價位'] >= df_filtered['5MA']) & (df_filtered['即時價位'] >= df_filtered['10MA'])]
    elif period == "中線" and use_mid_growth:
        df_filtered = df_filtered[(df_filtered['類別'] != 'EQUITY') | (df_filtered['營收獲利雙正'] == True)]
    elif period == "長線":
        if use_long_yield:
            df_filtered = df_filtered[df_filtered['現金殖利率(%)'] >= l_yield]
        if use_long_pe:
            df_filtered = df_filtered[(df_filtered['類別'] != 'EQUITY') | (df_filtered['本益比'] <= l_pe) | (df_filtered['本益比'].isna())]

    df_filtered = df_filtered[df_filtered['夏普值'] >= l_sharpe]
    df_filtered = df_filtered[df_filtered['Beta值'] <= combo_beta]

    st.subheader(f"🎯 符合【{period} 自訂參數】的全資產篩選結果")
    st.dataframe(
        df_filtered[['代號', '名稱', '類別', '即時價位', '漲跌幅(%)', '現金殖利率(%)', '夏普值', 'Beta值']], 
        use_container_width=True, hide_index=True
    )
else:
    st.error("❌ 無法連線交易所取得數據。")

st.markdown("---")

# ==========================================
# 💼 區塊二：真實個人庫存記帳與資產對帳單（獨立隔離）
# ==========================================
st.header("💼 我的實時庫存記帳與配置優化")

with st.form("add_stock_form", clear_on_submit=True):
    col_t, col_s, col_c, col_b = st.columns([1.5, 1.5, 1.5, 1])
    add_ticker = col_t.text_input("➕ 輸入代號新增到帳戶庫存:", placeholder="例如: 00919 或 6596")
    add_shares = col_s.number_input("持有股數:", min_value=1, value=1000, step=100)
    add_cost = col_c.number_input("買入成本價:", min_value=0.1, value=100.0, step=1.0)
    submit_btn = col_b.form_submit_button("確認新增持股")
    
    if submit_btn and add_ticker:
        t_clean = add_ticker.strip().upper()
        if t_clean not in st.session_state.my_portfolio:
            with st.spinner("正在連網驗證..."):
                test_res = fetch_ticker_data_safely(t_clean)
            if test_res:
                st.session_state.my_portfolio.append({"代號": test_res['代號'], "股數": add_shares, "成本": round(add_cost, 2)})
                st.success(f"✅ 成功將真實資產 {test_res['名稱']} 納入帳戶對帳單！")
                st.rerun()
            else:
                st.error("❌ 查無此代號，請確認輸入。")

if st.button("🗑️ 清空所有個人庫存數據"):
    st.session_state.my_portfolio = []
    st.rerun()

# 庫存對帳渲染
if len(st.session_state.my_portfolio) > 0 and not df_master_market.empty:
    portfolio_rows = []
    total_market_value = 0
    total_cost_value = 0
    
    for item in st.session_state.my_portfolio:
        r_info = df_master_market[df_master_market['代號'] == item['代號']]
        if not r_info.empty:
            r = r_info.iloc[0]
            m_val = r['即時價位'] * item['股數']
            c_val = item['成本'] * item['股數']
            profit = m_val - c_val
            roi = (profit / c_val) * 100 if c_val > 0 else 0.0
            
            total_market_value += m_val
            total_cost_value += c_val
            portfolio_rows.append({
                "代號": item['代號'], "名稱": r['名稱'], "買入成本": item['成本'], "即時市價": r['即時價位'],
                "目前股數": item['股數'], "目前市值 (元)": round(m_val, 0), "未實現損益": round(profit, 0),
                "報酬率 (%)": round(roi, 2), "夏普值": r['夏普值'], "Beta值": r['Beta值']
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
        
        # 權重分佈圓餅圖
        fig_p, ax_p = plt.subplots(figsize=(6, 3))
        ax_p.pie(df_p_summary["目前市值 (元)"], labels=df_p_summary["名稱"], autopct='%1.1f%%', startangle=90)
        ax_p.axis('equal')
        st.pyplot(fig_p)

st.markdown("---")

# ==========================================
# 📌 區塊三：個人庫存個股焦點技術指標 K 線圖
# ==========================================
if not df_master_market.empty:
    st.subheader("📈 焦點技術指標均線圖")
    all_available_codes = list(df_master_market['代號'].unique())
    code_view = st.selectbox("選擇一檔全市場資產繪製均線走勢圖:", options=all_available_codes)
    
    target_stock_df = df_master_market[df_master_market['代號'] == code_view]
    if not target_stock_df.empty:
        # 使用安全的 .iloc[0] 提取單檔真實歷史日線
        hist_data = target_stock_df['歷史日線'].values[0]
        stock_name = target_stock_df['名稱'].values[0]
        
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

