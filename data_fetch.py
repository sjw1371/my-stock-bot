# -*- coding: utf-8 -*-
"""
data_fetch.py
- S&P 500 (503개), NASDAQ 100 (101개), KOSPI (100개), KOSDAQ (100개) 전수조사 풀 완전 탑재
- 멀티스레딩(yf.download) 초고속 배치 데이터 수집 엔진
- 거시경제(VIX, 4대 지수) 데이터 패칭
"""

import sys
import io
import urllib.request
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

# Windows 콘솔 및 Streamlit UTF-8 인코딩 안전화
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def safe_print(msg: str):
    try:
        print(msg)
    except Exception:
        pass


# ==========================================================================
# 📌 마스터 티커 한글명 사전 (국내/해외 주요 종목 매핑)
# ==========================================================================
NAME_DICT = {
    # 해외 대표 종목
    "MSFT": "마이크로소프트", "AAPL": "애플", "NVDA": "엔비디아", "AMZN": "아마존",
    "GOOGL": "알파벳(구글)", "META": "메타", "TSLA": "테슬라", "AVGO": "브로드컴",
    "COST": "코스트코", "NFLX": "넷플릭스", "AMD": "AMD", "QCOM": "퀄컴",
    "INTC": "인텔", "TXN": "텍사스인스트루먼트", "CRM": "세일즈포스",
    "ADBE": "어도비", "ORCL": "오라클", "CSCO": "시스코", "IBM": "IBM",
    "JNJ": "존슨앤존슨", "UNH": "유나이티드헬스", "LLY": "일라이릴리",
    "JPM": "JP모건체이스", "V": "비자", "MA": "마스터카드", "WMT": "월마트",
    "PG": "P&G", "HD": "홈디포", "CVX": "셰브론", "XOM": "엑손모빌",
    "RJF": "Raymond James", "SCHW": "Charles Schwab", "CRWD": "CrowdStrike",
    "ADSK": "Autodesk", "CHD": "Church & Dwight", "MET": "MetLife",
    "AIZ": "Assurant", "HSIC": "Henry Schein", "CPAY": "Corpay",
    "ANET": "Arista Networks", "INCY": "Incyte", "BEN": "Franklin Templeton",
    "BNY": "BNY Mellon", "PANW": "Palo Alto", "KO": "코카콜라",
    "DG": "Dollar General", "FOX": "Fox Corp", "SLB": "SLB Limited",
    "HPQ": "HP Inc", "ULTA": "Ulta Beauty", "CAH": "Cardinal Health",
    "AES": "AES Corp", "FANG": "Diamondback Energy", "CNC": "Centene Corp",
    "BALL": "Ball Corp", "HPE": "Hewlett Packard Ent", "WAB": "Westinghouse Air",
    "QRVO": "Qorvo", "NOW": "ServiceNow", "UBER": "Uber", "DIS": "디즈니",
    # 코스피 대표 종목
    "005930": "삼성전자", "000660": "SK하이닉스", "373220": "LG에너지솔루션",
    "207940": "삼성바이오로직스", "005380": "현대차", "000270": "기아",
    "068270": "셀트리온", "105560": "KB금융", "005490": "POSCO홀딩스",
    "035420": "NAVER", "055550": "신한지주", "051910": "LG화학",
    "012330": "현대모비스", "028260": "삼성물산", "032830": "삼성생명",
    "015760": "한국전력", "086790": "하나금융지주", "035720": "카카오",
    "003670": "포스코퓨처엠", "018260": "삼성에스디에스", "000810": "삼성화재",
    "323410": "카카오뱅크", "010130": "고려아연", "034730": "SK",
    "017670": "SK텔레콤", "011200": "HMM", "009150": "삼성전기",
    "030200": "KT", "010950": "S-Oil", "003550": "LG",
    "034020": "두산에너빌리티", "006400": "삼성SDI", "024110": "기업은행",
    "259960": "크래프톤", "042660": "한화오션", "012450": "한화에어로스페이스",
    "047810": "한국항공우주", "029780": "삼성카드", "004020": "현대제철",
    "001040": "CJ", "090430": "아모레퍼시픽", "078930": "GS",
    "000100": "유한양행", "000720": "현대건설", "005830": "DB손해보험",
    "161890": "한국콜마", "097950": "CJ제일제당", "033780": "KT&G",
    "011170": "롯데케미칼", "028050": "삼성E&A", "138040": "메리츠금융지주",
    "086280": "현대글로비스", "071050": "한국금융지주", "032640": "LG유플러스",
    "011070": "LG이노텍", "271560": "오리온", "009540": "HD한국조선해양",
    "267250": "HD현대일렉트릭", "003490": "대한항공", "000150": "두산",
    "001450": "현대해상", "180640": "한진칼", "008770": "호텔신라",
    "006260": "LS", "007070": "GS리테일", "014680": "한솔케미칼",
    "009830": "한화솔루션", "329180": "HD현대중공업", "402340": "SK스퀘어",
    "377300": "카카오페이", "352820": "하이브", "383220": "F&F",
    "042700": "한미반도체", "128940": "한미약품", "241560": "두산밥캣",
    "000990": "DB하이텍", "004170": "신세계", "005440": "현대백화점",
    "006800": "미래에셋증권", "016360": "삼성증권", "039490": "키움증권",
    # 코스닥 대표 종목
    "247540": "에코프로비엠", "086520": "에코프로", "196170": "알테오젠",
    "028300": "HLB", "277810": "레인보우로보틱스", "058470": "리노공업",
    "145020": "휴젤", "066970": "엘앤에프", "191410": "이오테크닉스",
    "403000": "HPSP", "214150": "클래시스", "293490": "카카오게임즈",
    "035760": "CJ ENM", "035900": "JYP Ent.", "041510": "에스엠",
    "122870": "와이지엔터", "253450": "스튜디오드래곤", "263750": "펄어비스",
    "095340": "ISC", "112040": "위메이드", "068760": "셀트리온제약",
    "005290": "동진쎄미켐", "036830": "솔브레인", "214450": "파마리서치",
    "357780": "솔브레인홀딩스", "039200": "오스템임플란트", "034230": "파라다이스",
    "108320": "실리콘투", "048410": "현대바이오", "084370": "유진테크",
    "036930": "주성엔지니어링", "067310": "하나마이크론", "089030": "테크윙",
    "240810": "원익IPS", "095610": "테스", "131970": "두산테스나",
    "036490": "대주전자재료", "086900": "메디톡스", "141080": "리그켐바이오",
    "214370": "케어젠", "237690": "에스티팜", "053610": "프로텍",
    "064760": "티씨케이", "178920": "PI첨단소재", "213420": "덕산네오룩스",
    "065350": "신성델타테크", "319660": "피에스케이", "086450": "동국제약",
    "287410": "제이시스메디칼", "365340": "성일하이텍", "348210": "넥스틴",
    "137400": "피엔티", "215600": "신라젠", "086390": "유니테스트"
}

