@echo off
chcp 65001 >nul
title Tekkit Watch - démarrage automatique
cd /d "%~dp0"

set "RACCOURCI=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Tekkit Watch.lnk"

if exist "%RACCOURCI%" (
    echo Le démarrage automatique est déjà installé.
    choice /c ON /m "Veux-tu le RETIRER ? O = oui, N = non"
    if errorlevel 2 goto fin
    del "%RACCOURCI%"
    echo Démarrage automatique retiré.
    goto fin
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:RACCOURCI);" ^
  "$s.TargetPath = (Join-Path (Get-Location) 'lancer_bot.bat');" ^
  "$s.WorkingDirectory = (Get-Location).Path;" ^
  "$s.WindowStyle = 7;" ^
  "$s.Description = 'Tekkit Watch';" ^
  "$s.Save()"

if exist "%RACCOURCI%" (
    echo.
    echo  C'est fait ! Le bot se lancera tout seul, en fenêtre réduite,
    echo  à chaque démarrage de Windows.
    echo  Pour l'enlever : relance ce fichier et réponds O.
) else (
    echo  [!] Impossible de créer le raccourci. Voir le README.
)

:fin
echo.
pause
