"""
ui/theme.py
-----------
Palette et feuille de style (QSS) originales, alignees sur la maquette
validee par le client : fond tres sombre bleu-nuit/noir, cartes bordees d'un
liseret dore, gros bouton d'action dore, barre de titre "faite maison"
(fenetre sans decoration systeme). Aucun asset graphique Blizzard : tout est
couleur/QSS/formes generees par code (voir generate_assets.py pour le fond
et le logo).
"""

import config

# Chemin absolu vers l'icone "coche" (voir generate_assets.py). Un QSS Qt
# ne sait pas dessiner un glyphe de coche par lui-meme (pas d'equivalent du
# "content" CSS) : sans cette image, QCheckBox::indicator:checked ne peut
# que remplir tout le carre d'une couleur unie. Chemin absolu (et slashs
# normalises) pour que ca marche quel que soit le dossier de travail au
# lancement de l'exe compile.
CHECKBOX_CHECKED_PATH = config.CHECKBOX_CHECKED_PATH

# Palette
BG_DARK = "#090b10"
BG_TITLEBAR = "#0d0f15"
BG_PANEL = "#12141b"
BG_PANEL_SOFT = "#171a23"
BG_FIELD = "#1a1e29"
BORDER = "#3c3320"
BORDER_SOFT = "#2a2517"
GOLD = "#c9a227"
GOLD_BRIGHT = "#e8c34a"
GOLD_DIM = "#8a6f22"
TEXT_PRIMARY = "#f2eee2"
TEXT_SECONDARY = "#9aa0ad"
TEXT_MUTED = "#5f6672"
SUCCESS = "#3ddc84"
DANGER = "#e05b5b"

# Rayon des coins arrondis de la fenetre (fenetre sans decoration systeme,
# le "vrai" arrondi est obtenu en masquant la fenetre avec un QPainterPath
# de ce rayon dans ui/main_window.py ; cette valeur est aussi utilisee ici
# pour que le contour QSS suive exactement la meme courbe).
WINDOW_RADIUS = 14

