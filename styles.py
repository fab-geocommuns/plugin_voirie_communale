# -*- coding: utf-8 -*-
"""
Voirie Communale - Symbologie (styles, couleurs, regles de rendu)
Copyright (C) 2026 Yann Schwarz <yann.schwarz@gmail.com>
Licence : GNU GPL v2+

Ce module regroupe la logique de symbologie du plugin : dictionnaires de
couleurs (MAJIC), et methodes appliquant des QgsRuleBasedRenderer / renderers
categorises sur les couches chargees (BD TOPO, BAN, OSM, MagOSM).
"""
from qgis.PyQt.QtGui import QColor
from qgis.core import (Qgis, QgsMessageLog,
                       QgsMarkerSymbol,
                       QgsPalLayerSettings, QgsTextFormat, QgsVectorLayerSimpleLabeling,
                       QgsTextBufferSettings)

from .voirie_communale_dialog import SettingsDialog


# Groupes et couleurs exacts de l'application Koumoul
# Source : configuration de https://koumoul.com/data-fair/app/carte-des-parcelles-des-personnes-morales-majic
# Le champ groupe_personne est un entier (0-9)
MAJIC_GROUPES = {
    0: ("Personnes morales non remarquables", "#FF0000"),
    1: ("État",                               "#F79F11"),
    2: ("Région",                             "#068031"),
    3: ("Département",                        "#6CF163"),
    4: ("Commune",                            "#45C6E6"),
    5: ("Office HLM",                         "#F551E4"),
    6: ("Sociétés d'économie mixte",          "#FFFA00"),
    7: ("Copropriétaires",                    "#04147C"),
    8: ("Associés",                           "#6F2002"),
    9: ("Établissements publics ou organismes associés", "#0521DB"),
}
_MAJIC_GROUPE_DEFAULT_COLOR = "#A337F5"


