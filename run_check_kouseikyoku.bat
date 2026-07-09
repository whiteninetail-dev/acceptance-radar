@echo off
cd /d %~dp0

rem --- Execute the program ---
uv run main.py

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