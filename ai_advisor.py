# -*- coding: utf-8 -*-
"""
ai_advisor.py
- JTI 나만의 1:1 전담 AI 주식 자문 & 자산 증식 Private Banker (PB) 에이전트
- Google Gemini 최신 무료 티어 모델 연동
- 내 5대 계좌 실시간 자산, 순투입원금, 보유종목, 거시지표(VIX/이평선) 100% 인지
- 마크 미너비니 SEPA/VCP + 레이 달리오 올웨더 팩터 + 한국 세제(연금/ISA) 최적화
"""

import os
import json
import requests
from datetime import datetime

# 지원하는 Gemini 모델 우선순위 (개인 무료 티어 기준 최신 및 고성능 모델)
GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-1.5-flash",
    "gemini-3.8-flash"
]

QUICK_PROMPTS = [
    {
        "icon": "🩺",
        "title": "계좌 종합 건강검진",
        "prompt": "현재 내 5대 계좌 종합 현황과 보유 종목 상태를 월가 수석 PB 관점에서 정밀 진단하고, 가장 시급하게 개선해야 할 점 3가지를 두괄식으로 알려주세요."
    },
    {
        "icon": "🧭",
        "title": "이번 달 추천 매수 종목",
        "prompt": "현재 가용 현금과 계좌별 목표 비중(연금저축/ISA/일반계좌)을 고려할 때, 이번 달에 우선적으로 분할 매수해야 할 종목과 적정 매수 금액을 추천해 주세요."
    },
    {
        "icon": "🚨",
        "title": "손절(-7%) 위험 종목 점검",
        "prompt": "마크 미너비니의 원칙에 따라 현재 보유 종목 중 -7% 손절선에 근접했거나 50일선을 이탈하여 리스크 관리가 시급한 종목이 있는지 전수 점검해 주세요."
    },
    {
        "icon": "🌐",
        "title": "시장 상태(VIX) 대응 전략",
        "prompt": "현재 VIX 공포지수와 4대 지수 정배열 스코어를 감안할 때, 지금 적극적으로 신규 주식을 사야 할 타이밍인가요, 아니면 현금 비중을 방어해야 할 때인가요?"
    },
    {
        "icon": "🌱",
        "title": "10년 복리 자산 달성 플랜",
        "prompt": "현재 내 자산과 배당률을 바탕으로, 10년 뒤 '월 배당 200만 원' 파이프라인을 완성하려면 매달 얼마씩 추가 적립하고 어떻게 배당을 재투자해야 하는지 로드맵을 짜주세요."
    }
]


