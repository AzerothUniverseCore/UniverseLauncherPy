# Azeroth Universe - Launcher

Launcher officiel du client de jeu **Azeroth Universe** (serveur privé
WotLK 3.3.5a personnalisé). Télécharge, installe et met à jour
automatiquement le client depuis les releases GitHub du dépôt
[UniverseClient](https://github.com/AzerothUniverseCore/UniverseClient),
puis lance le jeu.

## Fonctionnalités

- Design sombre original façon "Midnight" (bleu nuit/noir + liserés dorés),
  fenêtre sans décoration système avec barre de titre maison - entièrement
  dessiné par code, aucun asset Blizzard utilisé.
- Interface bilingue Français / English (boutons FR/EN dans la barre de
  titre), changeable à tout moment.
- Le changement de langue FR/EN met aussi à jour la langue réelle du client
  (`WTF/Arealm.wtf`, ligne `SET locale "frFR"`/`"enUS"`), pas seulement celle
  du launcher.
- Téléchargement et installation automatique des ~30 fichiers du client
  (fichiers `.MPQ` directs + archives `.rar` multi-parties pour les patchs
  et les paquets de langue frFR/enUS), avec reprise en cas de coupure.
- Placement automatique au bon endroit : patchs dans `Data/`, langues dans
  `Data/frFR/` et `Data/enUS/`, contenu additionnel à la racine du client.
- Case "Vérification approfondie" : recontrôle la taille des `.MPQ` déjà
  téléchargés par rapport au serveur (une vraie vérification MD5 n'est pas
  possible tant qu'Azeroth Universe ne publie pas de sommes de contrôle
  officielles - voir `core/installer.py`).
- Bouton d'action unique qui change de libellé selon l'état : **Vérifier**
  → **Installer** → **Jouer**.
- Panneau "Actualités" (contenu statique éditable dans `i18n.py`,
  `NEWS_ITEMS`) et badge de statut serveur (voir limitation ci-dessous).

## Structure du projet

```
AzerothUniverseLauncher/
├── main.py                  # point d'entree de l'application
├── config.py                 # chemins, constantes, sauvegarde des reglages
├── i18n.py                   # textes FR/EN
├── generate_manifest.py      # genere manifest.json (liste des fichiers a telecharger)
├── generate_assets.py        # genere les images originales du launcher
├── manifest.json              # liste des fichiers du client (genere)
├── requirements.txt
├── core/
│   ├── downloader.py          # telechargement HTTP avec reprise
│   ├── extractor.py           # extraction .rar via UnRAR.exe portable
│   ├── installer.py           # orchestration complete (QThread)
│   ├── wtf.py                  # ecrit SET locale dans WTF/Arealm.wtf
│   └── server_status.py        # badge "serveur en ligne" (optionnel)
├── ui/
│   ├── theme.py                # feuille de style (QSS)
│   └── main_window.py          # fenetre principale (barre de titre maison)
├── assets/                    # logo, fond d'ecran, icone (generes)
├── tools/                      # UnRAR.exe a ajouter manuellement (voir dedans)
└── build/
    ├── launcher.spec            # spec PyInstaller
    └── BUILD_INSTRUCTIONS.md    # procedure de compilation Windows
```

## Lancer en développement (Linux/Windows/macOS)

```bash
python3 -m venv venv
source venv/bin/activate   # ou venv\Scripts\activate sous Windows
pip install -r requirements.txt
python3 main.py
```

Sous Linux/macOS, l'extraction utilisera `unrar` du système s'il est
installé (`apt install unrar` sur Debian/Ubuntu, ou `unrar-free` selon les
dépôts) puisque `tools/UnRAR.exe` est un binaire Windows.

## Compiler l'exécutable Windows final

Voir [`build/BUILD_INSTRUCTIONS.md`](build/BUILD_INSTRUCTIONS.md) - à faire
directement sur une machine Windows.

## Mettre à jour la liste des fichiers du client

Si de nouveaux patchs sont publiés sur UniverseClient, éditez les listes en
haut de `generate_manifest.py` (`MULTI_PART_MPQ`, `LOCALES`,
`SINGLE_MPQ_FILES`) puis relancez :

```bash
python3 generate_manifest.py
```

## ⚠️ À vérifier avant distribution

- Les URLs des 13 fichiers `.MPQ` livrés en une seule partie ont été déduites
  par convention (même schéma que les archives multi-parties) et n'ont pas pu
  être vérifiées avec un accès réseau direct à GitHub au moment du
  développement. Testez le téléchargement d'au moins 2-3 d'entre eux avant de
  distribuer le launcher à la communauté (détails dans
  `build/BUILD_INSTRUCTIONS.md`).
- Les boutons **Site web** et **S'inscrire** de la barre du bas pointent
  tous les deux vers `https://azeroth-universe.eu/en` par défaut
  (`config.WEBSITE_URL` / `config.REGISTER_URL`) : aucune page d'inscription
  dédiée ne nous avait été communiquée. Mettez à jour `REGISTER_URL` dans
  `config.py` si vous avez une page de création de compte séparée.
- Le badge "Serveur en ligne" en haut à droite affiche **"Statut non
  configuré"** tant que `config.STATUS_URL` reste à `None` : aucune API de
  statut réelle ne nous a été fournie, donc le launcher n'invente pas de
  nombre de joueurs connectés. Si vous avez (ou mettez en place) un
  endpoint JSON `{"online": true, "players": 12}`, renseignez son URL dans
  `config.py` pour activer le badge en direct (voir
  `core/server_status.py`). Un exemple prêt à l'emploi (PHP + MySQL en
  lecture seule) est fourni dans
  [`build/server_status_api/`](build/server_status_api/README.md) - à
  héberger sur votre site, pas dans le launcher.
- La fenêtre n'a plus de bordure système (barre de titre "maison", comme
  sur la maquette) : elle est donc de taille fixe et se déplace en glissant
  la barre du haut. Si vous préférez une fenêtre redimensionnable avec la
  décoration standard de Windows, il faudra retirer `Qt.FramelessWindowHint`
  dans `ui/main_window.py` (`AzerothLauncherWindow.__init__`).
