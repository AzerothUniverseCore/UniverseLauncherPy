"""
core/server_status.py
----------------------
Badge "Serveur en ligne" affiche en haut a droite du launcher (voir la
maquette fournie par le client). Interroge periodiquement une URL JSON
optionnelle (config.STATUS_URL) au format attendu :

    {"online": true, "players": 12, "characters": [{"name": "Foo", "race": 1, "class": 2, "level": 80}, ...]}

"characters" est OPTIONNEL (une reponse qui ne le contient pas, ou le
contient a null, reste valide) : c'est la liste utilisee par la fenetre
"Personnages en ligne" qui s'ouvre au clic sur le badge (voir
ui/main_window.py, OnlineCharactersDialog). `race`/`class` sont les
identifiants numeriques standard de WoW 3.3.5a, traduits en texte localise
cote UI (voir i18n.py), pas ici.

IMPORTANT : aucune URL de statut reelle ne nous a ete communiquee pour
Azeroth Universe. Tant que config.STATUS_URL vaut None (valeur par defaut),
ce module n'effectue AUCUNE requete reseau et le badge affiche un statut
neutre "Statut non configure" plutot que d'inventer un nombre de joueurs
en ligne. Des que vous aurez un endpoint reel (par ex. un petit script PHP
sur votre site qui lit le nombre de sessions actives cote UniverseEmu),
renseignez STATUS_URL dans config.py pour activer le badge en direct.

Utilise `urllib.request` (bibliotheque standard) plutot que `requests`,
comme core/downloader.py - voir la note en tete de ce dernier pour le
pourquoi (comportement different face a certains antivirus/proxys faisant
de l'inspection TLS, observe lors du debogage des telechargements).
"""

import json
import urllib.request
import urllib.error

from PySide6.QtCore import QThread, Signal

USER_AGENT = "AzerothUniverseLauncher/1.0"


def _parse_characters(raw):
    """Normalise le champ "characters" d'une reponse status.php en une
    liste de dicts {"name": str, "race": int, "class": int, "level": int},
    en ignorant silencieusement toute entree malformee plutot que de faire
    planter tout le badge de statut pour UNE ligne invalide (un endpoint
    custom, pas forcement aussi rigoureux que status.php, pourrait par
    exemple laisser passer une valeur nulle ou un champ manquant)."""
    if not isinstance(raw, list):
        return []
    characters = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            continue
        try:
            race = int(entry.get("race", 0))
            char_class = int(entry.get("class", 0))
            level = int(entry.get("level", 0))
        except (TypeError, ValueError):
            continue
        characters.append({"name": name, "race": race, "class": char_class, "level": level})
    return characters


class ServerStatusWorker(QThread):
    # (configured: bool, online: bool|None, players: int|None, characters: list[dict])
    sig_result = Signal(bool, object, object, list)

    def __init__(self, url, timeout=6, parent=None):
        super().__init__(parent)
        self.url = url
        self.timeout = timeout

    def run(self):
        if not self.url:
            self.sig_result.emit(False, None, None, [])
            return
        try:
            req = urllib.request.Request(
                self.url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
            online = bool(data.get("online", False))
            players = data.get("players")
            players = int(players) if isinstance(players, (int, float)) else None
            characters = _parse_characters(data.get("characters"))
            self.sig_result.emit(True, online, players, characters)
        except (urllib.error.URLError, ValueError, TypeError, OSError):
            # Endpoint configure mais injoignable/reponse invalide : on le
            # signale comme "configure mais hors ligne" plutot que de planter.
            self.sig_result.emit(True, False, None, [])
