# -*- coding: utf-8 -*-
"""
app.py
- JTI 전수조사형 퀀트 투자 시스템 & 과거 백테스팅 시뮬레이터
- 정밀 마크 미너비니 VCP 엔진 & 실전 하이브리드 리스크 관리 탑재
"""

import sys
import os

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

from data_fetch import (
    fetch_universe_tickers,
    fetch_macro_data,
    fetch_benchmark_close,
    fetch_all_stock_history_batch,
    fetch_stock_history,
    fetch_fundamental_data,
    NAME_DICT,
    clean_ticker,
    safe_print
)
from strategy import (
    evaluate_macro,
    evaluate_trend_and_sepa,
    evaluate_fundamentals,
    calculate_portfolio_allocation
)
from backtest import run_single_stock_backtest

# ==============================================================================
# 🌟 페이지 기본 설정 및 스타일링
# ==============================================================================
st.set_page_config(
    page_title="JTI 퀀트 주식 & 정밀 VCP 시스템",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.0rem;
        color: #6B7280;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .stDataFrame {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# ⚙️ 사이드바 컨트롤 타워
# ==============================================================================
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/bullish.png", width=64)
    st.title("📡 JTI 퀀트 컨트롤 타워")
    st.markdown("---")

    st.subheader("🔍 1. 실시간 분석 시장")
    market_options = ["1. S&P500", "2. nasdaq", "3. 코스피", "4. 코스닥", "5. 전체", "6. 직접입력"]
    select_mode = st.selectbox("분석 대상 시장", market_options, index=0)

    raw_input_tickers = ""
    if select_mode == "6. 직접입력":
        raw_input_tickers = st.text_area(
            "✍️ 티커 직접 입력 (쉼표로 구분)",
            value="000660, NVDA, CRWD, MSFT, AAPL, 005930"
        )

    st.subheader("🎯 2. 매수 타점 전략")
    strategy_options = [
        "기존 (엄격 모드 - 150% & 5%)",
        "옵션 A (거래량 완화 - 120%)",
        "옵션 B (이격도 완화 - 7%)",
        "옵션 C (복합 완화 - 120% & 7%)"
    ]
    strategy_mode = st.selectbox("진입 민감도 설정", strategy_options, index=0)

    st.subheader("💰 3. 운용 파라미터")
    capital = st.number_input("총 운용 자산 (원)", min_value=100000, max_value=10000000000, value=10000000, step=1000000)
    exchange_rate = st.number_input("대용 기준 환율 (원/달러)", min_value=900.0, max_value=2500.0, value=1550.0, step=10.0)

    st.markdown("---")
    run_btn = st.button("🚀 실시간 퀀트 분석 가동", type="primary", use_container_width=True)


# ==============================================================================
# 📊 데이터 로딩 및 분석 파이프라인 캐싱
# ==============================================================================
@st.cache_data(ttl=1800, show_spinner=False)
def run_quant_analysis(select_mode, raw_input_tickers, strategy_mode, capital, exchange_rate):
    tickers = fetch_universe_tickers(select_mode, raw_input_tickers)
    macro_data = fetch_macro_data()
    market_score, market_status, vix, detail_logs, indices_summary = evaluate_macro(macro_data)
    bm_close = fetch_benchmark_close()
    stock_dfs = fetch_all_stock_history_batch(tickers, select_mode=select_mode, period='1y')

    pipeline_records = []
    for ticker in tickers:
        df = stock_dfs.get(ticker, pd.DataFrame())
        sepa_res = evaluate_trend_and_sepa(ticker, df, bm_close)
        pipeline_records.append(sepa_res)

    pipeline_df = pd.DataFrame(pipeline_records)

    fund_records = []
    for ticker in pipeline_df['티커']:
        f_data = fetch_fundamental_data(ticker, select_mode=select_mode)
        e_fund = evaluate_fundamentals(f_data)
        fund_records.append(e_fund)

    fund_df = pd.DataFrame(fund_records)
    pipeline_df = pd.merge(pipeline_df, fund_df[['티커', '종목명', '섹터', 'ROE(%)', '이익성장(%)', '등급']], on='티커')

    final_df = calculate_portfolio_allocation(
        pipeline_df=pipeline_df,
        market_status=market_status,
        strategy_mode=strategy_mode,
        capital=capital,
        exchange_rate=exchange_rate
    )

    return {
        'tickers': tickers,
        'market_score': market_score,
        'market_status': market_status,
        'vix': vix,
        'detail_logs': detail_logs,
        'indices_summary': indices_summary,
        'pipeline_df': pipeline_df,
        'final_df': final_df,
        'stock_dfs': stock_dfs
    }


# ==============================================================================
# 🖥️ 메인 탭 레이아웃 구성
# ==============================================================================
st.markdown('<div class="main-header">📈 JTI 정밀 VCP 퀀트 & 백테스팅 시스템</div>', unsafe_allow_html=True)
st.markdown(f'<div class="sub-header">마크 미너비니 VCP 엔진 · 트렌드 템플릿(SEPA) · 동적 켈리 자산 배분 & 백테스팅 | 기준일시: {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>', unsafe_allow_html=True)

tab_realtime, tab_backtest = st.tabs(["📡 실시간 퀀트 대시보드", "📊 과거 백테스팅 검증 (10년 시뮬레이션)"])

# ==============================================================================
# 탭 1: 실시간 퀀트 대시보드
# ==============================================================================
with tab_realtime:
    if 'results' not in st.session_state or run_btn:
        with st.spinner(f"🌐 [{select_mode}] 전 종목 실시간 시세 및 정밀 VCP 분석 중..."):
            st.session_state['results'] = run_quant_analysis(
                select_mode, raw_input_tickers, strategy_mode, capital, exchange_rate
            )

    results = st.session_state.get('results')

    if results:
        # 거시 신호등
        st.subheader("📡 Stage 0: 글로벌 거시 경제 통합 필터")
        col1, col2, col3, col4, col5 = st.columns([1.2, 1.2, 1, 1, 1])

        with col1:
            st.metric(
                label="🌐 글로벌 시장 상태",
                value=results['market_status'],
                delta="정상 가동" if "🟢" in results['market_status'] else ("주의 관망" if "🟡" in results['market_status'] else "보수적 운용")
            )
        with col2:
            st.metric(
                label="📊 종합 지수 스코어",
                value=f"{results['market_score']:.2f} / 3.00",
                delta=f"{(results['market_score']/3.0)*100:.0f}% 달성"
            )
        with col3:
            vix_val = results['vix']
            vix_desc = "안정" if vix_val < 20 else "고위험"
            st.metric(
                label="📉 VIX 공포지수",
                value=f"{vix_val:.2f}",
                delta=vix_desc,
                delta_color="inverse" if vix_val >= 20 else "normal"
            )
        with col4:
            st.metric(
                label="🎯 분석 대상 시장",
                value=select_mode.split('.')[-1].strip(),
                delta=f"총 {len(results['tickers'])}개 종목 전수 스캔"
            )
        with col5:
            total_rec = len(results['final_df']) if results['final_df'] is not None else 0
            st.metric(
                label="🏆 추천 종목 수",
                value=f"{total_rec}개 종목",
                delta="포트폴리오 구성"
            )

        with st.expander("🔍 4대 글로벌 벤치마크 지수 상세 정배열 추세 스캔 성적표", expanded=False):
            idx_cols = st.columns(4)
            for i, (idx_name, idx_info) in enumerate(results['indices_summary'].items()):
                with idx_cols[i % 4]:
                    st.markdown(f"**{idx_name}**")
                    st.write(f"- 스코어: **{idx_info['score']} / 3점**")
                    st.write(f"- 상태: {idx_info['status']}")
                    st.write(f"- 종가: `{idx_info['curr']:,.2f}`")
                    st.write(f"- MA50: `{idx_info['ma50']:,.2f}` | MA200: `{idx_info['ma200']:,.2f}`")

        st.markdown("---")

        # 추천 포트폴리오
        st.subheader(f"🏆 AI 퀀트 추천 포트폴리오 [선택 시장: {select_mode} | 매수 전략: {strategy_mode}]")

        final_df = results['final_df']

        if final_df is not None and not final_df.empty:
            display_columns = [
                '순위', '티커', '종목명', '섹터', '트렌드_템플릿', '등급', '현재가_표기',
                '최종비중(%)', '매수수량', '현재_단계', '전략제언'
            ]
            show_table = final_df[display_columns].rename(columns={
                '현재가_표기': '현재가',
                '등급': '재무등급'
            })

            st.dataframe(
                show_table,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "순위": st.column_config.TextColumn("순위", width="small"),
                    "티커": st.column_config.TextColumn("티커", width="small"),
                    "종목명": st.column_config.TextColumn("종목명", width="medium"),
                    "섹터": st.column_config.TextColumn("섹터", width="medium"),
                    "트렌드_템플릿": st.column_config.TextColumn("트렌드 템플릿", width="small"),
                    "재무등급": st.column_config.TextColumn("재무 등급", width="small"),
                    "현재가": st.column_config.TextColumn("현재가", width="medium"),
                    "최종비중(%)": st.column_config.TextColumn("권장 비중", width="small"),
                    "매수수량": st.column_config.TextColumn("추천 수량", width="small"),
                    "현재_단계": st.column_config.TextColumn("현재 단계", width="medium"),
                    "전략제언": st.column_config.TextColumn("매매 신호 및 제언", width="large"),
                }
            )

            # 자산 배분 차트
            st.markdown("### 📊 포트폴리오 자산 및 섹터 배분 현황")
            chart_col1, chart_col2 = st.columns(2)

            with chart_col1:
                sector_agg = final_df.groupby('섹터')['최종비중_숫자'].sum().reset_index()
                fig_pie = go.Figure(data=[go.Pie(
                    labels=sector_agg['섹터'],
                    values=sector_agg['최종비중_숫자'],
                    hole=.4,
                    textinfo='label+percent',
                    marker=dict(colors=['#3B82F6', '#10B981', '#F59E0B', '#EC4899', '#8B5CF6', '#6366F1', '#14B8A6'])
                )])
                fig_pie.update_layout(
                    title="<b>섹터별 자산 배분 비중 (최대 35% 통제)</b>",
                    margin=dict(t=40, b=20, l=20, r=20),
                    height=320
                )
                st.plotly_chart(fig_pie, use_container_width=True)

            with chart_col2:
                fig_bar = go.Figure(data=[go.Bar(
                    x=final_df['종목명'],
                    y=final_df['최종비중_숫자'],
                    text=final_df['최종비중(%)'],
                    textposition='auto',
                    marker_color='#3B82F6'
                )])
                fig_bar.update_layout(
                    title="<b>종목별 권장 투자 비중 (%)</b>",
                    yaxis_title="비중 (%)",
                    margin=dict(t=40, b=20, l=20, r=20),
                    height=320
                )
                st.plotly_chart(fig_bar, use_container_width=True)

            # 개별 종목 심층 뷰어
            st.markdown("---")
            st.subheader("🔍 개별 종목 심층 캔들스틱 & 지표 뷰어")

            selected_ticker = st.selectbox(
                "분석할 종목을 선택하세요",
                options=final_df['티커'].tolist(),
                format_func=lambda x: f"{x} - {final_df[final_df['티커']==x]['종목명'].iloc[0]}"
            )

            if selected_ticker:
                stock_row = final_df[final_df['티커'] == selected_ticker].iloc[0]
                df_stock = results['stock_dfs'].get(selected_ticker)

                if df_stock is not None and not df_stock.empty and len(df_stock) >= 20:
                    fig = make_subplots(
                        rows=2, cols=1,
                        shared_xaxes=True,
                        vertical_spacing=0.08,
                        row_heights=[0.75, 0.25],
                        subplot_titles=[f"<b>{stock_row['종목명']} ({selected_ticker}) 주가 & 이동평균선</b>", "<b>거래량</b>"]
                    )

                    fig.add_trace(
                        go.Candlestick(
                            x=df_stock.index,
                            open=df_stock['Open'],
                            high=df_stock['High'],
                            low=df_stock['Low'],
                            close=df_stock['Close'],
                            name="주가 (OHLC)"
                        ),
                        row=1, col=1
                    )

                    df_stock_calc = df_stock.copy()
                    df_stock_calc['MA20'] = df_stock_calc['Close'].rolling(20).mean()
                    df_stock_calc['MA50'] = df_stock_calc['Close'].rolling(50).mean()
                    df_stock_calc['MA150'] = df_stock_calc['Close'].rolling(150).mean() if len(df_stock_calc) >= 150 else None
                    df_stock_calc['MA200'] = df_stock_calc['Close'].rolling(200).mean() if len(df_stock_calc) >= 200 else None

                    fig.add_trace(go.Scatter(x=df_stock_calc.index, y=df_stock_calc['MA20'], line=dict(color='#F59E0B', width=1.5), name='MA20'), row=1, col=1)
                    fig.add_trace(go.Scatter(x=df_stock_calc.index, y=df_stock_calc['MA50'], line=dict(color='#3B82F6', width=1.5), name='MA50'), row=1, col=1)
                    if 'MA150' in df_stock_calc and df_stock_calc['MA150'] is not None:
                        fig.add_trace(go.Scatter(x=df_stock_calc.index, y=df_stock_calc['MA150'], line=dict(color='#8B5CF6', width=1.5), name='MA150'), row=1, col=1)
                    if 'MA200' in df_stock_calc and df_stock_calc['MA200'] is not None:
                        fig.add_trace(go.Scatter(x=df_stock_calc.index, y=df_stock_calc['MA200'], line=dict(color='#EF4444', width=2), name='MA200'), row=1, col=1)

                    colors = ['#10B981' if c >= o else '#EF4444' for c, o in zip(df_stock['Close'], df_stock['Open'])]
                    fig.add_trace(
                        go.Bar(x=df_stock.index, y=df_stock['Volume'], marker_color=colors, name="거래량"),
                        row=2, col=1
                    )

                    fig.update_layout(
                        xaxis_rangeslider_visible=False,
                        height=520,
                        margin=dict(t=40, b=20, l=20, r=20),
                        template="plotly_white"
                    )

                    st.plotly_chart(fig, use_container_width=True)

                    card_col1, card_col2, card_col3, card_col4 = st.columns(4)
                    with card_col1:
                        st.markdown("**🎯 매매 신호**")
                        st.info(f"{stock_row['전략제언']}")
                    with card_col2:
                        st.markdown("**📐 미너비니 VCP 지표**")
                        st.write(f"- 다중 파동 수축: **{'완료 ✅' if stock_row.get('VCP수축') else '진행 중'}**")
                        st.write(f"- 거래량 고갈: **{'고갈 완료 💧' if stock_row.get('거래량고갈') else '일반'}**")
                        st.write(f"- 피벗 돌파: **{'상방 돌파 🚀' if stock_row.get('피벗돌파') else '대기'}**")
                        st.write(f"- 피벗 거리: **{stock_row['피벗거리(%)']}%**")
                    with card_col3:
                        st.markdown("**💎 펀더멘탈 지표**")
                        st.write(f"- 섹터: **{stock_row['섹터']}**")
                        st.write(f"- ROE: **{stock_row['ROE(%)']}%**")
                        st.write(f"- 이익성장률: **{stock_row['이익성장(%)']}%**")
                    with card_col4:
                        st.markdown("**⚖️ 배분 및 리스크**")
                        st.write(f"- 승률: **{stock_row['승률']*100:.1f}%**")
                        st.write(f"- 손익비: **{stock_row['손익비']}**")
                        st.write(f"- 추천 수량: **{stock_row['매수수량']}**")

        else:
            st.warning("⚠️ 선택하신 조건 및 필터 제약을 통과한 유효 종목이 없습니다.")

    else:
        st.info("좌측 사이드바에서 설정 후 [🚀 실시간 퀀트 분석 가동] 버튼을 눌러주세요.")


