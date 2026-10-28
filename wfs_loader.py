# -*- coding: utf-8 -*-
"""
Voirie Communale - Telechargement et construction des couches (WFS/WMS/XYZ)
Copyright (C) 2026 Yann Schwarz <yann.schwarz@gmail.com>
Licence : GNU GPL v2+

Ce module regroupe : la tache asynchrone WfsLoadTask (QgsTask), les fonctions
de telechargement bas niveau (fetch-to-vsimem, utilisees en arriere-plan sans
objets QGIS), et les methodes de chargement haut niveau de chaque source de
donnees (BAN, BD TOPO, OSM, MagOSM, MAJIC, cadastre, WMS historiques, etc.).
"""
import json
import time
import uuid
import urllib.parse
import urllib.request
import urllib.error
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import (QgsProject, QgsVectorLayer, QgsRasterLayer, QgsMessageLog,
                       Qgis, QgsTask,
                       QgsFeature, QgsGeometry, QgsPointXY)


def _unique_vsimem_path(stem):
    """Chemin /vsimem/ unique par téléchargement : deux chargements successifs
    (autre commune, rechargement) ne doivent jamais réécrire le fichier encore
    ouvert par une couche existante."""
    return f"/vsimem/{stem}_{uuid.uuid4().hex}.json"


class WfsLoadTask(QgsTask):
    """Exécute un téléchargement WFS en arrière-plan (thread secondaire).

    Le callable fetch_fn doit retourner (success: bool, vsimem_path: str|None, error: str|None).
    Le signal taskDone(task) est émis sur le thread principal dans finished().
    """

    taskDone = pyqtSignal(object)

    def __init__(self, label, fetch_fn):
        super().__init__(label, QgsTask.CanCancel)
        self.label = label
        self._fetch_fn = fetch_fn
        self.success = False
        self.vsimem_path = None
        self.error_msg = None

    def run(self):
        # Frontière volontairement large : ce code s'exécute dans un thread
        # secondaire QGIS. Toute exception non interceptée ici ferait planter
        # QGIS, donc on capture tout et on remonte le message via error_msg.
        try:
            self.success, self.vsimem_path, self.error_msg = self._fetch_fn()
            return self.success
        except Exception as exc:
            self.error_msg = str(exc)
            return False

    def finished(self, result):
        self.success = result
        self.taskDone.emit(self)



