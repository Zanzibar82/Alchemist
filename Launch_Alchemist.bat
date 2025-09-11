@echo off
cd /d "%~dp0"
start /min powershell -NoExit -ExecutionPolicy Bypass -Command "cd '%CD%'; python Alchemist.py"
