# -*- coding: utf-8 -*-
"""
backtest.py
- [엔진 1] 6대 자산 팩터 기반 포트폴리오 과거 10년 종합 백테스팅 (CAGR, MDD, 샤프 지수, 벤치마크 비교)
- [엔진 2] 미래 10년 정기 적립 & 배당 재투자 복리 자산 성장 & 월 배당금 달성 시뮬레이터
- [엔진 3] 개별 종목 SEPA & VCP 기술적 백테스팅
"""

import sys
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from data_fetch import clean_ticker, NAME_DICT


# 6대 자산군 대표 프록시 티커 및 연평균 기대 배당률
FACTOR_PROXIES = {
    "🌱 글로벌 코어 지수": {"ticker": "SPY", "name": "S&P 500 (SPY)", "div_yield": 0.013},
    "💰 고배당 & 인컴": {"ticker": "SCHD", "name": "미국배당다우존스 (SCHD)", "div_yield": 0.038},
    "🤖 테마 & 미래혁신": {"ticker": "QQQ", "name": "나스닥 테크 (QQQ)", "div_yield": 0.006},
    "🚀 퀀트 스윙 & 모멘텀": {"ticker": "MTUM", "name": "모멘텀 지수 (MTUM)", "div_yield": 0.010},
    "🪙 대체자산 (코인)": {"ticker": "BTC-USD", "name": "비트코인 (BTC)", "div_yield": 0.0},
    "💵 안전 현금": {"ticker": "CASH", "name": "안전 현금 (단기금리)", "div_yield": 0.030}
}


