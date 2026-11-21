# -*- coding: utf-8 -*-
"""
app.py
- JTI 전수조사형 퀀트 투자 시스템 & 내 실전 계좌 AI 맞춤 관리 시스템
- 1. 내 5대 계좌(연금저축/ISA/일반국내/일반해외/코인) 실시간 통합 자산 관리 & AI 건강검진
- 2. SEPA 8대 트렌드 템플릿 & 마크 미너비니 VCP 실전 스캐너
- 3. 10년 백테스팅 검증 시뮬레이터
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
    get_stock_name,
    extract_single_stock_df,
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
from backtest import (
    run_single_stock_backtest,
    run_portfolio_historical_backtest,
    run_future_wealth_projection
)
from portfolio_manager import (
    load_portfolio_data,
    save_portfolio_data,
    analyze_my_portfolio,
    parse_pasted_csv_text,
    fetch_live_exchange_rate,
    save_target_allocation,
    DEFAULT_ACCOUNT_TARGETS,
    DEFAULT_CATEGORY_TARGETS,
    FACTOR_PROFILES,
    calculate_portfolio_quant_metrics,
    get_cross_lens_matrix,
    calculate_smart_deposit_rebalancing,
    classify_asset_category,
    get_holding_factor_map,
    update_holding_asset_category,
    get_tax_leakage_diagnosis,
    generate_quant_pb_audit_report
)
import importlib
import ai_advisor
importlib.reload(ai_advisor)
from ai_advisor import (
    call_gemini_advisor,
    stream_gemini_advisor,
    build_portfolio_context,
    run_expert_quant_advisor,
    load_ai_config,
    save_ai_config,
    QUICK_PROMPTS,
    GEMINI_MODELS
)

# ==============================================================================
# 🌟 페이지 기본 설정 및 스타일링
# ==============================================================================
st.set_page_config(
    page_title="JTI 퀀트 & 나만의 AI 자산관리 PB",
    page_icon="💼",
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
    /* 모바일 스마트폰 반응형 최적화 */
    @media (max-width: 768px) {
        .main-header { font-size: 1.4rem !important; }
        .sub-header { font-size: 0.85rem !important; }
        .block-container { padding: 1rem 0.6rem !important; }
        div[data-testid="stMetricValue"] { font-size: 1.25rem !important; }
        div[data-testid="stMetricLabel"] { font-size: 0.8rem !important; }
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

    st.subheader("🔍 1. 시장 스캔 설정")
    market_options = [
        "1. S&P 500 (503개 전수)",
        "2. NASDAQ (200개 전수)",
        "3. 코스피 200 (200개 전수)",
        "4. 코스닥 150 (150개 전수)",
        "5. 글로벌 통합 전수 (850+개 전체)",
        "6. 직접입력"
    ]
    select_mode = st.selectbox("스캔 대상 시장", market_options, index=0)

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
    capital = st.number_input("스캐너 시뮬레이션 자산 (원)", min_value=100000, max_value=10000000000, value=10000000, step=1000000)
    live_fx = fetch_live_exchange_rate()
    exchange_rate_input = st.number_input(
        f"실시간 기준 환율 (원/달러, 당일: {live_fx:,.1f}원)",
        min_value=900.0,
        max_value=2500.0,
        value=float(round(live_fx, 2)),
        step=1.0,
        help="야후 파이낸스(KRW=X)에서 실시간으로 수집된 당일 기준 환율입니다."
    )
    st.caption("⚡ KRW=X 실시간 연동 (해외 주식 및 달러 자산에 당일 자동 반영)")

    st.markdown("---")
    run_btn = st.button("🚀 실시간 시장 퀀트 스캔 가동", type="primary", use_container_width=True)

    st.markdown("---")
    try:
        import socket
        _s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _s.connect(('8.8.8.8', 80))
        _lan_ip = _s.getsockname()[0]
        _s.close()
    except Exception:
        _lan_ip = "192.168.219.106"
    
    st.info(f"📱 **스마트폰 모바일 접속**\n\n`http://{_lan_ip}:8501`\n\n*(PC와 같은 Wi-Fi 연결 시 즉시 접속 가능)*")


# ==============================================================================
# 📊 시장 퀀트 파이프라인 캐싱 함수
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

    # 종목명이 누락되었거나 티커와 동일한 경우를 위한 최종 안전 보정 (100% 한글/정식명 보장)
    if '종목명' in pipeline_df.columns:
        pipeline_df['종목명'] = pipeline_df.apply(
            lambda r: get_stock_name(r['티커']) if (pd.isna(r['종목명']) or str(r['종목명']).strip() == str(r['티커']).strip()) else r['종목명'],
            axis=1
        )

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
st.markdown('<div class="main-header">💼 JTI 나만의 AI 자산관리 PB & 마크 미너비니 퀀트 시스템</div>', unsafe_allow_html=True)
st.markdown(f'<div class="sub-header">내 5대 계좌 실시간 통합 관리 · Dual-Track 건강검진 & 맞춤 주문표 · SEPA 트렌드 템플릿 | 기준일시: {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>', unsafe_allow_html=True)

tab_my_account, tab_allocator, tab_scanner, tab_backtest, tab_ai_advisor = st.tabs([
    "💼 [내 계좌] 실시간 종합 관리 & AI 맞춤 진단",
    "🧭 [자산 배분] Dual-Lens 포트폴리오 빌더 & What-If",
    "📡 [시장 스캐너] SEPA 트렌드 & 정밀 VCP",
    "📈 [백테스팅 & 복리] 10년 과거 검증 & 미래 부 시뮬레이터",
    "💬 [AI 전담 PB] 1:1 주식 자문 & 자산 증식 상담소"
])


# ==============================================================================
# 탭 1: [내 계좌] 실시간 종합 관리 & AI 맞춤 진단
# ==============================================================================
with tab_my_account:
    # 1. 포트폴리오 모듈 및 데이터 핫 리로드 (최신 코드 및 데이터 즉시 동기화)
    import importlib
    import portfolio_manager
    importlib.reload(portfolio_manager)
    
    raw_p_data = portfolio_manager.load_portfolio_data()
    my_analysis = portfolio_manager.analyze_my_portfolio(raw_p_data)

    # --------------------------------------------------------------------------
    # 🌟 1. 전체 계좌 종합 성적표 메트릭
    # --------------------------------------------------------------------------
    st.subheader("📊 5대 계좌 종합 자산 성적표")
    
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    with m1:
        st.metric(
            label="💰 총 평가 금액",
            value=f"{int(my_analysis['total_net_worth']):,}원",
            delta=f"투자 원금: {int(my_analysis['total_cost_basis']):,}원"
        )
    with m2:
        pnl_val = my_analysis['total_pnl_krw']
        st.metric(
            label="📈 총 평가 손익",
            value=f"{int(pnl_val):+,}원",
            delta=f"{my_analysis['total_return_pct']:+.2f}%",
            delta_color="normal" if pnl_val >= 0 else "inverse"
        )
    with m3:
        st.metric(
            label="💵 가용 총 현금",
            value=f"{int(my_analysis['total_cash_krw']):,}원",
            delta="원화+달러 합산"
        )
    with m4:
        st.metric(
            label="💰 연간 예상 배당금",
            value=f"연 {int(my_analysis['total_annual_dividend_krw']):,}원",
            delta=f"월 {int(my_analysis['total_monthly_dividend_krw']):,}원 (배당률 {my_analysis['portfolio_dividend_yield']:.2f}%)"
        )
    with m5:
        st.metric(
            label="🌐 실시간 기준 환율",
            value=f"${my_analysis['exchange_rate']:,.1f}원",
            delta="USD/KRW 당일 자동반영"
        )
    with m6:
        total_holdings_count = len(my_analysis['all_holdings_df']) if not my_analysis['all_holdings_df'].empty else 0
        st.metric(
            label="📁 총 보유 자산",
            value=f"{total_holdings_count}개 종목",
            delta="5개 계좌 분산"
        )

    st.markdown("---")

    # --------------------------------------------------------------------------
    # 📈 2. 총자산 시계열 추이 차트 & 계좌별 비중 및 목표 비교
    # --------------------------------------------------------------------------
    c_col1, c_col2 = st.columns([1.1, 1.3])

    with c_col1:
        st.markdown("### 📈 총자산 평가액 및 원금 추이 (2026년 5월 ~ 현재)")
        hist = my_analysis['asset_history']
        if hist:
            hist_df = pd.DataFrame(hist)
            fig_hist = go.Figure()
            fig_hist.add_trace(go.Scatter(
                x=hist_df['date'], y=hist_df['equity'],
                mode='lines+markers', name='총 평가금액',
                line=dict(color='#2563EB', width=2.5)
            ))
            fig_hist.add_trace(go.Scatter(
                x=hist_df['date'], y=hist_df['cost'],
                mode='lines', name='투자 원금',
                line=dict(color='#9CA3AF', width=1.5, dash='dash')
            ))
            fig_hist.update_layout(
                height=320,
                margin=dict(t=20, b=20, l=20, r=20),
                template="plotly_white",
                legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
            )
            st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.info("자산 추이 데이터가 없습니다.")

    with c_col2:
        st.markdown("### 🥧 5대 계좌별 자산 배분 & 현수준 vs 목표 비교")
        pie_sub1, pie_sub2 = st.columns([1.0, 1.25])

        with pie_sub1:
            acc_data = my_analysis['accounts']
            acc_names = list(acc_data.keys())
            acc_values = [acc_data[a]['total_eval_krw'] for a in acc_names]

            fig_acc_pie = go.Figure(data=[go.Pie(
                labels=acc_names,
                values=acc_values,
                hole=.45,
                textinfo='label+percent',
                marker=dict(colors=['#3B82F6', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899'])
            )])
            fig_acc_pie.update_layout(
                height=300,
                margin=dict(t=10, b=10, l=10, r=10),
                showlegend=False
            )
            st.plotly_chart(fig_acc_pie, use_container_width=True)

        with pie_sub2:
            st.markdown("<div style='margin-top: 2px;'>", unsafe_allow_html=True)
            for item in my_analysis['account_comparison']:
                acc = item['account']
                curr_w = item['current_weight']
                tgt_w = item['target_weight']
                badge = item['status_badge']
                color = item['status_color']
                eval_val = int(item['eval_krw'])
                
                st.markdown(f"""
                <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 6px 10px; margin-bottom: 5px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px;">
                        <span style="font-weight: 600; font-size: 0.83rem; color: #1E293B;">{acc}</span>
                        <span style="font-size: 0.82rem; font-weight: 700; color: {color};">{curr_w:.1f}% <span style="font-weight: 400; color: #64748B; font-size: 0.72rem;">(목표 {tgt_w:.0f}%)</span></span>
                    </div>
                    <div style="background: #E2E8F0; border-radius: 3px; height: 5px; overflow: hidden; margin-bottom: 3px;">
                        <div style="background: {color}; width: {min(100, curr_w)}%; height: 100%; border-radius: 3px;"></div>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 0.68rem; color: #64748B;">약 {eval_val:,}원</span>
                        <span style="font-size: 0.68rem; color: {color}; font-weight: 600;">{badge}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")

    # --------------------------------------------------------------------------
    # 🩺 3. Dual-Track AI 보유종목 실시간 건강검진 & 처방전
    # --------------------------------------------------------------------------
    st.subheader("🩺 Dual-Track AI 보유 종목 실시간 건강검진 & 배당 처방전")
    st.markdown("**[장기 적립 계좌 (연금/ISA)]**는 200일선 우상향 시 지속 적립 및 배당 재투자(DRIP)를 권고하며, **[단기 퀀트 스윙 계좌 (해외/일반)]**는 마크 미너비니 원칙에 따라 구체적 실행 단가(손절가/본전스탑가/목표가)와 매도/매수 수량을 강력하게 처방합니다.")

    all_h_df = my_analysis['all_holdings_df']
    if not all_h_df.empty:
        # 🚨 즉시 실행 행동 요약 카드 3대 브리핑
        danger_cnt = len(all_h_df[all_h_df['진단상태'].str.contains("손절", na=False)])
        stop_cnt = len(all_h_df[all_h_df['진단상태'].str.contains("익절|본전", na=False)])
        drip_cnt = len(all_h_df[all_h_df['진단상태'].str.contains("적립", na=False)])

        al_c1, al_c2, al_c3 = st.columns(3)
        with al_c1:
            if danger_cnt > 0:
                st.error(f"🚨 **[긴급 손절 권고] {danger_cnt}개 종목**이 -7% 손절선에 도달했습니다! 아래 표의 실행 단가로 즉시 시장가/지정가 매도하여 원금을 방어하십시오.")
            else:
                st.success("🛡️ **[손절 위험 없음]** 현재 -7% 손절 기준선에 도달한 위험 종목이 0개입니다. 원금 방어가 완벽히 작동 중입니다.")
        with al_c2:
            if stop_cnt > 0:
                st.info(f"💰 **[수익 확정 / 스탑 상향] {stop_cnt}개 종목**이 +10% 이상 수익권에 도달했습니다! 스탑로스를 본전가로 상향하여 무손실 트레이드로 잠그십시오.")
            else:
                st.info("📈 **[추세 추종 중]** 스윙 보유 종목들이 정상적인 변동성 범위 내에서 20일선 추세를 형성하고 있습니다.")
        with al_c3:
            st.metric("🌱 연간 총 배당 파이프라인", f"{int(my_analysis.get('total_annual_dividend_krw', 0)):,}원", delta="배당금 100% DRIP 재투자 권장")

        disp_df = all_h_df[[
            '계좌', '계좌유형', '종목명', '수량', '매수단가', '현재가', '수익률(%)', '평가금액(원)', '배당수익률(%)', '연간예상배당(원)', '실행단가', '진단상태', '처방내용', '통화'
        ]].copy()

        disp_df['수량'] = disp_df['수량'].apply(lambda x: f"{x:.8f}".rstrip('0').rstrip('.') if x < 1 else (f"{x:.2f}".rstrip('0').rstrip('.') if isinstance(x, float) and not x.is_integer() else f"{int(x)}"))
        disp_df['매수단가'] = disp_df.apply(lambda r: f"${r['매수단가']:.2f}" if r['통화'] == "USD" else f"{int(r['매수단가']):,}원", axis=1)
        disp_df['현재가'] = disp_df.apply(lambda r: f"${r['현재가']:.2f} (약 {int(r['현재가'] * my_analysis['exchange_rate']):,}원)" if r['통화'] == "USD" else f"{int(r['현재가']):,}원", axis=1)
        disp_df['수익률(%)'] = disp_df['수익률(%)'].apply(lambda x: f"{x:+.1f}%")
        disp_df['평가금액'] = disp_df['평가금액(원)'].apply(lambda x: f"{int(x):,}원")
        disp_df['배당률'] = disp_df['배당수익률(%)'].apply(lambda x: f"{x:.2f}%" if x > 0 else "-")
        disp_df['연간배당금'] = disp_df['연간예상배당(원)'].apply(lambda x: f"{int(x):,}원" if x > 0 else "-")

        st.dataframe(
            disp_df[['계좌', '종목명', '수량', '매수단가', '현재가', '수익률(%)', '평가금액', '배당률', '실행단가', '진단상태', '처방내용']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "계좌": st.column_config.TextColumn("계좌", width="small"),
                "종목명": st.column_config.TextColumn("종목명", width="medium"),
                "수량": st.column_config.TextColumn("수량", width="small"),
                "매수단가": st.column_config.TextColumn("매수단가", width="small"),
                "현재가": st.column_config.TextColumn("현재가", width="medium"),
                "수익률(%)": st.column_config.TextColumn("수익률", width="small"),
                "평가금액": st.column_config.TextColumn("평가금액", width="medium"),
                "배당률": st.column_config.TextColumn("배당률", width="small"),
                "실행단가": st.column_config.TextColumn("🎯 실행 트리거가", width="medium", help="손절 실행가 / 본전 스탑가 / 1차 목표가 등 실제 HTS에 걸어둘 가격"),
                "진단상태": st.column_config.TextColumn("AI 진단 뱃지", width="medium"),
                "처방내용": st.column_config.TextColumn("강력 처방 및 실전 행동 지침", width="large")
            }
        )

    st.markdown("---")

    # --------------------------------------------------------------------------
    # ⚖️ 4. 내 잔고 기반 오늘의 맞춤형 리밸런싱 & 매수 주문표 (미래 예측 탑재)
    # --------------------------------------------------------------------------
    st.subheader("⚖️ 내 잔고 기반 오늘의 맞춤형 리밸런싱 & 주문표 (미래 구간 예측 탑재)")
    st.markdown("내 실제 계좌별 가용 현금과 종목별 목표 비중을 결합하여, **오늘 주문을 실행했을 때 향후 1~3년 뒤 비중 수렴도와 배당/복리 성장 시나리오를 예측한 실전 주문서**입니다.")

    order_df = my_analysis['order_suggestions']
    if not order_df.empty:
        # 미래 예측 시뮬레이션 요약 안내
        st.dataframe(
            order_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "계좌": st.column_config.TextColumn("계좌", width="small"),
                "구분": st.column_config.TextColumn("구분", width="small"),
                "종목명": st.column_config.TextColumn("종목명", width="medium"),
                "현재가": st.column_config.TextColumn("현재가", width="small"),
                "추천주문": st.column_config.TextColumn("오늘 실행 주문", width="medium"),
                "주문금액": st.column_config.TextColumn("주문 금액", width="small"),
                "이유": st.column_config.TextColumn("주문 사유", width="medium"),
                "비중수렴예측": st.column_config.TextColumn("🔮 비중 수렴 예측", width="medium"),
                "1년후추가배당": st.column_config.TextColumn("💰 1년 후 추가 배당", width="small"),
                "3년후복리예측": st.column_config.TextColumn("📈 3년 후 복리 성장 예측", width="large")
            }
        )
        st.info("💡 **미래 구간 시뮬레이션 인사이트**: 위 주문을 실행하시면 부족한 코어/배당 자산군이 목표 비중에 정밀 수렴하며, 배당 파이프라인의 눈덩이 복리 효과가 즉시 가속화됩니다.")
    else:
        st.success("✅ 현재 모든 계좌의 비중이 이상적이며, 손절선에 도달한 리스크 종목이 없습니다. 현 상태를 유지하십시오.")

    st.markdown("---")

    # --------------------------------------------------------------------------
    # ⚙️ 5. 데이터 갱신 및 원금 히스토리 관리 도구 (속도 10배 최적화)
    # --------------------------------------------------------------------------
    with st.expander("⚙️ 내 계좌 데이터 및 투자 원금 히스토리 관리 (엑셀 복붙 / 고속 종목 편집 / 원금 스냅샷)", expanded=False):
        sync_col1, sync_col2, sync_col3 = st.tabs([
            "📋 [방법 A] 엑셀/CSV 붙여넣기",
            "✏️ [방법 B] 계좌별 종목/현금/배당 고속 편집",
            "📅 [방법 C] 일자별 투자 원금 스냅샷 관리"
        ])

        with sync_col1:
            st.markdown("엑셀에서 관리하던 표 내용을 복사하여 아래에 붙여넣고 **[1초 만에 갱신하기]** 버튼을 누르시면 5대 계좌가 즉시 최신 상태로 업데이트됩니다.")
            pasted_text = st.text_area("엑셀/CSV 데이터 붙여넣기", height=150, placeholder="계좌구분,종목명,종목코드,현재가,수량...\n연금저축펀드,TIGER 미국S&P500,360750,25780,120...")
            if st.button("🚀 1초 만에 갱신하기", type="primary", key="btn_sync_paste_csv"):
                if pasted_text.strip():
                    parse_pasted_csv_text(pasted_text)
                    st.success("🎉 5대 계좌 데이터가 성공적으로 갱신되었습니다! 페이지를 새로고침합니다.")
                    st.rerun()
                else:
                    st.warning("붙여넣은 텍스트가 없습니다.")

        with sync_col2:
            st.markdown("⚡ **고속 폼 모드**: 입력 중에는 불필요한 새로고침 렉이 발생하지 않으며, 아래 **[💾 영구 저장]** 버튼을 누르면 즉시 초고속으로 저장됩니다.")
            edit_acc = st.selectbox("수정할 계좌 선택", list(raw_p_data.get("accounts", {}).keys()), key="select_edit_acc")
            if edit_acc:
                target_acc_info = raw_p_data["accounts"][edit_acc]
                
                # st.form으로 감싸서 입력 시 Streamlit 전체 리런 지연을 100% 차단 (초고속 입력)
                with st.form(key=f"fast_edit_form_{edit_acc}"):
                    e_c1, e_c2, e_c3 = st.columns([1.4, 1.0, 1.0])
                    with e_c1:
                        curr_net_dep = int(target_acc_info.get("net_deposit", 0))
                        new_net_deposit = st.number_input(
                            f"💰 {edit_acc} 순투입원금 (원)",
                            value=curr_net_dep,
                            step=100000,
                            help="은행 통장에서 이 계좌로 실제 입금한 총액 - 출금액 (진짜 원금). 0으로 두시면 보유주식 매수가+현금으로 자동 추적됩니다."
                        )
                    with e_c2:
                        new_cash_krw = st.number_input(f"💵 원화 현금 잔고 (KRW)", value=int(target_acc_info.get("cash_krw", 0)), step=10000)
                    with e_c3:
                        new_cash_usd = st.number_input(f"💲 달러 현금 잔고 (USD)", value=float(target_acc_info.get("cash_usd", 0.0)), step=10.0)

                    st.markdown("**보유 종목 목록 편집 (수량, 매수단가, 배당수익률, 목표비중, 자산분류)**")
                    holdings_list = target_acc_info.get("holdings", [])
                    h_df = pd.DataFrame(holdings_list)
                    if not h_df.empty:
                        if 'dividend_yield' not in h_df.columns:
                            h_df['dividend_yield'] = 0.0
                        if 'target_weight' not in h_df.columns:
                            h_df['target_weight'] = 0.10
                        if 'asset_category' not in h_df.columns:
                            h_df['asset_category'] = "🌱 글로벌 코어 지수" if "연금" in edit_acc else "🚀 퀀트 스윙 & 모멘텀"
                    else:
                        h_df = pd.DataFrame(columns=["ticker", "name", "shares", "avg_price", "dividend_yield", "target_weight", "asset_category"])

                    edited_h_df = st.data_editor(
                        h_df,
                        key=f"editor_holdings_{edit_acc}",
                        num_rows="dynamic",
                        use_container_width=True,
                        column_config={
                            "ticker": st.column_config.TextColumn("티커 (종목코드)", width="small", required=True),
                            "name": st.column_config.TextColumn("종목명", width="medium", required=True),
                            "shares": st.column_config.NumberColumn("보유수량", width="small", required=True, min_value=0.0),
                            "avg_price": st.column_config.NumberColumn("매수단가 (KRW/USD)", width="small", required=True, min_value=0.0),
                            "dividend_yield": st.column_config.NumberColumn("배당수익률 (%)", width="small", min_value=0.0, max_value=100.0, step=0.1, format="%.2f%%"),
                            "target_weight": st.column_config.NumberColumn("목표비중 (0~1)", width="small", min_value=0.0, max_value=1.0, step=0.05, format="%.2f"),
                            "asset_category": st.column_config.SelectboxColumn("자산 팩터 분류", options=[
                                "🌱 글로벌 코어 지수", "💰 고배당 & 인컴", "🤖 테마 & 미래혁신", "🚀 퀀트 스윙 & 모멘텀", "🪙 대체자산 (코인)", "💵 안전 현금"
                            ], width="medium")
                        }
                    )

                    save_submitted = st.form_submit_button(f"💾 {edit_acc} 수정 내용 1초 만에 영구 저장하기", type="primary", use_container_width=True)
                    if save_submitted:
                        target_acc_info["net_deposit"] = new_net_deposit
                        target_acc_info["cash_krw"] = new_cash_krw
                        target_acc_info["cash_usd"] = new_cash_usd
                        target_acc_info["holdings"] = edited_h_df.to_dict(orient="records")
                        raw_p_data["accounts"][edit_acc] = target_acc_info
                        save_portfolio_data(raw_p_data)
                        st.success(f"🎉 {edit_acc} 데이터가 초고속으로 영구 저장되었습니다!")
                        st.rerun()

        with sync_col3:
            st.markdown("### 📸 오늘 자산 & 원금 스냅샷 기록하기")
            st.markdown("매주 또는 매월 정기적으로 계좌를 확인할 때, 버튼 하나로 **오늘의 총 평가액과 총 투자 원금을 자산 추이 그래프에 자동으로 기록(저장)**할 수 있습니다.")
            
            snap_c1, snap_c2 = st.columns(2)
            with snap_c1:
                snap_date = st.date_input("기록 일자", value=datetime.today())
            with snap_c2:
                current_cost_basis = int(my_analysis['total_cost_basis'])
                custom_cost_val = st.number_input("총 누적 투자 원금 (원)", value=current_cost_basis, step=100000)

            if st.button("📸 오늘 자산 스냅샷 그래프에 영구 기록하기", type="primary"):
                from portfolio_manager import add_daily_asset_snapshot
                add_daily_asset_snapshot(custom_date=snap_date.strftime("%Y-%m-%d"), custom_cost=float(custom_cost_val))
                st.success(f"🎉 [{snap_date.strftime('%Y-%m-%d')}] 자산 스냅샷이 성공적으로 기록되었습니다!")
                st.rerun()

            st.markdown("---")
            st.markdown("**과거 일자별 자산/원금 기록표 직접 편집**")
            hist_list = raw_p_data.get("asset_history", [])
            if hist_list:
                hist_edit_df = pd.DataFrame(hist_list)
                edited_hist_df = st.data_editor(hist_edit_df, num_rows="dynamic", use_container_width=True)
                if st.button("💾 자산 히스토리 전체 저장하기"):
                    raw_p_data["asset_history"] = edited_hist_df.to_dict(orient="records")
                    save_portfolio_data(raw_p_data)
                    st.success("🎉 자산 히스토리가 성공적으로 저장되었습니다!")
                    st.rerun()



