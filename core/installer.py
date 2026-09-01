"""
core/installer.py
------------------
Chef d'orchestre de l'installation : lit manifest.json, telecharge chaque
fichier/partie, extrait les archives, place tout au bon endroit, puis ecrit
le realmlist.wtf. Tourne dans un QThread pour ne jamais geler l'interface.

Reprise apres interruption : chaque entree du manifest (fichier direct ou
archive) est marquee "terminee" par un petit fichier vide dans
<install_dir>/.au_cache/done/<id>.done UNE FOIS que le resultat final est en
place. Si le launcher est ferme puis relance, toute entree deja marquee est
resautee (sauf si son fichier/dossier de destination a disparu entre temps),
ce qui evite de re-telecharger des Go de donnees deja installees.
"""

import os
import shutil
import threading
import time

from PySide6.QtCore import QThread, Signal

from core import downloader, extractor


class InstallCancelled(Exception):
    pass


def cache_dir_for(install_dir):
    return os.path.join(install_dir, ".au_cache")


def done_flag_path(install_dir, entry_id):
    return os.path.join(cache_dir_for(install_dir), "done", f"{entry_id}.done")


def parts_cache_dir_for(install_dir, entry_id):
    return os.path.join(cache_dir_for(install_dir), "parts", entry_id)


# Destinations d'extraction PARTAGEES entre PLUSIEURS entrees du manifeste :
# "Data" (tous les patchs .MPQ : patch-Y.MPQ, patch-D.MPQ... ainsi que
# common.MPQ, expansion.MPQ, lichking.MPQ) et "." (l'archive
# "AzerothUniverse (Additional)", qui s'extrait a la racine meme du dossier
# client, la ou vivent aussi le launcher, les DLL, etc). A la difference de
# destinations DEDIEES comme "Data/frFR" ou "Data/enUS" (qui n'appartiennent
# qu'a UNE SEULE entree et peuvent donc etre entierement supprimees sans
# risque), il ne faut JAMAIS faire un rmtree() de ces dossiers partages : ca
# emporterait aussi tout le reste du client deja installe - voire,
# litteralement, toute l'installation pour ".".
SHARED_ARCHIVE_EXTRACT_TARGETS = (".", "Data")


def reset_entry(install_dir, entry):
    """Supprime le flag "termine" d'UNE entree du manifest (et, quand on
    peut identifier son resultat sans risque de casser autre chose, ce
    resultat lui-meme), pour forcer son retelechargement/reinstallation
    complete au prochain passage. Generalisation du menage manuel qu'Aurora
    faisait a la main dans .au_cache/ et dans le dossier Data avant chaque
    mise a jour (a l'origine fait seulement pour frFR/enUS, puis etendu a
    TOUTES les entrees - patchs .MPQ du dossier Data, et l'archive
    "AzerothUniverse (Additional)" a la racine du client - voir
    reset_forced_refresh_entries ci-dessous)."""
    flag = done_flag_path(install_dir, entry["id"])
    try:
        if os.path.isfile(flag):
            os.remove(flag)
    except OSError:
        pass

    # Le cache des parties .rar deja telechargees (entrees "archive") doit
    # sauter lui aussi : sinon _install_archive() les retrouve dans
    # .au_cache/parts/<id>/ avec la meme taille qu'avant et les considere
    # "deja telechargees a l'identique", meme si le contenu a change cote
    # serveur (nouvelle version publiee sous la meme URL) - exactement le
    # probleme que ce reset est cense corriger.
    parts_cache = parts_cache_dir_for(install_dir, entry["id"])
    if os.path.isdir(parts_cache):
        shutil.rmtree(parts_cache, ignore_errors=True)

    if entry["kind"] == "direct":
        # Telechargement direct d'un seul fichier (ex: common.MPQ,
        # patch-2.MPQ...) : "target" pointe exactement vers CE fichier, on
        # peut donc le supprimer sans toucher a rien d'autre.
        target = os.path.normpath(os.path.join(install_dir, entry["target"]))
        try:
            if os.path.isfile(target):
                os.remove(target)
        except OSError:
            pass
        return

    # kind == "archive"
    extract_to = entry.get("extract_to", ".")
    if extract_to in SHARED_ARCHIVE_EXTRACT_TARGETS:
        # Destination partagee avec d'autres entrees : voir
        # SHARED_ARCHIVE_EXTRACT_TARGETS ci-dessus, jamais de rmtree ici.
        # Le flag + le cache de parties suffisent : au prochain passage,
        # l'entree sera retelechargee et re-extraite, et
        # extractor.move_merge() ecrasera uniquement les fichiers qu'elle
        # produit, sans toucher au reste du dossier partage.
        return

    # Destination DEDIEE (frFR -> "Data/frFR", enUS -> "Data/enUS") :
    # n'appartient qu'a cette seule entree, supprimable entierement sans
    # risque, comme avant.
    dest_dir = os.path.normpath(os.path.join(install_dir, extract_to))
    if os.path.isdir(dest_dir):
        shutil.rmtree(dest_dir, ignore_errors=True)


