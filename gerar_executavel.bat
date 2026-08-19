@echo off
chcp 65001 >nul
title Gerando executavel - PES 2021 Manager
echo ============================================
echo   Gerando o executavel do PES 2021 Manager
echo ============================================
echo.

REM Verifica se o Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao foi encontrado no seu computador.
    echo Baixe e instale em: https://www.python.org/downloads/
    echo IMPORTANTE: marque a opcao "Add Python to PATH" durante a instalacao.
    pause
    exit /b 1
)

echo [1/3] Instalando/atualizando dependencias necessarias...
python -m pip install --upgrade pip >nul
python -m pip install --upgrade pyinstaller pillow

echo.
echo [2/3] Compilando o executavel (isso pode levar 1-2 minutos)...
if exist "bola_vermelha.ico" (
    python -m PyInstaller --onefile --windowed --icon="bola_vermelha.ico" --name "PES_2021_Manager" pes2021.pyw
) else (
    echo [aviso] bola_vermelha.ico nao encontrado nesta pasta - compilando sem icone proprio do .exe.
    python -m PyInstaller --onefile --windowed --name "PES_2021_Manager" pes2021.pyw
)

echo.
if exist "dist\PES_2021_Manager.exe" (
    echo [3/3] Pronto! Copiando o executavel para a pasta atual...
    copy /Y "dist\PES_2021_Manager.exe" "PES_2021_Manager.exe" >nul
    echo.
    echo ============================================
    echo   SUCESSO! O arquivo PES_2021_Manager.exe
    echo   foi criado nesta mesma pasta.
    echo ============================================
) else (
    echo [ERRO] Algo deu errado e o executavel nao foi gerado.
    echo Role a tela para cima e veja qual mensagem de erro apareceu.
)

echo.
pause