class WfsLoaderMixin:
    """Regroupe les methodes de telechargement et de construction des couches (WFS/WMS/XYZ)."""

    @staticmethod
    def _download_with_progress(url, progress_cb=None, timeout=120, label="Téléchargement",
                                 chunk_size=262144, headers=None):
        """Télécharge une URL en streaming, avec retour de progression périodique.

        Contrairement à un `response.read()` unique, la réponse est lue par blocs
        de `chunk_size` octets, ce qui permet de signaler à `progress_cb` le
        volume déjà téléchargé (et le pourcentage si le serveur fournit
        Content-Length) pendant toute la durée du transfert. Utilisé pour les
        téléchargements volumineux en un seul fichier (export national BAL,
        archive EDIGEO) qui bloqueraient sinon l'interface plusieurs dizaines de
        secondes sans aucun signe de vie.

        Args:
            url: URL à télécharger (GET simple)
            progress_cb: callback optionnel appelé avec un message (str)
            timeout: délai d'expiration de la requête, en secondes
            label: préfixe du message de progression (ex. "Filaires BAL")
            chunk_size: taille des blocs de lecture, en octets
            headers: en-têtes HTTP additionnels (fusionnés avec le User-Agent par défaut)

        Returns:
            bytes: le contenu complet téléchargé.

        Raises:
            urllib.error.URLError, OSError: propagées telles quelles à l'appelant
                en cas d'échec réseau, à charge pour lui de les traiter.
        """
        req_headers = {'User-Agent': 'QGIS-VoirieCommunale/1.0'}
        if headers:
            req_headers.update(headers)
        req = urllib.request.Request(url, headers=req_headers)

        chunks = []
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content_length = response.headers.get('Content-Length')
            total = int(content_length) if content_length and content_length.isdigit() else None
            downloaded = 0
            last_reported_mb = -1
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                chunks.append(chunk)
                downloaded += len(chunk)
                if progress_cb:
                    mb = downloaded // (1024 * 1024)
                    if mb != last_reported_mb:  # limite la fréquence des mises à jour de l'UI
                        last_reported_mb = mb
                        if total:
                            pct = min(100, int(downloaded * 100 / total))
                            total_mb = total // (1024 * 1024)
                            progress_cb(f"{label} : {mb} Mo / {total_mb} Mo ({pct}%)...")
                        else:
                            progress_cb(f"{label} : {mb} Mo téléchargé(s)...")
        return b"".join(chunks)

    def load_xyz_tile_layer(self, url, display_name, zmin=0, zmax=19):
        """Charge une couche de tuiles XYZ.

        Args:
            url (str): URL du service XYZ avec {z}/{x}/{y} comme variables de tuile
            display_name (str): Nom affiché dans le panneau des couches
            zmin (int): Niveau de zoom minimum
            zmax (int): Niveau de zoom maximum

        Returns:
            tuple: (bool, list) - (succès, liste des couches chargées)
        """
        try:
            uri = f"type=xyz&url={url}&zmax={zmax}&zmin={zmin}"
            self._remove_layers_by_name(display_name)
            layer = QgsRasterLayer(uri, display_name, 'wms')
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer, False); QgsProject.instance().layerTreeRoot().addLayer(layer)
                QgsMessageLog.logMessage(
                    f"Tuiles XYZ chargées : {display_name}",
                    "VoirieCommunale",
                    Qgis.Info
                )
                return True, [layer]
            else:
                QgsMessageLog.logMessage(
                    f"Impossible de charger les tuiles XYZ : {display_name} \u2014 URI : {uri}",
                    "VoirieCommunale",
                    Qgis.Warning
                )
                return False, []
        # Frontière volontairement large : QgsRasterLayer/QgsProject peuvent
        # lever des erreurs variées selon le provider ('wms'/xyz) et l'état du
        # projet ; on journalise et on retourne un échec plutôt que de
        # laisser une exception interrompre le chargement des autres couches.
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Erreur chargement tuiles XYZ {display_name} : {str(e)}",
                "VoirieCommunale",
                Qgis.Critical
            )
            return False, []


    def _load_wms_layer_group(self, group_name, wms_url, crs, layers_to_load, format_type="image/png"):
        """Charge plusieurs couches WMS dans un groupe dédié (remplace le groupe existant s'il y en a un).

        Centralise la logique commune à load_cadastre_wms / load_geofoncier_wms / load_cosia_wms :
        création du groupe, boucle de chargement avec vérification isValid(), collecte des erreurs.
        Si aucune couche n'a pu être chargée, le groupe (vide) est retiré de l'arbre.

        Args:
            group_name: nom du groupe dans l'arbre des couches
            wms_url: URL de base du service WMS
            crs: CRS demandé au serveur (ex: 'EPSG:2154')
            layers_to_load: liste de (typename, display_name)
            format_type: format d'image WMS (par défaut 'image/png')

        Returns:
            tuple: (created_layers: list, errors: list[str]) — noms des couches en échec
        """
        root = QgsProject.instance().layerTreeRoot()
        self._remove_group_by_name(group_name)
        group = root.addGroup(group_name)

        created_layers = []
        errors = []
        for typename, display_name in layers_to_load:
            uri = f"crs={crs}&format={format_type}&layers={typename}&styles&url={wms_url}"
            layer = QgsRasterLayer(uri, display_name, 'wms')
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer, False)
                group.addLayer(layer)
                created_layers.append(layer)
                QgsMessageLog.logMessage(
                    f"✓ {display_name} chargée avec succès", "VoirieCommunale", Qgis.Success
                )
            else:
                errors.append(display_name)
                QgsMessageLog.logMessage(
                    f"✗ Échec du chargement de {display_name} : {layer.error().message()}",
                    "VoirieCommunale", Qgis.Warning
                )

        if not created_layers:
            root.removeChildNode(group)

        return created_layers, errors


    def load_cadastre_wms(self, code_insee):
        """Charge les couches cadastrales WMS pour le code INSEE donné

        Returns:
            tuple: (bool, list) - (succès, liste des couches chargées)
        """

        # URL du service WMS INSPIRE du cadastre (DGFiP)
        wms_url = f"https://inspire.cadastre.gouv.fr/scpc/{code_insee}.wms"

        # Toutes les couches disponibles sur le service INSPIRE
        layers_to_load = [
            ('CP.CadastralParcel', 'Parcelles cadastrales'),
            ('BU.Building', 'Bâtiments'),
            ('SUBFISCAL', 'Subdivisions fiscales'),
            ('LIEUDIT', 'Lieux-dits'),
            ('AMORCES_CAD', 'Amorces cadastrales'),
            ('CLOTURE', 'Clôtures'),
            ('DETAIL_TOPO', 'Détails topographiques'),
            ('HYDRO', 'Hydrographie'),
            ('VOIE_COMMUNICATION', 'Voies de communication'),
            ('BORNE_REPERE', 'Bornes et repères'),
        ]

        group_name = f"Cadastre - {code_insee}"
        created_layers, errors = self._load_wms_layer_group(
            group_name, wms_url, "EPSG:2154", layers_to_load
        )

        if created_layers:
            if errors:
                QMessageBox.warning(
                    self.iface.mainWindow(),
                    "Cadastre partiellement chargé",
                    f"{len(created_layers)} couche(s) chargée(s), couches en erreur : {', '.join(errors)}\n\n"
                    "Consultez le journal des messages pour plus de détails."
                )
            return True, created_layers
        else:
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Erreur de chargement du cadastre",
                f"Aucune couche cadastrale n'a pu être chargée.\n\n"
                f"Code INSEE : {code_insee}\nURL : {wms_url}\n\n"
                "Vérifiez le code INSEE, la connexion internet et le journal des messages."
            )
            return False, []


    def load_geofoncier_wms(self):
        """Charge les couches Géofoncier public (RFU + Plans d'alignement) dans un groupe dédié.

        Returns:
            tuple: (bool, list) - (succès, liste des couches chargées)
        """
        WMS_URL = "https://api2.geofoncier.fr/api/referentielsoge/wxs?"

        layers_to_load = [
            ('RFU_LIMITES',        'RFU - Limites'),
            ('RFU_SOMMETS',        'RFU - Sommets'),
            ('PLANS_EMPRISES',     "Plans d'alignement - Emprises"),
            ('PLANS_LIGNES',       "Plans d'alignement - Limites"),
            ('PLANS_LOCALISANTS',  "Plans d'alignement - Localisants"),
        ]

        created_layers, errors = self._load_wms_layer_group(
            "Géofoncier public", WMS_URL, "EPSG:2154", layers_to_load
        )

        if created_layers:
            if errors:
                QMessageBox.warning(
                    self.iface.mainWindow(),
                    "Géofoncier partiellement chargé",
                    f"Couches en erreur : {', '.join(errors)}"
                )
            return True, created_layers
        else:
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Erreur Géofoncier",
                "Aucune couche Géofoncier n'a pu être chargée.\n\n"
                "Vérifiez votre connexion internet."
            )
            return False, []


    def load_cosia_wms(self):
        """Charge les 3 millésimes CoSIA (Couverture du Sol par IA) dans un groupe dédié.

        Couches IGN Géoplateforme (ordre décroissant) :
          IGNF_COSIA_2024-2026, IGNF_COSIA_2021-2023, IGNF_COSIA_2017-2020

        Returns:
            tuple: (bool, list) - (au moins une couche chargée, liste des couches)
        """
        WMS_URL = "https://data.geopf.fr/wms-r"
        millesimes = [
            ('IGNF_COSIA_2024-2026', 'CoSIA 2024-2026'),
            ('IGNF_COSIA_2021-2023', 'CoSIA 2021-2023'),
            ('IGNF_COSIA_2017-2020', 'CoSIA 2017-2020'),
        ]

        created_layers, errors = self._load_wms_layer_group(
            "CoSIA (Couverture du Sol par IA)", WMS_URL, "EPSG:2154", millesimes
        )

        if not created_layers:
            QgsMessageLog.logMessage("Aucune couche CoSIA n'a pu être chargée", "VoirieCommunale", Qgis.Warning)

        return len(created_layers) > 0, created_layers


    def load_scan_historique_wms(self, layer_name_wms, display_name):
        """Charge un scan historique IGN (EPSG:2154). Délègue à _load_wms_layer."""
        return self._load_wms_layer(layer_name_wms, display_name, 'EPSG:2154')


    def _load_wms_layer(self, layer_name_wms, display_name, crs='EPSG:2154'):
        """Charge une couche WMS depuis la Géoplateforme IGN (wms-r).

        Args:
            layer_name_wms: Nom de la couche WMS (typename)
            display_name: Nom affiché dans QGIS
            crs: CRS demandé au serveur (ex: 'EPSG:2154', 'EPSG:3857', 'IGNF:WGS84G')

        Returns:
            tuple: (bool, list) - (succès, liste des couches créées)
        """
        WMS_URL = "https://data.geopf.fr/wms-r"
        uri = f"crs={crs}&format=image/png&layers={layer_name_wms}&styles&url={WMS_URL}"

        QgsMessageLog.logMessage(
            f"Chargement WMS ({crs}) : {display_name}",
            "VoirieCommunale", Qgis.Info
        )

        self._remove_layers_by_name(display_name)
        wms_layer = QgsRasterLayer(uri, display_name, 'wms')

        if wms_layer.isValid():
            QgsProject.instance().addMapLayer(wms_layer, False); QgsProject.instance().layerTreeRoot().addLayer(wms_layer)
            QgsMessageLog.logMessage(
                f"✓ {display_name} chargée avec succès",
                "VoirieCommunale", Qgis.Success
            )
            return True, [wms_layer]
        else:
            QgsMessageLog.logMessage(
                f"✗ Impossible de charger {display_name} : {wms_layer.error().message()}",
                "VoirieCommunale", Qgis.Warning
            )
            return False, []

    # URL du service WFS IGN Géoplateforme (constante pour tous les services WFS)
    WFS_IGN_URL = "https://data.geopf.fr/wfs"
    # URL du service WFS MagOSM (Magellium) — réseau routier OSM enrichi
    MAGOSM_WFS_URL = "https://magosm.magellium.com/geoserver/ows"


    def load_wfs_layer(self, typename, layer_name, code_insee=None, crs="EPSG:4326", style_callback=None):
        """Charge une couche WFS filtrée par code_insee (CQL_FILTER) depuis l'IGN Géoplateforme.

        Utilise directement le provider WFS de QGIS (pas de pagination : réservé
        aux couches de taille modeste, ex. l'emprise communale).
        """
        uri_string = (
            f"{self.WFS_IGN_URL}?"
            f"service=WFS&version=2.0.0&request=GetFeature&"
            f"typename={typename}&srsname={crs}"
        )
        if code_insee:
            uri_string += f"&CQL_FILTER=code_insee='{code_insee}'"

        QgsMessageLog.logMessage(f"WFS code_insee: {uri_string}", "VoirieCommunale", Qgis.Info)
        wfs_layer = QgsVectorLayer(uri_string, layer_name, "WFS")

        if wfs_layer.isValid() and wfs_layer.featureCount() > 0:
            self._remove_layers_by_name(layer_name)
            QgsProject.instance().addMapLayer(wfs_layer, False); QgsProject.instance().layerTreeRoot().addLayer(wfs_layer)
            if style_callback:
                style_callback(wfs_layer)
            QgsMessageLog.logMessage(f"✓ {layer_name} ({wfs_layer.featureCount()} entité(s))", "VoirieCommunale", Qgis.Success)
            return True, wfs_layer
        else:
            QgsMessageLog.logMessage(f"✗ {layer_name} : {wfs_layer.error().message()}", "VoirieCommunale", Qgis.Warning)
            return False, None


    def _fetch_wfs_paginated_to_vsimem(self, wfs_url, typename, cql_filter=None,
                                        crs="EPSG:4326", page_size=1000, bbox=None):
        """[background-safe] Télécharge un WFS paginé et écrit le résultat dans /vsimem/.

        Returns:
            tuple: (success: bool, vsimem_path: str|None, error: str|None)
        """
        from osgeo import gdal
        all_features = []
        start_index = 0
        crs_ref = None
        while True:
            params = {
                'SERVICE': 'WFS', 'VERSION': '2.0.0', 'REQUEST': 'GetFeature',
                'TYPENAMES': typename, 'SRSNAME': crs,
                'OUTPUTFORMAT': 'application/json',
                'COUNT': page_size, 'STARTINDEX': start_index,
            }
            if cql_filter:
                params['CQL_FILTER'] = cql_filter
            if bbox:
                xmin, ymin, xmax, ymax = bbox
                params['BBOX'] = f"{xmin},{ymin},{xmax},{ymax},{crs}"
            url = f"{wfs_url}?{urllib.parse.urlencode(params)}"
            QgsMessageLog.logMessage(
                f"[parallèle] WFS {typename} (startIndex={start_index}): {url}",
                "VoirieCommunale", Qgis.Info
            )
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'QGIS-VoirieCommunale/1.0'})
                with urllib.request.urlopen(req, timeout=120) as resp:
                    fc = json.loads(resp.read().decode('utf-8'))
            except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
                return False, None, str(exc)
            batch = fc.get('features', [])
            if crs_ref is None:
                crs_ref = fc.get('crs', None)
            all_features.extend(batch)
            number_matched = fc.get('numberMatched')
            number_returned = fc.get('numberReturned', len(batch))
            total_collected = start_index + number_returned
            if number_matched not in (None, 'unknown') and total_collected >= int(number_matched):
                break
            elif len(batch) < page_size:  # fallback si numberMatched absent ou inconnu
                break
            start_index += page_size
        if not all_features:
            return False, None, "Aucune entité retournée"
        assembled = {'type': 'FeatureCollection', 'features': all_features}
        if crs_ref:
            assembled['crs'] = crs_ref
        vsimem_path = _unique_vsimem_path(f"{typename.replace(':', '_').replace('.', '_')}_par")
        gdal.FileFromMemBuffer(vsimem_path, json.dumps(assembled).encode('utf-8'))
        return True, vsimem_path, None


    def _fetch_wfs_bbox_to_vsimem(self, wfs_url, typename, bbox, crs="EPSG:4326"):
        """[background-safe] Télécharge un WFS single-shot BBOX et écrit dans /vsimem/.

        Returns:
            tuple: (success: bool, vsimem_path: str|None, error: str|None)
        """
        from osgeo import gdal
        xmin, ymin, xmax, ymax = bbox
        url = (f"{wfs_url}?service=WFS&version=2.0.0&request=GetFeature"
               f"&typename={typename}&srsname={crs}&outputFormat=application/json"
               f"&BBOX={xmin},{ymin},{xmax},{ymax},{crs}")
        QgsMessageLog.logMessage(
            f"[parallèle] WFS BBOX {typename}: {url}", "VoirieCommunale", Qgis.Info
        )
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                payload = resp.read()
        except (urllib.error.URLError, OSError) as exc:
            return False, None, str(exc)
        vsimem_path = _unique_vsimem_path(f"{typename.replace(':', '_').replace('.', '_')}_bbox_par")
        gdal.FileFromMemBuffer(vsimem_path, payload)
        return True, vsimem_path, None


    def _fetch_magosm_to_vsimem(self, bbox, page_size=500):
        """[background-safe] Télécharge MagOSM WFS paginé et écrit dans /vsimem/.

        Returns:
            tuple: (success: bool, vsimem_path: str|None, error: str|None)
        """
        from osgeo import gdal
        typename = "magosm:highways_line"
        crs = "EPSG:4326"
        xmin, ymin, xmax, ymax = bbox
        all_features = []
        start_index = 0
        crs_ref = None
        while True:
            params = {
                'SERVICE': 'WFS', 'VERSION': '2.0.0', 'REQUEST': 'GetFeature',
                'TYPENAMES': typename, 'SRSNAME': crs,
                'OUTPUTFORMAT': 'application/json',
                'COUNT': page_size, 'STARTINDEX': start_index,
                'BBOX': f"{xmin},{ymin},{xmax},{ymax},{crs}",
            }
            url = f"{self.MAGOSM_WFS_URL}?{urllib.parse.urlencode(params)}"
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'QGIS-VoirieCommunale/1.0'})
                with urllib.request.urlopen(req, timeout=180) as resp:
                    fc = json.loads(resp.read().decode('utf-8'))
            except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
                return False, None, str(exc)
            batch = fc.get('features', [])
            if crs_ref is None:
                crs_ref = fc.get('crs', None)
            all_features.extend(batch)
            number_matched = fc.get('numberMatched')
            number_returned = fc.get('numberReturned', len(batch))
            total_collected = start_index + number_returned
            if number_matched not in (None, 'unknown') and total_collected >= int(number_matched):
                break
            elif len(batch) < page_size:  # fallback si numberMatched absent ou inconnu
                break
            start_index += page_size
        if not all_features:
            return False, None, "Aucune entité retournée"
        assembled = {'type': 'FeatureCollection', 'features': all_features}
        if crs_ref:
            assembled['crs'] = crs_ref
        vsimem_path = _unique_vsimem_path("magosm_highways_line_par")
        gdal.FileFromMemBuffer(vsimem_path, json.dumps(assembled).encode('utf-8'))
        return True, vsimem_path, None


    def _fetch_osm_roads_to_vsimem(self, bbox):
        """[background-safe] Télécharge routes OSM via Overpass et convertit en GeoJSON /vsimem/.

        Returns:
            tuple: (success: bool, vsimem_path: str|None, error: str|None)
        """
        from osgeo import gdal
        xmin, ymin, xmax, ymax = bbox
        south, west, north, east = ymin, xmin, ymax, xmax
        query = (
            "[out:json][timeout:120];"
            "("
            f"way[\"highway\"][\"ref\"~\"^(C|R)\"]({south},{west},{north},{east});"
            f"relation[\"route\"][\"ref\"~\"^(C|R)\"]({south},{west},{north},{east});"
            ");"
            "out geom;"
        )
        try:
            data = urllib.parse.urlencode({"data": query}).encode("utf-8")
            request = urllib.request.Request(
                "https://overpass-api.de/api/interpreter", data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            with urllib.request.urlopen(request, timeout=180) as response:
                payload = response.read().decode("utf-8")
        except (urllib.error.URLError, OSError) as exc:
            return False, None, str(exc)
        try:
            data_json = json.loads(payload)
        except json.JSONDecodeError as exc:
            return False, None, f"Parsing Overpass JSON: {exc}"

        elements = data_json.get("elements", [])
        relation_refs = {}
        for elem in elements:
            if elem.get("type") == "relation":
                ref_val = elem.get("tags", {}).get("ref")
                if not ref_val:
                    continue
                for member in elem.get("members", []):
                    if member.get("type") == "way":
                        relation_refs.setdefault(member.get("ref"), set()).add(ref_val)

        def way_to_geojson(tags, geometry_points, ref_value, rel_ref_value):
            highway = tags.get("highway")
            if not highway:
                return None
            chosen_ref = ref_value or rel_ref_value
            if not chosen_ref:
                return None
            ref_text = str(chosen_ref).strip().upper()
            if not (ref_text.startswith("C") or ref_text.startswith("R")):
                return None
            coords = [[p["lon"], p["lat"]] for p in geometry_points if "lon" in p and "lat" in p]
            if len(coords) < 2:
                return None
            return {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coords},
                "properties": {
                    "ref": chosen_ref,
                    "name": tags.get("name", ""),
                    "highway": highway,
                    "rel_ref": rel_ref_value or ""
                }
            }

        features = []
        added_way_ids = set()
        for elem in elements:
            if elem.get("type") != "way" or "geometry" not in elem:
                continue
            way_id = elem.get("id")
            tags = elem.get("tags", {})
            ref_value = tags.get("ref")
            rel_ref_value = ", ".join(sorted(relation_refs[way_id])) if way_id in relation_refs else None
            feat = way_to_geojson(tags, elem["geometry"], ref_value, rel_ref_value)
            if feat:
                features.append(feat)
                added_way_ids.add(way_id)
        for elem in elements:
            if elem.get("type") != "relation":
                continue
            rel_ref = elem.get("tags", {}).get("ref", "")
            if not rel_ref:
                continue
            for member in elem.get("members", []):
                if member.get("type") != "way" or "geometry" not in member:
                    continue
                way_id = member.get("ref")
                if way_id in added_way_ids:
                    continue
                tags = member.get("tags", {}) or {}
                feat = way_to_geojson(tags, member["geometry"], tags.get("ref"), rel_ref)
                if feat:
                    features.append(feat)
                    added_way_ids.add(way_id)

        if not features:
            return False, None, "Aucune route C/R trouvée"
        geojson = {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
            "features": features
        }
        vsimem_path = _unique_vsimem_path("osm_roads_par")
        gdal.FileFromMemBuffer(vsimem_path, json.dumps(geojson).encode('utf-8'))
        return True, vsimem_path, None


    def _make_layer_from_vsimem(self, vsimem_path, layer_name, style_callback=None):
        """[thread principal] Crée un QgsVectorLayer depuis /vsimem/ et l'ajoute au projet.

        Returns:
            tuple: (bool, QgsVectorLayer ou None)
        """
        from osgeo import gdal
        layer = QgsVectorLayer(vsimem_path, layer_name, "ogr")
        if not layer.isValid() or layer.featureCount() == 0:
            gdal.Unlink(vsimem_path)
            QgsMessageLog.logMessage(
                f"✗ {layer_name} : couche invalide depuis vsimem",
                "VoirieCommunale", Qgis.Warning
            )
            return False, None
        self._remove_layers_by_name(layer_name)
        QgsProject.instance().addMapLayer(layer, False); QgsProject.instance().layerTreeRoot().addLayer(layer)
        if style_callback:
            style_callback(layer)
        QgsMessageLog.logMessage(
            f"✓ {layer_name} ({layer.featureCount()} entité(s))",
            "VoirieCommunale", Qgis.Success
        )
        return True, layer


    def _load_wfs_paginated(self, typename, layer_name, cql_filter=None,
                             crs="EPSG:4326", page_size=1000, style_callback=None,
                             bbox=None):
        """Charge une couche WFS via pagination urllib + /vsimem/ (CQL_FILTER et/ou BBOX, COUNT + STARTINDEX).

        Contourne la limite serveur de 1 000 entités par requête en bouclant sur STARTINDEX.
        Assemble toutes les pages en un seul GeoJSON FeatureCollection puis charge via OGR.
        Aucun fichier créé sur le disque.

        Args:
            typename:       Nom complet du type WFS (ex. 'BAN.DATA.GOUV:ban')
            layer_name:     Nom de la couche dans QGIS
            cql_filter:     Filtre CQL optionnel (ex. "code_insee='01234'")
            crs:            Système de référence (défaut EPSG:4326)
            page_size:      Nombre d'entités par page (défaut 1000, max IGN 10000)
            style_callback: Callable(layer) appliqué après chargement
            bbox:           Emprise géographique optionnelle (xmin, ymin, xmax, ymax)
                            exprimée dans le CRS fourni. Si présent, ajoute BBOX au filtre.

        Returns:
            tuple: (bool, QgsVectorLayer ou None)
        """
        from osgeo import gdal

        all_features = []
        start_index = 0
        crs_ref = None  # on récupère le CRS depuis la première page

        while True:
            params = {
                'SERVICE':      'WFS',
                'VERSION':      '2.0.0',
                'REQUEST':      'GetFeature',
                'TYPENAMES':    typename,
                'SRSNAME':      crs,
                'OUTPUTFORMAT': 'application/json',
                'COUNT':        page_size,
                'STARTINDEX':   start_index,
            }
            if cql_filter:
                params['CQL_FILTER'] = cql_filter
            if bbox:
                xmin, ymin, xmax, ymax = bbox
                params['BBOX'] = f"{xmin},{ymin},{xmax},{ymax},{crs}"
            url = f"{self.WFS_IGN_URL}?{urllib.parse.urlencode(params)}"
            QgsMessageLog.logMessage(
                f"WFS paginé {typename} (startIndex={start_index}) : {url}",
                "VoirieCommunale", Qgis.Info
            )
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'QGIS-VoirieCommunale/1.0'})
                with urllib.request.urlopen(req, timeout=120) as resp:
                    fc = json.loads(resp.read().decode('utf-8'))
            except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
                QgsMessageLog.logMessage(
                    f"✗ WFS paginé {typename} (startIndex={start_index}) : {exc}",
                    "VoirieCommunale", Qgis.Critical
                )
                return False, None

            batch = fc.get('features', [])
            if crs_ref is None:
                crs_ref = fc.get('crs', None)
            all_features.extend(batch)
            QgsMessageLog.logMessage(
                f"  page {start_index // page_size + 1} : {len(batch)} entité(s) reçue(s)",
                "VoirieCommunale", Qgis.Info
            )
            number_matched = fc.get('numberMatched')
            number_returned = fc.get('numberReturned', len(batch))
            total_collected = start_index + number_returned
            if number_matched not in (None, 'unknown') and total_collected >= int(number_matched):
                break
            elif len(batch) < page_size:  # fallback si numberMatched absent ou inconnu
                break
            start_index += page_size

        if not all_features:
            QgsMessageLog.logMessage(
                f"✗ {layer_name} : aucune entité retournée par le WFS",
                "VoirieCommunale", Qgis.Warning
            )
            return False, None

        # Assembler le FeatureCollection complet
        assembled = {'type': 'FeatureCollection', 'features': all_features}
        if crs_ref:
            assembled['crs'] = crs_ref

        vsimem_path = f"/vsimem/{typename.replace(':', '_').replace('.', '_')}_paginated.json"
        gdal.FileFromMemBuffer(vsimem_path, json.dumps(assembled).encode('utf-8'))
        layer = QgsVectorLayer(vsimem_path, layer_name, "ogr")

        if not layer.isValid() or layer.featureCount() == 0:
            gdal.Unlink(vsimem_path)
            QgsMessageLog.logMessage(
                f"✗ {layer_name} : couche invalide après assemblage ({len(all_features)} entités collectées)",
                "VoirieCommunale", Qgis.Warning
            )
            return False, None

        self._remove_layers_by_name(layer_name)
        QgsProject.instance().addMapLayer(layer, False); QgsProject.instance().layerTreeRoot().addLayer(layer)
        if style_callback:
            style_callback(layer)
        QgsMessageLog.logMessage(
            f"✓ {layer_name} ({layer.featureCount()} entité(s), {len(all_features)} chargées en {start_index // page_size + 1} page(s))",
            "VoirieCommunale", Qgis.Success
        )
        return True, layer


    def load_commune_wfs(self, code_insee):
        """Charge l'emprise de la commune depuis le WFS Admin Express IGN
        
        Returns:
            tuple: (bool, QgsVectorLayer ou None) - (succès, couche chargée)
        """
        success, layer = self.load_wfs_layer(
            typename="LIMITES_ADMINISTRATIVES_EXPRESS.LATEST:commune",
            layer_name=f"Commune {code_insee}",
            code_insee=code_insee,
            crs="EPSG:4326"
        )
        
        if not success:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Emprise communale non disponible",
                f"Impossible de charger l'emprise pour le code INSEE {code_insee}.\n\n"
                "Consultez le journal des messages pour plus de détails."
            )

        return success, layer
    

    def load_majic_parcelles(self, code_insee, progress_cb=None):
        """Charge les parcelles des personnes morales (MAJIC) sous forme de polygones.

        Stratégie en deux étapes :
        1. Récupère les attributs MAJIC depuis l'API Koumoul (DGFiP) pour la commune.
        2. Charge les géométries des parcelles correspondantes depuis le WFS IGN
           Géoplateforme (CADASTRALPARCELS.PARCELLAIRE_EXPRESS:parcelle), en filtrant
           directement par identifiant de parcelle (idu IN (...)) par lots, plutôt que
           de télécharger l'intégralité des parcelles de la commune : pour une commune
           étendue (ex. commune de montagne), le cadastre total peut compter plusieurs
           dizaines de milliers de parcelles alors que seule une fraction est concernée
           par MAJIC, d'où un gain important de volume transféré et de temps de calcul.
        3. Crée une couche polygone mémoire avec uniquement les parcelles MAJIC.

        Args:
            code_insee: Code INSEE de la commune (5 caractères)
            progress_cb: Callback optionnel appelé avec un message de progression
                         (str) à chaque page/lot téléchargé, pour informer l'utilisateur
                         pendant les deux phases (Koumoul, puis WFS).

        Returns:
            tuple: (bool, QgsVectorLayer ou None)
        """
        def _report(msg):
            if progress_cb:
                progress_cb(msg)

        # ── Étape 1 : attributs MAJIC depuis Koumoul ──────────────────────────
        BASE_URL = "https://koumoul.com/data-fair/api/v1/datasets/parcelles-des-personnes-morales/lines"
        SELECT = ",".join([
            "code_parcelle", "denomination", "groupe_personne",
            "forme_juridique_abregee", "numero_siren", "contenance_parcelle",
            "nature_culture", "adresse"
        ])

        QgsMessageLog.logMessage(
            f"MAJIC : chargement des attributs pour {code_insee}",
            "VoirieCommunale", Qgis.Info
        )

        majic_by_parcelle = {}
        size = 1000
        after = None
        koumoul_page = 0

        try:
            while True:
                koumoul_page += 1
                _report(f"Parcelles MAJIC ({code_insee}) : lecture des attributs (page {koumoul_page})...")
                params = {
                    'qs': f'code_commune:{code_insee}',
                    'size': size,
                    'select': SELECT
                }
                if after:
                    params['after'] = after
                url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"

                req = urllib.request.Request(
                    url, headers={'User-Agent': 'QGIS-VoirieCommunale/1.0'}
                )
                with urllib.request.urlopen(req, timeout=30) as response:
                    data = json.loads(response.read().decode('utf-8'))

                for r in data.get('results', []):
                    cp = r.get('code_parcelle')
                    if cp:
                        majic_by_parcelle[cp] = r

                next_url = data.get('next')
                batch_len = len(data.get('results', []))
                if not next_url or batch_len < size:
                    break
                after_qs = urllib.parse.parse_qs(
                    urllib.parse.urlparse(next_url).query
                )
                after = (after_qs.get('after') or [None])[0]
                if not after:
                    break

        except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            QgsMessageLog.logMessage(
                f"MAJIC : erreur API Koumoul : {e}",
                "VoirieCommunale", Qgis.Critical
            )
            return False, None

        if not majic_by_parcelle:
            QgsMessageLog.logMessage(
                f"MAJIC : aucune parcelle trouvée pour {code_insee}",
                "VoirieCommunale", Qgis.Warning
            )
            return False, None

        QgsMessageLog.logMessage(
            f"MAJIC : {len(majic_by_parcelle)} parcelles MAJIC trouvées pour {code_insee}",
            "VoirieCommunale", Qgis.Info
        )

        # ── Étape 2 : géométries depuis le WFS IGN, filtrées par lots d'idu ───
        # Extraire code_dep et code_com selon le format du code INSEE
        import re as _re
        if _re.match(r'97[1-6]', code_insee):
            code_dep = code_insee[:3]
            code_com = code_insee[3:]
        else:
            code_dep = code_insee[:2]
            code_com = code_insee[2:]

        WFS_URL = "https://data.geopf.fr/wfs"
        CHUNK_SIZE = 300  # nb de codes idu par requête (URL raisonnable, largement < COUNT max)
        MAX_ATTEMPTS = 3  # le WFS IGN peut être ponctuellement lent/instable sur certains lots
        RETRY_DELAY_S = 3

        majic_codes = list(majic_by_parcelle.keys())
        chunks = [majic_codes[i:i + CHUNK_SIZE] for i in range(0, len(majic_codes), CHUNK_SIZE)]
        total_chunks = len(chunks)

        wfs_features = []
        failed_chunks = 0  # lots définitivement en échec après tous les essais (dégradation gracieuse)

        for i, chunk in enumerate(chunks, start=1):
            idu_list = ",".join(f"'{c}'" for c in chunk)
            params = {
                'SERVICE': 'WFS',
                'VERSION': '2.0.0',
                'REQUEST': 'GetFeature',
                'TYPENAMES': 'CADASTRALPARCELS.PARCELLAIRE_EXPRESS:parcelle',
                'CQL_FILTER': f"code_dep='{code_dep}' AND code_com='{code_com}' AND idu IN ({idu_list})",
                'OUTPUTFORMAT': 'application/json',
                'COUNT': CHUNK_SIZE,
            }
            url = f"{WFS_URL}?{urllib.parse.urlencode(params)}"

            fc = None
            last_error = None
            for attempt in range(1, MAX_ATTEMPTS + 1):
                suffix = f" (essai {attempt}/{MAX_ATTEMPTS})" if attempt > 1 else ""
                _report(f"Parcelles MAJIC ({code_insee}) : géométries WFS (lot {i}/{total_chunks}){suffix}...")
                try:
                    req = urllib.request.Request(
                        url, headers={'User-Agent': 'QGIS-VoirieCommunale/1.0'}
                    )
                    with urllib.request.urlopen(req, timeout=60) as response:
                        fc = json.loads(response.read().decode('utf-8'))
                    break
                except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
                    last_error = e
                    QgsMessageLog.logMessage(
                        f"MAJIC WFS lot {i}/{total_chunks} : échec essai {attempt}/{MAX_ATTEMPTS} : {e}",
                        "VoirieCommunale", Qgis.Warning
                    )
                    if attempt < MAX_ATTEMPTS:
                        time.sleep(RETRY_DELAY_S)

            if fc is None:
                # Lot définitivement perdu après tous les essais : on ne perd pas tout
                # le chargement pour autant, seules ces quelques parcelles manqueront
                # (signalé à l'utilisateur en fin de traitement).
                failed_chunks += 1
                QgsMessageLog.logMessage(
                    f"MAJIC WFS lot {i}/{total_chunks} : abandonné après {MAX_ATTEMPTS} essais ({last_error}), "
                    f"{len(chunk)} parcelle(s) ne seront pas géolocalisées",
                    "VoirieCommunale", Qgis.Critical
                )
                continue

            wfs_features.extend(fc.get('features', []))

        if failed_chunks:
            _report(
                f"Parcelles MAJIC ({code_insee}) : {failed_chunks} lot(s) sur {total_chunks} "
                "n'ont pas pu être récupérés (instabilité réseau)..."
            )
            # Signalé au code appelant (voirie_communale.py) pour afficher un avertissement
            # après la fermeture de la barre de progression, sans bloquer le chargement.
            self._majic_partial_failure_msg = (
                f"Le WFS IGN a été instable pendant le chargement des parcelles MAJIC de "
                f"{code_insee} : {failed_chunks} lot(s) sur {total_chunks} n'ont pas pu être "
                "récupérés malgré plusieurs tentatives. Certaines parcelles ne sont donc pas "
                "affichées sur la carte, bien que présentes dans les données MAJIC.\n\n"
                "Vous pouvez réessayer (« Forcer le rechargement ») pour tenter de récupérer "
                "les lots manquants."
            )
        else:
            self._majic_partial_failure_msg = None

        if not wfs_features:
            QgsMessageLog.logMessage(
                f"MAJIC : aucune géométrie WFS récupérée pour {code_insee}",
                "VoirieCommunale", Qgis.Critical
            )
            return False, None

        QgsMessageLog.logMessage(
            f"MAJIC : {len(wfs_features)} polygones WFS chargés pour {code_insee}"
            + (f" ({failed_chunks} lot(s) sur {total_chunks} en échec)" if failed_chunks else ""),
            "VoirieCommunale", Qgis.Info
        )

        # ── Étape 3 : jointure et création de la couche polygone ─────────────
        uri = (
            "MultiPolygon?crs=EPSG:4326"
            "&field=code_parcelle:string"
            "&field=denomination:string"
            "&field=groupe_personne:integer"
            "&field=forme_juridique:string"
            "&field=numero_siren:string"
            "&field=contenance_m2:integer"
            "&field=nature_culture:string"
            "&field=adresse:string"
            "&field=section:string"
            "&field=numero:string"
        )
        layer = QgsVectorLayer(uri, f"Parcelles MAJIC {code_insee}", "memory")
        provider = layer.dataProvider()

        def geojson_to_qgsgeometry(geom_dict):
            """Convertit un dict GeoJSON geometry en QgsGeometry (Polygon/MultiPolygon)."""
            gtype = geom_dict.get('type', '')
            coords = geom_dict.get('coordinates', [])
            if gtype == 'Polygon':
                rings = [[QgsPointXY(x, y) for x, y in ring] for ring in coords]
                return QgsGeometry.fromPolygonXY(rings)
            elif gtype == 'MultiPolygon':
                polys = [
                    [[QgsPointXY(x, y) for x, y in ring] for ring in poly]
                    for poly in coords
                ]
                return QgsGeometry.fromMultiPolygonXY(polys)
            return QgsGeometry()

        features = []
        matched = 0
        for wfs_feat in wfs_features:
            props = wfs_feat.get('properties', {})
            idu = props.get('idu', '')
            # Correction : tester aussi code_parcelle sans padding, sans majuscules, etc.
            candidates = [idu, idu.lstrip('0'), idu.upper(), idu.lower()]
            majic_match = None
            for c in candidates:
                if c in majic_by_parcelle:
                    majic_match = majic_by_parcelle[c]
                    break
            if not majic_match:
                continue

            m = majic_match
            geom_dict = wfs_feat.get('geometry')
            if not geom_dict:
                continue
            geom = geojson_to_qgsgeometry(geom_dict)
            if geom.isNull():
                continue

            feat = QgsFeature()
            feat.setGeometry(geom)
            groupe = m.get('groupe_personne')
            feat.setAttributes([
                idu,
                m.get('denomination', ''),
                int(groupe) if groupe is not None else None,
                m.get('forme_juridique_abregee', ''),
                m.get('numero_siren', ''),
                m.get('contenance_parcelle'),
                m.get('nature_culture', ''),
                m.get('adresse', ''),
                props.get('section', ''),
                props.get('numero', ''),
            ])
            features.append(feat)
            matched += 1

        provider.addFeatures(features)
        layer.updateExtents()

        # ── Rendu catégorisé par groupe_personne (légende identique à Koumoul) ──
        self.apply_majic_style(layer)

        self._remove_layers_by_name(f"Parcelles MAJIC {code_insee}")
        QgsProject.instance().addMapLayer(layer, False); QgsProject.instance().layerTreeRoot().addLayer(layer)

        QgsMessageLog.logMessage(
            f"MAJIC : {matched} parcelles polygones chargées pour {code_insee} "
            f"({len(majic_by_parcelle) - matched} non géolocalisées dans WFS)",
            "VoirieCommunale", Qgis.Info
        )
        return True, layer


    # URL de l'export national des filaires de voie des Bases Adresses Locales (BAL)
    FILAIRES_BAL_URL = "https://base-adresse-locale-prod-filaires-de-voie.s3.fr-par.scw.cloud/export-filaires-de-voie.json"

    def load_filaires_bal(self, code_insee, progress_cb=None):
        """Charge les filaires de voie des Bases Adresses Locales (BAL) pour une commune.

        L'export est un unique GeoJSON national (~100 Mo) sans filtre serveur possible :
        le fichier est téléchargé intégralement puis filtré côté client sur la propriété
        'commune' (code INSEE), à l'image de la stratégie utilisée pour les parcelles MAJIC.

        Args:
            code_insee: Code INSEE de la commune (5 caractères)
            progress_cb: Callback optionnel appelé avec un message de progression
                         (str) pendant le téléchargement du fichier national.

        Returns:
            tuple: (bool, QgsVectorLayer ou None, bool) - (succès, couche chargée, aucune_donnee)
                Le 3e élément vaut True si la commune n'a simplement aucune donnée BAL
                disponible (cas normal, pas une erreur technique).
        """
        layer_name = f"Filaires de voie BAL {code_insee}"

        QgsMessageLog.logMessage(
            f"Filaires de voie BAL : téléchargement de l'export national pour {code_insee}",
            "VoirieCommunale", Qgis.Info
        )

        if progress_cb:
            progress_cb("Filaires de voie BAL : téléchargement de l'export national (~100 Mo)...")

        try:
            raw = self._download_with_progress(
                self.FILAIRES_BAL_URL, progress_cb=progress_cb, timeout=120,
                label="Filaires de voie BAL"
            )
            if progress_cb:
                progress_cb("Filaires de voie BAL : analyse du fichier téléchargé...")
            data = json.loads(raw.decode('utf-8'))
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            QgsMessageLog.logMessage(
                f"Filaires de voie BAL : erreur de téléchargement/parsing : {e}",
                "VoirieCommunale", Qgis.Critical
            )
            return False, None, False

        features_in = [
            feat for feat in data.get('features', [])
            if feat.get('properties', {}).get('commune') == code_insee
        ]

        if not features_in:
            QgsMessageLog.logMessage(
                f"Filaires de voie BAL : aucune voie trouvée pour {code_insee}",
                "VoirieCommunale", Qgis.Warning
            )
            return False, None, True

        uri = "LineString?crs=EPSG:4326&field=nom:string&field=commune:string"
        layer = QgsVectorLayer(uri, layer_name, "memory")
        provider = layer.dataProvider()

        features = []
        for feat_in in features_in:
            coords = feat_in.get('geometry', {}).get('coordinates', [])
            if not coords:
                continue
            points = [QgsPointXY(x, y) for x, y in coords]
            geom = QgsGeometry.fromPolylineXY(points)
            if geom.isNull() or geom.isEmpty():
                continue

            props = feat_in.get('properties', {})
            feat = QgsFeature()
            feat.setGeometry(geom)
            feat.setAttributes([props.get('nom', ''), props.get('commune', '')])
            features.append(feat)

        if not features:
            QgsMessageLog.logMessage(
                f"Filaires de voie BAL : géométries invalides pour {code_insee}",
                "VoirieCommunale", Qgis.Warning
            )
            return False, None, False

        provider.addFeatures(features)
        layer.updateExtents()

        self._remove_layers_by_name(layer_name)
        QgsProject.instance().addMapLayer(layer, False); QgsProject.instance().layerTreeRoot().addLayer(layer)

        QgsMessageLog.logMessage(
            f"Filaires de voie BAL : {len(features)} voie(s) chargée(s) pour {code_insee}",
            "VoirieCommunale", Qgis.Success
        )
        return True, layer, False



