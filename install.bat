@echo off
REM ============================================================
REM  Voice-Clone Studio - CAI DAT (cho may moi / nguoi khac dung)
REM  Tao venv Python 3.11 + torch + f5-tts, roi tai model ~5GB.
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo(
echo ====== Voice-Clone Studio : CAI DAT ======
echo(

REM --- Chon torch: cu124 (GPU NVIDIA, mac dinh) hoac cpu ---
if "%TORCH_VARIANT%"=="" set TORCH_VARIANT=cu124
echo [cau hinh] torch = %TORCH_VARIANT%
echo            ^(khong co GPU NVIDIA? chay:  set TORCH_VARIANT=cpu  roi chay lai install.bat^)
echo(

REM --- 1) Tao venv Python 3.11 ---
set USE_UV=0
where uv >nul 2>&1 && set USE_UV=1

if exist ".venv\Scripts\python.exe" (
  echo [1/4] .venv da ton tai - bo qua tao moi.
) else (
  if "!USE_UV!"=="1" (
    echo [1/4] Tao venv bang uv ^(tu tai Python 3.11 neu can^)...
    uv venv --python 3.11 .venv || goto :err
  ) else (
    echo [1/4] Tao venv bang py launcher ^(can Python 3.11 cai san^)...
    py -3.11 -m venv .venv 2>nul || python -m venv .venv || goto :err
  )
)

set "PY=.venv\Scripts\python.exe"

REM --- Chuoi index torch ---
if /I "%TORCH_VARIANT%"=="cpu" (
  set "TORCH_INDEX=https://download.pytorch.org/whl/cpu"
) else (
  set "TORCH_INDEX=https://download.pytorch.org/whl/%TORCH_VARIANT%"
)

REM --- 2) Cai torch + 3) cac goi con lai ---
if "!USE_UV!"=="1" (
  echo [2/4] Cai torch 2.6.0 ^(%TORCH_VARIANT%^) bang uv...
  uv pip install -p "%PY%" torch==2.6.0 torchaudio==2.6.0 --index-url !TORCH_INDEX! || goto :err
  echo [3/4] Cai f5-tts va phu thuoc...
  uv pip install -p "%PY%" -r requirements.txt || goto :err
) else (
  echo [2/4] Nang cap pip + cai torch 2.6.0 ^(%TORCH_VARIANT%^)...
  "%PY%" -m pip install --upgrade pip || goto :err
  "%PY%" -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url !TORCH_INDEX! || goto :err
  echo [3/4] Cai f5-tts va phu thuoc...
  "%PY%" -m pip install -r requirements.txt || goto :err
)

REM --- 4) Tai model ~5GB ---
echo [4/4] Tai model F5-TTS tieng Viet ^(~5GB, co resume^)...
"%PY%" download_models.py || goto :err

REM --- Kiem tra ffmpeg ---
where ffmpeg >nul 2>&1 || (
  echo(
  echo [!] Chua thay ffmpeg trong PATH. Cai bang:  winget install Gyan.FFmpeg
  echo     ^(can ffmpeg de chinh pitch/volume/normalize va xuat mp3/wav^)
)

echo(
echo ====== HOAN TAT ======
echo Chay  start.bat  de mo web UI tai http://127.0.0.1:8124/
goto :done

:err
echo(
echo [x] Cai dat gap loi - xem thong bao ben tren.
endlocal
exit /b 1

:done
endlocal
