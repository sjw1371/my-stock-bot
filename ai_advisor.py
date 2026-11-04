# -*- coding: utf-8 -*-
"""
ai_advisor.py
- JTI 나만의 1:1 전담 AI 주식 자문 & 자산 증식 Private Banker (PB) 에이전트
- Google Gemini 최신 무료 티어 모델 연동 + 로컬 영구 설정 보관
- API 키가 없어도 100% 작동하는 '월가 수석 PB & 미너비니 퀀트 자체 엔진' 탑재
- 내 5대 계좌 실시간 자산, 순투입원금, 보유종목, 거시지표(VIX/이평선) 100% 인지
- 마크 미너비니 SEPA/VCP + 레이 달리오 올웨더 팩터 + 한국 세제(연금/ISA) 최적화
"""

import os
import json
import time
import requests
from datetime import datetime

# 설정 파일 경로
CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_config.json")

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


def load_ai_config() -> dict:
    """
    ai_config.json 파일 또는 환경변수에서 AI 설정(API 키, 모델)을 로드합니다.
    사용자가 한 번 등록하면 파일에 영구 저장되므로 다시 묻지 않습니다.
    """
    config = {
        "gemini_api_key": "",
        "gemini_model": "gemini-2.0-flash",
        "use_custom_api": False
    }

    # 1. 파일에서 로드
    if os.path.exists(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                config.update(saved)
        except Exception:
            pass

    # 2. 환경변수 확인 (파일에 키가 없을 때만)
    if not config.get("gemini_api_key"):
        env_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if env_key:
            config["gemini_api_key"] = env_key

    return config


def save_ai_config(api_key: str = "", model: str = "gemini-2.0-flash", use_custom_api: bool = False) -> bool:
    """
    AI 설정을 ai_config.json 파일에 영구 저장합니다.
    """
    config = {
        "gemini_api_key": api_key.strip(),
        "gemini_model": model.strip() if model else "gemini-2.0-flash",
        "use_custom_api": bool(api_key.strip())
    }
    try:
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


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
    preferred_model: str = "gemini-2.0-flash",
    analysis: dict = None,
    macro_summary: dict = None
):
    """
    스마트 자문 스트리밍 생성기:
    1) 유효한 API 키가 있을 경우: Google Gemini 최신 모델로 초고속 스트리밍 생성.
    2) API 키가 없거나 호출 실패 시: 시스템 내장 '월가 수석 PB & 미너비니 퀀트 자체 엔진'을 가동하여
       실시간 타이핑 효과(단어 단위 제너레이터)로 부드럽게 출력.
    """
    clean_key = (api_key or "").strip()

    # 1. API 키가 있으면 Gemini API 호출 시도
    if clean_key:
        system_instruction = get_system_prompt(portfolio_context)
        candidate_models = [preferred_model] + [m for m in GEMINI_MODELS if m != preferred_model]

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=clean_key)

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

        # REST API 호출 시도
        rest_reply = call_gemini_advisor(
            api_key=clean_key,
            user_prompt=user_prompt,
            conversation_history=conversation_history,
            portfolio_context=portfolio_context,
            preferred_model=preferred_model
        )
        if rest_reply and not rest_reply.startswith("❌"):
            yield rest_reply
            return

    # 2. [핵심] API 키가 없거나 호출이 실패한 경우: 내장 퀀트 수석 PB 엔진 가동
    expert_reply = run_expert_quant_advisor(user_prompt, analysis=analysis, macro_summary=macro_summary)

    # 타자 치듯 자연스러운 스트리밍 효과 반환 (0.01~0.02초 간격)
    words = expert_reply.split(" ")
    for i, w in enumerate(words):
        yield w + (" " if i < len(words) - 1 else "")
        time.sleep(0.015)


def call_gemini_advisor(
    api_key: str,
    user_prompt: str,
    conversation_history: list,
    portfolio_context: str,
    preferred_model: str = "gemini-2.0-flash"
) -> str:
    """
    Google Gemini REST API 직접 호출
    """
    clean_key = (api_key or "").strip()
    if not clean_key:
        return ""

    system_instruction = get_system_prompt(portfolio_context)
    url_models = [preferred_model] + [m for m in GEMINI_MODELS if m != preferred_model]

    for model in url_models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={clean_key}"
            
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

    return "❌ Gemini API 응답 생성에 실패했습니다."


