@echo off
rem Lance l'application « Audit ergonomique assisté » sous Windows.
rem Double-cliquer sur ce fichier : il installe ce qui manque la première fois, puis ouvre l'application.
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
title Audit ergonomique assisté

echo ==========================================
echo    Audit ergonomique assisté
echo ==========================================
echo.

rem --- 1. Python 3.10 ou plus récent -------------------------------------------------------------
set "PYTHON="
py -3 -c "import sys" >nul 2>nul && set "PYTHON=py -3"
if not defined PYTHON python -c "import sys" >nul 2>nul && set "PYTHON=python"
if not defined PYTHON goto :pas_de_python
%PYTHON% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 goto :python_trop_ancien

rem --- 2. Fichier de configuration .env ---------------------------------------------------------
rem La connexion au modèle se règle dans l'application, écran Réglages ; le .env reste facultatif
rem et prioritaire champ par champ, pour un déploiement sur plusieurs postes.
if not exist ".env" copy ".env.exemple" ".env" >nul

rem --- 3. Certificats de l'organisation, aussi pour l'installation des dépendances ---------------
set "CA_BUNDLE="
for /f "usebackq delims=" %%C in (`%PYTHON% scripts\lire_env.py CA_BUNDLE`) do set "CA_BUNDLE=%%C"
if defined CA_BUNDLE (
    if exist "!CA_BUNDLE!" (
        set "PIP_CERT=!CA_BUNDLE!"
    ) else (
        echo Attention : le fichier CA_BUNDLE est introuvable : !CA_BUNDLE!
        echo.
    )
)

rem --- 4. Environnement Python de l'application --------------------------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo Création de l'environnement Python, une seule fois...
    %PYTHON% -m venv .venv
    if errorlevel 1 goto :echec_venv
)
set "VPY=.venv\Scripts\python.exe"

rem --- 5. Dépendances : installées au premier lancement et quand requirements.txt change -------
fc /b "requirements.txt" ".venv\requirements.installes" >nul 2>nul
if errorlevel 1 (
    echo Installation des dépendances : quelques minutes au premier lancement...
    "%VPY%" -m pip install --upgrade pip --disable-pip-version-check --quiet
    "%VPY%" -m pip install -r requirements.txt --disable-pip-version-check
    if errorlevel 1 goto :echec_pip
    copy /y "requirements.txt" ".venv\requirements.installes" >nul
    echo.
)

rem --- 6. Lancement --------------------------------------------------------------------------------
"%VPY%" scripts\verifier_ia.py
echo.
echo L'application s'ouvre dans votre navigateur : http://localhost:8501
echo Elle n'est accessible que depuis ce poste. Pour l'arrêter, fermez cette fenêtre.
echo.
if not exist "web\dist\index.html" (
    echo L'interface de l'application est introuvable ^(dossier web\dist^).
    echo Récupérez à nouveau le dossier complet de l'application.
    echo.
    pause
    exit /b 1
)
"%VPY%" -m serveur --port 8501
echo.
echo L'application s'est arrêtée.
pause
exit /b 0

rem --- Messages d'erreur ---------------------------------------------------------------------------
:pas_de_python
echo Python est introuvable sur ce poste.
echo Installez Python 3.10 ou plus récent depuis https://www.python.org/downloads/
echo en cochant la case « Add python.exe to PATH », puis relancez start.bat.
echo.
pause
exit /b 1

:python_trop_ancien
echo La version de Python installée est trop ancienne : il faut Python 3.10 ou plus récent.
echo Installez-le depuis https://www.python.org/downloads/ puis relancez start.bat.
echo.
pause
exit /b 1

:echec_venv
echo La création de l'environnement Python a échoué.
echo Supprimez le dossier .venv s'il existe, puis relancez start.bat.
echo.
pause
exit /b 1

:echec_pip
echo L'installation des dépendances a échoué. Causes fréquentes :
echo  - pas d'accès à Internet, ou proxy d'entreprise : renseignez CA_BUNDLE dans .env ;
echo  - antivirus qui bloque l'installation.
echo Relancez start.bat une fois le problème corrigé.
echo.
pause
exit /b 1