STYLESHEET = f"""
QWidget {{
    background-color: transparent;
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "DejaVu Sans", sans-serif;
    font-size: 13px;
}}

/* QMessageBox (confirmations/erreurs) : fenetre a part, avec sa propre
   decoration systeme (elle n'a pas Qt.FramelessWindowHint). La regle
   generale QWidget plus haut, qui met un fond transparent, s'appliquerait
   sinon aussi a elle, ce qui l'affichait en pratique avec un fond
   transparent/incoherent sur certaines configurations Windows - on lui
   redonne explicitement un fond opaque et un style coherent avec le reste. */
QMessageBox {{
    background-color: {BG_PANEL};
}}

QMessageBox QLabel {{
    background-color: transparent;
    color: {TEXT_PRIMARY};
}}

QMainWindow {{
    background-color: {BG_DARK};
}}

#RootBackground {{
    background-color: {BG_DARK};
    border-radius: {WINDOW_RADIUS}px;
    border: 1px solid {BORDER};
}}

/* ---------------- Barre de titre personnalisee ---------------- */

#TitleBar {{
    background-color: {BG_TITLEBAR};
    border-bottom: 1px solid {BORDER};
}}

#TitleBarLabel {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
}}

#TitleBarBuild {{
    color: {TEXT_MUTED};
    font-size: 11px;
}}

QPushButton#WinButton {{
    background: transparent;
    border: none;
    border-radius: 4px;
    color: {TEXT_SECONDARY};
    font-size: 13px;
    padding: 4px 10px;
}}

QPushButton#WinButton:hover {{
    background-color: #1c202b;
    color: {TEXT_PRIMARY};
}}

QPushButton#WinButton[danger="true"]:hover {{
    background-color: {DANGER};
    color: #ffffff;
}}

QPushButton#LangButton {{
    background: transparent;
    border: 1px solid {BORDER};
    border-radius: 5px;
    color: {TEXT_SECONDARY};
    font-weight: 700;
    font-size: 11px;
    padding: 3px 10px;
}}

QPushButton#LangButton:hover {{
    border: 1px solid {GOLD_DIM};
    color: {TEXT_PRIMARY};
}}

QPushButton#LangButton:checked {{
    background-color: {GOLD};
    border: 1px solid {GOLD};
    color: #1a1305;
}}

/* ---------------- En-tete / hero ---------------- */

#HeroTitle {{
    color: {TEXT_PRIMARY};
    font-size: 30px;
    font-weight: 800;
    letter-spacing: 1px;
}}

#HeroTagline {{
    color: {TEXT_SECONDARY};
    font-size: 13px;
}}

#GoldUnderline {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {GOLD}, stop:0.5 {GOLD_BRIGHT}, stop:1 rgba(201,162,39,0));
    max-height: 2px;
    min-height: 2px;
    border: none;
}}

#StatusBadge {{
    background-color: {BG_PANEL_SOFT};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

#StatusBadgeTitle {{
    color: {TEXT_PRIMARY};
    font-weight: 700;
    font-size: 12px;
}}

#StatusBadgeSub {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
}}

#StatusDot {{
    border-radius: 5px;
    min-width: 10px;
    max-width: 10px;
    min-height: 10px;
    max-height: 10px;
}}

#StatusDot[state="online"] {{
    background-color: {SUCCESS};
}}

#StatusDot[state="offline"] {{
    background-color: {DANGER};
}}

#StatusDot[state="unknown"] {{
    background-color: {TEXT_MUTED};
}}

/* ---------------- Cartes ---------------- */

#Card {{
    background-color: rgba(18, 20, 27, 0.92);
    border: 1px solid {BORDER};
    border-radius: 10px;
}}

#CardHeader {{
    color: {GOLD};
    font-weight: 700;
    font-size: 12px;
    letter-spacing: 1.5px;
}}

#NewsCard {{
    background-color: {BG_PANEL_SOFT};
    border: 1px solid {BORDER_SOFT};
    border-radius: 8px;
}}

#NewsTag {{
    background-color: {GOLD};
    color: #1a1305;
    font-weight: 700;
    font-size: 10px;
    border-radius: 4px;
    padding: 2px 8px;
}}

#NewsDate {{
    color: {TEXT_MUTED};
    font-size: 11px;
}}

#NewsTitle {{
    color: {TEXT_PRIMARY};
    font-weight: 700;
    font-size: 13px;
}}

#NewsBody {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
}}

/* ---------------- Champs ---------------- */

QLabel {{
    background: transparent;
}}

QLineEdit, QComboBox {{
    background-color: {BG_FIELD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 10px;
    color: {TEXT_PRIMARY};
    selection-background-color: {GOLD};
    selection-color: #1a1305;
}}

QLineEdit:focus, QComboBox:focus {{
    border: 1px solid {GOLD_DIM};
}}

QCheckBox {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {BORDER};
    border-radius: 3px;
    background-color: {BG_FIELD};
}}

QCheckBox::indicator:hover {{
    border: 1px solid {GOLD_DIM};
}}

QCheckBox::indicator:checked {{
    image: url({CHECKBOX_CHECKED_PATH});
    border: none;
}}

/* ---------------- Boutons ---------------- */

QPushButton {{
    background-color: {BG_FIELD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 14px;
    color: {TEXT_PRIMARY};
    font-weight: 500;
}}

QPushButton:hover {{
    border: 1px solid {GOLD_DIM};
}}

QPushButton:disabled {{
    color: {TEXT_MUTED};
    border: 1px solid {BORDER_SOFT};
}}

QPushButton#OutlineButton {{
    background-color: transparent;
    border: 1px solid {GOLD_DIM};
    color: {GOLD_BRIGHT};
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 0.5px;
    padding: 8px 16px;
}}

QPushButton#OutlineButton:hover {{
    background-color: rgba(201, 162, 39, 0.12);
    border: 1px solid {GOLD};
}}

QPushButton#PrimaryButton {{
    background-color: {GOLD};
    border: 1px solid {GOLD};
    color: #1a1305;
    font-weight: 800;
    font-size: 13px;
    letter-spacing: 0.5px;
    padding: 10px 30px;
    border-radius: 6px;
}}

QPushButton#PrimaryButton:hover {{
    background-color: {GOLD_BRIGHT};
    border: 1px solid {GOLD_BRIGHT};
}}

QPushButton#PrimaryButton:pressed {{
    background-color: #a5820f;
}}

QPushButton#PrimaryButton:disabled {{
    background-color: #2e2a1a;
    border: 1px solid #2e2a1a;
    color: {TEXT_MUTED};
}}

QPushButton#DangerButton {{
    background-color: transparent;
    border: 1px solid {DANGER};
    color: {DANGER};
    font-weight: 800;
    font-size: 13px;
    padding: 10px 30px;
    border-radius: 6px;
}}

QPushButton#DangerButton:hover {{
    background-color: rgba(224, 91, 91, 0.15);
}}

/* ---------------- Progression / journal ---------------- */

QProgressBar {{
    background-color: {BG_FIELD};
    border: 1px solid {BORDER};
    border-radius: 5px;
    text-align: center;
    color: transparent;
    max-height: 8px;
    min-height: 8px;
}}

QProgressBar::chunk {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {GOLD_DIM}, stop:1 {GOLD_BRIGHT});
    border-radius: 4px;
}}

QPlainTextEdit#LogConsole {{
    background-color: #0b0d12;
    border: 1px solid {BORDER_SOFT};
    border-radius: 6px;
    color: {TEXT_SECONDARY};
    font-family: "DejaVu Sans Mono", monospace;
    font-size: 11px;
}}

QScrollArea {{
    border: none;
    background: transparent;
}}

QScrollArea > QWidget > QWidget {{
    background: transparent;
}}

QScrollBar:vertical {{
    background: {BG_PANEL};
    width: 9px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 24px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QLabel#StatusLabel {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
}}

QLabel#StatusLabel[state="error"] {{
    color: {DANGER};
}}

QLabel#StatusLabel[state="success"] {{
    color: {SUCCESS};
}}

QLabel#FooterVersion {{
    color: {TEXT_MUTED};
    font-size: 11px;
}}

QLabel#OverallCounterLabel {{
    color: {TEXT_MUTED};
    font-size: 10px;
}}

/* Barre "progression globale" (nombre d'entrees terminees) : plus fine et
   plus terne que la barre par defaut (celle du fichier en cours, juste
   au-dessus dans l'UI) pour qu'on ne les confonde plus visuellement -
   voir ui/main_window.py, _build_bottom_bar / _on_overall_progress. */
QProgressBar#ProgressOverall {{
    max-height: 4px;
    min-height: 4px;
}}

QProgressBar#ProgressOverall::chunk {{
    background-color: {GOLD_DIM};
    border-radius: 2px;
}}
"""