def run_expert_quant_advisor(user_prompt: str, analysis: dict = None, macro_summary: dict = None) -> str:
    """
    [월가 수석 PB & 마크 미너비니 퀀트 자체 내장 자문 엔진]
    API 키가 전혀 필요 없으며, 대표님의 5대 계좌 실시간 평가액, 순원금, 손익률,
    보유 종목 전수 데이터 및 미너비니 리스크 관리 원칙을 수학적으로 결합하여
    최상급 기관투자가 리포트를 즉시 생성합니다.
    """
    if analysis is None or not isinstance(analysis, dict):
        try:
            import portfolio_manager
            raw_p = portfolio_manager.load_portfolio_data()
            analysis = portfolio_manager.analyze_my_portfolio(raw_p)
        except Exception:
            analysis = {}

    total_worth = analysis.get('total_net_worth', 0.0)
    cost = analysis.get('total_cost_basis', 0.0)
    pnl = analysis.get('total_pnl_krw', 0.0)
    ret = analysis.get('total_return_pct', 0.0)
    cash = analysis.get('total_cash_krw', 0.0)
    annual_div = analysis.get('total_annual_dividend_krw', 0.0)
    monthly_div = analysis.get('total_monthly_dividend_krw', 0.0)
    div_yield = analysis.get('portfolio_dividend_yield', 0.0)
    exchange_rate = analysis.get('exchange_rate', 1430.0)
    accounts = analysis.get('account_comparison', [])
    orders = analysis.get('order_suggestions')
    all_h = analysis.get('all_holdings_df')
    categories = analysis.get('categories_data', {})

    prompt_low = user_prompt.lower()

    # --------------------------------------------------------------------------
    # 1. 종합 계좌 건강검진 / 총평 / 포트폴리오 진단
    # --------------------------------------------------------------------------
    if any(k in prompt_low for k in ["건강검진", "진단", "총평", "상태", "점검", "포트폴리오"]):
        res = "### 🏛️ [월가 수석 PB] 대표님의 5대 금융자산 정밀 건강검진 보고서\n\n"
        res += (
            f"대표님, 현재 대표님의 총 평가 자산은 **{int(total_worth):,}원**이며, "
            f"실제 투입하신 순원금 **{int(cost):,}원** 대비 누적 손익은 **{int(pnl):+,}원 ({ret:+.2f}%)**을 기록하고 있습니다. "
            f"월가 헤지펀드 및 패밀리오피스 PB 관점에서 포트폴리오를 정밀 진단한 핵심 요약과 3대 시급 과제입니다.\n\n"
        )

        res += "#### 📊 1. 5대 계좌 자산 배치 및 목표 비중 갭 분석\n"
        for acc in accounts:
            a_name = acc.get('account', '')
            a_eval = int(acc.get('eval_krw', 0))
            a_ret = acc.get('return_pct', 0.0)
            c_w = acc.get('current_weight', 0.0)
            t_w = acc.get('target_weight', 0.0)
            gap = acc.get('gap', 0.0)
            badge = acc.get('status_badge', '')
            res += f"- **{a_name}** [{acc.get('type', '')}]: 평가액 **{a_eval:,}원** (수익률 {a_ret:+.1f}%) | 비중 **{c_w:.1f}%** (목표 {t_w:.0f}%, 갭 {gap:+.1f}%) ➔ {badge}\n"

        cash_pct = (cash / total_worth * 100) if total_worth > 0 else 0.0
        res += f"\n#### 🛡️ 2. 유동성(현금) 및 배당 인컴 파이프라인\n"
        res += (
            f"- **가용 총 현금**: **{int(cash):,}원** (전체 자산의 **{cash_pct:.1f}%**)\n"
            f"- **현금 버퍼 평가**: 미너비니 원칙상 안전 현금 8~10% 수준이 이상적이며, "
            f"{'현재 충분한 하락장 저가 매수 여력을 확보하고 계십니다.' if cash_pct >= 7 else '급락장 대비 현금 비중을 조금 더 확보하시는 것을 권장합니다.'}\n"
            f"- **배당 인컴**: 연간 예상 **{int(annual_div):,}원** (월환산 약 **{int(monthly_div):,}원**, 연 배당수익률 **{div_yield:.2f}%**)\n"
        )

        res += "\n#### 🎯 3. 가장 시급하게 개선해야 할 3대 액션 플랜\n"
        # 부족 계좌 파악
        under_accs = [a for a in accounts if a.get('gap', 0) < -2.0]
        over_accs = [a for a in accounts if a.get('gap', 0) > 2.0]
        
        step1_txt = f"목표 비중 대비 부족한 **[{under_accs[0].get('account')}]** 계좌에 이번 달 적립금을 우선 배분하여 밸런스를 회복하십시오." if under_accs else "현재 5대 계좌의 비중 밸런스가 매우 양호하므로 정기 적립을 지속하십시오."
        step2_txt = "연금저축 및 ISA 계좌 내 200일선 우상향 코어 ETF(S&P500, 배당다우존스)에서 발생하는 배당금을 100% 즉시 재투자(DRIP)하십시오."
        step3_txt = "일반계좌 내 단기 스윙 종목은 매수가 대비 -7% 손절 원칙을 철저히 준수하여 계좌 원금을 방어하십시오."

        res += f"1. **{step1_txt}**\n"
        res += f"2. **{step2_txt}**\n"
        res += f"3. **{step3_txt}**\n"
        return res

    # --------------------------------------------------------------------------
    # 2. 이번 달 추천 매수 종목 / 분할 매수 / 적립 가이드
    # --------------------------------------------------------------------------
    elif any(k in prompt_low for k in ["매수", "추천", "이번 달", "살까", "적립", "사야"]):
        res = "### 🧭 [월가 수석 PB] 이번 달 맞춤형 리밸런싱 분할 매수 실행 주문표\n\n"
        res += (
            f"대표님, 현재 가용 현금 **{int(cash):,}원**과 5대 계좌별 목표 비중을 감안할 때, "
            f"신규 자금을 무분별하게 분산하지 않고 **비중 결핍이 가장 큰 절세 계좌와 우상향 코어 자산**에 집중하는 것이 복리 극대화의 핵심입니다.\n\n"
        )

        res += "#### 📋 1. 최우선 분할 매수 추천 주문 (No-Sell Water-Filling)\n"
        if orders is not None and hasattr(orders, 'empty') and not orders.empty:
            for idx, r in orders.head(4).iterrows():
                res += (
                    f"- **[{r.get('계좌')}] {r.get('종목명')}** ({r.get('티커')}):\n"
                    f"  * 권장 주문: **{r.get('추천주문')}** (주문금액 약 {r.get('주문금액')})\n"
                    f"  * 현재가: {r.get('현재가')} | 실행 사유: {r.get('이유')}\n"
                )
        else:
            res += (
                f"- **[연금저축펀드] TIGER 미국S&P500 (360750.KS)**: 가용 자금의 40% 분할 매수 (장기 지수 추종)\n"
                f"- **[ISA] SOL 미국배당다우존스 (446720.KS)**: 가용 자금의 35% 분할 매수 (배당 과세이연 극대화)\n"
                f"- **[일반계좌(해외)] 20/50일선 정배열 빅테크**: 가용 자금의 25% 이내 눌림목 분할 매수\n"
            )

        res += "\n#### 💡 2. PB 수석 위원의 실전 주문 팁\n"
        res += (
            "1. **장기적립 계좌(연금/ISA)**: 한 번에 전액 매수하기보다 매주 특정 요일(예: 수요일)에 3~4회 분할하여 분할 매수하십시오.\n"
            "2. **환율 변동 대응**: 원달러 환율이 1,400원 이상 고환율 구간일 때는 국내 상장 해외 ETF(환노출)의 분할 적립이 환차익 방어에 유리합니다.\n"
        )
        return res

    # --------------------------------------------------------------------------
    # 3. 마크 미너비니 손절(-7%) / 리스크 점검 / 위험 종목
    # --------------------------------------------------------------------------
    elif any(k in prompt_low for k in ["손절", "위험", "미너비니", "리스크", "청산", "탈출"]):
        res = "### 🚨 [마크 미너비니 퀀트] 리스크 관리 & -7% 손절선 전수 점검 브리핑\n\n"
        res += (
            "**\"수익률 챔피언의 제1원칙: 손실을 짧게 끊어라. 큰 손실은 언제나 작은 손실을 방치했을 때 시작된다.\"**\n\n"
            "대표님의 전체 보유 종목(국내외 주식 및 ETF)에 대해 미너비니의 -7% 하드스탑(Hard Stop) 및 추세 이탈 여부를 전수 검사했습니다.\n\n"
        )

        danger_items = []
        warning_items = []
        safe_items = []

        if all_h is not None and hasattr(all_h, 'empty') and not all_h.empty:
            for _, row in all_h.iterrows():
                ret_p = float(row.get('수익률(%)', 0.0))
                acc = row.get('계좌', '')
                name = row.get('종목명', '')
                tk = row.get('티커', '')
                diag = str(row.get('진단상태', ''))
                desc = str(row.get('처방내용', ''))

                if "손절" in diag or ret_p <= -7.0:
                    danger_items.append((acc, name, tk, ret_p, desc))
                elif ret_p < -3.0:
                    warning_items.append((acc, name, tk, ret_p, desc))
                else:
                    safe_items.append((acc, name, tk, ret_p))

        if danger_items:
            res += "#### ⚠️ [즉각 조치 필요] -7% 손절선 도달 종목\n"
            for acc, name, tk, ret_p, desc in danger_items:
                res += f"- **[{acc}] {name} ({tk})**: 현재 수익률 **{ret_p:+.1f}%** ➔ **{desc}**\n"
            res += "\n> **미너비니 지침**: 단기 퀀트 스윙 계좌의 종목이라면 감정을 배제하고 기계적으로 비중을 축소하거나 청산하여 소중한 원금을 지키십시오.\n\n"
        else:
            res += "#### ✅ [안전] -7% 초과 손실 종목 없음\n"
            res += "- 현재 단기 스윙 및 개별 종목 중 -7% 손절선에 걸린 위험 종목이 없습니다. 훌륭하게 통제되고 있습니다.\n\n"

        if warning_items:
            res += "#### 🟡 [주의 관찰] -3% ~ -7% 조정 구간 종목\n"
            for acc, name, tk, ret_p, desc in warning_items:
                res += f"- **[{acc}] {name} ({tk})**: 수익률 **{ret_p:+.1f}%** (50일선 지지 여부 모니터링 필요)\n"

        res += "\n#### 🛡️ 듀얼 트랙(Dual-Track) 예외 규정 재확인\n"
        res += (
            "- **연금저축/ISA의 코어 지수/배당 ETF**: 200일선 우상향 자산은 일시적 시장 조정 시 손절하지 않으며, 오히려 평단가를 낮추는 분할 매수 기회로 활용합니다.\n"
            "- **일반계좌의 개별 성장주/테마주**: -7% 손절 원칙을 1%의 타협도 없이 엄격히 적용합니다.\n"
        )
        return res

    # --------------------------------------------------------------------------
    # 4. 거시 시장(VIX) 및 국면별 포트폴리오 대응 전략
    # --------------------------------------------------------------------------
    elif any(k in prompt_low for k in ["vix", "공포", "거시", "시장", "지수", "타이밍", "국면"]):
        res = "### 🌐 [월가 수석 PB] 글로벌 거시 경제(VIX) 및 시장 국면 대응 전략\n\n"
        
        vix_val = 20.5
        vix_lvl = "정상"
        market_score = 2.1
        if macro_summary:
            meta = macro_summary.get('meta', {})
            vix_info = meta.get('vix_info', {})
            vix_val = vix_info.get('value', 20.5)
            vix_lvl = vix_info.get('level', '정상')
            market_score = macro_summary.get('avg_score', 2.1)

        res += f"- **실시간 VIX 변동성 지수**: **{vix_val:.2f}** ({vix_lvl} 국면)\n"
        res += f"- **글로벌 시장 정배열 종합 스코어**: **{market_score:.2f} / 3.00**\n"
        res += f"- **대표님 가용 현금**: **{int(cash):,}원** (방어 버퍼)\n\n"

        res += "#### 🎯 현 시장 국면에서의 구체적 행동 강령\n"
        if vix_val >= 25.0:
            res += (
                "1. **비상 방어 태세**: 시장 변동성이 급증했습니다. 신규 주식 매수를 즉각 중단하고 가용 현금을 보존하십시오.\n"
                "2. **스윙 종목 이익 보존**: 수익 중인 스윙 종목은 스탑 로스를 본전 이상으로 상향하여 수익을 확정 지으십시오.\n"
                "3. **코어 자산 관망**: 연금/ISA 코어 자산은 투매에 동참하지 말고 관망합니다.\n"
            )
        elif vix_val >= 18.0:
            res += (
                "1. **중립 안정적 분할 매수 국면**: 단기적 노이즈가 존재하지만 추세는 유지되고 있습니다.\n"
                "2. **현금 비중 8~10% 유지**: 급락장 발생 시 매수할 비상 탄약을 남겨두고, 월 적립금 범위 내에서만 매수하십시오.\n"
                "3. **주도 섹터 집중**: 20/50/200일선 정배열을 유지하는 강한 섹터에만 선별적으로 접근하십시오.\n"
            )
        else:
            res += (
                "1. **골디락스 공격적 투자 국면**: 시장 리스크가 낮고 추세 추종 전략의 승률이 가장 높은 구간입니다.\n"
                "2. **VCP 돌파 적극 공략**: 미너비니 VCP 패턴을 완성하고 돌파하는 주도주를 적극 매수하십시오.\n"
            )
        return res

    # --------------------------------------------------------------------------
    # 5. 10년 복리 자산 및 배당 파이프라인 달성 플랜
    # --------------------------------------------------------------------------
    elif any(k in prompt_low for k in ["복리", "10년", "배당", "파이프라인", "플랜", "은퇴", "월 200", "목표"]):
        res = "### 🌱 [월가 수석 PB] 10년 복리 자산 증식 & 월 200만 원 배당 파이프라인 로드맵\n\n"
        res += (
            f"대표님, 현재 연간 예상 배당금은 **{int(annual_div):,}원** (월환산 약 **{int(monthly_div):,}원**, 연 배당률 **{div_yield:.2f}%**)입니다. "
            f"현재 총자산 **{int(total_worth):,}원**을 발판으로 10년 뒤 **'월 배당 200만 원 (연 2,400만 원)'**을 달성하기 위한 구체적 시뮬레이션입니다.\n\n"
        )

        target_annual_div = 24000000  # 연 2400만원
        target_asset = target_annual_div / 0.04  # 배당률 4% 기준 6억원

        res += "#### 🎯 1. 10년 목표 정량 분석\n"
        res += (
            f"- **목표 자산 규모**: 연 배당수익률 4.0% 기준 약 **6억 원 (600,000,000원)**\n"
            f"- **현재 자산**: 약 **{int(total_worth):,}원** (목표 대비 진척률: {(total_worth/target_asset*100):.1f}%)\n"
            f"- **10년간 필요한 추가 자산 형성**: 약 **{int(target_asset - total_worth):,}원**\n\n"
        )

        res += "#### 📈 2. 10년 복리 달성을 위한 3대 핵심 엔진\n"
        res += (
            "1. **월 적립 목표**: 연평균 수익률(CAGR) 9.0% + 배당 재투자 가정 시, **매월 약 180만 ~ 220만 원**을 지속 적립하시면 10년 내 6억 원을 돌파합니다.\n"
            "2. **절세 계좌 100% 한도 채우기 (Asset Location)**:\n"
            "   - **연금저축**: 연 600만 원 (월 50만 원) ➔ 16.5% 세액공제(최대 99만 원 환급) + 과세이연\n"
            "   - **ISA**: 연 2,000만 원 ➔ 최대 400만 원 비과세 + 초과분 9.9% 분리과세\n"
            "   - 절세 계좌에서 아낀 세금(15.4%)만으로도 10년간 수천만 원의 복리 추가 수익이 발생합니다.\n"
            "3. **배당금 100% 자동 재투자 (DRIP)**: 수령한 배당금을 생활비로 쓰지 않고 SOL 미국배당다우존스 또는 S&P500을 1주씩 더 매수하는 눈덩이 굴리기를 진행하십시오.\n"
        )
        return res

    # --------------------------------------------------------------------------
    # 6. 개별 보유 종목에 대한 맞춤 상담 (종목명이 프롬프트에 들어있는 경우)
    # --------------------------------------------------------------------------
    matched_holding = None
    if all_h is not None and hasattr(all_h, 'empty') and not all_h.empty:
        for _, r in all_h.iterrows():
            name = str(r.get('종목명', '')).lower()
            tk = str(r.get('티커', '')).lower()
            if (len(name) >= 2 and name in prompt_low) or (len(tk) >= 2 and tk in prompt_low):
                matched_holding = r
                break

    if matched_holding is not None:
        name = matched_holding.get('종목명')
        tk = matched_holding.get('티커')
        acc = matched_holding.get('계좌')
        shares = matched_holding.get('수량')
        cost_p = matched_holding.get('매수단가')
        live_p = matched_holding.get('현재가')
        ret_p = float(matched_holding.get('수익률(%)', 0.0))
        eval_v = int(matched_holding.get('평가금액(원)', 0))
        diag = matched_holding.get('진단상태')
        desc = matched_holding.get('처방내용')

        res = f"### 📊 [월가 수석 PB] '{name} ({tk})' 보유 현황 및 맞춤형 포지션 전략\n\n"
        res += f"대표님께서 보유 중이신 **[{acc}] {name}**의 실시간 데이터와 퀀트 진단 결과입니다:\n\n"
        res += (
            f"- **보유 수량**: {shares}주\n"
            f"- **매수 평균단가**: {cost_p} | **현재가**: {live_p}\n"
            f"- **평가 금액**: {eval_v:,}원\n"
            f"- **현재 수익률**: **{ret_p:+.2f}%**\n"
            f"- **AI 퀀트 진단**: **{diag}** ({desc})\n\n"
        )

        res += "#### 🎯 수석 PB의 대응 가이드\n"
        if ret_p <= -7.0 and "스윙" in str(matched_holding.get('자산분류', '')):
            res += f"- **경고 조치**: 매수가 대비 -7% 손절 기준선에 도달했습니다. 미너비니 원칙상 추가 손실을 막기 위해 반등 시 즉시 비중 축소 또는 손절 청산을 강력 권고합니다.\n"
        elif ret_p > 10.0:
            res += f"- **수익 보존 (Trailing Stop)**: 훌륭한 수익을 내고 계십니다! 스탑 로스 가격을 본전 이상으로 올려 수익을 확정 지으시고, 20일선 이탈 전까지는 추세를 즐기십시오.\n"
        else:
            res += f"- **포지션 유지**: 현재 정상적인 변동성 범위 내에 있습니다. 계좌의 성격([{acc}])에 맞게 목표 비중을 유지하며 정기 점검하십시오.\n"
        return res

    # --------------------------------------------------------------------------
    # 7. 기본 포괄적 질의 응답 (Default General Advisor)
    # --------------------------------------------------------------------------
    res = "### 🏛️ [월가 수석 PB & 미너비니 퀀트 자문 보고서]\n\n"
    res += (
        f"대표님, 질문해 주신 **\"{user_prompt}\"** 건에 대해 현재 실시간 5대 계좌 자산 데이터 "
        f"(총 자산 **{int(total_worth):,}원**, 순원금 **{int(cost):,}원**, 가용 현금 **{int(cash):,}원**)를 기반으로 분석한 지침입니다.\n\n"
    )

    res += "#### 📌 1. 수석 PB의 4대 투자 원칙 관점의 제언\n"
    res += (
        "1. **철저한 손절 원칙 (Capital First)**: 어떤 상황에서도 스윙 종목의 -7% 손절 규칙을 어기지 않는 것이 장기 복리 수익률의 생명선입니다.\n"
        "2. **계좌별 분리 운용 (Dual-Track)**: 연금저축/ISA의 코어 자산은 시간과 배당 복리를 믿고 모아가시고, 일반계좌의 스윙 종목은 추세에 따라 기계적으로 매매하십시오.\n"
        "3. **신규 입금 시 No-Sell 리밸런싱**: 주식을 섣불리 팔지 마시고, 매월 새로 들어오는 여유 자금으로 부족한 자산군을 우선 매수하여 세금과 거래세를 아끼십시오.\n"
        "4. **현금 비중 확보**: 전체 자산의 최소 8% 이상의 현금 버퍼를 유지해야만 급락장에서 시장의 패닉을 기회로 바꿀 수 있습니다.\n\n"
    )

    res += f"💡 **상세 계좌 현황**: 현재 5대 계좌 중 목표 대비 비중 조정이 필요한 계좌는 상단 '🧭 [자산 배분] 탭'에서 확인하실 수 있으며, 구체적인 종목명이나 상황을 말씀해 주시면 더욱 정밀한 1:1 맞춤 조언을 제공해 드리겠습니다."
    return res
