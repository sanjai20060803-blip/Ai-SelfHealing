@echo off
echo Stopping Self-Healing Network services from this project folder...
taskkill /FI "WINDOWTITLE eq SHN AI - network_repair_working*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq SHN Backend - network_repair_working*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq SHN Dashboard - network_repair_working*" /T /F >nul 2>&1
echo Done. MongoDB is left running.
pause
