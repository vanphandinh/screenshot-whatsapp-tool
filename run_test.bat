@echo off
echo Running WhatsApp Bot NORMAL TEST MODE...
cd /d %~dp0
call venv\Scripts\activate
python main.py --test
pause
