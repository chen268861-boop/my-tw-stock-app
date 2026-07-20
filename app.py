import streamlit as st
import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# 網頁基礎設定 (優化手機窄螢幕顯示與視覺效果)
st.set_page_config(page_title="台股全功能智能選股與損益診斷系統", layout="centered")
st.title("🚀 台股智能篩選 ✕ 即時損益診斷完全體 App")

# 初始化 Session State 用以在手機網頁儲存個人庫存（包含股數與買入成本）
if 'my_portfolio' not in st.session_state:
    st.session_state.my_portfolio = [
        {"代號": "2330", "股數": 1000, "成本": 620.0},  # 預設範例：台積電1張，成本620元
        {"代號": "0050", "股數": 2000, "成本": 150.0}   # 預設範例：0050 2張，成本150元
    ]

# ==========================================
# 🛠️ 側邊欄 / 行動端頂部控制面板
# ==========================================
st.sidebar.header("⚙️ 專家級動態選股指標設定")

# 觀測代號與週期選擇
core_pool = ['2330', '2317', '2454', '2881', '2308', '5347', '0050', '006208', '00878', '0056', '00679B', '00772B']
code = st.sidebar.selectbox("🎯 選擇或輸入焦點觀測代號", options=core_pool, index=0)
period = st.sidebar.radio("⏱️ 策略操作週期模板選擇", options=["短線", "中線", "長線"], index=2)

st.sidebar.markdown("---")
st.sidebar.subheader("🎛️ 濾網參數自由自訂")

# 動態條件開關與數值滑桿
use_short_ma = st.sidebar.checkbox("短線：必須站上 5MA 與 10MA", value=True)
use_mid_growth = st.sidebar.checkbox("中線：財報營收獲利雙正", value=True)

use_long_yield = st.sidebar.checkbox("長線：啟用最低殖利率過濾", value=True)
l_yield = st.sidebar.slider(" ↳ 殖利率下限要求 (%)", min_value=0.0, max_value=8.0, value=3.0, step=0.5)

use_long_pe = st.sidebar.checkbox("長線：啟用本益比上限過濾", value=True)
l_pe = st.sidebar.slider(" ↳ 本益比上限要求 (倍)", min_value=8.0, max_value=25.0, value=15.0, step=1.0)

l_sharpe = st.sidebar.slider("📈 最低夏普值要求 ( Sharpe )", min_value=-0.5, max_value=2.0, value=0.0, step=0.1)
combo_beta = st.sidebar.slider("🛡️ 組合整體 Beta 風險上限", min_value=0.2, max_value=1.5, value=1.0, step=0.1)

# ==========================================
# ⚡ 即時市場數據穿透調用核心
# ==========================================
@st.cache_data(ttl=1800)  # 快取15分鐘，兼顧即時性與手機運行流暢度
def fetch_complete_market_data(tickers):
    rows = []
    for t in tickers:
        info = {}
        for suffix in ['.TW', '.TWO']:
            try:
                ticker_obj = yf.Ticker(f"{t}{suffix}")
                info = ticker_obj.info
                if info and 'shortName' in info: break
            except: continue
        if not info or 'shortName' not in info: continue
        try:
            hist_daily = ticker_obj.history(period="1y")
            if hist_daily.empty: continue
            current_price = hist_daily['Close'].iloc[-1]
            prev_close = hist_daily['Close'].iloc[-2] if len(hist_daily) > 1 else current_price
            change_pct = ((current_price - prev_close) / prev_close) * 100
            
            ma5 = hist_daily['Close'].iloc[-5:].mean()
            ma10 = hist_daily['Close'].iloc[-10:].mean()
            ma20 = hist_daily['Close'].iloc[-20:].mean()
            ma60 = hist_daily['Close'].iloc[-60:].mean()
            
            pe_ratio = info.get('trailingPE', np.nan)
            div_yield = info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0.0
            asset_type = info.get('quoteType', 'EQUITY')
            
            rev_growth = info.get('revenueGrowth', 0.0) >= 0
            earning_growth = info.get('earningsGrowth', 0.0) >= 0
            
            returns = hist_daily['Close'].pct_change().dropna()
            sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0.0
            beta = info.get('beta', 1.0) if info.get('beta') is not None else 1.0
            
            if asset_type != 'EQUITY': pe_ratio = np.nan
                
            rows.append({
                '代號': t, '名稱': info.get('shortName', t), '類別': asset_type,
                '即時價位': round(current_price, 2), '漲跌幅(%)': round(change_pct, 2),
                '5MA': ma5, '10MA': ma10, '20MA': ma20, '60MA': ma60,
                '本益比': pe_ratio, '現金殖利率(%)': round(div_yield, 2),
                '營收獲利雙正': (rev_growth and earning_growth), '夏普值': round(sharpe, 2), 'Beta值': round(beta, 2),
                '歷史日線': hist_daily
            })
        except: continue
    return pd.DataFrame(rows)

