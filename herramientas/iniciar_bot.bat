@echo off
rem Arranca el bot de Tu Tiendita IA en segundo plano (sin ventana). Registro: C:\Pedidos\bot.log
start "" /min pythonw "%~dp0bot.py"
