"""
core/wtf.py
-----------
Ecrit/maintient la ligne `SET locale "frFR"` / `SET locale "enUS"` dans le
fichier <dossier client>/WTF/Arealm.wtf, pour que le client WoW demarre
directement dans la langue choisie dans le launcher (comportement demande :
le bouton FR/EN du launcher doit aussi changer la langue reelle du jeu, pas
seulement celle de l'interface du launcher).

Le fichier WTF/Arealm.wtf est un fichier de configuration texte du client
WoW (une ligne `SET cle "valeur"` par parametre). S'il existe deja (client
deja lance au moins une fois, ou copie depuis une autre installation), on
modifie UNIQUEMENT la ligne `SET locale ...` et on laisse toutes les autres
lignes (compte, mot de passe sauvegarde, resolution, options graphiques...)
strictement intactes. S'il n'existe pas encore (client fraichement
installe, jamais lance), on cree le dossier WTF/ et un fichier minimal ne
contenant que cette ligne : le client completera lui-meme le reste au
premier lancement.
"""

import os
import re

LOCALE_LINE_RE = re.compile(r'^\s*SET\s+locale\s+"[^"]*"\s*$', re.IGNORECASE)


def wtf_path(install_dir):
    return os.path.join(install_dir, "WTF", "Arealm.wtf")


def update_wtf_locale(install_dir, locale_value):
    """Met a jour (ou cree) WTF/Arealm.wtf pour que `SET locale` vaille
    `locale_value` (ex: "frFR" ou "enUS"). Ne fait rien si `install_dir`
    n'existe pas encore (rien a mettre a jour avant l'installation).
    Renvoie True si le fichier a ete cree/modifie, False sinon.
    """
    if not install_dir or not os.path.isdir(install_dir):
        return False

    path = wtf_path(install_dir)
    new_line = f'SET locale "{locale_value}"'

    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()

        found = False
        for i, line in enumerate(lines):
            if LOCALE_LINE_RE.match(line):
                lines[i] = new_line
                found = True
                break
        if not found:
            lines.insert(0, new_line)

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    else:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_line + "\n")

    return True
