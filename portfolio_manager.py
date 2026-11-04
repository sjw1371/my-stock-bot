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

# 6대 자산 팩터별 퀀트 프로파일 (기대수익률, 변동성, 배당률, 위기 낙폭)
FACTOR_PROFILES = {
    "🌱 글로벌 코어 지수": {
        "expected_cagr": 0.105,   # 10.5%
        "volatility": 0.160,      # 16.0%
        "dividend_yield": 0.013,  # 1.3%
        "crisis_2008": -0.38,     # -38%
        "crisis_2020": -0.34,     # -34%
        "crisis_2022": -0.19,     # -19%
        "best_account": "연금저축 / ISA (과세이연/비과세)",
        "tax_reason": "장기 복리 해외 지수 ETF는 매매차익 및 배당소득 과세이연 혜택 극대화"
    },
    "💰 고배당 & 인컴": {
        "expected_cagr": 0.085,   # 8.5%
        "volatility": 0.120,      # 12.0%
        "dividend_yield": 0.042,  # 4.2%
        "crisis_2008": -0.26,
        "crisis_2020": -0.22,
        "crisis_2022": -0.10,
        "best_account": "ISA / 연금저축 (배당세 15.4% 비과세/이연)",
        "tax_reason": "고배당 인컴 자산은 금융소득종합과세 회피 및 15.4% 배당소득세 절세 필수"
    },
    "🤖 테마 & 미래혁신": {
        "expected_cagr": 0.145,   # 14.5%
        "volatility": 0.260,      # 26.0%
        "dividend_yield": 0.005,  # 0.5%
        "crisis_2008": -0.48,
        "crisis_2020": -0.32,
        "crisis_2022": -0.35,
        "best_account": "ISA / 일반계좌(해외)",
        "tax_reason": "시세차익 중심 고성장 자산으로 ISA 비과세 또는 해외계좌 양도세 기본공제 활용"
    },
    "🚀 퀀트 스윙 & 모멘텀": {
        "expected_cagr": 0.160,   # 16.0% (-7% 손절 적용 시)
        "volatility": 0.200,      # 20.0%
        "dividend_yield": 0.008,  # 0.8%
        "crisis_2008": -0.18,     # 손절 후 현금 대피
        "crisis_2020": -0.14,
        "crisis_2022": -0.12,
        "best_account": "일반계좌(해외/국내)",
        "tax_reason": "단기 잦은 매매와 손절이 발생하는 스윙은 일반계좌에서 매매 손익 상계 활용"
    },
    "🪙 대체자산 (코인)": {
        "expected_cagr": 0.220,   # 22.0%
        "volatility": 0.550,      # 55.0%
        "dividend_yield": 0.0,
        "crisis_2008": -0.60,
        "crisis_2020": -0.50,
        "crisis_2022": -0.65,
        "best_account": "IRP및코인 (전용 지갑)",
        "tax_reason": "포트폴리오 2~5% 미만 소액으로 인플레이션 헤지 및 초과수익 추구"
    },
    "💵 안전 현금": {
        "expected_cagr": 0.035,   # 3.5% (CMA / 파킹)
        "volatility": 0.002,
        "dividend_yield": 0.035,
        "crisis_2008": 0.0,
        "crisis_2020": 0.0,
        "crisis_2022": 0.0,
        "best_account": "모든 계좌의 예수금 / CMA",
        "tax_reason": "급락장 저가 분할매수를 위한 필수 유동성 탄약 버퍼"
    }
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

            # 6대 자산 팩터 카테고리 분류
            asset_cat = classify_asset_category(tk, name)

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
                '자산분류': asset_cat,
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
        
        # 순투입원금(순입금액) 기반 원금 정확 계산 (미입력 시 주식매수가+현금 fallback)
        acc_net_deposit = float(acc_info.get("net_deposit", 0.0))
        if acc_net_deposit > 0:
            acc_total_cost_krw = acc_net_deposit
            acc_cost_type = "순입금액 기준 (정확)"
        else:
            acc_total_cost_krw = acc_cost_stock_krw + total_acc_cash_krw
            acc_cost_type = "보유주식 매수원가+현금"

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
            'cost_type': acc_cost_type,
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

    # --------------------------------------------------------------------------
    # 4. 6대 자산 팩터별 카테고리 집계 & 목표치 대비 분석
    # --------------------------------------------------------------------------
    target_alloc = portfolio_data.get("target_allocation", {})
    target_accounts = target_alloc.get("accounts", DEFAULT_ACCOUNT_TARGETS)
    target_categories = target_alloc.get("categories", DEFAULT_CATEGORY_TARGETS)

    categories_data = {
        "🌱 글로벌 코어 지수": {"eval_krw": 0.0, "cost_krw": 0.0, "annual_div_krw": 0.0, "holdings": []},
        "💰 고배당 & 인컴": {"eval_krw": 0.0, "cost_krw": 0.0, "annual_div_krw": 0.0, "holdings": []},
        "🤖 테마 & 미래혁신": {"eval_krw": 0.0, "cost_krw": 0.0, "annual_div_krw": 0.0, "holdings": []},
        "🚀 퀀트 스윙 & 모멘텀": {"eval_krw": 0.0, "cost_krw": 0.0, "annual_div_krw": 0.0, "holdings": []},
        "🪙 대체자산 (코인)": {"eval_krw": 0.0, "cost_krw": 0.0, "annual_div_krw": 0.0, "holdings": []},
        "💵 안전 현금": {"eval_krw": total_cash_krw, "cost_krw": total_cash_krw, "annual_div_krw": 0.0, "holdings": []}
    }

    for h in all_holding_rows:
        cat = h.get("자산분류", "🚀 퀀트 스윙 & 모멘텀")
        if cat in categories_data:
            categories_data[cat]["eval_krw"] += h["평가금액(원)"]
            categories_data[cat]["cost_krw"] += h["매수금액(원)"]
            categories_data[cat]["annual_div_krw"] += h["연간예상배당(원)"]
            categories_data[cat]["holdings"].append(h)

    # 5대 계좌별 현수준 vs 목표 비교 리스트 (도넛 차트 옆 비주얼 카드용)
    account_comparison = []
    for acc_name, acc_eval in evaluated_accounts.items():
        curr_w = (acc_eval['total_eval_krw'] / total_net_worth * 100.0) if total_net_worth > 0 else 0.0
        target_w = float(target_accounts.get(acc_name, DEFAULT_ACCOUNT_TARGETS.get(acc_name, 0.20))) * 100.0
        gap = curr_w - target_w
        
        if abs(gap) <= 2.0:
            status_badge = "● 적정 비중 (유지)"
            status_color = "#10B981"  # 초록
            status_tag = "normal"
        elif gap < -2.0:
            status_badge = f"▲ {abs(gap):.1f}% 부족 (적립 권장)"
            status_color = "#2563EB"  # 파랑
            status_tag = "under"
        else:
            status_badge = f"▼ {gap:.1f}% 초과 (리밸런싱)"
            status_color = "#F59E0B"  # 주황
            status_tag = "over"

        account_comparison.append({
            "account": acc_name,
            "type": acc_eval['type'],
            "eval_krw": acc_eval['total_eval_krw'],
            "cost_krw": acc_eval['total_cost_krw'],
            "pnl_krw": acc_eval['pnl_krw'],
            "return_pct": acc_eval['return_pct'],
            "cost_type": acc_eval.get('cost_type', "순입금액"),
            "current_weight": curr_w,
            "target_weight": target_w,
            "gap": gap,
            "status_badge": status_badge,
            "status_color": status_color,
            "status_tag": status_tag
        })

    # 6대 자산군별 현수준 vs 목표 비교 리스트 (자산 배분 탭용)
    category_comparison = []
    for cat_name, cat_info in categories_data.items():
        curr_w = (cat_info['eval_krw'] / total_net_worth * 100.0) if total_net_worth > 0 else 0.0
        target_w = float(target_categories.get(cat_name, DEFAULT_CATEGORY_TARGETS.get(cat_name, 0.15))) * 100.0
        gap = curr_w - target_w
        cat_div_krw = cat_info['annual_div_krw']
        target_eval_krw = total_net_worth * (target_w / 100.0)
        rebalance_krw = target_eval_krw - cat_info['eval_krw']

        if abs(gap) <= 2.0:
            status_badge = "● 적정 비중 (유지)"
            status_color = "#10B981"
            action_advice = "현 비중 유지"
        elif gap < -2.0:
            status_badge = f"▲ {abs(gap):.1f}% 부족 (확대 필요)"
            status_color = "#2563EB"
            action_advice = f"+약 {int(abs(rebalance_krw)):,}원 추가 매수/적립"
        else:
            status_badge = f"▼ {gap:.1f}% 초과 (비중 축소)"
            status_color = "#F59E0B"
            action_advice = f"-약 {int(rebalance_krw):,}원 이익실현/축소"

        category_comparison.append({
            "category": cat_name,
            "eval_krw": cat_info['eval_krw'],
            "cost_krw": cat_info['cost_krw'],
            "current_weight": curr_w,
            "target_weight": target_w,
            "target_eval_krw": target_eval_krw,
            "rebalance_krw": rebalance_krw,
            "gap": gap,
            "annual_div_krw": cat_div_krw,
            "holdings_count": len(cat_info['holdings']),
            "status_badge": status_badge,
            "status_color": status_color,
            "action_advice": action_advice
        })

    # 5. 내 잔고 기반 맞춤형 주문표 (Rebalancing & Action Suggestions) 산출
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
        'asset_history': portfolio_data.get("asset_history", []),
        'account_comparison': account_comparison,
        'category_comparison': category_comparison,
        'categories_data': categories_data,
        'target_accounts': target_accounts,
        'target_categories': target_categories
    }


