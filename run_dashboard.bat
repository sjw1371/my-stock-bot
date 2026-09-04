@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
echo ===================================================
echo   JTI 퀀트 주식 시스템 & 대시보드를 실행합니다...
echo ===================================================
echo.
streamlit run app.py
pause
