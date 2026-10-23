@echo off
setlocal
pushd "%~dp0" || exit /b 1

echo Starting Charlottesville Transportation Quoter...
echo Your browser will open at http://127.0.0.1:8765
echo Keep this window open. Press Control+C here to stop the app.
echo.

py -3 --version >nul 2>&1
if not errorlevel 1 goto run_py

python -c "import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)" >nul 2>&1
if not errorlevel 1 goto run_python

python3 -c "import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)" >nul 2>&1
if not errorlevel 1 goto run_python3

echo Python 3 is needed to run the quoter.
echo Install it from https://www.python.org/downloads/windows/
echo Select the option to add Python to PATH during installation.
popd
pause
exit /b 1

:run_py
py -3 app.py
set "quoter_status=%errorlevel%"
goto finished

:run_python
python app.py
set "quoter_status=%errorlevel%"
goto finished

:run_python3
python3 app.py
set "quoter_status=%errorlevel%"

:finished
popd
if "%quoter_status%"=="0" exit /b 0
echo.
echo The quoter stopped. See any error message above.
pause
exit /b %quoter_status%