def build_portfolio_context(raw_p_data: dict, analysis: dict, macro_summary: dict = None) -> str:
    """
    대표님의 실시간 5대 계좌, 순투입원금, 보유종목, 거시 지표를 AI PB가 완벽히 파악할 수 있도록 
    구조화된 텍스트 컨텍스트로 생성합니다.
    """
    total_net_worth = analysis.get('total_net_worth', 0.0)
    total_cost_basis = analysis.get('total_cost_basis', 0.0)
    total_pnl = analysis.get('total_pnl_krw', 0.0)
    total_ret = analysis.get('total_return_pct', 0.0)
    total_cash = analysis.get('total_cash_krw', 0.0)
    annual_div = analysis.get('total_annual_dividend_krw', 0.0)
    monthly_div = analysis.get('total_monthly_dividend_krw', 0.0)
    div_yield = analysis.get('portfolio_dividend_yield', 0.0)
    exchange_rate = analysis.get('exchange_rate', 1430.0)

    lines = []
    lines.append("=== [고객(대표님) 실시간 통합 자산 포트폴리오 데이터] ===")
    lines.append(f"- 기준 일시: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"- 총 평가 자산: {int(total_net_worth):,}원")
    lines.append(f"- 순투입원금(진짜 원금): {int(total_cost_basis):,}원")
    lines.append(f"- 총 평가 손익: {int(total_pnl):+,}원 (수익률: {total_ret:+.2f}%)")
    lines.append(f"- 가용 총 현금(원화+달러): {int(total_cash):,}원 (현금 비중: {(total_cash/total_net_worth*100) if total_net_worth>0 else 0:.1f}%)")
    lines.append(f"- 연간 예상 배당금: {int(annual_div):,}원 (월환산: 약 {int(monthly_div):,}원, 배당수익률: {div_yield:.2f}%)")
    lines.append(f"- 실시간 기준 환율: 1 USD = {exchange_rate:,.1f} KRW\n")

    # 5대 계좌별 현황
    lines.append("--- [5대 계좌별 세부 자산 및 목표 비중 비교] ---")
    for acc in analysis.get('account_comparison', []):
        name = acc.get('account', '')
        eval_krw = int(acc.get('eval_krw', 0))
        cost_krw = int(acc.get('cost_krw', 0))
        ret_pct = acc.get('return_pct', 0.0)
        curr_w = acc.get('current_weight', 0.0)
        tgt_w = acc.get('target_weight', 0.0)
        gap = acc.get('gap', 0.0)
        badge = acc.get('status_badge', '')
        lines.append(f"* {name} [{acc.get('type', '')}]: 평가액 {eval_krw:,}원 | 순원금 {cost_krw:,}원 | 손익률 {ret_pct:+.1f}% | 현재비중 {curr_w:.1f}% (목표 {tgt_w:.0f}%, 차이 {gap:+.1f}%) -> {badge}")

    # 전체 보유 종목 상세 내역
    lines.append("\n--- [보유 종목 전체 현황 (총 20여 개 종목)] ---")
    all_h = analysis.get('all_holdings_df')
    if all_h is not None and not all_h.empty:
        for _, row in all_h.iterrows():
            lines.append(
                f"- [{row.get('계좌')}] {row.get('종목명')}({row.get('티커')}): "
                f"수량 {row.get('수량')} | 매수가 {row.get('매수단가')} | 현재가 {row.get('현재가')} | "
                f"수익률 {row.get('수익률(%)')} | 평가금액 {int(row.get('평가금액(원)', 0)):,}원 | "
                f"배당률 {row.get('배당수익률(%)')}% | AI진단: {row.get('진단상태')} ({row.get('처방내용')})"
            )

    # 거시 지표 상태 (VIX, 지수)
    if macro_summary:
        lines.append("\n--- [글로벌 거시 경제 및 퀀트 지표 상태] ---")
        meta = macro_summary.get('meta', {})
        vix_info = meta.get('vix_info', {})
        lines.append(f"- 시장 종합 점수: {macro_summary.get('avg_score', 2.0):.2f} / 3.00")
        lines.append(f"- 미국 시장 점수: {meta.get('us_score', 2.0):.2f} / 3.00 (S&P 500, 나스닥 100)")
        lines.append(f"- 국내 시장 점수: {meta.get('kr_score', 2.0):.2f} / 3.00 (코스피, 코스닥)")
        lines.append(f"- 실시간 VIX 공포지수: {vix_info.get('value', 21.0):.2f} (변동: {vix_info.get('change', 0.0):+.2f}, 리스크 수준: {vix_info.get('level', '정상')})")
        lines.append(f"- 시장 상태 진단: {meta.get('market_status_desc', '시장 추세 유지 중')}")
        lines.append(f"- 미너비니 행동 지침: {meta.get('market_action_guide', '분할 매수로 접근')}")

    return "\n".join(lines)


def get_system_prompt(portfolio_context: str) -> str:
    """
    월가 수석 포트폴리오 매니저 & 마크 미너비니 퀀트 전문 PB 페르소나 시스템 프롬프트
    """
    return f"""당신은 월가 최상위 헤지펀드 수석 포트폴리오 매니저이자, 마크 미너비니(Mark Minervini)의 SEPA 퀀트 스윙 전략 및 레이 달리오(Ray Dalio)의 올웨더 팩터 자산배분, 그리고 한국의 세제 혜택(연금저축/ISA)을 극대화하는 자산관리 전담 PB(Private Banker) 'JTI 수석 자문위원'입니다.

고객(대표님)은 현재 본인의 5대 금융 계좌 데이터를 시스템에 완전히 연동해 두었습니다. 당신은 아래에 제공된 대표님의 실시간 포트폴리오와 거시 경제 데이터를 100% 인지하고 상담을 진행합니다.

{portfolio_context}

### [당신의 핵심 투자 철학 및 4대 행동 원칙]
1. **철저한 리스크 관리 (Capital Preservation First)**:
   - "이익을 쫓기 전에 먼저 잃지 않는 법을 배워라." (마크 미너비니 원칙)
   - 개별 주식(단기 퀀트 스윙)은 매수가 대비 -7% 하락 시 기계적으로 칼손절을 권고합니다.
   - VIX 공포지수가 25 이상이거나 지수 이평선이 역배열인 경우, 신규 매수를 극도로 자제하고 현금 비중 확대를 제언합니다.
2. **계좌별 듀얼 트랙(Dual-Track) 전략 엄수**:
   - **장기 적립 계좌 (연금저축, ISA)**: 200일선 위 우상향 추세의 글로벌 코어 지수(S&P500, 나스닥) 및 고배당 인컴(미국배당다우존스)은 절대 손절하지 않으며, 단기 조정 시 저가 분할 적립 및 배당 재투자를 권장합니다.
   - **단기 퀀트 스윙 계좌 (일반해외, 일반국내)**: 20/50/200일선 정배열 주도주를 대상으로 VCP 피벗 초입 돌파 매수, 20일선 눌림목 지지 매수, -7% 칼손절을 엄격히 적용합니다.
3. **6대 자산 팩터 올웨더 밸런스 유지**:
   - 권장 목표 비중: 글로벌 코어 지수 35%, 고배당 & 인컴 30%, 테마 & 미래혁신 15%, 퀀트 스윙 10%, 대체자산(코인) 2%, 안전 현금 8%.
   - 특정 팩터나 계좌가 과도하게 쏠리지 않도록 리밸런싱을 제언합니다.
4. **구체적이고 실전적인 데이터 기반 조언**:
   - 절대 "좋은 종목을 분할 매수하세요" 같은 원론적인 답변을 하지 마십시오.
   - 대표님의 실제 계좌명, 보유 종목명, 현재 평가액, 수익률, 가용 현금 수치를 직접 언급하며, "연금저축의 현금 XX만 원 중 OO만 원으로 [종목명]을 X회에 걸쳐 분할 매수하십시오"와 같이 당장 증권사 앱에서 실행할 수 있는 액션 플랜을 제시하십시오.

### [답변 스타일 가이드]
- **어조**: 매우 정중하고 신뢰감 넘치는 최고급 금융 PB의 어조 ("대표님, 현재 포트폴리오를 진단한 결과...").
- **형식**: 핵심 결론을 가장 먼저 제시하는 두괄식 브리핑 -> 데이터 근거 -> 구체적 실전 실행 지침(Action Plan) 순으로 깔끔한 마크다운 불릿 포인트로 작성.
- 모바일 화면에서도 가독성이 뛰어나도록 단락을 명확히 구분하고 가독성을 극대화할 것.
- **간결성과 완결성**: 불필요한 장황한 서론이나 중복 설명은 배제하고, 핵심 분석과 실행 지침을 명료하고 완결성 있게 작성하여 답변이 도중에 끊기지 않고 완전히 마무리되도록 하십시오.
"""


def stream_gemini_advisor(
    api_key: str,
    user_prompt: str,
    conversation_history: list,
    portfolio_context: str,
    preferred_model: str = "gemini-2.0-flash"
):
    """
    Google Gemini API로부터 실시간 스트리밍으로 텍스트 조각(chunk)을 반환합니다.
    Streamlit의 st.write_stream과 결합하여 대기 시간 없이 0.5초 만에 타이핑되듯 즉시 화면에 출력됩니다.
    """
    if not api_key:
        yield "⚠️ Gemini API 키가 입력되지 않았습니다. 상단 설정창에 키를 입력해 주세요."
        return

    system_instruction = get_system_prompt(portfolio_context)
    candidate_models = [preferred_model] + [m for m in GEMINI_MODELS if m != preferred_model]

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        contents = []
        for msg in conversation_history[-6:]:
            role = "user" if msg.get("role") == "user" else "model"
            contents.append(types.Content(
                role=role,
                parts=[types.Part.from_text(text=msg.get("content", ""))]
            ))
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_prompt)]
        ))

        for model in candidate_models:
            try:
                thinking_cfg = types.ThinkingConfig(thinking_budget=0) if "2.5" in model else None
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.3,
                    max_output_tokens=8192,
                    thinking_config=thinking_cfg
                )

                response_stream = client.models.generate_content_stream(
                    model=model,
                    contents=contents,
                    config=config
                )

                yielded = False
                for chunk in response_stream:
                    if chunk and chunk.text:
                        yielded = True
                        yield chunk.text

                if yielded:
                    return
            except Exception:
                continue
    except Exception:
        pass

    # 스트리밍 실패 시 단일 호출 폴백
    fallback_res = call_gemini_advisor(
        api_key=api_key,
        user_prompt=user_prompt,
        conversation_history=conversation_history,
        portfolio_context=portfolio_context,
        preferred_model=preferred_model
    )
    yield fallback_res


