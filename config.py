"""
config.py
---------
Chemins et constantes partagees par tout le launcher.

Gere aussi la difference entre "lance depuis les sources" (python main.py)
et "lance depuis l'exe PyInstaller" (les fichiers sont alors extraits dans
un dossier temporaire pointe par sys._MEIPASS).
"""

import sys
import os
import json
import platform

APP_NAME = "Azeroth Universe Launcher"
APP_VERSION = "1.0.1"

# Numero de build affiche dans la barre de titre ("build 3.3.9"), aligne sur
# le numero de version d'UniverseEmu (3.3.9a.49448 dans son README). Purement
# indicatif pour les joueurs, a mettre a jour au fil des versions du serveur.
CLIENT_BUILD = "3.3.9"

# Depot GitHub et tag de release correspondant a la version du LAUNCHER
# actuellement livree (voir core/updater.py) : PAS le meme depot que le
# manifeste du client (manifest.json -> AzerothUniverseCore/UniverseClient).
# A chaque nouvelle release du launcher (tag + AzerothUniverseLauncher.rar
# publies sur GitHub), mettez LAUNCHER_VERSION a jour avec le tag exact de
# cette release AVANT de compiler, sinon le launcher fraichement compile se
# proposera de se "mettre a jour" vers... lui-meme en boucle.
LAUNCHER_UPDATE_REPO = "AzerothUniverseCore/UniverseLauncherPy"
LAUNCHER_VERSION = "339.49449"

# Liens ouverts par les boutons SITE WEB / S'INSCRIRE de la barre du bas.
# NOTE : seule l'URL du site principal a ete confirmee dans nos echanges
# precedents ; aucune page d'inscription dediee ne nous a ete communiquee,
# donc S'INSCRIRE pointe par defaut vers la meme page d'accueil. Changez
# REGISTER_URL ci-dessous si vous avez une page de creation de compte dediee
# (panel ACP, etc).
WEBSITE_URL = "https://azeroth-universe.eu/en"
REGISTER_URL = "https://azeroth-universe.eu/en/register"

# URL d'un endpoint JSON de statut serveur, au format attendu :
# {"online": true, "players": 12}. Voir build/server_status_api/status.php
# pour l'implementation cote serveur (compte les personnages `online = 1`
# dans la base characters, via un compte MySQL dedie en lecture seule).
# Mettez a None si vous retirez/deplacez cet endpoint : le badge "Serveur"
# repassera alors sur un statut neutre ("Statut non configure") plutot que
# d'inventer un nombre de joueurs.
STATUS_URL = "https://azeroth-universe.eu/api/status.php"
STATUS_POLL_INTERVAL_MS = 60_000

# Correspondance langue interface launcher -> valeur du parametre WTF
# "SET locale" attendu par le client WoW.
WTF_LOCALE_MAP = {"fr": "frFR", "en": "enUS"}

# Fichier ou l'on memorise les preferences utilisateur (langue, dossier
# d'installation, adresse du realmlist...) entre deux lancements du launcher.
SETTINGS_FILENAME = "au_launcher_settings.json"


def _base_dir():
    """Dossier contenant les ressources embarquees (manifest.json, assets/,
    tools/). En mode PyInstaller --onefile, ce sont les fichiers ajoutes via
    --add-data, extraits dans sys._MEIPASS a l'execution."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def _app_dir():
    """Dossier ou vit reellement l'executable/le script (pour ecrire les
    settings a cote, meme en mode --onefile ou _MEIPASS est un dossier
    temporaire jete a chaque lancement)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _base_dir()
APP_DIR = _app_dir()

MANIFEST_PATH = os.path.join(BASE_DIR, "manifest.json")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")
BACKGROUND_PATH = os.path.join(ASSETS_DIR, "background.png")
ICON_PATH = os.path.join(ASSETS_DIR, "icon.ico")
# Slashs normalises : requis par la syntaxe url() des feuilles de style Qt,
# meme sous Windows (un chemin avec des antislashs y casse le parsing QSS).
CHECKBOX_CHECKED_PATH = os.path.join(ASSETS_DIR, "checkbox_checked.png").replace(os.sep, "/")

SETTINGS_PATH = os.path.join(APP_DIR, SETTINGS_FILENAME)

# Nom de l'executable du jeu recherche par le bouton "Jouer" une fois
# l'installation terminee. AzerothUniverse.exe est le nom standard des clients 3.3.5a ;
# le launcher recherche aussi en variante minuscule par securite.
GAME_EXECUTABLE_CANDIDATES = ["AzerothUniverse.exe", "azerothuniverse.exe", "AzerothUniverse.exe"]

DEFAULT_REALMLIST = "realm.azeroth-universe.eu"


def default_install_dir():
    if platform.system() == "Windows":
        return os.path.join(os.environ.get("USERPROFILE", "C:\\"), "Games", "AzerothUniverse")
    return os.path.join(os.path.expanduser("~"), "AzerothUniverse")


def load_manifest():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_settings():
    if os.path.isfile(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_settings(data):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError:
        pass