# 載入基礎觀測標的池數據
full_load_pool = list(set(core_pool + [item["代號"] for item in st.session_state.my_portfolio]))
df_all_market = fetch_complete_market_data(full_load_pool)

# ==========================================
# 🔍 區塊一：動態策略智能快篩池
# ==========================================
st.header("🔍 多功能智能策略快篩池")

df_filtered = df_all_market.copy()

# 套用短/中/長線動態濾網
if period == "短線" and use_short_ma:
    df_filtered = df_filtered[(df_filtered['即時價位'] >= df_filtered['5MA']) & (df_filtered['即時價位'] >= df_filtered['10MA'])]
elif period == "中線" and use_mid_growth:
    df_filtered = df_filtered[df_filtered['營收獲利雙正'] == True]
elif period == "長線":
    if use_long_yield:
        df_filtered = df_filtered[df_filtered['現金殖利率(%)'] >= l_yield]
    if use_long_pe:
        df_filtered = df_filtered[(df_filtered['類別'] != 'EQUITY') | (df_filtered['本益比'] <= l_pe)]

# 通用風險與品質指標調控（滑桿即時連動）
df_filtered = df_filtered[df_filtered['夏普值'] >= l_sharpe]
df_filtered = df_filtered[df_filtered['Beta值'] <= combo_beta]

st.subheader(f"🎯 當前符合【{period} 自訂參數】的標的名單")
if df_filtered.empty:
    st.warning("⚠️ 目前設定的量化條件過於嚴格，暫無相符標的。")
else:
    st.dataframe(
        df_filtered[['代號', '名稱', '即時價位', '漲跌幅(%)', '現金殖利率(%)', '夏普值', 'Beta值']], 
        use_container_width=True, hide_index=True
    )

st.markdown("---")

# ==========================================
# 💼 區塊二：個人持有庫存損益記帳與資產診斷
# ==========================================
st.header("💼 我的實時庫存記帳與配置優化")

# 建立新增資產的輸入表單（支援代號、股數、買入成本）
with st.form("add_stock_form", clear_on_submit=True):
    col_t, col_s, col_c, col_b = st.columns([1.5, 1.5, 1.5, 1])
    add_ticker = col_t.text_input("➕ 新增持股代號:", placeholder="例如: 2317")
    add_shares = col_s.number_input("持有股數:", min_value=1, value=1000, step=100)
    add_cost = col_c.number_input("買入成本價 (元):", min_value=0.1, value=100.0, step=1.0)
    submit_btn = col_b.form_submit_button("確認新增")
    
    if submit_btn and add_ticker:
        t_clean = add_ticker.strip()
        existing = False
        # 如果庫存已存在，自動加權平均計成本，不存在則新增一筆
        for item in st.session_state.my_portfolio:
            if item["代號"] == t_clean:
                total_shares = item["股數"] + add_shares
                item["成本"] = round(((item["成本"] * item["股數"]) + (add_cost * add_shares)) / total_shares, 2)
                item["股數"] = total_shares
                existing = True
                break
        if not existing:
            st.session_state.my_portfolio.append({"代號": t_clean, "股數": add_shares, "成本": round(add_cost, 2)})
        st.success(f"成功加入庫存： {t_clean} 共 {add_shares} 股！")
        st.rerun()

if st.button("🗑️ 清空所有個人庫存數據"):
    st.session_state.my_portfolio = []
    st.rerun()