def calculate_portfolio_quant_metrics(cat_weights_pct: dict, total_equity: float) -> dict:
    """
    6대 자산 팩터 비중(%)과 총자산을 기반으로
    기대수익률(CAGR), 포트폴리오 변동성, 샤프지수, 배당 스트림, 과거 위기 낙폭 시뮬레이션 및 밸런스 점수 산출
    """
    tot_w = sum(cat_weights_pct.values())
    if tot_w <= 0:
        norm_w = {k: 1.0 / len(FACTOR_PROFILES) for k in FACTOR_PROFILES}
    else:
        norm_w = {k: cat_weights_pct.get(k, 0.0) / tot_w for k in FACTOR_PROFILES}

    cagr = sum(norm_w[k] * FACTOR_PROFILES[k]['expected_cagr'] for k in FACTOR_PROFILES)
    weighted_vol = sum(norm_w[k] * FACTOR_PROFILES[k]['volatility'] for k in FACTOR_PROFILES)
    portfolio_vol = weighted_vol * 0.78  # 상관관계 분산 감소 효과 반영

    div_yield = sum(norm_w[k] * FACTOR_PROFILES[k]['dividend_yield'] for k in FACTOR_PROFILES)
    annual_div = total_equity * div_yield
    monthly_div = annual_div / 12.0

    rf = 0.035  # 무위험 수익률 3.5%
    sharpe = (cagr - rf) / portfolio_vol if portfolio_vol > 0 else 0.0

    stress_2008 = sum(norm_w[k] * FACTOR_PROFILES[k]['crisis_2008'] for k in FACTOR_PROFILES)
    stress_2020 = sum(norm_w[k] * FACTOR_PROFILES[k]['crisis_2020'] for k in FACTOR_PROFILES)
    stress_2022 = sum(norm_w[k] * FACTOR_PROFILES[k]['crisis_2022'] for k in FACTOR_PROFILES)

    # 밸런스 지수 계산 (HHI 기반 분산도 40점 + 현금완충 20점 + 배당안정성 20점 + 변동성방어 20점 = 100점 만점)
    hhi = sum((w ** 2) for w in norm_w.values())
    diversification_score = max(0.0, min(40.0, (1.0 - hhi) / (1.0 - (1.0 / len(FACTOR_PROFILES))) * 40.0))
    cash_w = norm_w.get('💵 안전 현금', 0.0)
    cash_score = 20.0 if 0.05 <= cash_w <= 0.15 else max(5.0, 20.0 - abs(cash_w - 0.08) * 100.0)
    div_score = min(20.0, (div_yield / 0.04) * 20.0)
    vol_score = max(5.0, min(20.0, (0.25 - portfolio_vol) / 0.15 * 20.0))
    health_score = int(round(diversification_score + cash_score + div_score + vol_score))

    growth_ratio = int(round((norm_w.get('🌱 글로벌 코어 지수', 0) + norm_w.get('🤖 테마 & 미래혁신', 0) + norm_w.get('🚀 퀀트 스윙 & 모멘텀', 0)) * 100))
    income_ratio = int(round((norm_w.get('💰 고배당 & 인컴', 0) + norm_w.get('💵 안전 현금', 0)) * 100))

    return {
        'expected_cagr': cagr,
        'portfolio_volatility': portfolio_vol,
        'sharpe_ratio': sharpe,
        'dividend_yield': div_yield,
        'annual_dividend_krw': annual_div,
        'monthly_dividend_krw': monthly_div,
        'health_score': health_score,
        'growth_ratio': growth_ratio,
        'income_ratio': income_ratio,
        'stress_2008': stress_2008,
        'stress_2020': stress_2020,
        'stress_2022': stress_2022,
        'normalized_weights': norm_w
    }


