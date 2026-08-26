"""
core/server_status.py
----------------------
Badge "Serveur en ligne" affiche en haut a droite du launcher (voir la
maquette fournie par le client). Interroge periodiquement une URL JSON
optionnelle (config.STATUS_URL) au format attendu :

    {"online": true, "players": 12}

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


class ServerStatusWorker(QThread):
    # (configured: bool, online: bool|None, players: int|None)
    sig_result = Signal(bool, object, object)

    def __init__(self, url, timeout=6, parent=None):
        super().__init__(parent)
        self.url = url
        self.timeout = timeout

    def run(self):
        if not self.url:
            self.sig_result.emit(False, None, None)
            return
        try:
            req = urllib.request.Request(
                self.url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
            online = bool(data.get("online", False))
            players = data.get("players")
            players = int(players) if isinstance(players, (int, float)) else None
            self.sig_result.emit(True, online, players)
        except (urllib.error.URLError, ValueError, TypeError, OSError):
            # Endpoint configure mais injoignable/reponse invalide : on le
            # signale comme "configure mais hors ligne" plutot que de planter.
            self.sig_result.emit(True, False, None)
