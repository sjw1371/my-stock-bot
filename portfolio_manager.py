# -*- coding: utf-8 -*-
"""
portfolio_manager.py
- 내 5대 계좌(연금저축, ISA, 일반국내, 일반해외, IRP/코인) 통합 자산 관리 및 실시간 분석 엔진
- Dual-Track 진단: 장기 적립식 리밸런싱 vs 단기 퀀트 스윙(마크 미너비니 VCP 및 -7% 손절)
- 엑셀/CSV 텍스트 파싱 & 웹 직접 편집 듀얼 데이터 파이프라인
"""

import os
import sys
import json
import re
import io
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
from data_fetch import extract_single_stock_df

PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "my_portfolio.json")

# 5대 계좌 기본 권장 목표 비중 (세제 혜택 & 코어 적립 최적화)
DEFAULT_ACCOUNT_TARGETS = {
    "연금저축펀드": 0.40,
    "일반계좌(해외)": 0.25,
    "ISA": 0.20,
    "일반계좌(국내)": 0.10,
    "IRP및코인": 0.05
}

# 6대 자산 팩터 기본 권장 목표 비중 (Dual-Track 밸런스형)
DEFAULT_CATEGORY_TARGETS = {
    "🌱 글로벌 코어 지수": 0.35,
    "💰 고배당 & 인컴": 0.30,
    "🤖 테마 & 미래혁신": 0.15,
    "🚀 퀀트 스윙 & 모멘텀": 0.10,
    "🪙 대체자산 (코인)": 0.02,
    "💵 안전 현금": 0.08
}


def classify_asset_category(ticker: str, name: str) -> str:
    """종목의 티커와 명칭을 기반으로 6대 자산 팩터 자동 분류"""
    ticker_u = str(ticker).upper()
    name_u = str(name).upper()

    if "BTC" in ticker_u or "비트코인" in name_u:
        return "🪙 대체자산 (코인)"
    
    if "현금" in name_u or "CASH" in name_u:
        return "💵 안전 현금"
        
    # 배당 및 인컴
    if any(k in name_u for k in ["배당", "커버드콜", "인컴", "리츠", "인프라", "위클리"]) or ticker_u in [
        "KO", "JNJ", "FAST", "AES", "SCHD", "JEPI", "O", "MO", "402970.KS", "446720.KS", "475720.KS"
    ]:
        return "💰 고배당 & 인컴"
        
    # 글로벌 코어 지수
    if any(k in name_u for k in ["S&P500", "S&P 500", "나스닥100", "NASDAQ", "200", "KOSPI200"]) or ticker_u in [
        "360750.KS", "368590.KS", "102110.KS", "SPY", "QQQ", "VOO", "IVV"
    ]:
        return "🌱 글로벌 코어 지수"

    # 테마 & 미래 혁신
    if any(k in name_u for k in ["로봇", "AI", "인프라", "반도체", "전력", "2차전지", "바이오", "혁신", "휴머노이드"]) or ticker_u in [
        "487230.KS", "0053L0.KS", "0035T0.KS"
    ]:
        return "🤖 테마 & 미래혁신"

    # 퀀트 스윙 및 개별 종목
    return "🚀 퀀트 스윙 & 모멘텀"


def load_portfolio_data() -> dict:
    """포트폴리오 JSON 데이터 로드"""
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "accounts": {},
        "asset_history": [],
        "target_allocation": {
            "accounts": DEFAULT_ACCOUNT_TARGETS,
            "categories": DEFAULT_CATEGORY_TARGETS
        }
    }


def save_portfolio_data(data: dict) -> bool:
    """포트폴리오 JSON 데이터 영구 저장"""
    try:
        with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"포트폴리오 저장 실패: {e}")
        return False


def save_target_allocation(account_targets: dict = None, category_targets: dict = None) -> dict:
    """목표 자산 배분 비중 영구 저장"""
    portfolio_data = load_portfolio_data()
    if "target_allocation" not in portfolio_data:
        portfolio_data["target_allocation"] = {}
    
    if account_targets:
        portfolio_data["target_allocation"]["accounts"] = account_targets
    if category_targets:
        portfolio_data["target_allocation"]["categories"] = category_targets

    save_portfolio_data(portfolio_data)
    return portfolio_data