def get_cross_lens_matrix(analysis: dict) -> dict:
    """
    5대 계좌 x 6대 자산 팩터 크로스 매트릭스 및 세제 최적화 분석 결과 반환
    """
    acc_list = ["연금저축펀드", "일반계좌(해외)", "ISA", "일반계좌(국내)", "IRP및코인"]
    cat_list = [
        "🌱 글로벌 코어 지수",
        "💰 고배당 & 인컴",
        "🤖 테마 & 미래혁신",
        "🚀 퀀트 스윙 & 모멘텀",
        "🪙 대체자산 (코인)",
        "💵 안전 현금"
    ]

    all_h = analysis.get('all_holdings_df', pd.DataFrame())
    matrix_df = pd.DataFrame(0.0, index=acc_list, columns=cat_list)

    if not all_h.empty:
        for _, r in all_h.iterrows():
            acc = r.get('계좌')
            cat = r.get('자산분류')
            val = r.get('평가금액(원)', 0.0)
            if acc in matrix_df.index and cat in matrix_df.columns:
                matrix_df.loc[acc, cat] += val

    # 계좌별 현금 추가
    for acc in acc_list:
        acc_cash = analysis.get('accounts', {}).get(acc, {}).get('total_cash_krw', 0.0)
        matrix_df.loc[acc, "💵 안전 현금"] += acc_cash

    matrix_df["계좌 합계"] = matrix_df.sum(axis=1)

    # 세제 효율성 점검 및 인사이트
    total_net = analysis.get('total_net_worth', 1.0)
    tax_favored_eval = (
        matrix_df.loc["연금저축펀드", "계좌 합계"]
        + matrix_df.loc["ISA", "계좌 합계"]
        + matrix_df.loc["IRP및코인", "계좌 합계"] * 0.9  # IRP 부분 포함
    )
    tax_favored_pct = (tax_favored_eval / total_net * 100.0) if total_net > 0 else 0.0

    taxable_dividend = matrix_df.loc["일반계좌(해외)", "💰 고배당 & 인컴"] + matrix_df.loc["일반계좌(국내)", "💰 고배당 & 인컴"]
    taxable_dividend_pct = (taxable_dividend / total_net * 100.0) if total_net > 0 else 0.0

    return {
        'matrix_df': matrix_df,
        'tax_favored_eval': tax_favored_eval,
        'tax_favored_pct': tax_favored_pct,
        'taxable_dividend_krw': taxable_dividend,
        'taxable_dividend_pct': taxable_dividend_pct
    }


