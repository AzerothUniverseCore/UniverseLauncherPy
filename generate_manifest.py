"""
generate_manifest.py
---------------------
Genere manifest.json a partir de la liste des fichiers du client UniverseClient
(https://github.com/AzerothUniverseCore/UniverseClient/releases).

Pourquoi un generateur plutot que taper les ~100 URLs a la main : avec 16 archives
multi-parties (jusqu'a 15 parties pour patch-C.MPQ), une seule faute de frappe dans
une URL provoquerait un echec de telechargement silencieux pour un joueur. On
construit donc les URLs a partir d'une regle unique et verifiable, a partir des
infos donnees pour chaque fichier (tag GitHub + nombre de parties).

IMPORTANT (a lire avant de distribuer le launcher) :
Les URLs des fichiers MULTI-PARTIES ci-dessous sont recopiees telles quelles
depuis les liens fournis (verifiees). Les URLs des fichiers EN UNE SEULE PARTIE
(colonne SINGLE_MPQ_FILES) sont, elles, DEDUITES par convention (tag GitHub =
nom de fichier = nom de l'asset), le meme schema que celui utilise pour TOUTES
les archives multi-parties de ce meme depot. Cette convention n'a pas pu etre
verifiee directement (le bac a sable qui a genere ce script n'a pas d'acces
reseau sortant vers github.com en dehors du protocole "git clone"), donc
merci de tester le telechargement d'au moins 2-3 fichiers "single" avant de
distribuer le launcher a la communaute. Si un lien echoue, corrigez juste son
"url" dans manifest.json (pas besoin de repasser par ce script).
"""

import json

REPO = "AzerothUniverseCore/UniverseClient"
BASE = f"https://github.com/{REPO}/releases/download"


def part_suffix(index, total):
    """WinRAR/7-Zip: si le volume total est >= 10 parties, les numeros sont
    ecrits sur 2 chiffres (part01, part02, ..., part10, ...). Sinon 1 chiffre
    (part1, part2, ...). Regle deduite des URLs fournies : patch-B/C/D (>=10
    parties) utilisent "part01", tous les autres (< 10 parties) utilisent
    "part1"."""
    width = 2 if total >= 10 else 1
    return f"part{str(index).zfill(width)}"


def multi_part_urls(tag, total, ext="rar"):
    # IMPORTANT : le nom de l'asset (fichier .rar) n'est PAS forcement identique
    # au tag de la release. Pour les patchs, le tag est "patch-X.MPQ" mais les
    # parties .rar sont nommees "patch-X.partN.rar" (le ".MPQ" est retire).
    # Verifie sur les URLs fournies, ex: tag "patch-Y.MPQ" -> asset "patch-Y.part1.rar".
    # Pour frFR/enUS/AzerothUniverse (pas de suffixe .MPQ dans le tag), le nom de
    # base reste identique au tag.
    basename = tag[:-4] if tag.endswith(".MPQ") else tag
    return [f"{BASE}/{tag}/{basename}.{part_suffix(i, total)}.{ext}" for i in range(1, total + 1)]


# (tag_github, nombre_de_parties) pour chaque patch MPQ livre en plusieurs .rar
MULTI_PART_MPQ = [
    ("patch-Y.MPQ", 6),
    ("patch-K.MPQ", 3),
    ("patch-F.MPQ", 5),
    ("patch-E.MPQ", 5),
    ("patch-D.MPQ", 14),
    ("patch-C.MPQ", 15),
    ("patch-B.MPQ", 12),
    ("patch-A.MPQ", 4),
    ("patch-9.MPQ", 4),
    ("patch-8.MPQ", 5),
    ("patch-7.MPQ", 7),
    ("patch-6.MPQ", 6),
    ("patch-5.MPQ", 7),
    ("patch-4.MPQ", 3),
]

# Locales, livrees en 2 parties chacune, extraites dans Data/<locale>/
LOCALES = [
    ("frFR", 2),
    ("enUS", 2),
]

# Fichiers .MPQ livres en une seule partie (pas de .rar) : telecharges tels quels.
# D'apres la capture du dossier Data, ce sont tous les fichiers qui n'ont pas ete
# cites comme multi-parties.
SINGLE_MPQ_FILES = [
    "common.MPQ",
    "common-2.MPQ",
    "expansion.MPQ",
    "lichking.MPQ",
    "patch.MPQ",
    "patch-2.MPQ",
    "patch-3.MPQ",
    "patch-I.MPQ",
    "patch-N.MPQ",
    "patch-T.MPQ",
    "patch-U.MPQ",
    "patch-Z.MPQ",
    "patch-ZA.MPQ",
]

manifest = {
    "repo": REPO,
    "client_folder_name": "AzerothUniverse",
    "files": [],
}

# --- Locales -> Data/<locale>/ ---
for tag, total in LOCALES:
    manifest["files"].append({
        "id": tag,
        "kind": "archive",
        "display_name": tag,
        "extract_to": f"Data/{tag}",
        "flatten_single_subfolder": tag,
        "parts": multi_part_urls(tag, total),
    })

# --- Patchs multi-parties -> Data/ (l'archive contient directement le .MPQ) ---
for tag, total in MULTI_PART_MPQ:
    manifest["files"].append({
        "id": tag,
        "kind": "archive",
        "display_name": tag,
        "extract_to": "Data",
        "flatten_single_subfolder": None,
        "parts": multi_part_urls(tag, total),
    })

# --- Patchs/fichiers en une seule partie -> Data/ (telechargement direct, pas d'extraction) ---
for filename in SINGLE_MPQ_FILES:
    manifest["files"].append({
        "id": filename,
        "kind": "direct",
        "display_name": filename,
        "target": f"Data/{filename}",
        "url": f"{BASE}/{filename}/{filename}",
    })

# --- Contenu additionnel Azeroth Universe -> racine du client (a cote de Data/) ---
manifest["files"].append({
    "id": "AzerothUniverse",
    "kind": "archive",
    "display_name": "AzerothUniverse (Additional)",
    "extract_to": ".",
    "flatten_single_subfolder": "AzerothUniverse",
    "parts": [f"{BASE}/AzerothUniverse/AzerothUniverse.rar"],
})

with open("manifest.json", "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

print(f"manifest.json genere avec {len(manifest['files'])} entrees.")
archive_count = sum(1 for e in manifest["files"] if e["kind"] == "archive")
direct_count = sum(1 for e in manifest["files"] if e["kind"] == "direct")
total_parts = sum(len(e["parts"]) for e in manifest["files"] if e["kind"] == "archive")
print(f" - {archive_count} archives (.rar) totalisant {total_parts} parties a telecharger")
print(f" - {direct_count} fichiers telecharges directement (.MPQ)")
