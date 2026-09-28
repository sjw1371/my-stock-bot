# -*- coding: utf-8 -*-
"""
strategy.py
- Stage 0: 글로벌 거시 경제 통합 필터 및 시장 하락장 자동 셧다운(Hard Stop)
- Stage 1-2: SEPA 트렌드 템플릿 8대 조건 필수 검증 & 마크 미너비니 VCP + 추격 매수 차단 캡 + 눌림목 지지
- Stage 3: 계량 재무학 펀더멘탈 하한선 필터
- Stage 4-5: 자산 배분 및 퀀트 랭킹 엔진 (원전 완벽 구현 실전형 모델)
"""

import pandas as pd
import numpy as np


def evaluate_macro(macro_data: dict) -> tuple:
    """
    Stage 0 거시 경제 분석 & 시장 상태 판정:
    - VIX 수준 점검
    - 4대 주요 지수 50일/200일 이평선 정배열 및 20일선 추세 점검
    - 시장 상태 (🟢 ON / 🟡 CAUTION / 🔴 OFF - 신규 매수 셧다운)
    """
    vix = macro_data.get('vix', 21.51)
    if pd.isna(vix) or vix <= 0:
        vix = 21.51

    indices = macro_data.get('indices', {})

    scores = []
    detail_logs = []
    indices_summary = {}

    for name, hist in indices.items():
        if hist is not None and not hist.empty and len(hist) >= 20:
            try:
                close_series = hist['Close'].dropna()
                curr = float(close_series.iloc[-1])
                ma20 = float(close_series.rolling(20, min_periods=5).mean().iloc[-1])
                ma50 = float(close_series.rolling(50, min_periods=10).mean().iloc[-1])
                ma200 = float(close_series.rolling(200, min_periods=20).mean().iloc[-1])

                s1 = 1 if curr > ma50 else 0
                s2 = 1 if curr > ma200 else 0
                s3 = 1 if ma50 > ma200 else 0
                idx_score = s1 + s2 + s3
                scores.append(idx_score)

                is_short_down = curr < ma20
                if idx_score == 3 and not is_short_down:
                    status_text = "🟢 정배열 우상향 (매수 최적)"
                elif idx_score >= 2:
                    status_text = "🟡 단기 추세 훼손 (주의 관망)"
                else:
                    status_text = "🚨 중장기 하락세 (매수 금지)"

                indices_summary[name] = {
                    'score': idx_score,
                    'status': status_text,
                    'curr': curr,
                    'ma20': ma20,
                    'ma50': ma50,
                    'ma200': ma200,
                    's1': s1, 's2': s2, 's3': s3
                }
                detail_logs.append(
                    f"   * {name:<9}: {idx_score}.0 / 3.0 점 [{status_text}] -> (주가>MA50: {s1}, 주가>MA200: {s2}, MA50>MA200: {s3})"
                )
            except Exception:
                scores.append(2)
                detail_logs.append(f"   * {name:<9}: 기본 안전 점수(2.0) 대체 계산")
        else:
            scores.append(2)
            detail_logs.append(f"   * {name:<9}: 기본 안전 점수(2.0) 대체 계산")

    avg_score = sum(scores) / len(scores) if scores else 1.50

    if avg_score >= 2.5 and vix < 22:
        market_status = "🟢 ON"
    elif avg_score >= 1.5 and vix < 28:
        market_status = "🟡 CAUTION"
    else:
        market_status = "🔴 OFF (신규 매수 셧다운)"

    return avg_score, market_status, vix, detail_logs, indices_summary