# S&P 500 공식 503개 전 종목 마스터 리스트
SP500_ALL_503_TICKERS = [
    "MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES", "AFL", "A", "APD", "ABNB", "AKAM", "ALB",
    "ARE", "ALGN", "ALLE", "LNT", "ALL", "GOOGL", "GOOG", "MO", "AMZN", "AMCR", "AEE", "AEP", "AXP", "AIG",
    "AMT", "AWK", "AMP", "AME", "AMGN", "APH", "ADI", "ANSS", "AON", "APA", "AAPL", "AMAT", "APTV", "ACGL",
    "ADM", "ANET", "AJG", "AIZ", "T", "ATO", "ADSK", "ADP", "AZO", "AVB", "AVY", "AXON", "BKR", "BALL",
    "BAC", "BK", "BBWI", "BAX", "BDX", "BBY", "TECH", "BIIB", "BLK", "BX", "BA", "BKNG", "BWA", "BSX",
    "BMY", "AVGO", "BR", "BRO", "BF-B", "BLDR", "BG", "BXP", "CHRW", "CDNS", "CZR", "CPT", "CPB", "COF",
    "CAH", "KMX", "CCL", "CARR", "CAT", "CBOE", "CBRE", "CDW", "CE", "COR", "CNC", "CNP", "CF", "CRL",
    "SCHW", "CHTR", "CVX", "CMG", "CB", "CHD", "CI", "CINF", "CTAS", "CSCO", "C", "CFG", "CLX", "CME",
    "CMS", "KO", "CTSH", "CL", "CMCSA", "CAG", "COP", "ED", "STZ", "CEG", "COO", "CPRT", "GLW", "CPAY",
    "CTVA", "CSGP", "COST", "CTRA", "CRWD", "CCI", "CSX", "CMI", "CVS", "DHR", "DRI", "DVA", "DAY", "DECK",
    "DE", "DELL", "DAL", "DVN", "DXCM", "FANG", "DLR", "DFS", "DG", "DLTR", "D", "DPZ", "DOV", "DOW",
    "DHI", "DTE", "DUK", "DD", "EMN", "ETN", "EBAY", "ECL", "EIX", "EW", "EA", "ELV", "EMR", "ENPH",
    "ETR", "EOG", "EPAM", "EQT", "EFX", "EQIX", "EQR", "ERIE", "ESS", "EL", "EG", "EVRG", "ES", "EXC",
    "EXPE", "EXPD", "EXR", "XOM", "FFIV", "FDS", "FICO", "FAST", "FRT", "FDX", "FIS", "FITB", "FSLR", "FE",
    "FI", "FMC", "F", "FTNT", "FTV", "FOXA", "FOX", "BEN", "FCX", "GRMN", "IT", "GE", "GEHC", "GEV",
    "GEN", "GNRC", "GD", "GIS", "GM", "GPC", "GILD", "GPN", "GL", "GDDY", "GS", "HAL", "HIG", "HAS",
    "HCA", "DOC", "HSIC", "HSY", "HES", "HPE", "HLT", "HOLX", "HD", "HON", "HRL", "HST", "HWM", "HPQ",
    "HUBB", "HUM", "HBAN", "HII", "IBM", "IEX", "IDXX", "ITW", "INCY", "IR", "PODD", "INTC", "ICE", "IFF",
    "IP", "IPG", "INTU", "ISRG", "IVZ", "INVH", "IQV", "IRM", "JBHT", "JBL", "JKHY", "J", "JNJ", "JCI",
    "JPM", "JNPR", "K", "KVUE", "KDP", "KEY", "KEYS", "KMB", "KIM", "KMI", "KKR", "KLAC", "KHC", "KR",
    "LHX", "LH", "LRCX", "LW", "LVS", "LDOS", "LEN", "LLY", "LIN", "LYV", "LKQ", "LMT", "L", "LOW",
    "LULU", "LYB", "MTB", "MRO", "MPC", "MKTX", "MAR", "MMC", "MLM", "MAS", "MA", "MTCH", "MKC", "MCD",
    "MCK", "MDT", "MRK", "META", "MET", "MTD", "MGM", "MCHP", "MU", "MSFT", "MAA", "MRNA", "MHK", "MOH",
    "TAP", "MDLZ", "MPWR", "MNST", "MCO", "MS", "MOS", "MSI", "MSCI", "NDAQ", "NTAP", "NFLX", "NEM", "NWSA",
    "NWS", "NEE", "NKE", "NI", "NDSN", "NSC", "NTRS", "NOC", "NCLH", "NRG", "NUE", "NVDA", "NVR", "NXPI",
    "ORLY", "OXY", "ODFL", "OMC", "ON", "OKE", "ORCL", "OTIS", "PCAR", "PKG", "PLTR", "PANW", "PARA", "PH",
    "PAYX", "PAYC", "PYPL", "PNR", "PEP", "PFE", "PCG", "PM", "PSX", "PNW", "PNC", "POOL", "PPG", "PPL",
    "PFG", "PG", "PGR", "PRU", "PEG", "PTC", "PSA", "PHM", "QRVO", "PWR", "QCOM", "DGX", "RL", "RJF",
    "RTX", "O", "REG", "REGN", "RF", "RSG", "RMD", "RVTY", "ROK", "ROL", "ROP", "ROST", "RCL", "SPGI",
    "CRM", "SBAC", "SLB", "STX", "SRE", "NOW", "SHW", "SPG", "SWKS", "SJM", "SNA", "SOLV", "SO", "LUV",
    "SWK", "SW", "STT", "STLD", "STE", "SYK", "SMCI", "SYF", "SNPS", "SYY", "TMUS", "TROW", "TTWO", "TPR",
    "TARGO", "TGT", "TEL", "TDY", "TFX", "TER", "TSLA", "TXN", "TXT", "TMO", "TJX", "TSCO", "TT", "TDG",
    "TRV", "TRMB", "TFC", "TYL", "TSN", "USB", "UBER", "UDR", "ULTA", "UNP", "UAL", "UPS", "URI", "UNH",
    "UHS", "VLO", "VTR", "VLTO", "VRSN", "VRSK", "VZ", "VRTX", "VTRS", "VICI", "V", "VST", "VMC", "WRB",
    "GWW", "WAB", "WBA", "WMT", "DIS", "WBD", "WM", "WAT", "WEC", "WFC", "WELL", "WST", "WDC", "WRK",
    "WY", "WMB", "WTW", "WYNN", "XEL", "XYL", "YUM", "ZBRA", "ZBH", "ZTS"
]

