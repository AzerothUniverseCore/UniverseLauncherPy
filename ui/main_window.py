"""
ui/main_window.py
------------------
Fenetre principale du launcher (PySide6), reproduisant la maquette validee
par le client : fenetre sans decoration systeme + barre de titre maison,
gros titre "AZEROTH UNIVERSE" avec badge de statut serveur, panneau
"Actualites" a gauche, panneau "Dossier client" + "Journal" a droite, barre
d'action en bas (Site web / S'inscrire / Verifier / gros bouton d'action
dore dont le libelle change selon l'etat : Verifier -> Installer -> Jouer).
"""

import os
import sys
import time
import subprocess

from PySide6.QtCore import Qt, QSize, QUrl, QTimer, Signal
from PySide6.QtGui import QPixmap, QIcon, QDesktopServices, QPainterPath, QRegion
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QLineEdit, QPushButton, QCheckBox,
    QProgressBar, QPlainTextEdit, QFileDialog, QMessageBox, QVBoxLayout,
    QHBoxLayout, QFrame, QScrollArea, QButtonGroup, QStackedLayout, QDialog,
)

import config
from ui import theme
from i18n import Translator
from core import downloader
from core.installer import (
    InstallWorker, is_fully_installed, is_entry_done,
    reset_forced_refresh_entries,
)
from core import wtf as wtf_module
from core.server_status import ServerStatusWorker
from core import updater as updater_module


def _format_duration(seconds):
    """Formate une duree en secondes en texte court ("42 s", "3 min 12 s",
    "1 h 05"). Utilise pour le temps restant estime pendant un
    telechargement."""
    if seconds is None or seconds < 0 or seconds != seconds:  # NaN check
        return None
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}min {sec:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}"


