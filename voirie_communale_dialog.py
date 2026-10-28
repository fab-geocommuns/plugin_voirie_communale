# -*- coding: utf-8 -*-
"""
Voirie Communale - Dialogue principal
Copyright (C) 2026 Yann Schwarz <yann.schwarz@gmail.com>
Licence : GNU GPL v2+
"""

import os
import re
import json
import shutil
from qgis.core import QgsApplication
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QMessageBox, QCheckBox, QFrame,
    QToolButton, QLineEdit, QTabWidget, QListWidget, QListWidgetItem, QAbstractItemView,
    QSpinBox
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt import QtWidgets

# Importer la classe du fichier UI compilé
from .voirie_communale_dialog_base import Ui_VoirieCommunaleDialogBase


class VoirieCommunaleDialog(QtWidgets.QDialog, Ui_VoirieCommunaleDialogBase):
    def __init__(self, parent=None):
        """Constructor."""
        super(VoirieCommunaleDialog, self).__init__(parent)
        self.setupUi(self)
        # Liste de toutes les cases à cocher de sélection de couches
        self._layer_checkboxes = [
            'chkCommune', 'chkBDTopoRoutesNom', 'chkBDTopoTroncons', 'chkOsmRoutes', 'chkMagOsm',
            'chkVoirie', 'chkVoirieDep', 'chkBAN', 'chkFilairesBAL', 'chkEdigeoVoies', 'chkMajic', 'chkGeofoncier',
            'chkCadastre', 'chkPlanIGN', 'chkBDOrtho', 'chkMNTLidar',
            'chkOsmFR', 'chkWazeTiles', 'chkCoSIA', 'chkPhotoAeriennes',
            'chkScan50_1950', 'chkScanCassini', 'chkScanEtatMajor'
        ]
        # Utiliser 'clicked' (pas 'stateChanged') pour les clics utilisateur sur la case maître
        # afin d'éviter le cycle tristate 0→1→2 qui passe par l'état partiel au premier clic
        self.chkToutSelectionner.clicked.connect(self._on_tout_clicked)
        # Mettre à jour l'état de chkToutSelectionner quand une case individuelle change
        for name in self._layer_checkboxes:
            getattr(self, name).stateChanged.connect(self._update_tout_selectionner)

    def _on_tout_clicked(self, checked):
        """Coche ou décoche toutes les cases."""
        for name in self._layer_checkboxes:
            getattr(self, name).setChecked(checked)

    def _update_tout_selectionner(self):
        """Met à jour la case maître : cochée si toutes les cases le sont."""
        self.chkToutSelectionner.blockSignals(True)
        all_checked = all(getattr(self, name).isChecked() for name in self._layer_checkboxes)
        self.chkToutSelectionner.setChecked(all_checked)
        self.chkToutSelectionner.blockSignals(False)


