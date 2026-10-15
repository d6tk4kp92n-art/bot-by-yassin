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
echo    R = le retirer
echo    F = le refaire pour ce dossier-ci
echo    A = annuler, ne rien changer
choice /c RFA /m " Ton choix"
if errorlevel 3 goto fin
if errorlevel 2 goto creer
del "%RACCOURCI%"
echo.
echo  Démarrage automatique retiré.
goto fin

:creer
if exist "%RACCOURCI%" del "%RACCOURCI%"
if not exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\" mkdir "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:RACCOURCI);" ^
  "$s.TargetPath = (Join-Path (Get-Location) 'lancer_bot.bat');" ^
  "$s.WorkingDirectory = (Get-Location).Path;" ^
  "$s.WindowStyle = 7;" ^
  "$s.Description = 'Tekkit Watch';" ^
  "$s.Save()"

if not exist "%RACCOURCI%" goto echec
echo.
echo  C'est fait ! Le bot se lancera tout seul, en fenêtre réduite,
echo  dès que tu ouvriras ta session Windows, après ton code PIN.
echo  Pour l'enlever : relance ce fichier et réponds R.
goto fin

:echec
echo  [!] Windows a refusé de créer le raccourci. Fais-le à la main :
echo      1. Le dossier Démarrage va s'ouvrir.
echo      2. Dans le dossier du bot, fais un clic droit sur lancer_bot.bat,
echo         "Afficher d'autres options", puis "Créer un raccourci".
echo      3. Fais glisser ce raccourci dans le dossier Démarrage.
explorer shell:startup

:fin
echo.
pause
