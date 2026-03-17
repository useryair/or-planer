@echo off
REM OR Planer - Run web app for Computer + Mobile access
echo Starting OR Planer...
echo.

REM Auto-detect local IP address
for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /R "IPv4"') do (
    set LOCAL_IP=%%A
    goto :found
)
:found
set LOCAL_IP=%LOCAL_IP: =%

echo Open in browser:
echo   Computer : http://localhost:8501
echo   Mobile   : http://%LOCAL_IP%:8501
echo.
echo (Both must be on the same Wi-Fi network)
echo.
python -m streamlit run app.py --server.address 0.0.0.0
pause
