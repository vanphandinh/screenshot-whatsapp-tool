@echo off
echo Running WhatsApp Bot TEST MODE...
cd /d %~dp0
call venv\Scripts\activate
python main.py --test
pause
