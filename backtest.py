# -*- coding: utf-8 -*-
"""
backtest.py
- JTI 정밀 마크 미너비니 VCP & SEPA 트렌드 과거 백테스팅 시뮬레이션 엔진
- -7% 안전 버퍼 손절매, 트레일링 익절, 50일선 추세 완주
"""

import sys
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

# Windows UTF-8 지원
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from data_fetch import clean_ticker, NAME_DICT


def run_single_stock_backtest(
    ticker: str,
    period: str = "3y",
    initial_capital: float = 10000000.0,
    stop_loss_pct: float = 0.07,      # -7% 안전 버퍼 손절
    take_profit_trail: float = 0.15,  # 15% 이상 상승 후 20일선 이탈 시 트레일링 익절
    select_mode: str = ""
) -> dict:
    """
    개별 종목에 대한 정밀 마크 미너비니 VCP & SEPA 돌파 전략 백테스팅
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

    # 기술적 지표 계산
    df['MA20'] = df['Close'].rolling(20, min_periods=5).mean()
    df['MA50'] = df['Close'].rolling(50, min_periods=10).mean()
    df['MA150'] = df['Close'].rolling(150, min_periods=20).mean()
    df['MA200'] = df['Close'].rolling(200, min_periods=30).mean()
    df['Vol_MA20'] = df['Volume'].rolling(20, min_periods=5).mean()
    df['Vol_MA50'] = df['Volume'].rolling(50, min_periods=10).mean()
    df['High_52wk'] = df['High'].rolling(min(252, len(df)), min_periods=30).max()

    in_position = False
    entry_date = None
    entry_price = 0.0
    shares = 0
    cash = float(initial_capital)
    portfolio_values = []
    trade_logs = []
    highest_price_during_trade = 0.0

    dates = df.index
    closes = df['Close'].values
    opens = df['Open'].values
    highs = df['High'].values
    lows = df['Low'].values
    volumes = df['Volume'].values
    ma20s = df['MA20'].values
    ma50s = df['MA50'].values
    ma150s = df['MA150'].values
    ma200s = df['MA200'].values
    vol_ma20s = df['Vol_MA20'].values
    vol_ma50s = df['Vol_MA50'].values
    high_52wks = df['High_52wk'].values

    start_idx = 50
    first_close = closes[start_idx]

    for i in range(start_idx, len(df)):
        dt = dates[i]
        curr_close = float(closes[i])
        curr_open = float(opens[i])
        curr_high = float(highs[i])
        curr_low = float(lows[i])
        curr_vol = float(volumes[i])

        ma20 = float(ma20s[i]) if pd.notna(ma20s[i]) else curr_close
        ma50 = float(ma50s[i]) if pd.notna(ma50s[i]) else curr_close
        ma150 = float(ma150s[i]) if pd.notna(ma150s[i]) else ma50
        ma200 = float(ma200s[i]) if pd.notna(ma200s[i]) else ma150
        vol_ma20 = float(vol_ma20s[i]) if (pd.notna(vol_ma20s[i]) and vol_ma20s[i] > 0) else 1.0
        vol_ma50 = float(vol_ma50s[i]) if (pd.notna(vol_ma50s[i]) and vol_ma50s[i] > 0) else vol_ma20
        h_52wk = float(high_52wks[i]) if pd.notna(high_52wks[i]) else curr_close

        # 1. 포지션 보유 중인 경우 -> 매도(손절/익절/추세이탈) 체크
        if in_position:
            highest_price_during_trade = max(highest_price_during_trade, curr_high)
            pnl_pct = (curr_close - entry_price) / entry_price if entry_price > 0 else 0
            max_gain_pct = (highest_price_during_trade - entry_price) / entry_price if entry_price > 0 else 0

            sell_triggered = False
            sell_reason = ""
            exit_price = curr_close

            # A. 안전 버퍼 손절선 도달 (-stop_loss_pct 이하)
            if curr_low <= entry_price * (1.0 - stop_loss_pct):
                sell_triggered = True
                sell_reason = f"🚨 손절매 (-{stop_loss_pct*100:.1f}%)"
                exit_price = min(curr_open, entry_price * (1.0 - stop_loss_pct))

            # B. 트레일링 익절 (15% 이상 상승 후 20일선 하향 이탈)
            elif max_gain_pct >= take_profit_trail and curr_close < ma20:
                sell_triggered = True
                sell_reason = "💰 트레일링 익절 (20일선 이탈)"
                exit_price = curr_close

            # C. 주요 중기 추세선(50일선) 하향 이탈
            elif curr_close < ma50 and pnl_pct < 0.05:
                sell_triggered = True
                sell_reason = "📉 50일 이평선 하향 이탈"
                exit_price = curr_close

            if sell_triggered:
                proceeds = shares * exit_price * 0.998
                cash += proceeds
                trade_pnl = proceeds - (shares * entry_price * 1.002)
                trade_return_pct = ((exit_price - entry_price) / entry_price) * 100

                trade_logs.append({
                    '진입일': entry_date.strftime('%Y-%m-%d'),
                    '청산일': dt.strftime('%Y-%m-%d'),
                    '진입가': round(entry_price, 2),
                    '청산가': round(exit_price, 2),
                    '수익률(%)': round(trade_return_pct, 2),
                    '손익금(원/$)': round(trade_pnl, 0),
                    '보유일수': (dt - entry_date).days,
                    '청산사유': sell_reason
                })

                in_position = False
                shares = 0
                entry_price = 0.0

        # 2. 포지션 미보유 시 -> 정밀 VCP 피벗 돌파 매수 체크
        if not in_position and i < len(df) - 1:
            # Stage 2 대세 상승 추세
            stage2_cond = (curr_close > ma50) and (ma50 >= ma150) and (curr_close >= h_52wk * 0.75)

            # 다중 진폭 수축
            if i >= 35:
                d1 = (np.max(highs[i-35:i-15]) - np.min(lows[i-35:i-15])) / curr_close
                d2 = (np.max(highs[i-15:i-4]) - np.min(lows[i-15:i-4])) / curr_close
                d3 = (np.max(highs[i-4:i]) - np.min(lows[i-4:i])) / curr_close
                is_vcp_contraction = (d3 < d2 and d2 <= d1 * 1.15) or (d3 <= 0.055 and d2 < d1)
            else:
                is_vcp_contraction = False

            # 거래량 고갈
            recent_vol_avg = np.mean(volumes[max(0, i-3):i]) if i >= 3 else curr_vol
            is_dry_up = (recent_vol_avg <= vol_ma50 * 0.85)

            # 피벗 돌파 (최근 10일 저항선)
            pivot_price = np.max(highs[max(0, i-10):i]) if i >= 10 else curr_close
            vol_ratio = curr_vol / vol_ma20 if vol_ma20 > 0 else 1.0
            is_pivot_breakout = (curr_close >= pivot_price * 0.995) and (vol_ratio >= 1.20)

            # 피벗 이격도 0 ~ 6%
            disp_20 = ((curr_close - ma20) / ma20) * 100 if ma20 > 0 else 0.0
            pivot_dist_ok = (0.0 <= disp_20 <= 6.0)

            buy_signal = stage2_cond and pivot_dist_ok and (
                is_pivot_breakout or (is_vcp_contraction and (is_dry_up or vol_ratio >= 1.25))
            )

            if buy_signal:
                in_position = True
                entry_date = dt
                entry_price = curr_close
                highest_price_during_trade = curr_close

                invest_amt = cash * 0.95
                shares = int(invest_amt // (entry_price * 1.002))
                if shares > 0:
                    cash -= shares * entry_price * 1.002

        current_equity = cash + (shares * curr_close if in_position else 0)
        portfolio_values.append({
            'Date': dt,
            'Strategy': current_equity,
            'BuyHold': (initial_capital / first_close) * curr_close,
            'Close': curr_close
        })

    # 잔여 포지션 청산
    if in_position:
        final_close = float(closes[-1])
        proceeds = shares * final_close * 0.998
        cash += proceeds
        trade_pnl = proceeds - (shares * entry_price * 1.002)
        trade_return_pct = ((final_close - entry_price) / entry_price) * 100

        trade_logs.append({
            '진입일': entry_date.strftime('%Y-%m-%d'),
            '청산일': dates[-1].strftime('%Y-%m-%d'),
            '진입가': round(entry_price, 2),
            '청산가': round(final_close, 2),
            '수익률(%)': round(trade_return_pct, 2),
            '손익금(원/$)': round(trade_pnl, 0),
            '보유일수': (dates[-1] - entry_date).days,
            '청산사유': "🏁 백테스트 종료 청산"
        })

    equity_df = pd.DataFrame(portfolio_values).set_index('Date')
    trades_df = pd.DataFrame(trade_logs)

    final_equity = float(equity_df['Strategy'].iloc[-1])
    total_return_pct = ((final_equity - initial_capital) / initial_capital) * 100
    buyhold_final = float(equity_df['BuyHold'].iloc[-1])
    buyhold_return_pct = ((buyhold_final - initial_capital) / initial_capital) * 100

    total_days = (dates[-1] - dates[start_idx]).days
    years = max(total_days / 365.25, 0.5)
    cagr = ((final_equity / initial_capital) ** (1.0 / years) - 1.0) * 100 if final_equity > 0 else -100.0

    roll_max = equity_df['Strategy'].cummax()
    drawdown = (equity_df['Strategy'] - roll_max) / roll_max
    mdd = abs(float(drawdown.min())) * 100

    if not trades_df.empty:
        total_trades = len(trades_df)
        winning_trades = trades_df[trades_df['수익률(%)'] > 0]
        losing_trades = trades_df[trades_df['수익률(%)'] <= 0]

        win_rate = (len(winning_trades) / total_trades) * 100
        avg_win = float(winning_trades['수익률(%)'].mean()) if not winning_trades.empty else 0.0
        avg_loss = abs(float(losing_trades['수익률(%)'].mean())) if not losing_trades.empty else 0.0
        payoff_ratio = (avg_win / avg_loss) if avg_loss > 0 else 2.0
        profit_factor = (winning_trades['수익률(%)'].sum() / abs(losing_trades['수익률(%)'].sum())) if not losing_trades.empty and losing_trades['수익률(%)'].sum() != 0 else 2.5
        avg_holding_days = float(trades_df['보유일수'].mean())
    else:
        total_trades = 0
        win_rate = 0.0
        avg_win = 0.0
        avg_loss = 0.0
        payoff_ratio = 0.0
        profit_factor = 0.0
        avg_holding_days = 0.0

    return {
        'ticker': ticker,
        'stock_name': stock_name,
        'period': period,
        'initial_capital': initial_capital,
        'final_equity': final_equity,
        'total_return_pct': total_return_pct,
        'buyhold_return_pct': buyhold_return_pct,
        'cagr': cagr,
        'mdd': mdd,
        'total_trades': total_trades,
        'win_rate': win_rate,
        'payoff_ratio': payoff_ratio,
        'profit_factor': profit_factor,
        'avg_holding_days': avg_holding_days,
        'equity_df': equity_df,
        'trades_df': trades_df,
        'drawdown_series': drawdown * 100
    }