def reset_forced_refresh_entries(install_dir, manifest):
    """Applique reset_entry() a CHAQUE entree du manifest (locales frFR/
    enUS, tous les patchs .MPQ du dossier Data, et l'archive
    "AzerothUniverse (Additional)" a la racine du client) : le clic sur
    "Verifier" ne fait donc plus jamais confiance a un ancien marqueur
    local et retelecharge systematiquement la derniere version publiee de
    chaque element, comme le faisait deja Aurora a la main avant chaque
    mise a jour. Renvoie la liste des ids reinitialises, pour affichage
    dans le journal du launcher."""
    reset_ids = []
    for entry in manifest.get("files", []):
        reset_entry(install_dir, entry)
        reset_ids.append(entry["id"])
    return reset_ids


def is_entry_done(install_dir, entry, deep_verify=False):
    """`deep_verify` (case a cocher "Verification approfondie (MD5)" dans
    l'UI) : Azeroth Universe ne publie pas de sommes de controle officielles
    pour ses fichiers, donc une vraie verification MD5 n'est pas possible
    ici. En guise de verification renforcee "au mieux", on recompare, pour
    les fichiers .MPQ en telechargement direct seulement, la taille locale
    a la taille annoncee par le serveur (HEAD Content-Length) : un fichier
    tronque/corrompu aura presque toujours une taille differente. Les
    archives ne sont pas re-verifiees ainsi (on ne conserve pas leurs
    parties .rar une fois extraites, donc rien a re-comparer)."""
    flag = done_flag_path(install_dir, entry["id"])
    if not os.path.isfile(flag):
        return False

    if entry["kind"] == "direct":
        target = os.path.join(install_dir, entry["target"])
        if not os.path.isfile(target):
            return False
        if deep_verify:
            remote_size = downloader.get_remote_size(entry["url"])
            if remote_size is not None and os.path.getsize(target) != remote_size:
                return False
        return True

    return True


def is_fully_installed(manifest, install_dir, deep_verify=False):
    """Utilise par l'UI pour savoir si le bouton "Jouer" doit etre actif
    sans avoir a lancer un QThread juste pour verifier."""
    return all(is_entry_done(install_dir, e, deep_verify=deep_verify) for e in manifest["files"])


