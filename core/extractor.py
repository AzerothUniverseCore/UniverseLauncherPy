"""
core/extractor.py
------------------
Extraction des archives .rar (simples et multi-parties) via un binaire
UnRAR.exe portable embarque (tools/UnRAR.exe sous Windows), pour que les
joueurs n'aient rien a installer eux-memes.

HISTORIQUE IMPORTANT (aout 2026) - a lire avant de retoucher ce fichier :

Ce module utilisait au depart 7-Zip (7za.exe) pour extraire les archives
RAR. Deux problemes distincts, empiles l'un sur l'autre, ont ete
diagnostiques :

1) Un vrai 7zr.exe ("7-Zip (r)", version REDUITE) avait ete place par
   erreur dans tools/7za.exe. 7zr.exe ne gere que le format natif .7z et
   echoue TOUJOURS sur un .rar avec "Cannot open the file as archive".
   Corrige une premiere fois en detectant ce cas et en demandant le vrai
   7za.exe du paquet "7-Zip Extra".

2) Mais meme apres avoir place le VRAI 7za.exe (banner confirme "7-Zip
   (a) 26.02 (x64)", DLL compagnes correctes), `7za.exe i` (liste des
   formats geres) ne montre AUCUNE entree Rar/Rar5. Ce n'est pas un bug
   ni une mauvaise version : confirme par la documentation de 7-Zip et
   par Igor Pavlov (auteur de 7-Zip) lui-meme sur le forum officiel, le
   binaire autonome "7za.exe" du paquet "7-Zip Extra" ne PEUT PAS lire
   les RAR, quelle que soit sa version. La lecture des RAR par 7-Zip
   passe par un plugin non-libre ("rar plugin") qui n'est fourni QUE dans
   l'installateur complet de 7-Zip (celui qui s'installe dans
   C:\\Program Files\\7-Zip\\), jamais dans le paquet console/portable
   "Extra". Autrement dit : il n'existe pas de version portable de
   7za.exe capable d'ouvrir un .rar - ce n'est pas un probleme a
   contourner en changeant de version, c'est une limitation permanente
   de cet outil.

=> Solution retenue : ne plus utiliser 7-Zip du tout pour les RAR, et
   passer par UnRAR.exe (l'outil console officiel de WinRAR, gratuit en
   extraction meme sans licence WinRAR), exactement comme le fait le
   script de secours ("azeroth_launcher_emergency.py") qui, lui,
   fonctionnait de façon fiable. UnRAR.exe est un tout petit executable
   (~250 Ko) redistribuable librement pour de l'extraction, disponible
   sur le site officiel de WinRAR ou a l'interieur de toute installation
   de WinRAR (fichier Unrar.exe dans C:\\Program Files\\WinRAR\\).
"""

import os
import sys
import shutil
import subprocess


class ExtractionError(Exception):
    pass


class UnrarNotFound(Exception):
    pass


def find_unrar():
    """Cherche le binaire UnRAR a utiliser, dans cet ordre :
    1. tools/UnRAR.exe (ou variantes de casse) a cote de l'executable/du
       script - portable, fourni avec le launcher, c'est le cas normal
       pour un utilisateur final Windows.
    2. Une installation existante de WinRAR sur la machine
       (C:\\Program Files\\WinRAR\\ ou (x86)\\), qui fournit toujours
       Unrar.exe et/ou Rar.exe en plus du programme principal.
    3. unrar/rar present dans le PATH systeme (pratique en developpement
       sous Linux/macOS ou p7zip/unrar-free est deja installe, ou pour un
       utilisateur qui aurait deja rendu l'outil accessible globalement).
    """
    import config

    names = ("UnRAR.exe", "unrar.exe", "Unrar.exe", "Rar.exe", "rar.exe")
    search_dirs = [
        os.path.join(config.BASE_DIR, "tools"),
        os.path.join(config.APP_DIR, "tools"),
    ]
    for d in search_dirs:
        for name in names:
            path = os.path.join(d, name)
            if os.path.isfile(path):
                return path

    program_files_dirs = []
    for env_var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        base = os.environ.get(env_var)
        if base:
            program_files_dirs.append(os.path.join(base, "WinRAR"))
    for d in program_files_dirs:
        for name in ("UnRAR.exe", "Unrar.exe", "Rar.exe"):
            path = os.path.join(d, name)
            if os.path.isfile(path):
                return path

    for name in ("unrar", "unrar.exe", "rar", "rar.exe"):
        found = shutil.which(name)
        if found:
            return found

    raise UnrarNotFound(
        "UnRAR.exe introuvable (ni dans tools/, ni dans une installation "
        "WinRAR locale, ni dans le PATH systeme). Telechargez UnRAR.exe "
        "(gratuit) depuis le site officiel de WinRAR (www.win-rar.com, "
        "section \"UnRAR\"), ou copiez Unrar.exe depuis un dossier WinRAR "
        "deja installe, et placez-le dans le dossier tools/ du launcher."
    )