NASDAQ100_ALL_TICKERS = [
    "ADBE", "AMD", "ABNB", "GOOGL", "GOOG", "AMZN", "AEP", "AMGN", "ADI", "ANSS", "AAPL", "AMAT", "APP",
    "ARM", "ASML", "TEAM", "ADSK", "ADP", "AXON", "BIIB", "BKNG", "AVGO", "CDNS", "CDW", "CHTR", "CTAS",
    "CSCO", "CCEP", "CTSH", "CMCSA", "CEG", "CPRT", "CSGP", "COST", "CRWD", "CSX", "DXCM", "FANG", "DDOG",
    "DLTR", "DASH", "EA", "EXC", "FAST", "FTNT", "GEHC", "GILD", "GFS", "HON", "IDXX", "INTC", "INTU",
    "ISRG", "KDP", "KLAC", "KHC", "LRCX", "LIN", "LULU", "MAR", "MRVL", "MELI", "META", "MCHP", "MU",
    "MSFT", "MRNA", "MDLZ", "MDB", "MNST", "NFLX", "NVDA", "NXPI", "ORLY", "ODFL", "ON", "PCAR", "PANW",
    "PAYX", "PYPL", "PDD", "QCOM", "REGN", "ROP", "ROST", "SNPS", "TTWO", "TMUS", "TSLA", "TXN", "TTD",
    "VRTX", "WBD", "WDAY", "XEL", "ZS"
]

