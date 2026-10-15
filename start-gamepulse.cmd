@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" (
  uv sync --locked
  if errorlevel 1 exit /b 1
)
if not exist "frontend\dist\index.html" (
  call npm --prefix frontend ci
  if errorlevel 1 exit /b 1
  call npm --prefix frontend run build
  if errorlevel 1 exit /b 1
)
echo GamePulse: http://127.0.0.1:8767/
rem Open the browser once the server has had a few seconds to start.
start "" /b cmd /d /c "ping -n 4 127.0.0.1 >nul 2>&1 & start "" http://127.0.0.1:8767/"
".venv\Scripts\python.exe" -m src.quality.cli serve --port 8767