def call_gemini_advisor(
    api_key: str,
    user_prompt: str,
    conversation_history: list,
    portfolio_context: str,
    preferred_model: str = "gemini-2.0-flash"
) -> str:
    """
    Google Gemini API를 호출하여 자문 답변을 수신합니다.
    - max_output_tokens=8192로 대폭 확대하여 답변 중간 잘림 현상 원천 차단
    - thinking_budget=0 설정으로 생각 지연 시간(10~15초)을 제거하고 초고속 응답
    """
    if not api_key:
        return "⚠️ Gemini API 키가 입력되지 않았습니다. 상단 또는 사이드바의 API 키 설정창에 키를 입력해 주세요."

    system_instruction = get_system_prompt(portfolio_context)
    candidate_models = [preferred_model] + [m for m in GEMINI_MODELS if m != preferred_model]

    # 1. google-genai 최신 SDK 시도
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        contents = []
        for msg in conversation_history[-6:]:  # 최근 3턴 대화 유지
            role = "user" if msg.get("role") == "user" else "model"
            contents.append(types.Content(
                role=role,
                parts=[types.Part.from_text(text=msg.get("content", ""))]
            ))
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_prompt)]
        ))

        for model in candidate_models:
            try:
                thinking_cfg = types.ThinkingConfig(thinking_budget=0) if "2.5" in model else None
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.3,
                    max_output_tokens=8192,
                    thinking_config=thinking_cfg
                )

                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config
                )
                if response and response.text:
                    return response.text
            except Exception:
                continue

    except Exception:
        pass

    # 2. REST API 직접 호출 (SDK 호환성 문제 시 완벽한 폴백)
    url_models = [preferred_model] + [m for m in GEMINI_MODELS if m != preferred_model]
    for model in url_models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            
            contents = []
            for msg in conversation_history[-6:]:
                role = "user" if msg.get("role") == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg.get("content", "")}]
                })
            contents.append({
                "role": "user",
                "parts": [{"text": user_prompt}]
            })

            gen_config = {
                "temperature": 0.3,
                "maxOutputTokens": 8192
            }
            if "2.5" in model:
                gen_config["thinkingConfig"] = {"thinkingBudget": 0}

            payload = {
                "system_instruction": {
                    "parts": [{"text": system_instruction}]
                },
                "contents": contents,
                "generationConfig": gen_config
            }

            resp = requests.post(url, json=payload, timeout=25)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"]
        except Exception:
            continue

    return "❌ Gemini API 응답 생성에 실패했습니다. API 키의 유효성 또는 인터넷 연결 상태를 확인해 주세요."


