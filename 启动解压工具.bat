@echo off
rem 干净解压工具 启动器
rem 双击本文件即可打开解压工具
cd /d "%~dp0"
start "" pythonw "%~dp0干净解压工具.py" 2>nul || start "" python "%~dp0干净解压工具.py"