def calculate_smart_deposit_rebalancing(analysis: dict, deposit_krw: float, target_cat_weights_pct: dict) -> list:
    """
    [No-Sell 스마트 입금 리밸런싱 알고리즘]
    기존 주식을 매도하지 않고, 새로 입금할 현금(deposit_krw)을
    현재 목표 비중에서 가장 결핍된 자산군 및 계좌로 스마트 분배
    """
    total_eq = analysis.get('total_net_worth', 0.0)
    new_tot = total_eq + deposit_krw
    cats_data = analysis.get('categories_data', {})

    tot_w = sum(target_cat_weights_pct.values())
    norm_w = {k: target_cat_weights_pct.get(k, 0.0) / tot_w for k in target_cat_weights_pct} if tot_w > 0 else {}

    deficits = {}
    for c, w in norm_w.items():
        cur_eval = cats_data.get(c, {}).get('eval_krw', 0.0)
        tgt_eval = new_tot * w
        deficits[c] = max(0.0, tgt_eval - cur_eval)

    tot_deficit = sum(deficits.values())
    allocations = {}
    for c, d in deficits.items():
        allocations[c] = (deposit_krw * (d / tot_deficit)) if tot_deficit > 0 else (deposit_krw * norm_w.get(c, 0.0))

    orders = []
    all_h = analysis.get('all_holdings_df', pd.DataFrame())

    for cat_name, alloc_krw in allocations.items():
        if alloc_krw < 30000:
            continue

        if cat_name == "💵 안전 현금":
            orders.append({
                "자산 팩터": cat_name,
                "추천 계좌": "연금저축 / 해외계좌 예수금",
                "추천 대상": "안전 현금 (CMA / 달러 예수금)",
                "배분 금액": f"{int(alloc_krw):,}원",
                "추천 주문": "예수금 유지 / 파킹",
                "실행 이유": "하락장 저가 매수용 비상 탄약 버퍼 확보"
            })
            continue

        cat_holdings = all_h[all_h['자산분류'] == cat_name] if (not all_h.empty and '자산분류' in all_h.columns) else pd.DataFrame()
        if not cat_holdings.empty:
            if '수익률(%)' in cat_holdings.columns:
                top_h = cat_holdings.sort_values(by='수익률(%)', ascending=False).iloc[0]
            elif '평가금액(원)' in cat_holdings.columns:
                top_h = cat_holdings.sort_values(by='평가금액(원)', ascending=False).iloc[0]
            else:
                top_h = cat_holdings.iloc[0]
            price = top_h.get('현재가', 0.0)
            target_acc = top_h.get('계좌', '연금저축펀드')
            name = top_h.get('종목명', '')
            shares = int(alloc_krw // price) if price > 0 else 0
            buy_val = shares * price if price > 0 else alloc_krw

            orders.append({
                "자산 팩터": cat_name,
                "추천 계좌": target_acc,
                "추천 대상": f"{name} ({top_h.get('티커', '')})",
                "배분 금액": f"{int(buy_val if shares > 0 else alloc_krw):,}원",
                "추천 주문": f"{shares}주 분할 매수" if shares > 0 else "분할 매수",
                "실행 이유": f"목표 대비 {int(deficits.get(cat_name, 0)):,}원 부족분 최우선 채우기"
            })
        else:
            orders.append({
                "자산 팩터": cat_name,
                "추천 계좌": "절세 계좌 (연금/ISA)",
                "추천 대상": f"{cat_name} 대표 ETF",
                "배분 금액": f"{int(alloc_krw):,}원",
                "추천 주문": "분할 매수",
                "실행 이유": "신규 자산군 확충 (목표 대비 결핍)"
            })

    return orders


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