# 庫存大盤損益動態分析計算
if len(st.session_state.my_portfolio) > 0 and not df_all_market.empty:
    portfolio_rows = []
    total_market_value = 0
    total_cost_value = 0
    
    for item in st.session_state.my_portfolio:
        t_info = df_all_market[df_all_market['代號'] == item['代號']]
        if not t_info.empty:
            r_info = t_info.iloc
            current_market_val = r_info['即時價位'] * item['股數']
            current_cost_val = item['成本'] * item['股數']
            unrealized_profit = current_market_val - current_cost_val
            roi_pct = (unrealized_profit / current_cost_val) * 100 if current_cost_val > 0 else 0.0
            
            total_market_value += current_market_val
            total_cost_value += current_cost_val
            
            portfolio_rows.append({
                "代號": item['代號'], "名稱": r_info['名稱'], "買入成本": item['成本'],
                "即時市價": r_info['即時價位'], "目前股數": item['股數'],
                "目前市值 (元)": round(current_market_val, 0), "未實現損益": round(unrealized_profit, 0),
                "報酬率 (%)": round(roi_pct, 2), "夏普值": r_info['夏普值'], "Beta值": r_info['Beta值']
            })
            
    df_p_summary = pd.DataFrame(portfolio_rows)
    df_p_summary["資產權重 (%)"] = round((df_p_summary["目前市值 (元)"] / total_market_value) * 100, 1)
    
    total_profit = total_market_value - total_cost_value
    total_roi = (total_profit / total_cost_value) * 100 if total_cost_value > 0 else 0.0
    
    # 頂部三大即時數據看板呈現
    st.subheader("💰 投資組合即時財富資產看板")
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("目前庫存總市值", f"${int(total_market_value):,} 元")
    col_m2.metric("總未實現損益", f"+${int(total_profit):,}" if total_profit >= 0 else f"-${int(abs(total_profit)):,}", f"{round(total_roi, 2)}%")
    col_m3.metric("投入總本金", f"${int(total_cost_value):,} 元")
    
    # 即時損益明細表
    st.markdown("**🔍 持有股未實現損益明細明細表**")
    st.dataframe(
        df_p_summary[["代號", "名稱", "買入成本", "即時市價", "目前股數", "目前市值 (元)", "未實現損益", "報酬率 (%)", "資產權重 (%)"]],
        use_container_width=True, hide_index=True
    )
    
    # 📌 AI 專家系統資產品質健康度診斷與再平衡指引
    st.subheader("💡 專家系統庫存體質診斷與策略再平衡建議")
    
    # 計算組合加權指標
    weighted_beta = np.sum(df_p_summary["Beta值"] * (df_p_summary["目前市值 (元)"] / total_market_value))
    weighted_sharpe = np.sum(df_p_summary["夏普值"] * (df_p_summary["目前市值 (元)"] / total_market_value))
    
    st.write(f"📊 組合整體加權 **Beta風險值為: {round(weighted_beta, 2)}** | 全包加權 **夏普回報率為: {round(weighted_sharpe, 2)}**")
    
    st.info("📢 **【操作指引】**")
    
    # 進行個股汰弱換強與續抱檢索
    high_risk_trapped = df_p_summary[(df_p_summary['報酬率 (%)'] < -10) & (df_p_summary['夏普值'] <= 0)]
    high_quality_profit = df_p_summary[(df_p_summary['報酬率 (%)'] > 5) & (df_p_summary['夏普值'] >= 1.2)]
    
    if not high_risk_trapped.empty:
        for _, row in high_risk_trapped.iterrows():
            st.error(f"❌ **汰弱換強警告**：您持有的【{row['代號']} {row['名稱']}】目前處於套牢虧損（{row['報酬率 (%)']}%）狀態，且其回報品質**夏普值為低效能的 {row['夏普值']}**。建議利用網頁上方策略快篩池篩出的優質龍頭資產進行汰弱換強移轉。")
            
    if not high_quality_profit.empty:
        for _, row in high_quality_profit.iterrows():
            st.success(f"💎 **強勢資產續抱指引**：您的庫存【{row['代號']} {row['名稱']}】目前正穩定獲利（+{row['報酬率 (%)']}%），且夏普值高達卓越的 {row['夏普值']}。這屬於高回報效率的核心資產，長線建議抱緊，切勿輕易賣出。")

    # 診斷組合風險 (Beta)
    if weighted_beta > 1.1:
        st.warning("⚠️ **避險調配提示**：由於整體組合加權 Beta 指標偏高，當大盤系統性回檔時波動較劇烈。建議利用上方篩選池，將部分資金調配至穩健度極高或帶有負相關的美債 ETF（如 00679B）平衡風險。")

    # 庫存權重分佈圓餅圖
    fig_p, ax_p = plt.subplots(figsize=(6, 3))
    ax_p.pie(df_p_summary["目前市值 (元)"], labels=df_p_summary["名稱"], autopct='%1.1f%%', startangle=90)
    ax_p.axis('equal')
    st.pyplot(fig_p)

else:
    st.info("💡 目前您的個人庫存箱是空的。請在上方欄位輸入您持建立的台股代號、股數與成本，系統將會啟動自動記帳與健康度診斷。")

st.markdown("---")

# ==========================================
# 📈 區塊三：焦點標的技術指標 K 線走勢圖
# ==========================================
main_stock = df_all_market[df_all_market['代號'] == code]
if not main_stock.empty:
    r = main_stock.iloc
    st.subheader(f"📈 焦點技術均線走勢圖：{r['代號']} {r['名稱']}")
    hist = r['歷史日線'].tail(40)
    
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(hist.index, hist['Close'], label='最新成交價', color='#1f77b4', linewidth=2.5)
    ax.plot(hist.index, hist['Close'].rolling(5).mean(), label='5 MA (短線強弱線)', color='#ff7f0e', linestyle='--')
    ax.plot(hist.index, hist['Close'].rolling(10).mean(), label='10 MA', color='#2ca02c', linestyle=':')
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left")
    st.pyplot(fig)
