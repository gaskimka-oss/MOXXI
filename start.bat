@echo off
title MOXXI Bot Launcher [Auto-Restart Active]
chcp 65001 > nul
echo ===================================================
echo           Запуск Telegram Бота MOXXI
echo   Автоматический перезапуск при сбоях ВКЛЮЧЕН!
echo ===================================================
echo.

:loop
echo [%date% %time%] Запуск процесса бота...
.\venv\Scripts\python.exe bot.py
echo.
echo [!] Процесс бота завершился или произошел сетевой сбой (%date% %time%).
echo [!] Автоматический перезапуск через 5 секунд... (Нажмите Ctrl+C для остановки)
timeout /t 5 > nul
goto loop
