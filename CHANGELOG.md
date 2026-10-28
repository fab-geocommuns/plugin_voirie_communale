# [0.20.4] - 2026-10-28
### Corrigé
- **Couches perdues à la réouverture d'un projet enregistré** : après un téléchargement réseau, les couches Adresses BAN, Voirie communale/départementale DGCL, OSM Routes, MagOSM et BD TOPO restaient branchées sur un fichier temporaire en mémoire (`/vsimem/`). Un projet enregistré les perdait à la réouverture, sans aucun avertissement de QGIS. Elles sont désormais basculées vers le cache GeoPackage local juste après le téléchargement (comme MAJIC, Filaires BAL et EDIGEO), en conservant leur style, et la mémoire temporaire est libérée. Chaque téléchargement utilise aussi un fichier temporaire distinct : charger une deuxième commune ne peut plus écraser les données de la première.
- **Paramètres effacés à chaque mise à jour du plugin** : `settings.json` (regex, dernier code INSEE, cases cochées) et l'ordre des couches personnalisé étaient enregistrés dans le dossier du plugin, entièrement remplacé par le gestionnaire d'extensions à chaque mise à jour. Ils sont désormais enregistrés dans le profil QGIS (dossier `voirie_communale`). Un `settings.json` existant est repris automatiquement. Le `layer_order.json` du plugin reste l'ordre par défaut ; les couches ajoutées dans une version future sont rajoutées à la fin d'un ordre personnalisé.
- **Corse : groupe commune non réordonné** : le réordonnancement automatique ne reconnaissait que les codes INSEE à 5 chiffres ; les groupes « 2A… » / « 2B… » restaient à leur place.
- **Apostrophe dans une regex de catégorisation** : une regex contenant `'` (ex. « chemin d'exploitation ») produisait une expression QGIS invalide et la catégorisation Chemin rural / Voie communale ne s'appliquait plus. Les apostrophes sont désormais échappées.

### Modifié
- **Dépôt GitHub** : le projet est désormais hébergé sur https://github.com/fab-geocommuns/plugin_voirie_communale (metadata.txt, boîte « À propos », README des releases).
- **Fiabilisation de la publication (`build.bat`)** :
  - Les notes de version s'écrivent sous `# [Non publié]` en tête du CHANGELOG ; `bump_version.py` y inscrit lui-même le numéro et la date, et refuse de publier sans notes (fin des numéros devinés puis corrigés après coup).
  - `package.py` détecte automatiquement les modules du plugin au lieu d'une liste en dur (un module oublié rendait le ZIP inutilisable, cf. v0.17.0) et contrôle avant publication la syntaxe, les imports internes et les noms non définis (cf. régressions v0.15.18 / v0.15.19).
  - Le build s'arrête si des fichiers non suivis traînent dans le dossier, ne commite que les fichiers suivis, n'écrase plus jamais un tag existant et vérifie chaque push.

# [0.20.3] - 2026-09-09
### Corrigé
- **Filaires de voie BAL sans étiquette ni style** : contrairement aux autres couches de voies (BAN, BD TOPO tronçons, MagOSM, Voies EDIGEO), la couche « Filaires de voie BAL » n'avait jamais reçu de fonction de style — elle s'affichait avec le rendu par défaut de QGIS, sans étiquette de nom ni catégorisation Chemin rural / Voie communale. Une nouvelle méthode `apply_filaires_bal_style` (mêmes regex configurables que les autres couches) lui applique désormais le même traitement, avec étiquetage sur le champ « nom ».

# [0.20.2] - 2026-09-09
### Corrigé
- **Chargement des parcelles MAJIC : abandon complet à la première erreur réseau**. En observant la commune 05003, le serveur WFS IGN (data.geopf.fr) s'est révélé ponctuellement instable sur certains lots de la requête filtrée par idu (introduite en v0.20.0), avec des dépassements de délai (timeout) sur 1 ou 2 lots parmi une quinzaine. Le code interrompait alors tout le chargement dès la première erreur, même après avoir déjà récupéré la quasi-totalité des données — c'est ce qui donnait l'impression que « ça ne marche toujours pas » malgré le correctif précédent. Désormais :
  - Chaque lot est retenté jusqu'à 3 fois (avec un court délai entre essais) avant d'être considéré en échec.
  - Si un lot reste en échec après ses 3 essais, seules les quelques parcelles de ce lot sont manquantes — le chargement se poursuit et aboutit avec le reste des données, au lieu d'échouer intégralement.
  - Un message d'avertissement récapitule le nombre de lots concernés en fin de traitement, avec une invitation à réessayer via « Forcer le rechargement » si besoin.

# [0.20.1] - 2026-09-09
### Ajouté
- **Cache invalidé automatiquement après mise à jour du plugin** : chaque couche mise en cache (GeoPackage) enregistre désormais la version du plugin qui l'a écrite. Si le plugin a été mis à jour depuis, le cache correspondant est ignoré et les données sont retéléchargées automatiquement — au lieu de continuer à servir silencieusement des données figées par un bug corrigé depuis (comme observé pour MAJIC sur des communes déjà mises en cache avant la v0.20.0). Un message d'information récapitule les couches concernées dans ce cas. La note des paramètres (« Cache local des couches par commune ») a été mise à jour en conséquence.
- **Retour de progression pendant les téléchargements volumineux en un seul fichier** (Filaires de voie BAL : export national ~100 Mo, Voies EDIGEO cadastre : archive ZIP par sections) : la barre de progression affiche désormais le volume téléchargé (et le pourcentage si connu) en temps réel au lieu d'un message statique unique pendant toute l'opération, ainsi que l'avancement section par section pour EDIGEO.

# [0.20.0] - 2026-08-07
### Corrigé
- **Chargement des parcelles MAJIC** : sur les communes volumineuses (ex. 05001 Abriès-Ristolas : 6327 parcelles MAJIC sur 24989 parcelles cadastrales au total), le chargement pouvait sembler figé plusieurs minutes sans aucun retour visuel. Deux causes corrigées :
  - **Filtrage WFS ciblé par IDU** : le WFS IGN était auparavant paginé pour récupérer **toute la commune** avant de ne garder que les parcelles MAJIC correspondantes. Il est désormais interrogé par lots de 300 codes `idu` (filtre `CQL_FILTER ... AND idu IN (...)`), ne téléchargeant que les géométries réellement nécessaires.
  - **Feedback de progression en direct** : la barre de progression affiche désormais l'avancement page par page (attributs Koumoul) puis lot par lot (géométries WFS), au lieu d'un message statique unique pendant toute l'opération.

# [0.19.0] - 2026-08-06
### Nettoyé
- **Code mort massif retiré** suite à une revue complète du code (aucun changement de comportement) :
  - `wfs_loader.py` (1519 → 1064 lignes) : suppression de 8 méthodes jamais appelées, restes de l'ancienne architecture de chargement synchrone remplacée depuis par le chargement parallèle asynchrone (`WfsLoadTask` + `_fetch_*_to_vsimem`) : `load_bdtopo_troncons_wfs`, `load_bdtopo_routesnom_wfs`, `load_wms_epsg3857`, `load_ban_wfs`, `load_voirie_wfs`, `load_voirie_dep_wfs`, `load_osm_roads`, `load_magosm_wfs`. La branche `bbox` de `load_wfs_layer` (devenue inatteignable, plus aucun appelant vivant ne fournissant de `bbox`) ainsi que la méthode `_load_wfs_bbox` ont également été retirées ; seul le chemin `code_insee` (utilisé par `load_commune_wfs`) est conservé.
  - `styles.py` (668 → 517 lignes) : suppression du dictionnaire `MAJIC_FORMES_JURIDIQUES` (110 lignes, jamais référencé ailleurs — seul `MAJIC_GROUPES` sert réellement au rendu) et de la constante `_MAJIC_COLOR_UNKNOWN` inutilisée. Extraction de deux méthodes partagées (`_make_line_symbol`, `_apply_simple_line_labels`) pour éliminer la duplication du helper `make_line` et du bloc d'étiquetage répétés à l'identique dans `_apply_bdtopo_troncons_style`, `_apply_magosm_style` et `apply_edigeo_voies_style`.
  - `version.py` (744 → 19 lignes) : suppression du dictionnaire `VERSION_HISTORY` (dupliquait intégralement ce changelog sans jamais être affiché dans l'interface) ainsi que de la fonction `get_changelog()`, inutilisée. Les fonctions `get_version()`/`get_version_info()` sont conservées.
  - `test_regex.py` supprimé : fichier de test manuel obsolète, testant une ancienne formulation de la regex (avec gestion des pluriels) ne correspondant plus du tout aux valeurs par défaut actuelles (`SettingsDialog._DEFAULTS`).
  - Imports inutilisés retirés (`get_changelog` dans `voirie_communale.py`, `QSizePolicy` dans `voirie_communale_dialog.py`).
- Validation : `ast.parse` et `pyflakes` sans erreur sur tous les fichiers modifiés, vérification de l'absence de mojibake.

# [0.18.5] - 2026-08-05
### Modifié
- **Regex « Chemin rural » / « Voie communale »** : la valeur par défaut, jusqu'ici recopiée littéralement dans 9 endroits du code (`styles.py` ×4, `voirie_communale.py`, `wfs_loader.py` ×3, `voirie_communale_dialog.py`), est désormais centralisée dans une unique source de vérité (`SettingsDialog._DEFAULTS`). Toutes les fonctions de style et tous les points d'appel la lisent depuis là au lieu de la redéfinir, éliminant le risque de divergence entre copies (une incohérence de ce type, passée inaperçue, a d'ailleurs été corrigée au passage sur le chargement BAN). Aucun changement de comportement pour l'utilisateur.

# [0.18.4] - 2026-08-05
### Corrigé
- **Regex « Voie communale »** : retrait de la gestion des pluriels (« Voies Communales », « Chemins Communaux »...) ajoutée à tort en v0.18.3, non demandée. Seule la variante singulier « Chemin Communal » reste ajoutée, en plus de « Voie Communale » et « V.C. ». Migration automatique pour les utilisateurs ayant déjà reçu la valeur par défaut pluriel de la v0.18.3 (les regex personnalisées ne sont pas affectées).

# [0.18.3] - 2026-08-05
### Modifié
- **Regex « Voie communale »** : élargie pour reconnaître aussi les variantes « Chemin Communal(e/aux) » (ex. « Chemin Communal nº 5 »), en plus de « Voie(s) Communale(s) » et « V.C. ». Migration automatique de l'ancienne valeur par défaut vers la nouvelle au chargement des réglages (les regex personnalisées par l'utilisateur ne sont pas modifiées). Le libellé de la section des réglages passe de « Catégorisation des adresses BAN » à « Catégorisation Chemin rural / Voie communale », reflétant son usage désormais partagé par les couches BAN, BD TOPO tronçons, MagOSM et Voies EDIGEO (cadastre).

# [0.18.2] - 2026-08-05
### Ajouté
- **Voies EDIGEO (cadastre)** : style désormais catégorisé par regex (Chemin rural / Voie communale / Autre) sur le nom complet reconstitué, avec les mêmes expressions régulières (configurables via les mêmes clés de réglages `ban_regex_chemin`/`ban_regex_voie`) que celles déjà utilisées pour les couches BAN, BD TOPO tronçons et MagOSM. Auparavant la couche utilisait un style simple à trait unique.

# [0.18.1] - 2026-08-02
### Corrigé
- **Voies EDIGEO (cadastre)** : la couche `VOIEP_id` (« Dénomination de voie EDIGEO ») ajoutée en v0.18.0 a été retirée. Après vérification exhaustive sur l'ensemble des sections cadastrales d'une commune test, cette couche s'est révélée mélanger des toponymes divers (lieux-dits, bâtiments remarquables comme « Mairie »/« Poste », points cotés d'altitude, repères géodésiques) sans aucun champ permettant de distinguer un nom de voie des autres entrées. Seule la couche `ZONCOMMUNI_id` (voies, lignes) est donc conservée et chargée par la case à cocher « Voies (cadastre EDIGEO) ».

# [0.18.0] - 2026-08-02
### Ajouté
- **Voies EDIGEO (cadastre)** : nouvelle case à cocher chargeant les voies (`ZONCOMMUNI_id`) du plan cadastral vecteur EDIGEO (cadastre.data.gouv.fr), pour toutes les sections cadastrales de la commune. Le nom de voie, historiquement fragmenté sur plusieurs champs (`TEX`, `TEX2`...`TEX10`) dans le format EDIGEO, est reconstitué en un seul attribut `nom` avant l'ajout au projet. La couche est mise en cache dans le GeoPackage local (`edigeo_voies`), en Lambert-93 (EPSG:2154, le CRS natif du plan cadastral vecteur). Nouveau module `edigeo_loader.py` (mixin `EdigeoLoaderMixin`) et nouvelle méthode de style `apply_edigeo_voies_style` dans `styles.py`.

# [0.17.4] - 2026-08-02
### Corrigé
- **Cache** : la couche MAJIC chargée depuis le cache local GeoPackage conservait bien son style (v0.17.3), mais uniquement dans le cas d'un cache-miss (premier téléchargement) : la logique d'application du rendu catégorisé (par `groupe_personne`) n'était appelée que juste après le téléchargement Koumoul/WFS. Lors d'un chargement direct depuis le cache d'une session précédente (cas le plus fréquent), la couche gardait le style aléatoire par défaut de QGIS. La logique de style a été extraite en une méthode réutilisable (`apply_majic_style`) reconstruisant les catégories à partir des valeurs `groupe_personne` déjà présentes dans la couche, appelée aussi bien après téléchargement qu'après un chargement depuis le cache.

# [0.17.3] - 2026-08-02
### Corrigé
- **Cache** : la correction précédente (v0.17.2) recréait une nouvelle couche depuis le GeoPackage et ne recopiait que le renderer et l'opacité, perdant les autres aspects du style (étiquettes, mode de fusion, jointures...). La bascule vers le cache utilise désormais `QgsVectorLayer.setDataSource()` sur la couche existante : le style est conservé intégralement puisqu'il s'agit du même objet couche (même id, même renderer, mêmes labels), seule la source de données change de `memory` vers le fichier GeoPackage.

# [0.17.2] - 2026-08-02
### Corrigé
- **Cache** : la couche MAJIC (et Filaires de voie BAL) apparaissait comme « couche temporaire » dans QGIS lors d'un premier téléchargement (ou après « Forcer le rechargement »), car elle était construite avec le provider `memory`. Après écriture réussie dans le cache GeoPackage, la couche du projet est désormais rechargée depuis le fichier `.gpkg` (provider `ogr`), avec conservation du style et de sa position dans l'arbre des couches — elle n'est plus signalée comme temporaire.

# [0.17.1] - 2026-08-02
### Corrigé
- **Packaging** : `cache_manager.py` manquait dans la liste des fichiers empaquetés (`package.py`), rendant le ZIP v0.17.0 inutilisable (erreur d'import au chargement du plugin). Le fichier est désormais bien inclus dans le ZIP.

# [0.17.0] - 2026-08-02
### Ajouté
- **Cache local GeoPackage par commune** : les 10 couches vecteur par commune (Emprise communale, BAN, Filaires BAL, Voirie communale/départementale DGCL, Routes OSM, MagOSM, BD TOPO routes nommées/tronçons, MAJIC) sont désormais mises en cache automatiquement dans un fichier `voirie_{code_insee}.gpkg` stocké dans le profil QGIS de l'utilisateur. Le cache est transparent : réutilisé s'il existe, alimenté après chaque téléchargement réussi. Aucune expiration automatique — un message d'alerte s'affiche si le cache dépasse un seuil configurable (30 jours par défaut, réglable dans les Paramètres), sans jamais bloquer.
- **Bouton « Forcer le rechargement »** dans la fenêtre de chargement : ignore le cache local et retélécharge systématiquement toutes les données sélectionnées depuis leurs sources d'origine.
- Nouveau module `cache_manager.py` (mixin `CacheManagerMixin`) et nouveau paramètre `cache_warning_days`.

# [0.16.7] - 2026-08-02
### Modifié
- **README** : suppression de la section « En mode développement » (déploiement manuel via lien symbolique / `build.bat`), jugée peu utile pour les utilisateurs du plugin. L'installation depuis un ZIP reste documentée.

# [0.16.6] - 2026-08-02
### Corrigé
- **README** : ajout d'une sous-section « Filaires de voie BAL — style par défaut » précisant qu'aucun style personnalisé n'est appliqué à cette couche (style aléatoire QGIS par défaut), pour compléter la documentation des styles déjà présente pour BD TOPO, OSM, BAN et MagOSM.

# [0.16.5] - 2026-08-02
### Corrigé
- **README** : documentation de la structure du projet mise à jour (ajout de `styles.py`, `wfs_loader.py`, `layer_order.py` scindés depuis `voirie_communale.py`), ordre canonique des couches corrigé (Géofoncier en tête, MNT LiDAR HD ajouté), mention de la fonctionnalité de découpage sur emprise communale (buffer configurable), et MagOSM ajouté à la liste des couches à filtrage géographique/pagination.
- **`layer_order.py`** : les valeurs de repli (utilisées si `layer_order.json` est illisible) étaient désynchronisées — "MagOSM Routes {code_insee}" manquait de `commune_group` et "Géofoncier public" manquait de `root`. Synchronisées avec le contenu actuel de `layer_order.json`.
- **`couleurs_bdtopo.html`** : couleurs de prévisualisation obsolètes (désynchronisées de `styles.py` depuis une mise à jour de palette antérieure) — mises à jour avec les couleurs réellement utilisées, et fichier référencé depuis le README.

# [0.16.4] - 2026-08-02
### Corrigé
- **README** : ajout des liens sources manquants dans le tableau "Sources de données" — Emprise communale (Admin Express), Adresses BAN, Voirie communale/départementale DGCL, BD TOPO, OSM France (serveur de tuiles), CoSIA, BD ORTHO®, Photos aériennes historiques, SCAN 50® historique, Carte de Cassini, Carte de l'État-Major, MNT LiDAR HD (tous via cartes.gouv.fr). Waze et Plan IGN J+1 restent sans lien dédié (pas de page source officielle).

# [0.16.3] - 2026-08-02
### Corrigé
- **README** : ajout du lien source manquant pour les Filaires de voie des Bases Adresses Locales (data.gouv.fr) dans le tableau "Sources de données".

# [0.16.2] - 2026-08-02
### Modifié
- **Intitulés Voirie DGCL** : "Voirie communale (DGCL 2026)" → "Voirie communale retenue DSR 2026 (DGCL)", "Voirie départementale (DGCL 2026)" → "Voirie départementale retenue DGF 2026 (DGCL)". Uniquement les libellés de l'interface (cases à cocher) et du README ; aucun changement fonctionnel (typenames WFS et noms de couches chargées inchangés).

# [0.16.1] - 2026-08-02
### Corrigé
- **Adresse mail de contact incohérente** : les en-têtes de copyright de plusieurs modules (`voirie_communale.py`, `voirie_communale_dialog.py`, `wfs_loader.py`, `styles.py`, `layer_order.py`, `__init__.py`) ainsi que la boîte de dialogue "À propos" utilisaient `yann.schwarz@ign.fr`, tandis que `metadata.txt` et `README.md` utilisaient `yann.schwarz@gmail.com`. Uniformisé sur `yann.schwarz@gmail.com` partout.

# [0.16.0] - 2026-08-02
### Supprimé
- **Bouton "Liste des tâches" et gestion du TODO.md interne** : retiré de la barre de lancement du plugin (`LauncherDialog` ne propose plus que 4 actions : Charger des données, Numériser des données, Paramètres, À propos). Suppression complète du code associé — classe `TodoDialog`, méthode `show_todo()`, action de menu "ToDo", fichier modèle `TODO.md` du dépôt et son entrée `.gitignore`. La gestion des tâches est désormais assurée en dehors du plugin. Le fichier `TODO.md` éventuellement déjà présent dans le profil utilisateur QGIS n'est pas supprimé (non touché par cette modification).

# [0.15.23] - 2026-08-02
### Corrigé
- **Filaires de voie BAL : message d'erreur incohérent** : le popup affiché en cas d'échec ("Impossible de charger... vérifiez la connexion internet, le code INSEE...") s'affichait aussi quand la commune n'avait simplement aucune donnée BAL contribuée (cas normal, pas une erreur technique) — le journal indiquait pourtant clairement "aucune voie trouvée pour {code_insee}". `load_filaires_bal` distingue désormais explicitement les deux cas via un 3e élément de retour (`no_data`) : un message dédié et rassurant ("Aucune donnée BAL disponible pour cette commune...") s'affiche pour l'absence de données, tandis que le message d'alerte technique reste réservé aux véritables échecs réseau/parsing.

# [0.15.22] - 2026-08-02
### Ajouté
- **Nouvelle source de données** : Filaires de voie des Bases Adresses Locales (BAL) — case à cocher "Filaires de voie (BAL)" dans l'onglet Nationales, entre Adresses BAN et Parcelles MAJIC. L'export national (GeoJSON statique, ~100 Mo, sans filtre serveur) est téléchargé puis filtré côté client sur le code INSEE, à l'image de la stratégie déjà utilisée pour les parcelles MAJIC. Couche mémoire nommée `Filaires de voie BAL {code_insee}` avec champs `nom`/`commune`, style QGIS par défaut. Intégrée à l'ordre canonique des couches (`layer_order.json`).

# [0.15.21] - 2026-08-02
### Corrigé
- **Voirie DGCL 2026** : correction du `typename` WFS — `DGF_2026_:_voirie-retenue-communes` et `DGF_2026_:_voirie-retenue-departements` (underscores autour des deux-points, conformes au nommage réel du service, corrige une erreur introduite en 0.15.20 où le format `workspace:layer` classique avait été utilisé par erreur).

# [0.15.20] - 2026-08-02
### Modifié
- **Voirie DGCL** : mise à jour vers le millésime 2026 — couches WFS `DGF_2026:voirie-retenue-communes` et `DGF_2026:voirie-retenue-departements` (remplacent `DGCL.2025:voirie_communale`/`voirie_departementale`). Intitulés mis à jour dans l'interface ("Voirie communale (DGCL 2026)", "Voirie départementale (DGCL 2026)") et noms de couches chargées ("DGCL Voirie communale retenue DSR 2026", "DGCL Voirie départementale retenue DGF 2026"). `layer_order.json`/`layer_order.py` et `README.md` synchronisés.

# [0.15.19] - 2026-08-02
### Corrigé
- **Bug critique (régression du refactoring 0.15.14)** : `WfsLoadTask` (tâche d'arrière-plan utilisée pour tout chargement WFS parallèle — BAN, BD TOPO, OSM, MagOSM, etc.) n'était pas importée dans `voirie_communale.py` après son déplacement vers `wfs_loader.py`, provoquant un `NameError` dès la première tentative de chargement de couches. Import corrigé.
### Modifié
- Nettoyage des imports inutilisés détectés par analyse statique (`pyflakes`) dans `styles.py` et `wfs_loader.py` (`re`, `QgsRuleBasedLabeling`, `QgsLineSymbol`, `QgsFillSymbol`, `QgsRendererCategory`, `QgsCategorizedSymbolRenderer` au niveau module — déjà réimportés localement là où utilisés ; `time`, `QgsApplication` non utilisés dans `wfs_loader.py`).

# [0.15.18] - 2026-08-02
### Corrigé
- **Bug (régression du refactoring 0.15.14)** : `wfs_loader.py` utilisait `MAJIC_GROUPES`, `_MAJIC_GROUPE_DEFAULT_COLOR`, `QgsFillSymbol`, `QgsRendererCategory` et `QgsCategorizedSymbolRenderer` sans les importer — provoquait un `NameError` au moment d'appliquer le rendu catégorisé des parcelles MAJIC (bouton "Parcelles MAJIC"). Imports ajoutés.

# [0.15.17] - 2026-08-02
### Modifié
- **Optimisation** : factorisation de la logique commune de chargement de groupes de couches WMS (`load_cadastre_wms`, `load_geofoncier_wms`, `load_cosia_wms` dans `wfs_loader.py`) dans une méthode partagée `_load_wms_layer_group` — création du groupe, boucle de chargement avec vérification `isValid()`, collecte des erreurs. Réduit la duplication de code (~140 lignes économisées) sans changement de comportement.

# [0.15.16] - 2026-08-02
### Modifié
- **Optimisation** : gestion des exceptions resserrée sur les appels réseau (`urllib`) et de parsing JSON dans `wfs_loader.py`, ainsi que sur les lectures/écritures de fichiers (`layer_order.json`, `settings.json`, `TODO.md`) — `except Exception` remplacé par des types précis (`urllib.error.URLError`, `OSError`, `json.JSONDecodeError`, `ValueError`). Les quelques frontières volontairement larges restantes (thread d'arrière-plan QGIS, opérations géométriques complexes) sont désormais documentées par un commentaire expliquant pourquoi.

# [0.15.15] - 2026-08-02
### Modifié
- **Optimisation** : suppression de la boucle d'attente active (`time.sleep(0.05)` en boucle) lors du chargement parallèle des couches WFS/WMS — remplacée par une boucle d'événements Qt (`QEventLoop`) qui se termine directement au signal de fin de tâche, sans scruter le CPU inutilement.

# [0.15.14] - 2026-08-02
### Modifié
- **Refactoring interne** : `voirie_communale.py` (~3250 lignes) scindé en modules dédiés — `styles.py` (symbologie BD TOPO/BAN/OSM/MagOSM), `wfs_loader.py` (chargement réseau WFS/WMS/XYZ) et `layer_order.py` (ordonnancement et regroupement des couches). `voirie_communale.py` ne contient plus que l'orchestration du plugin. Aucun changement fonctionnel pour l'utilisateur.
- `package.py` et `build.bat` mis à jour pour inclure/vérifier les nouveaux modules.

# [0.15.12] - 2026-04-04
### Modifié
- **MagOSM** : catégorie *Voie communale* (residential) fusionnée dans *Desserte* — Desserte couvre désormais `residential`, `service`, `living_street`. `unclassified` classé dans *(autre)*.
- **MagOSM** : catégorie *Chemin rural* scindée en *Chemin* (`track`, `path`, `bridleway`) et *Sentier* (`footway`, `steps`, pointillés).

# [0.15.11] - 2026-04-04
### Modifié
- **MagOSM** : harmonisation des couleurs avec la palette BD TOPO — Autoroute `#f26119`, Nationale `#f2a824`, Départementale `#F2D7A2`, Route intercommunale `#2db9fc`, Desserte `#ededed`. Renommage *Desserte locale* → *Desserte*.

# [0.15.10] - 2026-04-04
### Modifié
- **BD TOPO tronçons** : catégorie *Sentier* affichée en pointillés (`line_style: dash`).

# [0.15.9] - 2026-04-04
### Modifié
- **BD TOPO tronçons** : mise à jour de la palette de couleurs — Autoroute `#f26119`, Nationale `#f2a824`, Départementale `#F2D7A2`, Route intercommunale `#2db9fc`, Desserte `#ededed`.

# [0.15.8] - 2026-04-04
### Corrigé
- **BD TOPO tronçons** : catégorie *Liaison locale* repositionnée après *Route intercommunale* dans l'ordre des règles.

# [0.15.7] - 2026-04-04
### Modifié
- **BD TOPO tronçons** : renommage *Chemin rural* → *Chemin*, *Desserte locale* → *Desserte*.
- **BD TOPO tronçons** : ajout de la catégorie *Liaison locale* pour `importance = 4` (anciennement inclus dans *Départementale*).
- **BD TOPO tronçons** : *Départementale* restreinte à `importance = 3` uniquement.

# [0.15.6] - 2026-04-03
### Modifié
- **BD TOPO tronçons** : catégorie *Voie communale* (nature=Rond-point) supprimée. Le Rond-point est désormais intégré à *Desserte locale* (nature = Route à 1 chaussée OR Route à 2 chaussées OR Rond-point).

# [0.15.5] - 2026-04-03
### Modifié
- **BD TOPO tronçons** : catégorie *Piste cyclable* supprimée des règles.
- **BD TOPO tronçons** : règle par défaut `(autre)` supprimée (les éléments non catégorisés ne sont plus affichés).

# [0.15.4] - 2026-04-03
### Modifié
- **BD TOPO tronçons** : règle regex *Chemin rural (nom)* enrichie — déclenche aussi quand `cpx_classement_administratif = 'Chemin rural'`.
- **BD TOPO tronçons** : catégorie *Chemin rural* scindée en *Chemin rural* (nature=Chemin, épaisseur 0.5) et *Sentier* (nature=Sentier, épaisseur 0.4).

# [0.15.3] - 2026-04-03
### Modifié
- **BD TOPO tronçons** : fusion des trois blocs (cpx, importance, nature) en une seule liste `categories` avec une condition combinée par catégorie sémantique.

# [0.15.2] - 2026-04-03
### Modifié
- **BD TOPO tronçons** : refactoring interne — `cpx_map`, `importance_map` et `nature_map` restructurés avec des listes de valeurs groupées (ex. Chemin rural = [Chemin, Sentier], Desserte locale = [Route à 1 chaussée, Route à 2 chaussées]).

# [0.15.1] - 2026-04-03
### Modifié
- **BD TOPO tronçons** : premier jet de la symbologie PLAN.IGN avec les trois blocs séparés (cpx / importance / nature).

# [0.15.0] - 2026-04-03
### Modifié
- **Harmonisation des couleurs PLAN.IGN** : toutes les couches vecteur utilisent désormais la palette de couleurs intérieures PLAN.IGN `standard.json` au niveau de zoom 15 (\u2248 1:10 000).
- **BD TOPO tron\u00e7ons** : la symbologie applique d\u00e9sormais une cha\u00eene de priorit\u00e9 : (1) `cpx_classement_administratif`, (2) `importance` 1-4, (3) `nature` en fallback si `importance \u2265 5`.
- **Nouvelles cat\u00e9gories** : *Route intercommunale* (`#FCF0A8`) et *Desserte locale* (`#FAEDC8`) dans toutes les m\u00e9thodes de style.
- **MagOSM** : `tertiary`/`tertiary_link` \u2192 Route intercommunale ; `unclassified`/`service`/`living_street` \u2192 Desserte locale ; `track`/`path`/`footway`/`bridleway`/`steps` \u2192 Chemin rural ; `cycleway` \u2192 Piste cyclable.
- **BAN** : marqueurs Chemin rural `#8C7274`, Voie communale `#B4B4B4`.
- **OSM** : `CE%` et `R%` \u2192 `#8C7274` ; `C%` \u2192 `#FCF6B5`.

# [0.14.9] - 2026-04-03
### Corrigé
- **Pagination WFS** : la condition d'arrêt de pagination utilise désormais `numberMatched` / `numberReturned` fournis par WFS 2.0 quand disponibles. Évite une requête réseau superflue en fin de série. Fallback sur l'ancien comportement (`len(batch) < page_size`) si `numberMatched` est absent ou `"unknown"` (applicable aux 4 méthodes de pagination : `_fetch_wfs_paginated_to_vsimem`, `_fetch_magosm_to_vsimem`, et leurs équivalents synchrones).
- **`bump_version.py`** : le remplacement du bloc `changelog=` dans `metadata.txt` passe désormais par une lambda dans `re.sub`, ce qui évite l'erreur `bad escape` lorsque le CHANGELOG contient des caractères spéciaux regex (ex. `\d`, `\b`).

# [0.14.7] - 2026-04-03
### Corrigé
- **Zoom** : lors du chargement d'un WMS global (Géofoncier, PLAN IGN, etc.) sur une commune absente du projet, la couche commune est désormais téléchargée silencieusement pour permettre le zoom. Si la commune est déjà présente, elle est réutilisée sans requête supplémentaire.

# [0.14.6] - 2026-04-03
### Corrigé
- **Zoom** : suppression du `zoomToFullExtent()` de fallback qui dézoomait sur le monde entier quand aucune couche commune n'était disponible. La vue reste inchangée dans ce cas.

# [0.14.5] - 2026-04-03
### Corrigé
- **Insertion dans les groupes** : tous les `addMapLayer(layer)` sans `False` convertis en `addMapLayer(layer, False)` + `layerTreeRoot().addLayer(layer)` pour bypasser le `QgsLayerTreeRegistryBridge`. Corrige le bug où les couches d'une nouvelle commune étaient insérées dans le groupe Géofoncier public après un réordonnancement.

# [0.14.4] - 2026-04-03
### Modifié
- **Ordre canonique** : `Géofoncier public` déplacé en tête de `layer_order.json`, avant `__COMMUNE_GROUP__`, pour qu'il reste toujours au-dessus de tous les groupes communes.

# [0.14.3] - 2026-04-03
### Corrigé
- **Ordre canonique multi-communes** : `_reorder_layers` détecte désormais tous les groupes communes présents (préfixe INSEE `^\d{5}`) et les repositionne ensemble. La commune courante se retrouve en tête, les précédentes en dessous, et les WMS globaux toujours sous tous les groupes communes.

# [0.14.2] - 2026-04-03
### Ajouté
- **Skip WMS globaux déjà présents** : lors du chargement d'une nouvelle commune, les WMS et groupes globaux déjà dans le projet (Waze, OSM France, CoSIA, BD ORTHO, MNT LiDAR, PLAN IGN, Géofoncier, scans historiques, photos aériennes) ne sont plus rechargés. Ils sont réutilisés tels quels, sans requête réseau ni étape supplémentaire dans la barre de progression.
### Ajouté
- Méthodes utilitaires : `_layer_exists_by_name`, `_get_layers_by_name`, `_group_exists_by_name`, `_get_group_layers`.

# [0.14.1] - 2026-04-02
### Corrigé
- **Progression** : les `QMessageBox` d'avertissement (OSM sans route C/R, MAJIC introuvable) sont désormais différés après `progress.close()` via une liste `deferred_warnings`. La barre de progression se ferme toujours proprement.

# [0.14.0] - 2026-04-02
### Ajouté
- **Chargement WFS parallèle** : les 7 couches WFS (BAN, Voirie communale, Voirie départementale, OSM Routes, MagOSM, BD TOPO Routes nommées, BD TOPO Tronçons) sont désormais téléchargées simultanément via `QgsTask` + `QgsTaskManager`. La barre de progression avance au fil des completions grâce au signal `taskDone`.
- Nouvelle classe `WfsLoadTask(QgsTask)` avec signal `taskDone(task)`.
- Nouvelles méthodes background-safe : `_fetch_wfs_paginated_to_vsimem`, `_fetch_wfs_bbox_to_vsimem`, `_fetch_magosm_to_vsimem`, `_fetch_osm_roads_to_vsimem`, `_make_layer_from_vsimem`.
### Ajouté
- **`build.bat`** : vérification de la syntaxe Python (`ast.parse`) ajoutée en étape 0, avant le bump de version. Un échec de syntaxe annule le build sans incrémenter la version.
### Modifié
- `_apply_bdtopo_routesnom_style` extrait en méthode dédiée (était inline dans `load_bdtopo_routesnom_wfs`).

# [0.13.10] - 2026-04-02
### Corrigé
- **Ordre canonique** : `Géofoncier public` ajouté dans `layer_order.json` en tête des items racine (après le groupe commune).

# [0.13.9] - 2026-04-02
### Corrigé
- **Géofoncier public** : déplacé dans l'onglet "Plans à charger" → "Actuels" (c'est une couche WMS raster, pas une donnée vecteur).

# [0.13.8] - 2026-04-02
### Ajouté
- **Géofoncier public** : nouvelle case à cocher "Géofoncier public (RFU + Plans d'alignement)" dans l'onglet "Nationales". Charge en WMS dans un groupe dédié les couches `RFU_LIMITES`, `RFU_SOMMETS`, `PLANS_EMPRISES`, `PLANS_LIGNES`, `PLANS_LOCALISANTS` depuis le service Géofoncier (OGE, accès libre, EPSG:2154).

# [0.13.7] - 2026-03-07
### Corrigé
- **Journal des messages QGIS** : toutes les entrées `logMessage` utilisaient deux tags distincts (`"VoirieCommunale"` et `"VoirieCommunale"`). Uniformisation sur `"VoirieCommunale"` (53 occurrences corrigées).

# [0.13.6] - 2026-03-07
### Modifié
- **Interface** : la section "Données à charger" est maintenant organisée en 3 onglets — **Nationales** (toutes les couches existantes : Admin Express, BD TOPO, OSM, MagOSM, DGCL, BAN, MAJIC), **Locales** (vide, prévu pour des données locales), **Autres** (vide, réservé).

# [0.13.5] - 2026-03-07
### Modifié
- **Regex BAN chemin rural** : réécriture pour couvrir toutes les abréviations courantes (`ch`, `che`, `chem`, `chin`, `chemin`, `cheminement`, `sen`, `sente`, `sentier`) avec suffixe rural tronqué (`r`, `ru`, `rur`, `ral`, `rle`, `rural`, `rurale`), plus point optionnel entre préfixe et suffixe. Ancienne regex : `(?i)(che(?:min)?|sen(?:tier)?) rural|\bC\.?R\.?\b`.
- **Regex BAN voie communale** : réécriture symétrique couvrant les préfixes `voi`/`voie`, `ch`→`cheminement`, `rout`/`route` et les suffixes communal tronqués (`c`, `com`, `commun`, `communal`, `communale`, `cal`, `cale`, `cle`). Ancienne regex : `(?i)(voi(?:e)?) (com(?:munale)?)|\bV\.?C\.?\b`.
- Mise à jour dans `voirie_communale.py` (3 occurrences) et `settings.json` (valeurs par défaut).

# [0.13.4] - 2026-03-07
### Ajouté
- **`build.bat`** : crée un tag `vX.Y.Z` après chaque commit et une GitHub Release avec le ZIP attaché (`gh release create --generate-notes`). Requiert le GitHub CLI (`gh`) installé et authentifié (`gh auth login`).
### Modifié
- **`metadata.txt`** : `name` corrigé en `Voirie Communale` (au lieu de `voirie_communale`), champ `tags` ajouté (voirie, commune, chemin rural…).

# [0.13.3] - 2026-03-07
### Corrigé
- **README** : MagOSM Routes ajouté dans l'ordre canonique, le tableau des couches vectorielles, la section style et la table des services.

# [0.13.2] - 2026-03-07
### Corrigé
- **Ordre canonique** : `MagOSM Routes {code_insee}` ajouté dans `layer_order.json`, juste après `OSM Routes {code_insee}`.

# [0.13.1] - 2026-03-07
### Ajouté
- **Réseau routier OSM via MagOSM** : nouvelle case à cocher "Réseau routier OSM (MagOSM)" qui charge la couche `magosm:highways_line` depuis le WFS public de Magellium (`https://magosm.magellium.com/geoserver/ows`). Le chargement est paginé (500 entités/page, timeout 180 s) pour s'adapter à la lenteur du service. Le style est calqué sur BD TOPO tronçons : règles regex CR/VC prioritaires sur le champ `name`, puis catégorisation par valeur du champ `highway` (motorway → steps), étiquettes sur `name`.

# [0.13.0] - 2026-03-07
### Ajouté
- **Paramètres dans un fichier JSON** : les paramètres du plugin (précédemment stockés dans le registre Windows via `QgsSettings`) sont désormais persistés dans un fichier `settings.json` local au dossier du plugin. Le fichier est UTF-8, lisible et éditable manuellement, et se crée automatiquement au premier usage à partir des valeurs par défaut (`_DEFAULTS`). Il n'est ni inclus dans le ZIP ni versionné dans git, ce qui évite d'écraser les réglages utilisateur lors d'une mise à jour et d'exposer des données personnelles (`last_insee`, `checked_layers`) dans le dépôt.

# [0.12.11] - 2026-03-07
### Modifié
- **Stockage des paramètres** : `settings.json` déplacé du profil QGIS vers le dossier du plugin, pour être partagé (versionné git). Le fichier est intégré au package ZIP et déployé avec le plugin. Au premier accès, toutes les clés manquantes sont complétées avec leurs valeurs par défaut (y compris `ban_regex_chemin` et `ban_regex_voie` même sans jamais ouvrir le dialogue Paramètres). Le dictionnaire `_DEFAULTS` centralise toutes les valeurs par défaut.

# [0.12.10] - 2026-03-07
### Modifié
- **Stockage des paramètres** : `QgsSettings` (registre Windows) remplacé par un fichier `settings.json` dans le profil QGIS (`<profil>/voirie_communale/settings.json`). Le fichier est UTF-8, indenté, lisible et éditable manuellement. Même emplacement que `TODO.md`. L'API interne `SettingsDialog.get()`/`set()` est inchangée.

# [0.12.9] - 2026-03-07
### Modifié
- **Étiquettes BAN** : expression `"numero" || ' ' || "nom_voie"` au lieu du seul champ `nom_voie`.

# [0.12.8] - 2026-03-07
### Corrigé
- **Étiquettes BAN** : `QgsRuleBasedLabeling` avec filtres `regexp_match` remplacé par `QgsVectorLayerSimpleLabeling` (même approche que BD TOPO tronçons). Le renderer catégorise déjà les entités — les étiquettes n'ont pas à refiltrer par regex.

# [0.12.7] - 2026-03-07
### Corrigé
- **Message de fin de chargement absent** : le message récapitulatif n'était affiché que si plusieurs sources étaient chargées (`len(results) > 1`). Il est désormais affiché pour n'importe quel chargement, y compris BAN seule.
- **Légende BAN : expression regex visible** : `QgsCategorizedSymbolRenderer` avec une expression CASE WHEN affichait la regex entière comme titre dans le panneau des couches. Remplacé par `QgsRuleBasedRenderer` (même approche que BD TOPO tronçons) : la légende n'affiche plus que les libellés "Chemin rural", "Voie communale", "Autre".

# [0.12.6] - 2026-03-07
### Corrigé
- **Catégorisation BAN/BD TOPO** : expression QGIS `regexp_match(field, '...')` interprète `\b` comme retour arrière et supprime `\`, rendant la regex invalide (ex. `\bC\.?R\.?\b` → `?C??R???`). Correction : les backslashes sont doublés avant intégration dans l'expression (`_qgis_expr_regex`).
- **Regex corrompue en QgsSettings** : si la valeur stockée est invalide (corruption antérieure à v0.12.5), elle est automatiquement restaurée au défaut — dans `SettingsDialog.__init__` (corrige le champ avant affichage) et dans `_get_regex_setting` (corrige à l'utilisation en log + reset).

# [0.12.5] - 2026-03-07
### Corrigé
- **Regex corrompues depuis QgsSettings** : `SettingsDialog.get()` sans `value_type` laissait Qt inférer le type, ce qui corrompait les backslashes (`\b`, `\.`) lors de la lecture sur Windows. Corrigé : le type est désormais automatiquement déduit depuis la valeur par défaut (ex. `str` si le défaut est une chaîne).

# [0.12.4] - 2026-03-07
### Corrigé
- **Paramètres** : validation des expressions régulières (regex chemin/voie) avant sauvegarde. Un message d'erreur explicite est affiché si la regex est invalide, avec focus automatique sur le champ fautif.

# [0.12.2] - 2026-03-07
### Corrigé
- **Clip par emprise communale** : la couche mémoire était invalide car `geometryDisplayString()` retourne `"Line"` au lieu de `"LineString"` attendu par le provider mémoire. Corrigé avec `QgsWkbTypes.displayString(layer.wkbType())`. Ajout d'une garde `isValid()` avant remplacement dans le projet.

# [0.12.0] - 2026-03-07
### Ajouté
- **Paramètres** : option "Découper les couches sur l'emprise communale" avec buffer configurable (0–10 000 m, défaut 25 m). Les couches filtrées par BBOX (Voirie comm., Voirie dép., OSM Routes, BD TOPO Routes nommées, BD TOPO Tronçons) sont découpées après chargement via `_clip_layer_to_commune()`.
- `_clip_layer_to_commune()` : filtre les entités intersectant le buffer communal (calcul en EPSG:2154 pour être métrique, puis transformé dans le CRS de la couche).
- `QSpinBox` ajouté aux imports de `voirie_communale_dialog.py` ; clés QgsSettings `clip_to_commune` et `clip_buffer_m`.

# [0.11.10] - 2026-03-06
### Corrigé
- Bug : l'emprise communale était re-téléchargée à chaque chargement de couche BBOX (Voirie, OSM, BD TOPO) même si la couche `Commune {code_insee}` existait déjà dans le projet. Fix : détection préalable (`commune_reuse`) avec réutilisation de la couche existante.
# [0.10.6] - 2026-03-04
### Modifié
- Ordre canonique des couches : BD TOPO → Voirie comm. → Voirie dép. → OSM Routes → BAN → MAJIC → Commune → PLAN IGN → Waze → OSM France → Cadastre → BD ORTHO® → 8×Photos → SCAN 50® → Cassini → État-Major.
# [0.10.5] - 2026-03-04
### Ajouté
- Couche **OSM France** (tuiles XYZ `openstreetmap.fr`) comme fond de plan raster, avec case à cocher dédiée.
# [0.10.4] - 2026-03-03
### Ajouté
- Incrément de version automatique via `bump_version.py` (`build.bat patch|minor|major`).
- Message de commit git extrait automatiquement depuis `CHANGELOG.md` via `get_commit_message.py`.
### Supprimé
- `build.sh` (Linux) — non maintenu, supprimé.
- `compile_simple.py`, `QUICKSTART.md`, `espacecoStyles/` — fichiers obsolètes.
# [0.10.3] - 2026-03-03
### Ajouté
- **Paramètres** : bouton activé dans la barre de lancement. `SettingsDialog` avec deux options : *Zoom automatique* et *Réordonnancement automatique des couches* après chargement.
- Mémorisation automatique du dernier code INSEE et de la sélection des couches (à chaque chargement réussi).
- Restauration automatique du code INSEE et des cases cochées à l'ouverture du dialogue de chargement.
### Corrigé
- Doublon `launcher.show()` dans `run()` supprimé.
# [0.10.2] - 2026-03-03
### Corrigé
- **ToDo** : erreur `'TodoDialog' object has no attribute '_on_modified'` lors de l'enregistrement — méthode `_on_modified()` manquante ajoutée.
# [0.10.1] - 2026-03-03
### Ajouté
- **Barre de lancement** : le bouton du plugin ouvre désormais une barre d'accès rapide avec 5 boutons : *Charger des données*, *Numériser des données* (à venir), *Liste des tâches*, *Paramètres* (à venir), *À propos*. Classe `LauncherDialog` ajoutée dans `voirie_communale_dialog.py`.
# [0.9.81] - 2026-03-03
### Note
- Version intermédiaire fusionnée dans 0.10.1.
# [0.9.80] - 2026-03-01
### Corrigé
- **MNT LiDAR HD** : bloc de chargement manquant dans `validate_and_load()` (même régression que PLAN IGN J+1 en v0.9.77). Remplacement de `IGNF:WGS84G` par `EPSG:4326` (CRS reconnu par QGIS).
- BD ORTHO® 20 cm et PLAN IGN J+1 migrés vers `_load_wms_layer()` dans les blocs de chargement.
# [0.9.79] - 2026-03-01
### Ajouté
- Case à cocher **MNT LiDAR HD** (`IGNF_LIDAR-HD_MNT_ELEVATION.ELEVATIONGRIDCOVERAGE.SHADOW`) dans "Plans à charger" : charge le modèle numérique de terrain issu du LiDAR HD via le WMS IGN Géoplateforme (CRS `IGNF:WGS84G`).
### Technique
- Refactorisation : `load_scan_historique_wms()` et `load_wms_epsg3857()` délèguent désormais à une méthode générique `_load_wms_layer(typename, display_name, crs)`, éliminant la duplication de code.
# [0.9.78] - 2026-03-01
### Corrigé
- **PLAN IGN J+1** absent de l'ordre canonique des couches : ajouté juste avant Waze.
# [0.9.77] - 2026-03-01
### Corrigé
- **PLAN IGN J+1** : correction du chargement — la couche ne déclarant que `EPSG:3857` dans les capacités WMS IGN, le chargement utilisait un CRS non supporté (`EPSG:2154`) rendant la couche invalide. Ajout de la méthode `load_wms_epsg3857()` dédiée. QGIS reprojecte côté client.
- Correctif : bloc de chargement `plan_ign_checked` manquant dans `validate_and_load()` (oubli lors de v0.9.76).
# [0.9.76] - 2026-03-01
### Ajouté
- Case à cocher **PLAN IGN J+1** (`GEOGRAPHICALGRIDSYSTEMS.MAPS.BDUNI.J1`) dans "Plans à charger" : charge le plan topographique IGN en contenu J+1 via le WMS IGN Géoplateforme.
# [0.9.75] - 2026-03-01
### Ajouté
- Case à cocher **BD ORTHO® 20 cm** (`HR.ORTHOIMAGERY.ORTHOPHOTOS`) dans "Plans à charger" : charge l'orthophotographie haute résolution 20 cm via le WMS IGN Géoplateforme.
# [0.9.74] - 2026-03-01
### Modifié
- Mentions `(Licence Ouverte 2.0)` et `(ODbL)` retirées de tous les libellés des cases à cocher du dialogue.
# [0.9.73] - 2026-03-01
### Modifié
- **Photographies aériennes historiques** converti de bouton en case à cocher, intégrée dans "Tout sélectionner/Désélectionner". Quand cochée, le dialogue de choix des périodes s'ouvre à l'appui de "Charger les données", les périodes sélectionnées sont chargées dans la barre de progression comme les autres sources.
# [0.9.72] - 2026-03-01
### Ajouté
- Dialogue Photos aériennes : 5 nouvelles périodes ajoutées (2000-2005, 2006-2010, 2011-2015, 2016-2020, 2021-2023) via `ORTHOIMAGERY.ORTHOPHOTOS{periode}` sur la Géoplateforme IGN.
# [0.9.71] - 2026-03-01
### Ajouté
- Bouton **Photographies aériennes historiques...** dans la section Plans à charger : ouvre un dialogue de sélection avec les 3 périodes IGN Géoplateforme (1950-1965, 1965-1980, 1980-1995). Chargement WMS immédiat à la validation, indépendant du bouton principal.
# [0.9.70] - 2026-03-01
### Modifié
- Couche OSM renommée `OSM Routes {code_insee}` (suppression du suffixe `(C/R)`).
# [0.9.69] - 2026-03-01
### Modifié
- Ordre canonique : **Waze** déplacée au-dessus de Cadastre.
# [0.9.68] - 2026-03-01
### Modifié
- Ordre canonique : **Parcelles MAJIC** déplacées entre Adresses BAN et Commune.
# [0.9.67] - 2026-03-01
### Ajouté
- Réordonnancement automatique des couches dans le panneau après chargement, quel que soit l'ordre de cobhage des cases. Ordre canonique (haut → bas) : Parcelles MAJIC → OSM → BD TOPO → Voirie comm. → Voirie dép. → BAN → Commune → Cadastre → SCAN 1950 → Cassini → État-Major → Waze. Méthode `_reorder_layers(code_insee)`.
# [0.9.66] - 2026-03-01
### Corrigé
- Recherche de la couche `Commune {code_insee}` dans le projet : remplacement de `startswith` par `==` pour éviter les faux positifs si plusieurs couches ont un nom proche (ex. deux communes différentes dont l'une est préfixe de l'autre).
# [0.9.65] - 2026-03-01
### Corrigé
- Zoom post-chargement : quand aucune commune n'était cochée (ex. chargement de Waze seul), le zoom tombait en `zoomToFullExtent()` (monde entier). Désormais, avant ce fallback, on recherche une couche `Commune {code_insee}` déjà présente dans le projet pour zoomer dessus.
# [0.9.64] - 2026-03-01
### Modifié
- Case **Tuiles Waze Editor** renommée en **Waze**.
# [0.9.63] - 2026-03-01
### Ajouté
- Case **Tuiles Waze Editor** dans Plans à charger : charge les tuiles XYZ `https://www.waze.com/row-tiles/editor/roads/{z}/{x}/{y}/tile.png` comme fond de plan raster.
- Méthode générique `load_xyz_tile_layer(url, display_name, zmin, zmax)` utilisable pour tout service XYZ.
# [0.9.62] - 2026-03-01
### Supprimé
- Case **Surfaces non agricoles RPG** (SNA) retirée — la source n'est pas disponible et surchargement inutile.
# [0.9.61] - 2026-03-01
### Ajouté
- **SCAN 50® 1950** (`GEOGRAPHICALGRIDSYSTEMS.MAPS.SCAN50.1950`) ajouté dans la section Plans à charger.
# [0.9.60] - 2026-03-01
### Ajouté
- Section **Plans à charger** : cases **Carte d'État-Major IGN (1820-1866)** et **Carte de Cassini (XVIIIe siècle)**, chargées via WMS Géoplateforme IGN (`data.geopf.fr/wms-r`).
# [0.9.59] - 2026-03-01
### Modifié
- "Tout sélectionner / Désélectionner" déplacé au-dessus du label "Données à charger".
# [0.9.58] - 2026-03-01
### Modifié
- Case **Cadastre** déplacée de la section "Données à charger" vers la section "Plans à charger".
# [0.9.57] - 2026-03-01
### Ajouté
- Section **Plans à charger** dans la boîte de dialogue (en dessous de "Données à charger").
# [0.9.56] - 2026-03-01
### Modifié
- `TODO.md` n'est plus stocké dans le dossier du plugin (qui est écrasé à chaque mise à jour). Il est désormais sauvegardd dans le profil utilisateur QGIS : `<profil>/voirie_communale/TODO.md` (via `QgsApplication.qgisSettingsDirPath()`). Le fichier est créé automatiquement à la première ouverture.
# [0.9.55] - 2026-03-01
### Ajouté
- Suppression automatique des doublons : si une couche du même nom (même commune) existe déjà dans le projet QGIS, elle est retirée avant le rechargement. Concerne toutes les sources (cadastre, commune, BAN, voirie, OSM, BD TOPO, MAJIC).
# [0.9.54] - 2026-03-01
### Modifié
- Zoom après chargement : utilise désormais l'emprise de la couche commune plutôt que l'emprise combinée de toutes les couches chargées.
# [0.9.53] - 2026-03-01
### Modifié
- ToDo : remplacement de l'ouverture dans l'éditeur système par une fenêtre QGIS intégrée (`QDialog`) avec éditeur de texte et bouton **Enregistrer**.
# [0.9.52] - 2026-03-01
### Ajouté
- Entrée de menu **Extensions → Voirie Communale → ToDo** : ouvre `TODO.md` dans l'éditeur système par défaut.
# [0.9.51] - 2026-03-01
### Modifié
- Menu du plugin déplacé de **Vecteur** vers **Extensions** (`addPluginToMenu`).
# [0.9.50] - 2026-03-01
### Supprimé
- Catégorie "Autre" inutile dans le renderer OSM (les tronçons sont filtrés à la source — seuls C/R passent dans la couche).
# [0.9.49] - 2026-03-01
### Correction
- `AttributeError: 'QgsRectangle' object has no attribute '__ior__'` dans `validate_and_load` — le calcul de l'emprise combinatoire utilisait l'opérateur `|=` non supporté par `QgsRectangle`. Remplacé par `combineExtentWith()`.
# [0.9.48] - 2026-03-01
### Correction
- OSM Routes : libellés de catégorisation incorrects — C = Voie communale, R = Chemin rural, CE = Chemin d'exploitation.
# [0.9.47] - 2026-03-01
### Correction
- OSM Routes : la catégorisation (CE / C / R) était incorrecte pour les tronçons sans `ref` direct mais appartenant à une relation référencée. Le champ `ref` stocke désormais la meilleure référence disponible (`ref` direct, sinon `rel_ref`).
# [0.9.46] - 2026-03-01
### Ajouté
- Barre de progression (`QProgressDialog`) affichée après 1,5 seconde d'attente, avec le nom de la source en cours de chargement. Se ferme automatiquement à la fin.
# [0.9.45] - 2026-03-01
### Modifié
- SNA RPG : le flux WFS n'est pas encore disponible sur la Géoplateforme IGN. La case à cocher est conservée mais affiche un message d'information en attendant la mise à disposition.
# [0.9.44] - 2026-03-01
### Ajouté
- Nouvelle source de données : **Surfaces non agricoles RPG** (`RPG.LATEST:SNA`, WFS IGN Géoplateforme), filtrée sur l'emprise communale, rendu orange semi-transparent. Case à cocher dédiée, intégrée dans Tout sélectionner/Désélectionner.
# [0.9.43] - 2026-03-01
### Correction
- Case "Routes numérotées ou nommées (BD TOPO)" absente du groupe Tout sélectionner/Désélectionner.
# [0.9.42] - 2026-02-28
### Technique
- Mise à jour technique : incrémentation automatique de version, workflow automatisé (test).
# [0.9.41] - 2026-02-25
### Ajouté
- Affichage d'un avertissement à l'utilisateur (QMessageBox.warning) en cas d'échec du chargement MAJIC (personnes morales).
# [0.9.40] - 2026-02-25
### Correction
- Mapping MAJIC/WFS IGN amélioré : correspondance multi-variantes pour géoréférencement maximal des parcelles.
# [0.9.39] - 2026-02-25
### Suppression
- Retrait complet de la couche BD TOPO Tronçons de route (case à cocher, logique, code, changelog, metadata).
# [0.9.38] - 2026-02-25
### Correction
- Symbologie BD TOPO limitée à 6 valeurs principales de type_de_route (les autres supprimées).
# [0.9.37] - 2026-02-25
### Correction
- Symbologie catégorisée mise à jour pour n'utiliser que les valeurs officielles de type_de_route BD TOPO.
# [0.9.36] - 2026-02-25
### Ajout
- Affichage catégorisé de la couche Routes numérotées ou nommées selon le champ type_de_route.
# Changelog - Voirie Communale

Toutes les modifications notables de ce projet seront documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet adhère au [Versionnement Sémantique](https://semver.org/lang/fr/).



## [0.9.35] - 2026-02-23

### Ajouté
- Affichage explicite des licences de chaque source de données dans le menu et la boîte de dialogue À propos (Licence Ouverte 2.0, ODbL, etc.).
- Nouvelle donnée : **Routes numérotées ou nommées (BD TOPO® IGN)** (BDTOPO_V3:route_numerotee_ou_nommee) — case à cocher dédiée, chargement filtré sur la commune, licence ouverte IGN.

## [Non publié]

## [0.9.34] - 2026-02-23

### Corrigé
- Dictionnaire `MAJIC_FORMES_JURIDIQUES` : libellés des codes `AU*` corrigés d'après analyse des dénominations observées dans les données (`AUDA` = Autre administration, `AUDP` = Autre de droit privé, `AUEP` = Autre entité publique, `AUPE` = Autre personne étrangère, `AURS` = Autre à régime spécial, `AUTA` = Autre titre administratif, `AUTC` = Autre titre collectif).

## [0.9.33] - 2026-02-23

### Modifié
- Couche **MAJIC** : catégorisation basée sur `groupe_personne` (10 groupes officiels DGFiP) avec les couleurs exactes de l'application Koumoul. Légende : 🔴 Personnes morales non remarquables · 🟠 État · 🟢 Région · 🟡 Département · 💙 Commune · 💜 Office HLM · 🟡 SEM · Copropriétaires · Associés · 🔵 Établissements publics.

## [0.9.32] - 2026-02-23

### Modifié
- Couche **MAJIC** : rendu catégorisé avec palette fixe (couleurs stables quelle que soit la commune). Chaque code de forme juridique est associé à un libellé complet (ex : `SARL` → _Société à responsabilité limitée_) et une couleur sémantique groupée : bleus pour les collectivités, teals pour l'intercommunalité, verts pour les associations, oranges pour l'agriculture, rouges pour les sociétés commerciales, violets pour les sociétés civiles. 100 formes juridiques répertoriées, fallback gris pour les codes inconnus.

## [0.9.31] - 2026-02-23

### Ajouté
- Couche **MAJIC** : rendu catégorisé QGIS appliqué automatiquement sur le champ `forme_juridique`. Chaque forme juridique abrégée (SA, SARL, COMMUNE, ASSOC…) obtient une couleur HSV distincte. Les parcelles sans forme juridique renseignée apparaissent en gris.

## [0.9.30] - 2026-02-22

### Modifié
- Couche **MAJIC** : géométrie passée de points (centroïdes `_geopoint`) à **polygones**. Les contours de parcelles sont désormais chargés depuis le WFS IGN Géoplateforme (`CADASTRALPARCELS.PARCELLAIRE_EXPRESS:parcelle`), filtrés par commune (`code_dep` + `code_com`). Jointure par `idu` (IGN) = `code_parcelle` (Koumoul). Seules les parcelles appartenant à des personnes morales sont retenues. Gestion des départements DOM (code_dep sur 3 chars).

## [0.9.29] - 2026-02-22

### Corrigé
- MAJIC HTTP 400 Bad Request (tentative 2) : deux causes identifiées par test direct de l'API :
  1. **Filtre inopérant** : `code_commune=88141` ne filtrait pas (renvoyait 16M résultats). Corrigé en `qs=code_commune:88141` (syntaxe Elasticsearch de Data Fair, test confirmé : 152 résultats pour commune 88141)
  2. **Pagination par `skip`** : avec 16M résultats sans filtre, `skip` dépassait la limite de l'API. Remplacé par curseur `after` (extrait du champ `next` de la réponse API)

## [0.9.28] - 2026-02-22

### Corrigé
- MAJIC HTTP 400 Bad Request : le champ `_parcelle_coords.coord` (point dans le nom) n'était pas accepté dans le paramètre `select` de l'API Data Fair. Remplacé par `_geopoint` (champ calculé centroïde `"lat,lon"`). Pagination corrigée de `skip` vers curseur `after`.

## [0.9.27] - 2026-02-22

### Ajouté
- Couche **Parcelles personnes morales (MAJIC)** : charge les parcelles cadastrales détenues par des personnes morales (entreprises, associations, collectivités) pour la commune sélectionnée. Source : API REST [Koumoul](https://koumoul.com/data-fair/app/carte-des-parcelles-des-personnes-morales-majic) (données DGFiP, Licence Ouverte). Couche de points avec attributs : dénomination, SIREN, forme juridique, groupe, contenance, nature culture, adresse.

## [0.9.26] - 2026-02-22

### Corrigé
- Case "Tout sélectionner" : suppression du tristate, comportement binaire simple

## [0.9.25] - 2026-02-22

### Corrigé
- Case maître "Tout sélectionner" : état partiel non fonctionnel au premier clic. Cause : signal `stateChanged` déclenchait le cycle tristate 0→1→2, passant par l'état partiel avant d'atteindre "coché". Correction : signal `clicked` utilisé à la place, avec forçage direct à l'état coché si la checkbox atterrit sur l'état partiel.

## [0.9.24] - 2026-02-22

### Ajouté
- Case à cocher **Tout sélectionner / Désélectionner** dans le panneau de sélection des couches : coche ou décoche toutes les couches en une action. Supporte l'état intermédiaire (partiellement coché) quand seules certaines couches sont sélectionnées.

## [0.9.23] - 2026-02-22

### Corrigé
- Champ géométrie BD TOPO `troncon_de_route` : `geometrie` au lieu de `geom` (Bad Request 400)
- Paramètre `geom_field` ajouté dans `load_wfs_layer` pour gérer les noms de champ variables selon la source

## [0.9.22] - 2026-02-22

### Ajouté

## [0.9.21] - 2026-02-22

### Ajouté
- Boîte de dialogue **À propos** dans le menu du plugin : version, auteur, licence, lien GitHub

## [0.9.20] - 2026-02-22

### Corrigé
- Renommage exhaustif du plugin en **Voirie Communale** dans tous les fichiers restants : message de log au chargement (`voirie_communale.py`), scripts de compilation (`compile_plugin.py`, `compile_simple.py`), script de packaging (`package.py`), guide de démarrage rapide (`QUICKSTART.md`) et `releases/README.md`

## [0.9.19] - 2026-02-22

### Modifié
- Renommage du plugin en **Voirie Communale** : la description, les menus, titres et en-têtes reflètent désormais le périmètre élargi (voies communales et chemins ruraux)

## [0.9.18] - 2026-02-22

### Optimisations
- Suppression des imports inutilisés : `QgsDataSourceUri`, `QgsCoordinateReferenceSystem`, `QgsSymbol`, `tempfile`
- Suppression de `self.temp_files` (plus de fichiers temporaires OSM)
- Suppression des paramètres `show_wait_message` de `load_wfs_layer` (jamais utilisés)
- Logs verbeux de la boucle de zoom supprimés

### Corrigé
- Bug `apply_ban_style` : `label_settings.fieldName` était assigné 3 fois consécutivement

### Nettoyage
- En-têtes boilerplate auto-générés remplacés par des en-têtes propres
- `first_start == True` simplifié en `first_start`

## [0.9.17] - 2026-02-22

### Modifié
- Renommage des couches voirie : `DGCL Voirie communale retenue DSR 2025 {insee}` et `DGCL Voirie départementale retenue DGF 2025 {insee}`

## [0.9.16] - 2026-02-22

### Modifié
- Renommage des couches voirie : `Voirie communale pour calcul DSR {insee}` et `Voirie départementale pour calcul DGF {insee}`

## [0.9.15] - 2026-02-18

### Corrigé
- OSM : champs définis dans l'URI de la couche mémoire (`field=ref:string&field=name:string&...`) au lieu de `addAttributes` — `setAttribute("ref", ...)` fonctionne désormais correctement

## [0.9.14] - 2026-02-18

### Corrigé
- OSM : `KeyError: 'ref'` corrigé — attributs écrits par index (`feat[0]`, `feat[1]`...) au lieu de `setAttribute(nom)`

## [0.9.13] - 2026-02-18

### Corrigé
- OSM : attributs écrits via `setAttribute(nom, valeur)` au lieu de `setAttributes([liste])` — le champ `ref` était vide, rendant le style catégorisé inopérant

## [0.9.12] - 2026-02-18

### Ajouté
- Style catégorisé pour la couche OSM : CE (vert), C (orange), R (rouge)
- Étiquettes avec le champ `ref` sur les routes OSM

## [0.9.11] - 2026-02-18

### Corrigé
- OSM : requête Overpass corrigée (`out geom;` au lieu de `out body;>;out body geom;`) — les ways n'avaient aucune géométrie inline, 0 feature chargée
- OSM : ajout du traitement des membres de relations (ways avec géométrie inline via `out geom;`)
- Testé sur commune 88141 : 74/74 routes C/R correctement chargées

## [0.9.10] - 2026-02-18

### Corrigé
- `QgsField` : suppression du constructeur déprécié avec `QVariant.String`, import `QVariant` retiré

## [0.9.9] - 2026-02-17

### Corrigé
- Indentation invalide dans le chargement OSM

## [0.9.8] - 2026-02-17

### Corrigé
- Correction du filtre OSM `ref` C/R (erreur `matched_count`)

## [0.9.7] - 2026-02-17

### Corrigé
- Filtre OSM `ref` C/R via JSON Overpass et couche mémoire

## [0.9.6] - 2026-02-17

### Corrigé
- Filtre OSM `ref` avec propagation des refs de relations

## [0.9.5] - 2026-02-17

### Corrigé
- Filtre OSM `ref` appliqué localement après téléchargement

## [0.9.4] - 2026-02-17

### Corrigé
- Filtre OSM `ref` via relations `route` et voies associées

## [0.9.3] - 2026-02-17

### Corrigé
- Filtre OSM `ref` via relations `route=road` et voies associées

## [0.9.2] - 2026-02-17

### Ajusté
- Filtre OSM routes avec `ref` commençant par C ou R

## [0.9.1] - 2026-02-17

### Ajusté
- Téléchargement des routes OSM sans filtres `highway`/`surface`

## [0.9.0] - 2026-02-17

### Ajouté
- Téléchargement des routes OSM via Overpass avec filtres `highway` et `surface`

## [0.8.6] - 2026-02-14

### Corrigé
- Utilisation de deux formats d'URI WFS selon le type de filtre :
  - Format classique `https://...?service=WFS&CQL_FILTER=...` pour filtres par code_insee (commune, BAN)
  - Format provider QGIS `url=...&bbox=...&restrictToRequestBBOX=1` pour filtres spatiaux (voiries)

## [0.8.5] - 2026-02-14

### Corrigé
- Format de l'URI WFS pour que QGIS respecte le filtre BBOX
- Changement de format : `url=...&typename=...&bbox=...&restrictToRequestBBOX=1` au lieu de `https://...?service=WFS&BBOX=...`
- Le filtre spatial BBOX fonctionne maintenant correctement pour les voiries

## [0.8.4] - 2026-02-14

### Corrigé
- Évite le chargement en double de la commune lorsque l'emprise communale est déjà sélectionnée
- Réutilisation de la couche commune déjà chargée pour obtenir le BBOX des voiries

## [0.8.3] - 2026-02-14

### Corrigé
- Chargement des voiries (communale et départementale) avec filtre BBOX spatial au lieu de code_insee
- Les tables DGCL.2025 n'ayant pas de champ code_insee, utilisation de l'emprise communale pour filtrage
- Chargement automatique de la couche commune si non sélectionnée mais nécessaire pour le BBOX

### Amélioré
- Méthode `load_wfs_layer()` générique supporte maintenant :
  - Filtre CQL avec code_insee (optionnel)
  - Filtre BBOX avec emprise (optionnel)
  - Combinaison des deux filtres possible

## [0.8.2] - 2026-02-14

### Supprimé
- Message d'attente (QMessageBox) lors du chargement des adresses BAN
- Chargement plus fluide sans interruption de l'interface

## [0.8.1] - 2026-02-14

### Corrigé
- Tooltips des checkboxes voirie : correction pour indiquer la source correcte (calcul IGN pour la DGCL)
- Formulation précise : "Charge le réseau de voirie communale/départementale (calcul IGN pour la DGCL)"

## [0.8.0] - 2026-02-14

### Ajouté
- Nouvelle source de données WFS : Voirie départementale (DGCL.2025:voirie_departementale)
- Checkbox dans l'interface pour sélectionner le chargement de la voirie départementale
- Méthode `load_voirie_dep_wfs()` utilisant l'architecture générique WFS

### Amélioré
- Ajout de la validation de la checkbox voirie départementale dans `validate_and_load()`
- Messages informatifs spécifiques pour la voirie départementale

## [0.7.0] - 2026-02-14

### Ajouté
- Nouvelle source de données WFS : Voirie communale (DGCL.2025:voirie_communale)
- Checkbox dans l'interface pour sélectionner le chargement de la voirie communale
- Méthode `load_voirie_wfs()` utilisant l'architecture générique WFS

### Amélioré
- Ajout de la validation de la checkbox voirie dans `validate_and_load()`
- Messages informatifs spécifiques pour la voirie communale

## [0.6.16] - 2026-02-14

### Optimisé
- URL WFS IGN mutualisée en constante de classe `WFS_IGN_URL = "https://data.geopf.fr/wfs"`
- Suppression de l'URL redondante `/wfs/ows` (tous les services utilisent maintenant `/wfs`)
- Signature de `load_wfs_layer()` simplifiée (paramètre `wfs_url` supprimé)

## [0.6.15] - 2026-02-14

### Refactorisé
- Création d'une méthode générique `load_wfs_layer()` pour centraliser le chargement WFS
- Les méthodes `load_commune_wfs()` et `load_ban_wfs()` utilisent maintenant la méthode générique
- Code plus maintenable et facilite l'ajout de nouvelles sources WFS
- Réduction de la duplication de code (~100 lignes économisées)

## [0.6.14] - 2026-02-14

### Amélioré
- Catégorie "Autre" désactivée par défaut dans la légende de la couche BAN
- Seuls les chemins ruraux et voies communales sont visibles au chargement

## [0.6.13] - 2026-02-14

### Amélioré
- Étiquettes BAN affichées uniquement sur les chemins ruraux et voies communales (filtre via expression CASE)

## [0.6.12] - 2026-02-14

### Corrigé
- Placement des étiquettes BAN : AroundPoint au lieu de OverPoint (TypeError résolu)

## [0.6.11] - 2026-02-14

### Amélioré
- Nouveau logo du plugin

## [0.6.10] - 2026-02-14

### Amélioré
- Étiquettes automatiques sur la couche BAN affichant le nom de la voie
- Buffer blanc autour des étiquettes pour meilleure lisibilité
- Placement des étiquettes au-dessus des points

## [0.6.9] - 2026-02-14

### Amélioré
- Regex optimisées avec groupes non capturants (?:...)
- che(?:min)? et sen(?:tier)? plus concis et performants
- voi(?:e)? et com(?:munale)? également optimisés

## [0.6.8] - 2026-02-14

### Corrigé
- regexp_match retourne position, ajout test > 0 pour fonctionnement correct
- Double échappement des backslash pour regex dans Python string

## [0.6.7] - 2026-02-14

### Corrigé
- Regex compatible avec moteur QGIS (sans groupes non capturants)
- Syntaxe simplifiée mais fonctionnalité identique

## [0.6.6] - 2026-02-14

### Corrigé
- Regex voie communale : COM au lieu de CO (VOI COM, VOIE COMMUNALE, etc.)

## [0.6.5] - 2026-02-14

### Amélioré
- Regex optimisée pour voies communales : VC, V.C., VOI COMMUNALE, VOIE CAL, etc.
- Suppression des filtres génériques rue/avenue/boulevard (trop larges)
- Cohérence avec le pattern chemins ruraux

## [0.6.4] - 2026-02-14

### Amélioré
- Remplacement des filtres LIKE par des regex optimisées
- Performance améliorée avec groupes non capturants (?:...)
- Expression plus concise et maintenable

## [0.6.3] - 2026-02-14

### Amélioré
- Filtres chemins ruraux beaucoup plus précis et exhaustifs :
  - "Chemin Rural" (toutes variations de casse)
  - "CR" (avec espaces avant/après)
  - "C.R." (avec points)
  - "CHE RURAL" (abréviation courante)
  - "Sentier Rural"
  - "SEN RURAL" (abréviation courante)
- Utilisation de upper() pour insensibilité à la casse
- Suppression du filtre générique "Chemin" trop large

## [0.6.2] - 2026-02-14

### Ajouté
- Style différencié automatique pour la couche BAN :
  - **Chemins ruraux** : Points marron/chocolat (détection via "Chemin", "CR")
  - **Voies communales** : Points bleus (détection via "Rue", "Avenue", "Boulevard", "VC")
  - **Autres voies** : Points gris
- Fonction apply_ban_style() avec expression CASE WHEN sur le champ nom_voie
- Symbologie basée sur QgsCategorizedSymbolRenderer
- Log de confirmation du style appliqué

## [0.6.1] - 2026-02-14

### Corrigé
- URL WFS BAN avec paramètres en minuscules (service, version, request)
- Ajout d'un message d'avertissement avant le chargement BAN pour informer l'utilisateur
- Message indique que le service peut être lent et demande de patienter

## [0.6.0] - 2026-02-14

### Ajouté
- Nouvelle source de données : Base Adresse Nationale (BAN)
- Case à cocher "Adresses (Base Adresse Nationale - BAN)" dans l'interface
- Fonction load_ban_wfs() pour charger les adresses via WFS
- Filtre par code_insee sur les 26+ millions d'adresses de France
- Support EPSG:4326 pour la BAN
- Logs de progression et avertissement sur le temps de chargement
- Gestion intelligente des messages selon les données chargées (cadastre/commune/BAN)

## [0.5.13] - 2026-01-27

### Modifié
- Remplacement de ADMINEXPRESS-COG.LATEST:commune par LIMITES_ADMINISTRATIVES_EXPRESS.LATEST:commune
- Couche WFS plus récente pour les limites communales
- Conserve EPSG:4326 et le filtre code_insee

## [0.5.12] - 2026-01-27

### Corrigé
- Transformation automatique de l'emprise dans le CRS du projet avant d'appliquer le zoom
- Détection du CRS source depuis les couches chargées
- Logs de la transformation : CRS source, CRS cible, emprise avant/après
- Résolution du problème : emprise WFS en EPSG:4326 vs projet en EPSG:2154

## [0.5.11] - 2026-01-27

### Corrigé
- Ajout de updateExtents() pour forcer le calcul de l'emprise des couches WFS
- Logs détaillés pour chaque couche : nom, extent, isEmpty
- Logs du résultat final du zoom pour faciliter le diagnostic
- Meilleure visibilité du processus de zoom dans le journal des messages

## [0.5.10] - 2026-01-27

### Amélioré
- Zoom robuste avec priorité sur les couches vectorielles (commune WFS)
- Fallback sur les couches raster WMS (cadastre) si nécessaire
- Ajout d'une marge de 5% autour de l'emprise pour meilleure visibilité
- Vérification que les emprises ne sont pas vides avant utilisation
- Gestion du cas où les couches WMS n'ont pas encore d'emprise valide

## [0.5.9] - 2026-01-27

### Amélioré
- Le zoom se fait désormais uniquement sur les couches nouvellement chargées
- Calcul de l'emprise combinée de toutes les couches chargées (cadastre + commune)
- Les fonctions load_cadastre_wms() et load_commune_wfs() retournent maintenant les couches créées
- Meilleure expérience utilisateur : pas de zoom sur toute la carte

## [0.5.8] - 2026-01-27

### Modifié
- Simplification : utilisation de EPSG:4326 (WGS84) pour tous les territoires français
- Suppression de la détection DOM-TOM devenue inutile
- Un seul CRS universel élimine les problèmes de compatibilité

## [0.5.7] - 2026-01-27

### Corrigé
- Détection automatique des DOM-TOM (codes INSEE 97xxx et 98xxx)
- Utilisation de EPSG:4326 (WGS84) pour les DOM-TOM au lieu de EPSG:2154
- Évite le plantage de QGIS lors du chargement d'emprises communales DOM-TOM
- EPSG:2154 (Lambert 93) conservé pour la métropole et la Corse

## [0.5.6] - 2026-01-27

### Corrigé
- Centralisation du zoom et du retour au premier plan dans la méthode validate_and_load()
- Le dialogue revient TOUJOURS au premier plan après chaque opération
- Zoom automatique après chaque chargement réussi (cadastre et/ou commune)
- Suppression du code redondant dans load_cadastre_wms() et load_commune_wfs()

## [0.5.5] - 2026-01-27

### Corrigé
- Restauration du zoom automatique sur l'emprise communale à chaque chargement
- Restauration du retour au premier plan du dialogue après chargement (toujours actif)
- Ajout du retour au premier plan après les messages récapitulatifs

## [0.5.4] - 2026-01-27

### Modifié
- Construction directe de l'URI WFS au lieu d'utiliser QgsDataSourceUri
- Utilisation de `CQL_FILTER=code_insee='54215'` dans l'URI complète
- Ajout de log pour afficher l'URI générée et faciliter le débogage

## [0.5.3] - 2026-01-27

### Modifié
- Suppression de tous les guillemets autour de la valeur dans le filtre CQL

## [0.5.2] - 2026-01-27

### Corrigé
- Filtre CQL WFS : suppression de tous les guillemets autour de la valeur
- Génère maintenant `code_insee=54215` (sans guillemets)

## [0.5.2] - 2026-01-27

### Corrigé
- Filtre CQL WFS : utilisation de guillemets doubles au lieu de simples pour éviter les antislashs d'échappement
- Le filtre génère maintenant `code_insee="54215"` au lieu de `code_insee=\'54215\'`

## [0.5.1] - 2026-01-27

### Corrigé
- Filtre WFS pour l'emprise communale : utilisation du champ correct `code_insee` au lieu de `insee_com`
- L'emprise communale se charge maintenant correctement avec le filtre sur le code INSEE

## [0.5.0] - 2026-01-27

### Modifié
- Remplacement des boutons radio par des cases à cocher pour permettre le chargement simultané de plusieurs types de données
- Cadastre ET emprise communale peuvent maintenant être chargés en même temps

### Ajouté
- Message récapitulatif lors du chargement de plusieurs types de données
- Gestion intelligente de l'affichage : pas de message individuel si chargement multiple

## [0.4.0] - 2026-01-27

### Ajouté
- Boutons radio pour choisir entre le chargement du cadastre (10 couches) ou de l'emprise communale
- Interface plus claire avec sélection explicite du type de données

### Modifié
- Titre du groupe changé de "Cadastre" à "Données géographiques"
- Texte du bouton changé de "Charger toutes les couches du Cadastre" à "Charger les données"
- Messages d'information adaptés selon le type de données chargées

## [0.3.2] - 2026-01-27

### Corrigé
- Nom correct de la couche WFS: `ADMINEXPRESS-COG.LATEST:commune` (avec "-COG")
- Le service WFS n'expose pas `ADMINEXPRESS.LATEST` mais `ADMINEXPRESS-COG.LATEST`

## [0.3.1] - 2026-01-27

### Corrigé
- Utilisation de la couche correcte `ADMINEXPRESS.LATEST:commune` au lieu de `ADMINEXPRESS-COG-CARTO.LATEST:commune`
- Couche Admin Express standard sans COG-CARTO

## [0.3.0] - 2026-01-27

### Ajouté
- **Chargement automatique de l'emprise communale** via WFS Admin Express de l'IGN Géoplateforme
- Service WFS : `https://data.geopf.fr/wfs` (couche `ADMINEXPRESS-COG-CARTO.LATEST:commune`)
- Filtre automatique par code INSEE
- Zoom automatique sur l'emprise de la commune après chargement
- Affichage du statut de chargement de l'emprise dans le message de confirmation

### Amélioré
- Intégration complète : cadastre (DGFiP) + emprise administrative (IGN)
- Logs détaillés pour le débogage WFS

## [0.2.9] - 2026-01-27

### Corrigé
- Le dialogue principal revient automatiquement au premier plan après les messages de succès ou d'erreur
- Ajout de `raise_()` et `activateWindow()` après les QMessageBox de confirmation
- Expérience utilisateur améliorée : flux de travail continu sans perdre le dialogue

## [0.2.8] - 2026-01-27

### Corrigé
- Le dialogue existant est maintenant ramené au premier plan au lieu de créer une nouvelle fenêtre
- Ajout de `raise_()` et `activateWindow()` pour gérer correctement le focus
- Un seul dialogue reste ouvert même avec plusieurs clics sur l'icône du plugin

## [0.2.7] - 2026-01-25

### Amélioré
- Dialogue non-modal : reste ouvert après le chargement du cadastre
- Permet de charger plusieurs communes successivement sans fermer/rouvrir le dialogue
- Suppression de `exec_()` remplacé par `show()` simple

## [0.2.6] - 2026-01-25

### Corrigé
- **CORRECTION CRITIQUE** : `IndentationError: unexpected indent` à la ligne 354
- Nettoyage des lignes orphelines restées après suppression du code mMapLayerComboBox

## [0.2.5] - 2026-01-25

### Corrigé
- **CORRECTION CRITIQUE** : Erreur `AttributeError: 'VoirieCommunaleDialog' object has no attribute 'mMapLayerComboBox'`
- Suppression du code qui référençait le widget supprimé en 0.2.4
- Le bouton OK ferme maintenant correctement le dialogue sans erreur

## [0.2.4] - 2026-01-25

### Supprimé
- Widget "Couche de chemins" inutilisé (sera réimplémenté avec une vraie fonctionnalité ultérieurement)
- Section "Options" vide de l'interface
- Déclaration du customwidget QgsMapLayerComboBox devenu inutile

### Amélioré
- Interface plus épure et focusée sur le cadastre

## [0.2.3] - 2026-01-25

### Corrigé
- **Correction de la validation des codes INSEE** (la regex de 0.2.2 était inutile)
- Validation complète et réelle des codes INSEE français :
  - Métropole : Départements 01-19, 21-95 (format : 2 chiffres + 3 chiffres)
  - Corse : 2A et 2B (format : 2A/2B + 3 chiffres)
  - DOM : 971-976 (format : 3 chiffres + 2 chiffres)
  - TOM : 984-988 (format : 3 chiffres + 2 chiffres)
- Messages d'erreur détaillés avec exemples par territoire
- Conversion automatique en majuscules pour les codes Corse
- Interface : Placeholder et tooltip mis à jour

## [0.2.2] - 2026-01-25

### Amélioré
- Validation du code INSEE avec expression régulière (`^\\d{5}$`)
- Validation plus robuste et explicite avec le module `re`

## [0.2.1] - 2026-01-25

### Corrigé
- Suppression des cases à cocher (Parcelles, Bâtiments, Sections) de l'interface utilisateur
- Simplification de l'interface : un seul bouton "Charger toutes les couches du Cadastre"
- Cohérence entre le code (chargement automatique) et l'interface utilisateur

## [0.2.0] - 2026-01-25

### Ajouté
- Chargement automatique de 10 couches cadastrales au lieu de 3
- Nouvelles couches : Lieux-dits, Amorces cadastrales, Clôtures, Détails topographiques, Hydrographie, Voies de communication, Bornes et repères
- Organisation automatique des couches dans un groupe nommé "Cadastre - {code INSEE}"

### Amélioré
- Les couches sont maintenant organisées dans un groupe dédié pour faciliter la gestion
- Chargement complet du cadastre en un seul clic

### Supprimé
- Cases à cocher de sélection des couches (chargement automatique de toutes les couches)

## [0.1.2] - 2026-01-25

### Corrigé
- **CORRECTION CRITIQUE** : Utilisation des noms de couches corrects selon le service INSPIRE
  - Parcelles : `CP.CadastralParcel` (au lieu de CADASTRALPARCELS.PARCELLAIRE_EXPRESS)
  - Bâtiments : `BU.Building` (au lieu de BUILDINGS.BUILDINGS)
  - Sections : `SUBFISCAL` (au lieu de CADASTRALPARCELS.PARCELS)
- Vérifié via GetCapabilities du service https://inspire.cadastre.gouv.fr/scpc/

## [0.1.1] - 2026-01-25

### Corrigé
- Correction du chargement de l'interface : utilisation du fichier UI compilé (.py) au lieu du fichier source (.ui)
- Résolution de l'erreur FileNotFoundError lors du chargement du plugin

### Amélioré
- Gestion d'erreur détaillée pour le chargement des flux WMS
- Logs détaillés dans le journal des messages QGIS (onglet VoirieCommunale)
- Messages d'erreur explicites avec instructions de diagnostic
- Affichage des URI WMS testés pour faciliter le débogage

## [0.1.0] - 2026-01-25

### Ajouté
- Structure initiale du plugin QGIS
- Interface utilisateur avec Qt Designer
- Intégration du flux WMS cadastre INSPIRE (DGFiP)
- Champ de saisie pour le code INSEE de la commune
- Validation du code INSEE (5 chiffres obligatoires)
- Sélection des couches cadastrales :
  - Parcelles cadastrales (CADASTRALPARCELS.PARCELLAIRE_EXPRESS)
  - Bâtiments (BUILDINGS.BUILDINGS)
  - Sections cadastrales (CADASTRALPARCELS.PARCELS)
- Messages d'erreur explicites pour l'utilisateur
- Logs dans la console QGIS
- Documentation complète (README.md, QUICKSTART.md)
- Instructions Copilot pour les agents IA (.github/copilot-instructions.md)
- Scripts de compilation Python (compile.bat, compile.sh, compile_plugin.py)
- Gestion des ressources (icônes) via PyQt5

### Configuration
- Support QGIS 3.0+
- Compatibilité Python 3.6+
- CRS par défaut : EPSG:2154 (Lambert 93)
- Format WMS : image/png

### Documentation
- Guide d'installation en mode développement
- Workflow de développement (modification UI, compilation, test)
- Exemples de codes INSEE
- Lien vers le site INSEE pour recherche de codes

## [0.0.1] - 2026-01-25

### Ajouté
- Initialisation du projet
- Structure de base du plugin PyQGIS
- Fichiers de métadonnées (metadata.txt)

[Non publié]: https://github.com/votre-username/voirie_communale/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/votre-username/voirie_communale/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/votre-username/voirie_communale/releases/tag/v0.0.1