def get_rule_based_fallback_advisor(user_prompt: str, analysis: dict = None, portfolio_context: str = "") -> str:
    """
    API 키가 없거나 연결이 어려울 때, 시스템 내부 퀀트 분석 엔진을 기반으로 
    즉시 맞춤형 자문을 제공하는 룰베이스 응답기입니다.
    analysis가 dict가 아니거나 str이 전달되더라도 안전하게 복구합니다.
    """
    if isinstance(analysis, str):
        portfolio_context = analysis
        analysis = None

    if analysis is None or not isinstance(analysis, dict):
        try:
            import portfolio_manager
            raw_p = portfolio_manager.load_portfolio_data()
            analysis = portfolio_manager.analyze_my_portfolio(raw_p)
        except Exception:
            analysis = {}

    total_worth = analysis.get('total_net_worth', 0.0)
    cost = analysis.get('total_cost_basis', 0.0)
    ret = analysis.get('total_return_pct', 0.0)
    cash = analysis.get('total_cash_krw', analysis.get('total_cash', 0.0))
    orders = analysis.get('order_suggestions')
    annual_div = analysis.get('total_annual_dividend_krw', 0.0)
    div_yield = analysis.get('portfolio_dividend_yield', 0.0)

    if any(k in user_prompt for k in ["건강검진", "진단", "총평", "상태"]):
        res = "### 🩺 [AI PB] 대표님의 포트폴리오 실시간 정밀 건강검진\n\n"
        res += f"대표님, 현재 총 평가자산 **{int(total_worth):,}원**, 순투입원금 **{int(cost):,}원**으로 누적 수익률은 **{ret:+.2f}%**입니다.\n\n"
        res += "**1. 핵심 자산 배분 진단:**\n"
        for acc in analysis.get('account_comparison', [])[:3]:
            res += f"- **{acc.get('account', '')}**: 현재 {acc.get('current_weight', 0):.1f}% (목표 {acc.get('target_weight', 0):.0f}%) -> {acc.get('status_badge', '')}\n"
        cash_pct = (cash / total_worth * 100) if total_worth > 0 else 0
        res += f"\n**2. 유동성(현금) 버퍼:** 가용 현금 {int(cash):,}원 (비중 {cash_pct:.1f}%)으로 시장 급락 시 방어력이 양호합니다.\n"
        res += "\n💡 **자유로운 심층 질의응답을 위해 상단의 '🔑 Gemini 무료 API 키 설정'에 키를 등록해 주시면, 최고 수준의 실시간 1:1 대화식 상담이 가능합니다.**"
        return res

    elif any(k in user_prompt for k in ["매수", "추천", "이번 달", "살까"]):
        res = "### 🧭 [AI PB] 이번 달 맞춤형 리밸런싱 및 분할 매수 제언\n\n"
        res += f"현재 계좌별 가용 현금(총 {int(cash):,}원)과 목표 비중 갭을 고려한 추천 주문입니다:\n\n"
        if orders is not None and hasattr(orders, 'empty') and not orders.empty:
            for _, r in orders.head(3).iterrows():
                res += f"- **[{r.get('계좌')}] {r.get('종목명')}**: {r.get('추천주문')} ({r.get('주문금액')}) - {r.get('이유')}\n"
        else:
            res += "- 현재 목표 비중 내에서 균형 있게 유지되고 있습니다. 200일선 우상향 중인 글로벌 코어 ETF 분할 적립을 추천합니다.\n"
        res += "\n💡 **종목별 구체적 비중 상담 및 매수 타이밍을 원하시면 상단에 무료 Gemini API 키를 등록해 보세요!**"
        return res

    elif any(k in user_prompt for k in ["손절", "위험", "미너비니"]):
        res = "### 🚨 [AI PB] 마크 미너비니 리스크 관리 & 손절(-7%) 전수 점검\n\n"
        danger_list = []
        all_h = analysis.get('all_holdings_df')
        if all_h is not None and hasattr(all_h, 'empty') and not all_h.empty:
            for _, row in all_h.iterrows():
                if "손절" in str(row.get('진단상태', '')) or row.get('수익률(%)', 0) <= -7.0:
                    danger_list.append(row)
        
        if danger_list:
            res += "⚠️ **미너비니 -7% 안전 버퍼 손절선에 도달한 경고 종목이 있습니다:**\n"
            for d in danger_list:
                res += f"- **[{d.get('계좌')}] {d.get('종목명')}**: 수익률 {d.get('수익률(%)', 0):.1f}% -> {d.get('처방내용', '')}\n"
        else:
            res += "✅ **현재 보유 중인 개별 종목 중 -7% 손절 기준선에 도달한 위험 종목은 없습니다.** 추세를 안정적으로 유지하고 있습니다.\n"
        res += "\n💡 **상세한 손절 및 트레일링 스탑 가이드는 Gemini 무료 API 키를 등록하시면 실시간으로 대화하실 수 있습니다.**"
        return res

    elif any(k in user_prompt for k in ["VIX", "공포", "시장 상태", "대응"]):
        res = "### 🌐 [AI PB] 거시 시장(VIX) 및 국면별 포트폴리오 대응 전략\n\n"
        res += "현재 시장 거시 지표를 분석한 결과:\n\n"
        res += f"- **가용 총 현금**: {int(cash):,}원 (안전 버퍼)\n"
        res += "- **원칙 제언**:\n"
        res += "  1. **VIX 15~20 구간 (중립 추세)**: 200일선 우상향 코어 자산(S&P500, 미국배당다우존스)은 흔들림 없이 정기 분할 적립을 유지하십시오.\n"
        res += "  2. **단기 스윙 종목**: 50일선 위에 위치한 주도주 위주로 비중을 유지하고, 50일선 이탈 종목은 반등 시 현금화하여 방어력을 높이십시오.\n"
        res += "\n💡 **실시간 VIX 수치 기반의 정밀 포트폴리오 리밸런싱을 원하시면 Gemini API 키를 등록해 주세요!**"
        return res

    elif any(k in user_prompt for k in ["복리", "10년", "배당", "파이프라인", "플랜"]):
        res = "### 🌱 [AI PB] 10년 복리 자산 증식 & 월 배당 파이프라인 로드맵\n\n"
        monthly_div = annual_div / 12.0
        res += f"대표님, 현재 연간 예상 배당금은 **{int(annual_div):,}원** (월환산 약 **{int(monthly_div):,}원**, 배당수익률 {div_yield:.2f}%)입니다.\n\n"
        res += "**목표: 10년 뒤 '월 배당 200만 원 (연 2,400만 원)' 파이프라인 달성 전략**\n"
        res += "- **목표 총자산**: 세후 배당수익률 4.0% 가정 시 약 **6억 원**의 자산이 필요합니다.\n"
        res += f"- **현재 자산**: 약 {int(total_worth):,}원\n"
        res += "- **핵심 액션 플랜**:\n"
        res += "  1. **절세 계좌 풀 활용**: 연금저축(연 600만 원) + ISA(연 2,000만 원)에 최우선 납입하여 배당소득세(15.4%)를 전액 재투자합니다.\n"
        res += "  2. **배당금 100% 재투자 (DRIP)**: 나오는 배당금을 즉시 코어 배당성장 ETF에 재투자하여 복리 효과를 극대화합니다.\n"
        res += "  3. **월 적립 목표**: 연 8% 복리 성장 가정 시, 매달 약 200~250만 원을 꾸준히 적립하시면 10년 이내에 월 200만 원 배당 파이프라인이 완성됩니다.\n"
        res += "\n💡 **대표님의 월 가용 저축액에 맞춘 맞춤형 시뮬레이션을 원하시면 Gemini API 키를 등록해 대화를 이어가 보세요!**"
        return res

    return (
        f"대표님, 질문하신 내용을 접수했습니다.\n\n"
        f"현재 총자산 {int(total_worth):,}원, 순투입 {int(cost):,}원, 가용 현금 {int(cash):,}원 상태를 고려할 때 원칙적인 리스크 관리가 필요합니다.\n\n"
        f"💡 **자유로운 대화식 상담을 원활히 이용하시려면, Google AI Studio에서 무료로 발급받으신 Gemini API 키를 상단 설정창에 등록해 주세요!**"
    )

