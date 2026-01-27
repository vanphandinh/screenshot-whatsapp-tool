@echo off
echo Running WhatsApp Bot 22:00 TEST MODE...
cd /d %~dp0
call venv\Scripts\activate
python main.py --test-22h
pause