def fetch_live_exchange_rate() -> float:
    """실시간 USD/KRW 환율 수집"""
    try:
        krw_df = yf.Ticker("KRW=X").history(period="5d")
        if not krw_df.empty and 'Close' in krw_df:
            return float(krw_df['Close'].dropna().iloc[-1])
    except Exception:
        pass
    return 1345.0


def analyze_my_portfolio(portfolio_data: dict) -> dict:
    """
    내 5대 계좌의 실시간 시세를 조회하고, 손익/비중/종합 진단 및 주문표 산출
    """
    exchange_rate = fetch_live_exchange_rate()
    accounts = portfolio_data.get("accounts", {})

    # 1. 모든 고유 티커 수집
    all_tickers = []
    for acc_name, acc_info in accounts.items():
        for h in acc_info.get("holdings", []):
            tk = h.get("ticker", "").strip()
            if tk and tk not in all_tickers:
                all_tickers.append(tk)

    # 2. 실시간 시세 및 지표 패칭
    price_map = {}
    tech_map = {}
    if all_tickers:
        try:
            raw_data = yf.download(all_tickers, period="1y", group_by='ticker', threads=True, progress=False)
            for tk in all_tickers:
                try:
                    df = extract_single_stock_df(raw_data, tk)
                    if not df.empty and len(df) >= 20:
                        close_s = df['Close'].dropna()
                        curr_p = float(close_s.iloc[-1])
                        ma20 = float(close_s.rolling(20, min_periods=5).mean().iloc[-1])
                        ma50 = float(close_s.rolling(50, min_periods=10).mean().iloc[-1])
                        ma200 = float(close_s.rolling(200, min_periods=20).mean().iloc[-1]) if len(close_s) >= 200 else ma50

                        price_map[tk] = curr_p
                        tech_map[tk] = {
                            'curr': curr_p,
                            'ma20': ma20,
                            'ma50': ma50,
                            'ma200': ma200,
                            'above_ma20': curr_p >= ma20,
                            'above_ma50': curr_p >= ma50,
                            'above_ma200': curr_p >= ma200,
                            'disp_20': ((curr_p - ma20) / ma20) * 100 if ma20 > 0 else 0.0
                        }
                    else:
                        price_map[tk] = 0.0
                        tech_map[tk] = {}
                except Exception:
                    price_map[tk] = 0.0
                    tech_map[tk] = {}
        except Exception:
            for tk in all_tickers:
                price_map[tk] = 0.0
                tech_map[tk] = {}

    # 3. 계좌별 평가 및 Dual-Track 건강검진
    evaluated_accounts = {}
    total_net_worth = 0.0
    total_net_worth = 0.0
    total_cost_basis = 0.0
    total_cash_krw = 0.0
    total_annual_dividend_krw = 0.0

    all_holding_rows = []
    prescriptions = []
    order_suggestions = []

    for acc_name, acc_info in accounts.items():
        acc_type = acc_info.get("type", "장기적립")
        cash_krw = float(acc_info.get("cash_krw", 0))
        cash_usd = float(acc_info.get("cash_usd", 0))
        total_acc_cash_krw = cash_krw + (cash_usd * exchange_rate)

        acc_eval_stock_krw = 0.0
        acc_cost_stock_krw = 0.0
        acc_annual_div_krw = 0.0
        holding_details = []

        is_usd_account = ("해외" in acc_name)

        for h in acc_info.get("holdings", []):
            tk = h.get("ticker", "")
            name = h.get("name", tk)
            shares = float(h.get("shares", 0))
            avg_p = float(h.get("avg_price", 0))
            div_yield = float(h.get("dividend_yield", 0.0))
            target_w = float(h.get("target_weight", 0.1))

            live_p = price_map.get(tk, 0.0)
            if live_p <= 0:
                live_p = avg_p  # 시세 미제공 시 매수가 대체

            # 금액 계산 (원화 환산)
            if is_usd_account:
                eval_val_krw = shares * live_p * exchange_rate
                cost_val_krw = shares * avg_p * exchange_rate
                eval_val_orig = shares * live_p
                cost_val_orig = shares * avg_p
            else:
                eval_val_krw = shares * live_p
                cost_val_krw = shares * avg_p
                eval_val_orig = eval_val_krw
                cost_val_orig = cost_val_krw

            pnl_krw = eval_val_krw - cost_val_krw
            return_pct = ((live_p - avg_p) / avg_p) * 100 if avg_p > 0 else 0.0

            # 배당금 계산 (평가액 기준 연간 및 월간 배당금)
            annual_div_krw = eval_val_krw * (div_yield / 100.0)
            monthly_div_krw = annual_div_krw / 12.0
            acc_annual_div_krw += annual_div_krw

            acc_eval_stock_krw += eval_val_krw
            acc_cost_stock_krw += cost_val_krw

            # ------------------------------------------------------------------
            # 🩺 Dual-Track AI 종목 진단 로직
            # ------------------------------------------------------------------
            tech = tech_map.get(tk, {})
            above_20 = tech.get('above_ma20', True)
            above_50 = tech.get('above_ma50', True)
            above_200 = tech.get('above_ma200', True)

            action_badge = "홀딩"
            action_desc = ""
            action_color = "green"

            if acc_type == "장기적립":
                # 장기 적립식 룰 (손절 절대 금지, 200일선 우상향 적립)
                if above_200:
                    action_badge = "🟢 지속 적립 (코어 우상향)"
                    action_desc = "200일선 위 장기 우상향 추세 완벽. 하락 시에도 적립식 매수 유지."
                    action_color = "green"
                else:
                    action_badge = "🟡 저가 분할매수 기회"
                    action_desc = "단기 조정 구간. 장기 코어 자산이므로 손절하지 않고 비중 유지."
                    action_color = "orange"

            else:
                # 단기 퀀트 스윙 룰 (마크 미너비니 SEPA & -7% 칼손절)
                if return_pct <= -7.0:
                    action_badge = "🚨 손절 권고 (-7% 도달)"
                    action_desc = f"진입가 대비 {return_pct:.1f}% 하락. 미너비니 원칙에 따라 리스크 차단 손절 권고."
                    action_color = "red"
                elif not above_50 and return_pct < 0:
                    action_badge = "⚠️ 리스크 축소 (50일선 이탈)"
                    action_desc = "중기 추세선(50일선) 하향 이탈. 반등 시 비중 축소 권고."
                    action_color = "orange"
                elif above_20 and return_pct >= 10.0:
                    action_badge = "💰 트레일링 익절 대기"
                    action_desc = f"+{return_pct:.1f}% 수익 중. 20일선 지지 시 끝까지 홀딩."
                    action_color = "blue"
                elif above_20:
                    action_badge = "📈 강력 보유 (추세 안정)"
                    action_desc = "20일선 위 안정적 상승 추세 유지 중."
                    action_color = "green"
                else:
                    action_badge = "⏳ 관망 (20일선 지지 체크)"
                    action_desc = "단기 눌림목 구간. 20일선 지지 여부 관망."
                    action_color = "gray"

            h_row = {
                '계좌': acc_name,
                '계좌유형': acc_type,
                '종목명': name,
                '티커': tk,
                '수량': shares,
                '매수단가': avg_p,
                '현재가': live_p,
                '수익률(%)': return_pct,
                '평가손익(원)': pnl_krw,
                '평가금액(원)': eval_val_krw,
                '매수금액(원)': cost_val_krw,
                '배당수익률(%)': div_yield,
                '연간예상배당(원)': annual_div_krw,
                '월환산배당(원)': monthly_div_krw,
                '목표비중': target_w,
                '진단상태': action_badge,
                '처방내용': action_desc,
                '진단색상': action_color,
                '통화': "USD" if is_usd_account else "KRW"
            }
            holding_details.append(h_row)
            all_holding_rows.append(h_row)

            prescriptions.append({
                '계좌': acc_name,
                '종목명': name,
                '수익률': f"{return_pct:+.1f}%",
                '진단': action_badge,
                '처방': action_desc
            })

        acc_total_eval_krw = acc_eval_stock_krw + total_acc_cash_krw
        acc_total_cost_krw = acc_cost_stock_krw + total_acc_cash_krw
        acc_pnl_krw = acc_total_eval_krw - acc_total_cost_krw
        acc_return_pct = (acc_pnl_krw / acc_total_cost_krw) * 100 if acc_total_cost_krw > 0 else 0.0

        evaluated_accounts[acc_name] = {
            'type': acc_type,
            'cash_krw': cash_krw,
            'cash_usd': cash_usd,
            'total_cash_krw': total_acc_cash_krw,
            'stock_eval_krw': acc_eval_stock_krw,
            'total_eval_krw': acc_total_eval_krw,
            'total_cost_krw': acc_total_cost_krw,
            'pnl_krw': acc_pnl_krw,
            'return_pct': acc_return_pct,
            'annual_dividend_krw': acc_annual_div_krw,
            'monthly_dividend_krw': acc_annual_div_krw / 12.0,
            'dividend_yield_pct': (acc_annual_div_krw / acc_total_eval_krw * 100.0) if acc_total_eval_krw > 0 else 0.0,
            'holdings': holding_details
        }

        total_net_worth += acc_total_eval_krw
        total_cost_basis += acc_total_cost_krw
        total_cash_krw += total_acc_cash_krw
        total_annual_dividend_krw += acc_annual_div_krw

    # 4. 내 잔고 기반 맞춤형 주문표 (Rebalancing & Action Suggestions) 산출
    for acc_name, acc_eval in evaluated_accounts.items():
        acc_type = acc_eval['type']
        acc_total_val = acc_eval['total_eval_krw']
        acc_cash = acc_eval['total_cash_krw']

        if acc_type == "장기적립":
            for h in acc_eval['holdings']:
                curr_val = h['평가금액(원)']
                curr_w = curr_val / acc_total_val if acc_total_val > 0 else 0
                target_w = h['목표비중']
                diff_w = target_w - curr_w

                if diff_w > 0.03 and acc_cash >= 50000:
                    needed_krw = min(acc_cash * 0.5, acc_total_val * diff_w)
                    price_krw = h['현재가']
                    buy_qty = int(needed_krw // price_krw) if price_krw > 0 else 0
                    if buy_qty > 0:
                        order_suggestions.append({
                            '계좌': acc_name,
                            '구분': '🌱 장기 정기 적립',
                            '종목명': h['종목명'],
                            '티커': h['티커'],
                            '현재가': f"{int(price_krw):,}원",
                            '추천주문': f"{buy_qty}주 추가 매수",
                            '주문금액': f"{int(buy_qty * price_krw):,}원",
                            '이유': f"목표 비중({target_w*100:.0f}%) 대비 부족({curr_w*100:.1f}%)"
                        })

        elif acc_type == "단기퀀트스윙":
            for h in acc_eval['holdings']:
                if h['수익률(%)'] <= -7.0:
                    order_suggestions.append({
                        '계좌': acc_name,
                        '구분': '🚨 리스크 손절 청산',
                        '종목명': h['종목명'],
                        '티커': h['티커'],
                        '현재가': f"${h['현재가']:.2f}",
                        '추천주문': f"{int(h['수량'])}주 전량 매도 (손절)",
                        '주문금액': f"약 {int(h['평가금액(원)']):,}원 회수",
                        '이유': f"손절 기준(-7%) 도달 ({h['수익률(%)']:.1f}%) ➔ 현금 확보"
                    })

    total_pnl_krw = total_net_worth - total_cost_basis
    total_return_pct = (total_pnl_krw / total_cost_basis) * 100 if total_cost_basis > 0 else 0.0
    total_monthly_dividend_krw = total_annual_dividend_krw / 12.0
    portfolio_dividend_yield = (total_annual_dividend_krw / total_net_worth * 100.0) if total_net_worth > 0 else 0.0

    return {
        'exchange_rate': exchange_rate,
        'total_net_worth': total_net_worth,
        'total_cost_basis': total_cost_basis,
        'total_pnl_krw': total_pnl_krw,
        'total_return_pct': total_return_pct,
        'total_cash_krw': total_cash_krw,
        'total_annual_dividend_krw': total_annual_dividend_krw,
        'total_monthly_dividend_krw': total_monthly_dividend_krw,
        'portfolio_dividend_yield': portfolio_dividend_yield,
        'accounts': evaluated_accounts,
        'all_holdings_df': pd.DataFrame(all_holding_rows),
        'prescriptions': prescriptions,
        'order_suggestions': pd.DataFrame(order_suggestions),
        'asset_history': portfolio_data.get("asset_history", [])
    }


def parse_pasted_csv_text(csv_text: str) -> dict:
    """
    사용자가 복사해서 붙여넣은 엑셀/CSV 텍스트를 파싱하여 포트폴리오 JSON 구조로 자동 변환
    """
    portfolio_data = load_portfolio_data()
    accounts = portfolio_data.get("accounts", {})

    lines = csv_text.strip().split('\n')
    current_account = None

    for line in lines:
        parts = [p.strip() for p in line.split(',')]
        if len(parts) < 2:
            continue

        first_col = parts[0].replace('"', '')
        
        if "연금저축" in first_col:
            current_account = "연금저축펀드"
        elif "일반계좌" in first_col and "해외" in first_col:
            current_account = "일반계좌(해외)"
        elif "일반계좌" in first_col and "국내" in first_col:
            current_account = "일반계좌(국내)"
        elif "ISA" in first_col:
            current_account = "ISA"
        elif "IRP" in first_col:
            current_account = "IRP및코인"

        # 종목 행 파싱
        if current_account and len(parts) >= 6:
            name = parts[1] if parts[1] else parts[0]
            if name in ["종목명", "계좌구분", "계", "합계", ""]:
                continue

            # 현금 행
            if "현금" in name:
                try:
                    val_str = re.sub(r'[^\d.]', '', parts[4] if len(parts) > 4 and parts[4] else parts[5])
                    if val_str:
                        if "해외" in current_account:
                            accounts[current_account]["cash_usd"] = float(val_str)
                        else:
                            accounts[current_account]["cash_krw"] = float(val_str)
                except Exception:
                    pass
                continue

            # 주식/ETF 행
            try:
                tk = parts[2].strip() if len(parts) > 2 and parts[2] else ""
                curr_p = float(re.sub(r'[^\d.]', '', parts[3])) if len(parts) > 3 and parts[3] else 0.0
                shares = float(re.sub(r'[^\d.]', '', parts[4])) if len(parts) > 4 and parts[4] else 0.0

                if tk and shares > 0:
                    # 기존 종목 업데이트 또는 추가
                    found = False
                    for h in accounts[current_account].get("holdings", []):
                        if h.get("ticker") == tk:
                            h["shares"] = shares
                            found = True
                            break
                    if not found:
                        accounts[current_account]["holdings"].append({
                            "ticker": tk,
                            "name": name,
                            "shares": shares,
                            "avg_price": curr_p,
                            "target_weight": 0.10
                        })
            except Exception:
                pass

    portfolio_data["accounts"] = accounts
    save_portfolio_data(portfolio_data)
    return portfolio_data


def add_daily_asset_snapshot(custom_date: str = "", custom_cost: float = 0.0) -> dict:
    """오늘(또는 지정일)의 총 평가액과 원금을 자산 히스토리에 스냅샷으로 영구 기록"""
    portfolio_data = load_portfolio_data()
    analysis = analyze_my_portfolio(portfolio_data)

    dt_str = custom_date if custom_date else datetime.now().strftime("%Y-%m-%d")
    equity_val = round(analysis['total_net_worth'], 0)
    cost_val = custom_cost if custom_cost > 0 else round(analysis['total_cost_basis'], 0)
    ret_pct = round(((equity_val - cost_val) / cost_val) * 100, 2) if cost_val > 0 else 0.0

    history = portfolio_data.get("asset_history", [])
    
    # 동일 날짜가 있으면 덮어쓰기, 없으면 신규 추가
    found = False
    for item in history:
        if item.get("date") == dt_str:
            item["equity"] = equity_val
            item["cost"] = cost_val
            item["return_pct"] = ret_pct
            found = True
            break
    if not found:
        history.append({
            "date": dt_str,
            "equity": equity_val,
            "cost": cost_val,
            "return_pct": ret_pct
        })

    # 날짜순 정렬
    history = sorted(history, key=lambda x: x.get("date", ""))
    portfolio_data["asset_history"] = history
    save_portfolio_data(portfolio_data)
    return portfolio_data