# ==============================================================================
# 탭 2: [자산 배분] Dual-Lens 스마트 포트폴리오 빌더 & What-If 시뮬레이터 (Institutional PB Grade)
# ==============================================================================
with tab_allocator:
    # 1. 포트폴리오 모듈 및 데이터 핫 리로드 (최신 코드 및 데이터 즉시 동기화)
    import importlib
    import portfolio_manager
    importlib.reload(portfolio_manager)
    
    raw_p_data = portfolio_manager.load_portfolio_data()
    my_analysis = portfolio_manager.analyze_my_portfolio(raw_p_data)
    total_equity = my_analysis['total_net_worth']

    st.markdown('<div style="font-size: 1.6rem; font-weight: 700; color: #1E3A8A; margin-bottom: 4px;">🧭 Dual-Lens 스마트 자산 배분 & 포트폴리오 빌더</div>', unsafe_allow_html=True)
    st.markdown(
        f"대표님의 전체 자산(실시간 평가: **{int(total_equity):,}원**, 순투입: **{int(my_analysis['total_cost_basis']):,}원**)을 "
        f"**[6대 자산 팩터 렌즈]**와 **[5대 절세 계좌 렌즈]**의 입체적 듀얼 렌즈로 정밀 진단합니다. "
        f"글로벌 기관투자가급 퀀트 지표(기대수익률, 샤프지수, 위기 낙폭, 월 배당)를 실시간 시뮬레이션하고, "
        f"기존 주식을 팔지 않고 월 적립금으로 최적 비중을 맞추는 **No-Sell 스마트 입금 리밸런싱 주문표**를 원클릭으로 생성합니다."
    )

    st.markdown("---")

    # --------------------------------------------------------------------------
    # 🌟 Step 1: AI 글로벌 기관 자산배분 모델 4대 프리셋
    # --------------------------------------------------------------------------
    st.markdown("### 🌟 Step 1: AI 글로벌 기관 자산배분 모델 4대 프리셋 (원클릭 세팅)")
    
    preset_cat_map = {
        "⚖️ [JTI 밸런스 Dual-Track (추천)] (코어 35% + 고배당 30% + 테마 15% + 스윙 10% + 현금 8% + 코인 2%)": {
            "🌱 글로벌 코어 지수": 35, "💰 고배당 & 인컴": 30, "🤖 테마 & 미래혁신": 15, "🚀 퀀트 스윙 & 모멘텀": 10, "🪙 대체자산 (코인)": 2, "💵 안전 현금": 8
        },
        "🦅 [레이 달리오 All-Weather 인컴 안정형] (고배당 45% + 코어 25% + 안전현금 20% + 테마 10%)": {
            "🌱 글로벌 코어 지수": 25, "💰 고배당 & 인컴": 45, "🤖 테마 & 미래혁신": 10, "🚀 퀀트 스윙 & 모멘텀": 0, "🪙 대체자산 (코인)": 0, "💵 안전 현금": 20
        },
        "🚀 [피터 린치 & 미너비니 공격 복리성장형] (코어 40% + 테마 25% + 퀀트스윙 20% + 고배당 5% + 현금 8% + 코인 2%)": {
            "🌱 글로벌 코어 지수": 40, "💰 고배당 & 인컴": 5, "🤖 테마 & 미래혁신": 25, "🚀 퀀트 스윙 & 모멘텀": 20, "🪙 대체자산 (코인)": 2, "💵 안전 현금": 8
        },
        "💎 [나심 탈레브 바벨 인컴 & 혁신 전략] (코어/고배당/현금 80% + 테마/스윙/코인 20%)": {
            "🌱 글로벌 코어 지수": 35, "💰 고배당 & 인컴": 35, "🤖 테마 & 미래혁신": 12, "🚀 퀀트 스윙 & 모멘텀": 6, "🪙 대체자산 (코인)": 2, "💵 안전 현금": 10
        }
    }

    preset_acc_map = {
        "⚖️ [JTI 밸런스 Dual-Track (추천)] (코어 35% + 고배당 30% + 테마 15% + 스윙 10% + 현금 8% + 코인 2%)": {
            "연금저축펀드": 40, "일반계좌(해외)": 25, "ISA": 20, "일반계좌(국내)": 10, "IRP및코인": 5
        },
        "🦅 [레이 달리오 All-Weather 인컴 안정형] (고배당 45% + 코어 25% + 안전현금 20% + 테마 10%)": {
            "연금저축펀드": 45, "ISA": 25, "일반계좌(해외)": 15, "일반계좌(국내)": 10, "IRP및코인": 5
        },
        "🚀 [피터 린치 & 미너비니 공격 복리성장형] (코어 40% + 테마 25% + 퀀트스윙 20% + 고배당 5% + 현금 8% + 코인 2%)": {
            "일반계좌(해외)": 35, "연금저축펀드": 30, "ISA": 20, "일반계좌(국내)": 10, "IRP및코인": 5
        },
        "💎 [나심 탈레브 바벨 인컴 & 혁신 전략] (코어/고배당/현금 80% + 테마/스윙/코인 20%)": {
            "연금저축펀드": 40, "ISA": 25, "일반계좌(해외)": 20, "일반계좌(국내)": 10, "IRP및코인": 5
        }
    }

    current_saved_cat_targets = raw_p_data.get("target_allocation", {}).get("categories", DEFAULT_CATEGORY_TARGETS)
    current_saved_acc_targets = raw_p_data.get("target_allocation", {}).get("accounts", DEFAULT_ACCOUNT_TARGETS)

    preset_choice = st.radio(
        "글로벌 거장들의 검증된 포트폴리오 모델을 선택하면, Step 2의 슬라이더가 100% 자동 배치됩니다:",
        options=[
            "⚖️ [JTI 밸런스 Dual-Track (추천)] (코어 35% + 고배당 30% + 테마 15% + 스윙 10% + 현금 8% + 코인 2%)",
            "🦅 [레이 달리오 All-Weather 인컴 안정형] (고배당 45% + 코어 25% + 안전현금 20% + 테마 10%)",
            "🚀 [피터 린치 & 미너비니 공격 복리성장형] (코어 40% + 테마 25% + 퀀트스윙 20% + 고배당 5% + 현금 8% + 코인 2%)",
            "💎 [나심 탈레브 바벨 인컴 & 혁신 전략] (코어/고배당/현금 80% + 테마/스윙/코인 20%)",
            "🎛️ [사용자 직접 커스텀 조절]"
        ],
        index=0,
        key="alloc_preset_radio"
    )

    if "prev_alloc_preset" not in st.session_state:
        st.session_state["prev_alloc_preset"] = preset_choice

    # 프리셋 선택 변경 시 Step 2 슬라이더 세션 상태 강제 동기화 (문제 4 완벽 해결!)
    if st.session_state["prev_alloc_preset"] != preset_choice:
        st.session_state["prev_alloc_preset"] = preset_choice
        if preset_choice in preset_cat_map:
            p_cat = preset_cat_map[preset_choice]
            st.session_state["slider_cat_core"] = p_cat.get("🌱 글로벌 코어 지수", 35)
            st.session_state["slider_cat_div"] = p_cat.get("💰 고배당 & 인컴", 30)
            st.session_state["slider_cat_theme"] = p_cat.get("🤖 테마 & 미래혁신", 15)
            st.session_state["slider_cat_swing"] = p_cat.get("🚀 퀀트 스윙 & 모멘텀", 10)
            st.session_state["slider_cat_coin"] = p_cat.get("🪙 대체자산 (코인)", 2)
            st.session_state["slider_cat_cash"] = p_cat.get("💵 안전 현금", 8)
        if preset_choice in preset_acc_map:
            p_acc = preset_acc_map[preset_choice]
            st.session_state["slider_acc_pension"] = p_acc.get("연금저축펀드", 40)
            st.session_state["slider_acc_overseas"] = p_acc.get("일반계좌(해외)", 25)
            st.session_state["slider_acc_isa"] = p_acc.get("ISA", 20)
            st.session_state["slider_acc_domestic"] = p_acc.get("일반계좌(국내)", 10)
            st.session_state["slider_acc_irp"] = p_acc.get("IRP및코인", 5)
        st.rerun()

    if preset_choice in preset_cat_map:
        selected_cat_weights = preset_cat_map[preset_choice]
        selected_acc_weights = preset_acc_map.get(preset_choice, {k: int(v * 100) for k, v in DEFAULT_ACCOUNT_TARGETS.items()})
    else:
        selected_cat_weights = {k: int(v * 100) if v <= 1.0 else int(v) for k, v in current_saved_cat_targets.items()}
        selected_acc_weights = {k: int(v * 100) if v <= 1.0 else int(v) for k, v in current_saved_acc_targets.items()}

    st.markdown("---")

    # --------------------------------------------------------------------------
    # 🎛️ Step 2: Dual-Lens 인터랙티브 컨트롤 타워 & 실시간 퀀트 계기판
    # --------------------------------------------------------------------------
    st.markdown("### 🎛️ Step 2: Dual-Lens 인터랙티브 조절기 & 실시간 퀀트 계기판 (What-If)")

    ctrl_col, dash_col = st.columns([1.1, 1.3])

    with ctrl_col:
        lens_subtab1, lens_subtab2 = st.tabs([
            "렌즈 1: 📊 6대 자산 팩터 배분",
            "렌즈 2: 🏦 5대 절세 계좌 배분"
        ])

        with lens_subtab1:
            st.caption("🌱 코어, 💰 배당, 🤖 테마, 🚀 스윙, 🪙 코인, 💵 현금의 비중을 설정합니다.")
            sim_core = st.slider("🌱 글로벌 코어 지수 (%)", 0, 100, selected_cat_weights.get("🌱 글로벌 코어 지수", 35), step=1, key="slider_cat_core")
            sim_div = st.slider("💰 고배당 & 인컴 (%)", 0, 100, selected_cat_weights.get("💰 고배당 & 인컴", 30), step=1, key="slider_cat_div")
            sim_theme = st.slider("🤖 테마 & 미래혁신 (%)", 0, 100, selected_cat_weights.get("🤖 테마 & 미래혁신", 15), step=1, key="slider_cat_theme")
            sim_swing = st.slider("🚀 퀀트 스윙 & 모멘텀 (%)", 0, 100, selected_cat_weights.get("🚀 퀀트 스윙 & 모멘텀", 10), step=1, key="slider_cat_swing")
            sim_coin = st.slider("🪙 대체자산 (코인) (%)", 0, 20, selected_cat_weights.get("🪙 대체자산 (코인)", 2), step=1, key="slider_cat_coin")
            sim_cash = st.slider("💵 안전 현금 (%)", 0, 50, selected_cat_weights.get("💵 안전 현금", 8), step=1, key="slider_cat_cash")

            tot_cat_w = sim_core + sim_div + sim_theme + sim_swing + sim_coin + sim_cash
            if tot_cat_w == 100:
                st.success(f"✅ 팩터 목표 비중 합계: **{tot_cat_w}%** (정상)")
            else:
                cat_diff = 100 - tot_cat_w
                st.warning(f"⚠️ 팩터 비중 합계: **{tot_cat_w}%** (100%가 되도록 {'+' if cat_diff > 0 else ''}{cat_diff}% 조정 필요)")

            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("⚖️ 팩터 100% 자동 맞춤", key="btn_norm_cat"):
                    if tot_cat_w > 0:
                        sim_core = int(round(sim_core / tot_cat_w * 100))
                        sim_div = int(round(sim_div / tot_cat_w * 100))
                        sim_theme = int(round(sim_theme / tot_cat_w * 100))
                        sim_swing = int(round(sim_swing / tot_cat_w * 100))
                        sim_coin = int(round(sim_coin / tot_cat_w * 100))
                        sim_cash = 100 - (sim_core + sim_div + sim_theme + sim_swing + sim_coin)
                        st.rerun()

            with btn_col2:
                if st.button("💾 이 팩터 목표 영구 저장", type="primary", key="btn_save_cat"):
                    norm_denom = tot_cat_w if tot_cat_w > 0 else 100
                    new_cat_targets = {
                        "🌱 글로벌 코어 지수": round(sim_core / norm_denom, 4),
                        "💰 고배당 & 인컴": round(sim_div / norm_denom, 4),
                        "🤖 테마 & 미래혁신": round(sim_theme / norm_denom, 4),
                        "🚀 퀀트 스윙 & 모멘텀": round(sim_swing / norm_denom, 4),
                        "🪙 대체자산 (코인)": round(sim_coin / norm_denom, 4),
                        "💵 안전 현금": round(sim_cash / norm_denom, 4)
                    }
                    save_target_allocation(category_targets=new_cat_targets)
                    st.success("🎉 6대 자산 팩터 목표가 영구 저장되었습니다!")
                    st.rerun()

        with lens_subtab2:
            st.caption("🏦 세제 혜택(과세이연/비과세)과 운용 목적에 맞춘 계좌별 목표 비중을 설정합니다.")
            sim_acc_pension = st.slider("🏛️ 연금저축펀드 (%)", 0, 100, selected_acc_weights.get("연금저축펀드", 40), step=1, key="slider_acc_pension")
            sim_acc_overseas = st.slider("🇺🇸 일반계좌(해외) (%)", 0, 100, selected_acc_weights.get("일반계좌(해외)", 25), step=1, key="slider_acc_overseas")
            sim_acc_isa = st.slider("🪙 ISA 계좌 (%)", 0, 100, selected_acc_weights.get("ISA", 20), step=1, key="slider_acc_isa")
            sim_acc_domestic = st.slider("🇰🇷 일반계좌(국내) (%)", 0, 100, selected_acc_weights.get("일반계좌(국내)", 10), step=1, key="slider_acc_domestic")
            sim_acc_irp = st.slider("🛡️ IRP 및 코인 (%)", 0, 50, selected_acc_weights.get("IRP및코인", 5), step=1, key="slider_acc_irp")

            tot_acc_w = sim_acc_pension + sim_acc_overseas + sim_acc_isa + sim_acc_domestic + sim_acc_irp
            if tot_acc_w == 100:
                st.success(f"✅ 계좌 목표 비중 합계: **{tot_acc_w}%** (정상)")
            else:
                acc_diff = 100 - tot_acc_w
                st.warning(f"⚠️ 계좌 비중 합계: **{tot_acc_w}%** (100%가 되도록 {'+' if acc_diff > 0 else ''}{acc_diff}% 조정 필요)")

            acc_btn_col1, acc_btn_col2 = st.columns(2)
            with acc_btn_col1:
                if st.button("⚖️ 계좌 100% 자동 맞춤", key="btn_norm_acc"):
                    if tot_acc_w > 0:
                        sim_acc_pension = int(round(sim_acc_pension / tot_acc_w * 100))
                        sim_acc_overseas = int(round(sim_acc_overseas / tot_acc_w * 100))
                        sim_acc_isa = int(round(sim_acc_isa / tot_acc_w * 100))
                        sim_acc_domestic = int(round(sim_acc_domestic / tot_acc_w * 100))
                        sim_acc_irp = 100 - (sim_acc_pension + sim_acc_overseas + sim_acc_isa + sim_acc_domestic)
                        st.rerun()

            with acc_btn_col2:
                if st.button("💾 이 계좌 목표 영구 저장", type="primary", key="btn_save_acc"):
                    norm_acc_denom = tot_acc_w if tot_acc_w > 0 else 100
                    new_acc_targets = {
                        "연금저축펀드": round(sim_acc_pension / norm_acc_denom, 4),
                        "일반계좌(해외)": round(sim_acc_overseas / norm_acc_denom, 4),
                        "ISA": round(sim_acc_isa / norm_acc_denom, 4),
                        "일반계좌(국내)": round(sim_acc_domestic / norm_acc_denom, 4),
                        "IRP및코인": round(sim_acc_irp / norm_acc_denom, 4)
                    }
                    save_target_allocation(account_targets=new_acc_targets)
                    st.success("🎉 5대 계좌 목표가 영구 저장되었습니다!")
                    st.rerun()

    sim_cat_weights = {
        "🌱 글로벌 코어 지수": sim_core,
        "💰 고배당 & 인컴": sim_div,
        "🤖 테마 & 미래혁신": sim_theme,
        "🚀 퀀트 스윙 & 모멘텀": sim_swing,
        "🪙 대체자산 (코인)": sim_coin,
        "💵 안전 현금": sim_cash
    }

    # --------------------------------------------------------------------------
    # 📊 실시간 퀀트 지표 연산 (Institutional Metrics)
    # --------------------------------------------------------------------------
    quant_res = calculate_portfolio_quant_metrics(sim_cat_weights, total_equity)

    with dash_col:
        st.markdown("**📊 기관투자가급 포트폴리오 퀀트 계기판 (실시간 연산)**")

        k1, k2, k3 = st.columns(3)
        with k1:
            h_score = quant_res['health_score']
            h_badge = "🟢 최상급" if h_score >= 85 else ("🔵 우수" if h_score >= 70 else "🟡 편중 주의")
            st.metric("🎯 밸런스 지수", f"{h_score}점 / 100", delta=h_badge)
        with k2:
            st.metric("📈 기대 연수익률(CAGR)", f"+{quant_res['expected_cagr']*100:.1f}%", delta="자산 가중 성장률")
        with k3:
            st.metric("🛡️ 포트폴리오 변동성", f"{quant_res['portfolio_volatility']*100:.1f}%", delta=f"샤프: {quant_res['sharpe_ratio']:.2f}")

        k4, k5, k6 = st.columns(3)
        with k4:
            st.metric(
                "💰 예상 연간 배당금",
                f"연 {int(quant_res['annual_dividend_krw']):,}원",
                delta=f"배당률 {quant_res['dividend_yield']*100:.2f}%"
            )
        with k5:
            st.metric(
                "💵 예상 월간 배당금",
                f"월 {int(quant_res['monthly_dividend_krw']):,}원",
                delta=f"안전 현금 {quant_res['normalized_weights'].get('💵 안전 현금', 0)*100:.0f}%"
            )
        with k6:
            st.metric(
                "⚖️ 성장 vs 인컴 비율",
                f"{quant_res['growth_ratio']}% : {quant_res['income_ratio']}%",
                delta="성장형 우위" if quant_res['growth_ratio'] > quant_res['income_ratio'] else "인컴 우위"
            )

        # 도넛 차트 비교 (현재 vs 시뮬레이션 목표)
        ch_c1, ch_c2 = st.columns(2)
        cat_labels = list(my_analysis['categories_data'].keys())
        cat_curr_vals = [my_analysis['categories_data'][k]['eval_krw'] for k in cat_labels]
        fig_curr_cat = go.Figure(data=[go.Pie(
            labels=cat_labels,
            values=cat_curr_vals,
            hole=.48,
            textinfo='percent',
            title=dict(text='현재 포트폴리오', font=dict(size=13, color='#1E293B')),
            marker=dict(colors=['#3B82F6', '#10B981', '#8B5CF6', '#F59E0B', '#EC4899', '#64748B'])
        )])
        fig_curr_cat.update_layout(height=230, margin=dict(t=20, b=20, l=10, r=10), showlegend=False)

        cat_sim_vals = [sim_cat_weights.get(k, 0) for k in cat_labels]
        fig_sim_cat = go.Figure(data=[go.Pie(
            labels=cat_labels,
            values=cat_sim_vals,
            hole=.48,
            textinfo='percent',
            title=dict(text='시뮬레이션 목표', font=dict(size=13, color='#1E293B')),
            marker=dict(colors=['#3B82F6', '#10B981', '#8B5CF6', '#F59E0B', '#EC4899', '#64748B'])
        )])
        fig_sim_cat.update_layout(height=230, margin=dict(t=20, b=20, l=10, r=10), showlegend=False)

        with ch_c1:
            st.plotly_chart(fig_curr_cat, use_container_width=True)
        with ch_c2:
            st.plotly_chart(fig_sim_cat, use_container_width=True)

    # --------------------------------------------------------------------------
    # 🏷️ [항목 5] 6대 팩터 × 실제 내 보유 종목 전수 매핑 & 원클릭 재분류 인스펙터
    # --------------------------------------------------------------------------
    st.markdown("---")
    st.markdown("#### 🏷️ 6대 자산 팩터 × 내 실제 보유 종목 전수 매핑 & 원클릭 재분류 인스펙터")
    st.caption("위 6대 팩터 슬라이더를 조정할 때, 내 보유 종목 중 어떤 자산이 실제로 연결되어 있는지 확인하고 필요 시 팩터 분류를 직접 변경할 수 있습니다.")

    factor_map = get_holding_factor_map(my_analysis)
    
    # 팩터별 카드/탭 구성
    f_cols = st.columns(3)
    f_items = list(factor_map.items())
    for idx, (f_name, f_data) in enumerate(f_items):
        with f_cols[idx % 3]:
            with st.expander(f"{f_name} ({f_data['count']}개 종목 / {int(f_data['total_eval']):,}원, {f_data['weight']:.1f}%)", expanded=(idx < 2)):
                if f_data['holdings']:
                    for h in f_data['holdings']:
                        st.markdown(f"**· {h['종목명']}** (`{h['티커']}`) | {h['계좌명']}")
                        st.caption(f"보유: {h['수량']:,}주 | 평가: {int(h['평가금액']):,}원 ({h['비중']:.1f}%) | 연배당: {int(h['예상연배당']):,}원")
                else:
                    st.caption("연결된 보유 종목이 없습니다 (현금 또는 미보유).")

    with st.expander("⚙️ [원클릭 자산 재분류] 내 종목의 팩터(코어/배당/테마/스윙 등)를 직접 변경하기", expanded=False):
        st.info("💡 종목의 자산군 분류가 마음에 들지 않으실 경우(예: 'NVDA'를 테마에서 스윙으로 변경 등), 아래에서 변경하시면 포트폴리오 분석 및 자산 배분 비중에 즉각 영구 반영됩니다.")
        
        all_holdings_list = []
        for acc_name, acc_info in my_analysis['accounts'].items():
            for h in acc_info.get('holdings', []):
                all_holdings_list.append({
                    "display": f"[{acc_name}] {h['종목명']} ({h['티커']}) - 현재: {h.get('자산분류', '기타')}",
                    "계좌명": acc_name,
                    "티커": h['티커'],
                    "종목명": h['종목명'],
                    "현재자산군": h.get('자산분류', '🌱 글로벌 코어 지수')
                })
        
        if all_holdings_list:
            rc1, rc2, rc3 = st.columns([2.5, 1.5, 1])
            with rc1:
                sel_reclass = st.selectbox(
                    "재분류할 종목 선택",
                    options=range(len(all_holdings_list)),
                    format_func=lambda i: all_holdings_list[i]["display"],
                    key="reclass_holding_select"
                )
            target_item = all_holdings_list[sel_reclass]
            with rc2:
                available_categories = [
                    "🌱 글로벌 코어 지수",
                    "💰 고배당 & 인컴",
                    "🤖 테마 & 미래혁신",
                    "🚀 퀀트 스윙 & 모멘텀",
                    "🪙 대체자산 (코인)",
                    "💵 안전 현금"
                ]
                curr_idx = available_categories.index(target_item["현재자산군"]) if target_item["현재자산군"] in available_categories else 0
                new_cat_choice = st.selectbox("새로운 자산 팩터 선택", options=available_categories, index=curr_idx, key="new_cat_choice")
            with rc3:
                st.write("")
                st.write("")
                if st.button("🏷️ 팩터 변경 저장", type="primary", use_container_width=True, key="btn_apply_reclass"):
                    ok = update_holding_asset_category(target_item["계좌명"], target_item["티커"], new_cat_choice)
                    if ok:
                        st.success(f"🎉 [{target_item['종목명']}]이(가) '{new_cat_choice}'(으)로 재분류되었습니다!")
                        st.rerun()
                    else:
                        st.error("재분류 저장 중 오류가 발생했습니다.")

    st.markdown("---")

    # --------------------------------------------------------------------------
    # 🗺️ Step 3: 5대 계좌 × 6대 자산 팩터 크로스 매트릭스 & 세제 최적화 진단
    # --------------------------------------------------------------------------
    st.markdown("### 🗺️ Step 3: 5대 계좌 × 6대 자산 팩터 크로스 매트릭스 & 세제 최적화 진단 (Asset Location)")
    st.caption("어느 계좌에 어떤 자산군이 배치되어 있는지 전수 분석하고, 배당소득세(15.4%) 및 양도소득세(22%) 절세 효율성을 정밀 평가합니다.")

    cross_data = get_cross_lens_matrix(my_analysis)
    matrix_df = cross_data['matrix_df']

    # 매트릭스 테이블 출력 (Pandas 1.x & 2.x 완전 호환 — applymap 완전 제거)
    def _fmt_cell(x):
        if isinstance(x, (int, float)):
            return f"{int(x):,}원" if x > 0 else "-"
        return str(x)
    try:
        # Pandas 2.1+ : DataFrame.map(func) 로 element-wise 적용
        disp_matrix = matrix_df.map(_fmt_cell)
    except TypeError:
        # Pandas 2.0 이하 fallback
        disp_matrix = matrix_df.applymap(_fmt_cell)
    st.dataframe(disp_matrix, use_container_width=True)

    # [항목 6] 세제 진단 엔진 연동
    tax_diag = get_tax_leakage_diagnosis(my_analysis)

    # 3대 세제 최적화 정밀 진단 카드
    t_c1, t_c2, t_c3 = st.columns(3)
    with t_c1:
        tax_pct = cross_data['tax_favored_pct']
        t_badge = "🟢 절세 최적" if tax_pct >= 50 else ("🟡 보통" if tax_pct >= 30 else "🔴 절세계좌 확대 시급")
        st.info(
            f"🏛️ **절세 계좌 비중 (연금+ISA+IRP)**: **{tax_pct:.1f}%** ({t_badge})\n\n"
            f"- 현재 절세 계좌 총 자산: 약 **{int(cross_data['tax_favored_eval']):,}원**\n"
            f"- 매매차익 비과세 및 배당소득세(15.4%) 과세이연 효과가 복리로 강력히 작동 중입니다.\n"
            f"- **ISA 연간 납입한도(2,000만 원)**를 적극 활용하여 일반계좌 자산을 점진 이전 권장합니다."
        )
    with t_c2:
        annual_leak = tax_diag.get('annual_dividend_tax_leakage', 0)
        ten_year_leak = tax_diag.get('ten_year_compounded_leakage', 0)
        st.warning(
            f"⚠️ **일반계좌 배당세(15.4%) 누수 진단**\n\n"
            f"- 일반계좌(국내/해외) 배당 평가액: **{int(tax_diag.get('taxable_eval', 0)):,}원**\n"
            f"- 매년 원천징수로 국세청에 자동 납부되는 배당세: **약 {int(annual_leak):,}원/년**\n"
            f"- 💡 **10년 복리 환산 절세 손실액**: **약 {int(ten_year_leak):,}원**\n"
            f"- ➔ *고배당 ETF(SCHD, JEPI 등)는 ISA 또는 연금저축에 우선 배치하는 것이 복리 극대화의 핵심입니다.*"
        )
    with t_c3:
        cap_gain_tax = tax_diag.get('capital_gain_tax_free_limit', 2500000)
        us_eval = matrix_df.loc['일반계좌(해외)', '계좌 합계'] if '일반계좌(해외)' in matrix_df.index else 0
        st.success(
            f"🎯 **해외계좌 양도소득세 250만 원 비과세 공제 캘린더**\n\n"
            f"- 일반계좌(해외) 총 평가액: **{int(us_eval):,}원**\n"
            f"- 1년 연간 비과세 공제 한도: **{int(cap_gain_tax):,}원**\n"
            f"- 📌 **실전 절세 팁**: 수익권인 미국 주식은 연말(12월 말) 전에 250만 원 한도 내에서 분할 매도 후 즉시 재매수하여 취득단가를 높이면, **세금 0원**으로 수익을 평생 비과세 확정 지을 수 있습니다."
        )

    st.markdown("---")

    # --------------------------------------------------------------------------
    # 📋 Step 4: 스마트 리밸런싱 실행 센터 (2가지 모드)
    # --------------------------------------------------------------------------
    st.markdown("### 📋 Step 4: 스마트 리밸런싱 실행 센터")

    rebal_tab1, rebal_tab2 = st.tabs([
        "💡 [모드 1] 스마트 신규 입금 리밸런싱 (No-Sell, 월 적립금 유입으로 갭 메우기)",
        "🔄 [모드 2] 보유 자산 매도/매수 정밀 리밸런싱 (Full Portfolio Rebalancing)"
    ])

    with rebal_tab1:
        st.markdown(
            "기존 주식을 굳이 팔지 않고, **이번 달에 내가 추가로 적립/투자할 현금**을 "
            "현재 목표 비중에서 가장 부족한 자산군과 계좌로 스마트 배분하여 1원 단위까지 분할 매수 주문서를 자동 산출합니다."
        )

        inflow_col1, inflow_col2 = st.columns([1, 2])
        with inflow_col1:
            deposit_input = st.slider(
                "💵 이번 달 추가 투자(적립) 금액 (원)",
                min_value=100000,
                max_value=5000000,
                value=1000000,
                step=100000,
                help="이번 달 월급이나 여유 자금에서 추가 입금할 금액을 입력하세요."
            )
            st.metric("🎯 신규 투입 총액", f"{int(deposit_input):,}원")

        with inflow_col2:
            deposit_orders = calculate_smart_deposit_rebalancing(my_analysis, deposit_input, sim_cat_weights)
            if deposit_orders:
                st.markdown(f"**📌 이번 달 {int(deposit_input):,}원 스마트 분할 매수 실행 주문표:**")
                dep_df = pd.DataFrame(deposit_orders)
                # 우선순위 티어 추가
                dep_df.insert(0, "우선순위", [f"🥇 Tier 1 (최우선)" if i == 0 else f"🥈 Tier {i+1} (권장)" for i in range(len(dep_df))])
                st.dataframe(dep_df, use_container_width=True, hide_index=True)

                st.markdown("""
                <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-left: 4px solid #3B82F6; border-radius: 6px; padding: 10px 14px; margin-top: 8px;">
                    <b>📱 MTS/HTS 실천 3단계 체크리스트</b><br>
                    <span style="font-size: 0.88rem; color: #475569;">
                    1. <b>예수금 이체</b>: 각 추천 계좌(연금저축/ISA/일반)에 위 권장 금액만큼 예수금을 분할 입금합니다.<br>
                    2. <b>Tier 1 최우선 매수</b>: 현재 비중 부족률이 가장 큰 1순위 자산군부터 현재가 기준 1~2호가 아래에 분할 매수 주문을 제출합니다.<br>
                    3. <b>해외 환전 팁</b>: 해외계좌 자산은 증권사 '원화주문(자동환전) 서비스'를 이용하면 별도 환전 수수료 없이 밤 11시 30분에 자동 체결됩니다.
                    </span>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("현재 모든 자산군이 목표 비중에 완벽히 도달해 있습니다.")

    with rebal_tab2:
        st.markdown("현재 총자산 내에서 비중이 초과된 자산을 매도하여 부족한 자산군을 채우는 전수 리밸런싱 계획표입니다.")
        
        rebal_rows = []
        for cat_name, cat_info in my_analysis['categories_data'].items():
            curr_eval = cat_info['eval_krw']
            curr_w = (curr_eval / total_equity * 100.0) if total_equity > 0 else 0.0
            tgt_w = float(sim_cat_weights.get(cat_name, 0.0))
            tgt_eval = total_equity * (tgt_w / 100.0)
            rebal_krw = tgt_eval - curr_eval
            
            h_names = [h['종목명'] for h in cat_info['holdings']]
            h_str = ", ".join(h_names) if h_names else "현금 잔고"
            
            if abs(rebal_krw) < 100000:
                act_text = "🟢 비중 적정 (유지)"
                priority = "유지"
            elif rebal_krw > 0:
                act_text = f"🔵 +{int(rebal_krw):,}원 추가 매수/적립"
                priority = "매수 필요"
            else:
                act_text = f"🟠 -{int(abs(rebal_krw)):,}원 이익 실현/축소"
                priority = "비중 축소"

            rebal_rows.append({
                "우선순위": priority,
                "자산 팩터": cat_name,
                "현재 평가액": f"{int(curr_eval):,}원",
                "현재 비중": f"{curr_w:.1f}%",
                "목표 비중": f"{tgt_w:.0f}%",
                "목표 평가액": f"{int(tgt_eval):,}원",
                "리밸런싱 실행 제언": act_text,
                "포함된 내 보유 종목": h_str
            })

        st.dataframe(pd.DataFrame(rebal_rows), use_container_width=True, hide_index=True)

    st.markdown("---")

    # --------------------------------------------------------------------------
    # 🛡️ Step 5: 과거 3대 위기 시나리오 스트레스 테스트 & [항목 7] 월가 수석 PB 정밀 감사 보고서
    # --------------------------------------------------------------------------
    st.markdown("### 🛡️ Step 5: 과거 3대 위기 시나리오 스트레스 테스트 & AI PB 투자심의위원회(IC) 정밀 감사")

    stress_col, audit_col = st.columns([1.1, 1.3])

    with stress_col:
        st.markdown("**📉 과거 대표적 3대 경제 위기 시뮬레이션 (방어력 검증)**")
        
        stress_df = pd.DataFrame({
            "위기 시나리오": ["2008 금융위기", "2020 코로나 쇼크", "2022 인플레 급락장"],
            "벤치마크 낙폭": [-50.0, -34.0, -33.0],
            "내 포트폴리오 예상 낙폭": [
                round(quant_res['stress_2008'] * 100, 1),
                round(quant_res['stress_2020'] * 100, 1),
                round(quant_res['stress_2022'] * 100, 1)
            ]
        })

        fig_stress = go.Figure()
        fig_stress.add_trace(go.Bar(
            name="벤치마크 (S&P/나스닥 몰빵)",
            x=stress_df["위기 시나리오"],
            y=stress_df["벤치마크 낙폭"],
            marker_color="#EF4444"
        ))
        fig_stress.add_trace(go.Bar(
            name="내 시뮬레이션 포트폴리오",
            x=stress_df["위기 시나리오"],
            y=stress_df["내 포트폴리오 예상 낙폭"],
            marker_color="#10B981"
        ))
        fig_stress.update_layout(
            barmode="group",
            height=260,
            yaxis_title="예상 최대 낙폭(MDD %)",
            margin=dict(t=20, b=20, l=20, r=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_stress, use_container_width=True)

    with audit_col:
        # [항목 7] 월가 수석 PB & 마크 미너비니 투자심의위원회 정밀 감사 보고서 렌더링
        macro_meta_info = st.session_state.get('results', {}).get('indices_summary', {}).get('meta', {}) if ('results' in st.session_state and st.session_state['results']) else {}
        audit_rep = generate_quant_pb_audit_report(sim_cat_weights, total_equity, my_analysis, macro_meta_info)

        st.markdown(f"**🏛️ 월가 수석 PB & 미너비니 투자심의위원회(IC) 공식 감사 인증서**")
        
        status_color = "#10B981" if "APPROVED" in audit_rep['approval_status'] else "#F59E0B"
        st.markdown(f"""
        <div style="background: #FFFFFF; border: 2px solid {status_color}; border-radius: 8px; padding: 12px 16px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 1.1rem; font-weight: 700; color: #1E293B;">📜 {audit_rep['committee_stamp']}</span>
                <span style="background: {status_color}; color: white; padding: 3px 10px; border-radius: 12px; font-weight: 700; font-size: 0.85rem;">{audit_rep['approval_status']}</span>
            </div>
            <div style="font-size: 0.92rem; color: #334155; line-height: 1.5; margin-bottom: 6px;">
                {audit_rep['summary_verdict']}
            </div>
            <div style="display: flex; gap: 16px; font-size: 0.82rem; color: #64748B;">
                <span>🌐 거시 국면 적합도: <b>{audit_rep['macro_fit_score']}점 / 100</b></span>
                <span>⚖️ 밸런스 지수: <b>{quant_res['health_score']}점</b></span>
                <span>📈 CAGR: <b>+{quant_res['expected_cagr']*100:.1f}%</b></span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("🩸 [레드팀 공격 진단] 최악의 경제 국면에서 어디가 깨지는가?", expanded=False):
            st.error(audit_rep['red_team_analysis'])

        with st.expander("🗓️ [단계별 실천 로드맵] 30일 / 90일 실행 마일스톤", expanded=False):
            st.markdown(audit_rep['action_roadmap'])

        ai_review_prompt = (
            f"대표님께서 방금 'Dual-Lens 스마트 자산 배분 빌더'에서 다음과 같이 포트폴리오 목표를 시뮬레이션하셨습니다:\n\n"
            f"- 목표 팩터 비중: 코어 지수 {sim_core}%, 고배당 {sim_div}%, 테마혁신 {sim_theme}%, 퀀트스윙 {sim_swing}%, 코인 {sim_coin}%, 안전현금 {sim_cash}%\n"
            f"- 퀀트 시뮬레이션 결과: 기대 연수익률(CAGR) +{quant_res['expected_cagr']*100:.1f}%, 변동성 {quant_res['portfolio_volatility']*100:.1f}%, 샤프지수 {quant_res['sharpe_ratio']:.2f}, 예상 연배당 {int(quant_res['annual_dividend_krw']):,}원 (월환산 {int(quant_res['monthly_dividend_krw']):,}원)\n"
            f"- 5대 계좌 현황: 연금저축/ISA 절세 계좌 비중 {cross_data['tax_favored_pct']:.1f}%, 일반계좌 배당세 노출 {cross_data['taxable_dividend_pct']:.1f}%\n"
            f"- 투자심의위원회 감사 결과: {audit_rep['approval_status']} (적합도 {audit_rep['macro_fit_score']}점)\n\n"
            f"월가 수석 PB이자 마크 미너비니 퀀트 자문관으로서, 이 포트폴리오의 실전 실행 전략과 리스크 헤지 팁을 3줄로 명확하게 브리핑해 주십시오."
        )

        if st.button("💬 이 자산 배분 모델로 전담 AI PB 심층 1:1 자문 시작", type="primary", use_container_width=True):
            st.session_state["pending_ai_prompt"] = ai_review_prompt
            st.success("🎉 전담 AI PB에게 자문 요청이 접수되었습니다! 상단 5번째 탭 [💬 AI 전담 PB]로 이동하시면 수석 PB의 브리핑이 시작됩니다.")
            st.success("🎉 전담 AI PB에게 자문 요청이 접수되었습니다! 상단 5번째 탭 [💬 AI 전담 PB]로 이동하시면 수석 PB의 정밀 검토 브리핑이 시작됩니다.")
            st.info("💡 위 상단 탭에서 **'💬 [AI 전담 PB] 1:1 주식 자문'** 탭을 클릭해 보세요!")


# ==============================================================================
# 탭 3: [시장 스캐너] SEPA 트렌드 & 정밀 VCP
# ==============================================================================
with tab_scanner:
    if 'results' not in st.session_state or run_btn:
        with st.spinner(f"🌐 [{select_mode}] 전 종목 실시간 시세 및 마크 미너비니 정밀 분석 중..."):
            st.session_state['results'] = run_quant_analysis(
                select_mode, raw_input_tickers, strategy_mode, capital, exchange_rate_input
            )

    results = st.session_state.get('results')

    if results:
        macro_meta = results['indices_summary'].get('meta', {})
        us_sc = macro_meta.get('us_score', 2.0)
        kr_sc = macro_meta.get('kr_score', 2.0)
        vix_meta = macro_meta.get('vix_info', {})
        status_desc = macro_meta.get('market_status_desc', "글로벌 벤치마크 지수와 VIX 공포지수를 종합 분석한 실시간 결과입니다.")
        action_guide = macro_meta.get('market_action_guide', "시장 추세를 확인 후 분할 매수로 접근하십시오.")

        # ----------------------------------------------------------------------
        # 🌟 글로벌 시장 상태 상세 설명 & 마크 미너비니 행동 지침 배너
        # ----------------------------------------------------------------------
        if "🔴" in results['market_status']:
            banner_bg = "#FEF2F2"
            banner_border = "#EF4444"
            banner_title_color = "#991B1B"
        elif "🟡" in results['market_status']:
            banner_bg = "#FFFBEB"
            banner_border = "#F59E0B"
            banner_title_color = "#92400E"
        else:
            banner_bg = "#F0FDF4"
            banner_border = "#10B981"
            banner_title_color = "#065F46"

        st.markdown(f"""
        <div style="background: {banner_bg}; border: 1px solid {banner_border}; border-left: 6px solid {banner_border}; border-radius: 8px; padding: 14px 18px; margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 1.15rem; font-weight: 700; color: {banner_title_color};">🌐 글로벌 시장 상태: {results['market_status']}</span>
                <span style="font-size: 0.85rem; font-weight: 600; color: #64748B;">기준: 4대 지수 50/200일선 정배열 + 실시간 VIX 복합 평가</span>
            </div>
            <div style="font-size: 0.93rem; color: #1E293B; margin-bottom: 6px; line-height: 1.5;">
                📌 <b>상태 분석 근거</b>: {status_desc}
            </div>
            <div style="font-size: 0.93rem; color: #1E293B; line-height: 1.5;">
                💡 <b>미너비니 실전 행동 지침</b>: <b>{action_guide}</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ----------------------------------------------------------------------
        # 📊 종합 지수 스코어 분해 & VIX 실시간 분석 5대 메트릭 카드
        # ----------------------------------------------------------------------
        st.subheader("📡 Stage 0: 글로벌 거시 경제 통합 필터 & 지수 분해")
        col1, col2, col3, col4, col5 = st.columns([1.1, 1.1, 1.1, 1.3, 1.1])

        with col1:
            st.metric(
                label="🌐 글로벌 종합 스코어",
                value=f"{results['market_score']:.2f} / 3.00",
                delta=f"{(results['market_score']/3.0)*100:.0f}% 달성"
            )
        with col2:
            st.metric(
                label="🇺🇸 미국 시장 스코어",
                value=f"{us_sc:.2f} / 3.00",
                delta="S&P 500 + 나스닥"
            )
        with col3:
            st.metric(
                label="🇰🇷 국내 시장 스코어",
                value=f"{kr_sc:.2f} / 3.00",
                delta="코스피 + 코스닥"
            )
        with col4:
            vix_val = results['vix']
            vix_chg = vix_meta.get('change', 0.0)
            vix_pct = vix_meta.get('change_pct', 0.0)
            vix_lvl = vix_meta.get('level', "정상")
            st.metric(
                label="📉 VIX 공포지수 (실시간)",
                value=f"{vix_val:.2f}",
                delta=f"{vix_chg:+.2f} ({vix_pct:+.1f}%) | {vix_lvl.split()[0]}",
                delta_color="inverse" if vix_chg >= 0 else "normal"
            )
        with col5:
            total_rec = len(results['final_df']) if results['final_df'] is not None else 0
            st.metric(
                label="🎯 분석 대상 / 추천수",
                value=f"{total_rec}개 추천",
                delta=f"총 {len(results['tickers'])}개 전수 스캔"
            )

        # 4대 지수 정밀 진단 현황표
        with st.expander("🔍 4대 주요 벤치마크 지수 (S&P500, 나스닥, 코스피, 코스닥) 상세 이평선 진단표 확인", expanded=False):
            idx_rows = []
            for idx_name, idx_data in results['indices_summary'].items():
                if idx_name == 'meta':
                    continue
                idx_rows.append({
                    "지수명": idx_name,
                    "현재가": f"{idx_data['curr']:,.2f}",
                    "20일선(단기)": f"{idx_data['ma20']:,.2f}",
                    "50일선(중기)": f"{idx_data['ma50']:,.2f}",
                    "200일선(장기)": f"{idx_data['ma200']:,.2f}",
                    "주가>50선": "✅ PASS" if idx_data['s1'] == 1 else "❌ FAIL",
                    "주가>200선": "✅ PASS" if idx_data['s2'] == 1 else "❌ FAIL",
                    "50선>200선(정배열)": "✅ PASS" if idx_data['s3'] == 1 else "❌ FAIL",
                    "지수 스코어": f"{idx_data['score']}.0 / 3.0",
                    "상태 진단": idx_data['status']
                })
            if idx_rows:
                st.dataframe(pd.DataFrame(idx_rows), use_container_width=True, hide_index=True)

        # ----------------------------------------------------------------------
        # 🦅 [항목 8] 마크 미너비니 하락장 특수 기동대: 위기를 기회로 바꾸는 4대 액션 플랜
        # ----------------------------------------------------------------------
        is_bear_status = ("🔴" in results['market_status'] or results['market_score'] < 1.8 or results['vix'] >= 22.0)
        
        st.markdown("""
        <div style="background: linear-gradient(135deg, #1E1B4B 0%, #312E81 100%); color: white; border-radius: 10px; padding: 14px 18px; margin-top: 14px; margin-bottom: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 1.12rem; font-weight: 700; color: #FDE047;">🦅 마크 미너비니 하락장 특수 전략: "위기는 차기 10배 텐배거를 줍는 최고의 기회다"</span>
                <span style="background: #4338CA; color: #E0E7FF; font-size: 0.8rem; padding: 2px 10px; border-radius: 12px; font-weight: 600;">Bear-Market Playbook</span>
            </div>
            <div style="font-size: 0.90rem; color: #E2E8F0; line-height: 1.5;">
                <i>"지수가 급락할 때 대중은 공포로 도망치지만, 프로는 지수가 하락함에도 불구하고 50일선 위에서 버티는 <b>차기 주도주(True Market Leaders)</b>를 사냥한다. 소극적 현금 100% 관망 대신, 철저한 리스크 통제 하에 위기를 기회로 만드십시오."</i>
            </div>
        </div>
        """, unsafe_allow_html=True)

        sp_col1, sp_col2, sp_col3, sp_col4 = st.columns(4)
        with sp_col1:
            st.info(
                "🎯 **액션 1: 2~3% 파일럿 정찰병**\n\n"
                "- 풀베팅 대신 **계좌의 2~3% 소액만 정찰병 투입**\n"
                "- 손절선은 매수가 대비 **-3% ~ -5%로 극단적 통제**\n"
                "- 정찰병이 수익을 낼 때만 피라미딩(추가매수)"
            )
        with sp_col2:
            st.warning(
                "🦅 **액션 2: 차기 황제주(RS 90+) 사냥**\n\n"
                "- 지수가 -10% 빠져도 **50일선/200일선 위에서 버티는 놈** 발굴\n"
                "- 시장 반등 첫날(Follow-Through Day) 가장 먼저 100~300% 폭등할 1순위 후보"
            )
        with sp_col3:
            st.success(
                "⚡ **액션 3: 패닉 과매도 바운스**\n\n"
                "- **재무 A급 우량주가 시장 패닉으로 RSI 30 미만** 빠질 때\n"
                "- 3~5일간의 기계적 기술적 반등(+8~15%) 구간에서 짧게 치고 빠지는 게릴라 전술"
            )
        with sp_col4:
            st.error(
                "🛡️ **액션 4: 인컴 피난처 바벨 전략**\n\n"
                "- **자산의 70~80%는 월배당/초단기 채권(JEPI, SGOV)**으로 방어벽\n"
                "- 남은 20% 이하로 주도주 돌파를 노리는 공수겸장 전략"
            )

        st.markdown("---")
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

            st.markdown("---")
            st.subheader("🔍 개별 종목 심층 캔들스틱 & 미너비니 지표 뷰어")

            selected_ticker = st.selectbox(
                "분석할 종목을 선택하세요",
                options=final_df['티커'].tolist(),
                format_func=lambda x: f"{x} - {final_df[final_df['티커']==x]['종목명'].iloc[0]}"
            )

            if selected_ticker:
                stock_row = final_df[final_df['티커'] == selected_ticker].iloc[0]
                df_stock = results['stock_dfs'].get(selected_ticker)

                # --------------------------------------------------------------
                # 1. 🌟 상단 미너비니 전략 진단 & 매매 포지션 가이드 배너
                # --------------------------------------------------------------
                curr_price_str = stock_row.get('현재가_표기', f"{stock_row.get('현재가', 0):,}")
                st.markdown(f"""
                <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-left: 5px solid #2563EB; border-radius: 8px; padding: 12px 18px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">
                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                        <div>
                            <span style="font-size: 1.25rem; font-weight: 700; color: #1E293B;">{stock_row['종목명']}</span>
                            <span style="color: #64748B; font-size: 0.95rem; margin-left: 8px;">({selected_ticker}) · {stock_row.get('섹터', 'Technology')}</span>
                        </div>
                        <div>
                            <span style="background: #EFF6FF; color: #2563EB; font-weight: 700; font-size: 0.9rem; padding: 4px 10px; border-radius: 6px; margin-right: 8px;">{stock_row.get('현재_단계', '2단계')}</span>
                            <span style="font-size: 1.2rem; font-weight: 700; color: #0F172A;">{curr_price_str}</span>
                        </div>
                    </div>
                    <div style="margin-top: 8px; font-size: 0.92rem; color: #334155;">
                        💡 <b>전략 행동 제언</b>: <span style="color: #2563EB; font-weight: 700;">{stock_row.get('전략제언', '보유')}</span> &nbsp;|&nbsp; 
                        <b>권장 비중</b>: <b>{stock_row.get('최종비중(%)', '4.0%')}</b> ({stock_row.get('매수수량', '0주')}) &nbsp;|&nbsp;
                        <b>재무 등급</b>: <b>{stock_row.get('재무등급', stock_row.get('등급', '🟢 Pass'))}</b> (ROE: {stock_row.get('ROE(%)', 12.0)}%, 이익성장: {stock_row.get('이익성장(%)', 10.0)}%)
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # --------------------------------------------------------------
                # 2. 📊 미너비니 4대 핵심 퀀트 지표 메트릭 카드
                # --------------------------------------------------------------
                v1, v2, v3, v4 = st.columns(4)
                
                disp_val = stock_row.get('피벗거리(%)', 0.0)
                pivot_dist = stock_row.get('피벗돌파율(%)', 0.0)
                with v1:
                    st.metric(
                        label="🎯 피벗/20일선 이격도",
                        value=f"{disp_val:+.1f}%",
                        delta=f"피벗 돌파율: {pivot_dist:+.1f}% (적정 < 5%)",
                        delta_color="normal" if 0 <= disp_val <= 3.5 else "inverse"
                    )
                
                vol_r = stock_row.get('거래량배수', 1.0)
                is_dry = stock_row.get('거래량고갈', False)
                with v2:
                    st.metric(
                        label="🔊 거래량 파워 (Vol Ratio)",
                        value=f"{vol_r:.2f}배",
                        delta="거래량 마른 눌림목" if is_dry else ("거래량 급증 돌파" if vol_r >= 1.3 else "평균 거래량"),
                        delta_color="normal" if (is_dry or vol_r >= 1.3) else "off"
                    )

                is_vcp = stock_row.get('VCP수축', False)
                is_pivot = stock_row.get('피벗초입돌파', False)
                with v3:
                    vcp_status = "💎 VCP 수축 완성" if is_vcp else ("🔥 피벗 초입 돌파" if is_pivot else "수축 진행 중")
                    st.metric(
                        label="⚡ VCP 변동성 수축",
                        value=vcp_status,
                        delta=f"트렌드: {stock_row.get('트렌드_템플릿', 'PASS')}"
                    )

                stop_price = stock_row.get('손절라인', float(stock_row.get('현재가', 100.0)) * 0.93)
                stop_str = f"{int(stop_price):,}원" if str(selected_ticker).isdigit() else f"${stop_price:,.2f}"
                with v4:
                    win_pct = int(stock_row.get('승률', 0.45) * 100)
                    payoff = stock_row.get('손익비', 1.2)
                    st.metric(
                        label="🛡️ 안전 버퍼 손절선 (-7%)",
                        value=stop_str,
                        delta=f"승률 {win_pct}% (손익비 {payoff:.1f})",
                        delta_color="inverse"
                    )

                # --------------------------------------------------------------
                # 3. 📋 SEPA 8대 트렌드 템플릿 정밀 체크리스트
                # --------------------------------------------------------------
                st.markdown("##### 📋 SEPA 8대 트렌드 템플릿 정밀 진단 체크리스트")
                
                c_c1, c_c2 = st.columns(2)
                
                c1 = stock_row.get('c1', True)
                c2 = stock_row.get('c2', True)
                c3 = stock_row.get('c3', True)
                c4 = stock_row.get('c4', True)
                c5 = stock_row.get('c5', True)
                c6 = stock_row.get('c6', True)
                c7 = stock_row.get('c7', True)
                c8 = stock_row.get('c8', True)

                with c_c1:
                    st.markdown(f"""
                    - {'🟢' if c1 else '🔴'} **1. 주가 > 150일선 & 200일선**: {'조건 충족 (장기 우상향)' if c1 else '조건 미달 (하회)'}
                    - {'🟢' if c2 else '🔴'} **2. 150일선 > 200일선**: {'정배열 유지 (중장기 상승 국면)' if c2 else '역배열 (장기 침체)'}
                    - {'🟢' if c3 else '🔴'} **3. 200일선 1개월 추세**: {'우상향 지속 (상승 추세 확립)' if c3 else '하향세 (추세 훼손)'}
                    - {'🟢' if c4 else '🔴'} **4. 50일선 > 150/200일선**: {'단중기 정배열 (에너지 집중)' if c4 else '이평선 역배열'}
                    """)
                with c_c2:
                    st.markdown(f"""
                    - {'🟢' if c5 else '🔴'} **5. 52주 신저가 대비 반등**: {'+25% 이상 강한 회복 (바닥 탈출)' if c5 else '바닥권 횡보'}
                    - {'🟢' if c6 else '🔴'} **6. 52주 신고가 근접도**: {'신고가 대비 -25% 이내 위치' if c6 else '고점 대비 과도한 낙폭'}
                    - {'🟢' if c7 else '🔴'} **7. 벤치마크 상대강도(RS)**: {'S&P500 대비 6주간 RS 우상향' if c7 else '시장 대비 상대적 약세'}
                    - {'🟢' if c8 else '🔴'} **8. 50일선 지지 여부**: {'주가 > 50일선 (단기 추세 건전)' if c8 else '50일선 하회'}
                    """)

                # --------------------------------------------------------------
                # 4. 📈 심층 캔들스틱 및 거래량 이동평균 차트
                # --------------------------------------------------------------
                if df_stock is not None and not df_stock.empty:
                    # MultiIndex 또는 비정규 컬럼 방어적 정규화
                    if isinstance(df_stock.columns, pd.MultiIndex):
                        df_stock = extract_single_stock_df(df_stock, selected_ticker)

                    # 컬럼 대소문자 표준화
                    col_map = {c: str(c).strip().capitalize() for c in df_stock.columns}
                    df_stock = df_stock.rename(columns=col_map)

                    has_ohlc = all(col in df_stock.columns for col in ['Open', 'High', 'Low', 'Close'])
                    if has_ohlc and len(df_stock) >= 20:
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
                        df_stock_calc['MA20'] = df_stock_calc['Close'].rolling(20, min_periods=5).mean()
                        df_stock_calc['MA50'] = df_stock_calc['Close'].rolling(50, min_periods=10).mean()
                        df_stock_calc['MA150'] = df_stock_calc['Close'].rolling(150, min_periods=20).mean() if len(df_stock_calc) >= 150 else None
                        df_stock_calc['MA200'] = df_stock_calc['Close'].rolling(200, min_periods=30).mean() if len(df_stock_calc) >= 200 else None

                        fig.add_trace(go.Scatter(x=df_stock_calc.index, y=df_stock_calc['MA20'], line=dict(color='#F59E0B', width=1.5), name='MA20 (단기)'), row=1, col=1)
                        fig.add_trace(go.Scatter(x=df_stock_calc.index, y=df_stock_calc['MA50'], line=dict(color='#3B82F6', width=1.5), name='MA50 (중기)'), row=1, col=1)
                        if 'MA150' in df_stock_calc and df_stock_calc['MA150'] is not None:
                            fig.add_trace(go.Scatter(x=df_stock_calc.index, y=df_stock_calc['MA150'], line=dict(color='#8B5CF6', width=1.5), name='MA150 (장기)'), row=1, col=1)
                        if 'MA200' in df_stock_calc and df_stock_calc['MA200'] is not None:
                            fig.add_trace(go.Scatter(x=df_stock_calc.index, y=df_stock_calc['MA200'], line=dict(color='#EF4444', width=2), name='MA200 (추세 기준선)'), row=1, col=1)

                        vol_col = 'Volume' if 'Volume' in df_stock.columns else None
                        if vol_col:
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
                    else:
                        st.info("차트를 표시하기 위한 충분한 시세 데이터가 없습니다.")
                else:
                    st.info("선택한 종목의 시세 데이터를 불러올 수 없습니다.")


# ==============================================================================
# 탭 4: [백테스팅 & 복리] 10년 과거 검증 & 미래 부 시뮬레이터
# ==============================================================================
with tab_backtest:
    st.subheader("📈 10년 자산 백테스팅 & 미래 복리 부(Wealth) 시뮬레이터")
    st.markdown("과거 10년의 팩터 자산 성장 궤적을 실증하고, 향후 10년간 복리 적립과 배당 재투자로 형성되는 **월 배당 현금흐름 파이프라인**을 정밀 시뮬레이션합니다.")

    # 사용자 계좌 자산 로드 (기본 자산 산정용)
    if 'my_analysis' not in locals():
        raw_p_data = load_portfolio_data()
        my_analysis = analyze_my_portfolio(raw_p_data)
    default_init_capital = int(my_analysis.get('total_net_worth', 39000000)) if my_analysis.get('total_net_worth', 0) > 0 else 39000000

    sub_bt1, sub_bt2, sub_bt3 = st.tabs([
        "🧭 [과거 10년 검증] 6대 자산 팩터 포트폴리오 백테스트",
        "🌱 [미래 10년 부] 정기 적립 & 배당 재투자 복리 시뮬레이터",
        "🔍 [개별 종목 검증] SEPA 8대 조건 & 마크 미너비니 VCP 백테스트"
    ])

    # --------------------------------------------------------------------------
    # 서브탭 1: 6대 자산 팩터 포트폴리오 과거 10년 백테스팅
    # --------------------------------------------------------------------------
    with sub_bt1:
        st.markdown("#### 🧭 내 6대 자산 팩터 포트폴리오 과거 실증 백테스트")
        st.caption("내 포트폴리오의 6대 핵심 팩터(글로벌 코어, 고배당 인컴, 테마 혁신, 퀀트 스윙, 코인, 현금)를 실제 시장 데이터(S&P500, SCHD, QQQ, MTUM, BTC, 현금수익)와 합성하여 지난 3~10년 동안의 연평균 복리(CAGR), 최대 낙폭(MDD), 샤프 지수를 정밀 검증합니다.")

        p_col1, p_col2, p_col3 = st.columns([1.2, 1, 1.8])
        with p_col1:
            p_initial_cap = st.number_input(
                "초기 투자 원금 (원)",
                min_value=1000000,
                max_value=2000000000,
                value=default_init_capital,
                step=1000000,
                key="p_initial_cap"
            )
        with p_col2:
            p_period = st.selectbox(
                "검증 기간 선택",
                options=["3y", "5y", "10y"],
                index=1,
                key="p_period"
            )
        with p_col3:
            strategy_preset = st.selectbox(
                "자산 배분 모델 선택",
                options=[
                    "내 현재 계좌 실제 비중 반영",
                    "🏆 JTI 권장 올웨더 균형형 (코어35/배당30/테마15/스윙10/코인2/현금8)",
                    "💰 고배당 인컴 방어형 (배당50/코어25/현금15/테마5/스윙5)",
                    "🚀 테크 & 성장 모멘텀형 (테마35/코어30/스윙20/현금15)"
                ],
                index=0,
                key="strategy_preset"
            )

        # 배분 가중치 설정
        if strategy_preset == "내 현재 계좌 실제 비중 반영":
            current_w = my_analysis.get('category_weights', {})
            total_w = sum(current_w.values())
            if total_w > 0:
                calc_weights = {k: v / total_w for k, v in current_w.items()}
            else:
                calc_weights = {
                    "🌱 글로벌 코어 지수": 0.35, "💰 고배당 & 인컴": 0.30,
                    "🤖 테마 & 미래혁신": 0.15, "🚀 퀀트 스윙 & 모멘텀": 0.10,
                    "🪙 대체자산 (코인)": 0.02, "💵 안전 현금": 0.08
                }
        elif "고배당" in strategy_preset:
            calc_weights = {
                "🌱 글로벌 코어 지수": 0.25, "💰 고배당 & 인컴": 0.50,
                "🤖 테마 & 미래혁신": 0.05, "🚀 퀀트 스윙 & 모멘텀": 0.05,
                "🪙 대체자산 (코인)": 0.00, "💵 안전 현금": 0.15
            }
        elif "테크" in strategy_preset:
            calc_weights = {
                "🌱 글로벌 코어 지수": 0.30, "💰 고배당 & 인컴": 0.00,
                "🤖 테마 & 미래혁신": 0.35, "🚀 퀀트 스윙 & 모멘텀": 0.20,
                "🪙 대체자산 (코인)": 0.00, "💵 안전 현금": 0.15
            }
        else:
            calc_weights = {
                "🌱 글로벌 코어 지수": 0.35, "💰 고배당 & 인컴": 0.30,
                "🤖 테마 & 미래혁신": 0.15, "🚀 퀀트 스윙 & 모멘텀": 0.10,
                "🪙 대체자산 (코인)": 0.02, "💵 안전 현금": 0.08
            }

        p_run_btn = st.button("🚀 포트폴리오 백테스트 실행", type="primary", use_container_width=True, key="p_run_btn")

        cached_port = st.session_state.get('port_bt_cache')
        is_port_valid = (
            cached_port is not None
            and isinstance(cached_port, dict)
            and 'hist_chart_df' in cached_port
            and 'yearly_records' in cached_port
            and 'cagr' in cached_port
        )

        if p_run_btn or not is_port_valid:
            with st.spinner("⏳ 6대 자산 팩터 및 벤치마크 과거 10년 시세 다운로드 & 포트폴리오 합성 분석 중..."):
                new_port_res = run_portfolio_historical_backtest(
                    initial_capital=p_initial_cap,
                    period=p_period,
                    category_weights=calc_weights
                )
                if new_port_res is not None:
                    st.session_state['port_bt_cache'] = new_port_res
                else:
                    st.session_state.pop('port_bt_cache', None)

        p_res = st.session_state.get('port_bt_cache')

        if p_res and isinstance(p_res, dict):
            st.markdown(f"### 🏆 포트폴리오 성과 분석 성적표 [검증 기간: 최근 {p_res.get('years', 5)}년]")
            pm1, pm2, pm3, pm4, pm5 = st.columns(5)
            with pm1:
                st.metric(
                    label="💰 최종 평가 자산",
                    value=f"{int(p_res.get('final_capital', 0)):,}원",
                    delta=f"{p_res.get('total_return_pct', 0.0):+.1f}% 누적수익"
                )
            with pm2:
                st.metric(
                    label="📈 연평균 복리(CAGR)",
                    value=f"{p_res.get('cagr', 0.0):+.1f}%",
                    delta=f"S&P 500: {p_res.get('spy_cagr', 0.0):+.1f}%"
                )
            with pm3:
                st.metric(
                    label="🛡️ 최대 낙폭 (MDD)",
                    value=f"-{p_res.get('mdd', 0.0):.1f}%",
                    delta=f"코스피: -{p_res.get('ks_mdd', 0.0):.1f}%",
                    delta_color="inverse"
                )
            with pm4:
                st.metric(
                    label="⚖️ 샤프 지수 (위험대비)",
                    value=f"{p_res.get('sharpe', 0.0):.2f}",
                    delta=f"연 변동성 {p_res.get('annual_vol', 0.0):.1f}%"
                )
            with pm5:
                st.metric(
                    label="💵 누적 추정 배당수익",
                    value=f"{int(p_res.get('est_total_dividend_paid', 0)):,}원",
                    delta=f"연 배당률 {p_res.get('weighted_div_yield', 0.0):.2f}%"
                )

            chart_df = p_res.get('hist_chart_df')
            if chart_df is not None and isinstance(chart_df, pd.DataFrame) and not chart_df.empty:
                st.markdown("#### 📈 자산 성장 곡선 (Equity Curve vs S&P500 vs 코스피)")
                fig_p = go.Figure()
                if '내 포트폴리오' in chart_df.columns:
                    fig_p.add_trace(go.Scatter(x=chart_df.index, y=chart_df['내 포트폴리오'], mode='lines', name='내 포트폴리오', line=dict(color='#2563EB', width=2.5)))
                if 'S&P 500 (SPY)' in chart_df.columns:
                    fig_p.add_trace(go.Scatter(x=chart_df.index, y=chart_df['S&P 500 (SPY)'], mode='lines', name='S&P 500 (SPY)', line=dict(color='#10B981', width=1.5, dash='dash')))
                if '코스피 (KOSPI)' in chart_df.columns:
                    fig_p.add_trace(go.Scatter(x=chart_df.index, y=chart_df['코스피 (KOSPI)'], mode='lines', name='코스피 (KOSPI)', line=dict(color='#F59E0B', width=1.5, dash='dot')))
                if '투자 원금' in chart_df.columns:
                    fig_p.add_trace(go.Scatter(x=chart_df.index, y=chart_df['투자 원금'], mode='lines', name='투자 원금선', line=dict(color='#9CA3AF', width=1.2, dash='dash')))
                fig_p.update_layout(
                    height=420,
                    yaxis_title="자산 평가액 (원)",
                    margin=dict(t=20, b=20, l=20, r=20),
                    template="plotly_white",
                    legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
                )
                st.plotly_chart(fig_p, use_container_width=True)

            yearly_records = p_res.get('yearly_records', [])
            if yearly_records:
                st.markdown("#### 📅 연도별 성과 비교 성적표")
                st.dataframe(pd.DataFrame(yearly_records), use_container_width=True, hide_index=True)
        else:
            st.info("💡 포트폴리오 백테스트 데이터를 불러오는 중이거나 데이터가 없습니다. 상단의 '🚀 포트폴리오 백테스트 실행' 버튼을 눌러주세요.")

    # --------------------------------------------------------------------------
    # 서브탭 2: 미래 10년 정기 적립 & 배당 재투자 복리 시뮬레이터
    # --------------------------------------------------------------------------
    with sub_bt2:
        st.markdown("#### 🌱 미래 10년 부(Wealth)의 복리 적립 & 월 배당 파이프라인 시뮬레이터")
        st.caption("초기 자산과 매월 추가 적립금, 연평균 자본 수익률 및 배당금 재투자가 맞물렸을 때, 10년 뒤 내 총자산과 '은퇴를 앞당기는 월 배당 현금흐름'이 얼마나 커지는지 정밀 시뮬레이션합니다.")

        f_c1, f_c2, f_c3, f_c4 = st.columns(4)
        with f_c1:
            fut_init_cap = st.number_input("초기 투자 자본 (원)", min_value=1000000, max_value=2000000000, value=default_init_capital, step=1000000, key="fut_init_cap")
        with f_c2:
            fut_monthly_save = st.number_input("매월 정기 적립금 (원)", min_value=0, max_value=20000000, value=1000000, step=100000, key="fut_monthly_save")
        with f_c3:
            fut_cagr_est = st.slider("연 기대 자본수익률 (%)", min_value=1.0, max_value=25.0, value=10.5, step=0.5, key="fut_cagr_est")
        with f_c4:
            fut_div_est = st.slider("연 예상 배당수익률 (%)", min_value=0.0, max_value=12.0, value=3.2, step=0.1, key="fut_div_est")

        f_sub1, f_sub2 = st.columns([1.5, 2.5])
        with f_sub1:
            fut_years_cnt = st.select_slider("시뮬레이션 목표 기간 (년)", options=[3, 5, 7, 10, 15, 20, 25, 30], value=10, key="fut_years_cnt")
        with f_sub2:
            fut_reinvest_opt = st.checkbox("🔄 수령 배당금 전액 자동 재투자 (복리 스노우볼 극대화)", value=True, key="fut_reinvest_opt")

        fut_calc_btn = st.button("🌱 미래 복리 자산 시뮬레이션 계산", type="primary", use_container_width=True, key="fut_calc_btn")

        cached_fut = st.session_state.get('fut_proj_cache')
        is_fut_valid = (
            cached_fut is not None
            and isinstance(cached_fut, dict)
            and 'proj_df' in cached_fut
            and 'yearly_summary' in cached_fut
            and 'final_wealth' in cached_fut
        )

        if fut_calc_btn or not is_fut_valid:
            st.session_state['fut_proj_cache'] = run_future_wealth_projection(
                initial_capital=fut_init_cap,
                monthly_contribution=fut_monthly_save,
                annual_growth_rate=fut_cagr_est,
                annual_dividend_yield=fut_div_est,
                years=fut_years_cnt,
                reinvest_dividend=fut_reinvest_opt
            )

        f_res = st.session_state.get('fut_proj_cache')

        if f_res and isinstance(f_res, dict):
            final_w = f_res.get('final_wealth', 0)
            tot_p = f_res.get('total_principal', 1)
            tot_prof = f_res.get('total_profit', 0)
            st.markdown(f"### 🎯 {fut_years_cnt}년 후 미래 자산 & 월 배당금 달성 예측")
            fm1, fm2, fm3, fm4 = st.columns(4)
            with fm1:
                st.metric(
                    label=f"🏁 {fut_years_cnt}년 후 총 예상 자산",
                    value=f"{int(final_w):,}원",
                    delta=f"수익률 {(tot_prof / tot_p * 100) if tot_p > 0 else 0:+.1f}%"
                )
            with fm2:
                st.metric(
                    label=f"💵 {fut_years_cnt}년 후 월 예상 배당금",
                    value=f"월 {int(f_res.get('final_monthly_dividend', 0)):,}원",
                    delta=f"연간 {int(f_res.get('final_annual_dividend', 0)):,}원 수령"
                )
            with fm3:
                st.metric(
                    label="🏦 총 납입 원금 (저축)",
                    value=f"{int(tot_p):,}원",
                    delta="순수 투입 원금"
                )
            with fm4:
                st.metric(
                    label="📈 순수 복리 수익 (이자+배당)",
                    value=f"+{int(tot_prof):,}원",
                    delta=f"총 배당수령: {int(f_res.get('total_dividend_earned', 0)):,}원"
                )

            p_df = f_res.get('proj_df')
            if p_df is not None and isinstance(p_df, pd.DataFrame) and not p_df.empty:
                st.markdown("#### 📊 복리 스노우볼 자산 성장 궤적 (원금 vs 복리 수익)")
                fig_proj = go.Figure()
                fig_proj.add_trace(go.Scatter(
                    x=p_df['date'], y=p_df['wealth'], mode='lines', name='기말 총 자산',
                    line=dict(color='#10B981', width=3), fill='tonexty'
                ))
                fig_proj.add_trace(go.Scatter(
                    x=p_df['date'], y=p_df['principal'], mode='lines', name='누적 납입 원금',
                    line=dict(color='#64748B', width=2), fill='tozeroy', fillcolor='rgba(100, 116, 139, 0.15)'
                ))
                fig_proj.update_layout(
                    height=400,
                    yaxis_title="자산 가치 (원)",
                    margin=dict(t=20, b=20, l=20, r=20),
                    template="plotly_white",
                    legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
                )
                st.plotly_chart(fig_proj, use_container_width=True)

            # 재정적 자유 마일스톤 달성 타임라인
            st.markdown("#### 🏆 경제적 자유(FIRE) 마일스톤 달성 타임라인")
            ms = f_res['milestones']
            m_col1, m_col2 = st.columns(2)
            with m_col1:
                st.markdown("**💵 월 배당금 파이프라인 달성 시점**")
                st.write(f"- ☕ **월 50만 원 달성**: `{ms.get('월 배당 50만 원 달성', '기간 내 달성 불가')}`")
                st.write(f"- 🛒 **월 100만 원 달성**: `{ms.get('월 배당 100만 원 달성', '기간 내 달성 불가')}`")
                st.write(f"- 🏠 **월 200만 원 달성**: `{ms.get('월 배당 200만 원 달성', '기간 내 달성 불가')}`")
                st.write(f"- 🚀 **월 300만 원 달성**: `{ms.get('월 배당 300만 원 달성', '기간 내 달성 불가')}`")
                st.write(f"- 👑 **월 500만 원 달성**: `{ms.get('월 배당 500만 원 달성', '기간 내 달성 불가')}`")
            with m_col2:
                st.markdown("**🏦 총 자산 규모 달성 시점**")
                st.write(f"- 🥉 **총 자산 1억 원 돌파**: `{ms.get('총 자산 1억 원 달성', '기간 내 달성 불가')}`")
                st.write(f"- 🥈 **총 자산 3억 원 돌파**: `{ms.get('총 자산 3억 원 달성', '기간 내 달성 불가')}`")
                st.write(f"- 🥇 **총 자산 5억 원 돌파**: `{ms.get('총 자산 5억 원 달성', '기간 내 달성 불가')}`")
                st.write(f"- 💎 **총 자산 10억 원 돌파**: `{ms.get('총 자산 10억 원 달성', '기간 내 달성 불가')}`")

            st.markdown("#### 📅 1년 단위 상세 적립 & 복리 성장 성적표")
            st.dataframe(pd.DataFrame(f_res['yearly_summary']), use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # 서브탭 3: 개별 종목 SEPA & VCP 기술적 백테스트
    # --------------------------------------------------------------------------
    with sub_bt3:
        st.markdown("#### 🔍 개별 종목 마크 미너비니 SEPA & VCP 백테스팅")
        st.caption("과거 실제 시세 데이터를 바탕으로 **안전 버퍼 손절매(-7%) & 피벗 초입 돌파(+0~2.5%) & 20일선 거래량 마른 눌림목 지지 매수** 전략의 실제 수익률을 정밀 검증합니다.")

        bt_col1, bt_col2, bt_col3, bt_col4 = st.columns(4)
        with bt_col1:
            bt_ticker = st.selectbox(
                "백테스트 종목 선택",
                options=["000660", "NVDA", "CRWD", "MSFT", "AAPL", "005930", "직접입력"],
                index=0,
                key="bt_single_ticker"
            )
            if bt_ticker == "직접입력":
                bt_ticker = st.text_input("직접 티커 입력", value="GOOGL", key="bt_single_custom").strip().upper()

        with bt_col2:
            bt_period = st.selectbox("백테스트 기간", ["1y", "2y", "3y", "5y", "10y"], index=2, key="bt_single_period")

        with bt_col3:
            bt_stop_loss = st.selectbox("손절매 기준 (Stop-Loss)", [-0.05, -0.06, -0.07, -0.08, -0.10], index=2, format_func=lambda x: f"{x*100:.0f}%", key="bt_single_sl")

        with bt_col4:
            bt_capital_bt = st.number_input("시뮬레이션 초기 자산 (원)", min_value=1000000, max_value=1000000000, value=10000000, step=1000000, key="bt_single_cap")

        bt_run_btn = st.button("🚀 종목 백테스트 실행하기", type="primary", use_container_width=True, key="bt_single_run")

        cached_res = st.session_state.get('bt_result')
        is_cache_valid = (
            cached_res is not None
            and isinstance(cached_res, dict)
            and 'equity_df' in cached_res
            and 'drawdown_series' in cached_res
            and 'cagr' in cached_res
            and cached_res.get('ticker') == bt_ticker
            and cached_res.get('period') == bt_period
        )

        if bt_run_btn or not is_cache_valid:
            with st.spinner(f"⏳ {bt_ticker} ({bt_period}) 정밀 SEPA 백테스트 시뮬레이션 계산 중..."):
                new_res = run_single_stock_backtest(
                    ticker=bt_ticker,
                    period=bt_period,
                    initial_capital=bt_capital_bt,
                    stop_loss_pct=abs(bt_stop_loss)
                )
                if new_res is not None:
                    st.session_state['bt_result'] = new_res
                else:
                    st.session_state.pop('bt_result', None)

        bt_res = st.session_state.get('bt_result')

        if bt_res and isinstance(bt_res, dict):
            st.markdown(f"### 🏆 백테스트 성과 분석 성적표: **{bt_res.get('stock_name', bt_ticker)} ({bt_res.get('ticker', bt_ticker)})** [기간: {bt_res.get('period', bt_period)}]")
            
            m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
            with m_col1:
                st.metric(
                    label="💰 전략 총 수익률",
                    value=f"{bt_res.get('total_return_pct', 0.0):+.1f}%",
                    delta=f"단순보유: {bt_res.get('buyhold_return_pct', 0.0):+.1f}%"
                )
            with m_col2:
                st.metric(
                    label="📈 연평균 복리(CAGR)",
                    value=f"{bt_res.get('cagr', 0.0):+.1f}%"
                )
            with m_col3:
                st.metric(
                    label="🛡️ 최대 낙폭 (MDD)",
                    value=f"-{bt_res.get('mdd', 0.0):.1f}%",
                    delta="리스크 방어력",
                    delta_color="inverse"
                )
            with m_col4:
                st.metric(
                    label="🎯 승률 (Win Rate)",
                    value=f"{bt_res.get('win_rate', 0.0):.1f}%",
                    delta=f"총 {bt_res.get('total_trades', 0)}회 매매"
                )
            with m_col5:
                st.metric(
                    label="⚖️ 손익비 (Payoff Ratio)",
                    value=f"{bt_res.get('payoff_ratio', 1.0):.2f} : 1"
                )

            eq_df = bt_res.get('equity_df')
            if eq_df is not None and isinstance(eq_df, pd.DataFrame) and not eq_df.empty:
                st.markdown("### 📈 누적 자산 가치 곡선 (Equity Curve vs 단순보유)")
                fig_eq = go.Figure()
                if 'Strategy' in eq_df.columns:
                    fig_eq.add_trace(go.Scatter(
                        x=eq_df.index,
                        y=eq_df['Strategy'],
                        mode='lines',
                        name='JTI 퀀트 전략 자산',
                        line=dict(color='#2563EB', width=2.5)
                    ))
                if 'BuyHold' in eq_df.columns:
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

            dd_series = bt_res.get('drawdown_series')
            if dd_series is not None and hasattr(dd_series, 'empty') and not dd_series.empty:
                st.markdown("### 🛡️ 계좌 낙폭 (Drawdown) 추이")
                fig_dd = go.Figure()
                fig_dd.add_trace(go.Scatter(
                    x=dd_series.index if hasattr(dd_series, 'index') else (eq_df.index if eq_df is not None else None),
                    y=dd_series,
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
        else:
            st.info("💡 과거 시세를 불러오는 중이거나 데이터가 없습니다. 상단의 '🚀 종목 백테스트 실행하기' 버튼을 눌러주세요.")


# ==============================================================================
# 탭 5: [AI 전담 PB] 1:1 주식 자문 & 자산 증식 상담소
# ==============================================================================
with tab_ai_advisor:
    # 1. 포트폴리오 데이터 핫 리로드 (최신 코드 및 데이터 즉시 동기화)
    import importlib
    import portfolio_manager
    importlib.reload(portfolio_manager)
    import ai_advisor
    importlib.reload(ai_advisor)
    
    raw_p_data = portfolio_manager.load_portfolio_data()
    my_analysis = portfolio_manager.analyze_my_portfolio(raw_p_data)
    
    # 거시 시장 지표 캐싱 수집 (VIX 및 4대 지수 이평선)
    macro_summary = {}
    try:
        macro_data = fetch_macro_data()
        m_score, m_status, vix_val, d_logs, idx_sum = evaluate_macro(macro_data)
        macro_summary = {
            'market_score': m_score,
            'market_status': m_status,
            'vix': vix_val,
            'vix_change': macro_data.get('vix_change', 0.0),
            'vix_change_pct': macro_data.get('vix_change_pct', 0.0),
            'indices_summary': idx_sum
        }
    except Exception:
        pass

    # AI 주식 자문 전용 포트폴리오 텍스트 컨텍스트 생성
    portfolio_ctx = build_portfolio_context(raw_p_data, my_analysis, macro_summary)

    # 세션 상태 초기화 (로컬 영구 설정 파일 자동 로드)
    saved_ai_cfg = load_ai_config()
    if "gemini_chat_history" not in st.session_state:
        st.session_state["gemini_chat_history"] = []
    if "gemini_api_key" not in st.session_state:
        st.session_state["gemini_api_key"] = saved_ai_cfg.get("gemini_api_key", "")
    if "gemini_model" not in st.session_state:
        st.session_state["gemini_model"] = saved_ai_cfg.get("gemini_model", "gemini-2.0-flash")
    if "pending_ai_prompt" not in st.session_state:
        st.session_state["pending_ai_prompt"] = None

    # 헤더
    st.markdown("### 💬 월가 수석 PB & 마크 미너비니 퀀트 자문관")
    st.markdown(
        "대표님의 **실시간 5대 계좌(자산 3,800여만 원, 순투입 4,030만 원)**, **보유 20여 개 종목**, "
        "계좌별 예수금, 그리고 **실시간 거시 시장 지표(VIX/4대 지수 정배열)**를 100% 숙지한 최정예 1:1 전담 AI 금융 PB입니다."
    )

    # --------------------------------------------------------------------------
    # 🌟 수석 PB 실시간 포트폴리오 브리핑 카드
    # --------------------------------------------------------------------------
    total_worth = my_analysis.get('total_net_worth', 0.0)
    cost_basis = my_analysis.get('total_cost_basis', 0.0)
    pnl_val = my_analysis.get('total_pnl_krw', 0.0)
    ret_pct = my_analysis.get('total_return_pct', 0.0)
    total_cash_val = my_analysis.get('total_cash', 0.0)
    vix_val_disp = macro_summary.get('vix', 19.5)
    vix_status_disp = macro_summary.get('market_status', '중립')

    pb1, pb2, pb3, pb4, pb5 = st.columns(5)
    with pb1:
        st.metric("💼 총 평가 자산", f"{total_worth:,.0f}원")
    with pb2:
        st.metric("🎯 순투입원금 (진짜 원금)", f"{cost_basis:,.0f}원")
    with pb3:
        st.metric("📈 누적 평가 손익", f"{pnl_val:+,.0f}원", delta=f"{ret_pct:+.2f}%")
    with pb4:
        st.metric("💵 가용 총 예수금", f"{total_cash_val:,.0f}원")
    with pb5:
        st.metric("🌐 시장 VIX / 상태", f"{vix_val_disp:.2f}", delta=vix_status_disp)

    st.markdown("---")

    # --------------------------------------------------------------------------
    # ⚙️ Google Gemini API 설정 및 모델 선택 (접이식)
    # --------------------------------------------------------------------------
    has_api_key = bool(st.session_state["gemini_api_key"].strip())
    exp_label = (
        "🟢 [고급 LLM 모드] Google Gemini AI 실시간 연동 활성화 (클릭하여 키 관리/변경)"
        if has_api_key else
        "🏛️ [기본 퀀트 모드] 월가 수석 PB & 미너비니 자체 퀀트 엔진 가동 중 (무료/API 불필요, 클릭하여 Gemini 키 등록 가능)"
    )
    
    with st.expander(exp_label, expanded=False):
        st.markdown(
            "💡 **자체 퀀트 PB 엔진 안내**: **API 키가 없어도** 대표님의 실시간 5대 계좌 자산, 종목별 손익, 가용 예수금 데이터를 바탕으로 "
            "**월가 수석 PB & 마크 미너비니 퀀트 엔진**이 100% 정상 작동합니다. Google Gemini 최신 모델과의 자유 대화를 원하실 때만 선택적으로 키를 등록하십시오."
        )
        cfg_col1, cfg_col2 = st.columns([3, 2])
        with cfg_col1:
            entered_key = st.text_input(
                "Gemini API Key (선택 사항)",
                value=st.session_state["gemini_api_key"],
                type="password",
                help="Google AI Studio에서 무료로 발급받은 API 키를 입력하세요. '영구 저장' 버튼을 누르면 평생 유지됩니다.",
                key="input_gemini_api_key"
            )
        with cfg_col2:
            current_model = st.selectbox(
                "Gemini 최신 모델 선택",
                GEMINI_MODELS,
                index=GEMINI_MODELS.index(st.session_state["gemini_model"]) if st.session_state["gemini_model"] in GEMINI_MODELS else 0,
                help="개인 무료 티어 기준 가장 우수한 최신 모델들을 우선적으로 지원합니다.",
                key="select_gemini_model"
            )

        btn_save_col, btn_del_col = st.columns(2)
        with btn_save_col:
            if st.button("💾 API 키 로컬 영구 저장", use_container_width=True):
                st.session_state["gemini_api_key"] = entered_key.strip()
                st.session_state["gemini_model"] = current_model
                save_ai_config(entered_key.strip(), current_model)
                st.success("🎉 API 키가 로컬 파일에 영구 저장되었습니다! 브라우저를 새로고침하거나 껐다 켜도 계속 유지됩니다.")
                st.rerun()
        with btn_del_col:
            if st.button("🗑️ API 키 삭제 (자체 엔진 모드로 복귀)", use_container_width=True):
                st.session_state["gemini_api_key"] = ""
                save_ai_config("", current_model)
                st.info("API 키가 삭제되었습니다. 월가 수석 PB 자체 내장 엔진 모드로 즉시 복귀합니다.")
                st.rerun()

        st.markdown(
            """
            ---
            *🔑 무료 API 키가 필요하신 경우: [Google AI Studio (aistudio.google.com)](https://aistudio.google.com/app/apikey)에서 무료 발급받아 등록하실 수 있습니다.*
            """
        )

    # --------------------------------------------------------------------------
    # ⚡ 모바일 원터치 빠른 자문 프리셋 버튼
    # --------------------------------------------------------------------------
    st.markdown("##### ⚡ 원터치 빠른 자문 (아래 카드를 터치하시면 즉시 분석합니다)")
    
    # 1행: 3개 버튼
    r1_c1, r1_c2, r1_c3 = st.columns(3)
    with r1_c1:
        if st.button(f"{QUICK_PROMPTS[0]['icon']} {QUICK_PROMPTS[0]['title']}", use_container_width=True):
            st.session_state["pending_ai_prompt"] = QUICK_PROMPTS[0]["prompt"]
            st.rerun()
    with r1_c2:
        if st.button(f"{QUICK_PROMPTS[1]['icon']} {QUICK_PROMPTS[1]['title']}", use_container_width=True):
            st.session_state["pending_ai_prompt"] = QUICK_PROMPTS[1]["prompt"]
            st.rerun()
    with r1_c3:
        if st.button(f"{QUICK_PROMPTS[2]['icon']} {QUICK_PROMPTS[2]['title']}", use_container_width=True):
            st.session_state["pending_ai_prompt"] = QUICK_PROMPTS[2]["prompt"]
            st.rerun()

    # 2행: 2개 버튼 + 대화 초기화 버튼
    r2_c1, r2_c2, r2_c3 = st.columns([1, 1, 1])
    with r2_c1:
        if st.button(f"{QUICK_PROMPTS[3]['icon']} {QUICK_PROMPTS[3]['title']}", use_container_width=True):
            st.session_state["pending_ai_prompt"] = QUICK_PROMPTS[3]["prompt"]
            st.rerun()
    with r2_c2:
        if st.button(f"{QUICK_PROMPTS[4]['icon']} {QUICK_PROMPTS[4]['title']}", use_container_width=True):
            st.session_state["pending_ai_prompt"] = QUICK_PROMPTS[4]["prompt"]
            st.rerun()
    with r2_c3:
        if st.button("🗑️ 대화 내역 초기화", use_container_width=True):
            st.session_state["gemini_chat_history"] = []
            st.session_state["pending_ai_prompt"] = None
            st.rerun()

    st.markdown("---")

    # --------------------------------------------------------------------------
    # 💬 대화창 (Chat Messages)
    # --------------------------------------------------------------------------
    chat_container = st.container()
    with chat_container:
        if not st.session_state["gemini_chat_history"]:
            with st.chat_message("assistant", avatar="💼"):
                st.markdown(
                    f"""
                    **반갑습니다, 대표님! 대표님의 5대 계좌를 전담 관리하는 수석 AI 자산관리 PB입니다.**
                    
                    현재 대표님의 실시간 5대 계좌(순투입 **{cost_basis:,.0f}원**, 총자산 **{total_worth:,.0f}원**), **20여 개 보유 종목**, 계좌별 예수금, 그리고 실시간 거시지표(VIX: **{vix_val_disp:.2f}**)를 100% 실시간으로 숙지하고 있습니다.
                    
                    - 🩺 상단의 **'원터치 빠른 자문'** 버튼을 터치하시거나,
                    - 💬 하단 대화창에 *"이번 달 ISA에서 무엇을 살까?"*, *"-7% 손절해야 할 위험 종목은?"*, *"10년 뒤 월 200만 원 배당 플랜은?"* 등 자유롭게 질문해 주세요.
                    """
                )
        else:
            for msg in st.session_state["gemini_chat_history"]:
                role = msg.get("role", "user")
                avatar = "💼" if role == "assistant" else "👤"
                with st.chat_message(role, avatar=avatar):
                    st.markdown(msg.get("content", ""))

    # --------------------------------------------------------------------------
    # 📥 사용자 입력 처리 (원터치 버튼 또는 채팅 입력창)
    # --------------------------------------------------------------------------
    user_input = st.chat_input("대표님, 주식 매수/매도, 자산 배분, 복리 플랜 등 무엇이든 질문하세요...")

    active_prompt = None
    if st.session_state["pending_ai_prompt"]:
        active_prompt = st.session_state["pending_ai_prompt"]
        st.session_state["pending_ai_prompt"] = None
    elif user_input:
        active_prompt = user_input

    if active_prompt:
        # 사용자 메시지 추가
        st.session_state["gemini_chat_history"].append({"role": "user", "content": active_prompt})
        
        # 화면에 즉시 표시
        with chat_container:
            with st.chat_message("user", avatar="👤"):
                st.markdown(active_prompt)

            with st.chat_message("assistant", avatar="💼"):
                api_key = st.session_state.get("gemini_api_key", "").strip()
                preferred_model = st.session_state.get("gemini_model", "gemini-2.0-flash")
                
                stream_gen = stream_gemini_advisor(
                    api_key=api_key,
                    user_prompt=active_prompt,
                    conversation_history=st.session_state["gemini_chat_history"][:-1],
                    portfolio_context=portfolio_ctx,
                    preferred_model=preferred_model,
                    analysis=my_analysis,
                    macro_summary=macro_summary
                )
                ai_reply = st.write_stream(stream_gen)
                st.session_state["gemini_chat_history"].append({"role": "assistant", "content": ai_reply})
        
        st.rerun()

    # --------------------------------------------------------------------------
    # 📱 스마트폰(모바일) 연동 가이드
    # --------------------------------------------------------------------------
    st.markdown("---")
    with st.expander("📱 스마트폰(모바일)에서 이 대시보드 및 AI PB 바로 연동하는 방법", expanded=False):
        st.markdown(
            f"""
            ### 📲 스마트폰 홈 화면에 'AI PB 앱'으로 등록하는 방법 (1분 소요)
            
            1. **동일 Wi-Fi 연결**:
               - PC와 스마트폰을 같은 집/사무실 Wi-Fi에 연결합니다.
               
            2. **스마트폰 브라우저에서 바로 접속**:
               - 스마트폰 사파리(아이폰) 또는 크롬(갤럭시)을 엽니다.
               - 주소창에 아래 주소를 그대로 입력합니다:
               - 👉 **`http://{_lan_ip}:8501`**
               
            3. **홈 화면에 추가 (원터치 앱 만들기)**:
               - **아이폰 (Safari)**: 하단 공유 버튼(`공유` 아이콘) -> **[홈 화면에 추가]**
               - **안드로이드 (Chrome)**: 우측 상단 메뉴(`⋮`) -> **[홈 화면에 추가]**
               - 이제 스마트폰 바탕화면에 앱 아이콘이 생겨 언제든 터치 한 번으로 1:1 PB 상담을 받으실 수 있습니다!
               
            4. **만약 핸드폰에서 접속 에러가 날 때 해결법**:
               - 프로젝트 폴더의 **`방화벽_8501_허용.bat`** 파일을 마우스 우클릭 -> **[관리자 권한으로 실행]**해 주세요.
               - 윈도우 방화벽에서 스마트폰 접속을 허용해 줍니다.
            """
        )