# KOSPI 핵심 100대 대형 우량주 전수조사 풀
KOSPI_100_TICKERS = [
    "005930", "000660", "373220", "207940", "005380", "000270", "068270", "105560", "005490", "035420",
    "055550", "051910", "012330", "028260", "032830", "015760", "086790", "035720", "003670", "018260",
    "000810", "323410", "010130", "034730", "017670", "011200", "009150", "030200", "010950", "003550",
    "034020", "006400", "024110", "259960", "042660", "012450", "047810", "029780", "004020", "001040",
    "090430", "078930", "000100", "000720", "005830", "161890", "097950", "033780", "011170", "028050",
    "138040", "086280", "071050", "032640", "011070", "271560", "009540", "267250", "003490", "000150",
    "001450", "180640", "008770", "006260", "007070", "014680", "009830", "329180", "402340", "377300",
    "352820", "383220", "042700", "128940", "241560", "000990", "004170", "005440", "006800", "016360",
    "039490", "000080", "004990", "005850", "007310", "010060", "011780", "012750", "014820", "016380",
    "020150", "020560", "021240", "023530", "026960", "030000", "036460", "036570", "069500", "229200"
]

# KOSDAQ 핵심 100대 주도 성장주 전수조사 풀
KOSDAQ_100_TICKERS = [
    "247540", "086520", "196170", "028300", "277810", "058470", "145020", "066970", "191410", "403000",
    "214150", "293490", "035760", "035900", "041510", "122870", "253450", "263750", "095340", "112040",
    "068760", "005290", "036830", "214450", "357780", "039200", "034230", "108320", "048410", "084370",
    "036930", "067310", "089030", "240810", "095610", "131970", "036490", "086900", "141080", "214370",
    "237690", "053610", "064760", "178920", "213420", "065350", "319660", "086450", "287410", "365340",
    "348210", "137400", "215600", "086390", "036810", "039030", "041960", "046890", "053800", "060280",
    "067160", "078600", "084990", "091990", "102710", "140410", "187870", "200130", "217730", "230360",
    "259630", "272210", "290650", "298040", "302440", "307950", "318020", "336260", "336370", "347860",
    "361390", "007390", "022100", "025980", "032500", "036010", "038540", "042000", "043150", "046120",
    "049070", "052690", "053030", "054450", "054920", "058610", "060310", "063160", "064290", "065680"
]

