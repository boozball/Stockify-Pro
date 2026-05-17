import streamlit as st
import yfinance as yf
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import xml.etree.ElementTree as ET  
import re 
import json 

# 1. ตั้งค่าหน้าจอแบบกว้างพิเศษหน้าเดียวจบ
st.set_page_config(page_title="Stockify Pro Ultimate", page_icon="📈", layout="wide")

# --- 🎨 THE ABSOLUTE BEST - 10/10 Ultimate Masterpiece CSS Injection ---
st.markdown("""
    <style>
        /* นำเข้าฟอนต์และปรับระบบการเรนเดอร์ตัวหนังสือให้คมชัดระดับพิกเซล */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+Thai:wght@400;500;600;700&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Inter', 'Noto Sans Thai', sans-serif;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }

        /* กล่องข้อมูลแถวบนสุดระดับพรีเมียม (Uniform Metric Cards) */
        .premium-metric-card {
            background-color: var(--secondary-background-color);
            padding: 18px 22px;
            border-radius: 14px;
            border: 1px solid var(--border-color);
            box-shadow: 0 4px 12px rgba(0,0,0,0.01);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            min-height: 122px; /* ล็อกความสูงเท่ากันทุกกล่อง */
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .premium-metric-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(0,0,0,0.03);
        }
        .metric-label {
            font-size: 0.85rem;
            color: var(--text-color);
            opacity: 0.65;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .metric-value {
            font-size: 1.85rem;
            font-weight: 700;
            color: var(--text-color);
            margin: 4px 0;
            letter-spacing: -0.5px;
        }
        .metric-delta {
            font-size: 0.85rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 4px;
        }

        /* แถวแสดงข้อมูลการเงินสไตล์แอปสตรีมมิ่งหุ้นระดับโปร */
        .financial-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 8px;
            border-bottom: 1px solid var(--border-color);
            font-size: 0.95rem;
            transition: background-color 0.15s ease;
            border-radius: 6px;
        }
        .financial-row:hover {
            background-color: rgba(59, 130, 246, 0.04); /* ไฮไลต์สีฟ้าใสเวลาเมาส์ชี้ */
        }
        .financial-row:last-child {
            border-bottom: none;
        }
        .financial-label {
            color: var(--text-color);
            opacity: 0.75;
            font-weight: 400;
        }
        .financial-value {
            font-weight: 600;
            color: var(--text-color);
        }

        /* การ์ดข่าวพรีเมียมคลาสสิก */
        .premium-news-card {
            background-color: var(--secondary-background-color);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.01);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .premium-news-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 12px 30px rgba(59, 130, 246, 0.08);
            border-color: #3B82F6;
        }
        
        .premium-news-link {
            display: inline-block;
            font-size: 0.88rem;
            color: #2563EB;
            text-decoration: none;
            font-weight: 600;
            margin-top: 8px;
            transition: color 0.2s;
        }
        .premium-news-link:hover {
            color: #1D4ED8;
            text-decoration: underline;
        }
    </style>
""", unsafe_allow_html=True)

st.title("📈 Stockify Pro - Dashboard")
st.write("ระบบตรวจจับสัญญาณซื้อขาย งบการเงิน และวิเคราะห์กรอบแนวรับแนวต้านระยะสำคัญ")

ticker_input = st.text_input("สัญลักษณ์หุ้น หรือ ETF (เช่น NVDA, AMZN, RKLB, VOO):", value="AMZN").upper().strip()

def format_number(val):
    if val is None or pd.isna(val): return "-"
    if abs(val) >= 1_000_000_000_000: return f"{val / 1_000_000_000_000:.2f}T"
    if abs(val) >= 1_000_000_000: return f"{val / 1_000_000_000:.2f}B"
    if abs(val) >= 1_000_000: return f"{val / 1_000_000:.2f}M"
    return f"{val:.2f}"

def clean_text(text):
    if not text: return ""
    clean = re.sub('<.*?>', '', text) 
    return clean.replace('&quot;', '"').replace('&apos;', "'").replace('&amp;', '&').strip()

@st.cache_data(ttl=1800, show_spinner=False) 
def translate_google_single(text):
    if not text: return text
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=th&dt=t&q={requests.utils.quote(text)}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200: return "".join([s[0] for s in res.json()[0] if s[0]])
    except: pass
    return text  