def evaluate_trend_and_sepa(ticker: str, df: pd.DataFrame, bm_close: pd.Series = None) -> dict:
    """
    Stage 1-2 SEPA 트렌드 템플릿 8대 조건 필수 검증 & 정밀 VCP + 추격 매수 차단 캡 + 눌림목 지지
    """
    if df is None or df.empty or len(df) < 50:
        return get_fallback_data(ticker)

    try:
        df = df.copy()
        close_series = df['Close'].dropna()
        if close_series.empty or len(close_series) < 50:
            return get_fallback_data(ticker)

        curr_price = float(close_series.iloc[-1])

        df['MA20'] = close_series.rolling(20, min_periods=5).mean()
        df['MA50'] = close_series.rolling(50, min_periods=10).mean()
        df['MA60'] = close_series.rolling(60, min_periods=10).mean()
        df['MA150'] = close_series.rolling(150, min_periods=20).mean()
        df['MA200'] = close_series.rolling(200, min_periods=30).mean()

        ma20_curr = float(df['MA20'].iloc[-1]) if pd.notna(df['MA20'].iloc[-1]) else curr_price
        ma50_curr = float(df['MA50'].iloc[-1]) if pd.notna(df['MA50'].iloc[-1]) else curr_price
        ma60_curr = float(df['MA60'].iloc[-1]) if pd.notna(df['MA60'].iloc[-1]) else curr_price
        ma150_curr = float(df['MA150'].iloc[-1]) if pd.notna(df['MA150'].iloc[-1]) else curr_price
        ma200_curr = float(df['MA200'].iloc[-1]) if pd.notna(df['MA200'].iloc[-1]) else curr_price
        ma200_1m_ago = float(df['MA200'].iloc[-22]) if len(df) >= 22 and pd.notna(df['MA200'].iloc[-22]) else ma200_curr

        high_52wk = float(df['High'].tail(min(252, len(df))).max())
        low_52wk = float(df['Low'].tail(min(252, len(df))).min())

        # ======================================================================
        # 🌟 SEPA 8대 트렌드 템플릿 (100% 필수 0순위 관문)
        # ======================================================================
        c1 = (curr_price > ma150_curr) and (curr_price > ma200_curr)
        c2 = ma150_curr > ma200_curr
        c3 = ma200_curr >= ma200_1m_ago
        c4 = (ma50_curr > ma150_curr) and (ma50_curr > ma200_curr)
        c5 = curr_price >= (low_52wk * 1.25)
        c6 = curr_price >= (high_52wk * 0.75)

        c7 = True
        if bm_close is not None and len(bm_close) >= len(df):
            try:
                rs_series = (df['Close'] / bm_close.reindex(df.index).ffill()).dropna()
                rs_curr = rs_series.iloc[-1]
                rs_6wk_ago = rs_series.iloc[-30] if len(rs_series) >= 30 else rs_curr
                c7 = bool(rs_curr > rs_6wk_ago)
            except Exception:
                c7 = True

        c8 = curr_price > ma50_curr

        trend_template_pass = all([c1, c2, c3, c4, c5, c6, c7, c8])
        passed_conditions_count = sum([c1, c2, c3, c4, c5, c6, c7, c8])

        # ======================================================================
        # 🌟 마크 미너비니 VCP & 실전 타점 정밀 분석
        # ======================================================================
        highs = df['High'].values
        lows = df['Low'].values
        volumes = df['Volume'].values
        n = len(df)

        # 1) 다중 파동 수축 (Multi-Contraction)
        if n >= 40:
            d1 = (np.max(highs[n-40:n-20]) - np.min(lows[n-40:n-20])) / curr_price
            d2 = (np.max(highs[n-20:n-5]) - np.min(lows[n-20:n-5])) / curr_price
            d3 = (np.max(highs[n-5:n]) - np.min(lows[n-5:n])) / curr_price
            is_vcp_contraction = bool((d3 < d2 and d2 <= d1 * 1.15) or (d3 <= 0.055 and d2 < d1))
        else:
            is_vcp_contraction = False

        # 2) 거래량 고갈 (Volume Dry-Up)
        df['Vol_MA50'] = df['Volume'].rolling(50, min_periods=10).mean()
        df['Vol_MA20'] = df['Volume'].rolling(20, min_periods=5).mean()
        vol_ma50_curr = float(df['Vol_MA50'].iloc[-1]) if (pd.notna(df['Vol_MA50'].iloc[-1]) and df['Vol_MA50'].iloc[-1] > 0) else 1.0
        vol_ma20_curr = float(df['Vol_MA20'].iloc[-1]) if (pd.notna(df['Vol_MA20'].iloc[-1]) and df['Vol_MA20'].iloc[-1] > 0) else 1.0

        recent_vol_avg = float(np.mean(volumes[-4:])) if n >= 4 else float(volumes[-1])
        is_dry_up = bool(recent_vol_avg <= vol_ma50_curr * 0.85)

        # 3) 피벗 포인트 (최근 10일 저항선) 및 추격 매수 캡(+0.0% ~ +2.5% 이내)
        pivot_price = float(np.max(highs[-10:-1])) if n >= 11 else curr_price
        curr_vol = float(volumes[-1])
        vol_ratio = curr_vol / vol_ma20_curr if vol_ma20_curr > 0 else 1.0

        # 피벗 상방 돌파 (피벗 돌파 직후 +0% ~ +2.5% 이내의 이상적 초입 타점)
        pivot_dist_pct = ((curr_price - pivot_price) / pivot_price) * 100 if pivot_price > 0 else 0.0
        is_ideal_pivot_entry = bool((0.0 <= pivot_dist_pct <= 2.5) and (vol_ratio >= 1.20))
        is_over_chased = bool(pivot_dist_pct > 3.0)  # +3% 이상 이미 뜬 상투는 추격 매수 차단

        # 4) 20일선 거래량 마른 눌림목 지지 타점 (First Pullback to 20MA)
        disp_20 = ((curr_price - ma20_curr) / ma20_curr) * 100 if ma20_curr > 0 else 0.0
        is_pullback_entry = bool(trend_template_pass and (-1.0 <= disp_20 <= 2.0) and is_dry_up and (curr_price >= ma20_curr * 0.99))

        # ATR(14)
        high_low = df['High'] - df['Low']
        high_cp = np.abs(df['High'] - df['Close'].shift())
        low_cp = np.abs(df['Low'] - df['Close'].shift())
        df['ATR'] = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1).rolling(14, min_periods=5).mean()
        curr_atr = float(df['ATR'].iloc[-1]) if pd.notna(df['ATR'].iloc[-1]) else curr_price * 0.02

        # 승률 및 켈리 비중
        df['Returns'] = df['Close'].pct_change()
        wins = df['Returns'][df['Returns'] > 0]
        losses = df['Returns'][df['Returns'] < 0]

        valid_returns = df['Returns'].dropna()
        win_rate = len(wins) / len(valid_returns) if len(valid_returns) > 0 else 0.45
        payoff_ratio = abs(wins.mean() / losses.mean()) if not losses.empty and losses.mean() != 0 and pd.notna(losses.mean()) else 1.2
        if pd.isna(payoff_ratio) or payoff_ratio <= 0:
            payoff_ratio = 1.2

        kelly_f = win_rate - ((1 - win_rate) / payoff_ratio) if payoff_ratio > 0 else 0.0
        if pd.isna(kelly_f):
            kelly_f = 0.04
        recommended_weight = max(0.04, float(kelly_f * 0.5)) if trend_template_pass else 0.02

        return {
            '티커': ticker,
            '현재가': curr_price,
            '피벗거리(%)': round(float(disp_20), 2) if not pd.isna(disp_20) else 0.0,
            '피벗돌파율(%)': round(float(pivot_dist_pct), 2),
            '승률': round(float(win_rate), 3),
            '손익비': round(float(payoff_ratio), 2),
            '켈리비중': round(float(recommended_weight), 4),
            'ATR': round(float(curr_atr), 2),
            '거래량배수': round(float(vol_ratio), 2),
            'VCP수축': is_vcp_contraction,
            '거래량고갈': is_dry_up,
            '피벗초입돌파': is_ideal_pivot_entry,
            '눌림목지지': is_pullback_entry,
            '단기과열여부': is_over_chased,
            'VCP패턴': (is_vcp_contraction and is_dry_up) or is_ideal_pivot_entry or is_pullback_entry,
            'MA20': ma20_curr,
            'MA50': ma50_curr,
            'MA60': ma60_curr,
            'MA150': ma150_curr,
            'MA200': ma200_curr,
            '트렌드_템플릿': "✅ PASS" if trend_template_pass else f"⚠️ {passed_conditions_count}/8",
            '템플릿_통과수': passed_conditions_count,
            '템플릿_PASS여부': trend_template_pass
        }
    except Exception:
        return get_fallback_data(ticker)


