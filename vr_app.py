# vr_app.py
# 사이드바 제거 -> 메인 화면 상단 배치 버전

import streamlit as st
import datetime
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# --- 페이지 설정 (레이아웃 조절) ---
st.set_page_config(page_title="VR 리밸런싱 시뮬레이터", page_icon="📈", layout="wide")

st.header("📊 VR 무한매수법 시뮬레이터 V6")
st.markdown("옵션을 설정하고 **[시뮬레이션 시작]** 버튼을 눌러주세요. 👇")

# ==============================================================================
# 1. 설정 패널 (사이드바 대신 메인 화면에 배치)
# ==============================================================================
# expanded=True 옵션으로 처음부터 쫙 펼쳐서 보여줍니다.
with st.expander("⚙️ 종목 및 자금 설정 (클릭해서 접기/펴기)", expanded=True):
    
    # 보기 좋게 3단으로 나눕니다.
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("##### 1️⃣ 종목 선택")
        ticker_input = st.text_input("티커 (예: TQQQ)", value="TQQQ").upper()
        band_pct = st.slider("허용 밴드 (%)", 0.0, 10.0, 5.0, step=0.5)

    with col2:
        st.markdown("##### 2️⃣ 기간 설정")
        start_date = st.date_input("시작일", datetime.date(2022, 1, 1))
        end_date = st.date_input("종료일", datetime.date.today())

    with col3:
        st.markdown("##### 3️⃣ 자금 설정 ($)")
        start_money = st.number_input("초기 원금", value=10000, step=1000)
        monthly_add = st.number_input("월 적립금", value=250, step=50)

    # 리밸런싱 주기는 아래에 깔끔하게
    st.markdown("---")
    rebalance_period = st.radio("🔄 리밸런싱 주기 선택", [14, 30], index=0, horizontal=True, format_func=lambda x: f"{x}일 간격")

    # 실행 버튼을 설정창 안에 넣어서 바로 누르게 유도
    run_btn = st.button("🚀 시뮬레이션 시작 (Click)", type="primary", use_container_width=True)

# ==============================================================================
# 2. 메인 탭 구성
# ==============================================================================
tab1, tab2 = st.tabs([f"📈 {ticker_input} 백테스트 결과", "🧮 오늘자 매매 계산기"])

