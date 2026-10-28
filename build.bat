@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
REM Script pour compiler, packager et publier le plugin QGIS Voirie Communale
REM Usage : build.bat [patch|minor|major]   (defaut : patch)
REM
REM Prerequis : les notes de la version sont ecrites en tete de CHANGELOG.md
REM sous le titre "# [Non publie]" (avec accent) ; le numero et la date sont
REM renseignes automatiquement par bump_version.py.

REM Forcer l'UTF-8 pour tous les scripts Python appeles ci-dessous
REM (evite les UnicodeEncodeError sur les caracteres accentues/symboles
REM  quand la console Windows est en codepage cp1252)
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

set BUMP=%1
if "!BUMP!"=="" set BUMP=patch
if /i "!BUMP!" NEQ "patch" if /i "!BUMP!" NEQ "minor" if /i "!BUMP!" NEQ "major" (
    echo Usage : build.bat [patch^|minor^|major]
    exit /b 1
)

echo ========================================
echo  Compilation et packaging du plugin
echo ========================================
echo.

REM Recherche de git.exe (PATH systeme ou GitHub Desktop)
set GIT_EXE=
where git >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set GIT_EXE=git
) else (
    for /f "delims=" %%G in ('powershell -NoProfile -Command "Get-ChildItem \"$env:LOCALAPPDATA\GitHubDesktop\" -Recurse -Filter git.exe -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName"') do set GIT_EXE=%%G
)

REM Etape 0 : Controles, AVANT toute modification de fichier
echo [0/6] Controles avant release...
if defined GIT_EXE (
    REM Fichiers non suivis : ni commites par erreur, ni oublies dans le depot
    set UNTRACKED=
    for /f "delims=" %%F in ('!GIT_EXE! ls-files --others --exclude-standard') do (
        echo   Fichier non suivi : %%F
        set UNTRACKED=1
    )
    if defined UNTRACKED (
        echo Ajoutez ces fichiers a git, ignorez-les ou supprimez-les - build annule
        exit /b 1
    )
)
REM Syntaxe, imports internes et noms non definis de tous les modules du plugin
python package.py --check
if !ERRORLEVEL! NEQ 0 (
    echo Controles en echec - build annule
    exit /b 1
)
echo.

REM Etape 1 : Increment de version (refuse sans section "Non publie" dans CHANGELOG.md)
echo [1/6] Increment de version (!BUMP!)...
set VERSION=
for /f "delims=" %%v in ('python bump_version.py !BUMP!') do set VERSION=%%v
if not defined VERSION (
    echo Erreur lors de l'increment de version - aucun fichier modifie
    exit /b 1
)
echo Nouvelle version : !VERSION!
echo.

REM Etape 2 : Compilation
echo [2/6] Compilation des ressources et UI...
python compile_plugin.py
if !ERRORLEVEL! NEQ 0 (
    echo Erreur lors de la compilation
    exit /b 1
)
echo.

REM Etape 3 : Packaging (relance les controles sur l'UI recompilee)
echo [3/6] Creation du package ZIP...
python package.py
if !ERRORLEVEL! NEQ 0 (
    echo Erreur lors du packaging
    exit /b 1
)
echo.

REM Etape 4 : Commit, tag et push
echo [4/6] Publication sur GitHub (commit + tag)...
if not defined GIT_EXE (
    echo AVERTISSEMENT : git non trouve, etapes GitHub ignorees
    goto :deploy
)
REM Uniquement les fichiers suivis (les non suivis ont ete refuses a l'etape 0)
!GIT_EXE! add -u
!GIT_EXE! diff --cached --quiet
if !ERRORLEVEL! EQU 0 (
    echo Rien a committer - working tree propre
) else (
    python get_commit_message.py > .commit_msg.txt
    !GIT_EXE! commit -F .commit_msg.txt
    set COMMIT_ERR=!ERRORLEVEL!
    del .commit_msg.txt
    if !COMMIT_ERR! NEQ 0 (
        echo Erreur lors du commit
        exit /b 1
    )
)
REM Tag annote de version : jamais ecrase (une version publiee ne change plus)
!GIT_EXE! tag -a v!VERSION! -m "Release v!VERSION!"
if !ERRORLEVEL! NEQ 0 (
    echo Erreur : le tag v!VERSION! existe deja
    exit /b 1
)
!GIT_EXE! push origin HEAD
if !ERRORLEVEL! NEQ 0 (
    echo Erreur lors du push du commit
    exit /b 1
)
!GIT_EXE! push origin v!VERSION!
if !ERRORLEVEL! NEQ 0 (
    echo Erreur lors du push du tag
    exit /b 1
)
echo Push et tag v!VERSION! envoyes vers GitHub
echo.

REM Etape 5 : GitHub Release avec le ZIP
echo [5/6] Creation de la GitHub Release v!VERSION!...
powershell -NoProfile -Command "$v='!VERSION!'; $zip='releases\voirie_communale-' + $v + '.zip'; $title='Voirie Communale v' + $v; gh release create ('v'+$v) $zip --title $title --generate-notes; if ($LASTEXITCODE -eq 0) { Write-Host ('GitHub Release v'+$v+' creee avec le ZIP') } else { Write-Host 'Erreur lors de la creation de la GitHub Release'; exit 1 }"
echo.

:deploy
REM Etape 6 : Deploiement automatique dans QGIS
set QGIS_PLUGINS=%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\voirie_communale
echo [6/6] Deploiement vers %QGIS_PLUGINS%...
powershell -NoProfile -Command "$zip = 'd:\voirie_communale\releases\voirie_communale-!VERSION!.zip'; if (Test-Path $zip) { Expand-Archive -Path $zip -DestinationPath (Split-Path '%QGIS_PLUGINS%') -Force; Write-Host ('Deploye : ' + (Split-Path $zip -Leaf)) } else { Write-Host 'ZIP non trouve'; exit 1 }"
if !ERRORLEVEL! NEQ 0 (
    echo Erreur lors du deploiement
) else (
    echo Deploiement termine avec succes !
)

echo.
echo ========================================
echo  Termine - v!VERSION!
echo ========================================
