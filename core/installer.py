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

import hashlib
import json
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


def manifest_fingerprint_path(install_dir):
    return os.path.join(cache_dir_for(install_dir), "manifest_fingerprint.txt")


def compute_manifest_fingerprint(manifest):
    """Empreinte stable du contenu du manifest (ids, URLs, destinations...) :
    sert a detecter qu'un manifest.json REELLEMENT different a ete publie
    (nouvelle build du launcher embarquant un manifest.json a jour), par
    opposition a "l'utilisateur a simplement referme puis rouvert le meme
    launcher". json.dumps(sort_keys=True) rend la comparaison independante
    de l'ordre des cles (mais PAS de l'ordre des entrees dans "files" ni des
    parts, ce qui est voulu : un ajout/retrait/reordonnancement de fichiers
    a livrer doit bien redeclencher un rafraichissement force)."""
    encoded = json.dumps(manifest, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
    "AzerothUniverse (Additional)" a la racine du client), comme le faisait
    deja Aurora a la main avant chaque mise a jour - mais UNE SEULE FOIS par
    manifest reellement publie, pas a chaque clic sur "Verifier".

    manifest.json est embarque DANS l'executable du launcher (voir
    config.MANIFEST_PATH) : il ne change donc que lorsqu'une nouvelle build
    du launcher est installee, jamais entre deux lancements du meme exe. Sans
    ce garde-fou, chaque "Verifier" (y compris le tout premier, automatique,
    a chaque ouverture - voir ui/main_window.py::_on_cta_clicked) effacait
    TOUS les marqueurs "termine", forcant un retelechargement complet du
    client (plusieurs Go) a chaque lancement, meme quand rien n'avait
    change cote serveur. On compare donc une empreinte du manifest actuel a
    celle enregistree lors du dernier reset (fichier
    manifest_fingerprint_path()) : identique -> on ne touche a rien (le
    verifie/reinstalle normal, base sur is_entry_done(), se charge de ne
    retelecharger que ce qui manque reellement) ; differente (premiere
    installation, ou nouvelle build du launcher avec un manifest.json a jour)
    -> reset complet comme avant, puis l'empreinte est mise a jour pour ne
    plus redeclencher tant que ce meme manifest reste en place.

    Renvoie la liste des ids reinitialises (vide si rien n'a ete reinitialise
    cette fois), pour affichage dans le journal du launcher."""
    fingerprint = compute_manifest_fingerprint(manifest)
    fp_path = manifest_fingerprint_path(install_dir)

    previous_fingerprint = None
    try:
        if os.path.isfile(fp_path):
            with open(fp_path, "r", encoding="utf-8") as f:
                previous_fingerprint = f.read().strip()
    except OSError:
        previous_fingerprint = None

    if previous_fingerprint == fingerprint:
        return []

    reset_ids = []
    for entry in manifest.get("files", []):
        reset_entry(install_dir, entry)
        reset_ids.append(entry["id"])

    try:
        os.makedirs(os.path.dirname(fp_path), exist_ok=True)
        with open(fp_path, "w", encoding="utf-8") as f:
            f.write(fingerprint)
    except OSError:
        # Si l'ecriture echoue (disque plein, permissions...), on ne casse
        # pas l'installation en cours pour autant : au pire, le prochain
        # "Verifier" refera un reset complet (moins grave qu'une exception
        # ici qui empecherait de jouer du tout).
        pass

    return reset_ids


def _sha256_file(path, chunk_size=1024 * 1024):
    """SHA256 d'un fichier local, calcule par blocs (jamais tout en memoire -
    important pour les gros .MPQ, plusieurs centaines de Mo)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _read_done_marker(flag_path):
    """Lit un marqueur .done au format JSON ecrit par _mark_done() (voir
    InstallWorker._mark_done ci-dessous). Renvoie None si le fichier est
    absent, illisible, ou dans l'ANCIEN format ("ok" en texte brut, ecrit par
    les versions du launcher d'avant ce correctif) : dans ce cas l'appelant
    (is_entry_done, en verification approfondie) n'a aucune empreinte a
    comparer et doit se rabattre sur un comportement prudent."""
    try:
        with open(flag_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return None
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _remote_metadata_matches(recorded, current):
    """Compare l'empreinte distante enregistree lors du dernier
    telechargement reussi (voir _mark_done) a l'etat ACTUEL du serveur
    (voir downloader.get_remote_metadata). On utilise le premier identifiant
    fiable disponible DES DEUX COTES, dans l'ordre : ETag (le plus fiable -
    change des qu'un seul octet change dans le fichier distant), puis
    Last-Modified, puis Content-Length en dernier recours (le moins fiable :
    un remplacement peut coincider avec exactement la meme taille - mais
    mieux que rien si le serveur/CDN ne renvoie ni ETag ni Last-Modified).
    Si AUCUN identifiant exploitable n'est disponible des deux cotes a la
    fois, on ne peut rien affirmer avec certitude : on considere alors, par
    prudence, que ca NE correspond PAS - ca force une reverification/
    retelechargement plutot que de laisser passer silencieusement un
    fichier qu'on ne sait plus authentifier."""
    for key in ("etag", "last_modified", "content_length"):
        r = recorded.get(key)
        c = current.get(key)
        if r is not None and c is not None:
            return r == c
    return False


def is_entry_done(install_dir, entry, deep_verify=False):
    """`deep_verify` (case a cocher "Verification approfondie" dans l'UI).

    BUG CORRIGE (aout/septembre 2026) : le marqueur .done ne contenait
    auparavant que le texte "ok" - une fois pose, une entree (frFR, enUS,
    patch-X.MPQ...) etait consideree a jamais a jour, MEME si le fichier
    correspondant avait ete REMPLACE depuis sur GitHub sous LA MEME URL
    (upload qui ecrase une release existante - le cas vecu : republier
    frFR.part1.rar/part2.rar avec un contenu different mais le meme nom).
    Pire : pour les entrees "archive", aucune reverification n'existait meme
    en mode "approfondi" (on ne conserve pas les .rar une fois extraits,
    donc il n'y avait litteralement rien a comparer) - seuls les fichiers
    "direct" (.MPQ telecharges seuls) etaient re-verifies, et uniquement par
    taille.

    Le marqueur .done contient desormais un JSON ecrit par
    InstallWorker._mark_done() : pour chaque URL source de l'entree (le
    fichier direct, ou toutes les "parts" d'une archive), l'ETag/
    Last-Modified/Content-Length observes cote serveur au moment ou le
    telechargement a reussi (Azeroth Universe ne publie pas de MD5/SHA256
    officiels, donc pas de "vraie" empreinte de reference possible - voir
    downloader.get_remote_metadata pour le detail de ce choix), plus un
    SHA256 LOCAL pour les fichiers "direct" (verification d'integrite locale,
    en plus de la comparaison distante).

    En verification approfondie, on recompare donc maintenant, pour TOUTE
    entree (direct ET archive) : l'empreinte distante enregistree contre
    l'etat actuel du serveur (HEAD, tres bon marche - voir
    _remote_metadata_matches) ; et, pour les fichiers "direct" en plus, le
    SHA256 local recalcule (detecte aussi une corruption/alteration
    purement locale, independante du serveur).

    Un marqueur dans l'ANCIEN format ("ok" texte brut, pose par une version
    du launcher d'avant ce correctif) n'a aucune empreinte a comparer : en
    verification approfondie, il est traite comme PAS a jour (force UNE
    SEULE reinstallation complete de cette entree, apres quoi le nouveau
    marqueur JSON permettra de vraies comparaisons futures)."""
    flag = done_flag_path(install_dir, entry["id"])
    if not os.path.isfile(flag):
        return False

    if entry["kind"] == "direct":
        target = os.path.join(install_dir, entry["target"])
        if not os.path.isfile(target):
            return False

    if not deep_verify:
        return True

    data = _read_done_marker(flag)
    if data is None:
        return False

    for record in data.get("remote") or []:
        url = record.get("url")
        if not url:
            return False
        current = downloader.get_remote_metadata(url)
        if not _remote_metadata_matches(record, current):
            return False

    if entry["kind"] == "direct":
        stored_hash = data.get("sha256")
        if stored_hash:
            target = os.path.join(install_dir, entry["target"])
            try:
                if _sha256_file(target) != stored_hash:
                    return False
            except OSError:
                return False

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
    # BUG FIX (barre de progression/pourcentage qui redevient vide et
    # affiche un pourcentage NEGATIF passe un certain point - constate sur
    # frFR/enUS) : le "recu" ci-dessous etait declare Signal(..., int, ...).
    # Un Signal PySide type explicitement "int" est marshalle en entier C
    # 32 bits SIGNE lors de la traversee thread-a-thread (borne a environ
    # 2,147 Go) - PAS un entier Python a precision arbitraire. Tant que
    # chaque telechargement restait sous cette limite (c'etait le cas avant
    # le decoupage en plusieurs "parts"/segments en parallele - voir
    # core/downloader.py : chaque "part" seule de frFR/enUS, ~1 Go, passait
    # sous le plafond), aucun souci. Mais l'agregation du nombre d'octets
    # recus a travers PLUSIEURS parties en parallele (voir
    # _install_archive/make_progress_cb ci-dessous) fait tres vite depasser
    # 2,147 Go pour une archive de ~2 Go au total (frFR/enUS) : la valeur
    # deborde alors en negatif au milieu du telechargement, d'ou le
    # pourcentage negatif observe et la barre qui retombe a 0 (voir
    # ui/main_window.py::_on_file_progress, dont le calcul de fraction se
    # borne a 0 quand le total agrege deborde lui aussi en negatif). "object"
    # transporte la valeur Python telle quelle (entier a precision
    # arbitraire), sans aucune conversion/troncature C - le correctif
    # s'applique aussi bien au nombre d'octets recus qu'au total.
    sig_file_progress = Signal(str, object, object)     # (nom, recu, total|None)
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
        # BUG FIX (voir is_entry_done ci-dessus pour le detail) : on
        # n'ecrit plus juste "ok", mais une empreinte JSON permettant de
        # detecter plus tard qu'un fichier a ete remplace sur GitHub sous
        # la meme URL. Cout : une requete HEAD de plus par URL source
        # (fichier direct, ou chaque "part" d'une archive) - negligeable,
        # faite une seule fois ici, juste apres un telechargement/une
        # installation qui vient de reussir.
        urls = [entry["url"]] if entry["kind"] == "direct" else list(entry["parts"])
        data = {
            "remote": [
                {"url": url, **downloader.get_remote_metadata(url)}
                for url in urls
            ],
        }

        if entry["kind"] == "direct":
            target = os.path.join(self.install_dir, entry["target"])
            try:
                data["sha256"] = _sha256_file(target)
            except OSError:
                # Pas bloquant : le marqueur reste ecrit sans SHA256 local,
                # la comparaison distante (ci-dessus) reste operante seule.
                pass

        flag = done_flag_path(self.install_dir, entry["id"])
        os.makedirs(os.path.dirname(flag), exist_ok=True)
        with open(flag, "w", encoding="utf-8") as f:
            json.dump(data, f)

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
        # Segmente en plusieurs connexions quand le fichier/serveur s'y
        # pretent (voir le point 4 de la note en tete de core/downloader.py)
        # - se rabat seul sur une connexion unique sinon (petit fichier,
        # taille inconnue, ou serveur qui n'annonce pas le support des
        # requetes par plage).
        downloader.download_file_segmented(
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

        # Progression combinee de TOUTES les parties en cours de
        # telechargement EN PARALLELE (voir downloader.download_files_parallel
        # plus bas, et la note "Debit (aout 2026)" en tete de
        # core/downloader.py) : plusieurs parties progressent en meme temps,
        # sur des threads differents, donc on additionne leurs octets
        # recus/totaux a chaque mise a jour pour n'emettre qu'UNE SEULE
        # progression/vitesse globale vers l'UI (sig_file_progress garde le
        # meme nom "entree", `name`, du debut a la fin) plutot que de faire
        # clignoter l'affichage entre plusieurs parties qui avancent en
        # meme temps. Bonus : la vitesse affichee est ainsi le debit AGREGE
        # reel de toutes les connexions, ce qui est justement le chiffre qui
        # interesse le joueur.
        # BUG FIX (vitesse affichee erratique - "ca monte, ca descend, c'est
        # aleatoire") : chaque download_file() a SON PROPRE throttle interne
        # ("pas plus souvent que toutes les ~0.1s", voir downloader.py) qui
        # ignore completement les autres threads. Avec 4 parties en
        # parallele, ca donnait donc jusqu'a 4 emissions independantes et
        # PAS SYNCHRONISEES toutes les ~0.1s chacune : cote UI (main_window.
        # _on_file_progress), la vitesse est calculee comme un delta
        # d'octets divise par le delta de TEMPS ECOULE entre deux emissions
        # consecutives - or avec 4 threads qui se decalent les uns par
        # rapport aux autres, ces emissions arrivaient parfois quasi
        # groupees (delta de temps tres petit -> vitesse instantanee
        # demesuree) et parfois espacees (delta plus grand -> vitesse qui
        # semble chuter), d'ou l'impression de valeur aleatoire malgre le
        # lissage (moyenne mobile) deja applique cote UI, qui n'etait pas
        # concu pour un rythme d'emission aussi irregulier.
        #
        # On limite donc ICI, cote emission (donc independamment du nombre
        # de parties en parallele), a UNE SEULE emission agregee toutes les
        # PROGRESS_EMIT_INTERVAL secondes au maximum - peu importe combien
        # de threads ont progresse entre-temps, on envoie a chaque fois
        # l'etat cumule le plus recent. Le rythme redevient ainsi regulier
        # (comme un telechargement a une seule connexion), ce qui est
        # justement ce que le calcul de vitesse cote UI attend pour donner
        # une courbe stable plutot que des a-coups.
        PROGRESS_EMIT_INTERVAL = 0.15  # secondes

        progress_lock = threading.Lock()
        part_progress = {}  # index de partie -> [downloaded, total_or_None]
        emit_state = {"last_emit": 0.0}

        def make_progress_cb(idx):
            def _cb(downloaded, total_bytes):
                now = time.time()
                with progress_lock:
                    part_progress[idx] = [downloaded, total_bytes]
                    # On force quand meme une emission des qu'UNE partie
                    # termine (downloaded >= total_bytes) meme si le delai
                    # n'est pas ecoule : sinon l'affichage final (100%) peut
                    # accuser un petit retard visible, notamment sur la
                    # toute derniere partie qui cloture l'ensemble.
                    part_finished = bool(total_bytes) and downloaded >= total_bytes
                    if (now - emit_state["last_emit"]) < PROGRESS_EMIT_INTERVAL and not part_finished:
                        return
                    emit_state["last_emit"] = now
                    snapshot = list(part_progress.values())
                dl_sum = sum(v[0] for v in snapshot)
                totals = [v[1] for v in snapshot]
                total_sum = sum(totals) if all(t is not None for t in totals) else None
                self.sig_file_progress.emit(name, dl_sum, total_sum)
            return _cb

        local_parts = []
        jobs = []
        for i, url in enumerate(parts, start=1):
            self._check_cancel()
            part_label = f"{name} ({i}/{total_parts})" if total_parts > 1 else name
            local_path = os.path.join(cache_dir, os.path.basename(url))
            local_parts.append(local_path)

            if os.path.isfile(local_path):
                remote_size = downloader.get_remote_size(url)
                if remote_size is not None and os.path.getsize(local_path) == remote_size:
                    self.sig_log.emit(f"[OK] {part_label} deja telecharge, ignore.")
                    continue

            jobs.append({"url": url, "dest_path": local_path, "progress_cb": make_progress_cb(i)})

        if jobs:
            self._wait_if_paused()
            self._check_cancel()
            self.sig_status.emit("status_downloading", {"name": name})
            # Plusieurs "parts" telechargees EN PARALLELE (connexions HTTP
            # separees) au lieu d'une par une : voir la note "Debit (aout
            # 2026)" en tete de core/downloader.py pour pourquoi une seule
            # connexion a la fois plafonnait le debit bien en dessous de ce
            # que la ligne du joueur permet reellement.
            downloader.download_files_parallel(
                jobs, cancel_event=self._cancel_event, pause_event=self._pause_event,
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
