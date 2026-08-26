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
"""

import os
import time
import urllib.request
import urllib.error

CHUNK_SIZE = 1024 * 256  # 256 Ko par lecture, bon compromis debit/reactivite
USER_AGENT = "AzerothUniverseLauncher/1.0 (+https://azeroth-universe.eu)"


class DownloadError(Exception):
    pass


class DownloadCancelled(Exception):
    pass


def get_remote_size(url, session=None, timeout=15):
    """Renvoie la taille annoncee par le serveur (Content-Length), ou None
    si elle n'est pas connue a l'avance (dans ce cas la barre de progression
    du fichier repassera en mode indetermine).

    `session` est conserve dans la signature pour compatibilite (une
    ancienne version, basee sur `requests`, acceptait une session
    partagee) mais n'est plus utilise.

    Essaie HEAD en premier (leger, une seule requete), puis se rabat sur
    GET si le serveur/CDN ne supporte pas HEAD correctement (le corps de
    la reponse n'est alors pas lu, seule l'en-tete nous interesse).
    """
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(
                url, method=method, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                length = r.headers.get("Content-Length")
                if length:
                    return int(length)
        except (urllib.error.URLError, ValueError, OSError):
            continue
    return None


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