class PhotoAeriennesDialog(QDialog):
    """Dialogue de sélection des photographies aériennes historiques IGN."""

    # (typename WMS, libellé affiché)
    SOURCES = [
        ('ORTHOIMAGERY.ORTHOPHOTOS.1950-1965', 'Photos aériennes 1950-1965 (IGN Géoplateforme)'),
        ('ORTHOIMAGERY.ORTHOPHOTOS.1965-1980', 'Photos aériennes 1965-1980 (IGN Géoplateforme)'),
        ('ORTHOIMAGERY.ORTHOPHOTOS.1980-1995', 'Photos aériennes 1980-1995 (IGN Géoplateforme)'),
        ('ORTHOIMAGERY.ORTHOPHOTOS2000-2005',  'Photos aériennes 2000-2005 (IGN Géoplateforme)'),
        ('ORTHOIMAGERY.ORTHOPHOTOS2006-2010',  'Photos aériennes 2006-2010 (IGN Géoplateforme)'),
        ('ORTHOIMAGERY.ORTHOPHOTOS2011-2015',  'Photos aériennes 2011-2015 (IGN Géoplateforme)'),
        ('ORTHOIMAGERY.ORTHOPHOTOS2016-2020',  'Photos aériennes 2016-2020 (IGN Géoplateforme)'),
        ('ORTHOIMAGERY.ORTHOPHOTOS2021-2023',  'Photos aériennes 2021-2023 (IGN Géoplateforme)'),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Photographies aériennes historiques")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)

        desc = QLabel(
            "Sélectionnez les périodes à charger depuis la Géoplateforme IGN :"
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        self._checkboxes = []
        for typename, label in self.SOURCES:
            chk = QCheckBox(label)
            chk.setChecked(True)
            chk.setProperty('typename', typename)
            layout.addWidget(chk)
            self._checkboxes.append(chk)

        layout.addSpacing(8)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_ok = QPushButton("Charger")
        self.btn_ok.setDefault(True)
        self.btn_cancel = QPushButton("Annuler")
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

    def selected_sources(self):
        """Retourne la liste des (typename, libellé) cochés."""
        return [
            (chk.property('typename'), chk.text().split(' (')[0])
            for chk in self._checkboxes
            if chk.isChecked()
        ]


class SettingsDialog(QDialog):
    """Dialogue de paramètres du plugin."""

    _NS = "voirie_communale"
    _LAYER_ORDER_JSON = os.path.join(os.path.dirname(__file__), 'layer_order.json')

    # Valeurs par défaut de tous les paramètres.
    # Ce dictionnaire est la source de vérité : toute nouvelle clé doit y figurer.
    _DEFAULTS = {
        "auto_zoom":         True,
        "auto_reorder":      True,
        "clip_to_commune":   False,
        "clip_buffer_m":     25,
        "ban_regex_chemin":  r'(?i)(che(?:min)?|sen(?:tier)?) rural|\bC\.?R\.?\b',
        "ban_regex_voie":    r'(?i)(voi(?:e)?|che(?:min)?) (com(?:munal)?)|\bV\.?C\.?\b',
        "last_insee":        "",
        "checked_layers":    [],
        "cache_warning_days": 30,
    }

    # Anciennes valeurs par défaut de 'ban_regex_voie', migrées automatiquement vers
    # la valeur courante de _DEFAULTS lors du chargement (voir _load) si l'utilisateur
    # n'a pas personnalisé son réglage. Permet d'élargir les regex sans casser les
    # personnalisations existantes ni exiger de réinitialisation manuelle.
    _LEGACY_BAN_REGEX_VOIE = {
        r'(?i)(voi(?:e)?) (com(?:munale)?)|\bV\.?C\.?\b',
        r'(?i)\b(?:voi(?:es?)?|che(?:mins?)?)\.?\s+com(?:m(?:un(?:al(?:e|es)?|aux))?)?\.?\b|\bV\.?C\.?\b',
    }

    @staticmethod
    def _user_dir():
        """Dossier des fichiers utilisateur dans le profil QGIS actif (créé si besoin).

        Hors du dossier du plugin : celui-ci est entièrement remplacé à chaque
        mise à jour par le gestionnaire d'extensions, ce qui effaçait les réglages.
        """
        path = os.path.join(QgsApplication.qgisSettingsDirPath(), "voirie_communale")
        os.makedirs(path, exist_ok=True)
        return path

    @staticmethod
    def _settings_path():
        """Chemin du fichier settings.json dans le profil QGIS."""
        return os.path.join(SettingsDialog._user_dir(), "settings.json")

    @staticmethod
    def _load():
        """Charge settings.json, complète les clés manquantes avec les défauts,
        migre les anciennes valeurs par défaut connues vers la valeur courante,
        et sauvegarde si des clés ont été ajoutées ou migrées."""
        path = SettingsDialog._settings_path()
        # Migration : settings.json était auparavant stocké dans le dossier du plugin
        legacy_path = os.path.join(os.path.dirname(__file__), "settings.json")
        if not os.path.isfile(path) and os.path.isfile(legacy_path):
            try:
                shutil.copyfile(legacy_path, path)
            except OSError:
                pass
        data = {}
        if os.path.isfile(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                data = {}
        changed = False
        # Injecter les défauts pour les clés absentes
        missing = {k: v for k, v in SettingsDialog._DEFAULTS.items() if k not in data}
        if missing:
            data.update(missing)
            changed = True
        # Migrer 'ban_regex_voie' si l'utilisateur a toujours une ancienne valeur
        # par défaut (jamais personnalisée) vers la valeur par défaut courante.
        if data.get('ban_regex_voie') in SettingsDialog._LEGACY_BAN_REGEX_VOIE:
            data['ban_regex_voie'] = SettingsDialog._DEFAULTS['ban_regex_voie']
            changed = True
        if changed:
            SettingsDialog._save(data)
        return data

    @staticmethod
    def _save(data):
        """Écrit le dictionnaire dans settings.json (UTF-8, indenté)."""
        path = SettingsDialog._settings_path()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def get(key, default, value_type=None):
        """Lit un paramètre depuis settings.json.

        Le type JSON est préservé nativement (bool, int, str, list).
        value_type permet une coercition explicite si nécessaire.
        """
        val = SettingsDialog._load().get(key, default)
        if value_type is not None and not isinstance(val, value_type):
            try:
                val = value_type(val)
            except (ValueError, TypeError):
                val = default
        return val

    @staticmethod
    def set(key, value):
        """Enregistre un paramètre dans settings.json."""
        data = SettingsDialog._load()
        data[key] = value
        SettingsDialog._save(data)

    # ------------------------------------------------------------------
    # Lecture / écriture de layer_order.json
    # ------------------------------------------------------------------
    @classmethod
    def _user_layer_order_path(cls):
        """Ordre personnalisé, dans le profil QGIS (le layer_order.json du plugin
        reste l'ordre par défaut, réécrit à chaque mise à jour)."""
        return os.path.join(cls._user_dir(), "layer_order.json")

    @classmethod
    def _read_layer_order(cls):
        """Retourne (commune_group, root) : l'ordre personnalisé s'il existe,
        complété des entrées par défaut absentes (couches ajoutées depuis),
        sinon l'ordre par défaut du plugin. ([], []) si rien n'est lisible."""
        def _read(path):
            try:
                with open(path, encoding='utf-8') as f:
                    data = json.load(f)
                return data.get('commune_group', []), data.get('root', [])
            except (OSError, json.JSONDecodeError):
                return [], []

        default_cg, default_root = _read(cls._LAYER_ORDER_JSON)
        user_cg, user_root = _read(cls._user_layer_order_path())
        if not user_cg or not user_root:
            return default_cg, default_root
        return (user_cg + [n for n in default_cg if n not in user_cg],
                user_root + [n for n in default_root if n not in user_root])

    @classmethod
    def _write_layer_order(cls, commune_group, root):
        """Sauvegarde l'ordre personnalisé dans le profil QGIS."""
        data = {'commune_group': commune_group, 'root': root}
        with open(cls._user_layer_order_path(), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Paramètres - Voirie Communale")
        self.setMinimumWidth(480)
        self.setMinimumHeight(500)

        outer = QVBoxLayout(self)
        outer.setSpacing(8)

        tabs = QTabWidget()
        outer.addWidget(tabs)

        # ============================================================
        # Onglet 1 : Général
        # ============================================================
        tab_general = QDialog()
        tab_general.setFlat = lambda *a: None  # QDialog n'a pas setFlat, compat shim
        lay_general = QVBoxLayout(tab_general)
        lay_general.setSpacing(8)

        # --- Comportement ---
        lay_general.addWidget(QLabel("<b>Comportement après chargement</b>"))

        self.chk_auto_zoom = QCheckBox("Zoom automatique sur la commune")
        self.chk_auto_zoom.setChecked(self.get('auto_zoom', True, bool))
        lay_general.addWidget(self.chk_auto_zoom)

        self.chk_auto_reorder = QCheckBox("Réordonnancement automatique des couches")
        self.chk_auto_reorder.setChecked(self.get('auto_reorder', True, bool))
        lay_general.addWidget(self.chk_auto_reorder)

        self.chk_clip_commune = QCheckBox("Découper les couches sur l'emprise communale")
        self.chk_clip_commune.setChecked(self.get('clip_to_commune', False, bool))
        lay_general.addWidget(self.chk_clip_commune)

        row_buf = QHBoxLayout()
        row_buf.addSpacing(20)
        row_buf.addWidget(QLabel("Buffer :"))
        self.spn_clip_buffer = QSpinBox()
        self.spn_clip_buffer.setRange(0, 10000)
        self.spn_clip_buffer.setValue(self.get('clip_buffer_m', 25, int))
        self.spn_clip_buffer.setSuffix(" m")
        self.spn_clip_buffer.setMaximumWidth(100)
        row_buf.addWidget(self.spn_clip_buffer)
        row_buf.addStretch()
        lay_general.addLayout(row_buf)
        self.chk_clip_commune.toggled.connect(self.spn_clip_buffer.setEnabled)
        self.spn_clip_buffer.setEnabled(self.chk_clip_commune.isChecked())

        lay_general.addSpacing(4)
        sep = QFrame(); sep.setFrameShape(QFrame.HLine); sep.setFrameShadow(QFrame.Sunken)
        lay_general.addWidget(sep)
        lay_general.addSpacing(4)

        # --- Mémorisation automatique ---
        lay_general.addWidget(QLabel("<b>Mémorisation automatique</b>"))

        last_insee = self.get('last_insee', '') or ''
        row = QHBoxLayout()
        row.addWidget(QLabel("Dernier code INSEE chargé :"))
        self.lbl_insee = QLabel(f"<b>{last_insee}</b>" if last_insee else "<i>(aucun)</i>")
        row.addWidget(self.lbl_insee)
        row.addStretch()
        lay_general.addLayout(row)

        note = QLabel(
            "<small><i>Le code INSEE et la sélection des couches sont mémorisés "
            "automatiquement à chaque chargement.</i></small>"
        )
        note.setWordWrap(True)
        lay_general.addWidget(note)

        lay_general.addSpacing(4)
        sep_cache = QFrame(); sep_cache.setFrameShape(QFrame.HLine); sep_cache.setFrameShadow(QFrame.Sunken)
        lay_general.addWidget(sep_cache)
        lay_general.addSpacing(4)

        # --- Cache local des couches vecteur ---
        lay_general.addWidget(QLabel("<b>Cache local des couches par commune</b>"))

        row_cache = QHBoxLayout()
        row_cache.addWidget(QLabel("Alerte si le cache dépasse :"))
        self.spn_cache_warning_days = QSpinBox()
        self.spn_cache_warning_days.setRange(1, 3650)
        self.spn_cache_warning_days.setValue(self.get('cache_warning_days', 30, int))
        self.spn_cache_warning_days.setSuffix(" jour(s)")
        self.spn_cache_warning_days.setMaximumWidth(120)
        row_cache.addWidget(self.spn_cache_warning_days)
        row_cache.addStretch()
        lay_general.addLayout(row_cache)

        note_cache = QLabel(
            "<small><i>Les données par commune (BAN, MAJIC, Filaires BAL, Voirie DGCL, "
            "OSM Routes, MagOSM, BD TOPO...) sont mises en cache localement (GeoPackage) "
            "pour éviter de retélécharger à chaque ouverture. Le cache d'une commune est "
            "automatiquement retéléchargé après une mise à jour du plugin (pour ne jamais "
            "réutiliser des données figées par un bug corrigé depuis). Utilisez le bouton "
            "« Forcer le rechargement » pour ignorer le cache et retélécharger à tout "
            "moment.</i></small>"
        )
        note_cache.setWordWrap(True)
        lay_general.addWidget(note_cache)

        lay_general.addSpacing(4)
        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine); sep2.setFrameShadow(QFrame.Sunken)
        lay_general.addWidget(sep2)
        lay_general.addSpacing(4)

        # --- Catégorisation Chemin rural / Voie communale ---
        lay_general.addWidget(QLabel("<b>Catégorisation Chemin rural / Voie communale</b>"))

        _BAN_REGEX_CHEMIN_DEFAULT = SettingsDialog._DEFAULTS['ban_regex_chemin']
        _BAN_REGEX_VOIE_DEFAULT   = SettingsDialog._DEFAULTS['ban_regex_voie']

        # Charger les valeurs stockées ; si corrompues (regex invalide), restaurer le défaut
        # et corriger settings.json pour éviter l'erreur lors du prochain chargement BAN.
        _stored_cr = self.get('ban_regex_chemin', _BAN_REGEX_CHEMIN_DEFAULT) or _BAN_REGEX_CHEMIN_DEFAULT
        try:
            re.compile(_stored_cr)
        except re.error:
            _stored_cr = _BAN_REGEX_CHEMIN_DEFAULT
            self.set('ban_regex_chemin', _stored_cr)

        _stored_vc = self.get('ban_regex_voie', _BAN_REGEX_VOIE_DEFAULT) or _BAN_REGEX_VOIE_DEFAULT
        try:
            re.compile(_stored_vc)
        except re.error:
            _stored_vc = _BAN_REGEX_VOIE_DEFAULT
            self.set('ban_regex_voie', _stored_vc)

        row_cr = QHBoxLayout()
        row_cr.addWidget(QLabel("Regex Chemin rural :"))
        self.txt_regex_chemin = QLineEdit(_stored_cr)
        self.txt_regex_chemin.setPlaceholderText(_BAN_REGEX_CHEMIN_DEFAULT)
        self.txt_regex_chemin.setMinimumWidth(260)
        row_cr.addWidget(self.txt_regex_chemin)
        lay_general.addLayout(row_cr)

        row_vc = QHBoxLayout()
        row_vc.addWidget(QLabel("Regex Voie communale :"))
        self.txt_regex_voie = QLineEdit(_stored_vc)
        self.txt_regex_voie.setPlaceholderText(_BAN_REGEX_VOIE_DEFAULT)
        self.txt_regex_voie.setMinimumWidth(260)
        row_vc.addWidget(self.txt_regex_voie)
        lay_general.addLayout(row_vc)

        note_ban = QLabel(
            "<small><i>Expressions régulières utilisées pour identifier les chemins ruraux "
            "et voies communales (y compris variantes « Chemin Communal ») dans les couches "
            "BAN, BD TOPO tronçons, MagOSM et Voies EDIGEO (cadastre).</i></small>"
        )
        note_ban.setWordWrap(True)
        lay_general.addWidget(note_ban)
        lay_general.addStretch()

        tabs.addTab(tab_general, "Général")

        # ============================================================
        # Onglet 2 : Ordre des couches
        # ============================================================
        tab_order = QDialog()
        lay_order = QVBoxLayout(tab_order)
        lay_order.setSpacing(6)

        commune_group, root = self._read_layer_order()

        # ---- Liste groupe commune ----
        lay_order.addWidget(QLabel(
            "<b>Couches dans le groupe commune</b> "
            "<small>(glisser-déposer pour réordonner)</small>"
        ))
        note_cg = QLabel(
            "<small><i>Utiliser <tt>{code_insee}</tt> comme marqueur. "
            "La couche en tête de liste sera affichée en haut dans QGIS.</i></small>"
        )
        note_cg.setWordWrap(True)
        lay_order.addWidget(note_cg)

        self.lst_commune = QListWidget()
        self.lst_commune.setDragDropMode(QAbstractItemView.InternalMove)
        self.lst_commune.setDefaultDropAction(Qt.MoveAction)
        self.lst_commune.setSelectionMode(QAbstractItemView.SingleSelection)
        self.lst_commune.setAlternatingRowColors(True)
        self.lst_commune.setMinimumHeight(160)
        for entry in commune_group:
            self.lst_commune.addItem(QListWidgetItem(entry))
        lay_order.addWidget(self.lst_commune)

        lay_order.addSpacing(8)

        # ---- Liste racine ----
        lay_order.addWidget(QLabel(
            "<b>Fonds de plan (racine de l’arbre)</b> "
            "<small>(glisser-déposer pour réordonner)</small>"
        ))
        note_root = QLabel(
            "<small><i><tt>__COMMUNE_GROUP__</tt> représente la position du groupe commune. "
            "Les noms inconnus sont ignorés.</i></small>"
        )
        note_root.setWordWrap(True)
        lay_order.addWidget(note_root)

        self.lst_root = QListWidget()
        self.lst_root.setDragDropMode(QAbstractItemView.InternalMove)
        self.lst_root.setDefaultDropAction(Qt.MoveAction)
        self.lst_root.setSelectionMode(QAbstractItemView.SingleSelection)
        self.lst_root.setAlternatingRowColors(True)
        self.lst_root.setMinimumHeight(180)
        for entry in root:
            self.lst_root.addItem(QListWidgetItem(entry))
        lay_order.addWidget(self.lst_root)

        tabs.addTab(tab_order, "Ordre des couches")

        # ============================================================
        # Boutons
        # ============================================================
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_ok = QPushButton("OK")
        self.btn_ok.setDefault(True)
        self.btn_cancel = QPushButton("Annuler")
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        outer.addLayout(btn_layout)

        self.btn_ok.clicked.connect(self._save_and_accept)
        self.btn_cancel.clicked.connect(self.reject)

    def _save_and_accept(self):
        # Valider les regex avant toute sauvegarde
        for label, txt_widget in [
            ("Regex chemins", self.txt_regex_chemin),
            ("Regex voies", self.txt_regex_voie),
        ]:
            pattern = txt_widget.text().strip()
            if pattern:
                try:
                    re.compile(pattern)
                except re.error as exc:
                    QMessageBox.warning(
                        self,
                        "Expression régulière invalide",
                        f"{label} : expression régulière invalide.\n\nÉchec : {exc}\n\nCorrigez-la avant d'enregistrer."
                    )
                    txt_widget.setFocus()
                    txt_widget.selectAll()
                    return

        self.set('auto_zoom', self.chk_auto_zoom.isChecked())
        self.set('auto_reorder', self.chk_auto_reorder.isChecked())
        self.set('clip_to_commune', self.chk_clip_commune.isChecked())
        self.set('clip_buffer_m', self.spn_clip_buffer.value())
        self.set('ban_regex_chemin', self.txt_regex_chemin.text().strip())
        self.set('ban_regex_voie', self.txt_regex_voie.text().strip())
        self.set('cache_warning_days', self.spn_cache_warning_days.value())

        # Sauvegarder l'ordre des couches dans layer_order.json
        commune_group = [
            self.lst_commune.item(i).text()
            for i in range(self.lst_commune.count())
        ]
        root = [
            self.lst_root.item(i).text()
            for i in range(self.lst_root.count())
        ]
        try:
            self._write_layer_order(commune_group, root)
        except (OSError, TypeError, ValueError) as exc:
            QMessageBox.warning(
                self,
                "Erreur d’enregistrement",
                f"Impossible de sauvegarder layer_order.json :\n{exc}"
            )
            return
        self.accept()


class LauncherDialog(QDialog):
    """Barre de lancement du plugin : accès rapide aux fonctionnalités principales."""

    _BTN_STYLE = """
        QToolButton {
            font-size: 12px;
            padding: 10px 6px 8px 6px;
            border: 1px solid #c8c8c8;
            border-radius: 6px;
            background: #f7f7f7;
            min-width: 105px;
            min-height: 72px;
        }
        QToolButton:hover:enabled {
            background: #ddeeff;
            border-color: #4a90d9;
        }
        QToolButton:pressed:enabled {
            background: #b8d4f0;
        }
        QToolButton:disabled {
            color: #aaaaaa;
            background: #f0f0f0;
            border-color: #ddd;
        }
    """

    def __init__(self, parent=None, callbacks=None):
        super().__init__(parent)
        callbacks = callbacks or {}
        self.setWindowTitle("Voirie Communale")
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self.setSizeGripEnabled(False)

        layout = QHBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        buttons_def = [
            (
                "📂",
                "Charger\ndes données",
                "Ouvre le panneau de chargement des données",
                callbacks.get('charger'),
            ),
            (
                "✏️",
                "Numériser\ndes données",
                "Numérisation des voies (fonctionnalité à venir)",
                None,
            ),
            (
                "⚙️",
                "Paramètres",
                "Paramètres du plugin",
                callbacks.get('settings'),
            ),
            (
                "ℹ️",
                "À propos",
                "Informations sur le plugin Voirie Communale",
                callbacks.get('about'),
            ),
        ]

        for icon, label, tooltip, callback in buttons_def:
            btn = QToolButton()
            btn.setText(f"{icon}\n{label}")
            btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
            btn.setToolTip(tooltip)
            btn.setStyleSheet(self._BTN_STYLE)
            btn.setEnabled(callback is not None)
            if callback:
                btn.clicked.connect(callback)
            layout.addWidget(btn)

        self.adjustSize()
        self.setFixedHeight(self.sizeHint().height())
