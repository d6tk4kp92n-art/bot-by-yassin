@echo off
chcp 65001 >nul
title Tekkit Watch
cd /d "%~dp0"

echo.
echo  =============================================
echo     Tekkit Watch - lancement du bot
echo  =============================================
echo.

rem ----- 1. Le fichier .env existe-t-il ? -----
if exist ".env" goto env_ok
if exist ".env.example" copy ".env.example" ".env" >nul
echo  [!] Il manque le fichier .env
echo.
echo  Je viens de le créer et je l'ouvre dans le Bloc-notes.
echo  Remplis DISCORD_TOKEN, OWNER_ID et WEBHOOK_CHANNEL_ID,
echo  enregistre avec Ctrl+S, ferme le Bloc-notes,
echo  puis relance lancer_bot.bat
echo.
start "" notepad ".env"
pause
exit /b 1
:env_ok

rem ----- 2. Trouver Python : de préférence 3.13 ou 3.12 -----
set "PY="
where py >nul 2>nul
if errorlevel 1 goto sans_launcher
py -3.13 -c "pass" >nul 2>nul && set "PY=py -3.13"
if not defined PY py -3.12 -c "pass" >nul 2>nul && set "PY=py -3.12"
if not defined PY py -3 -c "pass" >nul 2>nul && set "PY=py -3"
:sans_launcher
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo  [!] Python est introuvable.
    echo  Installe-le depuis https://www.python.org/downloads/
    echo  et coche bien la case "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

rem ----- 3. Environnement virtuel + dépendances -----
if exist ".venv\Scripts\python.exe" goto venv_ok
echo  Première installation : création de l'environnement Python...
%PY% -m venv .venv
if errorlevel 1 (
    echo  [!] Impossible de créer l'environnement virtuel.
    pause
    exit /b 1
)
:venv_ok

fc /b "requirements.txt" ".venv\requirements.installe" >nul 2>nul
if not errorlevel 1 goto deps_ok
echo  Installation des dépendances, ça peut prendre quelques minutes...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo  [!] L'installation a échoué. Voir le README, section Problèmes fréquents.
    echo      Astuce : installe Python 3.13, le script le choisira automatiquement.
    pause
    exit /b 1
)
copy /y "requirements.txt" ".venv\requirements.installe" >nul
:deps_ok

rem ----- 4. Lancement (relance automatique en cas de plantage) -----
:lancer
echo.
echo  Bot en cours d'exécution. Ferme cette fenêtre pour l'arrêter.
echo.
".venv\Scripts\python.exe" -m bot.main
set "CODE=%errorlevel%"
if "%CODE%"=="0" goto fin
if "%CODE%"=="2" (
    echo.
    echo  [!] Corrige le problème ci-dessus, puis relance lancer_bot.bat
    pause
    exit /b 2
)
echo.
echo  Le bot s'est arrêté de façon inattendue. Nouveau démarrage dans 10 secondes...
timeout /t 10 /nobreak >nul
goto lancer

:fin
echo  Bot arrêté.
pause
