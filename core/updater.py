"""
core/updater.py
----------------
Mise a jour automatique du LAUNCHER lui-meme (a ne pas confondre avec
core/installer.py, qui installe/met a jour le CLIENT WoW). Au demarrage, on
interroge l'API GitHub Releases du depot du launcher
(AzerothUniverseCore/UniverseLauncherPy) ; si le tag de la derniere release
differe de la version actuellement executee, on propose de telecharger et
d'appliquer cette nouvelle version.

Comparaison de version : on essaie d'abord une comparaison NUMERIQUE (les
tags de ce depot suivent un format propre au projet, ex: "339.49448", pas
un schema major.minor.patch classique, mais restent des groupes de chiffres
separes par des points - on les compare donc comme des tuples d'entiers,
"339.49449" > "339.49448"). Ce n'est QUE si l'un des deux ne ressemble pas
du tout a ca (aucun chiffre dedans) qu'on retombe sur une simple inegalite
de chaine, pour rester compatible avec un format de tag totalement
different a l'avenir.

Pourquoi pas une simple inegalite partout (comme avant) : pendant les tests
en local, il est frequent d'avancer LAUNCHER_VERSION dans config.py AVANT
de publier la release GitHub correspondante (ex: passer a "339.49449" en
prevision de la prochaine build, alors que "339.49448" est encore la
derniere release publiee). Avec une simple inegalite, le launcher proposait
alors de "mettre a jour" vers une version PLUS ANCIENNE que celle en cours
d'execution - source de confusion. La comparaison numerique evite ça : elle
ne propose une mise a jour que si la release GitHub est reellement PLUS
RECENTE que la version executee.

CONTRAINTE WINDOWS INCONTOURNABLE : le launcher compile (PyInstaller
--onefile, voir build/launcher.spec) tourne depuis un unique .exe verrouille
par Windows tant que le processus est en vie - impossible de l'ecraser
depuis lui-meme. La technique standard (utilisee par la plupart des
launchers de jeu) consiste donc a :
  1. Telecharger et extraire la nouvelle version dans un dossier temporaire.
  2. Ecrire un petit script .bat qui attend que CE processus (identifie par
     son PID) ait completement quitte, copie ensuite le nouveau contenu
     par-dessus l'installation existante, relance l'executable, puis se
     supprime lui-meme.
  3. Lancer ce script de façon detachee et quitter immediatement l'appli
     Qt : le fichier .exe se retrouve alors deverrouille cote Windows des
     que le processus Python se termine reellement, ce que le script
     attend activement avant de copier quoi que ce soit.

En mode developpement (`python main.py`, pas d'exe PyInstaller), cette
mecanique de remplacement de fichier verrouille ne s'applique pas et n'est
pas tentee : on se contente de signaler qu'une mise a jour existe.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

from PySide6.QtCore import QThread, Signal

from core import downloader, extractor

GITHUB_API_TIMEOUT = 15
USER_AGENT = downloader.USER_AGENT


class UpdateCheckError(Exception):
    pass


class UpdateApplyError(Exception):
    pass


def fetch_latest_release(repo, timeout=GITHUB_API_TIMEOUT):
    """Interroge l'API GitHub ("releases/latest") et renvoie
    (tag_name, asset_url) : `asset_url` pointe vers la premiere piece
    jointe se terminant par ".rar" de cette release (None si la release
    n'en contient aucune). Renvoie (None, None) si le depot n'a tout
    simplement aucune release publiee (404, pas une erreur en soi). Leve
    UpdateCheckError pour tout autre probleme reseau/HTTP."""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None, None
        raise UpdateCheckError(f"HTTP {exc.code}") from exc
    except (urllib.error.URLError, ValueError, OSError) as exc:
        raise UpdateCheckError(str(exc)) from exc

    tag = data.get("tag_name")
    asset_url = None
    for asset in data.get("assets", []) or []:
        name = asset.get("name", "")
        if name.lower().endswith(".rar"):
            asset_url = asset.get("browser_download_url")
            break
    return tag, asset_url


def _version_tuple(version_str):
    """Extrait tous les groupes de chiffres d'une chaine de version
    ("339.49448" -> (339, 49448)) pour une comparaison numerique. Renvoie
    None si la chaine ne contient AUCUN chiffre (format totalement
    different) : le seul cas ou l'appelant doit retomber sur une simple
    comparaison d'egalite."""
    if not version_str:
        return None
    digits = re.findall(r"\d+", str(version_str))
    if not digits:
        return None
    return tuple(int(d) for d in digits)


def is_update_available(current_version, latest_tag):
    if not latest_tag:
        return False

    current_tuple = _version_tuple(current_version)
    latest_tuple = _version_tuple(latest_tag)
    if current_tuple is not None and latest_tuple is not None:
        # Comparaison numerique : ne propose une mise a jour QUE si la
        # release GitHub est reellement plus recente (evite de proposer de
        # "revenir" a une version anterieure quand la version locale a ete
        # avancee en prevision d'une prochaine publication - voir le
        # docstring de ce module).
        return latest_tuple > current_tuple

    # Fallback : au moins l'une des deux chaines ne contient aucun chiffre
    # exploitable, on ne peut pas comparer numeriquement. Ancien
    # comportement (simple inegalite) conserve pour ne rien casser sur un
    # format de tag inattendu.
    return latest_tag != current_version


class UpdateCheckWorker(QThread):
    # (available, tag, asset_url, error_message_or_None)
    sig_result = Signal(bool, object, object, object)

    def __init__(self, repo, current_version, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.current_version = current_version

    def run(self):
        try:
            tag, asset_url = fetch_latest_release(self.repo)
        except UpdateCheckError as exc:
            self.sig_result.emit(False, None, None, str(exc))
            return
        available = is_update_available(self.current_version, tag)
        self.sig_result.emit(available, tag, asset_url, None)


class UpdateDownloadWorker(QThread):
    # (downloaded_bytes, total_bytes_or_None)
    sig_progress = Signal(int, object)
    # (success, batch_script_path_or_None, error_message_or_None)
    sig_finished = Signal(bool, object, object)

    def __init__(self, asset_url, install_root, exe_path, parent=None):
        super().__init__(parent)
        self.asset_url = asset_url
        self.install_root = install_root
        self.exe_path = exe_path

    def run(self):
        try:
            batch_path = download_and_prepare_update(
                self.asset_url, self.install_root, self.exe_path,
                progress_cb=lambda done, total: self.sig_progress.emit(done, total),
            )
            self.sig_finished.emit(True, batch_path, None)
        except UpdateApplyError as exc:
            self.sig_finished.emit(False, None, str(exc))
        except Exception as exc:  # noqa: BLE001 - on veut remonter TOUTE erreur a l'UI
            self.sig_finished.emit(False, None, str(exc))


def download_and_prepare_update(asset_url, install_root, exe_path, progress_cb=None):
    """Telecharge l'archive .rar de mise a jour, l'extrait dans un dossier
    temporaire (HORS de install_root : le launcher tourne encore depuis
    la, on ne touche a rien tant que le script .bat n'a pas pris le
    relais), et ecrit le script .bat charge de finir le travail une fois ce
    processus termine. Renvoie le chemin du script .bat a lancer.

    Ne fait rien de destructif ici : aucun fichier de l'installation
    existante n'est touche par cette fonction, seulement lu (le PID/chemin
    de l'exe courant). Tout le remplacement reel se fait plus tard, dans le
    script .bat, apres la fermeture du launcher."""
    work_dir = tempfile.mkdtemp(prefix="au_launcher_update_")
    rar_path = os.path.join(work_dir, "update.rar")

    downloader.download_file(asset_url, rar_path, progress_cb=progress_cb)

    extract_dir = os.path.join(work_dir, "extracted")
    os.makedirs(extract_dir, exist_ok=True)
    try:
        extractor.extract_archive(rar_path, extract_dir)
    except extractor.ExtractionError as exc:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise UpdateApplyError(str(exc)) from exc

    # Si l'archive enveloppe son contenu dans un unique sous-dossier, on le
    # remonte d'un niveau (meme logique que pour les archives du client,
    # voir extractor.flatten_single_subfolder).
    extractor.flatten_single_subfolder(extract_dir)

    try:
        os.remove(rar_path)
    except OSError:
        pass

    batch_path = _write_update_batch(work_dir, extract_dir, install_root, exe_path)
    return batch_path


def _write_update_batch(work_dir, extract_dir, install_root, exe_path):
    """Ecrit le script .bat qui, une fois CE processus termine :
      1. copie tout le contenu de `extract_dir` par-dessus `install_root`
         (robocopy /E : copie recursive avec ecrasement des fichiers deja
         presents, SANS l'option /MIR - on ne veut surtout pas supprimer ce
         qui n'est pas dans l'archive de mise a jour, comme manifest.json,
         Data/, ou les parametres sauvegardes de l'utilisateur) ;
      2. relance `exe_path` ;
      3. nettoie le dossier temporaire et se supprime lui-meme.

    Le PID du processus courant est passe au script pour qu'il attende
    activement (boucle sur `tasklist`) que ce PID ait disparu, plutot que
    de deviner un delai fixe : la fermeture d'une appli Qt peut prendre de
    quelques dixiemes de seconde a plusieurs secondes selon la machine.
    """
    pid = os.getpid()
    batch_path = os.path.join(work_dir, "apply_update.bat")

    # robocopy renvoie des codes de sortie "bit-flags" ou toute valeur < 8
    # signifie un succes (voire un succes partiel normal, ex: "8" = echecs
    # de copie qu'on ignore volontairement ici plutot que de bloquer
    # indefiniment le redemarrage du launcher pour un fichier secondaire).
    # On ne teste donc PAS %errorlevel% apres le robocopy : c'est un choix
    # assume ("best effort"), pas un oubli.
    content = f"""@echo off
setlocal
set "AU_PID={pid}"
set "AU_SRC={extract_dir}"
set "AU_DEST={install_root}"
set "AU_EXE={exe_path}"

:au_wait_exit
tasklist /FI "PID eq %AU_PID%" 2>nul | find "%AU_PID%" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto au_wait_exit
)

robocopy "%AU_SRC%" "%AU_DEST%" /E /R:5 /W:1 /NFL /NDL /NJH /NJS >nul

start "" "%AU_EXE%"

rem On ne supprime QUE le sous-dossier extrait (AU_SRC), jamais AU_WORKDIR :
rem ce script vit lui-meme dans AU_WORKDIR, et supprimer le dossier PARENT
rem d'un .bat en cours d'execution est nettement moins fiable que supprimer
rem le fichier .bat lui-meme (l'astuce "(goto) 2>nul & del" ci-dessous,
rem bien connue, fonctionne car cmd.exe garde le contenu du script en
rem memoire une fois lu - rien ne garantit le meme comportement pour tout
rem un dossier). AU_WORKDIR ne contient plus alors qu'un dossier
rem "extracted" vide et ce script : reste negligeable dans %TEMP%, nettoye
rem par Windows comme n'importe quel fichier temporaire.
rmdir /S /Q "%AU_SRC%" >nul 2>&1
(goto) 2>nul & del "%~f0"
"""
    with open(batch_path, "w", encoding="utf-8") as f:
        f.write(content)
    return batch_path


def launch_updater_and_quit(batch_path):
    """Lance le script .bat de facon completement detachee (il doit
    survivre a la fermeture immediate du launcher qui suit cet appel), puis
    revient a l'appelant pour que celui-ci quitte l'application Qt."""
    creationflags = 0
    if sys.platform == "win32":
        creationflags = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | getattr(subprocess, "DETACHED_PROCESS", 0)
        )
    subprocess.Popen(
        ["cmd", "/c", batch_path],
        creationflags=creationflags,
        close_fds=True,
    )
