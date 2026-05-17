import streamlit as st
import yfinance as yf
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

# 1. ตั้งค่าหน้าจอแบบกว้างพิเศษหน้าเดียวจบ
st.set_page_config(page_title="Stockify Pro Ultimate", page_icon="📈", layout="wide")

# --- 🎨 ระบบ CSS Dynamic Variables (ปรับตามโหมด Light/Dark ของคอมพิวเตอร์อัตโนมัติ) ---
st.markdown("""
    <style>
        .adaptive-advice-box {
            padding: 12px; 
            background-color: var(--secondary-background-color); 
            border-radius: 6px; 
            margin-top: 5px;
            border: 1px solid var(--border-color);
        }
    </style>
""", unsafe_allow_html=True)

st.title("📈 Stockify Pro - Dashboard")
st.write("ระบบตรวจจับสัญญาณซื้อขาย งบการเงิน และวิเคราะห์กรอบแนวรับแนวต้านระยะสำคัญ")

# 2. ช่องรับชื่อหุ้น (ล้างช่องว่างและทำเป็นตัวพิมพ์ใหญ่)
ticker_input = st.text_input("สัญลักษณ์หุ้น หรือ ETF (เช่น NVDA, RKLB, JEPQ, QQQI, VOO):", value="NVDA").upper().strip()

# 3. ฟังก์ชันแปลงหน่วยตัวเลข (ล้าน/พันล้าน/ล้านล้าน)
def format_number(val):
    if val is None or pd.isna(val):
        return "-"
    if abs(val) >= 1_000_000_000_000:
        return f"{val / 1_000_000_000_000:.2f}T"
    if abs(val) >= 1_000_000_000:
        return f"{val / 1_000_000_000:.2f}B"
    if abs(val) >= 1_000_000:
        return f"{val / 1_000_000:.2f}M"
    return f"{val:.2f}"