def _run_unrar(args, cwd=None):
    unrar = find_unrar()
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW
    try:
        proc = subprocess.run(
            [unrar] + args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
    except OSError as exc:
        if getattr(exc, "winerror", None) == 740:
            raise ExtractionError(
                "Le fichier tools/UnRAR.exe necessite les droits "
                "administrateur pour s'executer : ce n'est probablement "
                "pas le bon fichier (Rar.exe/WinRAR.exe complet au lieu "
                "de l'outil console UnRAR.exe/Unrar.exe)."
            ) from exc
        raise
    output = proc.stdout.decode("utf-8", errors="replace") if proc.stdout else ""
    # Codes de sortie UnRAR : 0 = OK, 1 = avertissement non bloquant (warning),
    # tout le reste (2+) est une vraie erreur (archive corrompue, mot de passe
    # manquant, disque plein...). Voir la doc officielle UnRAR "Exit codes".
    if proc.returncode not in (0, 1):
        raise ExtractionError(
            f"UnRAR a echoue (code {proc.returncode}) sur {args}:\n{output}"
        )
    return output


def extract_archive(first_part_path, dest_dir):
    """Extrait `first_part_path` (chemin de la premiere partie, ou de
    l'archive si elle n'a qu'une seule partie) dans `dest_dir`. Les autres
    parties doivent etre dans le meme dossier que `first_part_path`, nommees
    selon la convention WinRAR/7-Zip (.part1.rar, .part2.rar, ... ou
    .part01.rar, ...). UnRAR les detecte automatiquement a partir de la
    premiere partie.
    """
    os.makedirs(dest_dir, exist_ok=True)
    # x     : extrait en conservant les chemins/dossiers internes a l'archive
    # -y    : repond "oui" a toutes les questions (ecrasement, etc.)
    # -o+   : autorise l'ecrasement des fichiers existants sans demander
    # Le dossier de destination doit se terminer par un separateur pour
    # qu'UnRAR le reconnaisse bien comme dossier cible (syntaxe UnRAR).
    dest_arg = dest_dir if dest_dir.endswith(os.sep) else dest_dir + os.sep
    _run_unrar(["x", "-y", "-o+", first_part_path, dest_arg])


def _is_junk(name):
    return name.lower() in (".ds_store", "thumbs.db", "desktop.ini")


def flatten_single_subfolder(dest_dir, expected_name=None):
    """Logique defensive de "mise a plat" : certaines archives peuvent
    contenir directement les fichiers, d'autres peuvent les envelopper dans
    UN dossier (par ex. un dossier "frFR/" a l'interieur de l'archive
    "frFR.part1.rar" deja extraite dans Data/frFR/, ce qui donnerait
    Data/frFR/frFR/... au lieu de Data/frFR/...). Comme on n'a pas pu
    verifier la structure interne exacte de chaque archive a l'avance, on
    detecte ce cas et on remonte le contenu d'un niveau automatiquement.

    Regle : si `dest_dir` ne contient QU'UN SEUL element et que c'est un
    dossier (peu importe son nom si `expected_name` n'est pas precise, ou
    en priorite si son nom correspond a `expected_name`), on deplace tout
    son contenu dans `dest_dir` et on supprime le dossier vide.
    """
    entries = [e for e in os.listdir(dest_dir) if not _is_junk(e)]
    if len(entries) != 1:
        return  # deja "a plat" (plusieurs fichiers/dossiers) : rien a faire

    only = entries[0]
    only_path = os.path.join(dest_dir, only)
    if not os.path.isdir(only_path):
        return  # un seul fichier direct : rien a aplatir

    if expected_name is not None and only.lower() != expected_name.lower():
        # Le seul dossier trouve ne correspond pas au nom attendu : on
        # prefere ne rien casser plutot que de deplacer un dossier inconnu.
        return

    for item in os.listdir(only_path):
        src = os.path.join(only_path, item)
        dst = os.path.join(dest_dir, item)
        if os.path.exists(dst):
            if os.path.isdir(dst) and os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
                continue
            os.remove(dst) if os.path.isfile(dst) else shutil.rmtree(dst)
        shutil.move(src, dst)

    shutil.rmtree(only_path, ignore_errors=True)


def move_merge(src_dir, dest_dir):
    """Deplace tout le contenu de `src_dir` dans `dest_dir`, en fusionnant
    les dossiers deja existants et en ecrasant les fichiers deja existants
    (utilise pour poser le contenu (deja aplati) d'une archive fraichement
    extraite sur le dossier final du client, qui contient deja d'autres
    fichiers provenant d'autres archives/telechargements)."""
    os.makedirs(dest_dir, exist_ok=True)
    for item in os.listdir(src_dir):
        src = os.path.join(src_dir, item)
        dst = os.path.join(dest_dir, item)
        if os.path.isdir(src):
            if os.path.isdir(dst):
                move_merge(src, dst)
            else:
                shutil.move(src, dst)
        else:
            if os.path.exists(dst):
                os.remove(dst)
            shutil.move(src, dst)


def cleanup_parts(part_paths):
    for p in part_paths:
        try:
            if os.path.isfile(p):
                os.remove(p)
        except OSError:
            pass