class InstallWorker(QThread):
    # (status_key, kwargs_dict) -> traduit cote UI, pour rester a jour meme
    # si l'utilisateur change de langue en cours d'installation.
    sig_status = Signal(str, dict)
    sig_log = Signal(str)
    sig_overall_progress = Signal(int, int)              # (fait, total)
    sig_file_progress = Signal(str, int, object)         # (nom, recu, total|None)
    sig_finished = Signal(bool, str, dict)                # (succes, cle, kwargs)

    def __init__(self, manifest, install_dir, realmlist_address, deep_verify=False, parent=None):
        super().__init__(parent)
        self.manifest = manifest
        self.install_dir = install_dir
        self.realmlist_address = realmlist_address
        self.deep_verify = deep_verify
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()

    def cancel(self):
        self._cancel_event.set()

    def pause(self):
        self._pause_event.set()

    def resume(self):
        self._pause_event.clear()

    def is_paused(self):
        return self._pause_event.is_set()

    # ------------------------------------------------------------------
    def _cache_dir(self):
        return cache_dir_for(self.install_dir)

    def _is_done(self, entry):
        # Verification defensive : si la destination finale a disparu
        # (utilisateur qui a supprime des fichiers manuellement), on
        # retelecharge/re-extrait plutot que de faire confiance aveuglement
        # au marqueur.
        return is_entry_done(self.install_dir, entry, deep_verify=self.deep_verify)

    def _mark_done(self, entry):
        flag = done_flag_path(self.install_dir, entry["id"])
        os.makedirs(os.path.dirname(flag), exist_ok=True)
        with open(flag, "w", encoding="utf-8") as f:
            f.write("ok")

    def _check_cancel(self):
        if self._cancel_event.is_set():
            raise InstallCancelled()

    def _wait_if_paused(self):
        # Utilise ENTRE deux fichiers/parties (avant d'ouvrir la prochaine
        # connexion) : pendant un telechargement en cours, c'est
        # `pause_event` transmis directement a downloader.download_file qui
        # gere la pause au niveau du flux reseau deja ouvert (voir la note
        # dans core/downloader.py). On continue quand meme a verifier
        # l'annulation ici pour qu'Annuler reste instantane meme en pause.
        while self._pause_event.is_set():
            self._check_cancel()
            time.sleep(0.2)

    # ------------------------------------------------------------------
    def run(self):
        try:
            self._run_install()
        except (InstallCancelled, downloader.DownloadCancelled):
            # Deux exceptions d'annulation distinctes existent : InstallCancelled
            # (levee par _check_cancel(), entre deux fichiers/parties) et
            # downloader.DownloadCancelled (levee DANS download_file(), pendant
            # la lecture d'un chunk reseau). Les deux doivent atterrir ici : ne
            # rattraper que la premiere faisait tomber une annulation en plein
            # telechargement dans la branche "erreur" generique ci-dessous, avec
            # un message vide (str(DownloadCancelled()) == ""), d'ou le "Erreur :"
            # sans texte observe en cliquant sur Annuler pendant un transfert.
            self.sig_finished.emit(False, "status_cancelled", {})
        except Exception as exc:  # noqa: BLE001 - on veut remonter TOUTE erreur a l'UI
            self.sig_log.emit(f"[ERREUR] {exc}")
            self.sig_finished.emit(False, "status_error", {"error": str(exc)})

    def _run_install(self):
        files = self.manifest["files"]
        total = len(files)
        os.makedirs(self.install_dir, exist_ok=True)

        for index, entry in enumerate(files):
            self._check_cancel()
            self._wait_if_paused()

            if self._is_done(entry):
                self.sig_log.emit(f"[OK] {entry['display_name']} deja installe, ignore.")
                self.sig_overall_progress.emit(index + 1, total)
                continue

            if entry["kind"] == "direct":
                self._install_direct(entry)
            else:
                self._install_archive(entry)

            self._mark_done(entry)
            self.sig_overall_progress.emit(index + 1, total)

        self._check_cancel()
        self._write_realmlist()

        # Nettoyage du cache si tout s'est bien passe et qu'il est vide
        cache = self._cache_dir()
        try:
            if os.path.isdir(cache) and not any(
                os.scandir(cache)
            ):
                shutil.rmtree(cache, ignore_errors=True)
        except OSError:
            pass

        self.sig_finished.emit(True, "status_done", {})

    # ------------------------------------------------------------------
    def _install_direct(self, entry):
        name = entry["display_name"]
        self.sig_status.emit("status_downloading", {"name": name})
        target = os.path.join(self.install_dir, entry["target"])

        def progress_cb(downloaded, total_bytes):
            self.sig_file_progress.emit(name, downloaded, total_bytes)

        self._check_cancel()
        downloader.download_file(
            entry["url"], target, progress_cb=progress_cb,
            cancel_event=self._cancel_event, pause_event=self._pause_event,
        )
        self.sig_log.emit(f"[OK] Telecharge : {name}")

    def _install_archive(self, entry):
        name = entry["display_name"]
        parts = entry["parts"]
        total_parts = len(parts)
        cache_dir = os.path.join(self._cache_dir(), "parts", entry["id"])
        os.makedirs(cache_dir, exist_ok=True)

        local_parts = []
        for i, url in enumerate(parts, start=1):
            self._check_cancel()
            self._wait_if_paused()
            part_label = f"{name} ({i}/{total_parts})" if total_parts > 1 else name
            self.sig_status.emit("status_downloading", {"name": part_label})
            local_path = os.path.join(cache_dir, os.path.basename(url))
            local_parts.append(local_path)

            if os.path.isfile(local_path):
                remote_size = downloader.get_remote_size(url)
                if remote_size is not None and os.path.getsize(local_path) == remote_size:
                    self.sig_log.emit(f"[OK] {part_label} deja telecharge, ignore.")
                    continue

            def progress_cb(downloaded, total_bytes, _label=part_label):
                self.sig_file_progress.emit(_label, downloaded, total_bytes)

            downloader.download_file(
                url, local_path, progress_cb=progress_cb,
                cancel_event=self._cancel_event, pause_event=self._pause_event,
            )

        self._check_cancel()
        self.sig_status.emit("status_extracting", {"name": name})

        # IMPORTANT : on extrait d'abord dans un dossier ISOLE (propre a cette
        # entree), jamais directement dans la destination finale. La
        # destination finale (ex: Data/, ou meme la racine du client pour
        # "extract_to": ".") contient deja d'autres fichiers (Data/,
        # .au_cache/, des patchs precedents...), donc la logique de
        # "aplatissement du sous-dossier unique" (flatten_single_subfolder)
        # se tromperait en la regardant directement : elle ne doit s'appliquer
        # qu'au contenu propre de CETTE archive, avant de le fusionner avec le
        # reste de l'installation.
        extract_tmp = os.path.join(self._cache_dir(), "extract_tmp", entry["id"])
        if os.path.isdir(extract_tmp):
            shutil.rmtree(extract_tmp, ignore_errors=True)
        os.makedirs(extract_tmp, exist_ok=True)
        try:
            extractor.extract_archive(local_parts[0], extract_tmp)
        except extractor.ExtractionError:
            # L'archive locale semble corrompue ou invalide (7-Zip n'arrive
            # meme pas a l'ouvrir) alors que sa taille correspondait a ce qui
            # etait attendu : le contenu s'est corrompu quelque part entre le
            # serveur et le disque (reseau instable, reprise apres coupure,
            # antivirus/synchronisation cloud qui modifie le fichier pendant
            # l'ecriture, etc.). On supprime les parties locales pour forcer
            # un telechargement entierement neuf (sans reprise partielle) au
            # prochain essai, plutot que de laisser l'utilisateur bloque sur
            # des fichiers locaux corrompus qui echoueraient indefiniment de
            # la meme facon a chaque nouvel essai.
            self.sig_log.emit(
                f"[INFO] Fichiers locaux de {name} corrompus, supprimes : "
                "relancez l'installation pour un telechargement neuf."
            )
            for p in local_parts:
                try:
                    if os.path.isfile(p):
                        os.remove(p)
                except OSError:
                    pass
            shutil.rmtree(extract_tmp, ignore_errors=True)
            raise

        flatten_name = entry.get("flatten_single_subfolder")
        if flatten_name:
            extractor.flatten_single_subfolder(extract_tmp, flatten_name)

        self._check_cancel()
        self.sig_status.emit("status_placing", {"name": name})
        dest_dir = os.path.normpath(os.path.join(self.install_dir, entry["extract_to"]))
        os.makedirs(dest_dir, exist_ok=True)
        extractor.move_merge(extract_tmp, dest_dir)
        shutil.rmtree(extract_tmp, ignore_errors=True)

        self.sig_log.emit(f"[OK] Extrait : {name} -> {entry['extract_to']}")

        # On libere l'espace disque occupe par les .rar une fois extraits.
        extractor.cleanup_parts(local_parts)
        try:
            if not any(os.scandir(cache_dir)):
                os.rmdir(cache_dir)
        except OSError:
            pass

    # ------------------------------------------------------------------
    def _write_realmlist(self):
        self.sig_status.emit("status_writing_realmlist", {})
        content = f"set realmlist {self.realmlist_address}\n"
        for locale in ("enUS", "frFR"):
            locale_dir = os.path.join(self.install_dir, "Data", locale)
            if not os.path.isdir(locale_dir):
                continue
            path = os.path.join(locale_dir, "realmlist.wtf")
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self.sig_log.emit(f"[OK] realmlist.wtf ecrit dans Data/{locale}/")
