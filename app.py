import streamlit as st
import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# 網頁基礎設定 (優化手機窄螢幕顯示與視覺效果)
st.set_page_config(page_title="台股實時多資產損益選股系統", layout="centered")
st.title("🚀 台股多資產實時篩選 ✕ 庫存對帳診斷系統")

# ==========================================
# 📥 核心設定：初始化純乾淨庫存（100%無內建、無假資料）
# ==========================================
if 'my_portfolio' not in st.session_state:
    st.session_state.my_portfolio = []  # 初始狀態全空

# ==========================================
# 🛠️ 側邊欄 / 行動端頂部控制面板
# ==========================================
st.sidebar.header("⚙️ 專家級動態選股指標設定")

# 週期模板選擇
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
# ⚡ 穿透式真實市場數據網路提取核心（零死角防錯）
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
                try:
                    info = ticker_obj.info
                except:
                    info = {}
                break
        except:
            continue
            
    if hist_daily.empty:
        return None
        
    try:
        current_price = hist_daily['Close'].iloc[-1]
        prev_close = hist_daily['Close'].iloc[-2] if len(hist_daily) > 1 else current_price
        change_pct = ((current_price - prev_close) / prev_close) * 100
        
        ma5 = hist_daily['Close'].iloc[-5:].mean() if len(hist_daily) >= 5 else current_price
        ma10 = hist_daily['Close'].iloc[-10:].mean() if len(hist_daily) >= 10 else current_price
        ma20 = hist_daily['Close'].iloc[-20:].mean() if len(hist_daily) >= 20 else current_price
        ma60 = hist_daily['Close'].iloc[-60:].mean() if len(hist_daily) >= 60 else current_price
        
        name = info.get('shortName', info.get('longName', f"台股 {t}"))
        asset_type = info.get('quoteType', 'ETF' if (len(t) == 5 or t.startswith('00')) else 'EQUITY')
        
        div_yield = info.get('dividendYield', 0.0)
        if not div_yield and info.get('trailingAnnualDividendYield'):
            div_yield = info.get('trailingAnnualDividendYield', 0.0)
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
    except:
        return None

# ==========================================
# 💼 區塊一：真實個人庫存記帳與資產對帳單
# ==========================================
st.header("💼 我的實時庫存記帳與配置優化")

with st.form("add_stock_form", clear_on_submit=True):
    col_t, col_s, col_c, col_b = st.columns([1.5, 1.5, 1.5, 1])
    add_ticker = col_t.text_input("➕ 輸入代號 (個股/ETF/債券/REITs):", placeholder="例如: 2317 或 00919")
    add_shares = col_s.number_input("持有股數 (張*1000):", min_value=1, value=1000, step=100)
    add_cost = col_c.number_input("平均買入成本價 (元):", min_value=0.1, value=100.0, step=1.0)
    submit_btn = col_b.form_submit_button("確認新增持股")
    
    if submit_btn and add_ticker:
        t_clean = add_ticker.strip().upper()
        with st.spinner(f"正在連線交易所驗證並下載 {t_clean} 的真實市價..."):
            fetched_res = fetch_ticker_data_safely(t_clean)
            
        if fetched_res is not None:
            std_code = fetched_res['代號']
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
            st.success(f"✅ 真實數據對接成功！庫存已加入：{fetched_res['名稱']} ({std_code})")
            st.rerun()
        else:
            st.error(f"❌ 查無此代號！無法在交易所找到 '{t_clean}'，請確認上市櫃代號是否輸入正確。")

if st.button("🗑️ 清空所有個人庫存數據"):
    st.session_state.my_portfolio = []
    st.rerun()