class StylesMixin:
    """Regroupe les methodes de symbologie (styles, couleurs, regles) du plugin."""

    @staticmethod
    def _make_line_symbol(color, width, dash=False, rounded=False):
        """Crée un QgsLineSymbol simple (couleur, largeur, tirets optionnels).

        Utilisé par les styles à règles (BD TOPO tronçons, MagOSM, EDIGEO Voies)
        pour éviter de dupliquer la même fonction locale dans chaque méthode.
        """
        from qgis.core import QgsLineSymbol
        props = {'color': color, 'width': str(width)}
        if dash:
            props['line_style'] = 'dash'
        if rounded:
            props['capstyle'] = 'round'
            props['joinstyle'] = 'round'
        return QgsLineSymbol.createSimple(props)

    @staticmethod
    def _apply_simple_line_labels(layer, field_name, size=8):
        """Applique un étiquetage simple (champ brut, buffer blanc) sur une couche
        de lignes. Factorise le bloc QgsPalLayerSettings/QgsTextFormat/
        QgsTextBufferSettings dupliqué dans les styles à règles.
        """
        lbl = QgsPalLayerSettings()
        lbl.isExpression = False
        lbl.fieldName = field_name
        lbl.enabled = True
        lbl.placement = QgsPalLayerSettings.Line
        fmt = QgsTextFormat()
        fmt.setSize(size)
        fmt.setColor(QColor(0, 0, 0))
        buf = QgsTextBufferSettings()
        buf.setEnabled(True)
        buf.setSize(0.5)
        buf.setColor(QColor(255, 255, 255))
        fmt.setBuffer(buf)
        lbl.setFormat(fmt)
        layer.setLabeling(QgsVectorLayerSimpleLabeling(lbl))
        layer.setLabelsEnabled(True)
        layer.triggerRepaint()

    def apply_majic_style(self, layer):
        """Applique le rendu catégorisé MAJIC (par 'groupe_personne') à `layer`.

        Construit les catégories à partir des valeurs de `groupe_personne`
        réellement présentes dans les attributs de la couche (et non depuis
        les données Koumoul brutes), afin de pouvoir être réutilisée aussi
        bien juste après téléchargement que lors d'un chargement depuis le
        cache local (où seule la couche polygone existe, sans accès aux
        données API d'origine).
        """
        from qgis.core import QgsFillSymbol, QgsCategorizedSymbolRenderer, QgsRendererCategory

        if layer.fields().indexOf('groupe_personne') < 0:
            return

        unique_groupes = sorted({
            int(v) for v in layer.uniqueValues(layer.fields().indexOf('groupe_personne'))
            if v is not None
        })
        cat_styles = []
        for g in unique_groupes:
            libelle, couleur = MAJIC_GROUPES.get(g, (f'Groupe {g}', _MAJIC_GROUPE_DEFAULT_COLOR))
            symbol = QgsFillSymbol.createSimple({
                'color': couleur,
                'outline_color': '#333333',
                'outline_width': '0.25',
            })
            cat_styles.append(QgsRendererCategory(g, symbol, libelle))
        layer.setRenderer(QgsCategorizedSymbolRenderer('groupe_personne', cat_styles))

    def _apply_bdtopo_troncons_style(self, layer, regex_chemin=None, regex_voie=None):
        """Style à règles : regex de filtrage (chemin rural / voie communale) en priorité
        sur le champ 'nom_1_gauche', puis catégorisation par 'nature'.
        """
        from qgis.core import QgsRuleBasedRenderer
        regex_chemin = regex_chemin or SettingsDialog._DEFAULTS['ban_regex_chemin']
        regex_voie = regex_voie or SettingsDialog._DEFAULTS['ban_regex_voie']

        make_line = self._make_line_symbol

        root_rule = QgsRuleBasedRenderer.Rule(None)  # règle racine (conteneur)

        # ---- 1. Regex CR / VC sur nom_collaboratif_gauche (prioritaires) ----
        nom_field = 'nom_collaboratif_gauche'

        rule_cr = QgsRuleBasedRenderer.Rule(make_line('#8C7274', 0.7))
        rule_cr.setLabel('Chemin rural (nom)')
        rule_cr.setFilterExpression(
            f"regexp_match(\"{nom_field}\", '{self._qgis_expr_regex(regex_chemin)}') > 0"
            f" OR \"cpx_classement_administratif\" = 'Chemin rural'"
        )
        root_rule.appendChild(rule_cr)

        rule_vc = QgsRuleBasedRenderer.Rule(make_line('#FCF6B5', 0.7))
        rule_vc.setLabel('Voie communale (nom)')
        rule_vc.setFilterExpression(
            f"regexp_match(\"{nom_field}\", '{self._qgis_expr_regex(regex_voie)}') > 0"
        )
        root_rule.appendChild(rule_vc)

        # ---- 2. Catégories fusionnées (cpx OR importance OR nature) ----
        # Une seule règle par catégorie sémantique
        cpx_null = "(\"cpx_classement_administratif\" IS NULL OR \"cpx_classement_administratif\" = '')"
        imp_fallback = f"({cpx_null} AND (\"importance\" IS NULL OR \"importance\" >= 5))"

        categories = [
            ('Autoroute',
             "\"cpx_classement_administratif\" = 'Autoroute' OR ({cpx_null} AND \"importance\" = 1)".format(cpx_null=cpx_null),
             '#f26119', 1.4),
            ('Nationale',
             "\"cpx_classement_administratif\" = 'Nationale' OR ({cpx_null} AND \"importance\" = 2)".format(cpx_null=cpx_null),
             '#f2a824', 1.2),
            ('Départementale',
             "\"cpx_classement_administratif\" = 'Départementale' OR ({cpx_null} AND \"importance\" = 3)".format(cpx_null=cpx_null),
             '#F2D7A2', 0.9),
            ('Route intercommunale',
             "\"cpx_classement_administratif\" = 'Route intercommunale'",
             '#2db9fc', 0.8),
            ('Liaison locale',
             "({cpx_null} AND \"importance\" = 4)".format(cpx_null=cpx_null),
             '#FCF0A8', 0.8),
            ('Desserte',
             "({imp_fallback} AND (\"nature\" = 'Route à 1 chaussée' OR \"nature\" = 'Route à 2 chaussées' OR \"nature\" = 'Rond-point'))".format(imp_fallback=imp_fallback),
             '#ededed', 0.7),
            ('Route empierrée',
             "({imp_fallback} AND \"nature\" = 'Route empierrée')".format(imp_fallback=imp_fallback),
             '#7C7C7C', 0.6),
            ('Chemin',
             "({imp_fallback} AND \"nature\" = 'Chemin')".format(imp_fallback=imp_fallback),
             '#8C7274', 0.5),
            ('Sentier',
             "({imp_fallback} AND \"nature\" = 'Sentier')".format(imp_fallback=imp_fallback),
             '#8C7274', 0.4, True),
            ('Bac / Maritime',
             "({imp_fallback} AND \"nature\" = 'Bac ou liaison maritime')".format(imp_fallback=imp_fallback),
             '#5792C2', 0.5),
        ]
        for item in categories:
            label, expr, color, width = item[0], item[1], item[2], item[3]
            dash = item[4] if len(item) > 4 else False
            rule = QgsRuleBasedRenderer.Rule(make_line(color, width, dash))
            rule.setLabel(label)
            rule.setFilterExpression(expr)
            root_rule.appendChild(rule)

        layer.setRenderer(QgsRuleBasedRenderer(root_rule))

        # ---- Étiquettes : champ brut, aucune regex ----
        # Le renderer gère déjà la catégorisation. Le labeling affiche simplement
        # nom_collaboratif_gauche ; QGIS n'affiche rien si le champ est null/vide.
        self._apply_simple_line_labels(layer, nom_field)


    def _apply_bdtopo_routesnom_style(self, layer):
        """Applique une symbologie catégorisée sur 'type_de_route' aux routes BD TOPO nommées."""
        from qgis.core import QgsCategorizedSymbolRenderer, QgsRendererCategory, QgsSymbol
        color_map = {
            'Autoroute':            '#F2A824',
            'Nationale':            '#F2D7A2',
            'Départementale':       '#FCF5AF',
            'Route intercommunale': '#FCF0A8',
            'Voie communale':       '#FCF6B5',
            'Chemin rural':         '#8C7274',
        }
        categories = []
        for route_type, color in color_map.items():
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol.setColor(QColor(color))
            categories.append(QgsRendererCategory(route_type, symbol, route_type))
        layer.setRenderer(QgsCategorizedSymbolRenderer('type_de_route', categories))
        layer.triggerRepaint()


    @staticmethod
    def _get_regex_setting(key, default=None):
        """Lit une regex depuis settings.json, valide, et restaure le défaut si corrompue.

        Args:
            key:     Clé (sans préfixe).
            default: Valeur par défaut. Si omis, prise depuis SettingsDialog._DEFAULTS[key]
                     (source unique de vérité, cf. voirie_communale_dialog.py).

        Returns:
            str: Expression régulière valide.
        """
        import re as _re
        if default is None:
            default = SettingsDialog._DEFAULTS[key]
        val = SettingsDialog.get(key, default)
        try:
            _re.compile(val)
            return val
        except _re.error:
            QgsMessageLog.logMessage(
                f"Regex corrompue pour '{key}' ({val!r}), restauration du défaut.",
                "VoirieCommunale", Qgis.Warning
            )
            SettingsDialog.set(key, default)   # Réparer settings.json
            return default


    @staticmethod
    def _qgis_expr_regex(regex):
        """Prépare une regex pour intégration dans un littéral de chaîne d'expression QGIS.

        Le parseur d'expressions QGIS interprète les séquences d'échappement standard
        (``\\n``, ``\\t``, ``\\b`` = retour arrière, etc.) dans les chaînes entre guillemets
        simples.  Pour que ``\\b`` ou ``\\.`` soient transmis tels quels au moteur regex Qt,
        il faut les doubler : ``\\\\b`` dans la chaîne Python → ``\\b`` dans l'expression
        QGIS → ``\\b`` reçu par le moteur regex.

        Les apostrophes sont doublées (``'`` → ``''``), sinon elles fermeraient le
        littéral et rendraient l'expression invalide (ex. « chemin d'exploitation »).

        Args:
            regex: Expression régulière Python (ex. ``r'\\bC\\.?R\\.?\\b'``).

        Returns:
            str: Regex échappée, prête à être insérée dans ``'...'``.
        """
        return regex.replace('\\', '\\\\').replace("'", "''")

    # ------------------------------------------------------------------
    # Méthodes fetch-to-vsimem (background-safe, sans objets QGIS)
    # Utilisées par WfsLoadTask pour le chargement WFS parallèle
    # ------------------------------------------------------------------


    def apply_ban_style(self, layer, regex_chemin=None, regex_voie=None):
        """Applique un style différencié à la couche BAN selon le type de voie

        Args:
            layer: La couche QgsVectorLayer BAN à styliser
            regex_chemin: Expression régulière QGIS pour détecter les chemins ruraux
            regex_voie: Expression régulière QGIS pour détecter les voies communales
        """
        
        # Créer une expression qui catégorise les voies
        # Recherche dans le champ nom_voie les mots-clés
        field_name = 'nom_voie'
        regex_chemin = regex_chemin or SettingsDialog._DEFAULTS['ban_regex_chemin']
        regex_voie = regex_voie or SettingsDialog._DEFAULTS['ban_regex_voie']
        
        # Vérifier que le champ existe
        if layer.fields().indexOf(field_name) == -1:
            QgsMessageLog.logMessage(
                f"Le champ '{field_name}' n'existe pas dans la couche BAN",
                "VoirieCommunale",
                Qgis.Warning
            )
            return
        
        # Renderer à règles : chaque règle porte une regex de filtre + un symbole ponctuel.
        # QgsRuleBasedRenderer est préférable à QgsCategorizedSymbolRenderer avec une
        # expression CASE WHEN, car QGIS n'affiche pas l'expression dans la légende.
        from qgis.core import QgsRuleBasedRenderer

        def make_marker(color, outline_color, size='3'):
            return QgsMarkerSymbol.createSimple({
                'name': 'circle', 'color': color, 'size': size,
                'outline_color': outline_color, 'outline_width': '0.5'
            })

        root_rule = QgsRuleBasedRenderer.Rule(None)

        # Chemin rural
        rule_cr = QgsRuleBasedRenderer.Rule(make_marker('#8C7274', '#6B5557'))
        rule_cr.setLabel('Chemin rural')
        rule_cr.setFilterExpression(
            f"regexp_match(\"{field_name}\", '{self._qgis_expr_regex(regex_chemin)}') > 0"
        )
        root_rule.appendChild(rule_cr)

        # Voie communale
        rule_vc = QgsRuleBasedRenderer.Rule(make_marker('#B4B4B4', '#909090'))
        rule_vc.setLabel('Voie communale')
        rule_vc.setFilterExpression(
            f"regexp_match(\"{field_name}\", '{self._qgis_expr_regex(regex_voie)}') > 0"
        )
        root_rule.appendChild(rule_vc)

        # Autre – gris, désactivé par défaut
        rule_autre = QgsRuleBasedRenderer.Rule(make_marker('#808080', '#505050', '2.5'))
        rule_autre.setLabel('Autre')
        rule_autre.setActive(False)
        rule_autre.setIsElse(True)   # s'applique à tout ce qui n'est pas matché
        root_rule.appendChild(rule_autre)

        layer.setRenderer(QgsRuleBasedRenderer(root_rule))

        # ---- Étiquettes : champ brut, aucune regex ----
        # Le renderer gère déjà la catégorisation. Le labeling affiche simplement
        # nom_voie ; QGIS n'affiche rien si le champ est null/vide.
        lbl = QgsPalLayerSettings()
        lbl.isExpression = True
        lbl.fieldName = '"numero" || \' \' || "nom_voie"'
        lbl.enabled = True
        lbl.placement = QgsPalLayerSettings.AroundPoint
        fmt = QgsTextFormat()
        fmt.setSize(8)
        fmt.setColor(QColor(0, 0, 0))
        buf = QgsTextBufferSettings()
        buf.setEnabled(True)
        buf.setSize(0.5)
        buf.setColor(QColor(255, 255, 255))
        fmt.setBuffer(buf)
        lbl.setFormat(fmt)
        layer.setLabeling(QgsVectorLayerSimpleLabeling(lbl))
        layer.setLabelsEnabled(True)
        layer.triggerRepaint()
        
        QgsMessageLog.logMessage(
            "Style différencié et étiquettes appliqués à la couche BAN (Chemins ruraux / Voies communales)",
            "VoirieCommunale",
            Qgis.Success
        )
    

    def _style_osm_layer(self, layer):
        """Applique un style catégorisé CE / C / R basé sur le champ ref, avec étiquettes."""
        from qgis.core import QgsRuleBasedRenderer, QgsLineSymbol

        def make_sym(color, width='0.5'):
            return QgsLineSymbol.createSimple({
                'color': color, 'width': width,
                'capstyle': 'round', 'joinstyle': 'round',
            })

        root = QgsRuleBasedRenderer.Rule(None)

        rules = [
            ('"ref" LIKE \'CE%\'',                           make_sym('#8C7274', '0.6'), 'CE – Chemin d\'exploitation'),
            ('"ref" LIKE \'C%\' AND "ref" NOT LIKE \'CE%\'', make_sym('#FCF6B5', '0.6'), 'C – Voie communale'),
            ('"ref" LIKE \'R%\'',                            make_sym('#8C7274', '0.6'), 'R – Chemin rural'),
        ]

        for expr, sym, label in rules:
            rule = QgsRuleBasedRenderer.Rule(sym)
            rule.setLabel(label)
            rule.setFilterExpression(expr)
            root.appendChild(rule)

        layer.setRenderer(QgsRuleBasedRenderer(root))

        # Étiquettes : ref en priorité, sinon name
        label_settings = QgsPalLayerSettings()
        label_settings.fieldName = "coalesce(nullif(\"ref\",''), nullif(\"name\",''))"
        label_settings.isExpression = True
        label_settings.enabled = True
        label_settings.placement = QgsPalLayerSettings.Line

        text_format = QgsTextFormat()
        text_format.setSize(7)
        text_format.setColor(QColor(40, 40, 40))

        buffer = QgsTextBufferSettings()
        buffer.setEnabled(True)
        buffer.setSize(0.8)
        buffer.setColor(QColor(255, 255, 255))
        text_format.setBuffer(buffer)

        label_settings.setFormat(text_format)
        layer.setLabeling(QgsVectorLayerSimpleLabeling(label_settings))
        layer.setLabelsEnabled(True)
        layer.triggerRepaint()

    def _apply_magosm_style(self, layer, regex_chemin=None, regex_voie=None):
        """Style à règles pour la couche MagOSM highways_line.

        Même structure que BD TOPO tronçons :
        1. Règles regex CR/VC sur le champ 'name' (prioritaires)
        2. Catégorisation par valeur du champ 'highway' (à la place de 'nature')
        """
        from qgis.core import QgsRuleBasedRenderer
        regex_chemin = regex_chemin or SettingsDialog._DEFAULTS['ban_regex_chemin']
        regex_voie = regex_voie or SettingsDialog._DEFAULTS['ban_regex_voie']

        def make_line(color, width, dash=False):
            return self._make_line_symbol(color, width, dash=dash, rounded=True)

        nom_field = 'name'
        root_rule = QgsRuleBasedRenderer.Rule(None)

        # ---- 1. Regex CR / VC (prioritaires) ----
        rule_cr = QgsRuleBasedRenderer.Rule(make_line('#8C7274', 0.7))
        rule_cr.setLabel('Chemin rural (nom)')
        rule_cr.setFilterExpression(
            f"regexp_match(\"{nom_field}\", '{self._qgis_expr_regex(regex_chemin)}') > 0"
        )
        root_rule.appendChild(rule_cr)

        rule_vc = QgsRuleBasedRenderer.Rule(make_line('#FCF6B5', 0.7))
        rule_vc.setLabel('Voie communale (nom)')
        rule_vc.setFilterExpression(
            f"regexp_match(\"{nom_field}\", '{self._qgis_expr_regex(regex_voie)}') > 0"
        )
        root_rule.appendChild(rule_vc)

        # ---- 2. Catégorisation par champ 'highway' ----
        highway_map = [
            ('Autoroute',            ['motorway', 'motorway_link'],                                    '#f26119', 1.2, False),
            ('Nationale',            ['trunk', 'trunk_link', 'primary', 'primary_link'],               '#f2a824', 1.0, False),
            ('Départementale',       ['secondary', 'secondary_link'],                                 '#F2D7A2', 0.8, False),
            ('Route intercommunale', ['tertiary', 'tertiary_link'],                                    '#2db9fc', 0.7, False),
            ('Desserte',             ['residential', 'service', 'living_street'],                       '#ededed', 0.6, False),
            ('Chemin',               ['track', 'path', 'bridleway'],                                   '#8C7274', 0.5, False),
            ('Sentier',              ['footway', 'steps'],                                             '#8C7274', 0.4, True),
            ('Piste cyclable',       ['cycleway'],                                                     '#9B5CCC', 0.4, False),
        ]
        for label, vals, color, width, dash in highway_map:
            expr = ' OR '.join(f"\"highway\" = '{v}'" for v in vals)
            rule = QgsRuleBasedRenderer.Rule(make_line(color, width, dash))
            rule.setLabel(label)
            rule.setFilterExpression(expr)
            root_rule.appendChild(rule)

        # Règle par défaut
        rule_default = QgsRuleBasedRenderer.Rule(make_line('#969696', 0.4))
        rule_default.setLabel('(autre)')
        rule_default.setIsElse(True)
        root_rule.appendChild(rule_default)

        layer.setRenderer(QgsRuleBasedRenderer(root_rule))

        # ---- Étiquettes : champ 'name' ----
        self._apply_simple_line_labels(layer, nom_field)

        QgsMessageLog.logMessage(
            "Style différencié appliqué à la couche MagOSM (highway)",
            "VoirieCommunale", Qgis.Success
        )

    def apply_edigeo_voies_style(self, layer, regex_chemin=None, regex_voie=None):
        """Style à règles pour la couche des voies EDIGEO (ZONCOMMUNI_id) : mêmes
        regex de catégorisation (Chemin rural / Voie communale) que BAN, BD TOPO
        tronçons et MagOSM, appliquées sur le nom complet reconstitué (champ 'nom').

        Args:
            layer: La couche QgsVectorLayer des voies EDIGEO à styliser
            regex_chemin: Expression régulière QGIS pour détecter les chemins ruraux
            regex_voie: Expression régulière QGIS pour détecter les voies communales
        """
        from qgis.core import QgsRuleBasedRenderer
        regex_chemin = regex_chemin or SettingsDialog._DEFAULTS['ban_regex_chemin']
        regex_voie = regex_voie or SettingsDialog._DEFAULTS['ban_regex_voie']

        make_line = self._make_line_symbol

        nom_field = 'nom'
        root_rule = QgsRuleBasedRenderer.Rule(None)

        rule_cr = QgsRuleBasedRenderer.Rule(make_line('#8C7274', 0.7, dash=True))
        rule_cr.setLabel('Chemin rural (nom)')
        rule_cr.setFilterExpression(
            f"regexp_match(\"{nom_field}\", '{self._qgis_expr_regex(regex_chemin)}') > 0"
        )
        root_rule.appendChild(rule_cr)

        rule_vc = QgsRuleBasedRenderer.Rule(make_line('#FCF6B5', 0.7, dash=True))
        rule_vc.setLabel('Voie communale (nom)')
        rule_vc.setFilterExpression(
            f"regexp_match(\"{nom_field}\", '{self._qgis_expr_regex(regex_voie)}') > 0"
        )
        root_rule.appendChild(rule_vc)

        rule_autre = QgsRuleBasedRenderer.Rule(make_line('#8C7274', 0.4, dash=True))
        rule_autre.setLabel('(autre)')
        rule_autre.setIsElse(True)
        root_rule.appendChild(rule_autre)

        layer.setRenderer(QgsRuleBasedRenderer(root_rule))

        self._apply_simple_line_labels(layer, nom_field)

        QgsMessageLog.logMessage(
            "Style différencié appliqué à la couche Voies EDIGEO (cadastre) (Chemin rural / Voie communale)",
            "VoirieCommunale", Qgis.Success
        )

    def apply_filaires_bal_style(self, layer, regex_chemin=None, regex_voie=None):
        """Style à règles pour la couche des filaires de voie BAL : mêmes regex de
        catégorisation (Chemin rural / Voie communale) que BAN, BD TOPO tronçons,
        MagOSM et EDIGEO, appliquées sur le nom de voie (champ 'nom'), avec
        étiquetage. Auparavant cette couche ne recevait aucun style ni étiquette
        (renderer/labeling par défaut de QGIS).

        Args:
            layer: La couche QgsVectorLayer des filaires de voie BAL à styliser
            regex_chemin: Expression régulière QGIS pour détecter les chemins ruraux
            regex_voie: Expression régulière QGIS pour détecter les voies communales
        """
        from qgis.core import QgsRuleBasedRenderer
        regex_chemin = regex_chemin or SettingsDialog._DEFAULTS['ban_regex_chemin']
        regex_voie = regex_voie or SettingsDialog._DEFAULTS['ban_regex_voie']

        make_line = self._make_line_symbol

        nom_field = 'nom'
        root_rule = QgsRuleBasedRenderer.Rule(None)

        rule_cr = QgsRuleBasedRenderer.Rule(make_line('#8C7274', 0.7))
        rule_cr.setLabel('Chemin rural (nom)')
        rule_cr.setFilterExpression(
            f"regexp_match(\"{nom_field}\", '{self._qgis_expr_regex(regex_chemin)}') > 0"
        )
        root_rule.appendChild(rule_cr)

        rule_vc = QgsRuleBasedRenderer.Rule(make_line('#FCF6B5', 0.7))
        rule_vc.setLabel('Voie communale (nom)')
        rule_vc.setFilterExpression(
            f"regexp_match(\"{nom_field}\", '{self._qgis_expr_regex(regex_voie)}') > 0"
        )
        root_rule.appendChild(rule_vc)

        rule_autre = QgsRuleBasedRenderer.Rule(make_line('#4A90D9', 0.4))
        rule_autre.setLabel('(autre)')
        rule_autre.setIsElse(True)
        root_rule.appendChild(rule_autre)

        layer.setRenderer(QgsRuleBasedRenderer(root_rule))

        self._apply_simple_line_labels(layer, nom_field)

        QgsMessageLog.logMessage(
            "Style différencié appliqué à la couche Filaires de voie BAL (Chemin rural / Voie communale)",
            "VoirieCommunale", Qgis.Success
        )


