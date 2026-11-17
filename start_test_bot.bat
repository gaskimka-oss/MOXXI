@echo off
chcp 65001 >nul
echo ========================================================
echo        ЗАПУСК ТЕСТОВОГО БОТА MOXXI (STAGING)
echo ========================================================
echo Токен: @testbotmoxxxi_bot
echo База:  data\test_moxxi.db (СТРОГАЯ ИЗОЛЯЦИЯ ОТ IRIS.DB)
echo --------------------------------------------------------
.\venv\Scripts\python.exe -u bot_test.py
pause
