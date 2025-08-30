@echo off
cd /d "%~dp0"
start powershell -NoExit -ExecutionPolicy Bypass -Command "cd '%CD%'; python Alchemist.py"
