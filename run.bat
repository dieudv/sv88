@echo off
@echo Running Python script in a loop...
:loop
py main.py
timeout /t 60 >nul
goto loop
