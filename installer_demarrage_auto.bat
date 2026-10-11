@echo off
chcp 65001 >nul
title Tekkit Watch - démarrage automatique
cd /d "%~dp0"

if exist "lancer_bot.bat" goto dossier_ok
echo  [!] Lance ce fichier depuis le dossier EXTRAIT du bot, pas depuis le ZIP.
echo.
pause
exit /b 1
:dossier_ok

set "RACCOURCI=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Tekkit Watch.lnk"

if not exist "%RACCOURCI%" goto creer
echo  Le démarrage automatique est déjà installé.
echo    O = le retirer
echo    N = le refaire pour ce dossier-ci
choice /c ON /m " Ton choix"
if errorlevel 2 goto creer
del "%RACCOURCI%"
echo.
echo  Démarrage automatique retiré.
goto fin

:creer
if exist "%RACCOURCI%" del "%RACCOURCI%"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:RACCOURCI);" ^
  "$s.TargetPath = (Join-Path (Get-Location) 'lancer_bot.bat');" ^
  "$s.WorkingDirectory = (Get-Location).Path;" ^
  "$s.WindowStyle = 7;" ^
  "$s.Description = 'Tekkit Watch';" ^
  "$s.Save()"

if not exist "%RACCOURCI%" goto echec
echo.
echo  C'est fait ! Le bot se lancera tout seul, en fenêtre réduite,
echo  à chaque démarrage de Windows.
echo  Pour l'enlever : relance ce fichier et réponds O.
goto fin

:echec
echo  [!] Impossible de créer le raccourci. Voir le README.

:fin
echo.
pause
