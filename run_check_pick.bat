@echo off
cd /d %~dp0

rem --- Pick one profile interactively and run it ---
uv run main.py --pick

rem --- Check the exit code ---
if %errorlevel% equ 0 (
    echo.
    echo =======================================
    echo [SUCCESS] Process finished successfully.
    echo The window will close in 10 seconds...
    timeout /t 10
) else (
    echo.
    echo =======================================
    echo [ERROR] Something went wrong! Check the log above.
    echo The window will close in 60 seconds...
    timeout /t 60
)
