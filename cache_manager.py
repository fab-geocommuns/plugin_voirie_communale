# -*- coding: utf-8 -*-
"""
Voirie Communale - Cache local GeoPackage
Copyright (C) 2026 Yann Schwarz <yann.schwarz@gmail.com>
Licence : GNU GPL v2+
"""
import os
import sqlite3
import time

from qgis.core import (QgsVectorLayer, QgsVectorFileWriter, QgsProject,
                        QgsMessageLog, Qgis, QgsApplication, QgsDataProvider)

from .version import __version__ as PLUGIN_VERSION

# Table de métadonnées non spatiale ajoutée dans chaque GeoPackage de cache,
# retenant la version du plugin ayant écrit chaque couche. Un GeoPackage
# n'étant qu'un fichier SQLite, elle est gérée directement en SQL plutôt
# qu'avec l'API QGIS (pas de géométrie à stocker ici).
CACHE_META_TABLE = "_voirie_cache_meta"


class CacheManagerMixin:
    """Cache local des couches vecteur par commune, sous forme de GeoPackage.

    Un fichier `voirie_{code_insee}.gpkg` est créé dans un dossier dédié du
    profil QGIS actif, avec une couche interne par type de donnée (ex. 'ban',
    'majic', 'filaires_bal'...). Le cache est transparent : consulté avant
    tout téléchargement réseau, et alimenté après chaque chargement réussi.

    Il n'y a pas d'expiration automatique — seulement un avertissement
    affiché si le cache dépasse un âge configurable (paramètre
    'cache_warning_days'), l'utilisateur restant libre de forcer un
    rechargement complet via le bouton dédié.
    """

    CACHE_SUBDIR = "voirie_communale_cache"

    def _cache_dir(self):
        """Retourne (et crée si besoin) le dossier de cache dans le profil QGIS."""
        base = QgsApplication.qgisSettingsDirPath()
        cache_dir = os.path.join(base, self.CACHE_SUBDIR)
        try:
            os.makedirs(cache_dir, exist_ok=True)
        except OSError as exc:
            QgsMessageLog.logMessage(
                f"Cache : impossible de créer le dossier {cache_dir} : {exc}",
                "VoirieCommunale", Qgis.Warning
            )
        return cache_dir

    def _cache_gpkg_path(self, code_insee):
        """Chemin du fichier GeoPackage de cache pour une commune donnée."""
        return os.path.join(self._cache_dir(), f"voirie_{code_insee}.gpkg")

    def _cache_age_days(self, code_insee):
        """Âge du fichier de cache en jours, ou None si le cache est absent."""
        path = self._cache_gpkg_path(code_insee)
        if not os.path.isfile(path):
            return None
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return None
        return (time.time() - mtime) / 86400.0

    def _cache_meta_get_version(self, path, layer_key):
        """Retourne la version du plugin ayant écrit `layer_key` dans le GeoPackage
        `path`, ou None si absente/table inexistante (cache d'une version antérieure
        à ce mécanisme, ou couche jamais enregistrée)."""
        if not os.path.isfile(path):
            return None
        try:
            with sqlite3.connect(path) as conn:
                cur = conn.execute(
                    f"SELECT plugin_version FROM {CACHE_META_TABLE} WHERE layer_key = ?",
                    (layer_key,)
                )
                row = cur.fetchone()
                return row[0] if row else None
        except sqlite3.Error:
            # Table absente (ancien cache) ou fichier non-SQLite valide : pas bloquant.
            return None

    def _cache_meta_set_version(self, path, layer_key):
        """Enregistre la version courante du plugin pour `layer_key` dans le
        GeoPackage `path`. Best-effort : ne doit jamais faire échouer l'écriture
        du cache elle-même."""
        try:
            with sqlite3.connect(path) as conn:
                conn.execute(
                    f"CREATE TABLE IF NOT EXISTS {CACHE_META_TABLE} "
                    "(layer_key TEXT PRIMARY KEY, plugin_version TEXT, saved_at REAL)"
                )
                conn.execute(
                    f"INSERT INTO {CACHE_META_TABLE} (layer_key, plugin_version, saved_at) "
                    "VALUES (?, ?, ?) "
                    "ON CONFLICT(layer_key) DO UPDATE SET plugin_version=excluded.plugin_version, "
                    "saved_at=excluded.saved_at",
                    (layer_key, PLUGIN_VERSION, time.time())
                )
                conn.commit()
        except sqlite3.Error as exc:
            QgsMessageLog.logMessage(
                f"Cache : impossible d'enregistrer la version du cache pour {layer_key} : {exc}",
                "VoirieCommunale", Qgis.Warning
            )

    def _load_layer_from_cache(self, code_insee, layer_key, display_name):
        """Tente de charger `layer_key` depuis le GeoPackage de cache de `code_insee`.

        Args:
            code_insee: code INSEE de la commune
            layer_key: nom interne de la couche dans le GeoPackage (ex. 'ban')
            display_name: nom d'affichage à donner à la couche QGIS chargée

        Returns:
            QgsVectorLayer valide (nommée display_name) ou None si absente/invalide
            ou si elle a été écrite par une version antérieure du plugin (le cache
            est alors considéré comme potentiellement obsolète et ignoré, afin de
            ne jamais servir des données figées par un bug corrigé depuis).
        """
        path = self._cache_gpkg_path(code_insee)
        if not os.path.isfile(path):
            return None

        cached_version = self._cache_meta_get_version(path, layer_key)
        if cached_version is not None and cached_version != PLUGIN_VERSION:
            QgsMessageLog.logMessage(
                f"Cache : {display_name} ignorée (écrite par la version {cached_version}, "
                f"plugin actuel {PLUGIN_VERSION}) — retéléchargement automatique",
                "VoirieCommunale", Qgis.Info
            )
            if not hasattr(self, '_cache_version_invalidations'):
                self._cache_version_invalidations = []
            self._cache_version_invalidations.append(display_name)
            return None

        uri = f"{path}|layername={layer_key}"
        layer = QgsVectorLayer(uri, display_name, "ogr")
        if not layer.isValid() or layer.featureCount() == 0:
            return None
        QgsMessageLog.logMessage(
            f"Cache : {display_name} chargée depuis {os.path.basename(path)} "
            f"({layer.featureCount()} entité(s))",
            "VoirieCommunale", Qgis.Info
        )
        return layer

    def _save_layer_to_cache(self, code_insee, layer_key, layer):
        """Écrit (ou remplace) la couche `layer_key` dans le GeoPackage de `code_insee`.

        Opération best-effort : toute erreur est loguée sans jamais interrompre
        le chargement en cours — le cache n'est qu'une optimisation, jamais
        une dépendance bloquante.

        Returns:
            bool: True si l'écriture a réussi.
        """
        if layer is None or not layer.isValid():
            return False

        path = self._cache_gpkg_path(code_insee)

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.layerName = layer_key
        options.fileEncoding = "UTF-8"
        if os.path.isfile(path):
            options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer

        transform_context = QgsProject.instance().transformContext()
        try:
            if hasattr(QgsVectorFileWriter, 'writeAsVectorFormatV3'):
                error = QgsVectorFileWriter.writeAsVectorFormatV3(layer, path, transform_context, options)
            else:
                error = QgsVectorFileWriter.writeAsVectorFormatV2(layer, path, transform_context, options)
            error_code = error[0] if isinstance(error, tuple) else error
        except Exception as exc:  # défensif : une erreur de cache ne doit jamais faire échouer un chargement
            QgsMessageLog.logMessage(
                f"Cache : échec d'écriture de {layer_key} dans {path} : {exc}",
                "VoirieCommunale", Qgis.Warning
            )
            return False

        if error_code != QgsVectorFileWriter.NoError:
            QgsMessageLog.logMessage(
                f"Cache : échec d'écriture de {layer_key} dans {path} (code {error_code})",
                "VoirieCommunale", Qgis.Warning
            )
            return False

        self._cache_meta_set_version(path, layer_key)

        QgsMessageLog.logMessage(
            f"Cache : {layer_key} enregistrée dans {os.path.basename(path)}",
            "VoirieCommunale", Qgis.Info
        )
        return True

    def _reload_layer_from_cache_preserving_style(self, code_insee, layer_key, layer, display_name):
        """Bascule la source de données de `layer` (provider 'memory', ou
        GeoJSON en /vsimem/) vers sa version fraîchement écrite dans le
        GeoPackage de cache (provider 'ogr'), afin qu'elle ne soit plus
        signalée par QGIS comme « couche temporaire » et qu'elle survive à
        l'enregistrement du projet.

        Utilise `QgsVectorLayer.setDataSource()` plutôt que de recréer une
        nouvelle couche : il s'agit du même objet QgsVectorLayer (même id,
        même renderer, mêmes labels, jointures, etc.), donc tout le style est
        conservé automatiquement, sans recopie manuelle.

        Best-effort : si le cache est absent/invalide ou si la bascule
        échoue, `layer` est retournée inchangée (le cache reste une
        optimisation, jamais une dépendance bloquante).
        """
        # Vérifie d'abord que le cache est exploitable avant de basculer la
        # source de la couche réelle, pour ne jamais la rendre invalide.
        check = self._load_layer_from_cache(code_insee, layer_key, display_name)
        if check is None:
            return layer

        path = self._cache_gpkg_path(code_insee)
        uri = f"{path}|layername={layer_key}"
        try:
            layer.setDataSource(uri, display_name, "ogr", QgsDataProvider.ProviderOptions())
        except Exception as exc:
            QgsMessageLog.logMessage(
                f"Cache : impossible de basculer la source de {display_name} vers le cache : {exc}",
                "VoirieCommunale", Qgis.Warning
            )
            return layer

        if not layer.isValid():
            QgsMessageLog.logMessage(
                f"Cache : bascule de source invalide pour {display_name}, couche laissée en mémoire",
                "VoirieCommunale", Qgis.Warning
            )
            return layer

        return layer