class TitleBar(QWidget):
    """Barre de titre maison (la fenetre n'a pas de decoration systeme) :
    porte le titre, les boutons FR/EN, et les boutons reduire/fermer. Le
    deplacement de la fenetre se fait en glissant cette barre."""

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        self._drag_pos = None
        self.setObjectName("TitleBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(40)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            handle = self._window.windowHandle()
            if handle is not None and hasattr(handle, "startSystemMove"):
                if handle.startSystemMove():
                    return
            self._drag_pos = event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self._window.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


class ClickableFrame(QFrame):
    """QFrame qui emet `clicked` sur un clic gauche - utilise pour le badge
    de statut serveur (voir _build_status_badge), qui n'est pas un
    QPushButton (son style visuel de "carte" ne colle pas a celui des
    boutons de l'appli) mais doit quand meme reagir au clic pour ouvrir la
    liste des personnages en ligne."""
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class OnlineCharactersDialog(QDialog):
    """Fenetre "Personnages en ligne", ouverte en cliquant sur le badge de
    statut serveur. Reprend le meme motif visuel que le panneau
    "Actualites" (une carte par entree dans une zone defilante) plutot que
    d'introduire un nouveau composant Qt (QListWidget, QTableView...) pour
    un besoin somme toute simple - liste courte de lignes texte."""

    def __init__(self, tr_, characters, status_configured, status_online, parent=None):
        super().__init__(parent)
        self.tr_ = tr_
        t = tr_.t
        self.setWindowTitle(t("online_characters_title"))
        self.setMinimumSize(360, 420)
        self.resize(360, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header = QLabel(t("online_characters_title"))
        header.setObjectName("CardHeader")
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        container = QWidget()
        rows_layout = QVBoxLayout(container)
        rows_layout.setSpacing(8)

        if not status_configured or not status_online:
            empty = QLabel(t("online_characters_unavailable"))
            empty.setObjectName("OnlineCharactersEmpty")
            empty.setWordWrap(True)
            rows_layout.addWidget(empty)
        elif not characters:
            empty = QLabel(t("online_characters_empty"))
            empty.setObjectName("OnlineCharactersEmpty")
            empty.setWordWrap(True)
            rows_layout.addWidget(empty)
        else:
            # Deja triee par niveau decroissant cote serveur (voir
            # status.php), mais on ne fait pas confiance a un endpoint
            # tiers pour garder ce comportement - un petit tri defensif ici
            # ne coute rien pour au plus quelques centaines d'entrees.
            for char in sorted(characters, key=lambda c: c["level"], reverse=True):
                rows_layout.addWidget(self._build_character_row(char))

        rows_layout.addStretch(1)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        btn_close = QPushButton(t("btn_close"))
        btn_close.setObjectName("OutlineButton")
        btn_close.clicked.connect(self.accept)
        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_row.addWidget(btn_close)
        layout.addLayout(close_row)

    def _build_character_row(self, char):
        row = QFrame()
        row.setObjectName("CharacterRow")
        row.setAttribute(Qt.WA_StyledBackground, True)
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(12, 8, 12, 8)
        row_layout.setSpacing(2)

        name = QLabel(char["name"])
        name.setObjectName("CharacterName")
        name.setStyleSheet(f"color: {self.tr_.class_color(char['class'])};")
        row_layout.addWidget(name)

        subtitle = QLabel(self.tr_.t(
            "character_row_subtitle", level=char["level"],
            race=self.tr_.race_name(char["race"]),
            class_name=self.tr_.class_name(char["class"])))
        subtitle.setObjectName("CharacterSubtitle")
        row_layout.addWidget(subtitle)

        return row


class AzerothLauncherWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.manifest = config.load_manifest()
        self.settings = config.load_settings()
        self.tr_ = Translator(self.settings.get("lang", "fr"))
        self.worker = None
        self.status_worker = None
        self.update_check_worker = None
        self.update_download_worker = None
        self._checked_once = False
        self._missing_count = None
        self._dl_tracker = {"name": None, "last_time": None, "last_bytes": 0, "speed_ema": None}
        # Nombre d'entrees (fichiers/archives) du manifeste totalement
        # terminees, et total d'entrees : utilises pour faire avancer la
        # barre de progression EN CONTINU pendant le telechargement de
        # l'entree en cours (voir _on_file_progress), plutot que seulement
        # par paliers a chaque fichier termine (voir _on_overall_progress).
        self._entries_done = 0
        self._entries_total = 0
        self._is_paused = False
        # Dernier resultat connu du badge de statut serveur (voir
        # _on_status_result) : reutilise tel quel par
        # _on_status_badge_clicked, plutot que de refaire une requete reseau
        # a chaque clic - le badge est deja rafraichi periodiquement par
        # _status_timer (config.STATUS_POLL_INTERVAL_MS).
        self._status_configured = False
        self._status_online = None
        self._last_characters = []

        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        # Necessaire pour que les coins arrondis (voir _apply_rounded_mask)
        # laissent vraiment voir le bureau derriere, plutot qu'un fond noir
        # rectangulaire visible sous les coins coupes.
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(QSize(1060, 700))
        if os.path.isfile(config.ICON_PATH):
            self.setWindowIcon(QIcon(config.ICON_PATH))

        self._build_ui()
        self._center_on_screen()
        self._load_settings_into_ui()
        self.retranslate_ui()
        self._refresh_cta()
        self._check_server_status()
        self._update_background_pixmap()
        self._apply_rounded_mask()

        # Rafraichit le badge de statut serveur periodiquement (config.py
        # -> STATUS_POLL_INTERVAL_MS). Sans ce timer, le statut n'etait
        # verifie qu'une seule fois au demarrage du launcher et ne se
        # mettait plus jamais a jour tant que l'appli restait ouverte.
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(config.STATUS_POLL_INTERVAL_MS)
        self._status_timer.timeout.connect(self._check_server_status)
        self._status_timer.start()

        # Verification de mise a jour du LAUNCHER (pas du client WoW, voir
        # core/installer.py pour ca) : une seule fois au demarrage, en
        # arriere-plan, sans bloquer l'affichage de la fenetre.
        self._check_for_launcher_update()

    # ------------------------------------------------------------------
    def _center_on_screen(self):
        screen = self.screen() if hasattr(self, "screen") else None
        geo = screen.availableGeometry() if screen else None
        if geo:
            self.move(
                geo.center().x() - self.width() // 2,
                geo.center().y() - self.height() // 2,
            )

    # ------------------------------------------------------------------
    # Construction de l'UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        central.setObjectName("RootBackground")
        central.setAttribute(Qt.WA_StyledBackground, True)
        self.setCentralWidget(central)

        stack = QStackedLayout(central)
        stack.setStackingMode(QStackedLayout.StackAll)
        stack.setContentsMargins(0, 0, 0, 0)

        self.bg_label = QLabel()
        self.bg_label.resize(self.size())
        self._bg_source_pixmap = (
            QPixmap(config.BACKGROUND_PATH) if os.path.isfile(config.BACKGROUND_PATH) else None
        )
        # Pas d'appel a _update_background_pixmap() ici : la taille reelle du
        # widget central n'est pas encore stabilisee avant le premier show().
        # Le decoupage "cover" correct est fait a la fin de __init__ et a
        # chaque resizeEvent.
        stack.addWidget(self.bg_label)

        # IMPORTANT : ne PAS faire foreground.setStyleSheet("background:
        # transparent;") ici. Un style local (widget.setStyleSheet(...))
        # sans selecteur explicite s'applique comme un "style inline" a tout
        # le sous-arbre QWidget et prend le pas sur la feuille de style de
        # l'application MEME pour des regles plus specifiques (#LangButton,
        # #Card, ...) - ca desactivait silencieusement le remplissage dore
        # des boutons FR/EN coches et le fond des cartes. La regle globale
        # `QWidget { background-color: transparent; }` de ui/theme.py suffit
        # deja pour ce widget, donc aucun style local n'est necessaire.
        foreground = QWidget()
        foreground.setAttribute(Qt.WA_TranslucentBackground)
        stack.addWidget(foreground)
        foreground.raise_()

        root = QVBoxLayout(foreground)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_titlebar())

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(26, 20, 26, 16)
        content_layout.setSpacing(14)

        content_layout.addLayout(self._build_hero())

        body_row = QHBoxLayout()
        body_row.setSpacing(16)
        body_row.addWidget(self._build_news_card(), 1)

        right_col = QVBoxLayout()
        right_col.setSpacing(16)
        right_col.addWidget(self._build_client_folder_card())
        right_col.addWidget(self._build_journal_card(), 1)
        body_row.addLayout(right_col, 1)

        content_layout.addLayout(body_row, 1)
        content_layout.addLayout(self._build_bottom_bar())

        root.addWidget(content, 1)

    def _build_titlebar(self):
        bar = TitleBar(self)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 10, 0)
        layout.setSpacing(10)

        self.lbl_titlebar = QLabel()
        self.lbl_titlebar.setObjectName("TitleBarLabel")
        self.lbl_titlebar_build = QLabel(f"build {config.CLIENT_BUILD}")
        self.lbl_titlebar_build.setObjectName("TitleBarBuild")
        layout.addWidget(self.lbl_titlebar)
        layout.addWidget(self.lbl_titlebar_build)
        layout.addStretch(1)

        self.btn_lang_fr = QPushButton("FR")
        self.btn_lang_en = QPushButton("EN")
        for btn in (self.btn_lang_fr, self.btn_lang_en):
            btn.setObjectName("LangButton")
            btn.setCheckable(True)
            btn.setFixedWidth(36)
        self.lang_group = QButtonGroup(self)
        self.lang_group.setExclusive(True)
        self.lang_group.addButton(self.btn_lang_fr)
        self.lang_group.addButton(self.btn_lang_en)
        self.btn_lang_fr.clicked.connect(lambda: self._on_language_changed("fr"))
        self.btn_lang_en.clicked.connect(lambda: self._on_language_changed("en"))
        layout.addWidget(self.btn_lang_fr)
        layout.addWidget(self.btn_lang_en)

        layout.addSpacing(10)

        btn_min = QPushButton("—")
        btn_min.setObjectName("WinButton")
        btn_min.clicked.connect(self.showMinimized)
        btn_close = QPushButton("×")
        btn_close.setObjectName("WinButton")
        btn_close.setProperty("danger", True)
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_min)
        layout.addWidget(btn_close)

        return bar

    def _build_hero(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)

        row = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.lbl_hero_title = QLabel()
        self.lbl_hero_title.setObjectName("HeroTitle")
        self.lbl_hero_tagline = QLabel()
        self.lbl_hero_tagline.setObjectName("HeroTagline")
        title_box.addWidget(self.lbl_hero_title)
        title_box.addWidget(self.lbl_hero_tagline)
        row.addLayout(title_box)
        row.addStretch(1)
        row.addWidget(self._build_status_badge())
        layout.addLayout(row)

        underline = QFrame()
        underline.setObjectName("GoldUnderline")
        underline.setFrameShape(QFrame.HLine)
        layout.addWidget(underline)

        return layout

    def _build_status_badge(self):
        # ClickableFrame (pas un simple QFrame) : le badge ouvre la liste
        # des personnages en ligne au clic (voir _on_status_badge_clicked).
        badge = ClickableFrame()
        badge.setObjectName("StatusBadge")
        badge.setAttribute(Qt.WA_StyledBackground, True)
        badge.setCursor(Qt.PointingHandCursor)
        badge.clicked.connect(self._on_status_badge_clicked)
        # Largeur minimale fixe plutot que purement basee sur le sizeHint du
        # texte courant : evite un badge qui reste trop etroit et coupe le
        # texte apres un changement de langue a chaud (le libelle le plus
        # long, "Status not configured"/"Statut non configure", doit tenir
        # sans qu'on ait besoin de forcer un recalcul de layout a la main).
        badge.setMinimumWidth(220)
        self.status_badge = badge
        layout = QHBoxLayout(badge)
        layout.setContentsMargins(12, 8, 14, 8)
        layout.setSpacing(8)

        self.status_dot = QLabel()
        self.status_dot.setObjectName("StatusDot")
        self.status_dot.setProperty("state", "unknown")
        layout.addWidget(self.status_dot)

        text_box = QVBoxLayout()
        text_box.setSpacing(0)
        self.lbl_status_badge_title = QLabel()
        self.lbl_status_badge_title.setObjectName("StatusBadgeTitle")
        self.lbl_status_badge_sub = QLabel()
        self.lbl_status_badge_sub.setObjectName("StatusBadgeSub")
        text_box.addWidget(self.lbl_status_badge_title)
        text_box.addWidget(self.lbl_status_badge_sub)
        layout.addLayout(text_box)

        return badge

    def _make_card(self, header_text_attr):
        card = QFrame()
        card.setObjectName("Card")
        card.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 16)
        layout.setSpacing(10)
        header = QLabel()
        header.setObjectName("CardHeader")
        setattr(self, header_text_attr, header)
        layout.addWidget(header)
        return card, layout

    def _build_news_card(self):
        card, layout = self._make_card("lbl_news_header")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        news_container = QWidget()
        self.news_layout = QVBoxLayout(news_container)
        self.news_layout.setSpacing(10)
        self.news_layout.addStretch(1)
        scroll.setWidget(news_container)
        layout.addWidget(scroll, 1)

        return card

    def _build_news_item(self, item):
        card = QFrame()
        card.setObjectName("NewsCard")
        card.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        top_row = QHBoxLayout()
        tag = QLabel(item["tag"])
        tag.setObjectName("NewsTag")
        date = QLabel(item["date"])
        date.setObjectName("NewsDate")
        top_row.addWidget(tag)
        top_row.addStretch(1)
        top_row.addWidget(date)
        layout.addLayout(top_row)

        title = QLabel(item["title"])
        title.setObjectName("NewsTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

        body = QLabel(item["body"])
        body.setObjectName("NewsBody")
        body.setWordWrap(True)
        layout.addWidget(body)

        return card

    def _refresh_news(self):
        while self.news_layout.count():
            item = self.news_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for entry in self.tr_.news():
            self.news_layout.addWidget(self._build_news_item(entry))
        self.news_layout.addStretch(1)

    def _build_client_folder_card(self):
        card, layout = self._make_card("lbl_client_folder_header")

        dir_row = QHBoxLayout()
        self.edit_install_dir = QLineEdit()
        self.btn_browse = QPushButton("…")
        self.btn_browse.setFixedWidth(36)
        self.btn_browse.clicked.connect(self._on_browse)
        dir_row.addWidget(self.edit_install_dir, 1)
        dir_row.addWidget(self.btn_browse)
        layout.addLayout(dir_row)

        self.chk_deep_verify = QCheckBox()
        layout.addWidget(self.chk_deep_verify)

        return card

    def _build_journal_card(self):
        card, layout = self._make_card("lbl_journal_header")
        self.log_console = QPlainTextEdit()
        self.log_console.setObjectName("LogConsole")
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumBlockCount(500)
        layout.addWidget(self.log_console, 1)
        return card

    def _build_bottom_bar(self):
        outer = QVBoxLayout()
        outer.setSpacing(8)

        self.lbl_status = QLabel()
        self.lbl_status.setObjectName("StatusLabel")
        outer.addWidget(self.lbl_status)

        # Barre "fichier en cours" : c'est CETTE barre qui correspond au
        # pourcentage affiche juste au-dessus dans lbl_status (ex: "97%")
        # pendant un telechargement - avant, il n'existait qu'une seule
        # barre representant la progression GLOBALE (toutes les entrees du
        # manifeste confondues), qui semblait donc "figee" ou "en retard"
        # par rapport au texte alors qu'elle etait juste correcte pour ce
        # qu'elle mesurait (voir _on_file_progress/_on_overall_progress).
        self.progress_current = QProgressBar()
        self.progress_current.setRange(0, 1000)
        self.progress_current.setValue(0)
        self.progress_current.setTextVisible(False)
        outer.addWidget(self.progress_current)

        overall_row = QHBoxLayout()
        overall_row.setSpacing(8)
        self.lbl_overall_counter = QLabel()
        self.lbl_overall_counter.setObjectName("OverallCounterLabel")
        overall_row.addWidget(self.lbl_overall_counter)
        # Barre "progression globale" (nombre d'entrees du manifeste
        # terminees sur le total) : volontairement plus fine/attenuee (voir
        # ui/theme.py, #ProgressOverall) que la barre du fichier en cours
        # ci-dessus, pour qu'on ne les confonde plus visuellement.
        self.progress_overall = QProgressBar()
        self.progress_overall.setObjectName("ProgressOverall")
        self.progress_overall.setRange(0, 1)
        self.progress_overall.setValue(0)
        self.progress_overall.setTextVisible(False)
        overall_row.addWidget(self.progress_overall, 1)
        outer.addLayout(overall_row)

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch(1)

        self.btn_website = QPushButton()
        self.btn_website.setObjectName("OutlineButton")
        self.btn_website.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(config.WEBSITE_URL)))
        self.btn_register = QPushButton()
        self.btn_register.setObjectName("OutlineButton")
        self.btn_register.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(config.REGISTER_URL)))
        self.btn_check = QPushButton()
        self.btn_check.setObjectName("OutlineButton")
        self.btn_check.clicked.connect(self._on_check_clicked)

        self.btn_pause = QPushButton()
        self.btn_pause.setObjectName("OutlineButton")
        self.btn_pause.clicked.connect(self._on_pause_clicked)
        self.btn_pause.setVisible(False)

        self.btn_cta = QPushButton()
        self.btn_cta.setObjectName("PrimaryButton")
        self.btn_cta.clicked.connect(self._on_cta_clicked)

        for b in (self.btn_website, self.btn_register, self.btn_check, self.btn_pause, self.btn_cta):
            row.addWidget(b)

        outer.addLayout(row)
        return outer

    # ------------------------------------------------------------------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.bg_label.resize(self.centralWidget().size())
        self._update_background_pixmap()
        self._apply_rounded_mask()

    def _apply_rounded_mask(self):
        """Decoupe la fenetre (sans decoration systeme) en rectangle a coins
        arrondis : la zone hors du trace redevient transparente/cliquable a
        travers (on voit le bureau), au lieu d'un bloc noir rectangulaire
        sous des coins visuellement coupes."""
        path = QPainterPath()
        path.addRoundedRect(
            0, 0, self.width(), self.height(),
            theme.WINDOW_RADIUS, theme.WINDOW_RADIUS)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def _update_background_pixmap(self):
        """Redimensionne le fond d'ecran en mode "cover" (remplit tout
        l'espace SANS deformer l'image, quitte a en couper legerement les
        bords) plutot qu'un simple etirement qui deformerait une image
        rectangulaire fournie par l'utilisateur (personnage, logo...)."""
        if self._bg_source_pixmap is None or self._bg_source_pixmap.isNull():
            return
        target = self.centralWidget().size()
        scaled = self._bg_source_pixmap.scaled(
            target, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        x = max(0, (scaled.width() - target.width()) // 2)
        y = max(0, (scaled.height() - target.height()) // 2)
        cropped = scaled.copy(x, y, target.width(), target.height())
        self.bg_label.setPixmap(cropped)

    # ------------------------------------------------------------------
    # Settings <-> UI
    # ------------------------------------------------------------------
    def _load_settings_into_ui(self):
        if self.tr_.lang == "en":
            self.btn_lang_en.setChecked(True)
        else:
            self.btn_lang_fr.setChecked(True)
        # setChecked() avant le premier affichage ne redeclenche pas
        # toujours le style Qt (pseudo-etat :checked) tout seul : on force
        # un repolish explicite pour que le remplissage dore soit visible
        # des le demarrage, pas seulement apres un clic utilisateur.
        self._repolish(self.btn_lang_fr)
        self._repolish(self.btn_lang_en)

        self.edit_install_dir.setText(
            self.settings.get("install_dir", config.default_install_dir()))
        self.chk_deep_verify.setChecked(bool(self.settings.get("deep_verify", True)))

    def _save_settings(self):
        config.save_settings({
            "lang": self.tr_.lang,
            "install_dir": self.edit_install_dir.text().strip(),
            "realmlist": config.DEFAULT_REALMLIST,
            "deep_verify": self.chk_deep_verify.isChecked(),
        })

    # ------------------------------------------------------------------
    # Traduction
    # ------------------------------------------------------------------
    def retranslate_ui(self):
        t = self.tr_.t
        self.setWindowTitle(t("app_title"))
        self.lbl_titlebar.setText(t("titlebar_title"))
        self.lbl_hero_title.setText(t("hero_title"))
        self.lbl_hero_tagline.setText(t("tagline"))
        self.lbl_news_header.setText(t("news_header").upper())
        self.lbl_client_folder_header.setText(t("client_folder_header").upper())
        self.lbl_journal_header.setText(t("journal_header").upper())
        self.chk_deep_verify.setText(t("deep_verify_checkbox"))
        self.chk_deep_verify.setToolTip(t("deep_verify_tooltip"))
        self.btn_website.setText(t("btn_website"))
        self.btn_register.setText(t("btn_register"))
        self.btn_check.setText(t("btn_check"))
        self.status_badge.setToolTip(t("status_badge_tooltip"))
        self._refresh_pause_button()
        self._refresh_news()
        self._refresh_status_badge_text()
        self.lbl_overall_counter.setText(
            t("files_progress", done=self._entries_done, total=self._entries_total))

        if self.worker is None:
            self.lbl_status.setText(t("select_folder_prompt"))
        self._refresh_cta()

    def _refresh_pause_button(self):
        self.btn_pause.setText(self.tr_.t("btn_resume" if self._is_paused else "btn_pause"))

    def _on_language_changed(self, code):
        self.tr_.set_lang(code)
        self.retranslate_ui()
        self._save_settings()

        # Comportement demande : le bouton FR/EN change aussi la langue REELLE
        # du client (WTF/realm.wtf), pas seulement celle de l'interface du
        # launcher.
        wtf_locale = config.WTF_LOCALE_MAP.get(code, "enUS")
        install_dir = self.edit_install_dir.text().strip()
        if wtf_module.update_wtf_locale(install_dir, wtf_locale):
            self._on_log(f"[OK] " + self.tr_.t("wtf_locale_updated", locale=wtf_locale))

    # ------------------------------------------------------------------
    # Statut serveur
    # ------------------------------------------------------------------
    def _refresh_status_badge_text(self):
        t = self.tr_.t
        state = self.status_dot.property("state") or "unknown"
        if state == "online":
            self.lbl_status_badge_title.setText(t("status_online"))
            players = getattr(self, "_last_players", None)
            self.lbl_status_badge_sub.setText(
                t("players_connected", n=players) if players is not None else "")
        elif state == "offline":
            self.lbl_status_badge_title.setText(t("status_offline"))
            self.lbl_status_badge_sub.setText("")
        else:
            self.lbl_status_badge_title.setText(t("status_not_configured"))
            self.lbl_status_badge_sub.setText("")

    def _check_server_status(self):
        if self.status_worker is not None and self.status_worker.isRunning():
            return
        self.status_worker = ServerStatusWorker(config.STATUS_URL)
        self.status_worker.sig_result.connect(self._on_status_result)
        self.status_worker.start()

    def _on_status_result(self, configured, online, players, characters):
        if not configured:
            self.status_dot.setProperty("state", "unknown")
        else:
            self.status_dot.setProperty("state", "online" if online else "offline")
        self._last_players = players
        self._status_configured = configured
        self._status_online = online
        self._last_characters = characters
        self._repolish(self.status_dot)
        self._refresh_status_badge_text()

    def _on_status_badge_clicked(self):
        dialog = OnlineCharactersDialog(
            self.tr_, self._last_characters, self._status_configured,
            self._status_online, parent=self)
        dialog.exec()

    # ------------------------------------------------------------------
    # Mise a jour du launcher (voir core/updater.py - ne concerne PAS le
    # client WoW, qui reste gere par core/installer.py)
    # ------------------------------------------------------------------
    def _check_for_launcher_update(self):
        if self.update_check_worker is not None and self.update_check_worker.isRunning():
            return
        self.update_check_worker = updater_module.UpdateCheckWorker(
            config.LAUNCHER_UPDATE_REPO, config.LAUNCHER_VERSION)
        self.update_check_worker.sig_result.connect(self._on_update_check_result)
        self.update_check_worker.start()

    def _on_update_check_result(self, available, tag, asset_url, error):
        if error:
            # Simple echec reseau/API (pas de connexion, GitHub injoignable,
            # limite de requetes atteinte...) : pas la peine d'interrompre
            # l'utilisateur avec une boite de dialogue pour ca, un mot dans
            # le journal suffit. La verification suivante (prochain
            # lancement) reessaiera normalement.
            self._on_log("[INFO] " + self.tr_.t("update_check_failed"))
            return
        if not available:
            return

        is_frozen = bool(getattr(sys, "frozen", False))
        if not is_frozen:
            # Lance depuis les sources (python main.py) : pas d'executable
            # PyInstaller a remplacer, donc pas de mise a jour automatique
            # possible ici (voir la note en tete de core/updater.py). On se
            # contente de signaler la nouvelle version dans le journal.
            self._on_log("[INFO] " + self.tr_.t("update_dev_mode_skip", tag=tag))
            return

        if not asset_url:
            # Release plus recente detectee, mais sans piece jointe .rar
            # (release mal preparee cote GitHub, ou en cours de publication) :
            # rien a telecharger automatiquement, on le signale simplement.
            self._on_log(
                "[INFO] " + self.tr_.t("update_error_body", error=f"no .rar asset ({tag})"))
            return

        answer = QMessageBox.question(
            self, self.tr_.t("update_available_title"),
            self.tr_.t("update_available_body", tag=tag),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if answer == QMessageBox.Yes:
            self._start_launcher_update(asset_url)

    def _start_launcher_update(self, asset_url):
        if self.update_download_worker is not None and self.update_download_worker.isRunning():
            return
        self.lbl_status.setText(self.tr_.t("update_downloading"))
        self.update_download_worker = updater_module.UpdateDownloadWorker(
            asset_url, config.APP_DIR, sys.executable)
        self.update_download_worker.sig_progress.connect(self._on_update_download_progress)
        self.update_download_worker.sig_finished.connect(self._on_update_download_finished)
        self.update_download_worker.start()

    def _on_update_download_progress(self, downloaded, total):
        pct = f" — {int(downloaded * 100 / total)}%" if total else ""
        self.lbl_status.setText(f"{self.tr_.t('update_downloading')}{pct}")

    def _on_update_download_finished(self, success, batch_path, error):
        if not success:
            QMessageBox.warning(
                self, self.tr_.t("update_error_title"),
                self.tr_.t("update_error_body", error=error))
            self.lbl_status.setText(self.tr_.t("select_folder_prompt"))
            return

        # A partir d'ici, le script .bat attend deja (en boucle sur
        # tasklist) que ce processus disparaisse avant de copier quoi que
        # ce soit : on peut donc fermer la fenetre en toute securite, il ne
        # touchera aux fichiers qu'une fois qu'on aura vraiment quitte.
        updater_module.launch_updater_and_quit(batch_path)
        self.close()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_browse(self):
        chosen = QFileDialog.getExistingDirectory(
            self, self.tr_.t("confirm_install_dir_title"),
            self.edit_install_dir.text() or config.default_install_dir())
        if chosen:
            self.edit_install_dir.setText(chosen)
            self._checked_once = False
            self._refresh_cta()

    def _ensure_install_dir(self):
        install_dir = self.edit_install_dir.text().strip()
        if not install_dir:
            self._on_browse()
            install_dir = self.edit_install_dir.text().strip()
        return install_dir

    def _on_check_clicked(self):
        self._run_check(log=True)

    def _run_check(self, log=False):
        install_dir = self._ensure_install_dir()
        if not install_dir:
            return
        os.makedirs(install_dir, exist_ok=True)

        reset_ids = reset_forced_refresh_entries(install_dir, self.manifest)
        if reset_ids and log:
            self._on_log(
                "[INFO] " + ", ".join(reset_ids) +
                " : reinitialise pour reinstallation complete."
            )

        deep = self.chk_deep_verify.isChecked()
        missing = [e for e in self.manifest["files"]
                   if not is_entry_done(install_dir, e, deep_verify=deep)]
        self._missing_count = len(missing)
        self._checked_once = True
        if log:
            if missing:
                self._on_log("[INFO] " + self.tr_.t("missing_files_found", count=len(missing)))
            else:
                self._on_log("[OK] " + self.tr_.t("all_files_verified"))
        if not missing:
            self.lbl_status.setText(self.tr_.t("all_files_verified"))
        else:
            self.lbl_status.setText(self.tr_.t("missing_files_found", count=len(missing)))
        self._refresh_cta()

    def _on_cta_clicked(self):
        if self.worker is not None:
            self._cancel_install()
            return

        if self._is_installed():
            self._on_play_clicked()
            return

        if not self._checked_once:
            self._run_check(log=True)
            return

        self._start_install()

    def _start_install(self):
        install_dir = self._ensure_install_dir()
        if not install_dir:
            return
        os.makedirs(install_dir, exist_ok=True)
        self._save_settings()
        self.log_console.clear()
        self._dl_tracker = {"name": None, "last_time": None, "last_bytes": 0, "speed_ema": None}
        self._entries_done = 0
        self._entries_total = len(self.manifest["files"])
        self._is_paused = False
        self._refresh_pause_button()
        self.progress_overall.setRange(0, max(self._entries_total, 1))
        self.progress_overall.setValue(0)
        self.progress_current.setRange(0, 1000)
        self.progress_current.setValue(0)
        self.lbl_overall_counter.setText(
            self.tr_.t("files_progress", done=0, total=self._entries_total))

        self.worker = InstallWorker(
            self.manifest, install_dir, config.DEFAULT_REALMLIST,
            deep_verify=self.chk_deep_verify.isChecked())
        self.worker.sig_status.connect(self._on_status)
        self.worker.sig_log.connect(self._on_log)
        self.worker.sig_overall_progress.connect(self._on_overall_progress)
        self.worker.sig_file_progress.connect(self._on_file_progress)
        self.worker.sig_finished.connect(self._on_finished)

        self._set_installing_ui(True)
        self.worker.start()

    def _cancel_install(self):
        # Annulation directe, sans boite de dialogue de confirmation : un
        # QMessageBox natif parente a cette fenetre (sans decoration
        # systeme, WA_TranslucentBackground + masque arrondi) s'est avere
        # instable sur certaines configs Windows - dans certains cas il ne
        # s'affichait pas correctement et l'utilisateur perdait
        # completement la fenetre du launcher en essayant d'interagir avec
        # lui. Annuler un telechargement est de toute facon sans risque :
        # tout ce qui est deja telecharge/extrait reste marque comme fait
        # (voir core/installer.py, fichiers .done) et sera repris sans
        # tout retelecharger a la prochaine installation.
        if self.worker is None:
            return
        self.btn_cta.setEnabled(False)  # evite un double-clic pendant l'arret du thread
        self.btn_pause.setEnabled(False)
        self._on_log("[INFO] " + self.tr_.t("status_cancelled"))
        self.worker.cancel()

    def _on_pause_clicked(self):
        # Vraie pause (pas juste un cosmetique cote UI) : le thread continue
        # de tourner mais n'emet plus la moindre requete/lecture reseau tant
        # qu'on ne clique pas sur "Reprendre" - voir InstallWorker.pause()/
        # resume() et le pause_event transmis a downloader.download_file().
        # Contrairement a Annuler, RIEN n'est supprime : la reprise continue
        # de lire la MEME connexion HTTP deja ouverte, sans nouvelle requete
        # Range (voir la note en tete de core/downloader.py sur pourquoi
        # cette derniere approche avait ete abandonnee).
        if self.worker is None:
            return
        self._is_paused = not self._is_paused
        if self._is_paused:
            self.worker.pause()
            self._on_log("[INFO] " + self.tr_.t("log_paused"))
            name = self._dl_tracker.get("name") or ""
            self.lbl_status.setText(self.tr_.t("status_paused", name=name))
        else:
            # On reinitialise le point de depart du calcul de vitesse : sans
            # ca, le premier calcul apres la reprise diviserait un petit
            # delta d'octets par un ecart de temps incluant toute la duree
            # de la pause, ce qui afficherait un debit ridiculement bas
            # pendant une fraction de seconde avant de se corriger tout seul.
            self._dl_tracker["last_time"] = time.time()
            self.worker.resume()
            self._on_log("[INFO] " + self.tr_.t("log_resumed"))
        self._refresh_pause_button()

    def _on_play_clicked(self):
        install_dir = self.edit_install_dir.text().strip()
        exe_path = None
        for candidate in config.GAME_EXECUTABLE_CANDIDATES:
            path = os.path.join(install_dir, candidate)
            if os.path.isfile(path):
                exe_path = path
                break

        if not exe_path:
            QMessageBox.warning(
                self, self.tr_.t("error_game_not_found_title"),
                self.tr_.t("error_game_not_found_body"))
            return

        self.lbl_status.setText(self.tr_.t("status_launching"))
        try:
            subprocess.Popen([exe_path], cwd=install_dir)
        except OSError as exc:
            QMessageBox.critical(self, self.tr_.t("error_game_not_found_title"), str(exc))

    # ------------------------------------------------------------------
    # Signaux du InstallWorker
    # ------------------------------------------------------------------
    def _on_status(self, key, kwargs):
        self.lbl_status.setProperty("state", "normal")
        self.lbl_status.setText(self.tr_.t(key, **kwargs))
        self._repolish(self.lbl_status)

    def _on_log(self, message):
        self.log_console.appendPlainText(message)

    def _on_overall_progress(self, done, total):
        # `done`/`total` comptent des ENTREES entieres du manifeste (30
        # fichiers/archives), pas des octets : cet evenement n'arrive qu'une
        # fois par entree terminee. Cette barre reste volontairement
        # "grossiere" (un pas entier par entree terminee) : la progression
        # FINE pendant le telechargement d'une seule entree est affichee
        # separement par self.progress_current (voir _on_file_progress),
        # pour ne plus melanger les deux echelles dans une seule barre.
        self._entries_done = done
        self._entries_total = total
        self.progress_overall.setRange(0, max(total, 1))
        self.progress_overall.setValue(done)
        self.lbl_overall_counter.setText(
            self.tr_.t("files_progress", done=done, total=total))

    def _on_file_progress(self, name, downloaded, total):
        pct = f" — {int(downloaded * 100 / total)}%" if total else ""

        # Barre du fichier/de la partie EN COURS uniquement (0-100%) :
        # correspond exactement au pourcentage affiche dans lbl_status
        # juste au-dessus (voir `pct`). Si la taille totale est inconnue
        # (serveur sans Content-Length), on bascule la barre en mode
        # "indetermine" (va-et-vient) plutot que de la laisser figee a 0.
        if total:
            fraction = min(max(downloaded / total, 0.0), 1.0)
            if self.progress_current.maximum() == 0:
                self.progress_current.setRange(0, 1000)
            self.progress_current.setValue(int(fraction * 1000))
        else:
            self.progress_current.setRange(0, 0)

        now = time.time()
        tracker = self._dl_tracker
        if tracker["name"] != name:
            # Nouveau fichier/partie : la progression redemarre a 0 pour ce
            # transfert, donc on reinitialise le suivi de vitesse plutot que
            # de calculer un delta avec l'ancien fichier (ce qui donnerait
            # une vitesse absurde, negative ou enorme, le temps d'un appel).
            tracker.update(name=name, last_time=now, last_bytes=downloaded, speed_ema=None)
        else:
            elapsed = now - tracker["last_time"]
            delta_bytes = downloaded - tracker["last_bytes"]
            if elapsed > 0 and delta_bytes >= 0:
                instant_speed = delta_bytes / elapsed
                # Moyenne mobile exponentielle : lisse les a-coups (chaque
                # chunk reseau arrive de façon irreguliere) sans faire une
                # simple moyenne depuis le debut qui reagirait trop lentement
                # a un vrai changement de debit.
                prev = tracker["speed_ema"]
                tracker["speed_ema"] = instant_speed if prev is None else (0.3 * instant_speed + 0.7 * prev)
            tracker["last_time"] = now
            tracker["last_bytes"] = downloaded

        extra = ""
        speed = tracker["speed_ema"]
        if speed and speed > 0:
            extra = f" — {self.tr_.t('speed_label', speed=downloader.human_size(speed, lang=self.tr_.lang))}"
            if total:
                remaining_bytes = max(0, total - downloaded)
                eta_text = _format_duration(remaining_bytes / speed)
                if eta_text:
                    extra += f" — {self.tr_.t('eta_inline', eta=eta_text)}"

        self.lbl_status.setText(f"{self.tr_.t('status_downloading', name=name)}{pct}{extra}")

    def _on_finished(self, success, key, kwargs):
        # IMPORTANT : sig_finished est emis DEPUIS le thread du worker,
        # juste AVANT que sa methode run() ne retourne (donc juste avant que
        # le thread systeme sous-jacent ne s'arrete reellement). La connexion
        # est automatiquement en file d'attente (signal emis depuis un autre
        # thread que celui de l'UI), donc ce slot peut s'executer, cote UI,
        # dans la toute petite fenetre de temps ou le thread n'a pas encore
        # fini de s'arreter cote systeme. Si on laisse alors self.worker
        # passer a None ici (plus aucune reference Python -> l'objet QThread
        # est detruit par le ramasse-miettes) AVANT que le thread ne soit
        # vraiment termine, Qt declenche "QThread: Destroyed while thread is
        # still running" - un avertissement inoffensif sous Linux, mais qui
        # s'est revele FATAL sous Windows dans le build de l'utilisateur :
        # tout le processus se fermait instantanement, sans aucun message
        # d'erreur, juste apres l'affichage de "Installation annulee.". Le
        # .wait() ci-dessous elimine cette course : a ce stade il ne reste
        # plus rien a executer dans run(), donc il rend la main en quelques
        # millisecondes tout au plus.
        if self.worker is not None:
            self.worker.wait(3000)
        self._set_installing_ui(False)
        self.worker = None

        self.lbl_status.setProperty("state", "success" if success else "error")
        self.lbl_status.setText(self.tr_.t(key, **kwargs))
        self._repolish(self.lbl_status)

        if success:
            self._checked_once = False
            self._missing_count = 0
        self._refresh_cta()

    def _repolish(self, widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    # ------------------------------------------------------------------
    def _set_installing_ui(self, installing):
        self.edit_install_dir.setEnabled(not installing)
        self.btn_browse.setEnabled(not installing)
        self.btn_check.setEnabled(not installing)
        self.chk_deep_verify.setEnabled(not installing)
        self.btn_pause.setVisible(installing)
        self.btn_pause.setEnabled(installing)
        if not installing:
            # Repart toujours sur "Pause" (jamais "Reprendre") au prochain
            # lancement d'installation, meme si on a quitte l'ecran alors
            # qu'on etait en pause (ex: apres un Annuler pendant la pause).
            self._is_paused = False
            self._refresh_pause_button()
            self.progress_current.setRange(0, 1000)
            self.progress_current.setValue(0)
        self._refresh_cta()

    def _is_installed(self):
        install_dir = self.edit_install_dir.text().strip()
        if not install_dir or not os.path.isdir(install_dir):
            return False
        return is_fully_installed(self.manifest, install_dir,
                                   deep_verify=self.chk_deep_verify.isChecked())

    def _refresh_cta(self):
        t = self.tr_.t
        self.btn_cta.setEnabled(True)  # annule le setEnabled(False) pose par _cancel_install()
        if self.worker is not None:
            self.btn_cta.setText(t("btn_cancel"))
            self.btn_cta.setObjectName("DangerButton")
        elif self._is_installed():
            self.btn_cta.setText(t("btn_play"))
            self.btn_cta.setObjectName("PrimaryButton")
        elif self._checked_once and self._missing_count:
            self.btn_cta.setText(t("btn_install"))
            self.btn_cta.setObjectName("PrimaryButton")
        else:
            self.btn_cta.setText(t("btn_check"))
            self.btn_cta.setObjectName("PrimaryButton")
        self._repolish(self.btn_cta)

    def closeEvent(self, event):
        if self.worker is not None:
            self.worker.cancel()
            self.worker.wait(3000)
        if self.status_worker is not None and self.status_worker.isRunning():
            # ServerStatusWorker fait une vraie requete reseau (timeout de
            # 6s, voir core/server_status.py). Un wait() trop court ici (500ms
            # avant ce correctif) peut rendre la main a Qt AVANT que ce thread
            # ne soit reellement termine ; Qt detruit alors l'objet QThread en
            # meme temps que la fenetre se ferme, ce qui produit "QThread:
            # Destroyed while thread is still running" - le meme crash fatal
            # (fermeture immediate et silencieuse de toute l'application) que
            # celui corrige plus haut dans _on_finished(). On attend donc au
            # moins aussi longtemps que le timeout reseau du thread de statut.
            self.status_worker.wait(7000)
        # Meme raisonnement que pour status_worker juste au-dessus (voir sa
        # note) : on laisse les threads de verification/telechargement de
        # mise a jour du launcher, s'ils tournent encore, vraiment se
        # terminer avant de fermer la fenetre (et donc de perdre toute
        # reference Python vers eux), pour eviter le meme crash "QThread:
        # Destroyed while thread is still running".
        if self.update_check_worker is not None and self.update_check_worker.isRunning():
            self.update_check_worker.wait(7000)
        if self.update_download_worker is not None and self.update_download_worker.isRunning():
            self.update_download_worker.wait(3000)
        self._save_settings()
        super().closeEvent(event)
