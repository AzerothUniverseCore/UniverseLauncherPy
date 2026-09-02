"""
core/downloader.py
-------------------
Telechargement HTTP simple avec :
  - progression (callback appele regulierement avec octets recus/total)
  - annulation cooperative via un threading.Event
  - retentatives en cas d'erreur reseau transitoire (chaque tentative
    retelecharge le fichier EN ENTIER depuis le debut - voir la note
    ci-dessous sur pourquoi il n'y a plus de reprise partielle)

IMPORTANT - historique de debogage (aout 2026), a lire avant de
retoucher ce fichier :

1) Ce module utilisait au depart la bibliotheque tierce `requests`, puis
   est passe a `urllib.request` (bibliotheque standard) en pensant que le
   probleme venait d'un desaccord de confiance TLS specifique a
   `requests`/`certifi`. Resultat : AUCUN changement, le probleme
   persistait a l'identique avec les deux. Ce n'etait pas la cause.

2) La vraie cause, confirmee en comparant ce module a une version de
   secours du launcher qui, elle, fonctionnait de facon fiable sur la
   meme machine/connexion : ce module tentait de REPRENDRE un
   telechargement interrompu en pleine lecture (erreur reseau
   transitoire) via un en-tete HTTP Range, en ajoutant les octets
   manquants a la suite du fichier partiel deja sur le disque - y
   compris PENDANT LA MEME session de telechargement (une nouvelle
   tentative apres coupure, pas seulement une reprise apres fermeture du
   launcher).

   Sur une connexion mobile/4G (frequente chez les joueurs - pas besoin
   d'un reseau exotique, une simple connexion 4G avec un forfait limite
   suffit), un gros telechargement de plusieurs minutes (l'archive
   frFR/enUS, ~2 Go chacune) a largement le temps de subir un accroc
   reseau. Rien ne garantit alors qu'une NOUVELLE requete Range, sur une
   nouvelle connexion TCP (qui peut transiter par un relais/cache
   operateur different du tout premier octet recu), serve exactement la
   suite logique des octets deja ecrits. Resultat observe, de facon
   parfaitement reproductible sur le gros fichier et JAMAIS sur les
   petits .MPQ (trop rapides pour subir un accroc reseau en cours de
   route) : un fichier final de la BONNE taille (Content-Length
   identique au fichier attendu) mais au contenu corrompu au milieu,
   que 7-Zip refusait d'ouvrir. Une reprise mal alignee de quelques
   octets suffit a casser irremediablement une archive RAR.

   Un simple telechargement complet SANS reprise (ce que fait un
   navigateur classique, et ce que faisait deja la version de secours du
   launcher) ne presentait jamais ce probleme.

Ce module ne tente donc plus AUCUNE reprise partielle, ni au sein d'une
meme tentative, ni d'une session a l'autre : en cas d'echec (reseau ou
annulation), le fichier partiel est rejete et la tentative suivante
retelecharge tout depuis le debut (jusqu'a `max_retries` fois). C'est un
compromis assume : un peu moins efficace en cas de grosse coupure reseau
en cours de telechargement (on reperd la progression du fichier EN
COURS, pas celle des fichiers deja entierement termines - voir le
systeme de marqueurs .done dans core/installer.py, inchange), mais
fiable. Un fichier corrompu qu'il faut de toute facon retelecharger
integralement (voir l'auto-nettoyage dans installer.py en cas d'echec
d'extraction) coute de toute facon les memes octets, pour rien.

Ce module ne connait rien de Qt : il est appele depuis un QThread (voir
core/installer.py) mais reste testable/utilisable en pur Python.

3) Debit (aout 2026) : plusieurs joueurs ont rapporte un debit plafonne
   (~30 Mo/s) via le launcher alors que le meme fichier, telecharge
   manuellement depuis GitHub, atteint ~80 Mo/s sur la meme connexion.
   Cause : ce module telechargeait les fichiers/parties UN PAR UN, sur une
   seule connexion HTTP a la fois - or une seule connexion, meme vers un
   CDN rapide, plafonne generalement bien en dessous du debit reellement
   disponible. Voir `download_files_parallel()` ci-dessous, qui ouvre
   plusieurs connexions simultanees (utilisee par core/installer.py pour
   telecharger les differentes "parts" d'une meme archive en parallele) :
   chaque fichier individuel reste telecharge integralement d'un bloc par
   un seul thread (aucun decoupage par en-tete Range), donc sans reintroduire
   le risque de corruption decrit au point 2) ci-dessus.

4) Debit, suite (septembre 2026) : le point 3) ne suffisait pas pour les
   fichiers "direct" a UNE SEULE URL (la majorite des patchs .MPQ) ni pour
   une archive a une seule "part" - ceux-la restaient sur UNE SEULE
   connexion. Un joueur en fibre (~900 Mb/s descendant confirme par
   speedtest, plein debit sur d'autres launchers de jeux sur la MEME ligne)
   ne recuperait que ~4 Mo/s sur ce launcher : le plafond n'est ni sa ligne
   ni une limite artificielle du launcher, c'est le nombre de connexions
   simultanees pour UN MEME fichier (les autres launchers segmentent
   systematiquement leurs telechargements, comme le fait tout gestionnaire
   de telechargement serieux). Voir `download_file_segmented()` ci-dessous :
   decoupe UN fichier en plusieurs plages d'octets (Range) recuperees en
   parallele.

   A NE PAS CONFONDRE avec la reprise partielle interdite au point 2) :
   celle-ci reprenait un telechargement INTERROMPU en ajoutant des octets
   MANQUANTS a la suite d'un fichier PARTIEL deja sur disque, potentiellement
   longtemps apres coup, sur une NOUVELLE connexion qui pouvait atterrir sur
   un etat CDN different de celui qui avait servi les premiers octets - d'ou
   le desalignement. `download_file_segmented()` fait tout autre chose :
   TOUS les segments sont demandes DES LE DEBUT, EN PARALLELE, DANS LA MEME
   TENTATIVE, contre le MEME fichier immuable (une release GitHub publiee ne
   change pas pendant le telechargement) - chaque segment couvre une plage
   FIXE et DISJOINTE, ecrite UNE SEULE FOIS a l'offset correspondant. Si UN
   SEUL segment echoue, TOUTE la tentative est rejetee (le .part est
   supprime) et la tentative suivante refait TOUS les segments depuis zero -
   la meme politique "tout ou rien" que download_file(), juste appliquee a
   l'echelle de la tentative entiere. Une verification de taille finale est
   faite avant d'accepter le resultat.
"""

