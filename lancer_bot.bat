@echo off
chcp 65001 >nul
title Tekkit Watch
cd /d "%~dp0"

echo.
echo  =============================================
echo     Tekkit Watch - lancement du bot
echo  =============================================
echo.

rem ----- 0. Le ZIP doit avoir été extrait -----
if exist "requirements.txt" goto dossier_ok
echo  [!] Tu as lancé ce fichier depuis l'intérieur du ZIP.
echo  Ferme cette fenêtre, fais un clic droit sur le ZIP,
echo  choisis "Extraire tout..." puis "Extraire",
echo  et relance lancer_bot.bat depuis le dossier extrait.
echo.
pause
exit /b 1
:dossier_ok

rem ----- 1. Le fichier .env existe-t-il ? -----
if exist ".env" goto env_ok
copy ".env.example" ".env" >nul
echo  [!] Premier lancement : il faut remplir le fichier .env
echo.
echo  Je viens de le créer et je l'ouvre dans le Bloc-notes.
echo  1. Remplis DISCORD_TOKEN, OWNER_ID et WEBHOOK_CHANNEL_ID
echo  2. Enregistre avec Ctrl+S
echo  3. Ferme le Bloc-notes
echo  4. Relance lancer_bot.bat
echo.
start "" notepad ".env"
pause
exit /b 1
:env_ok

rem ----- 2. Trouver Python 3.12 ou plus récent -----
echo  Recherche de Python : la première fois, ça peut prendre une minute...
set "PY="
where py >nul 2>nul
if errorlevel 1 goto sans_py
py -3.13 -c "pass" >nul 2>nul && set "PY=py -3.13"
if not defined PY py -3.12 -c "pass" >nul 2>nul && set "PY=py -3.12"
if not defined PY py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul && set "PY=py -3"
:sans_py
if not defined PY python -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul && set "PY=python"
if defined PY goto python_ok
echo  [!] Python 3.12 ou plus récent est introuvable.
echo  Installe "Python Install Manager" depuis le Microsoft Store,
echo  puis ouvre une fenêtre noire : touche Windows, tape cmd, Entrée,
echo  et tape :  pymanager install 3.15
echo  Ensuite, relance lancer_bot.bat
echo.
pause
exit /b 1
:python_ok

%PY% -c "import struct, sys; sys.exit(0 if struct.calcsize('P') == 8 else 1)" >nul 2>nul
if not errorlevel 1 goto bits_ok
echo  [!] Ton Python est en 32 bits : il faut la version 64 bits.
echo  Installe "Python Install Manager" depuis le Microsoft Store,
echo  puis ouvre une fenêtre noire : touche Windows, tape cmd, Entrée,
echo  et tape :  pymanager install 3.15
echo.
pause
exit /b 1
:bits_ok

rem ----- 3. Environnement virtuel (recréé s'il est abîmé) -----
if not exist ".venv\Scripts\python.exe" goto creer_venv
".venv\Scripts\python.exe" -m pip --version >nul 2>nul
if not errorlevel 1 goto venv_ok
echo  L'environnement Python existant est abîmé : je le recrée...
rmdir /s /q ".venv"
:creer_venv
echo  Première installation : création de l'environnement Python...
echo  Ça peut prendre une minute, ne ferme pas la fenêtre.
%PY% -m venv .venv
if not errorlevel 1 goto venv_ok
echo.
echo  [!] Impossible de créer l'environnement Python.
echo      Lis l'erreur ci-dessus, puis relance lancer_bot.bat
if exist ".venv" rmdir /s /q ".venv"
pause
exit /b 1
:venv_ok

rem ----- 4. Dépendances (réinstallées si requirements.txt a changé) -----
fc /b "requirements.txt" ".venv\requirements.installe" >nul 2>nul
if not errorlevel 1 goto deps_ok
echo  Installation des dépendances : quelques minutes, beaucoup de texte en anglais.
echo  C'est normal, ne ferme pas la fenêtre.
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if not errorlevel 1 goto deps_installees
echo.
echo  [!] L'installation a échoué. Vérifie ta connexion internet,
echo      puis relance lancer_bot.bat : je repartirai de zéro.
rmdir /s /q ".venv"
pause
exit /b 1
:deps_installees
copy /y "requirements.txt" ".venv\requirements.installe" >nul
:deps_ok

rem ----- 5. Lancement (relance automatique, 5 essais maximum) -----
set "ESSAIS=0"
:lancer
echo.
echo  Bot en cours d'exécution. Ferme cette fenêtre pour l'arrêter.
echo.
".venv\Scripts\python.exe" -m bot.main
set "CODE=%errorlevel%"
if "%CODE%"=="0" goto fin
if "%CODE%"=="2" goto a_corriger
if "%CODE%"=="4" goto a_corriger_portail
if "%CODE%"=="5" goto deja_lance
rem Code 3 = plantage après un long fonctionnement normal : on remet le compteur à zéro
if "%CODE%"=="3" set "ESSAIS=0"
set /a ESSAIS+=1
if %ESSAIS% GEQ 5 goto trop_de_plantages
echo.
echo  Le bot s'est arrêté de façon inattendue, essai %ESSAIS% sur 5.
echo  Nouveau démarrage dans 10 secondes...
timeout /t 10 /nobreak >nul
goto lancer

:a_corriger
echo.
echo  [!] Corrige le problème indiqué juste au-dessus.
echo      S'il parle du token : refais "Reset Token" sur le site de Discord.
echo      J'ouvre le fichier .env : corrige-le, fais Ctrl+S, ferme son onglet,
echo      appuie sur une touche ici, puis relance lancer_bot.bat
start "" notepad ".env"
pause
exit /b 2

:a_corriger_portail
echo.
echo  [!] Ton fichier .env est bon : le réglage manquant est sur le site de Discord.
echo      Page Bot, active "Message Content Intent", clique "Save Changes",
echo      puis relance lancer_bot.bat
pause
exit /b 2

:deja_lance
echo.
echo  [!] Le bot tourne déjà : cherche la fenêtre "Tekkit Watch"
echo      dans la barre des tâches, elle est peut-être réduite.
echo      Il ne faut qu'un seul bot à la fois.
pause
exit /b 1

:trop_de_plantages
echo.
echo  [!] Le bot plante en boucle. Lis l'erreur ci-dessus
echo      et le fichier data\logs\bot.log
echo      Si l'erreur parle de python.exe introuvable :
echo      supprime le dossier .venv puis relance lancer_bot.bat
pause
exit /b 1

:fin
echo  Bot arrêté.
pause