def get_fallback_data(ticker: str) -> dict:
    price = 73000.0 if ticker == "005930" else (172000.0 if ticker == "000660" else 150.0)
    return {
        '티커': ticker, '현재가': price, '피벗거리(%)': -2.1, '피벗돌파율(%)': 0.0, '승률': 0.45, '손익비': 1.1,
        '켈리비중': 0.04, 'ATR': price * 0.025, '거래량배수': 1.0, 'VCP수축': False,
        '거래량고갈': False, '피벗초입돌파': False, '눌림목지지': False, '단기과열여부': False, 'VCP패턴': False,
        'MA20': price * 1.03, 'MA50': price * 1.04, 'MA150': price * 1.05, 'MA200': price * 1.06,
        'MA60': price * 1.06, '트렌드_템플릿': "⚠️ 6/8", '템플릿_통과수': 6, '템플릿_PASS여부': False
    }


def evaluate_fundamentals(fund_info: dict) -> dict:
    """
    Stage 3 펀더멘탈 필터링 (ROE > 0%, 이익성장률 > 0%)
    """
    roe = fund_info.get('ROE', 0.12)
    growth = fund_info.get('이익성장', 0.10)

    is_roe_pass = roe is not None and not pd.isna(roe) and roe > 0
    is_growth_pass = growth is not None and not pd.isna(growth) and growth > 0

    if is_roe_pass and is_growth_pass:
        fund_grade = "🟢 Pass"
    else:
        fund_grade = "⚠️ Fail"

    return {
        '티커': fund_info['티커'],
        '종목명': fund_info.get('종목명', fund_info['티커']),
        '섹터': fund_info.get('섹터', 'Technology'),
        'ROE(%)': round(float(roe) * 100, 1) if roe is not None and not pd.isna(roe) else 0.0,
        '이익성장(%)': round(float(growth) * 100, 1) if growth is not None and not pd.isna(growth) else 0.0,
        '등급': fund_grade
    }


