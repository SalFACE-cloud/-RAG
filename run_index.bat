@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe main.py index --force > index_result.txt 2>&1
echo EXIT_CODE=%ERRORLEVEL%>> index_result.txt