# ==============================================================================
# 탭 2: 과거 백테스팅 시뮬레이션
# ==============================================================================
with tab_backtest:
    st.subheader("📊 정밀 VCP & SEPA 전략 과거 백테스팅 시뮬레이터")
    st.markdown("과거 실제 시세 데이터를 바탕으로 **안전 버퍼 손절매(-7%) & 트레일링 익절 & 미너비니 VCP 피벗 돌파 매수** 전략의 실제 수익률을 정밀 검증합니다.")

    bt_col1, bt_col2, bt_col3, bt_col4 = st.columns(4)
    with bt_col1:
        bt_ticker = st.selectbox(
            "백테스트 종목 선택",
            options=["000660", "NVDA", "CRWD", "MSFT", "AAPL", "005930", "직접입력"],
            index=0
        )
        if bt_ticker == "직접입력":
            bt_ticker = st.text_input("직접 티커 입력", value="GOOGL").strip().upper()

    with bt_col2:
        bt_period = st.selectbox("백테스트 기간", ["1y", "2y", "3y", "5y", "10y"], index=2)

    with bt_col3:
        bt_stop_loss = st.selectbox("손절매 기준 (Stop-Loss)", [-0.05, -0.06, -0.07, -0.08, -0.10], index=2, format_func=lambda x: f"{x*100:.0f}%")

    with bt_col4:
        bt_capital = st.number_input("시뮬레이션 초기 자산 (원)", min_value=1000000, max_value=1000000000, value=10000000, step=1000000)

    bt_run_btn = st.button("🚀 백테스트 실행하기", type="primary", use_container_width=True)

    if bt_run_btn or 'bt_result' not in st.session_state:
        with st.spinner(f"⏳ {bt_ticker} ({bt_period}) 정밀 VCP 백테스트 시뮬레이션 계산 중..."):
            st.session_state['bt_result'] = run_single_stock_backtest(
                ticker=bt_ticker,
                period=bt_period,
                initial_capital=bt_capital,
                stop_loss_pct=abs(bt_stop_loss)
            )

    bt_res = st.session_state.get('bt_result')

    if bt_res:
        st.markdown(f"### 🏆 백테스트 성과 분석 성적표: **{bt_res['stock_name']} ({bt_res['ticker']})** [기간: {bt_res['period']}]")
        
        m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
        with m_col1:
            st.metric(
                label="💰 전략 총 수익률",
                value=f"{bt_res['total_return_pct']:+.1f}%",
                delta=f"단순보유: {bt_res['buyhold_return_pct']:+.1f}%"
            )
        with m_col2:
            st.metric(
                label="📈 연평균 복리(CAGR)",
                value=f"{bt_res['cagr']:+.1f}%"
            )
        with m_col3:
            st.metric(
                label="🛡️ 최대 낙폭 (MDD)",
                value=f"-{bt_res['mdd']:.1f}%",
                delta="리스크 방어력",
                delta_color="inverse"
            )
        with m_col4:
            st.metric(
                label="🎯 승률 (Win Rate)",
                value=f"{bt_res['win_rate']:.1f}%",
                delta=f"총 {bt_res['total_trades']}회 매매"
            )
        with m_col5:
            st.metric(
                label="⚖️ 손익비 (Payoff Ratio)",
                value=f"{bt_res['payoff_ratio']:.2f} : 1"
            )

        st.markdown("### 📈 누적 자산 가치 곡선 (Equity Curve vs 단순보유)")
        eq_df = bt_res['equity_df']

        fig_eq = go.Figure()
        fig_eq.add_trace(go.Scatter(
            x=eq_df.index,
            y=eq_df['Strategy'],
            mode='lines',
            name='JTI 퀀트 전략 자산',
            line=dict(color='#2563EB', width=2.5)
        ))
        fig_eq.add_trace(go.Scatter(
            x=eq_df.index,
            y=eq_df['BuyHold'],
            mode='lines',
            name='단순 보유 (Buy & Hold)',
            line=dict(color='#9CA3AF', width=1.5, dash='dot')
        ))
        fig_eq.update_layout(
            height=400,
            yaxis_title="계좌 총 평가액 (원/$)",
            margin=dict(t=30, b=20, l=20, r=20),
            template="plotly_white",
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
        )
        st.plotly_chart(fig_eq, use_container_width=True)

        st.markdown("### 🛡️ 계좌 낙폭 (Drawdown) 추이")
        fig_dd = go.Figure()
        fig_dd.add_trace(go.Scatter(
            x=eq_df.index,
            y=bt_res['drawdown_series'],
            mode='lines',
            fill='tozeroy',
            name='낙폭 (%)',
            line=dict(color='#EF4444', width=1.5),
            fillcolor='rgba(239, 68, 68, 0.2)'
        ))
        fig_dd.update_layout(
            height=240,
            yaxis_title="낙폭 (%)",
            margin=dict(t=20, b=20, l=20, r=20),
            template="plotly_white"
        )
        st.plotly_chart(fig_dd, use_container_width=True)

        st.markdown("### 📋 개별 매매 상세 일지 (Trade Log)")
        trades_df = bt_res['trades_df']
        if not trades_df.empty:
            st.dataframe(
                trades_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "진입일": st.column_config.TextColumn("진입일", width="small"),
                    "청산일": st.column_config.TextColumn("청산일", width="small"),
                    "진입가": st.column_config.NumberColumn("진입가", format="%.2f"),
                    "청산가": st.column_config.NumberColumn("청산가", format="%.2f"),
                    "수익률(%)": st.column_config.NumberColumn("수익률(%)", format="%.2f%%"),
                    "손익금(원/$)": st.column_config.NumberColumn("손익금", format="%d"),
                    "보유일수": st.column_config.NumberColumn("보유일(일)", width="small"),
                    "청산사유": st.column_config.TextColumn("청산 사유", width="large")
                }
            )
        else:
            st.info("해당 기간 동안 발생한 매매 체결 내역이 없습니다.")

    else:
        st.error("선택한 종목의 시세 데이터를 불러오지 못했습니다. 올바른 티커를 입력해주세요.")