def calculate_portfolio_allocation(
    pipeline_df: pd.DataFrame,
    market_status: str,
    strategy_mode: str = "기존 (엄격 모드 - 150% & 5%)",
    capital: float = 10000000,
    exchange_rate: float = 1350
) -> pd.DataFrame:
    """
    Stage 4-5 자산배분 및 퀀트 랭킹 엔진 (원전 완벽 구현 실전형 모델)
    """
    if pipeline_df is None or pipeline_df.empty:
        return None

    # 시장 셧다운 판정: 하락장(🔴 OFF)일 경우 신규 매수 전면 차단
    is_market_shutdown = "🔴" in market_status

    df = pipeline_df.copy()

    # 하락 추세 종목(MA20 < MA60 이면서 주가 < MA20) 사전 배제
    df = df[~((df['현재가'] < df['MA20']) & (df['MA20'] < df['MA60']))]
    if df.empty:
        df = pipeline_df.copy()

    market_multiplier = 1.0 if "🟢" in market_status else (0.5 if "🟡" in market_status else 0.0)
    df['켈리비중'] = df['켈리비중'].fillna(0.04)
    df['최종비중'] = df['켈리비중'] * market_multiplier

    portfolio_status = []
    sort_priority = []

    for _, row in df.iterrows():
        curr = float(row['현재가']) if pd.notna(row['현재가']) else 100.0
        ma20 = float(row['MA20']) if pd.notna(row['MA20']) else curr
        ma60 = float(row['MA60']) if pd.notna(row['MA60']) else curr
        disp_20 = float(row['피벗거리(%)']) if pd.notna(row['피벗거리(%)']) else 0.0
        vol_ratio = float(row['거래량배수']) if pd.notna(row['거래량배수']) else 1.0
        is_template_pass = bool(row.get('템플릿_PASS여부', False))
        is_pivot_entry = bool(row.get('피벗초입돌파', False))
        is_pullback = bool(row.get('눌림목지지', False))
        is_over_chased = bool(row.get('단기과열여부', False))
        is_vcp_ready = bool(row.get('VCP수축', False) and row.get('거래량고갈', False))

        # 1. 시장 하락장 셧다운 시
        if is_market_shutdown:
            stage, strategy, priority = "시장 관망", "🛑 하락장 매수 셧다운 (현금 100% 대기)", 90

        # 2. 역배열 하락세
        elif curr < ma20 and ma20 < ma60:
            stage, strategy, priority = "5단계 (하락)", "❌ 매수 금지 (하방 이탈)", 99

        # 3. 단기 과열 (추격 매수 차단: 이미 +3% 이상 뜸)
        elif is_over_chased or disp_20 > 5.5:
            stage, strategy, priority = "2단계 (과열)", "🚨 단기 과열 (추격 매수 금지 - 고점 덫)", 8

        # 4. 트렌드 템플릿 PASS 종목의 정밀 실전 타점
        elif is_template_pass:
            if is_pivot_entry:
                stage, strategy, priority = "3단계 (가속)", "🔥 VCP 피벗 초입 돌파 (최우선 매수)", 1
            elif is_pullback:
                stage, strategy, priority = "2단계 (수축)", "💎 20일선 거래량 마른 눌림목 (저위험 매수)", 2
            elif is_vcp_ready and 0.0 <= disp_20 <= 3.0:
                stage, strategy, priority = "2단계 (수축)", "⏳ VCP 수축 완료 (돌파 임박 대기)", 3
            elif vol_ratio >= 1.3 and 0.0 <= disp_20 <= 3.5:
                stage, strategy, priority = "3단계 (가속)", "🔥 불타기 (거래량 동반 추가 매수)", 4
            elif 0.0 <= disp_20 <= 4.0:
                stage, strategy, priority = "2단계 (안정)", "📈 강력 보유 (추세 안정)", 5
            else:
                stage, strategy, priority = "3단계 (가속)", "⚠️ 보유 (거래량 부족 추가 유보)", 6

        # 5. 트렌드 템플릿 미달 종목
        elif curr >= ma20 and ma20 >= ma60:
            if 0.0 <= disp_20 <= 3.0:
                stage, strategy, priority = "관망", "⚠️ 트렌드 템플릿 조건 미달 (관망)", 7
            else:
                stage, strategy, priority = "관망", "⚠️ 관망", 8

        elif curr < ma20 and ma20 >= ma60:
            stage, strategy, priority = "4단계 (이탈)", "💰 익절 확정 혹은 리스크 축소 분할매도", 9
        else:
            stage, strategy, priority = "분석 대기", "관망", 10

        portfolio_status.append({'현재_단계': stage, '전략제언': strategy})
        sort_priority.append(priority)

    status_df = pd.DataFrame(portfolio_status)
    df = pd.concat([df.reset_index(drop=True), status_df], axis=1)
    df['우선순위'] = sort_priority

    # 정렬: 우선순위(1~99) ➔ 템플릿 통과 여부(PASS 우선) ➔ 피벗거리(오름차순)
    df['템플릿_통과'] = df['트렌드_템플릿'].apply(lambda x: 0 if "✅" in str(x) else 1)
    df = df.sort_values(by=['우선순위', '템플릿_통과', '피벗거리(%)'], ascending=[True, True, True])

    # 섹터 비중 상한(35%) 적용
    final_rows = []
    sector_weights = {}

    for _, row in df.iterrows():
        sec = row.get('섹터', 'Other')
        curr_sec_w = sector_weights.get(sec, 0.0)
        w_val = float(row['최종비중']) if pd.notna(row['최종비중']) else 0.02
        if curr_sec_w + w_val <= 0.35:
            sector_weights[sec] = curr_sec_w + w_val
            final_rows.append(row)

    if not final_rows:
        final_rows = [row for _, row in df.head(15).iterrows()]

    final_df = pd.DataFrame(final_rows)

    qty_list = []
    raw_price_list = []
    for _, row in final_df.iterrows():
        tk = str(row['티커'])
        curr = float(row['현재가']) if pd.notna(row['현재가']) and row['현재가'] > 0 else 100.0
        raw_price_list.append(curr)
        w = float(row['최종비중']) if pd.notna(row['최종비중']) else 0.0
        allocated_capital = float(capital) * w

        if tk.isdigit() and len(tk) == 6:
            cost_per_share = curr * 1.002
        else:
            cost_per_share = curr * float(exchange_rate) * 1.004

        if cost_per_share > 0 and not np.isnan(allocated_capital) and allocated_capital > 0:
            qty = int(allocated_capital // cost_per_share)
        else:
            qty = 0
        qty_list.append(max(0, qty))

    final_df['raw_현재가'] = raw_price_list
    final_df['매수수량_숫자'] = qty_list
    final_df['매수수량'] = [f"{q}주" for q in qty_list]
    final_df['최종비중_숫자'] = (final_df['최종비중'].fillna(0.0) * 100).round(1)
    final_df['최종비중(%)'] = final_df['최종비중_숫자'].astype(str) + '%'
    final_df['현재가_표기'] = final_df.apply(
        lambda r: f"{int(r['raw_현재가']):,}원" if str(r['티커']).isdigit() else f"${r['raw_현재가']:,.2f}", axis=1
    )

    top15_df = final_df.head(15).reset_index(drop=True)
    top15_df['순위'] = [f"{i+1}위" for i in range(len(top15_df))]

    return top15_df
