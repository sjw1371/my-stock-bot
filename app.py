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
from backtest import run_single_stock_backtest
from portfolio_manager import (
    load_portfolio_data,
    save_portfolio_data,
    analyze_my_portfolio,
    parse_pasted_csv_text,
    fetch_live_exchange_rate,
    save_target_allocation,
    DEFAULT_ACCOUNT_TARGETS,
    DEFAULT_CATEGORY_TARGETS,
    classify_asset_category
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

tab_my_account, tab_allocator, tab_scanner, tab_backtest = st.tabs([
    "💼 [내 계좌] 실시간 종합 관리 & AI 맞춤 진단",
    "🧭 [자산 배분] Dual-Lens 포트폴리오 빌더 & What-If",
    "📡 [시장 스캐너] SEPA 트렌드 & 정밀 VCP",
    "📊 [백테스팅] 10년 과거 검증 시뮬레이터"
])


# ==============================================================================
# 탭 1: [내 계좌] 실시간 종합 관리 & AI 맞춤 진단
# ==============================================================================
with tab_my_account:
    # 1. 포트폴리오 데이터 로드 및 실시간 분석
    raw_p_data = load_portfolio_data()
    my_analysis = analyze_my_portfolio(raw_p_data)

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
    st.markdown("**[장기 적립 계좌 (연금/ISA)]**는 200일선 우상향 시 지속 적립 및 배당 재투자를 권고하며, **[단기 퀀트 스윙 계좌 (해외/일반)]**는 마크 미너비니 원칙에 따라 -7% 칼손절 및 홀딩 처방을 내립니다. (해외 주식은 **당일 실시간 환율** 자동 적용)")

    all_h_df = my_analysis['all_holdings_df']
    if not all_h_df.empty:
        disp_df = all_h_df[[
            '계좌', '계좌유형', '종목명', '수량', '매수단가', '현재가', '수익률(%)', '평가금액(원)', '배당수익률(%)', '연간예상배당(원)', '진단상태', '처방내용', '통화'
        ]].copy()

        disp_df['수량'] = disp_df['수량'].apply(lambda x: f"{x:.8f}".rstrip('0').rstrip('.') if x < 1 else (f"{x:.2f}".rstrip('0').rstrip('.') if isinstance(x, float) and not x.is_integer() else f"{int(x)}"))
        disp_df['매수단가'] = disp_df.apply(lambda r: f"${r['매수단가']:.2f}" if r['통화'] == "USD" else f"{int(r['매수단가']):,}원", axis=1)
        disp_df['현재가'] = disp_df.apply(lambda r: f"${r['현재가']:.2f} (약 {int(r['현재가'] * my_analysis['exchange_rate']):,}원)" if r['통화'] == "USD" else f"{int(r['현재가']):,}원", axis=1)
        disp_df['수익률(%)'] = disp_df['수익률(%)'].apply(lambda x: f"{x:+.1f}%")
        disp_df['평가금액'] = disp_df['평가금액(원)'].apply(lambda x: f"{int(x):,}원")
        disp_df['배당률'] = disp_df['배당수익률(%)'].apply(lambda x: f"{x:.2f}%" if x > 0 else "-")
        disp_df['연간배당금'] = disp_df['연간예상배당(원)'].apply(lambda x: f"{int(x):,}원" if x > 0 else "-")

        st.dataframe(
            disp_df[['계좌', '종목명', '수량', '매수단가', '현재가', '수익률(%)', '평가금액', '배당률', '연간배당금', '진단상태', '처방내용']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "계좌": st.column_config.TextColumn("계좌", width="small"),
                "종목명": st.column_config.TextColumn("종목명", width="medium"),
                "수량": st.column_config.TextColumn("수량", width="small"),
                "매수단가": st.column_config.TextColumn("매수단가", width="small"),
                "현재가": st.column_config.TextColumn("현재가 (실시간 환율)", width="medium"),
                "수익률(%)": st.column_config.TextColumn("수익률", width="small"),
                "평가금액": st.column_config.TextColumn("평가금액", width="medium"),
                "배당률": st.column_config.TextColumn("배당률", width="small"),
                "연간배당금": st.column_config.TextColumn("예상 연배당금", width="small"),
                "진단상태": st.column_config.TextColumn("AI 진단", width="medium"),
                "처방내용": st.column_config.TextColumn("처방 및 행동 지침", width="large")
            }
        )

    st.markdown("---")

    # --------------------------------------------------------------------------
    # ⚖️ 4. 내 잔고 기반 오늘의 맞춤형 리밸런싱 & 매수 주문표
    # --------------------------------------------------------------------------
    st.subheader("⚖️ 내 잔고 기반 오늘의 맞춤형 리밸런싱 & 주문표")
    st.markdown("내 실제 계좌별 가용 현금과 종목별 목표 비중을 고려하여 **오늘 증권사 앱에서 바로 실행해야 할 추천 주문**입니다.")

    order_df = my_analysis['order_suggestions']
    if not order_df.empty:
        st.dataframe(
            order_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "계좌": st.column_config.TextColumn("계좌", width="small"),
                "구분": st.column_config.TextColumn("구분", width="medium"),
                "종목명": st.column_config.TextColumn("종목명", width="medium"),
                "현재가": st.column_config.TextColumn("현재가", width="small"),
                "추천주문": st.column_config.TextColumn("실행 주문", width="medium"),
                "주문금액": st.column_config.TextColumn("주문 금액", width="small"),
                "이유": st.column_config.TextColumn("주문 사유", width="large")
            }
        )
    else:
        st.success("✅ 현재 모든 계좌의 비중이 이상적이며, 손절선에 도달한 리스크 종목이 없습니다. 현 상태를 유지하십시오.")

    st.markdown("---")

    # --------------------------------------------------------------------------
    # ⚙️ 5. 데이터 갱신 및 원금 히스토리 관리 도구
    # --------------------------------------------------------------------------
    with st.expander("⚙️ 내 계좌 데이터 및 투자 원금 히스토리 관리 (엑셀 복붙 / 종목 편집 / 원금 스냅샷)", expanded=False):
        sync_col1, sync_col2, sync_col3 = st.tabs([
            "📋 [방법 A] 엑셀/CSV 붙여넣기",
            "✏️ [방법 B] 계좌별 종목/현금/배당 편집",
            "📅 [방법 C] 일자별 투자 원금 스냅샷 관리"
        ])

        with sync_col1:
            st.markdown("엑셀에서 관리하던 표 내용을 복사하여 아래에 붙여넣고 **[1초 만에 갱신하기]** 버튼을 누르시면 5대 계좌가 즉시 최신 상태로 업데이트됩니다.")
            pasted_text = st.text_area("엑셀/CSV 데이터 붙여넣기", height=150, placeholder="계좌구분,종목명,종목코드,현재가,수량...\n연금저축펀드,TIGER 미국S&P500,360750,25780,120...")
            if st.button("🚀 1초 만에 갱신하기", type="primary"):
                if pasted_text.strip():
                    parse_pasted_csv_text(pasted_text)
                    st.success("🎉 5대 계좌 데이터가 성공적으로 갱신되었습니다! 페이지를 새로고침합니다.")
                    st.rerun()
                else:
                    st.warning("붙여넣은 텍스트가 없습니다.")

        with sync_col2:
            st.markdown("핸드폰이나 컴퓨터에서 계좌별 현금 잔고와 보유 종목, **배당수익률(%)**을 직접 수정하고 영구 저장할 수 있습니다.")
            edit_acc = st.selectbox("수정할 계좌 선택", list(raw_p_data.get("accounts", {}).keys()))
            if edit_acc:
                target_acc_info = raw_p_data["accounts"][edit_acc]
                e_c1, e_c2 = st.columns(2)
                with e_c1:
                    new_cash_krw = st.number_input(f"{edit_acc} 원화 현금 (KRW)", value=int(target_acc_info.get("cash_krw", 0)), step=10000)
                with e_c2:
                    new_cash_usd = st.number_input(f"{edit_acc} 달러 현금 (USD)", value=float(target_acc_info.get("cash_usd", 0.0)), step=10.0)

                st.markdown("**보유 종목 목록 편집 (수량, 매수단가, 배당수익률, 목표비중)**")
                holdings_list = target_acc_info.get("holdings", [])
                h_df = pd.DataFrame(holdings_list)
                if not h_df.empty:
                    if 'dividend_yield' not in h_df.columns:
                        h_df['dividend_yield'] = 0.0
                    if 'target_weight' not in h_df.columns:
                        h_df['target_weight'] = 0.10
                else:
                    h_df = pd.DataFrame(columns=["ticker", "name", "shares", "avg_price", "dividend_yield", "target_weight"])

                edited_h_df = st.data_editor(
                    h_df,
                    num_rows="dynamic",
                    use_container_width=True,
                    column_config={
                        "ticker": st.column_config.TextColumn("티커 (종목코드)", width="small", required=True),
                        "name": st.column_config.TextColumn("종목명", width="medium", required=True),
                        "shares": st.column_config.NumberColumn("보유수량", width="small", required=True, min_value=0.0),
                        "avg_price": st.column_config.NumberColumn("매수단가 (KRW/USD)", width="small", required=True, min_value=0.0),
                        "dividend_yield": st.column_config.NumberColumn("배당수익률 (%)", width="small", min_value=0.0, max_value=100.0, step=0.1, format="%.2f%%", help="연간 예상 배당수익률 (예: 3.8은 3.8%)"),
                        "target_weight": st.column_config.NumberColumn("목표비중 (0~1)", width="small", min_value=0.0, max_value=1.0, step=0.05, format="%.2f", help="계좌 내 목표 비중 (예: 0.2는 20%)")
                    }
                )

                if st.button(f"💾 {edit_acc} 수정 내용 영구 저장하기", type="primary"):
                    target_acc_info["cash_krw"] = new_cash_krw
                    target_acc_info["cash_usd"] = new_cash_usd
                    target_acc_info["holdings"] = edited_h_df.to_dict(orient="records")
                    raw_p_data["accounts"][edit_acc] = target_acc_info
                    save_portfolio_data(raw_p_data)
                    st.success(f"🎉 {edit_acc} 데이터(배당 및 종목 정보)가 영구 저장되었습니다!")
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
# 탭 2: [자산 배분] Dual-Lens 포트폴리오 빌더 & What-If 시뮬레이터
# ==============================================================================
with tab_allocator:
    st.subheader("🧭 Dual-Lens 스마트 자산 배분 & 포트폴리오 빌더")
    st.markdown("내 전체 자산(약 **3,900만 원**)을 **[6대 자산 팩터]**와 **[5대 계좌]**의 듀얼 렌즈로 진단하고, 목표 포트폴리오 비중을 슬라이더로 조절하여 **리밸런싱 매매 금액** 및 **예상 연간 배당금 변화**를 실시간으로 시뮬레이션합니다.")

    # --------------------------------------------------------------------------
    # 🌟 Step 1: AI 3대 투자 전략 프리셋
    # --------------------------------------------------------------------------
    st.markdown("### 🌟 Step 1: AI 3대 투자 전략 프리셋 (원클릭 세팅)")
    
    preset_choice = st.radio(
        "추천 자산 배분 모델을 선택하거나 직접 슬라이더로 커스텀 설정하세요:",
        options=[
            "⚖️ [밸런스 Dual-Track (추천)] (글로벌 코어 35% + 고배당 30% + 테마/혁신 15% + 퀀트스윙 10% + 현금 8% + 코인 2%)",
            "🔥 [공격적 복리 성장형] (글로벌 코어 45% + 테마/혁신 25% + 퀀트스윙 15% + 고배당 5% + 현금 8% + 코인 2%)",
            "🛡️ [배당 인컴 & 방어형] (고배당 50% + 글로벌 코어 25% + 안전현금 15% + 테마/스윙 10%)",
            "🎛️ [사용자 직접 커스텀 조절]"
        ],
        index=0
    )

    preset_map = {
        "⚖️ [밸런스 Dual-Track (추천)] (글로벌 코어 35% + 고배당 30% + 테마/혁신 15% + 퀀트스윙 10% + 현금 8% + 코인 2%)": {
            "🌱 글로벌 코어 지수": 35,
            "💰 고배당 & 인컴": 30,
            "🤖 테마 & 미래혁신": 15,
            "🚀 퀀트 스윙 & 모멘텀": 10,
            "🪙 대체자산 (코인)": 2,
            "💵 안전 현금": 8
        },
        "🔥 [공격적 복리 성장형] (글로벌 코어 45% + 테마/혁신 25% + 퀀트스윙 15% + 고배당 5% + 현금 8% + 코인 2%)": {
            "🌱 글로벌 코어 지수": 45,
            "💰 고배당 & 인컴": 5,
            "🤖 테마 & 미래혁신": 25,
            "🚀 퀀트 스윙 & 모멘텀": 15,
            "🪙 대체자산 (코인)": 2,
            "💵 안전 현금": 8
        },
        "🛡️ [배당 인컴 & 방어형] (고배당 50% + 글로벌 코어 25% + 안전현금 15% + 테마/스윙 10%)": {
            "🌱 글로벌 코어 지수": 25,
            "💰 고배당 & 인컴": 50,
            "🤖 테마 & 미래혁신": 5,
            "🚀 퀀트 스윙 & 모멘텀": 5,
            "🪙 대체자산 (코인)": 0,
            "💵 안전 현금": 15
        }
    }

    current_saved_targets = raw_p_data.get("target_allocation", {}).get("categories", DEFAULT_CATEGORY_TARGETS)
    
    if preset_choice in preset_map:
        selected_weights = preset_map[preset_choice]
    else:
        selected_weights = {k: int(v * 100) if v <= 1.0 else int(v) for k, v in current_saved_targets.items()}

    st.markdown("---")

    # --------------------------------------------------------------------------
    # 🎛️ Step 2: What-If 인터랙티브 슬라이더 & 비포/애프터 비교
    # --------------------------------------------------------------------------
    st.markdown("### 🎛️ Step 2: What-If 인터랙티브 슬라이더 & 비포/애프터 실시간 비교")

    sim_col1, sim_col2 = st.columns([1.1, 1.3])

    with sim_col1:
        st.markdown("**📊 6대 자산 팩터별 목표 비중 설정 (%)**")
        sim_core = st.slider("🌱 글로벌 코어 지수 (%)", 0, 100, selected_weights.get("🌱 글로벌 코어 지수", 35), step=1)
        sim_div = st.slider("💰 고배당 & 인컴 (%)", 0, 100, selected_weights.get("💰 고배당 & 인컴", 30), step=1)
        sim_theme = st.slider("🤖 테마 & 미래혁신 (%)", 0, 100, selected_weights.get("🤖 테마 & 미래혁신", 15), step=1)
        sim_swing = st.slider("🚀 퀀트 스윙 & 모멘텀 (%)", 0, 100, selected_weights.get("🚀 퀀트 스윙 & 모멘텀", 10), step=1)
        sim_coin = st.slider("🪙 대체자산 (코인) (%)", 0, 20, selected_weights.get("🪙 대체자산 (코인)", 2), step=1)
        sim_cash = st.slider("💵 안전 현금 (%)", 0, 50, selected_weights.get("💵 안전 현금", 8), step=1)

        total_sim_weight = sim_core + sim_div + sim_theme + sim_swing + sim_coin + sim_cash
        if total_sim_weight == 100:
            st.success(f"✅ 목표 비중 합계: **{total_sim_weight}%** (정상)")
        else:
            diff = 100 - total_sim_weight
            st.warning(f"⚠️ 목표 비중 합계: **{total_sim_weight}%** (100%가 되도록 {'+' if diff > 0 else ''}{diff}% 조정 필요)")

        if st.button("💾 이 배분 전략을 내 공식 목표로 영구 저장", type="primary"):
            new_cat_targets = {
                "🌱 글로벌 코어 지수": sim_core / 100.0,
                "💰 고배당 & 인컴": sim_div / 100.0,
                "🤖 테마 & 미래혁신": sim_theme / 100.0,
                "🚀 퀀트 스윙 & 모멘텀": sim_swing / 100.0,
                "🪙 대체자산 (코인)": sim_coin / 100.0,
                "💵 안전 현금": sim_cash / 100.0
            }
            save_target_allocation(category_targets=new_cat_targets)
            st.success("🎉 새로운 자산 배분 목표가 영구 저장되었습니다!")
            st.rerun()

    sim_targets_map = {
        "🌱 글로벌 코어 지수": sim_core,
        "💰 고배당 & 인컴": sim_div,
        "🤖 테마 & 미래혁신": sim_theme,
        "🚀 퀀트 스윙 & 모멘텀": sim_swing,
        "🪙 대체자산 (코인)": sim_coin,
        "💵 안전 현금": sim_cash
    }

    total_equity = my_analysis['total_net_worth']
    
    # 예상 배당금 계산 (고배당 평균 4.5%, 코어 1.3%, 테마 0.5%, 기타 0%)
    sim_div_krw = (total_equity * (sim_div / 100.0) * 0.045) + (total_equity * (sim_core / 100.0) * 0.013) + (total_equity * (sim_theme / 100.0) * 0.005)
    current_div_krw = my_analysis['total_annual_dividend_krw']
    div_delta_krw = sim_div_krw - current_div_krw

    with sim_col2:
        d_m1, d_m2, d_m3 = st.columns(3)
        with d_m1:
            st.metric(
                label="💰 시뮬레이션 예상 연배당",
                value=f"연 {int(sim_div_krw):,}원",
                delta=f"{int(div_delta_krw):+,}원 ({'증가' if div_delta_krw >= 0 else '감소'})"
            )
        with d_m2:
            st.metric(
                label="💵 시뮬레이션 월배당",
                value=f"월 {int(sim_div_krw / 12):,}원",
                delta=f"연 배당률 {(sim_div_krw / total_equity * 100):.2f}%"
            )
        with d_m3:
            growth_ratio = sim_core + sim_theme + sim_swing
            income_ratio = sim_div
            st.metric(
                label="⚖️ 성장형 vs 인컴형 비율",
                value=f"{growth_ratio}% : {income_ratio}%",
                delta=f"현금 {sim_cash}%"
            )

        ch_c1, ch_c2 = st.columns(2)
        
        cat_labels = list(my_analysis['categories_data'].keys())
        cat_curr_vals = [my_analysis['categories_data'][k]['eval_krw'] for k in cat_labels]
        fig_curr_cat = go.Figure(data=[go.Pie(
            labels=cat_labels,
            values=cat_curr_vals,
            hole=.45,
            textinfo='percent',
            title='현재 포트폴리오',
            marker=dict(colors=['#3B82F6', '#10B981', '#8B5CF6', '#F59E0B', '#EC4899', '#64748B'])
        )])
        fig_curr_cat.update_layout(height=240, margin=dict(t=20, b=20, l=10, r=10), showlegend=False)

        cat_sim_vals = [sim_targets_map.get(k, 0) for k in cat_labels]
        fig_sim_cat = go.Figure(data=[go.Pie(
            labels=cat_labels,
            values=cat_sim_vals,
            hole=.45,
            textinfo='percent',
            title='시뮬레이션 목표',
            marker=dict(colors=['#3B82F6', '#10B981', '#8B5CF6', '#F59E0B', '#EC4899', '#64748B'])
        )])
        fig_sim_cat.update_layout(height=240, margin=dict(t=20, b=20, l=10, r=10), showlegend=False)

        with ch_c1:
            st.plotly_chart(fig_curr_cat, use_container_width=True)
        with ch_c2:
            st.plotly_chart(fig_sim_cat, use_container_width=True)

    st.markdown("---")

    # --------------------------------------------------------------------------
    # 📋 Step 3: 6대 자산 팩터별 리밸런싱 실행 계획표
    # --------------------------------------------------------------------------
    st.markdown("### 📋 Step 3: 6대 자산 팩터별 리밸런싱 실행 계획표")
    
    rebal_rows = []
    for cat_name, cat_info in my_analysis['categories_data'].items():
        curr_eval = cat_info['eval_krw']
        curr_w = (curr_eval / total_equity * 100.0) if total_equity > 0 else 0.0
        tgt_w = float(sim_targets_map.get(cat_name, 0.0))
        tgt_eval = total_equity * (tgt_w / 100.0)
        rebal_krw = tgt_eval - curr_eval
        
        h_names = [h['종목명'] for h in cat_info['holdings']]
        h_str = ", ".join(h_names) if h_names else "현금 잔고"
        
        if abs(rebal_krw) < 100000:
            act_text = "🟢 비중 적정 (유지)"
        elif rebal_krw > 0:
            act_text = f"🔵 +{int(rebal_krw):,}원 추가 매수/적립"
        else:
            act_text = f"🟠 -{int(abs(rebal_krw)):,}원 이익 실현/축소"

        rebal_rows.append({
            "자산 팩터": cat_name,
            "현재 평가액": f"{int(curr_eval):,}원",
            "현재 비중": f"{curr_w:.1f}%",
            "목표 비중": f"{tgt_w:.0f}%",
            "목표 평가액": f"{int(tgt_eval):,}원",
            "조정 필요 금액": act_text,
            "포함된 내 보유 종목": h_str
        })

    st.dataframe(
        pd.DataFrame(rebal_rows),
        use_container_width=True,
        hide_index=True,
        column_config={
            "자산 팩터": st.column_config.TextColumn("자산 팩터", width="medium"),
            "현재 평가액": st.column_config.TextColumn("현재 평가액", width="small"),
            "현재 비중": st.column_config.TextColumn("현재 비중", width="small"),
            "목표 비중": st.column_config.TextColumn("목표 비중", width="small"),
            "목표 평가액": st.column_config.TextColumn("목표 평가액", width="small"),
            "조정 필요 금액": st.column_config.TextColumn("리밸런싱 실행 제언", width="medium"),
            "포함된 내 보유 종목": st.column_config.TextColumn("포함된 내 종목", width="large")
        }
    )

    st.markdown("---")

    # --------------------------------------------------------------------------
    # 🏦 Step 4: 5대 계좌별 세제 혜택 극대화 & 자금 배분 전략
    # --------------------------------------------------------------------------
    st.markdown("### 🏦 Step 4: 5대 계좌별 세제 혜택 극대화 & 자금 배분 가이드")
    
    k_col1, k_col2, k_col3 = st.columns(3)
    with k_col1:
        st.info("💡 **연금저축펀드 (목표 40%)**\n\n- 연간 600만 원 한도 세액공제(13.2~16.5% 환급)\n- 배당소득세(15.4%) 과세이연 혜택\n- 추천 자산: `TIGER 미국S&P500`, `ACE 미국배당다우존스`")
    with k_col2:
        st.info("💡 **ISA 계좌 (목표 20%)**\n\n- 순손익 200만~400만 원 비과세, 초과분 9.9% 분리과세\n- 국내상장 해외 ETF 및 고배당주 최적\n- 추천 자산: `SOL 미국배당다우존스`, `RISE 미국나스닥100`")
    with k_col3:
        st.info("💡 **일반계좌 (해외 25% / 국내 10%)**\n\n- 해외 주식: 연간 250만 원 양도소득세 기본공제\n- 단기 퀀트 스윙(SEPA VCP) 및 글로벌 우량 배당주\n- 추천 자산: `FAST`, `KO`, `JNJ`, `NVDA`, `MSFT`")


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
        if "🔴" in results['market_status']:
            st.error("🚨 **[시장 하락장 자동 셧다운 발동]** 글로벌 벤치마크 지수가 20일/50일선 아래로 꺾인 위험 구간입니다. 마크 미너비니 원칙에 따라 **신규 매수를 전면 중단하고 100% 현금을 보존**하십시오.")
        elif "🟡" in results['market_status']:
            st.warning("⚠️ **[시장 주의 관망 구간]** 지수 단기 추세가 흔들리고 있습니다. 투자 비중을 50%로 자동 축소하고 엄격한 손익비 타점에서만 접근합니다.")

        st.subheader("📡 Stage 0: 글로벌 거시 경제 통합 필터")
        col1, col2, col3, col4, col5 = st.columns([1.2, 1.2, 1, 1, 1])

        with col1:
            st.metric(
                label="🌐 글로벌 시장 상태",
                value=results['market_status'],
                delta="정상 가동" if "🟢" in results['market_status'] else ("주의 관망" if "🟡" in results['market_status'] else "매수 셧다운")
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
# 탭 4: [백테스팅] 10년 과거 검증 시뮬레이터
# ==============================================================================
with tab_backtest:
    st.subheader("📊 마크 미너비니 SEPA & 정밀 VCP 백테스팅 시뮬레이터")
    st.markdown("과거 실제 시세 데이터를 바탕으로 **안전 버퍼 손절매(-7%) & 피벗 초입 돌파(+0~2.5%) & 20일선 거래량 마른 눌림목 지지 매수** 전략의 실제 수익률을 정밀 검증합니다.")

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
        bt_capital_bt = st.number_input("시뮬레이션 초기 자산 (원)", min_value=1000000, max_value=1000000000, value=10000000, step=1000000)

    bt_run_btn = st.button("🚀 백테스트 실행하기", type="primary", use_container_width=True)

    if bt_run_btn or 'bt_result' not in st.session_state:
        with st.spinner(f"⏳ {bt_ticker} ({bt_period}) 정밀 SEPA 백테스트 시뮬레이션 계산 중..."):
            st.session_state['bt_result'] = run_single_stock_backtest(
                ticker=bt_ticker,
                period=bt_period,
                initial_capital=bt_capital_bt,
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