# 4. เริ่มระบบประมวลผลข้อมูล
if ticker_input:
    with st.spinner('กำลังประมวลผลข้อมูลโครงสร้างมินิมอลพรีเมียม...'):
        try:
            session = requests.Session()
            session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'})
            stock = yf.Ticker(ticker_input, session=session)
            info = stock.info
            # ดึงข้อมูล 1 ปีตามคำขอ เพื่อความรวดเร็วในการโหลดข้อมูลสูงสุด
            hist = stock.history(period="1y")
            
            if hist.empty:
                st.error("ไม่พบข้อมูลสัญลักษณ์นี้ กรุณาตรวจสอบอีกครั้ง")
            else:
                current_price = hist['Close'].iloc[-1]
                prev_price = hist['Close'].iloc[-2]
                price_change = current_price - prev_price
                price_change_pct = (price_change / prev_price) * 100
                
                asset_type = info.get('quoteType', 'EQUITY')
                is_etf = asset_type == 'ETF'
                
                # --- คำนวณอินดิเคเตอร์เทคนิคอล ---
                hist['EMA20'] = hist['Close'].ewm(span=20, adjust=False).mean()
                hist['EMA50'] = hist['Close'].ewm(span=50, adjust=False).mean()
                hist['SMA200'] = hist['Close'].rolling(window=200).mean()
                
                ema20_curr = hist['EMA20'].iloc[-1]
                ema50_curr = hist['EMA50'].iloc[-1]
                sma200_curr = hist['SMA200'].iloc[-1] if not pd.isna(hist['SMA200'].iloc[-1]) else current_price
                
                # RSI 14
                delta = hist['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rsi_curr = (100 - (100 / (1 + (gain / loss)))).iloc[-1]
                
                # --- 🎯 กรอบแนวรับแนวต้านคัดมาเฉพาะเนื้อๆ 20 วัน กับ 1 ปี ตามสั่ง ---
                support_20d = hist['Low'].tail(20).min()
                resistance_20d = hist['High'].tail(20).max()
                
                support_1y = info.get('fiftyTwoWeekLow') or hist['Low'].min()
                resistance_1y = info.get('fiftyTwoWeekHigh') or hist['High'].max()
                
                # Fibonacci (อิงฐานกรอบเวลา 1 ปี)
                fib_diff = resistance_1y - support_1y
                fib_382 = resistance_1y - (0.382 * fib_diff)
                fib_500 = resistance_1y - (0.500 * fib_diff)
                fib_618 = resistance_1y - (0.618 * fib_diff)
                
                # --- 💰 คำนวณปันผลจากบัญชีจริงย้อนหลัง 365 วัน ---
                dividend_yield = 0.0
                annual_div_sum = 0.0
                ex_div_date = "-"
                
                try:
                    actions = stock.actions
                    if actions is not None and 'Dividends' in actions.columns:
                        div_events = actions[actions['Dividends'] > 0]
                        if not div_events.empty:
                            ex_div_date = div_events.index[-1].strftime('%d-%m-%Y') + " (ล่าสุด)"
                            one_year_ago = pd.Timestamp.now(tz=div_events.index.tz) - pd.Timedelta(days=365)
                            recent_divs = div_events[div_events.index >= one_year_ago]
                            annual_div_sum = recent_divs['Dividends'].sum()
                except:
                    pass

                if annual_div_sum > 0:
                    dividend_rate = annual_div_sum
                    dividend_yield = (annual_div_sum / current_price) * 100
                else:
                    dividend_rate = info.get('dividendRate') or info.get('trailingAnnualDividendRate') or 0
                    div_yield_raw = info.get('dividendYield') or info.get('yield') or info.get('trailingAnnualDividendYield') or 0
                    dividend_yield = div_yield_raw if div_yield_raw > 1 else div_yield_raw * 100
                    if dividend_yield > 40.0:
                        dividend_yield = div_yield_raw

                # ติดป้ายประเภทสินทรัพย์
                if is_etf:
                    if dividend_yield >= 7.0:
                        asset_label = "กองทุน ETF ปันผลสูง / Covered Call 💰"
                        label_color = "green"
                    else:
                        asset_label = "กองทุนรวมดัชนีทั่วไป (Growth/Index ETF) 📦"
                        label_color = "blue"
                else:
                    if dividend_yield >= 4.0:
                        asset_label = "หุ้นรายตัวปันผลสูง (High-Dividend Stock) 💎"
                        label_color = "green"
                    else:
                        asset_label = "หุ้นรายตัว / สินทรัพย์เติบโต (Growth Equity) 🏢"
                        label_color = "orange"

                # ระบบประมวลคำแนะนำภาษาไทย
                if current_price > sma200_curr and current_price > ema50_curr and rsi_curr < 55:
                    advice_text = "ซื้อทันที (Strong Buy) 🚀"
                    advice_color = "#10B981"
                elif current_price > sma200_curr and rsi_curr <= 68:
                    advice_text = "ซื้อ (Buy) 🟢"
                    advice_color = "#10B981"
                elif current_price <= sma200_curr and rsi_curr < 35:
                    advice_text = "ทยอยซื้อสะสม (Accumulate Buy) 🟡"
                    advice_color = "#F59E0B"
                elif rsi_curr > 73:
                    advice_text = "ถือ / ระวังแรงขายทำกำไรระยะสั้น (Hold) 🟠"
                    advice_color = "#F97316"
                else:
                    advice_text = "ถือเพื่อรอดูแนวโน้ม (Hold) 🔵"
                    advice_color = "#3B82F6"
                
                if rsi_curr >= 70.0:
                    rsi_metric_label = "🚨 อันตราย (ซื้อมากไป Overbought)"
                    rsi_text_color = "red"
                elif rsi_curr <= 30.0:
                    rsi_metric_label = "🟢 ปลอดภัย (ขายมากไป โซนช้อนซื้อ)"
                    rsi_text_color = "green"
                else:
                    rsi_metric_label = "🟡 ปกติ (อยู่ช่วงพักตัว 30-70)"
                    rsi_text_color = "orange"

                st.write(f"### 📊 **{info.get('longName', ticker_input)}**")
                st.markdown(f"**ประเภทสินทรัพย์วิเคราะห์โดยบอต** | :{label_color}[**{asset_label}**]")
                
                m_col1, m_col2, m_col3 = st.columns(3)
                with m_col1:
                    st.metric(label="💵 ราคาปัจจุบัน (USD)", value=f"${current_price:.2f}", delta=f"{price_change_pct:.2f}%")
                with m_col2:
                    st.metric(label="⚡ ดัชนี RSI (14 วัน)", value=f"{rsi_curr:.2f}", delta=rsi_metric_label, delta_color="off")
                with m_col3:
                    st.markdown(f"""
                        <div class='adaptive-advice-box' style='border-left: 5px solid {advice_color};'>
                            <span style='color: var(--text-color); opacity: 0.6; font-size: 13px;'>🤖 ระบบแนะนำการลงทุน</span><br>
                            <strong style='color: var(--text-color); font-size: 18px;'>{advice_text}</strong>
                        </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("---")
                
                col1, col2 = st.columns([1.1, 1.2])
                
                with col1:
                    with st.container(border=True):
                        if is_etf:
                            st.subheader("📋 ข้อมูลและขนาดกองทุน")
                            st.markdown(f"**Total Assets (ขนาดกองทุน)** | `{format_number(info.get('totalAssets', 0))}`")
                            st.markdown(f"**ราคา NAV (มูลค่าจริง)** | `${info.get('navPrice', current_price):.2f}`")
                            st.markdown(f"**ผู้บริหารจัดการกองทุน** | `{info.get('fundFamily', '-')}`")
                        else:
                            st.subheader("📋 ปัจจัยพื้นฐาน & งบการเงิน")
                            net_income = info.get('netIncomeToCommon', 0)
                            profit_margin = info.get('profitMargins', 0) * 100 if info.get('profitMargins') else 0
                            rev_growth = info.get('revenueGrowth', 0) * 100 if info.get('revenueGrowth') else 0
                            trailing_pe = info.get('trailingPE', 0)
                            eps_trailing = info.get('trailingEps', 0)
                            
                            total_cash = info.get('totalCash', 0) if info.get('totalCash') is not None else 0
                            total_debt = info.get('totalDebt', 0) if info.get('totalDebt') is not None else 0
                            
                            growth_color = "green" if rev_growth >= 0 else "red"
                            income_color = "green" if net_income >= 0 else "red"
                            margin_color = "green" if profit_margin >= 0 else "red"
                            eps_color = "green" if eps_trailing >= 0 else "red"
                            
                            debt_color = "green" if total_cash >= total_debt else "red"
                            debt_icon = "🟢" if total_cash >= total_debt else "⚠️"
                            
                            st.markdown(f"**Market Cap (มูลค่าบริษัท)** | `{format_number(info.get('marketCap', 0))}`")
                            st.markdown(f"**รายได้รวมทั้งหมด** | `{format_number(info.get('totalRevenue', 0))}`")
                            st.markdown(f"**การเติบโตของรายได้ (YoY)** | :{growth_color}[{rev_growth:.2f}%]")
                            st.markdown(f"**รายได้สุทธิ (กำไร/ขาดทุน)** | :{income_color}[{format_number(net_income)}]")
                            st.markdown(f"**อัตรากำไรสุทธิ (%)** | :{margin_color}[{profit_margin:.2f}%]")
                            st.markdown(f"**กำไรต่อหุ้น (EPS)** | :{eps_color}[{eps_trailing:.2f}]")
                            st.markdown(f"**P/E Ratio** | `{trailing_pe:.2f}`" if trailing_pe else "**P/E Ratio** | `N/A`")
                            st.markdown(f"**PEG Ratio** | `{info.get('pegRatio', '-'):.2f}`" if info.get('pegRatio') else "**PEG Ratio** | `N/A`")
                            st.markdown(f"**คลังเงินสดรวมทั้งหมด** | `🟢 {format_number(total_cash)}`" if total_cash > 0 else f"**คลังเงินสดรวมทั้งหมด** | `-`")
                            st.markdown(f"**ภาระหนี้สินทั้งหมด** | :{debt_color}[**{format_number(total_debt)} {debt_icon}**]")
                    
                    with st.container(border=True):
                        st.subheader("💰 นโยบายการจ่ายเงินปันผล")
                        if isinstance(dividend_rate, (int, float)) and dividend_rate > 0:
                            st.markdown(f"**เงินปันผลรวมรอบปีล่าสุด** | `${dividend_rate:.2f}`")
                        else:
                            st.markdown(f"**เงินปันผลรวมรอบปี** | `{dividend_rate}`")
                        st.markdown(f"**อัตราผลตอบแทนปันผล (%)** | `🟢 {dividend_yield:.2f}%`" if dividend_yield else "**อัตราผลตอบแทนปันผล (%)** | `-`")
                        st.markdown(f"**วันที่ขึ้นเครื่องหมายปันผล (Ex-Date)** | `{ex_div_date}`")
                
                with col2:
                    # 📋 กล่องสรุปขอบเขตราคาแบบคลีนตา สแกนไว (20 วัน ข้ามไป 1 ปี)
                    with st.container(border=True):
                        st.subheader("⚡ กรอบราคากลยุทธ์แนวรับแนวต้าน")
                        st.markdown(f"**Volume ซื้อขายวันนี้** | `{format_number(hist['Volume'].iloc[-1])}`")
                        st.markdown(f"**ดัชนีแรงซื้อขาย RSI (14 วัน)** | :{rsi_text_color}[**{rsi_curr:.2f} {rsi_metric_label}**]")
                        st.markdown("---")
                        st.markdown(f"**แนวรับ / แนวต้าน (ระยะสั้น 20 วัน)** | `${support_20d:.2f}` / `${resistance_20d:.2f}`")
                        st.markdown(f"**แนวรับ / แนวต้าน (ระยะยาว 1 ปี)** | `${support_1y:.2f}` / `${resistance_1y:.2f}`")
                    
                    with st.container(border=True):
                        st.subheader("📐 ด่านจิตวิทยาคัดกรองการย่อตัว (Fibonacci)")
                        st.markdown(f"**แนวรับแรก (38.2% - ย่อตัวระยะสั้น)** | `${fib_382:.2f}`")
                        st.markdown(f"**แนวรับกึ่งกลาง (50.0% - ด่านวัดใจ)** | `${fib_500:.2f}`")
                        st.markdown(f"**แนวรับเหล็กกองทุน (61.8% - โซนทองคำ)** | `${fib_618:.2f}`")
                    
                    with st.container(border=True):
                        st.subheader("🛡️ เส้นค่าเฉลี่ยเทรนด์ราคา (Moving Averages)")
                        ma_col1, ma_col2, ma_col3 = st.columns(3)
                        with ma_col1:
                            st.markdown(f"**EMA 20 (สั้น)**\n`${ema20_curr:.2f}`")
                        with ma_col2:
                            st.markdown(f"**EMA 50 (กลาง)**\n`${ema50_curr:.2f}`")
                        with ma_col3:
                            st.markdown(f"**SMA 200 (ใหญ่)**\n`${sma200_curr:.2f}`")
                        
                        # วาดกราฟแท่งเทียนรอบ 1 ปีแบบมาตรฐาน คลีนตาที่สุด ไม่รกเส้นประ
                        fig = go.Figure(data=[go.Candlestick(
                            x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'], name='ราคา'
                        )])
                        fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA20'], mode='lines', line=dict(color='orange', width=1), name='EMA20'))
                        fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA50'], mode='lines', line=dict(color='red', width=1.5), name='EMA50'))
                        fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA200'], mode='lines', line=dict(color='blue', width=2, dash='dash'), name='SMA200'))
                        fig.update_layout(xaxis_rangeslider_visible=False, height=250, margin=dict(l=5, r=5, t=5, b=5))
                        st.plotly_chart(fig, use_container_width=True)
                    
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดทางเทคนิค: {e}")