def run_portfolio_historical_backtest(
    initial_capital: float = 39000000.0,
    period: str = "5y",
    category_weights: dict = None
) -> dict:
    """
    내 6대 자산 팩터 포트폴리오의 과거(5년/10년) 실제 데이터 기반 종합 백테스팅 엔진
    """
    if category_weights is None:
        category_weights = {
            "🌱 글로벌 코어 지수": 0.35,
            "💰 고배당 & 인컴": 0.30,
            "🤖 테마 & 미래혁신": 0.15,
            "🚀 퀀트 스윙 & 모멘텀": 0.10,
            "🪙 대체자산 (코인)": 0.02,
            "💵 안전 현금": 0.08
        }

    # 1. 과거 데이터 다운로드 (프록시 자산 + 벤치마크)
    proxy_tickers = [info["ticker"] for cat, info in FACTOR_PROXIES.items() if info["ticker"] != "CASH"]
    bm_tickers = ["SPY", "^KS11"]
    all_download_tickers = list(set(proxy_tickers + bm_tickers))

    try:
        raw_df = yf.download(all_download_tickers, period=period, progress=False)
        if raw_df.empty:
            return None
    except Exception:
        return None

    # MultiIndex 정규화
    close_df = pd.DataFrame()
    if isinstance(raw_df.columns, pd.MultiIndex):
        if 'Close' in raw_df.columns.levels[0]:
            close_df = raw_df['Close'].copy()
        elif 'Close' in raw_df.columns.levels[1]:
            close_df = raw_df.xs('Close', axis=1, level=1).copy()
        else:
            close_df = raw_df.copy()
    else:
        close_df = raw_df.copy()

    close_df = close_df.ffill().dropna()
    if len(close_df) < 50:
        return None

    # 2. 일별 수익률 계산
    daily_returns = close_df.pct_change().dropna()
    
    # 3. 포트폴리오 합성 일별 수익률 계산
    port_daily_ret = pd.Series(0.0, index=daily_returns.index)
    
    for cat_name, w in category_weights.items():
        if w <= 0:
            continue
        proxy = FACTOR_PROXIES.get(cat_name)
        if not proxy:
            continue
        tk = proxy["ticker"]
        if tk == "CASH":
            # 현금 연 3.0% 일별 복리 수익
            cash_daily_ret = (1.0 + 0.030) ** (1 / 252.0) - 1.0
            port_daily_ret += cash_daily_ret * w
        elif tk in daily_returns:
            port_daily_ret += daily_returns[tk] * w

    # 4. 누적 자산 성장 곡선 (Equity Curve)
    port_equity = (1.0 + port_daily_ret).cumprod() * float(initial_capital)
    
    # 벤치마크 S&P 500 및 KOSPI 누적 성장 곡선
    spy_ret = daily_returns['SPY'] if 'SPY' in daily_returns else port_daily_ret
    spy_equity = (1.0 + spy_ret).cumprod() * float(initial_capital)

    ks_ret = daily_returns['^KS11'] if '^KS11' in daily_returns else (spy_ret * 0.4)
    ks_equity = (1.0 + ks_ret).cumprod() * float(initial_capital)

    # 5. 핵심 성과 지표 계산
    total_days = (port_equity.index[-1] - port_equity.index[0]).days
    years = total_days / 365.25 if total_days > 0 else 1.0

    final_port_val = float(port_equity.iloc[-1])
    port_total_return = (final_port_val - initial_capital) / initial_capital * 100.0
    port_cagr = ((final_port_val / initial_capital) ** (1.0 / years) - 1.0) * 100.0 if years > 0 else 0.0

    # MDD (최대 낙폭)
    port_peak = port_equity.cummax()
    port_dd = (port_equity - port_peak) / port_peak
    port_mdd = float(port_dd.min()) * 100.0

    # 연간 변동성 및 샤프 지수
    annual_vol = float(port_daily_ret.std() * np.sqrt(252)) * 100.0
    rf_rate = 3.0  # 무위험 수익률 3.0%
    sharpe_ratio = (port_cagr - rf_rate) / annual_vol if annual_vol > 0 else 1.0

    # 벤치마크 성과
    final_spy_val = float(spy_equity.iloc[-1])
    spy_cagr = ((final_spy_val / initial_capital) ** (1.0 / years) - 1.0) * 100.0
    spy_peak = spy_equity.cummax()
    spy_mdd = float(((spy_equity - spy_peak) / spy_peak).min()) * 100.0

    final_ks_val = float(ks_equity.iloc[-1])
    ks_cagr = ((final_ks_val / initial_capital) ** (1.0 / years) - 1.0) * 100.0
    ks_peak = ks_equity.cummax()
    ks_mdd = float(((ks_equity - ks_peak) / ks_peak).min()) * 100.0

    # 누적 예상 배당금 수익
    weighted_div_yield = sum([
        w * FACTOR_PROXIES[cat]["div_yield"] for cat, w in category_weights.items() if cat in FACTOR_PROXIES
    ])
    est_total_dividend_paid = float(port_equity.mean() * weighted_div_yield * years)

    # 시계열 차트 데이터프레임
    hist_chart_df = pd.DataFrame({
        'Date': port_equity.index,
        '내 포트폴리오': port_equity.values,
        'S&P 500 (SPY)': spy_equity.values,
        '코스피 (KOSPI)': ks_equity.values,
        '투자 원금': [initial_capital] * len(port_equity)
    }).set_index('Date')

    # 연도별 수익률 비교 테이블
    yearly_df = pd.DataFrame({
        '포트폴리오': port_daily_ret,
        'S&P 500': spy_ret,
        '코스피': ks_ret
    }).resample('YE').apply(lambda x: (1 + x).prod() - 1) * 100.0

    yearly_records = []
    for dt, row in yearly_df.iterrows():
        yearly_records.append({
            "연도": f"{dt.year}년",
            "내 포트폴리오": f"{row['포트폴리오']:+.1f}%",
            "S&P 500": f"{row['S&P 500']:+.1f}%",
            "코스피": f"{row['코스피']:+.1f}%",
            "초과성과(vs코스피)": f"{row['포트폴리오'] - row['코스피']:+.1f}%"
        })

    return {
        'initial_capital': initial_capital,
        'final_capital': final_port_val,
        'total_return_pct': port_total_return,
        'cagr': port_cagr,
        'mdd': port_mdd,
        'sharpe': sharpe_ratio,
        'annual_vol': annual_vol,
        'weighted_div_yield': weighted_div_yield * 100.0,
        'est_total_dividend_paid': est_total_dividend_paid,
        'years': round(years, 1),
        'spy_cagr': spy_cagr,
        'spy_mdd': spy_mdd,
        'ks_cagr': ks_cagr,
        'ks_mdd': ks_mdd,
        'hist_chart_df': hist_chart_df,
        'yearly_records': yearly_records
    }