# 庫存大盤損益動態分析計算
user_universe = []
if len(st.session_state.my_portfolio) > 0:
    portfolio_rows = []
    total_market_value = 0
    total_cost_value = 0
    
    for item in st.session_state.my_portfolio:
        user_universe.append(item['代號'])
        r_info = fetch_ticker_data_safely(item['代號'])
        if r_info is not None:
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
            
    if portfolio_rows:
        df_p_summary = pd.DataFrame(portfolio_rows)
        df_p_summary["資產權重 (%)"] = round((df_p_summary["目前市值 (元)"] / total_market_value) * 100, 1) if total_market_value > 0 else 0.0
        
        total_profit = total_market_value - total_cost_value
        total_roi = (total_profit / total_cost_value) * 100 if total_cost_value > 0 else 0.0
        
        st.subheader("💰 您的資產綜合即時對帳單")
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("庫存總市值", f"${int(total_market_value):,} 元")
        col_m2.metric("總未實現損益", f"+${int(total_profit):,}" if total_profit >= 0 else f"-${int(abs(total_profit)):,}", f"{round(total_roi, 2)}%")
        col_m3.metric("投入總本金", f"${int(total_cost_value):,} 元")
        
        st.dataframe(
            df_p_summary[["代號", "名稱", "買入成本", "即時市價", "目前股數", "目前市值 (元)", "未實現損益", "報酬率 (%)", "資產權重 (%)"]],
            use_container_width=True, hide_index=True
        )
        
        st.subheader("💡 專家系統庫存體質診斷與策略再平衡建議")
        weighted_beta = np.sum(df_p_summary["Beta值"] * (df_p_summary["目前市值 (元)"] / total_market_value))
        weighted_sharpe = np.sum(df_p_summary["夏普值"] * (df_p_summary["目前市值 (元)"] / total_market_value))
        st.write(f"📊 組合整體加權 **Beta風險值為: {round(weighted_beta, 2)}** | 全包加權 **夏普回報率為: {round(weighted_sharpe, 2)}**")
        
        fig_p, ax_p = plt.subplots(figsize=(6, 3))
        ax_p.pie(df_p_summary["Currently Market Value" if "Currently Market Value" in df_p_summary.columns else "目前市值 (元)"], labels=df_p_summary["名稱"], autopct='%1.1f%%', startangle=90)
        ax_p.axis('equal')
        st.pyplot(fig_p)
else:
    st.info("💡 目前您的個人庫存箱是空的。請在上方欄位輸入您持有的台股/ETF/債券代號與股數成本，系統將會現場連網抓取數據。")

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
            if use_long_yield:
                df_filtered = df_filtered[df_filtered['現金殖利率(%)'] >= l_yield]
            if use_long_pe:
                df_filtered = df_filtered[(df_filtered['類別'] != 'EQUITY') | (df_filtered['本益比'] <= l_pe) | (df_filtered['本益比'].isna())]

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
        code_view = st.selectbox("選擇一檔庫存標的繪製均線K線圖:", options=user_universe)
        
        # 安全優化：改用直接條件過濾，澈底杜絕 iloc 造成的當機 Bug
        target_stock_df = df_all_market[df_all_market['代號'] == code_view]
        
        if not target_stock_df.empty:
            # 穩健提取底層的歷史日線數據
            hist = target_stock_df['歷史日線'].values[0]
            stock_name = target_stock_df['名稱'].values[0]
            
            if hist is not None and not hist.empty:
                hist_tail = hist.tail(40)
                
                fig, ax = plt.subplots(figsize=(10, 4))
                ax.plot(hist_tail.index, hist_tail['Close'], label='最新成交價', color='#1f77b4', linewidth=2.5)
                ax.plot(hist_tail.index, hist_tail['Close'].rolling(5).mean(), label='5 MA (短線強弱線)', color='#ff7f0e', linestyle='--')
                ax.plot(hist_tail.index, hist_tail['Close'].rolling(10).mean(), label='10 MA', color='#2ca02c', linestyle=':')
                ax.set_title(f"{code_view} {stock_name} 近 40 日均線走勢")
                ax.grid(True, alpha=0.3)
                ax.legend(loc="upper left")
                st.pyplot(fig)
            else:
                st.warning("⚠️ 暫時無法取得該標的的歷史走勢數據。")
else:
    st.warning("🔍 策略快篩池與K線圖目前處於隱藏狀態。請先在上方輸入並新增至少一檔真實庫存標的，系統將自動啟動追蹤！")
