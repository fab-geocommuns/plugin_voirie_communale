# -*- coding: utf-8 -*-
"""
Voirie Communale - Gestion de l'arbre des couches
Copyright (C) 2026 Yann Schwarz <yann.schwarz@gmail.com>
Licence : GNU GPL v2+

Ce module regroupe : la lecture de l'ordre canonique (layer_order.json), le
regroupement des couches d'une commune dans un groupe dedie, le reordonnancement
selon l'ordre canonique, les utilitaires de recherche de couches/groupes par
nom, et le clip geometrique par emprise communale.
"""
import re
from qgis.core import (QgsProject, QgsMessageLog, Qgis, QgsLayerTreeGroup, QgsLayerTreeLayer,
                       QgsVectorLayer, QgsCoordinateTransform, QgsCoordinateReferenceSystem,
                       QgsGeometry, QgsWkbTypes)

from .voirie_communale_dialog import SettingsDialog

# Groupe commune : "{code_insee}" ou "{code_insee} - {nom}", Corse (2A/2B) comprise
_COMMUNE_GROUP_RE = re.compile(r'^(?:\d{2}|2[AB])\d{3}')


class LayerOrderMixin:
    """Regroupe la gestion de l'arbre des couches : ordre canonique, groupement par commune, clip."""

    # ------------------------------------------------------------------
    # Clip géométrique par emprise communale
    # ------------------------------------------------------------------

    def _clip_layer_to_commune(self, layer, commune_layer, buffer_m=25):
        """Filtre les entités d'une couche vectorielle selon l'emprise de la commune.

        Calcule un buffer (en mètres, en EPSG:2154) autour de la géométrie
        communale, reprojette ce buffer dans le CRS de la couche cible, puis
        ne conserve que les entités dont la géométrie intersecte ce buffer.
        Le résultat est une couche mémoire qui remplace la couche originale
        dans le projet QGIS.

        Args:
            layer: QgsVectorLayer à filtrer (déjà chargée dans le projet)
            commune_layer: QgsVectorLayer contenant la géométrie de la commune
            buffer_m: rayon du buffer en mètres (défaut 25)

        Returns:
            QgsVectorLayer filtrée (couche mémoire), ou la couche originale
            si le clip échoue.
        """
        try:
            # 1. Fusionner les géométries de la couche commune
            geom_commune = None
            for feat in commune_layer.getFeatures():
                g = feat.geometry()
                if g and not g.isEmpty():
                    geom_commune = g if geom_commune is None else geom_commune.combine(g)

            if geom_commune is None or geom_commune.isEmpty():
                QgsMessageLog.logMessage(
                    "Clip commune : géométrie communale vide, clip ignoré.",
                    "VoirieCommunale", Qgis.Warning
                )
                return layer

            # 2. Reprojeter la géométrie en EPSG:2154 pour le buffer métrique
            crs_2154 = QgsCoordinateReferenceSystem("EPSG:2154")
            crs_commune = commune_layer.crs()
            if crs_commune != crs_2154:
                xform_to_2154 = QgsCoordinateTransform(
                    crs_commune, crs_2154, QgsProject.instance()
                )
                geom_2154 = QgsGeometry(geom_commune)
                geom_2154.transform(xform_to_2154)
            else:
                geom_2154 = geom_commune

            # 3. Appliquer le buffer en mètres
            mask_2154 = geom_2154.buffer(buffer_m, 25) if buffer_m > 0 else geom_2154

            # 4. Reprojeter le masque dans le CRS de la couche cible
            crs_layer = layer.crs()
            if crs_layer != crs_2154:
                xform_to_layer = QgsCoordinateTransform(
                    crs_2154, crs_layer, QgsProject.instance()
                )
                mask = QgsGeometry(mask_2154)
                mask.transform(xform_to_layer)
            else:
                mask = mask_2154

            # 5. Filtrer les entités qui intersectent le masque
            kept_features = [
                f for f in layer.getFeatures()
                if f.geometry() and not f.geometry().isEmpty()
                and f.geometry().intersects(mask)
            ]

            if not kept_features:
                QgsMessageLog.logMessage(
                    f"Clip commune : aucune entité conservée pour la couche '{layer.name()}'.",
                    "VoirieCommunale", Qgis.Warning
                )
                return layer

            # 6. Créer une couche mémoire avec les entités filtrées
            # QgsWkbTypes.displayString() retourne "LineString", "MultiLineString", etc.
            # (contrairement à geometryDisplayString qui retourne "Line" — invalide pour le provider mémoire)
            geom_type_str = QgsWkbTypes.displayString(layer.wkbType())
            crs_authid = crs_layer.authid()
            mem_layer = QgsVectorLayer(
                f"{geom_type_str}?crs={crs_authid}",
                layer.name(),
                "memory"
            )
            if not mem_layer.isValid():
                QgsMessageLog.logMessage(
                    f"Clip commune : couche mémoire invalide pour '{layer.name()}' (type={geom_type_str}), clip ignoré.",
                    "VoirieCommunale", Qgis.Warning
                )
                return layer
            mem_provider = mem_layer.dataProvider()
            mem_provider.addAttributes(layer.fields().toList())
            mem_layer.updateFields()
            mem_provider.addFeatures(kept_features)
            mem_layer.updateExtents()

            # Conserver le style de la couche originale
            mem_layer.setRenderer(layer.renderer().clone())
            if layer.labeling():
                mem_layer.setLabeling(layer.labeling().clone())
                mem_layer.setLabelsEnabled(layer.labelsEnabled())

            # 7. Remplacer dans le projet
            layer_id = layer.id()
            layer_tree = QgsProject.instance().layerTreeRoot()
            layer_node = layer_tree.findLayer(layer_id)
            parent_node = layer_node.parent() if layer_node else layer_tree

            QgsProject.instance().removeMapLayer(layer_id)
            QgsProject.instance().addMapLayer(mem_layer, False)
            parent_node.insertLayer(0, mem_layer)

            QgsMessageLog.logMessage(
                f"Clip commune : {len(kept_features)} entités conservées pour '{mem_layer.name()}'.",
                "VoirieCommunale", Qgis.Info
            )
            return mem_layer

        except Exception as exc:
            # Frontière volontairement large : de nombreuses opérations QGIS
            # (géométrie, provider mémoire, arbre des couches) peuvent échouer
            # ici pour des raisons variées ; on préfère renvoyer la couche
            # d'origine non clippée plutôt que d'interrompre le chargement.
            QgsMessageLog.logMessage(
                f"Clip commune : erreur sur '{layer.name()}' : {exc}",
                "VoirieCommunale", Qgis.Warning
            )
            return layer


    def _load_canonical_order(self):
        """Retourne l'ordre canonique (commune_group, root) : ordre personnalisé du
        profil QGIS, sinon layer_order.json du plugin (voir SettingsDialog._read_layer_order).

        Si aucun n'est lisible, retourne les valeurs par défaut hardcodées et logue
        un avertissement.
        """
        commune_group, root = SettingsDialog._read_layer_order()
        if commune_group and root:
            return commune_group, root
        else:
            QgsMessageLog.logMessage(
                "layer_order.json illisible ou incomplet — ordre canonique par défaut utilisé",
                "VoirieCommunale", Qgis.Warning
            )
            # Valeurs de repli (identiques au contenu initial du JSON)
            commune_group = [
                "BD TOPO Tron\u00e7ons de route {code_insee}",
                "BD TOPO Routes num\u00e9rot\u00e9es ou nomm\u00e9es {code_insee}",
                "DGCL Voirie communale retenue DSR 2026 {code_insee}",
                "DGCL Voirie d\u00e9partementale retenue DGF 2026 {code_insee}",
                "OSM Routes {code_insee}",
                "MagOSM Routes {code_insee}",
                "Adresses BAN {code_insee}",
                "Filaires de voie BAL {code_insee}",
                "Voies EDIGEO (cadastre) {code_insee}",
                "Parcelles MAJIC {code_insee}",
                "Commune {code_insee}",
                "Cadastre - {code_insee}",
            ]
            root = [
                "G\u00e9ofoncier public",
                "__COMMUNE_GROUP__",
                "PLAN IGN J+1", "Waze", "OSM France",
                "CoSIA (Couverture du Sol par IA)",
                "BD ORTHO\u00ae 20 cm", "MNT LiDAR HD",
                "Photos a\u00e9riennes 1950-1965", "Photos a\u00e9riennes 1965-1980",
                "Photos a\u00e9riennes 1980-1995", "Photos a\u00e9riennes 2000-2005",
                "Photos a\u00e9riennes 2006-2010", "Photos a\u00e9riennes 2011-2015",
                "Photos a\u00e9riennes 2016-2020", "Photos a\u00e9riennes 2021-2023",
                "SCAN 50\u00ae 1950", "Carte de Cassini", "Carte d'\u00c9tat-Major",
            ]
            return commune_group, root


    def _reorder_layers(self, code_insee):
        """Réordonne les couches chargées dans le panneau selon un ordre canonique.

        Ordre canonique (du haut vers le bas) :
        groupes communes (courant en tête) → fonds raster → rasters historiques.
        Tous les groupes communes présents dans le projet (détectés par préfixe INSEE)
        sont repositionnés ensemble au-dessus des WMS globaux.

        Algorithme : insert-at-0 en ordre inversé — déplace chaque item connu en tête
        de liste, un par un. Les items inconnus ne sont pas touchés (restent en place).
        """
        root = QgsProject.instance().layerTreeRoot()

        # Ordre chargé depuis layer_order.json (root = items à la racine)
        _, root_order_templates = self._load_canonical_order()

        for name in reversed(root_order_templates):
            if name == "__COMMUNE_GROUP__":
                # Traiter TOUS les groupes communes (préfixe code INSEE)
                # dans leur ordre actuel dans l'arbre (du haut vers le bas)
                commune_groups = [
                    child for child in root.children()
                    if isinstance(child, QgsLayerTreeGroup) and _COMMUNE_GROUP_RE.match(child.name())
                ]
                if not commune_groups:
                    continue
                # Séparer la commune courante des autres
                current = [g for g in commune_groups
                           if g.name() == code_insee or g.name().startswith(code_insee + ' - ')]
                others   = [g for g in commune_groups if g not in current]
                # Ordre d'insertion à la position 0 :
                # reversed(others) en premier → current en dernier
                # → après la boucle : current en tête, others dans leur ordre original
                for group in list(reversed(others)) + current:
                    clone = group.clone()
                    root.insertChildNode(0, clone)
                    root.removeChildNode(group)
            else:
                target = None
                for child in root.children():
                    if isinstance(child, QgsLayerTreeGroup) and child.name() == name:
                        target = child
                        break
                    elif isinstance(child, QgsLayerTreeLayer):
                        layer = child.layer()
                        if layer and layer.name() == name:
                            target = child
                            break
                if target is None:
                    continue
                clone = target.clone()
                root.insertChildNode(0, clone)
                root.removeChildNode(target)

        QgsMessageLog.logMessage(
            f"Couches réordonnées selon l'ordre canonique pour {code_insee}",
            "VoirieCommunale",
            Qgis.Info
        )


    def _layer_exists_by_name(self, name):
        """Retourne True si une couche portant ce nom exact existe dans le projet."""
        return any(lyr.name() == name for lyr in QgsProject.instance().mapLayers().values())


    def _get_layers_by_name(self, name):
        """Retourne la liste des couches du projet portant ce nom exact."""
        return [lyr for lyr in QgsProject.instance().mapLayers().values() if lyr.name() == name]


    def _group_exists_by_name(self, name):
        """Retourne True si un groupe portant ce nom existe dans l'arbre des couches."""
        return QgsProject.instance().layerTreeRoot().findGroup(name) is not None


    def _get_group_layers(self, group_name):
        """Retourne les couches d'un groupe existant."""
        root = QgsProject.instance().layerTreeRoot()
        group = root.findGroup(group_name)
        if group:
            return [child.layer() for child in group.findLayers() if child.layer()]
        return []


    def _remove_layers_by_name(self, layer_name):
        """Supprime toutes les couches du projet portant ce nom exact."""
        to_remove = [
            lid for lid, lyr in QgsProject.instance().mapLayers().items()
            if lyr.name() == layer_name
        ]
        for lid in to_remove:
            QgsProject.instance().removeMapLayer(lid)


    def _remove_group_by_name(self, group_name):
        """Supprime récursivement un groupe (et ses couches) dans l'arbre des couches."""
        root = QgsProject.instance().layerTreeRoot()
        group = root.findGroup(group_name)
        if group:
            # Supprimer d'abord les couches du projet
            for child in group.findLayers():
                QgsProject.instance().removeMapLayer(child.layerId())
            root.removeChildNode(group)


    def _get_commune_name(self, code_insee, commune_layer=None):
        """Récupère le nom de la commune depuis sa couche chargée ou les couches du projet.

        Returns:
            str or None: Nom de la commune, ou None si non trouvé
        """
        def _extract_nom(lyr):
            for feature in lyr.getFeatures():
                try:
                    val = feature.attribute('nom_officiel')
                    if val:
                        return str(val)
                except KeyError:
                    pass
            return None

        if commune_layer and commune_layer.isValid():
            nom = _extract_nom(commune_layer)
            if nom:
                return nom

        commune_layer_name = f"Commune {code_insee}"
        for lyr in QgsProject.instance().mapLayers().values():
            if lyr.name() == commune_layer_name:
                nom = _extract_nom(lyr)
                if nom:
                    return nom
        return None


    def _group_commune_layers(self, code_insee, commune_name=None):
        """Regroupe les couches de données spécifiques à la commune dans un groupe dédié.

        Seules les couches filtrées sur la commune (vecteurs + cadastre) sont regroupées.
        Les fonds raster communs (PLAN IGN, Waze, BD ORTHO, etc.) restent à la racine.

        Le groupe est nommé "{code_insee} - {nom_commune}" ou "{code_insee}" si le nom est inconnu.
        Si le groupe existe déjà (rechargement partiel), les nouvelles couches y sont ajoutées
        sans supprimer les couches du chargement précédent.
        Les couches dans le groupe sont ensuite réordonnées selon l'ordre canonique.
        """
        root = QgsProject.instance().layerTreeRoot()

        group_name = f"{code_insee} - {commune_name}" if commune_name else code_insee

        # Ordre canonique des couches à l'intérieur du groupe (haut → bas)
        # Ordre chargé depuis layer_order.json, {}  remplacé par le code_insee réel
        commune_group_templates, _ = self._load_canonical_order()
        canonical_order_in_group = [
            name.replace('{code_insee}', code_insee)
            for name in commune_group_templates
        ]
        canonical_names = set(canonical_order_in_group)

        # Identifier les nœuds à la RACINE à déplacer et la position du premier.
        # On ne touche pas aux nœuds déjà à l'intérieur du groupe existant.
        to_move = []
        first_idx = None
        for i, child in enumerate(root.children()):
            node_name = None
            if isinstance(child, QgsLayerTreeGroup):
                node_name = child.name()
            elif isinstance(child, QgsLayerTreeLayer):
                layer = child.layer()
                if layer:
                    node_name = layer.name()
            if node_name in canonical_names:
                if first_idx is None:
                    first_idx = i
                to_move.append(child)

        # Chercher un groupe existant pour cette commune.
        # On cherche par préfixe code_insee car le nom peut différer si commune_name
        # n'était pas disponible lors du 1er chargement (ex: "75056" vs "75056 - Paris").
        existing_group = None
        for child in root.children():
            if isinstance(child, QgsLayerTreeGroup):
                cname = child.name()
                if cname == code_insee or cname.startswith(code_insee + ' - '):
                    existing_group = child
                    # Renommer le groupe si on a maintenant le nom complet
                    if commune_name and cname == code_insee:
                        child.setName(group_name)
                    break

        if existing_group and not to_move:
            # Groupe existant, rien de nouveau à déplacer : rien à faire
            return

        if existing_group:
            # Le groupe existe déjà (rechargement partiel) : ajouter les nouvelles couches
            # sans supprimer celles qui n'ont pas été rechargées.
            for node in to_move:
                clone = node.clone()
                existing_group.addChildNode(clone)
                root.removeChildNode(node)
            target_group = existing_group
        elif to_move:
            # Créer le groupe à la position du premier nœud correspondant
            target_group = root.insertGroup(first_idx, group_name)

            # Déplacer les nœuds dans le groupe (clone + suppression originale)
            for node in to_move:
                clone = node.clone()
                target_group.addChildNode(clone)
                root.removeChildNode(node)

            target_group.setExpanded(True)
        else:
            return

        # Réordonner les couches à l'intérieur du groupe selon l'ordre canonique.
        # Technique : insertion en position 0 en ordre inversé.
        # Gère à la fois les QgsLayerTreeLayer (couches) et QgsLayerTreeGroup (ex: Cadastre).
        for name in reversed(canonical_order_in_group):
            target = None
            for child in target_group.children():
                if isinstance(child, QgsLayerTreeGroup) and child.name() == name:
                    target = child
                    break
                elif isinstance(child, QgsLayerTreeLayer):
                    layer = child.layer()
                    if layer and layer.name() == name:
                        target = child
                        break
            if target is None:
                continue
            clone = target.clone()
            target_group.insertChildNode(0, clone)
            target_group.removeChildNode(target)

        QgsMessageLog.logMessage(
            f"Couches regroup\u00e9es et r\u00e9ordonn\u00e9es dans '{group_name}'",
            "VoirieCommunale",
            Qgis.Info
        )


