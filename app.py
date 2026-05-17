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

st.markdown("""
    <style>
        .adaptive-advice-box { padding: 12px; background-color: var(--secondary-background-color); border-radius: 6px; margin-top: 5px; border: 1px solid var(--border-color); }
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

# 🤖 ระบบแปลเดี่ยว (เอาไว้เป็นแผนสำรองฉุกเฉิน)
def translate_google_single(text):
    if not text: return text
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=th&dt=t&q={requests.utils.quote(text)}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200: return "".join([s[0] for s in res.json()[0] if s[0]])
    except: pass
    return text  

# ⚡ [ฟีเจอร์ใหม่ความเร็วแสง] มัดรวมข้อความทั้งหมดส่งแปลรอบเดียวดึงสปีดสูงสุด 0.3 วินาที
@st.cache_data(ttl=1800, show_spinner=False) 
def translate_google_batch(texts_tuple):
    texts_list = list(texts_tuple)
    if not texts_list: return []
    
    # ล้างเครื่องหมายขึ้นบรรทัดใหม่จากต้นทางก่อนเพื่อป้องกันข้อความคลาดเคลื่อน
    cleaned_texts = [t.replace("\n", " ").strip() for t in texts_list]
    payload = "\n".join(cleaned_texts)
    
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=th&dt=t&q={requests.utils.quote(payload)}"
        res = requests.get(url, timeout=8)
        if res.status_code == 200:
            raw_segments = res.json()[0]
            # รวมชิ้นส่วนคำแปลทั้งหมดเข้าด้วยกัน โดยระบบจะคงเครื่องหมายตัวคั่น \n ไว้ให้ครบถ้วน
            full_translated = "".join([seg[0] for seg in raw_segments if seg[0]])
            
            translated_list = full_translated.split("\n")
            # ถ้าจำนวนแถวที่ส่งไปและกลับมาตรงกันเป๊ะ ให้ส่งข้อมูลกลับไปใช้งานได้เลย
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
            return_1y_color = "normal" if return_1y_pct >= 0 else "inverse"
            
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
            
            if rsi_curr >= 70.0: rsi_metric_label, rsi_text_color = "🚨 อันตราย (ซื้อมากไป Overbought)", "red"
            elif rsi_curr <= 30.0: rsi_metric_label, rsi_text_color = "🟢 ปลอดภัย (ขายมากไป โซนช้อนซื้อ)", "green"
            else: rsi_metric_label, rsi_text_color = "🟡 ปกติ (อยู่ช่วงพักตัว 30-70)", "orange"

            # --- 📦 ดึงและจัดแจงข้อมูลข่าวสารหลังบ้านไว้ก่อน ---
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

            # --- 🚚 [คำนวณแพ็กเกจพัสดุ] รวมข่าวและลักษณะธุรกิจส่งแปลในช็อตเดียว ---
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

            # กระจายคำแปลสปีดสายฟ้ากลับลงกล่องข้อมูล
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

            # --- 🖥️ แสดงผล UI ทั้งหน้าจอพร้อมกันในอึดใจเดียว ---
            st.write(f"### 📊 **{info.get('longName', ticker_input)}**")
            st.markdown(f"**ประเภทสินทรัพย์** | :{label_color}[**{asset_label}**]")
            
            if has_summary:
                with st.expander("📖 ดูข้อมูลลักษณะธุรกิจ (Company Summary)"):
                    st.markdown(f"<p style='color: var(--text-color); font-size: 0.95rem; line-height: 1.6; text-align: justify;'>{thai_biz_summary}</p>", unsafe_allow_html=True)
                    try:
                        earnings_dates, cal = [], stock.calendar
                        if isinstance(cal, dict) and 'Earnings Date' in cal: earnings_dates = cal['Earnings Date']
                        elif hasattr(cal, 'index') and 'Earnings Date' in cal.index: earnings_dates = cal.loc['Earnings Date'].values
                        if not earnings_dates:
                            n_earn = info.get('earningsTimestamp') or info.get('earningsTimestampStart')
                            if n_earn: earnings_dates = [datetime.fromtimestamp(n_earn)]
                        if earnings_dates:
                            date_strs = list(dict.fromkeys([d.strftime('%d-%m-%Y') if hasattr(d, 'strftime') else (datetime.fromtimestamp(d).strftime('%d-%m-%Y') if isinstance(d, (int, float)) and d > 0 else str(d)[:10]) for d in earnings_dates if d and not str(d).startswith('NaT')]))
                            if date_strs: st.info(f"📅 **Earnings Announcement:** วันประกาศงบการเงินงวดถัดไปโดยประมาณ: `{', '.join(date_strs)}` (โปรดระวังความผันผวนของราคา)")
                    except: pass

            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            with m_col1: st.metric(label="💵 ราคาปัจจุบัน (USD)", value=f"${current_price:.2f}", delta=f"{price_change_pct:.2f}%")
            with m_col2: st.metric(label="📈 ผลตอบแทนรอบ 1 ปี", value=f"{return_1y_pct:+.2f}%", delta="ประสิทธิภาพย้อนหลัง 1 ปี", delta_color=return_1y_color)
            with m_col3: st.metric(label="⚡ ดัชนี RSI (14 วัน)", value=f"{rsi_curr:.2f}", delta=rsi_metric_label, delta_color="off")
            with m_col4: st.markdown(f"<div class='adaptive-advice-box' style='border-left: 5px solid {advice_color};'><span style='color: var(--text-color); opacity: 0.6; font-size: 13px;'>🤖 ระบบแนะนำการลงทุน</span><br><strong style='color: var(--text-color); font-size: 18px;'>{advice_text}</strong></div>", unsafe_allow_html=True)
            
            st.markdown("---")
            col1, col2 = st.columns([1.1, 1.2])
            
            with col1:
                with st.container(border=True):
                    if is_etf:
                        st.subheader("📋 ข้อมูลและขนาดกองทุน")
                        st.markdown(f"**Total Assets (ขนาดกองทุน)** | `{format_number(info.get('totalAssets', 0))}`\n\n**ราคา NAV (มูลค่าจริง)** | `${info.get('navPrice', current_price):.2f}`\n\n**ผู้บริหารจัดการกองทุน** | `{info.get('fundFamily', '-')}`")
                    else:
                        st.subheader("📋 ปัจจัยพื้นฐาน & งบการเงิน")
                        net_income, profit_margin, rev_growth = info.get('netIncomeToCommon', 0), info.get('profitMargins', 0)*100 if info.get('profitMargins') else 0, info.get('revenueGrowth', 0)*100 if info.get('revenueGrowth') else 0
                        trailing_pe, eps_trailing = info.get('trailingPE', 0), info.get('trailingEps', 0)
                        total_cash, total_debt = info.get('totalCash', 0) or 0, info.get('totalDebt', 0) or 0
                        st.markdown(f"**Market Cap (มูลค่าบริษัท)** | `{format_number(info.get('marketCap', 0))}`\n\n**รายได้รวมทั้งหมด** | `{format_number(info.get('totalRevenue', 0))}`\n\n**การเติบโตของรายได้ (YoY)** | :{'green' if rev_growth>=0 else 'red'}[{rev_growth:.2f}%]\n\n**รายได้สุทธิ (กำไร/ขาดทุน)** | :{'green' if net_income>=0 else 'red'}[{format_number(net_income)}]\n\n**อัตรากำไรสุทธิ (%)** | :{'green' if profit_margin>=0 else 'red'}[{profit_margin:.2f}%]\n\n**กำไรต่อหุ้น (EPS)** | :{'green' if eps_trailing>=0 else 'red'}[{eps_trailing:.2f}]\n\n**P/E Ratio** | `{trailing_pe:.2f}`" if trailing_pe else "**P/E Ratio** | `N/A`")
                        st.markdown(f"**PEG Ratio** | `{info.get('pegRatio', '-'):.2f}`" if info.get('pegRatio') else "**PEG Ratio** | `N/A`")
                        st.markdown(f"**คลังเงินสดรวมทั้งหมด** | `🟢 {format_number(total_cash)}`" if total_cash > 0 else "**คลังเงินสดรวมทั้งหมด** | `-`")
                        st.markdown(f"**ภาระหนี้สินทั้งหมด** | :{'green' if total_cash>=total_debt else 'red'}[**{format_number(total_debt)} {'🟢' if total_cash>=total_debt else '⚠️'}**]")
                
                with st.container(border=True):
                    st.subheader("💰 นโยบายการจ่ายเงินปันผล")
                    st.markdown(f"**เงินปันผลรวมรอบปีล่าสุด** | `${dividend_rate:.2f}`" if isinstance(dividend_rate, (int, float)) and dividend_rate > 0 else f"**เงินปันผลรวมรอบปี** | `{dividend_rate}`")
                    st.markdown(f"**อัตราผลตอบแทนปันผล (%)** | `🟢 {dividend_yield:.2f}%`" if dividend_yield else "**อัตราผลตอบแทนปันผล (%)** | `-`")
                    st.markdown(f"**วันที่ขึ้นเครื่องหมายปันผล (Ex-Date)** | `{ex_div_date}`")
            
            with col2:
                with st.container(border=True):
                    st.subheader("⚡ กรอบราคากลยุทธ์แนวรับแนวต้าน")
                    st.markdown(f"**Volume ซื้อขายวันนี้** | `{format_number(hist['Volume'].iloc[-1])}`\n\n**ดัชนีแรงซื้อขาย RSI (14 วัน)** | :{rsi_text_color}[**{rsi_curr:.2f} {rsi_metric_label}**]\n\n---\n\n**แนวรับ / แนวต้าน (ระยะสั้น 20 วัน)** | `${support_20d:.2f}` / `${resistance_20d:.2f}`\n\n**แนวรับ / แนวต้าน (ระยะยาว 1 ปี)** | `${support_1y:.2f}` / `${resistance_1y:.2f}`")
                    target_price = info.get('targetMedianPrice')
                    if target_price: st.markdown(f"**ราคาเป้าหมายโดยเฉลี่ย (Wall Street)** | `${target_price:.2f}` (Upside คงเหลือ: :{'green' if ((target_price - current_price) / current_price) * 100>=0 else 'red'}[**{((target_price - current_price) / current_price) * 100:+.2f}%**])")
                
                with st.container(border=True):
                    st.subheader("📐 ด่านจิตวิทยาคัดกรองการย่อตัว (Fibonacci)")
                    st.markdown(f"**แนวรับแรก (38.2% - ย่อตัวระยะสั้น)** | `${fib_382:.2f}`\n\n**แนวรับกึ่งกลาง (50.0% - ด่านวัดใจ)** | `${fib_500:.2f}`\n\n**แนวรับเหล็กกองทุน (61.8% - โซนทองคำ)** | `${fib_618:.2f}`")
                
                with st.container(border=True):
                    st.subheader("🛡️ เส้นค่าเฉลี่ยเทรนด์ราคา (Moving Averages)")
                    ma_col1, ma_col2, ma_col3 = st.columns(3)
                    with ma_col1: st.markdown(f"**EMA 20 (สั้น)**\n`${ema20_curr:.2f}`")
                    with ma_col2: st.markdown(f"**EMA 50 (กลาง)**\n`${ema50_curr:.2f}`")
                    with ma_col3: st.markdown(f"**SMA 200 (ใหญ่)**\n`${sma200_curr:.2f}`")
                    fig = go.Figure(data=[go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'], name='ราคา')])
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA20'], mode='lines', line=dict(color='orange', width=1), name='EMA20'))
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA50'], mode='lines', line=dict(color='red', width=1.5), name='EMA50'))
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA200'], mode='lines', line=dict(color='blue', width=2, dash='dash'), name='SMA200'))
                    fig.update_layout(xaxis_rangeslider_visible=False, height=250, margin=dict(l=5, r=5, t=5, b=5))
                    st.plotly_chart(fig, use_container_width=True)

            if news_items:
                st.markdown("---")
                st.subheader("📰 สรุปข่าวเด่นล่าสุด (Live Stock News)")
                for it in news_items:
                    translated_url = f"https://translate.google.com/translate?sl=en&tl=th&u={requests.utils.quote(it['link'])}"
                    with st.container(border=True):
                        st.markdown(f"**[{it['thai_title']}]({it['link']})**")
                        st.markdown(f"<p style='font-size: 0.95rem; color: var(--text-color); opacity: 0.85;'>{it['thai_summary'] if it['thai_summary'] else 'คลิกเพื่ออ่านเนื้อหาเต็ม...'}</p>", unsafe_allow_html=True)
                        st.caption(f"🕒 **เวลา:** {it['time']} | ✍️ สำนักข่าว: {it['pub']} | 📝 ต้นฉบับ: {it['title']}")
                        st.markdown(f"[🇹🇭 คลิกอ่านฉบับเต็มแปลไทย (ผ่าน Google Translate)]({translated_url})")

        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดทางเทคนิค: {e}")