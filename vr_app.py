# vr_app.py
# 무한매수법 VR 시뮬레이터 V6 (Streamlit 버전)

import streamlit as st
import datetime
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# --- 페이지 설정 ---
st.set_page_config(page_title="VR 리밸런싱 시뮬레이터 V6", page_icon="📈", layout="wide")

st.title("📈 무한매수법 VR 백테스터 V6 (Band Visualizer)")
st.markdown("""
**회색 음영 영역(밴드)**을 벗어날 때만 매매가 실행됩니다.
그래프를 통해 내 자산이 밴드 안에서 움직이는지, 뚫고 나가는지 확인해보세요.
""")

# --- 사이드바 ---
with st.sidebar:
    st.header("⚙️ 종목 및 기간 설정")
    
    ticker_input = st.text_input("티커 입력 (예: TQQQ, SOXL)", value="TQQQ").upper()
    
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        start_date = st.date_input("시작 날짜", datetime.date(2022, 1, 1))
    with col_d2:
        end_date = st.date_input("종료 날짜", datetime.date.today())
    
    st.divider()
    st.subheader("💰 자금 설정")
    start_money = st.number_input("시작 원금 ($)", value=10000, step=1000)
    monthly_add = st.number_input("적립금 ($)", value=250, step=50)
    
    st.divider()
    st.subheader("🛡️ 로직 상세 설정")
    rebalance_period = st.radio("리밸런싱 주기", [14, 30], index=0, format_func=lambda x: f"{x}일 간격")
    
    band_pct = st.slider("허용 오차 밴드 (%)", 0.0, 10.0, 5.0, step=0.5)

# --- 탭 구성 ---
tab1, tab2 = st.tabs([f"📊 {ticker_input} 백테스트", "🧮 오늘자 매매 계산기"])

