# Compiler AzerothUniverseLauncher.exe (Windows)

Ce launcher est fourni en code source Python. Il doit être compilé en `.exe`
directement sur une machine **Windows** : le code a été écrit et testé dans
un environnement Linux qui ne peut pas produire un exécutable Windows natif
fiable (la compilation croisée PyInstaller Linux → Windows n'est pas
supportée officiellement).

La bonne nouvelle : la compilation elle-même prend moins de 10 minutes et ne
demande aucune compétence en développement, juste de suivre les étapes.

## Pré-requis

- Windows 10/11 (64 bits)
- [Python 3.11 ou 3.12](https://www.python.org/downloads/windows/) installé
  (cochez bien **"Add python.exe to PATH"** pendant l'installation)
- Une connexion internet (pour installer les dépendances et télécharger 7-Zip)

## Étape 1 - Récupérer les sources

Copiez tout le dossier `AzerothUniverseLauncher/` sur la machine Windows
(clé USB, Google Drive, `git clone` du dépôt... peu importe le moyen).

## Étape 2 - Installer les dépendances Python

Ouvrez une invite de commandes (`cmd` ou PowerShell) **dans le dossier**
`AzerothUniverseLauncher/`, puis :

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Étape 3 - Ajouter UnRAR.exe (obligatoire)

Le launcher a besoin d'un petit outil (`UnRAR.exe`) pour extraire les
archives `.rar` des patchs. Il n'est pas inclus dans les sources (voir le
fichier `tools/PLACEZ_UnRAR.exe_ICI.txt` pour le détail) :

1. Allez sur <https://www.win-rar.com/download.html> (site officiel WinRAR)
2. Récupérez **UnRAR.exe** (gratuit, ~250 Ko, sans limite d'essai - c'est
   différent de WinRAR complet) - ou copiez-le depuis une installation
   WinRAR déjà présente sur votre machine (`C:\Program Files\WinRAR\UnRAR.exe`)
3. Placez-le dans `AzerothUniverseLauncher/tools/UnRAR.exe`

⚠️ Ne prenez pas `7za.exe`/7-Zip pour cette étape : la version portable de
7-Zip ne peut pas lire les fichiers `.rar` (le support RAR de 7-Zip
nécessite un plugin non fourni dans la version console/portable - voir le
commentaire en tête de `core/extractor.py` pour l'historique complet).

## Étape 4 - Générer les images du launcher (si besoin)

Les fichiers `assets/logo.png`, `assets/background.png` et `assets/icon.ico`
sont déjà fournis avec les sources. Si vous voulez les régénérer ou les
personnaliser, modifiez `generate_assets.py` puis relancez :

```bat
python generate_assets.py
```

## Étape 5 - Compiler l'exécutable

Toujours dans le même dossier, avec le venv activé :

```bat
pyinstaller build\launcher.spec
```

PyInstaller crée un dossier `dist/`. L'exécutable final se trouve à :

```
dist\AzerothUniverseLauncher.exe
```

C'est ce fichier unique que vous distribuez aux joueurs - il embarque déjà
Python, PySide6, `manifest.json`, les images et `UnRAR.exe`. Les joueurs
n'ont rien d'autre à installer.

## Étape 6 - Tester avant de distribuer

Avant d'envoyer le launcher à la communauté :

1. Lancez `dist\AzerothUniverseLauncher.exe` sur une machine "propre" (sans
   Python installé) pour vérifier qu'il démarre bien tout seul.
2. Lancez une installation complète et vérifiez qu'au moins un fichier de
   chaque catégorie s'installe correctement :
   - un `.MPQ` en téléchargement direct (ex: `common.MPQ`)
   - un patch multi-parties (ex: `patch-4.MPQ`, seulement 3 parties)
   - le pack `AzerothUniverse` (doit finir à la racine du dossier client,
     à côté de `Data/`, pas dedans)
3. Vérifiez que `Data/enUS/realmlist.wtf` et `Data/frFR/realmlist.wtf`
   contiennent bien l'adresse de connexion saisie dans le launcher.
4. Vérifiez que le bouton **Jouer** lance bien `Wow.exe`.

⚠️ **Important** : les URLs de téléchargement des 13 fichiers `.MPQ` livrés
en un seul morceau (`common.MPQ`, `expansion.MPQ`, `lichking.MPQ`, etc.) ont
été déduites par convention à partir des URLs des archives multi-parties
que vous avez fournies, et n'ont pas pu être vérifiées automatiquement
(pas d'accès réseau sortant vers GitHub depuis l'environnement où ce
launcher a été développé). Testez le téléchargement d'au moins 2-3 de ces
fichiers avant de distribuer largement le launcher. Si une URL est
incorrecte, il suffit de corriger le champ `"url"` correspondant dans
`manifest.json` (pas besoin de recompiler tout le launcher pour ça - juste
remettre à jour ce fichier à côté de l'exe, ou re-belon avec PyInstaller).

## Mettre à jour le launcher plus tard

- **Changer/ajouter un fichier du client** (nouveau patch, nouvelle version) :
  modifiez `generate_manifest.py`, relancez-le (`python generate_manifest.py`),
  puis recompilez avec `pyinstaller build\launcher.spec`.
- **Changer juste une URL cassée** : éditez directement `manifest.json` puis
  recompilez (ou distribuez ce fichier à part si vous préférez charger le
  manifeste depuis un fichier externe - non fait par défaut ici, le
  manifeste est embarqué dans l'exe pour simplifier la distribution).
