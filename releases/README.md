# releases/

Ce dossier contient les fichiers ZIP générés localement par `build.bat`.

> **Les ZIPs sont ignorés par git** (voir `.gitignore`).  
> Pour télécharger une version, rendez-vous sur les **[GitHub Releases](https://github.com/fab-geocommuns/plugin_voirie_communale/releases)**.

## Installer une version

1. Téléchargez le ZIP depuis [GitHub Releases](https://github.com/fab-geocommuns/plugin_voirie_communale/releases)
2. QGIS → **Extensions** → **Installer/Gérer les extensions** → onglet **Installer depuis un ZIP**
3. Sélectionnez le fichier téléchargé et cliquez sur **Installer l’extension**

## Générer un ZIP localement

`powershell
.\build.bat patch   # 0.X.Y → 0.X.Y+1
.\build.bat minor   # 0.X.Y → 0.X+1.0
.\build.bat major   # 0.X.Y → X+1.0.0
`

`build.bat` compile, package, commit, crée le tag git, publie la GitHub Release et déploie dans QGIS.