KOSDAQ_SET = set(KOSDAQ_100_TICKERS)

HTTP_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}


def clean_ticker(ticker: str, select_mode: str = "") -> str:
    """
    국장/미장 티커 형식 자동 정규화 (.KS / .KQ 자동 지정)
    """
    ticker_str = str(ticker).strip()
    if ticker_str.isdigit() and len(ticker_str) == 6:
        if "코스닥" in select_mode:
            return f"{ticker_str}.KQ"
        elif "코스피" in select_mode:
            return f"{ticker_str}.KS"
        else:
            if ticker_str in KOSDAQ_SET:
                return f"{ticker_str}.KQ"
            return f"{ticker_str}.KS"
    return ticker_str.replace('.', '-')


def fetch_universe_tickers(select_mode: str, raw_input_tickers: str = "") -> list:
    """
    선택된 모드에 따라 분석 대상 전 종목 명단을 수집하여 반환합니다.
    """
    tickers = []

    if select_mode == "1. S&P500":
        try:
            url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
            req = urllib.request.Request(url, headers=HTTP_HEADERS)
            with urllib.request.urlopen(req, timeout=5) as response:
                html_content = response.read()
            sp500_table = pd.read_html(io.BytesIO(html_content))[0]
            tickers = [str(t).replace('.', '-') for t in sp500_table['Symbol'].tolist()]
            safe_print(f"   [수집 완료] S&P 500 전 종목 {len(tickers)}개 실시간 수집 성공")
        except Exception:
            tickers = [t.replace('.', '-') for t in SP500_ALL_503_TICKERS]
            safe_print(f"   [마스터 로딩] S&P 500 전 종목 {len(tickers)}개 전수조사 풀 가동")

    elif select_mode == "2. nasdaq":
        try:
            url = "https://en.wikipedia.org/wiki/Nasdaq-100"
            req = urllib.request.Request(url, headers=HTTP_HEADERS)
            with urllib.request.urlopen(req, timeout=5) as response:
                html_content = response.read()
            tables = pd.read_html(io.BytesIO(html_content))
            nasdaq_tickers = []
            for table in tables:
                cols_upper = [str(c).upper() for c in table.columns]
                if 'TICKER' in cols_upper:
                    nasdaq_tickers = table.iloc[:, cols_upper.index('TICKER')].tolist()
                    break
                elif 'SYMBOL' in cols_upper:
                    nasdaq_tickers = table.iloc[:, cols_upper.index('SYMBOL')].tolist()
                    break
            tickers = [str(t).replace('.', '-') for t in nasdaq_tickers if pd.notna(t)]
            safe_print(f"   [수집 완료] NASDAQ 100 전 종목 {len(tickers)}개 실시간 수집 성공")
        except Exception:
            tickers = [t.replace('.', '-') for t in NASDAQ100_ALL_TICKERS]
            safe_print(f"   [마스터 로딩] NASDAQ 100 전 종목 {len(tickers)}개 전수조사 풀 가동")

    elif select_mode == "3. 코스피":
        tickers = KOSPI_100_TICKERS
        safe_print(f"   [마스터 로딩] 대한민국 코스피 핵심 100대 기업 전수조사 풀 ({len(tickers)}개) 가동")

    elif select_mode == "4. 코스닥":
        tickers = KOSDAQ_100_TICKERS
        safe_print(f"   [마스터 로딩] 대한민국 코스닥 핵심 100대 주도주 전수조사 풀 ({len(tickers)}개) 가동")

    elif select_mode == "5. 전체":
        tickers = [
            "MSFT", "AAPL", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "COST", "NFLX",
            "RJF", "SCHW", "CRWD", "ADSK", "CHD", "MET", "AIZ", "HSIC", "CPAY", "ANET",
            "005930", "000660", "373220", "207940", "005380", "000270", "068270", "105560", "005490", "035420",
            "247540", "086520", "196170", "028300", "277810", "058470", "145020", "066970", "191410", "403000"
        ]

    elif select_mode == "6. 직접입력":
        tickers = list(set([str(t).strip().upper() for t in raw_input_tickers.split(',') if t.strip()]))

    return tickers


