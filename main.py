# -*- coding: utf-8 -*-
"""
main.py
- JTI 전수조사형 퀀트 파이프라인 CLI 실행기 (코랩 100% 정합 & 초고속 배치 엔진)
"""

import sys
import io
import re
import argparse
import pandas as pd
from datetime import datetime

# Windows 콘솔 인코딩 대응 (UTF-8)
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from data_fetch import (
    fetch_universe_tickers,
    fetch_macro_data,
    fetch_benchmark_close,
    fetch_all_stock_history_batch,
    fetch_fundamental_data,
    NAME_DICT
)
from strategy import (
    evaluate_macro,
    evaluate_trend_and_sepa,
    evaluate_fundamentals,
    calculate_portfolio_allocation
)


def print_pretty_grid_table(df: pd.DataFrame) -> str:
    """
    터미널에 깔끔한 아스키 그리드 표를 출력하는 유틸리티
    """
    if df is None or df.empty:
        return "⚠️ 출력할 데이터가 없습니다."

    display_cols = ['순위', '티커', '종목명', '섹터', '트렌드_템플릿', '등급', '현재가_표기', '최종비중(%)', '매수수량', '현재_단계', '전략제언']
    cols_to_use = [c for c in display_cols if c in df.columns]
    rename_map = {'현재가_표기': '현재가'}
    show_df = df[cols_to_use].rename(columns=rename_map)

    headers = list(show_df.columns)

    def get_display_width(text):
        width = 0
        for char in str(text):
            if ord(char) > 127:
                width += 2
            else:
                width += 1
        return width

    col_widths = {}
    for col in headers:
        max_w = get_display_width(col)
        for val in show_df[col]:
            max_w = max(max_w, get_display_width(val))
        col_widths[col] = max_w + 2

    border_line = "+" + "+".join(["-" * col_widths[col] for col in headers]) + "+"
    lines = [border_line]

    header_row = "|"
    for col in headers:
        pad = col_widths[col] - get_display_width(col)
        header_row += f" {col}" + " " * (pad - 1) + "|"
    lines.append(header_row)
    lines.append(border_line)

    for _, row in show_df.iterrows():
        data_row = "|"
        for col in headers:
            val = str(row[col])
            val = re.sub(r'[^\w\s\$\%\,\.\-\(\)\:\!\?\️\💎\⚖️\🚨\📈\❌\✅\🔥\💰\🟢\원]', '', val)
            pad = col_widths[col] - get_display_width(val)
            if col in ['현재가', '최종비중(%)', '매수수량', '순위']:
                data_row += " " * (pad - 1) + f"{val} |"
            else:
                data_row += f" {val}" + " " * (pad - 1) + "|"
        lines.append(data_row)

    lines.append(border_line)
    return "\n".join(lines)


