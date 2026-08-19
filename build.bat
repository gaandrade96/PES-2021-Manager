@echo off
REM ============================================================
REM  Compila o PES 2021 Manager em um executavel (.exe) unico,
REM  com a bola de futebol como icone.
REM
REM  IMPORTANTE: o arquivo bola_vermelha.ico precisa continuar
REM  na mesma pasta do .exe depois de compilado (e tambem se voce
REM  rodar direto o pes2021.pyw) - o programa usa ele em tempo de
REM  execucao para definir o icone da JANELA/barra de tarefas,
REM  alem de ser o icone do proprio .exe.
REM
REM  Como usar:
REM   1) Coloque este arquivo (build.bat), o pes2021.pyw novo
REM      e o bola.ico dentro da pasta "PES 2021 Manager"
REM      (a mesma pasta onde estao dados_pes2021.json, config.json
REM      e a pasta bandeiras_planas).
REM   2) De dois cliques neste build.bat.
REM   3) Ao final, o executavel estara em: dist\PES2021Manager.exe
REM ============================================================

echo Instalando o PyInstaller (se ja estiver instalado, so confirma)...
pip install pyinstaller

echo.
echo Compilando o executavel...
pyinstaller --onefile --windowed --icon=bola_vermelha.ico --name "PES2021Manager" pes2021.pyw

echo.
echo ============================================================
echo Pronto! O executavel esta em: dist\PES2021Manager.exe
echo.
echo Mova (ou copie) o PES2021Manager.exe para a pasta principal
echo "PES 2021 Manager" (junto com dados_pes2021.json, config.json
echo e bandeiras_planas), e apague as pastas "build" e "dist" e o
echo arquivo "PES2021Manager.spec" que sobraram da compilacao.
echo ============================================================
pause