def fetch_macro_data() -> dict:
    """
    Stage 0 거시경제 지표 수집:
    - VIX 지수
    - 4대 벤치마크 (S&P 500, Nasdaq, KOSPI, KOSDAQ) 최근 250일 데이터
    """
    macro_data = {
        'vix': 21.51,
        'indices': {}
    }

    try:
        vix_df = yf.Ticker('^VIX').history(period='5d')
        if not vix_df.empty and 'Close' in vix_df:
            macro_data['vix'] = float(vix_df['Close'].dropna().iloc[-1])
    except Exception:
        pass

    indices_map = {
        'S&P 500': '^GSPC',
        'Nasdaq': '^IXIC',
        'KOSPI': '^KS11',
        'KOSDAQ': '^KQ11'
    }

    for name, sym in indices_map.items():
        try:
            hist = yf.Ticker(sym).history(period='250d')
            macro_data['indices'][name] = hist
        except Exception:
            macro_data['indices'][name] = pd.DataFrame()

    return macro_data


def fetch_benchmark_close(period: str = '1y') -> pd.Series:
    """
    상대강도(RS) 계산용 벤치마크(S&P 500: ^GSPC) 종가 시리즈 반환
    """
    try:
        bm_df = yf.Ticker('^GSPC').history(period=period)
        if not bm_df.empty and 'Close' in bm_df:
            return bm_df['Close'].dropna()
    except Exception:
        pass
    return None


def fetch_all_stock_history_batch(tickers: list, select_mode: str = "", period: str = "1y") -> dict:
    """
    [핵심 최적화] yf.download를 통한 전 종목 시세 초고속 일괄 병렬 수집
    """
    clean_tickers_map = {t: clean_ticker(t, select_mode) for t in tickers}
    unique_search_tickers = list(set(clean_tickers_map.values()))

    stock_dfs = {}

    try:
        raw_data = yf.download(
            tickers=unique_search_tickers,
            period=period,
            group_by='ticker',
            threads=True,
            progress=False
        )

        for orig_t, search_t in clean_tickers_map.items():
            try:
                if len(unique_search_tickers) == 1:
                    df = raw_data.copy()
                else:
                    if search_t in raw_data.columns.levels[0]:
                        df = raw_data[search_t].dropna(subset=['Close']).copy()
                    else:
                        df = pd.DataFrame()
                stock_dfs[orig_t] = df
            except Exception:
                stock_dfs[orig_t] = pd.DataFrame()

    except Exception as e:
        safe_print(f"   [안내] 일괄 다운로드 예외({e}) -> 개별 수집 전환")
        for orig_t, search_t in clean_tickers_map.items():
            try:
                df = yf.Ticker(search_t).history(period=period)
                stock_dfs[orig_t] = df.dropna(subset=['Close']) if not df.empty else pd.DataFrame()
            except Exception:
                stock_dfs[orig_t] = pd.DataFrame()

    return stock_dfs


def fetch_stock_history(ticker: str, select_mode: str = "", period: str = "1y") -> pd.DataFrame:
    """
    개별 종목의 OHLCV 과거 데이터 수집
    """
    search_ticker = clean_ticker(ticker, select_mode)
    try:
        tk_obj = yf.Ticker(search_ticker)
        df = tk_obj.history(period=period)
        return df.dropna(subset=['Close']) if not df.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def fetch_fundamental_data(ticker: str, select_mode: str = "") -> dict:
    """
    개별 종목의 펀더멘탈(ROE, 이익성장률, 섹터, 종목명) 수집
    """
    search_ticker = clean_ticker(ticker, select_mode)
    name = NAME_DICT.get(ticker, ticker)
    sector = 'Technology'
    roe = 0.12
    growth = 0.10

    try:
        tk_obj = yf.Ticker(search_ticker)
        info = tk_obj.info

        if ticker not in NAME_DICT:
            raw_name = info.get('shortName', info.get('longName', ticker))
            if raw_name:
                name = str(raw_name).split('.')[0].split(',')[0]

        roe_val = info.get('returnOnEquity', None)
        if roe_val is not None and not pd.isna(roe_val):
            roe = float(roe_val)

        growth_val = info.get('earningsGrowth', None)
        if growth_val is not None and not pd.isna(growth_val):
            growth = float(growth_val)

        sector = info.get('sector', sector)
    except Exception:
        pass

    return {
        '티커': ticker,
        '종목명': name,
        '섹터': sector,
        'ROE': roe,
        '이익성장': growth
    }
