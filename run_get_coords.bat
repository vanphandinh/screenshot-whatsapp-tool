@echo off
echo Starting Coordinate Capture Tool...
cd /d %~dp0
call venv\Scripts\activate
python get_coords.py
pause