def run_pipeline(
    select_mode: str = "1. S&P500",
    raw_input_tickers: str = "AES,A,STT,MAS,CVX",
    strategy_mode: str = "기존 (엄격 모드 - 150% & 5%)",
    capital: float = 10000000,
    exchange_rate: float = 1550
):
    print("=" * 100)
    print(f"🚀 [JTI 퀀트 파이프라인 가동] 시장: {select_mode} | 전략: {strategy_mode} | 자산: {capital:,.0f}원")
    print("=" * 100)

    # 1. 유니버스 티커 수집
    print("🌐 [Step 1] 분석 대상 전 종목 명단 수집 중...")
    tickers = fetch_universe_tickers(select_mode, raw_input_tickers)
    print(f"   -> 총 {len(tickers)}개 전 종목 명단 확보 완료.")

    # 2. Stage 0 거시 경제 분석
    print(f"\n📡 [Step 2 / Stage 0] 글로벌 거시 경제 통합 필터 가동 (기준일: {datetime.now().strftime('%Y-%m-%d')})")
    macro_data = fetch_macro_data()
    market_score, market_status, vix, detail_logs, _ = evaluate_macro(macro_data)

    print("-" * 100)
    print(f" 📊 [Part 1] 글로벌 시장 종합 지수 스코어 : {market_score:.2f} / 3.00 마스터 필터 상태 -> {market_status}")
    print(f" 📉 [Part 2] VIX 공포 및 내재 변동성 지수 : {vix:.2f} ({'🚨 고위험 발작 주의 구간' if vix >= 20 else '🍏 변동성 안정 국면'})")
    print(" 🌐 [Part 3] 4대 핵심 글로벌 벤치마크 지수별 정배열 추세 :")
    for log in detail_logs:
        print(log)
    print("-" * 100)

    # 3. Stage 1-2 전 종목 초고속 배치 다운로드 및 SEPA 분석
    print(f"\n🔍 [Step 3 / Stage 1-2] {len(tickers)}개 전 종목 초고속 일괄 병렬 시세 패칭 & SEPA VCP 분석 중...")
    bm_close = fetch_benchmark_close()
    stock_dfs = fetch_all_stock_history_batch(tickers, select_mode=select_mode, period='1y')

    pipeline_records = []
    for ticker in tickers:
        df = stock_dfs.get(ticker, pd.DataFrame())
        sepa_result = evaluate_trend_and_sepa(ticker, df, bm_close)
        pipeline_records.append(sepa_result)

    pipeline_df = pd.DataFrame(pipeline_records)
    print(f"   -> 총 {len(pipeline_df)}개 후보군 적재 완료.")

    # 4. Stage 3 펀더멘탈 필터
    print("\n💎 [Step 4 / Stage 3] 계량 재무학 펀더멘탈 하한선 조건 검증 (ROE > 0%, 이익성장 > 0%)...")
    fund_records = []
    for ticker in pipeline_df['티커']:
        fund_data = fetch_fundamental_data(ticker, select_mode=select_mode)
        evaluated_fund = evaluate_fundamentals(fund_data)
        fund_records.append(evaluated_fund)

    fund_df = pd.DataFrame(fund_records)
    pipeline_df = pd.merge(pipeline_df, fund_df[['티커', '종목명', '섹터', 'ROE(%)', '이익성장(%)', '등급']], on='티커')
    print("   -> 펀더멘탈 조건 검증 및 데이터 병합 완료.")

    # 5. Stage 4-5 자산배분 및 포트폴리오 산출
    print(f"\n🎯 [Step 5 / Stage 4-5] 자산배분 엔진 가동 및 리스크 헤지 통제 적용 (전략: {strategy_mode})...")
    final_portfolio = calculate_portfolio_allocation(
        pipeline_df=pipeline_df,
        market_status=market_status,
        strategy_mode=strategy_mode,
        capital=capital,
        exchange_rate=exchange_rate
    )

    # 6. 최종 결과 출력
    print("\n" + "=" * 120)
    print(f"🏆 JTI 통합 퀀트 포트폴리오 결과 보고서 [선택 시장: {select_mode} | 매수 전략: {strategy_mode}] (시장 환경: {market_status})")
    print("=" * 120)
    if final_portfolio is not None and not final_portfolio.empty:
        print(print_pretty_grid_table(final_portfolio))
    else:
        print("⚠️ 퀀트 필터 제약을 통과한 유효 종목이 존재하지 않습니다.")
    print("=" * 120)

    return final_portfolio


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JTI Full Market Quant System CLI")
    parser.add_argument("--market", type=str, default="1. S&P500", choices=["1. S&P500", "2. nasdaq", "3. 코스피", "4. 코스닥", "5. 전체", "6. 직접입력"], help="분석 대상 시장 지수")
    parser.add_argument("--tickers", type=str, default="AES,A,STT,MAS,CVX", help="직접 입력용 티커 풀 (콤마 구분)")
    parser.add_argument("--strategy", type=str, default="기존 (엄격 모드 - 150% & 5%)", choices=["기존 (엄격 모드 - 150% & 5%)", "옵션 A (거래량 완화 - 120%)", "옵션 B (이격도 완화 - 7%)", "옵션 C (복합 완화 - 120% & 7%)"], help="매수 타점 전략")
    parser.add_argument("--capital", type=float, default=10000000, help="총 운용 자산 (원)")
    parser.add_argument("--exchange_rate", type=float, default=1550, help="대용 기준 환율 (원/달러)")

    args = parser.parse_args()

    try:
        run_pipeline(
            select_mode=args.market,
            raw_input_tickers=args.tickers,
            strategy_mode=args.strategy,
            capital=args.capital,
            exchange_rate=args.exchange_rate
        )
    except Exception as e:
        print(f"❌ [에러 리포트]: {e}")
        import traceback
        traceback.print_exc()
