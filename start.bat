@echo off
REM Voice-Clone Studio — F5-TTS voice cloning server + web UI.
REM Model ~5GB: lan chay dau cho ~1 phut de nap. Trinh duyet TU MO khi san sang.
setlocal
cd /d "%~dp0"
if "%TTS_PORT%"=="" set TTS_PORT=8124
if "%F5_DEVICE%"=="" set F5_DEVICE=cuda

REM --- Co lap moi truong: tranh Python310 toan cuc & user-site gay loi "entry point" ---
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONNOUSERSITE=1
set PYTHONPATH=
set PYTHONHOME=
set HF_HUB_DISABLE_SYMLINKS_WARNING=1

REM --- PATH sach: DLL cua venv + System32 truoc tien, KHONG co Python310 ---
set "FFDIR=C:\Users\AD\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin"
set "PATH=%~dp0.venv\Scripts;%~dp0.venv;%~dp0.venv\Lib\site-packages\torch\lib;%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%SystemRoot%\System32\WindowsPowerShell\v1.0\;%FFDIR%"

REM --- Chong chay trung: neu da co server tren cong nay thi chi mo trinh duyet ---
netstat -ano | findstr ":%TTS_PORT% " | findstr LISTENING >nul 2>&1
if %errorlevel%==0 (
  echo [studio] Server da chay san tren cong %TTS_PORT%. Mo trinh duyet...
  start "" http://127.0.0.1:%TTS_PORT%/
  goto :end
)

echo [studio] Khoi dong F5-TTS tren cong %TTS_PORT% (device %F5_DEVICE%)
echo [studio] Dang nap model ~5GB... cho ~1 phut. Trinh duyet se TU MO khi san sang.
echo [studio] Web UI: http://127.0.0.1:%TTS_PORT%/

REM Mo trinh duyet CHI KHI /health tra 200 (tranh mo som luc model chua nap xong)
start "" /min powershell -NoProfile -WindowStyle Hidden -Command "$u='http://127.0.0.1:%TTS_PORT%'; for($i=0;$i -lt 240;$i++){ try{ if((Invoke-WebRequest -UseBasicParsing \"$u/health\" -TimeoutSec 2).StatusCode -eq 200){ Start-Process \"$u/\"; break } }catch{ Start-Sleep -Milliseconds 1500 } }"

".venv\Scripts\python.exe" "server.py"

:end
endlocal
