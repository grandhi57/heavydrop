@echo off
taskkill /F /IM pythonw.exe /T
taskkill /F /IM python.exe /FI "WINDOWTITLE eq uvicorn*"
echo Deal Tracker Stopped.
pause