@st.cache_data(ttl=1800, show_spinner=False) 
def translate_google_batch(texts_tuple):
    texts_list = list(texts_tuple)
    if not texts_list: return []
    cleaned_texts = [t.replace("\n", " ").strip() for t in texts_list]
    payload = "\n".join(cleaned_texts)
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=th&dt=t&q={requests.utils.quote(payload)}"
        res = requests.get(url, timeout=8)
        if res.status_code == 200:
            raw_segments = res.json()[0]
            full_translated = "".join([seg[0] for seg in raw_segments if seg[0]])
            translated_list = full_translated.split("\n")
            if len(translated_list) == len(texts_list):
                return [t.strip() for t in translated_list]
    except: pass
    return None  

# 4. เริ่มระบบประมวลผลข้อมูล
if ticker_input:
    with st.spinner('กำลังประมวลผลโครงสร้างแดชบอร์ดความเร็วแสง...'):
        try:
            stock = yf.Ticker(ticker_input)
            info = stock.info
            hist = stock.history(period="1y")
            
            if hist.empty:
                st.error("ไม่พบข้อมูลสัญลักษณ์นี้ กรุณาตรวจสอบอีกครั้ง")
                st.stop()
                
            current_price = info.get('regularMarketPrice', hist['Close'].iloc[-1])
            prev_price = hist['Close'].iloc[-2]
            price_change_pct = ((current_price - prev_price) / prev_price) * 100
            return_1y_pct = ((current_price - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100
            return_1y_color = "#10B981" if return_1y_pct >= 0 else "#EF4444"
            
            is_etf = info.get('quoteType', 'EQUITY') == 'ETF'
            hist['EMA20'] = hist['Close'].ewm(span=20, adjust=False).mean()
            hist['EMA50'] = hist['Close'].ewm(span=50, adjust=False).mean()
            hist['SMA200'] = hist['Close'].rolling(window=200).mean()
            ema20_curr, ema50_curr = hist['EMA20'].iloc[-1], hist['EMA50'].iloc[-1]
            sma200_curr = hist['SMA200'].iloc[-1] if not pd.isna(hist['SMA200'].iloc[-1]) else current_price
            
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rsi_curr = (100 - (100 / (1 + (gain / loss)))).iloc[-1]
            
            support_20d, resistance_20d = hist['Low'].tail(20).min(), hist['High'].tail(20).max()
            support_1y, resistance_1y = info.get('fiftyTwoWeekLow') or hist['Low'].min(), info.get('fiftyTwoWeekHigh') or hist['High'].max()
            fib_diff = resistance_1y - support_1y
            fib_382, fib_500, fib_618 = resistance_1y - (0.382 * fib_diff), resistance_1y - (0.500 * fib_diff), resistance_1y - (0.618 * fib_diff)
            
            dividend_yield, annual_div_sum, ex_div_date = 0.0, 0.0, "-"
            try:
                actions = stock.actions
                if actions is not None and 'Dividends' in actions.columns:
                    div_events = actions[actions['Dividends'] > 0]
                    if not div_events.empty:
                        ex_div_date = div_events.index[-1].strftime('%d-%m-%Y') + " (ล่าสุด)"
                        annual_div_sum = div_events[div_events.index >= (pd.Timestamp.now(tz=div_events.index.tz) - pd.Timedelta(days=365))]['Dividends'].sum()
            except: pass

            if annual_div_sum > 0:
                dividend_rate, dividend_yield = annual_div_sum, (annual_div_sum / current_price) * 100
            else:
                dividend_rate = info.get('dividendRate') or info.get('trailingAnnualDividendRate') or 0
                div_yield_raw = info.get('dividendYield') or info.get('yield') or info.get('trailingAnnualDividendYield') or 0
                dividend_yield = div_yield_raw if div_yield_raw > 1 else div_yield_raw * 100
                if dividend_yield > 40.0: dividend_yield = div_yield_raw

            if is_etf: asset_label, label_color = ("กองทุน ETF ปันผลสูง / Covered Call 💰", "green") if dividend_yield >= 7.0 else ("กองทุนรวมดัชนีทั่วไป (Growth/Index ETF) 📦", "blue")
            else: asset_label, label_color = ("หุ้นรายตัวปันผลสูง (High-Dividend Stock) 💎", "green") if dividend_yield >= 4.0 else ("หุ้นรายตัว / สินทรัพย์เติบโต (Growth Equity) 🏢", "orange")

            if current_price > sma200_curr and current_price > ema50_curr and rsi_curr < 55: advice_text, advice_color = "ซื้อทันที (Strong Buy) 🚀", "#10B981"
            elif current_price > sma200_curr and rsi_curr <= 68: advice_text, advice_color = "ซื้อ (Buy) 🟢", "#10B981"
            elif current_price <= sma200_curr and rsi_curr < 35: advice_text, advice_color = "ทยอยซื้อสะสม (Accumulate Buy) 🟡", "#F59E0B"
            elif rsi_curr > 73: advice_text, advice_color = "ถือ / ระวังแรงขายทำกำไรระยะสั้น (Hold) 🟠", "#F97316"
            else: advice_text, advice_color = "ถือเพื่อรอดูแนวโน้ม (Hold) 🔵", "#3B82F6"
            
            if rsi_curr >= 70.0: rsi_metric_label, rsi_text_color = "🚨 อันตราย (Overbought)", "#EF4444"
            elif rsi_curr <= 30.0: rsi_metric_label, rsi_text_color = "🟢 ปลอดภัย (โซนช้อนซื้อ)", "#10B981"
            else: rsi_metric_label, rsi_text_color = "🟡 ปกติ (ช่วงพักตัว 30-70)", "#F59E0B"

            # --- 📦 ระบบจัดแจงคัดกรองข่าวสาร ---
            news_items = []
            try:
                for item in (stock.news or [])[:5]:
                    t, l, p = item.get('title'), item.get('link'), item.get('publisher', 'Financial News')
                    s = item.get('summary', '') 
                    ts = item.get('providerPublishTime') 
                    pub_time = datetime.fromtimestamp(ts).strftime('%d/%m/%Y %H:%M') if ts else "ล่าสุด"
                    if not t and 'content' in item:
                        t, l = item['content'].get('title'), item['content'].get('clickThroughUrl', {}).get('url') or item['content'].get('canonicalUrl', {}).get('url')
                        p, s = item['content'].get('provider', {}).get('displayName', 'Yahoo Finance'), item['content'].get('summary', '')
                        c_ts = item['content'].get('pubDate')
                        if c_ts:
                            try: pub_time = datetime.strptime(c_ts, "%Y-%m-%dT%H:%M:%SZ").strftime('%d/%m/%Y %H:%M')
                            except: pub_time = "ล่าสุด"
                    if t and l: news_items.append({"title": t, "link": l, "pub": p, "summary": clean_text(s), "time": pub_time})
            except: pass
            
            if not news_items:
                try:
                    res = requests.get(f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker_input}&region=US&lang=en-US", headers={'User-Agent': 'Mozilla/5.0'})
                    if res.status_code == 200:
                        for item in ET.fromstring(res.content).findall('./channel/item')[:5]:
                            t, l = item.find('title').text or '', item.find('link').text or ''
                            s = item.find('description').text or ''
                            p_date = item.find('pubDate').text or 'ล่าสุด'
                            if p_date != 'ล่าสุด':
                                try: pub_time = datetime.strptime(p_date[5:25], "%d %b %Y %H:%M:%S").strftime('%d/%m/%Y %H:%M')
                                except: pub_time = p_date[:16]
                            else: pub_time = "ล่าสุด"
                            if t and l: news_items.append({"title": t, "link": l, "pub": "Yahoo Finance (RSS)", "summary": clean_text(s), "time": pub_time})
                except: pass

            texts_to_translate = []
            has_summary = 'longBusinessSummary' in info
            if has_summary: texts_to_translate.append(info['longBusinessSummary'])
            for it in news_items:
                texts_to_translate.append(it['title'])
                texts_to_translate.append(it['summary'] if it['summary'] else "No summary available.")

            google_results = None
            if texts_to_translate:
                google_results = map(str, translate_google_batch(tuple(texts_to_translate)) or [])
                google_results = list(google_results) if google_results else None

            thai_biz_summary = ""
            idx = 0
            if has_summary:
                thai_biz_summary = google_results[idx] if google_results else translate_google_single(info['longBusinessSummary'])
                idx += 1
                
            for it in news_items:
                if google_results:
                    it['thai_title'] = google_results[idx]
                    idx += 1
                    it['thai_summary'] = google_results[idx] if it['summary'] else ""
                    idx += 1
                else: 
                    it['thai_title'] = translate_google_single(it['title'])
                    it['thai_summary'] = translate_google_single(it['summary']) if it['summary'] else ""

            # --- 🖥️ ส่วนวาดการแสดงผลบนหน้าจอ ---
            st.write(f"### 📊 **{info.get('longName', ticker_input)}**")
            st.markdown(f"**ประเภทสินทรัพย์** | :{label_color}[**{asset_label}**]")
            
            if has_summary:
                with st.expander("📖 ดูข้อมูลลักษณะธุรกิจ (Company Summary)"):
                    st.markdown(f"<p style='color: var(--text-color); font-size: 0.95rem; line-height: 1.6; text-align: justify;'>{thai_biz_summary}</p>", unsafe_allow_html=True)

            # คอลัมน์แถวบนบีบกระชับชิดติดกัน (Compact Grid)
            m_col1, m_col2, m_col3, m_col4 = st.columns(4, gap="small")
            
            # กล่องที่ 1: ราคาปัจจุบัน
            with m_col1:
                price_color = "#10B981" if price_change_pct >= 0 else "#EF4444"
                price_arrow = "▲" if price_change_pct >= 0 else "▼"
                st.markdown(f"""
                    <div class="premium-metric-card">
                        <div class="metric-label">💵 ราคาปัจจุบัน (USD)</div>
                        <div class="metric-value">${current_price:.2f}</div>
                        <div class="metric-delta" style="color: {price_color};">{price_arrow} {abs(price_change_pct):.2f}%</div>
                    </div>
                """, unsafe_allow_html=True)

            # กล่องที่ 2: ผลตอบแทน 1 ปี
            with m_col2:
                st.markdown(f"""
                    <div class="premium-metric-card">
                        <div class="metric-label">📈 ผลตอบแทนรอบ 1 ปี</div>
                        <div class="metric-value">{return_1y_pct:+.2f}%</div>
                        <div class="metric-delta" style="color: {return_1y_color};">▲ ประสิทธิภาพย้อนหลัง 1 ปี</div>
                    </div>
                """, unsafe_allow_html=True)

            # กล่องที่ 3: ดัชนี RSI
            with m_col3:
                st.markdown(f"""
                    <div class="premium-metric-card">
                        <div class="metric-label">⚡ ดัชนี RSI (14 วัน)</div>
                        <div class="metric-value">{rsi_curr:.2f}</div>
                        <div class="metric-delta" style="color: {rsi_text_color};">{rsi_metric_label}</div>
                    </div>
                """, unsafe_allow_html=True)
            
            # กล่องที่ 4: ระบบแนะนำการลงทุน (✨ เพิ่มระบบ Neon Glow แผ่ออร่าตามสีคำแนะนำโดยอัตโนมัติ)
            with m_col4: 
                st.markdown(f"""
                    <div class="premium-metric-card" style="border-left: 5px solid {advice_color}; padding-left: 16px; box-shadow: 0 0 15px {advice_color}1a;">
                        <div class="metric-label" style="color: {advice_color}; font-weight: 700;">🤖 ระบบแนะนำการลงทุน</div>
                        <div class="metric-value" style="font-size: 1.35rem; font-weight: 700; margin-top: 6px; color: var(--text-color);">{advice_text}</div>
                        <div class="metric-delta" style="opacity: 0.5;">วิเคราะห์เทรนด์แบบระบบควอนต์</div>
                    </div>
                """, unsafe_allow_html=True)
            
            st.markdown("---")
            col1, col2 = st.columns([1.0, 1.3]) 
            
            with col1:
                with st.container(border=True):
                    if is_etf:
                        st.subheader("📋 ข้อมูลและขนาดกองทุน")
                        st.markdown(f"""
                            <div class="financial-row"><span class="financial-label">Total Assets (ขนาดกองทุน)</span><span class="financial-value">{format_number(info.get('totalAssets', 0))}</span></div>
                            <div class="financial-row"><span class="financial-label">ราคา NAV (มูลค่าจริง)</span><span class="financial-value">${info.get('navPrice', current_price):.2f}</span></div>
                            <div class="financial-row"><span class="financial-label">ผู้บริหารจัดการกองทุน</span><span class="financial-value">{info.get('fundFamily', '-')}</span></div>
                        """, unsafe_allow_html=True)
                    else:
                        st.subheader("📋 ปัจจัยพื้นฐาน & งบการเงิน")
                        net_income, profit_margin, rev_growth = info.get('netIncomeToCommon', 0), info.get('profitMargins', 0)*100 if info.get('profitMargins') else 0, info.get('revenueGrowth', 0)*100 if info.get('revenueGrowth') else 0
                        trailing_pe, eps_trailing = info.get('trailingPE', 0), info.get('trailingEps', 0)
                        total_cash, total_debt = info.get('totalCash', 0) or 0, info.get('totalDebt', 0) or 0
                        
                        inc_color = '#10B981' if net_income>=0 else '#EF4444'
                        margin_color = '#10B981' if profit_margin>=0 else '#EF4444'
                        growth_color = '#10B981' if rev_growth>=0 else '#EF4444'
                        debt_color = '#10B981' if total_cash>=total_debt else '#EF4444'
                        debt_suffix = ' 🟢' if total_cash>=total_debt else ' ⚠️'

                        st.markdown(f"""
                            <div class="financial-row"><span class="financial-label">Market Cap (มูลค่าบริษัท)</span><span class="financial-value">{format_number(info.get('marketCap', 0))}</span></div>
                            <div class="financial-row"><span class="financial-label">รายได้รวมทั้งหมด</span><span class="financial-value">{format_number(info.get('totalRevenue', 0))}</span></div>
                            <div class="financial-row"><span class="financial-label">การเติบโตของรายได้ (YoY)</span><span class="financial-value" style="color: {growth_color};">{rev_growth:.2f}%</span></div>
                            <div class="financial-row"><span class="financial-label">รายได้สุทธิ (กำไร/ขาดทุน)</span><span class="financial-value" style="color: {inc_color};">{format_number(net_income)}</span></div>
                            <div class="financial-row"><span class="financial-label">อัตรากำไรสุทธิ (%)</span><span class="financial-value" style="color: {margin_color};">{profit_margin:.2f}%</span></div>
                            <div class="financial-row"><span class="financial-label">กำไรต่อหุ้น (EPS)</span><span class="financial-value">{eps_trailing:.2f}</span></div>
                            <div class="financial-row"><span class="financial-label">P/E Ratio</span><span class="financial-value">{f'{trailing_pe:.2f}' if trailing_pe else 'N/A'}</span></div>
                            <div class="financial-row"><span class="financial-label">PEG Ratio</span><span class="financial-value">{f"{info.get('pegRatio', '-'):.2f}" if info.get('pegRatio') else 'N/A'}</span></div>
                            <div class="financial-row"><span class="financial-label">คลังเงินสดรวมทั้งหมด</span><span class="financial-value" style="color: #10B981;">{format_number(total_cash)}</span></div>
                            <div class="financial-row"><span class="financial-label">ภาระหนี้สินทั้งหมด</span><span class="financial-value" style="color: {debt_color};">{format_number(total_debt)}{debt_suffix}</span></div>
                        """, unsafe_allow_html=True)
                
                with st.container(border=True):
                    st.subheader("💰 นโยบายการจ่ายเงินปันผล")
                    st.markdown(f"""
                        <div class="financial-row"><span class="financial-label">เงินปันผลรวมรอบปีล่าสุด</span><span class="financial-value">{f"${dividend_rate:.2f}" if isinstance(dividend_rate, (int, float)) and dividend_rate > 0 else dividend_rate}</span></div>
                        <div class="financial-row"><span class="financial-label">อัตราผลตอบแทนปันผล (%)</span><span class="financial-value" style="color: #10B981;">{f"{dividend_yield:.2f}%" if dividend_yield else "-"}</span></div>
                        <div class="financial-row"><span class="financial-label">วันที่ขึ้นเครื่องหมายปันผล (Ex-Date)</span><span class="financial-value">{ex_div_date}</span></div>
                    """, unsafe_allow_html=True)
            
            with col2:
                with st.container(border=True):
                    st.subheader("⚡ กรอบราคากลยุทธ์แนวรับแนวต้าน")
                    target_price = info.get('targetMedianPrice')
                    upside_html = ""
                    if target_price:
                        upside_pct = ((target_price - current_price) / current_price) * 100
                        up_color = '#10B981' if upside_pct >= 0 else '#EF4444'
                        upside_html = f'<div class="financial-row"><span class="financial-label">ราคาเป้าหมายเฉลี่ย (Wall Street)</span><span class="financial-value">${target_price:.2f} (<span style="color:{up_color};">{upside_pct:+.2f}%</span>)</span></div>'
                    
                    st.markdown(f"""
                        <div class="financial-row"><span class="financial-label">Volume ซื้อขายวันนี้</span><span class="financial-value">{format_number(hist['Volume'].iloc[-1])}</span></div>
                        <div class="financial-row"><span class="financial-label">ดัชนีแรงซื้อขาย RSI (14 วัน)</span><span class="financial-value" style="color: {rsi_text_color};">{rsi_curr:.2f} ({rsi_metric_label})</span></div>
                        <div class="financial-row"><span class="financial-label">แนวรับ / แนวต้าน (ระยะสั้น 20 วัน)</span><span class="financial-value">${support_20d:.2f} / ${resistance_20d:.2f}</span></div>
                        <div class="financial-row"><span class="financial-label">แนวรับ / แนวต้าน (ระยะยาว 1 ปี)</span><span class="financial-value">${support_1y:.2f} / ${resistance_1y:.2f}</span></div>
                        {upside_html}
                    """, unsafe_allow_html=True)
                
                with st.container(border=True):
                    st.subheader("📐 โซนแนวรับทางจิตวิทยา (Fibonacci Retracement)")
                    st.markdown(f"""
                        <div class="financial-row"><span class="financial-label">แนวรับแรก (38.2% - โซนย่อตัวระยะสั้น)</span><span class="financial-value" style="color: #10B981;">${fib_382:.2f}</span></div>
                        <div class="financial-row"><span class="financial-label">แนวรับสำคัญ (50.0% - จุดตัดสินแนวโน้มหลัก)</span><span class="financial-value" style="color: #F59E0B;">${fib_500:.2f}</span></div>
                        <div class="financial-row"><span class="financial-label">แนวรับแข็งแกร่ง (61.8% - โซนช้อนซื้อกลุ่มสถาบัน)</span><span class="financial-value" style="color: #3B82F6;">${fib_618:.2f}</span></div>
                    """, unsafe_allow_html=True)
                
                with st.container(border=True):
                    st.subheader("🛡️ เส้นค่าเฉลี่ยเทรนด์ราคา (Moving Averages)")
                    ma_col1, ma_col2, ma_col3 = st.columns(3)
                    with ma_col1: st.markdown(f"**EMA 20 (สั้น)**\n`${ema20_curr:.2f}`")
                    with ma_col2: st.markdown(f"**EMA 50 (กลาง)**\n`${ema50_curr:.2f}`")
                    with ma_col3: st.markdown(f"**SMA 200 (ใหญ่)**\n`${sma200_curr:.2f}`")
                    
                    fig = go.Figure(data=[go.Candlestick(
                        x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'], name='ราคา',
                        increasing_line_color='#10B981', decreasing_line_color='#EF4444',
                        increasing_fillcolor='rgba(16, 185, 129, 0.15)', decreasing_fillcolor='rgba(239, 68, 68, 0.15)'
                    )])
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA20'], mode='lines', line=dict(color='#F59E0B', width=1.5), name='EMA20'))
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA50'], mode='lines', line=dict(color='#EF4444', width=1.5), name='EMA50'))
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA200'], mode='lines', line=dict(color='#3B82F6', width=2, dash='dash'), name='SMA200'))
                    
                    fig.update_layout(
                        xaxis_rangeslider_visible=False, height=280, margin=dict(l=5, r=5, t=5, b=5),
                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                        xaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.06)'),
                        yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.06)'),
                        dragmode='pan' 
                    )
                    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True, 'displayModeBar': True})

            if news_items:
                st.markdown("---")
                st.subheader("📰 สรุปข่าวเด่นล่าสุด (Live Stock News)")
                for it in news_items:
                    translated_url = f"https://translate.google.com/translate?sl=en&tl=th&u={requests.utils.quote(it['link'])}"
                    st.markdown(f"""
                        <div class="premium-news-card">
                            <h4 style="margin-top:0; margin-bottom:10px;">
                                <a href="{it['link']}" target="_blank" style="text-decoration:none; color:#1D4ED8;">{it['thai_title']}</a>
                            </h4>
                            <p style="font-size:0.95rem; color:var(--text-color); opacity:0.88; line-height:1.6; margin-bottom:14px; text-align:justify;">
                                {it['thai_summary'] if it['thai_summary'] else 'ไม่มีข้อมูลสรุปคำโปรยข่าวเบื้องต้น กรุณาคลิกลิงก์ด้านล่างเพื่อเข้าสู่อ่านเนื้อหาฉบับเต็ม...'}
                            </p>
                            <div style="font-size:0.82rem; color:gray; border-top:1px solid var(--border-color); padding-top:10px;">
                                🕒 <b>เวลาเผยแพร่:</b> {it['time']} | ✍️ สำนักข่าว: {it['pub']} | 📝 หัวข้อดั้งเดิม: <i>{it['title']}</i>
                            </div>
                            <a href="{translated_url}" target="_blank" class="premium-news-link">🇹🇭 แปลฉบับเต็มโดย Google Translate ↗</a>
                        </div>
                    """, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดทางเทคนิค: {e}")