import concurrent.futures
import os
import threading
import time
import urllib.request
import urllib.error

CHUNK_SIZE = 1024 * 256  # 256 Ko par lecture, bon compromis debit/reactivite
USER_AGENT = "AzerothUniverseLauncher/1.0 (+https://azeroth-universe.eu)"


class DownloadError(Exception):
    pass


class DownloadCancelled(Exception):
    pass


def get_remote_metadata(url, timeout=15):
    """Renvoie un dict {"content_length": int|None, "etag": str|None,
    "last_modified": str|None, "accept_ranges": bool} decrivant l'etat
    ACTUEL de la ressource cote serveur, sans en telecharger le contenu
    (HEAD, avec repli sur GET sans lire le corps si le serveur/CDN ne gere
    pas HEAD correctement - meme logique que l'ancien get_remote_size, dont
    ceci est desormais l'implementation sous-jacente).

    Sert a detecter qu'un fichier a ete REMPLACE sur GitHub sous LA MEME URL
    (un simple "upload qui ecrase" une release existante, sans changer ni le
    nom du fichier ni le tag - voir core/installer.py::is_entry_done() et le
    marqueur .done, qui comparent ces valeurs a celles enregistrees lors du
    dernier telechargement reussi). Azeroth Universe ne publie pas de sommes
    MD5/SHA256 officielles pour ses fichiers ; ETag et Last-Modified sont ce
    que le CDN GitHub (redirige vers Azure Blob Storage) fournit deja
    gratuitement et qui change de facon fiable des qu'un asset est ecrase -
    Content-Length seul ne suffit pas a lui tout seul (un remplacement peut,
    par coincidence, tomber exactement sur la meme taille).

    `accept_ranges` (ajoute septembre 2026) : indique si le serveur annonce
    explicitement le support des requetes par plage (en-tete
    "Accept-Ranges: bytes") - voir download_file_segmented() ci-dessous, qui
    n'essaie de decouper un telechargement en plusieurs connexions que si
    c'est le cas.
    """
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(
                url, method=method, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                length = r.headers.get("Content-Length")
                return {
                    "content_length": int(length) if length else None,
                    "etag": r.headers.get("ETag"),
                    "last_modified": r.headers.get("Last-Modified"),
                    "accept_ranges": (r.headers.get("Accept-Ranges") or "").strip().lower() == "bytes",
                }
        except (urllib.error.URLError, ValueError, OSError):
            continue
    return {"content_length": None, "etag": None, "last_modified": None, "accept_ranges": False}


def get_remote_size(url, session=None, timeout=15):
    """Renvoie la taille annoncee par le serveur (Content-Length), ou None
    si elle n'est pas connue a l'avance (dans ce cas la barre de progression
    du fichier repassera en mode indetermine).

    `session` est conserve dans la signature pour compatibilite (une
    ancienne version, basee sur `requests`, acceptait une session
    partagee) mais n'est plus utilise.

    Implemente desormais via get_remote_metadata() ci-dessus (memes deux
    tentatives HEAD puis GET) ; conserve comme fonction a part pour tous
    les appelants existants qui n'ont besoin que de la taille.
    """
    return get_remote_metadata(url, timeout=timeout)["content_length"]


def download_file(url, dest_path, progress_cb=None, cancel_event=None,
                   pause_event=None, session=None, max_retries=3):
    """Telecharge integralement `url` vers `dest_path`.

    progress_cb(downloaded_bytes, total_bytes_or_None) est appele a chaque
    chunk recu (pas plus souvent que toutes les ~0.1s pour eviter de saturer
    l'UI). cancel_event, si fourni, est verifie regulierement : si il est
    "set", DownloadCancelled est levee.

    pause_event, si fourni : quand il est "set", la lecture s'arrete ENTRE
    deux chunks (la connexion HTTP deja ouverte n'est PAS fermee, on ne lit
    juste plus dessus) jusqu'a ce qu'il soit efface ou que cancel_event
    soit leve. Contrairement a l'ancienne reprise par en-tete Range (voir
    la note en tete de fichier), il n'y a ICI aucune nouvelle requete
    emise a la reprise : on continue de lire le MEME flux reseau deja en
    cours, donc aucun risque de desalignement/corruption. Limite connue :
    si la pause dure trop longtemps, le serveur/CDN peut fermer la
    connexion de son cote par inactivite ; la prochaine lecture leve alors
    une erreur reseau normale, rattrapee plus bas comme n'importe quel
    accroc reseau (le fichier repart de zero au prochain essai). Une pause
    de quelques minutes ne pose pas de probleme ; une pause de plusieurs
    heures peut donc, dans le pire des cas, faire recommencer CE fichier.

    Volontairement AUCUNE reprise partielle (voir la note en tete de
    fichier) : chaque tentative telecharge le fichier depuis le debut. En
    cas d'echec reseau transitoire, on reessaie jusqu'a `max_retries` fois,
    en rejetant a chaque fois ce qui avait ete recu.

    `session` est conserve dans la signature pour compatibilite (voir
    get_remote_size) mais n'est plus utilise.
    """
    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    tmp_path = dest_path + ".part"

    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                content_length = resp.headers.get("Content-Length")
                total = int(content_length) if content_length else None

                downloaded = 0
                last_update = 0.0
                with open(tmp_path, "wb") as f:
                    while True:
                        if cancel_event is not None and cancel_event.is_set():
                            raise DownloadCancelled()
                        while pause_event is not None and pause_event.is_set():
                            if cancel_event is not None and cancel_event.is_set():
                                raise DownloadCancelled()
                            time.sleep(0.2)
                        chunk = resp.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        now = time.time()
                        if progress_cb and (now - last_update > 0.1):
                            progress_cb(downloaded, total)
                            last_update = now
                if progress_cb:
                    progress_cb(downloaded, total if total else downloaded)

            os.replace(tmp_path, dest_path)
            return dest_path

        except DownloadCancelled:
            raise
        except urllib.error.HTTPError as http_exc:
            # Statut HTTP franchement en erreur (404, 500...) : pas la peine
            # de reessayer, ce n'est pas un probleme reseau transitoire.
            raise DownloadError(f"HTTP {http_exc.code} pour {url}") from http_exc
        except (urllib.error.URLError, OSError) as exc:
            last_exc = exc
            # On rejette entierement ce qui a ete recu : la prochaine
            # tentative repart de zero (voir la note en tete de fichier).
            try:
                if os.path.isfile(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            time.sleep(min(2 * attempt, 6))
            continue

    raise DownloadError(f"Echec du telechargement de {url} apres {max_retries} tentatives : {last_exc}")


# Cadence maximale d'emission de la progression AGREGEE (voir
# download_file_segmented ci-dessous) : meme raisonnement que le
# PROGRESS_EMIT_INTERVAL de core/installer.py::_install_archive - avec
# plusieurs segments qui progressent en parallele, emettre a chaque chunk
# recu (sans throttle partage) donnerait un rythme irregulier a l'appelant
# et donc une vitesse affichee erratique cote UI.
SEGMENT_PROGRESS_EMIT_INTERVAL = 0.15


def download_file_segmented(url, dest_path, progress_cb=None, cancel_event=None,
                             pause_event=None, max_retries=3, segment_count=4,
                             min_total_size_for_split=4 * 1024 * 1024):
    """Comme download_file(), mais telecharge UN SEUL fichier en le
    decoupant en `segment_count` plages d'octets (en-tete HTTP Range),
    recuperees EN PARALLELE sur des connexions separees, avant de les
    reassembler. Voir le point 4) de la note en tete de ce module pour le
    contexte complet (pourquoi c'est necessaire, et pourquoi ce n'est PAS
    la reprise partielle interdite au point 2).

    Se rabat automatiquement sur download_file() (une seule connexion) si :
    la taille totale n'est pas connue a l'avance (impossible de decouper des
    plages sans savoir ou elles s'arretent), le serveur n'annonce pas
    explicitement le support des requetes partielles (en-tete
    "Accept-Ranges: bytes"), ou le fichier est trop petit pour que decouper
    en plusieurs connexions en vaille la peine (`min_total_size_for_split`,
    quelques Mo par defaut : en dessous, le cout de connexion supplementaire
    depasse le gain).

    Si UN SEUL segment echoue definitivement (apres l'ecoulement normal de
    sa lecture, HTTP en erreur, annulation...), TOUTE la tentative est
    rejetee (fichier .part supprime integralement) et la tentative suivante
    refait TOUS les segments depuis zero, jusqu'a `max_retries` fois - la
    meme politique "tout ou rien" que download_file(). Une fois tous les
    segments recus, la taille finale du fichier assemble est verifiee par
    rapport au Content-Length annonce avant d'accepter le resultat.
    """
    meta = get_remote_metadata(url)
    total = meta.get("content_length")
    can_split = (
        segment_count > 1
        and total is not None
        and total >= min_total_size_for_split
        and meta.get("accept_ranges")
    )
    if not can_split:
        return download_file(
            url, dest_path, progress_cb=progress_cb, cancel_event=cancel_event,
            pause_event=pause_event, max_retries=max_retries,
        )

    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    tmp_path = dest_path + ".part"

    # Plages d'octets DISJOINTES et CONTIGUES couvrant tout le fichier.
    ranges = []
    seg_size = total // segment_count
    start = 0
    for i in range(segment_count):
        end = (total - 1) if i == segment_count - 1 else (start + seg_size - 1)
        ranges.append((start, end))
        start = end + 1

    progress_lock = threading.Lock()
    seg_downloaded = [0] * segment_count
    emit_state = {"last_emit": 0.0}

    def report_progress(idx, received, force=False):
        if not progress_cb:
            return
        now = time.time()
        with progress_lock:
            seg_downloaded[idx] = received
            if not force and (now - emit_state["last_emit"]) < SEGMENT_PROGRESS_EMIT_INTERVAL:
                return
            emit_state["last_emit"] = now
            dl_sum = sum(seg_downloaded)
        progress_cb(dl_sum, total)

    def fetch_segment(idx, seg_start, seg_end):
        expected = seg_end - seg_start + 1
        req = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT, "Range": f"bytes={seg_start}-{seg_end}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status not in (200, 206):
                raise DownloadError(f"HTTP {resp.status} (segment) pour {url}")
            with open(tmp_path, "r+b") as f:
                f.seek(seg_start)
                received = 0
                while received < expected:
                    if cancel_event is not None and cancel_event.is_set():
                        raise DownloadCancelled()
                    while pause_event is not None and pause_event.is_set():
                        if cancel_event is not None and cancel_event.is_set():
                            raise DownloadCancelled()
                        time.sleep(0.2)
                    chunk = resp.read(min(CHUNK_SIZE, expected - received))
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)
                    report_progress(idx, received)
        if received != expected:
            raise DownloadError(
                f"Segment {idx} incomplet ({received}/{expected} octets) pour {url}")
        report_progress(idx, received, force=True)

    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            # Pre-dimensionne le fichier de destination temporaire a la
            # taille finale : chaque thread ecrit ensuite UNIQUEMENT dans SA
            # plage, via son propre descripteur de fichier ouvert en 'r+b' -
            # des plages disjointes, donc aucune ecriture concurrente au
            # meme endroit malgre plusieurs threads sur le meme fichier.
            with open(tmp_path, "wb") as f:
                f.truncate(total)
            for i in range(segment_count):
                seg_downloaded[i] = 0

            with concurrent.futures.ThreadPoolExecutor(max_workers=segment_count) as pool:
                futures = [pool.submit(fetch_segment, i, s, e) for i, (s, e) in enumerate(ranges)]
                seg_exc = None
                for future in concurrent.futures.as_completed(futures):
                    exc = future.exception()
                    if exc is not None and seg_exc is None:
                        seg_exc = exc
            if seg_exc is not None:
                raise seg_exc

            actual_size = os.path.getsize(tmp_path)
            if actual_size != total:
                raise DownloadError(
                    f"Taille finale incoherente ({actual_size}/{total} octets) pour {url}")

            if progress_cb:
                progress_cb(total, total)

            os.replace(tmp_path, dest_path)
            return dest_path

        except DownloadCancelled:
            try:
                if os.path.isfile(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            raise
        except urllib.error.HTTPError as http_exc:
            try:
                if os.path.isfile(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            raise DownloadError(f"HTTP {http_exc.code} pour {url}") from http_exc
        except (urllib.error.URLError, OSError, DownloadError) as exc:
            last_exc = exc
            # Meme politique "tout ou rien" que download_file() : on rejette
            # TOUT ce qui a ete recu (les segments deja termines compris),
            # la tentative suivante refait tous les segments depuis zero.
            try:
                if os.path.isfile(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            time.sleep(min(2 * attempt, 6))
            continue

    raise DownloadError(
        f"Echec du telechargement segmente de {url} apres {max_retries} tentatives : {last_exc}")


def download_files_parallel(jobs, cancel_event=None, pause_event=None, max_workers=4,
                             max_retries=3, total_connection_budget=6):
    """Telecharge plusieurs fichiers INDEPENDANTS en parallele, chacun sur sa
    propre connexion HTTP AU MINIMUM (plusieurs threads, chacun appelant
    download_file_segmented() - voir plus haut - qui peut lui-meme ouvrir
    PLUSIEURS connexions pour UN SEUL job si le fichier s'y prete : memes
    garanties que d'habitude, aucune reprise partielle, retentatives
    completes en cas d'erreur reseau transitoire, voir la note en tete de ce
    module, points 2 a 4).

    Pourquoi : une seule connexion HTTP, meme vers un serveur/CDN rapide
    (ex: les releases GitHub), plafonne souvent bien en dessous du debit
    reellement disponible sur la ligne (fenetre TCP/latence, throttling par
    connexion cote serveur...). Ouvrir plusieurs connexions simultanees vers
    le meme hote - exactement ce que fait un navigateur ou un gestionnaire
    de telechargement - permet generalement d'approcher le debit reel.

    `jobs` : liste de dicts {"url": ..., "dest_path": ..., "progress_cb": ...
    (optionnel), "segment_count": ... (optionnel, remplace le calcul
    automatique ci-dessous pour CE job)}.

    `total_connection_budget` (defaut 6) : nombre TOTAL de connexions visees
    pour l'ensemble de l'appel, quelle que soit la repartition entre nombre
    de jobs et segmentation par job - ex: 1 seul job (fichier "direct" ou
    archive a une seule "part") -> jusqu'a 6 segments pour CE job ; 2 jobs
    (ex: frFR en 2 "parts") -> jusqu'a 3 segments chacun ; 6 jobs (ex:
    patch-Y.MPQ en 6 "parts") -> 1 segment chacun (le nombre de parts suffit
    deja). Evite d'ouvrir un nombre de connexions demesure quand plusieurs
    niveaux de parallelisme (jobs x segments) se combinent.

    `cancel_event`/`pause_event`, s'ils sont fournis, sont partages entre
    tous les threads (les objets threading.Event sont deja thread-safe) :
    annuler (ex: bouton "Annuler" de l'installateur) arrete donc bien TOUS
    les telechargements en cours, pas seulement un seul comme avant.

    IMPORTANT : contrairement a une annulation utilisateur, l'echec
    DEFINITIF d'UN SEUL job (reseau, HTTP 404...) ne force PAS l'arret
    anticipe des autres jobs encore en cours - on laisse volontairement les
    telechargements deja en vol se terminer naturellement (succes ou echec
    independant) plutot que de "signaler" cet echec aux autres threads. Ce
    choix est deliberer : le seul mecanisme d'arret partage disponible ici
    est justement `cancel_event`, qui est le MEME objet que celui utilise
    ailleurs pour detecter une annulation VOULUE PAR L'UTILISATEUR (voir
    InstallWorker dans core/installer.py) - le declencher nous-memes suite a
    une simple erreur reseau ferait passer, plus haut dans la pile, un echec
    de telechargement pour une annulation utilisateur (mauvais message
    affiche : "Annule" au lieu du vrai message d'erreur). Une fois que TOUS
    les jobs sont termines, la premiere exception rencontree (s'il y en a
    une) est propagee a l'appelant - meme resultat final qu'un enchainement
    sequentiel de download_file() (l'entree entiere est consideree en echec
    des qu'une seule de ses parties l'est), juste potentiellement quelques
    octets de reseau "gaspilles" sur les parties encore en vol au moment de
    l'echec - un compromis largement acceptable pour la simplicite et la
    correction du signal d'annulation.
    """
    if not jobs:
        return

    workers = max(1, min(max_workers, len(jobs)))
    default_segment_count = max(1, total_connection_budget // len(jobs))

    def _run(job):
        download_file_segmented(
            job["url"], job["dest_path"],
            progress_cb=job.get("progress_cb"),
            cancel_event=cancel_event, pause_event=pause_event,
            max_retries=max_retries,
            segment_count=job.get("segment_count", default_segment_count),
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_run, job) for job in jobs]
        first_exc = None
        for future in concurrent.futures.as_completed(futures):
            exc = future.exception()
            if exc is not None and first_exc is None:
                first_exc = exc
        if first_exc is not None:
            raise first_exc


def human_size(num_bytes, lang="fr"):
    if num_bytes is None:
        return "?"
    units = ["o", "Ko", "Mo", "Go", "To", "Po"] if lang != "en" else ["B", "KB", "MB", "GB", "TB", "PB"]
    step = 1024.0
    for unit in units[:-1]:
        if abs(num_bytes) < step:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= step
    return f"{num_bytes:.1f} {units[-1]}"