def run_future_wealth_projection(
    initial_capital: float = 39000000.0,
    monthly_contribution: float = 1000000.0,
    annual_growth_rate: float = 10.5,     # 연 기대 자본수익률 (%)
    annual_dividend_yield: float = 3.2,   # 연 배당수익률 (%)
    years: int = 10,
    reinvest_dividend: bool = True
) -> dict:
    """
    미래 10년 정기 적립식 복리 성장 & 월 배당금 현금흐름 시뮬레이터
    """
    total_months = years * 12
    monthly_growth_r = (1.0 + annual_growth_rate / 100.0) ** (1.0 / 12.0) - 1.0
    monthly_div_r = (annual_dividend_yield / 100.0) / 12.0

    curr_wealth = float(initial_capital)
    cum_principal = float(initial_capital)
    cum_dividend_earned = 0.0

    monthly_records = []
    yearly_summary = []

    milestones = {
        "월 배당 50만 원 달성": None,
        "월 배당 100만 원 달성": None,
        "월 배당 200만 원 달성": None,
        "월 배당 300만 원 달성": None,
        "월 배당 500만 원 달성": None,
        "총 자산 1억 원 달성": None,
        "총 자산 3억 원 달성": None,
        "총 자산 5억 원 달성": None,
        "총 자산 10억 원 달성": None
    }

    start_date = datetime.today()

    for m in range(1, total_months + 1):
        month_date = start_date + timedelta(days=m * 30.4)
        
        # 1. 월 정기 납입 원금 추가
        curr_wealth += monthly_contribution
        cum_principal += monthly_contribution

        # 2. 월 자본 수익
        growth_gain = curr_wealth * monthly_growth_r
        curr_wealth += growth_gain

        # 3. 월 배당금 수령
        div_income = curr_wealth * monthly_div_r
        cum_dividend_earned += div_income

        # 배당금 재투자 여부
        if reinvest_dividend:
            curr_wealth += div_income

        current_monthly_dividend_runrate = curr_wealth * (annual_dividend_yield / 100.0) / 12.0

        # 마일스톤 체크
        curr_years_passed = m / 12.0
        if current_monthly_dividend_runrate >= 500000 and milestones["월 배당 50만 원 달성"] is None:
            milestones["월 배당 50만 원 달성"] = f"{curr_years_passed:.1f}년 후 ({month_date.strftime('%Y년 %m월')})"
        if current_monthly_dividend_runrate >= 1000000 and milestones["월 배당 100만 원 달성"] is None:
            milestones["월 배당 100만 원 달성"] = f"{curr_years_passed:.1f}년 후 ({month_date.strftime('%Y년 %m월')})"
        if current_monthly_dividend_runrate >= 2000000 and milestones["월 배당 200만 원 달성"] is None:
            milestones["월 배당 200만 원 달성"] = f"{curr_years_passed:.1f}년 후 ({month_date.strftime('%Y년 %m월')})"
        if current_monthly_dividend_runrate >= 3000000 and milestones["월 배당 300만 원 달성"] is None:
            milestones["월 배당 300만 원 달성"] = f"{curr_years_passed:.1f}년 후 ({month_date.strftime('%Y년 %m월')})"
        if current_monthly_dividend_runrate >= 5000000 and milestones["월 배당 500만 원 달성"] is None:
            milestones["월 배당 500만 원 달성"] = f"{curr_years_passed:.1f}년 후 ({month_date.strftime('%Y년 %m월')})"

        if curr_wealth >= 100000000 and milestones["총 자산 1억 원 달성"] is None:
            milestones["총 자산 1억 원 달성"] = f"{curr_years_passed:.1f}년 후 ({month_date.strftime('%Y년 %m월')})"
        if curr_wealth >= 300000000 and milestones["총 자산 3억 원 달성"] is None:
            milestones["총 자산 3억 원 달성"] = f"{curr_years_passed:.1f}년 후 ({month_date.strftime('%Y년 %m월')})"
        if curr_wealth >= 500000000 and milestones["총 자산 5억 원 달성"] is None:
            milestones["총 자산 5억 원 달성"] = f"{curr_years_passed:.1f}년 후 ({month_date.strftime('%Y년 %m월')})"
        if curr_wealth >= 1000000000 and milestones["총 자산 10억 원 달성"] is None:
            milestones["총 자산 10억 원 달성"] = f"{curr_years_passed:.1f}년 후 ({month_date.strftime('%Y년 %m월')})"

        monthly_records.append({
            'month': m,
            'date': month_date.strftime('%Y-%m'),
            'wealth': curr_wealth,
            'principal': cum_principal,
            'profit': max(0.0, curr_wealth - cum_principal),
            'cum_dividend': cum_dividend_earned,
            'monthly_dividend': current_monthly_dividend_runrate
        })

        # 연 단위 요약
        if m % 12 == 0:
            y_num = m // 12
            cum_profit = curr_wealth - cum_principal
            yearly_summary.append({
                "경과 기간": f"{y_num}년차",
                "누적 납입 원금": f"{int(cum_principal):,}원",
                "누적 복리 수익": f"{int(cum_profit):,}원",
                "기말 총 평가 자산": f"{int(curr_wealth):,}원",
                "월 예상 배당금": f"월 {int(current_monthly_dividend_runrate):,}원",
                "연간 총 수령 배당금": f"연 {int(current_monthly_dividend_runrate * 12):,}원",
                "총 수익률(%)": f"{(cum_profit / cum_principal * 100):+.1f}%"
            })

    proj_df = pd.DataFrame(monthly_records)

    return {
        'initial_capital': initial_capital,
        'final_wealth': curr_wealth,
        'total_principal': cum_principal,
        'total_profit': curr_wealth - cum_principal,
        'total_dividend_earned': cum_dividend_earned,
        'final_monthly_dividend': curr_wealth * (annual_dividend_yield / 100.0) / 12.0,
        'final_annual_dividend': curr_wealth * (annual_dividend_yield / 100.0),
        'proj_df': proj_df,
        'yearly_summary': yearly_summary,
        'milestones': {k: v if v else "10년 초과 달성" for k, v in milestones.items()}
    }