# --- 탭 1: 백테스팅 로직 ---
with tab1:
    if run_btn:
        with st.spinner(f"미국 서버에서 {ticker_input} 데이터 가져오는 중..."):
            try:
                # 데이터 다운로드
                df = yf.download(ticker_input, start=start_date - datetime.timedelta(days=10), end=end_date + datetime.timedelta(days=5), progress=False)
                
                if len(df) == 0:
                    st.error("데이터가 없습니다. 티커를 확인해주세요.")
                else:
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    
                    df = df[(df.index >= pd.Timestamp(start_date)) & (df.index <= pd.Timestamp(end_date))]
                    
                    if len(df) == 0:
                        st.error("해당 기간의 데이터가 부족합니다.")
                    else:
                        # --- 여기서부터 시뮬레이션 로직 (기존과 동일) ---
                        log_data = []
                        cash_pool = float(start_money)
                        total_invested = float(start_money)
                        target_value = float(start_money)
                        
                        first_price = float(df['Close'].iloc[0]) 
                        current_qty = int(start_money / first_price)
                        cash_pool -= (current_qty * first_price)
                        last_trade_day = df.index[0]

                        # 초기 데이터
                        log_data.append({
                            "날짜": df.index[0], "종가": first_price, "목표금액": target_value,
                            "내자산": current_qty * first_price, "수량": current_qty, "예수금": cash_pool, "행동": "시작"
                        })

                        for date, row in df.iloc[1:].iterrows():
                            price = float(row['Close'])
                            my_asset = current_qty * price
                            days_diff = (date - last_trade_day).days
                            action = ""

                            if days_diff >= rebalance_period:
                                target_value += monthly_add
                                diff = target_value - my_asset
                                band_money = target_value * (band_pct / 100)

                                if abs(diff) > band_money:
                                    qty = int(diff / price)
                                    if qty > 0: # 매수
                                        cost = qty * price
                                        if cash_pool < cost:
                                            needed = cost - cash_pool
                                            total_invested += needed
                                            cash_pool += needed
                                        current_qty += qty
                                        cash_pool -= cost
                                        action = f"매수 {qty}주"
                                    elif qty < 0: # 매도
                                        sell_qty = abs(qty)
                                        current_qty -= sell_qty
                                        cash_pool += (sell_qty * price)
                                        action = f"매도 {sell_qty}주"
                                else:
                                    action = "관망(밴드내)"
                                last_trade_day = date
                            
                            log_data.append({
                                "날짜": date, "종가": price, "목표금액": target_value,
                                "내자산": current_qty * price, "수량": current_qty, "예수금": cash_pool, "행동": action
                            })

                        # 결과 정리
                        res_df = pd.DataFrame(log_data)
                        res_df['날짜'] = pd.to_datetime(res_df['날짜'])
                        res_df = res_df.set_index("날짜")
                        
                        res_df['상단밴드'] = res_df['목표금액'] * (1 + band_pct/100)
                        res_df['하단밴드'] = res_df['목표금액'] * (1 - band_pct/100)

                        final_asset = (current_qty * df['Close'].iloc[-1]) + cash_pool
                        final_return = ((final_asset - total_invested) / total_invested) * 100

                        # 메트릭 표시
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("총 투입금", f"${total_invested:,.0f}")
                        m2.metric("최종 자산", f"${final_asset:,.0f}")
                        m3.metric("수익률", f"{final_return:.2f}%", delta_color="normal")
                        m4.metric("보유 수량", f"{current_qty}주")

                        # 차트 그리기
                        fig = go.Figure()
                        # 밴드 (회색 영역)
                        fig.add_trace(go.Scatter(x=res_df.index, y=res_df['상단밴드'], mode='lines', line=dict(width=0), showlegend=False))
                        fig.add_trace(go.Scatter(x=res_df.index, y=res_df['하단밴드'], mode='lines', fill='tonexty', fillcolor='rgba(200,200,200,0.3)', line=dict(width=0), name='밴드 영역'))
                        # 목표선
                        fig.add_trace(go.Scatter(x=res_df.index, y=res_df['목표금액'], mode='lines', line=dict(color='red', dash='dash'), name='목표선'))
                        # 내 자산
                        fig.add_trace(go.Scatter(x=res_df.index, y=res_df['내자산'], mode='lines', line=dict(color='blue', width=2), name='내 자산'))

                        fig.update_layout(height=500, margin=dict(l=20, r=20, t=40, b=20), hovermode="x unified", legend=dict(orientation="h", y=1.1))
                        st.plotly_chart(fig, use_container_width=True)

            except Exception as e:
                st.error(f"오류 발생: {e}")
    else:
        st.info("👆 위 설정에서 종목을 확인하고 [시뮬레이션 시작] 버튼을 눌러주세요.")

# --- 탭 2: 계산기 ---
with tab2:
    st.write("##### 🧮 현재가 기준 매매 수량 계산")
    c1, c2 = st.columns(2)
    with c1:
        now_p = st.number_input("현재 주가($)", value=100.0)
        now_q = st.number_input("보유 수량", value=50)
    with c2:
        now_target = st.number_input("현재 목표치($)", value=5000.0)
        now_band = st.number_input("밴드(%)", value=5.0)
    
    if st.button("계산하기", type="secondary"):
        now_val = now_p * now_q
        diff = now_target - now_val
        limit = now_target * (now_band/100)
        
        st.write(f"현재 가치: **${now_val:,.0f}** / 차이: **${diff:,.0f}**")
        
        if abs(diff) <= limit:
            st.success("✅ **관망** (밴드 이내입니다)")
        else:
            req_qty = int(diff / now_p)
            if req_qty > 0:
                st.error(f"🚀 **{req_qty}주 매수** 필요")
            else:
                st.warning(f"📉 **{abs(req_qty)}주 매도** 필요")
