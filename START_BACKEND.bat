@echo off
echo Starting Crypto Signals Backend...
echo Phone URL: http://192.168.0.2:8000
echo Keep this window OPEN while using the app.
cd /d "%~dp0backend"
call .venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