def run_single_stock_backtest(
    ticker: str,
    period: str = "3y",
    initial_capital: float = 10000000.0,
    stop_loss_pct: float = 0.07,
    take_profit_trail: float = 0.15,
    select_mode: str = ""
) -> dict:
    """
    개별 종목 기술적 SEPA VCP 백테스트 (보조 기능)
    """
    search_ticker = clean_ticker(ticker, select_mode)
    stock_name = NAME_DICT.get(ticker, ticker)

    try:
        tk = yf.Ticker(search_ticker)
        df = tk.history(period=period)
        if df is None or df.empty or len(df) < 60:
            return None
    except Exception:
        return None

    df = df.dropna(subset=['Open', 'High', 'Low', 'Close', 'Volume']).copy().sort_index()
    if len(df) < 60:
        return None

    df['MA20'] = df['Close'].rolling(20, min_periods=5).mean()
    df['MA50'] = df['Close'].rolling(50, min_periods=10).mean()
    df['MA150'] = df['Close'].rolling(150, min_periods=20).mean()
    df['MA200'] = df['Close'].rolling(200, min_periods=30).mean()

    in_position = False
    entry_date = None
    entry_price = 0.0
    shares = 0
    cash = float(initial_capital)
    trade_logs = []

    dates = df.index
    closes = df['Close'].values
    highs = df['High'].values
    lows = df['Low'].values
    ma20s = df['MA20'].values
    ma50s = df['MA50'].values
    ma150s = df['MA150'].values
    ma200s = df['MA200'].values
    portfolio_values = []

    for i in range(50, len(df)):
        dt = dates[i]
        curr_close = float(closes[i])
        curr_high = float(highs[i])
        curr_low = float(lows[i])
        ma20 = float(ma20s[i]) if pd.notna(ma20s[i]) else curr_close
        ma50 = float(ma50s[i]) if pd.notna(ma50s[i]) else curr_close
        ma150 = float(ma150s[i]) if pd.notna(ma150s[i]) else ma50
        ma200 = float(ma200s[i]) if pd.notna(ma200s[i]) else ma150

        if in_position:
            if curr_low <= entry_price * (1.0 - stop_loss_pct):
                proceeds = shares * curr_close * 0.998
                cash += proceeds
                trade_logs.append({
                    '진입일': entry_date.strftime('%Y-%m-%d'),
                    '청산일': dt.strftime('%Y-%m-%d'),
                    '수익률(%)': -round(stop_loss_pct * 100, 2),
                    '청산사유': f"🚨 손절매 (-{stop_loss_pct*100:.0f}%)"
                })
                in_position = False
            elif curr_close < ma20 and (curr_close - entry_price) / entry_price > take_profit_trail:
                proceeds = shares * curr_close * 0.998
                cash += proceeds
                trade_logs.append({
                    '진입일': entry_date.strftime('%Y-%m-%d'),
                    '청산일': dt.strftime('%Y-%m-%d'),
                    '수익률(%)': round(((curr_close - entry_price) / entry_price) * 100, 2),
                    '청산사유': "💰 트레일링 익절"
                })
                in_position = False
        else:
            if curr_close > ma150 and curr_close > ma200 and ma50 > ma150:
                in_position = True
                entry_date = dt
                entry_price = curr_close
                shares = int(cash * 0.95 // (entry_price * 1.002))
                if shares > 0:
                    cash -= shares * entry_price * 1.002

        # 포트폴리오 가치 추적
        current_equity = cash + (shares * curr_close if in_position else 0.0)
        portfolio_values.append(current_equity)

    final_val = cash + (shares * float(closes[-1]) if in_position else 0.0)
    total_ret = ((final_val - initial_capital) / initial_capital) * 100.0

    # 기간 연수 계산 (CAGR)
    total_days = (dates[-1] - dates[50]).days if len(dates) > 50 else 365
    years = total_days / 365.25 if total_days > 0 else 1.0
    cagr = (((final_val / initial_capital) ** (1.0 / years)) - 1.0) * 100.0 if (years > 0 and final_val > 0) else total_ret

    # MDD (최대 낙폭) & Drawdown 시리즈
    eval_dates = dates[50:]
    eq_series = pd.Series(portfolio_values, index=eval_dates) if len(portfolio_values) == len(eval_dates) else pd.Series(portfolio_values)
    eq_peak = eq_series.cummax()
    dd_series = (eq_series - eq_peak) / eq_peak * 100.0
    mdd = abs(float(dd_series.min())) if not dd_series.empty else 0.0

    # 단순보유 곡선
    bh_series = (pd.Series(closes[50:], index=eval_dates) / closes[50]) * initial_capital
    bh_ret = ((closes[-1] - closes[50]) / closes[50]) * 100.0

    equity_df = pd.DataFrame({
        'Strategy': eq_series,
        'BuyHold': bh_series
    })

    # 승률 및 손익비
    wins = [t['수익률(%)'] for t in trade_logs if t['수익률(%)'] > 0]
    losses = [abs(t['수익률(%)']) for t in trade_logs if t['수익률(%)'] < 0]
    total_trades = len(trade_logs)
    win_rate = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0
    avg_win = np.mean(wins) if wins else 0.0
    avg_loss = np.mean(losses) if losses else 1.0
    payoff_ratio = (avg_win / avg_loss) if avg_loss > 0 else 1.0

    return {
        'ticker': ticker,
        'stock_name': stock_name,
        'period': period,
        'total_return_pct': total_ret,
        'buyhold_return_pct': bh_ret,
        'cagr': cagr,
        'mdd': mdd,
        'win_rate': win_rate,
        'payoff_ratio': payoff_ratio,
        'total_trades': total_trades,
        'trade_count': total_trades,
        'equity_df': equity_df,
        'drawdown_series': dd_series,
        'trade_logs': trade_logs
    }