# ==============================================================================
# 탭 1: 백테스팅
# ==============================================================================
with tab1:
    if st.button("시뮬레이션 시작 🚀", type="primary"):
        with st.spinner(f"{ticker_input} 데이터 가져오는 중..."):
            # 1. 데이터 가져오기
            try:
                df = yf.download(ticker_input, start=start_date - datetime.timedelta(days=10), end=end_date + datetime.timedelta(days=5), progress=False)
                
                if len(df) == 0:
                    st.error(f"'{ticker_input}' 데이터를 찾을 수 없습니다.")
                else:
                    # yfinance 버전 이슈 대응 (MultiIndex)
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    
                    df = df[(df.index >= pd.Timestamp(start_date)) & (df.index <= pd.Timestamp(end_date))]
                    
                    if len(df) == 0:
                        st.error("선택한 기간의 데이터가 없습니다.")
                        st.stop()

                    # --- 시뮬레이션 로직 ---
                    log_data = []
                    cash_pool = float(start_money)
                    total_invested = float(start_money)
                    target_value = float(start_money)
                    last_trade_day = df.index[0]
                    
                    first_price = float(df['Close'].iloc[0]) 
                    current_qty = int(start_money / first_price)
                    cash_pool -= (current_qty * first_price)
                    
                    log_data.append({
                        "날짜": df.index[0],
                        f"{ticker_input} 가격($)": first_price,
                        "목표 가치($)": target_value,
                        "내 자산($)": current_qty * first_price,
                        "보유 수량(주)": current_qty,
                        "예수금(Pool)($)": cash_pool,
                        "매매 행동": f"첫 매수 {current_qty}주 (@${first_price:.2f})"
                    })

                    for date, row in df.iloc[1:].iterrows():
                        price = float(row['Close'])
                        my_asset_value = (current_qty * price)
                        days_diff = (date - last_trade_day).days
                        action = ""
                        
                        if days_diff >= rebalance_period:
                            target_value += monthly_add 
                            diff = target_value - my_asset_value
                            allowable_error = target_value * (band_pct / 100)
                            
                            if abs(diff) > allowable_error:
                                trade_qty = int(diff / price)
                                if trade_qty > 0:
                                    cost = trade_qty * price
                                    if cash_pool < cost:
                                        needed = cost - cash_pool
                                        total_invested += needed 
                                        cash_pool += needed      
                                        action_type = "매수(추가)"
                                    else:
                                        action_type = "매수(Pool)"
                                    current_qty += trade_qty
                                    cash_pool -= cost
                                    action = f"{action_type} {trade_qty}주 (@${price:.2f})"
                                elif trade_qty < 0:
                                    sell_qty = abs(trade_qty)
                                    earn = sell_qty * price
                                    current_qty -= sell_qty
                                    cash_pool += earn 
                                    action = f"매도 {sell_qty}주 (@${price:.2f})"
                                else:
                                    action = "관망 (수량 0)"
                            else:
                                action = f"밴드 관망 (오차 ${abs(diff):,.0f})"

                            last_trade_day = date
                            log_data.append({
                                "날짜": date,
                                f"{ticker_input} 가격($)": price,
                                "목표 가치($)": target_value,
                                "내 자산($)": current_qty * price,
                                "보유 수량(주)": current_qty,
                                "예수금(Pool)($)": cash_pool,
                                "매매 행동": action
                            })
                        else:
                             log_data.append({
                                "날짜": date,
                                f"{ticker_input} 가격($)": price,
                                "목표 가치($)": target_value,
                                "내 자산($)": current_qty * price,
                                "보유 수량(주)": current_qty,
                                "예수금(Pool)($)": cash_pool,
                                "매매 행동": ""
                            })
                    
                    # --- 결과 정리 ---
                    res_df = pd.DataFrame(log_data)
                    res_df['날짜'] = pd.to_datetime(res_df['날짜']) # 날짜 형변환
                    res_df = res_df.set_index("날짜")
                    
                    # 밴드 데이터 생성
                    res_df['Upper_Band'] = res_df['목표 가치($)'] * (1 + band_pct/100)
                    res_df['Lower_Band'] = res_df['목표 가치($)'] * (1 - band_pct/100)
                    
                    final_price = float(df['Close'].iloc[-1])
                    final_asset = (current_qty * final_price) + cash_pool
                    final_return = ((final_asset - total_invested) / total_invested) * 100

                    # --- 📊 결과 화면 ---
                    st.success(f"[{ticker_input}] 분석 완료!")
                    
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("총 투입 원금", f"${total_invested:,.0f}")
                    m2.metric("최종 총 자산", f"${final_asset:,.0f}")
                    m3.metric("최종 수익률", f"{final_return:,.2f}%")
                    m4.metric("현재 보유 수량", f"{current_qty}주")

                    # 1. 자산 변동 차트 (밴드 추가)
                    st.subheader(f"1. {ticker_input} 자산 변동 차트 (Band View)")
                    
                    fig = go.Figure()

                    # (1) 상단 밴드 (투명선)
                    fig.add_trace(go.Scatter(
                        x=res_df.index, y=res_df['Upper_Band'],
                        mode='lines', name='상단 밴드',
                        line=dict(width=0),
                        showlegend=False
                    ))

                    # (2) 하단 밴드 (채우기)
                    fig.add_trace(go.Scatter(
                        x=res_df.index, y=res_df['Lower_Band'],
                        mode='lines', name=f'밴드(±{band_pct}%)',
                        line=dict(width=0),
                        fill='tonexty',
                        fillcolor='rgba(200, 200, 200, 0.3)',
                        showlegend=True
                    ))

                    # (3) 목표 가치
                    fig.add_trace(go.Scatter(
                        x=res_df.index, y=res_df['목표 가치($)'],
                        mode='lines', name='목표 가치(Target)',
                        line=dict(color='#FF4B4B', width=2, dash='dash')
                    ))

                    # (4) 내 자산
                    fig.add_trace(go.Scatter(
                        x=res_df.index, y=res_df['내 자산($)'],
                        mode='lines', name='내 자산(My Asset)',
                        line=dict(color='#1C83E1', width=2)
                    ))

                    fig.update_layout(
                        title=f'{ticker_input} 자산 흐름과 밴드 영역',
                        xaxis_title='날짜', yaxis_title='금액($)',
                        hovermode="x unified",
                        template="plotly_white"
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # 2. 괴리율 차트
                    st.subheader("2. 목표와의 괴리율")
                    res_df['괴리율($)'] = res_df['내 자산($)'] - res_df['목표 가치($)']
                    st.bar_chart(res_df['괴리율($)'], color="#00CC96")

                    # 3. 상세 장부
                    with st.expander("🔎 상세 거래 장부"):
                        price_col = f"{ticker_input} 가격($)"
                        # 날짜 포맷팅을 위해 인덱스 리셋 후 스타일 적용
                        display_df = res_df.copy()
                        display_df.index = display_df.index.strftime('%Y-%m-%d')
                        
                        st.dataframe(
                            display_df.style.format({
                                price_col: "${:,.2f}",
                                "목표 가치($)": "${:,.0f}",
                                "내 자산($)": "${:,.0f}",
                                "보유 수량(주)": "{:,}주",
                                "예수금(Pool)($)": "${:,.0f}",
                                "괴리율($)": "${:,.0f}",
                                "Upper_Band": "${:,.0f}",
                                "Lower_Band": "${:,.0f}"
                            }),
                            use_container_width=True
                        )
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")

# ==============================================================================
# 탭 2: 오늘자 계산기
# ==============================================================================
with tab2:
    st.header(f"🧮 [{ticker_input}] 오늘자 매매 계산기")
    
    col_a, col_b = st.columns(2)
    with col_a:
        cur_p = st.number_input(f"현재 {ticker_input} 가격 ($)", value=55.0)
        my_q = st.number_input("내 보유 수량 (주)", value=100)
    with col_b:
        target_v_now = st.number_input("현재 나의 목표 가치 ($)", value=10000.0)
        band_now = st.number_input("밴드 설정 (%)", value=5.0)
    
    if st.button("계산하기"):
        curr_v = cur_p * my_q
        diff = target_v_now - curr_v
        band_money = target_v_now * (band_now / 100)
        
        st.info(f"목표: ${target_v_now:,.0f} vs 현재: ${curr_v:,.0f} (차액: ${diff:,.0f})")
        st.write(f"🛡️ 밴드 허용 범위: ±${band_money:,.0f}")
        
        if abs(diff) <= band_money:
             st.warning(f"☕ [밴드 관망] 차액이 밴드 이내입니다.")
        else:
            qty = int(diff / cur_p)
            if qty > 0:
                st.success(f"🚀 [매수] {qty}주")
            elif qty < 0:
                st.error(f"🔵 [매도] {abs(qty)}주")
            else:
                st.warning("☕ 수량이 적어서 관망")