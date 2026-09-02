"""
i18n.py
-------
Textes de l'interface en francais et anglais. Pas de dependance externe
(pas de fichiers .ts/.qm Qt Linguist) pour rester simple a maintenir : un
simple dictionnaire par langue, une fonction t(key) qui renvoie le texte
dans la langue courante.
"""

LANGUAGES = {
    "fr": "Français",
    "en": "English",
}

STRINGS = {
    "fr": {
        "app_title": "Azeroth Universe - Launcher",
        "titlebar_title": "AZEROTH UNIVERSE LAUNCHER",
        "hero_title": "AZEROTH UNIVERSE",
        "tagline": "Choisissez votre faction et préparez-vous à une aventure épique !",
        "news_header": "Actualités",
        "client_folder_header": "Dossier client",
        "journal_header": "Journal",
        "deep_verify_checkbox": "Vérification approfondie (MD5)",
        "deep_verify_tooltip": (
            "Recontrôle en plus la taille annoncée par le serveur pour les "
            "fichiers .MPQ déjà téléchargés (une vérification MD5 complète "
            "n'est pas possible : Azeroth Universe ne publie pas de sommes "
            "de contrôle officielles pour l'instant)."
        ),
        "btn_website": "Site web",
        "btn_register": "S'inscrire",
        "btn_check": "Vérifier",
        "status_not_configured": "Statut non configuré",
        "status_online": "Serveur en ligne",
        "status_offline": "Serveur hors ligne",
        "players_connected": "{n} joueur(s) connecté(s)",
        "select_folder_prompt": "Sélectionnez votre dossier client pour commencer.",
        "missing_files_found": "{count} fichier(s) manquant(s) ou incomplet(s) détecté(s).",
        "all_files_verified": "Tous les fichiers sont présents et à jour.",
        "wtf_locale_updated": "Langue du client mise à jour ({locale}) dans WTF/Arealm.wtf.",
        "tab_play": "Jeu",
        "tab_settings": "Paramètres",
        "install_dir_label": "Dossier d'installation :",
        "browse": "Parcourir…",
        "realmlist_label": "Adresse du serveur (realmlist) :",
        "language_label": "Langue :",
        "btn_install": "Installer",
        "btn_update_check": "Vérifier les fichiers",
        "btn_play": "Jouer",
        "btn_cancel": "Annuler",
        "btn_pause": "Pause",
        "btn_resume": "Reprendre",
        "status_paused": "En pause - {name}",
        "log_paused": "Téléchargement mis en pause.",
        "log_resumed": "Reprise du téléchargement.",
        "status_idle": "Prêt à installer Azeroth Universe.",
        "status_checking": "Vérification des fichiers déjà présents…",
        "status_downloading": "Téléchargement : {name}",
        "status_extracting": "Extraction : {name}",
        "status_placing": "Copie des fichiers : {name}",
        "status_writing_realmlist": "Écriture du realmlist…",
        "status_done": "Installation terminée ! Vous pouvez lancer le jeu.",
        "status_error": "Erreur : {error}",
        "status_cancelled": "Installation annulée.",
        "status_launching": "Lancement du jeu…",
        "status_already_installed": "Tous les fichiers semblent déjà installés.",
        "overall_progress": "Progression globale",
        "current_file": "Fichier en cours",
        "log_console": "Journal",
        "confirm_install_dir_title": "Choisir le dossier d'installation",
        "error_no_unrar_title": "Outil d'extraction manquant",
        "error_no_unrar_body": (
            "Le composant d'extraction (UnRAR.exe) est introuvable dans le "
            "dossier tools/ du launcher. Réinstallez le launcher ou "
            "contactez le support Azeroth Universe."
        ),
        "error_disk_space_title": "Espace disque insuffisant",
        "error_game_not_found_title": "Client introuvable",
        "error_game_not_found_body": (
            "AzerothUniverse.exe est introuvable dans le dossier d'installation. "
            "Lancez d'abord l'installation ou vérifiez le dossier choisi."
        ),
        "confirm_cancel_title": "Annuler l'installation ?",
        "confirm_cancel_body": "Voulez-vous vraiment interrompre l'installation en cours ?",
        "yes": "Oui",
        "no": "Non",
        "settings_saved": "Paramètres enregistrés.",
        "menu_open_folder": "Ouvrir le dossier d'installation",
        "footer_opensource": "Azeroth Universe est un projet open source, basé sur TrinityCore (3.3.5a).",
        "speed_label": "{speed}/s",
        "eta_label": "Temps restant estimé : {eta}",
        "eta_inline": "reste {eta}",
        "files_progress": "{done} / {total} fichiers",
        "unverified_warning": (
            "Certains liens de téléchargement n'ont pas pu être vérifiés à "
            "l'avance. En cas d'échec, réessayez ou contactez le support."
        ),
        "update_available_title": "Mise à jour du launcher disponible",
        "update_available_body": (
            "Une nouvelle version du launcher est disponible ({tag}). "
            "Voulez-vous la télécharger et l'installer maintenant ? Le "
            "launcher redémarrera automatiquement une fois la mise à jour "
            "appliquée."
        ),
        "update_downloading": "Téléchargement de la mise à jour du launcher…",
        "update_check_failed": "Impossible de vérifier les mises à jour du launcher.",
        "update_error_title": "Échec de la mise à jour",
        "update_error_body": "La mise à jour du launcher a échoué : {error}",
        "update_dev_mode_skip": (
            "Mise à jour du launcher disponible ({tag}), mais l'installation "
            "automatique n'est possible que depuis l'exécutable compilé."
        ),
        "status_badge_tooltip": "Cliquez pour voir les personnages en ligne.",
        "online_characters_title": "Personnages en ligne",
        "online_characters_count": "{count} personnage(s) en ligne",
        "online_characters_empty": "Aucun personnage en ligne pour le moment.",
        "online_characters_unavailable": (
            "La liste des personnages en ligne n'est pas disponible pour "
            "l'instant (statut serveur non configuré ou hors ligne)."
        ),
        "character_row_subtitle": "Niveau {level} — {race} {class_name}",
        "btn_close": "Fermer",
    },
    "en": {
        "app_title": "Azeroth Universe - Launcher",
        "titlebar_title": "AZEROTH UNIVERSE LAUNCHER",
        "hero_title": "AZEROTH UNIVERSE",
        "tagline": "Choose your faction and get ready for an epic adventure!",
        "news_header": "News",
        "client_folder_header": "Client folder",
        "journal_header": "Log",
        "deep_verify_checkbox": "Deep verification (MD5)",
        "deep_verify_tooltip": (
            "Also re-checks the size reported by the server for .MPQ files "
            "that are already downloaded (a full MD5 check isn't possible: "
            "Azeroth Universe doesn't publish official checksums yet)."
        ),
        "btn_website": "Website",
        "btn_register": "Register",
        "btn_check": "Check",
        "status_not_configured": "Status not configured",
        "status_online": "Server online",
        "status_offline": "Server offline",
        "players_connected": "{n} player(s) online",
        "select_folder_prompt": "Select your client folder to get started.",
        "missing_files_found": "{count} missing or incomplete file(s) detected.",
        "all_files_verified": "All files are present and up to date.",
        "wtf_locale_updated": "Client language updated ({locale}) in WTF/Arealm.wtf.",
        "tab_play": "Play",
        "tab_settings": "Settings",
        "install_dir_label": "Installation folder:",
        "browse": "Browse…",
        "realmlist_label": "Server address (realmlist):",
        "language_label": "Language:",
        "btn_install": "Install",
        "btn_update_check": "Check files",
        "btn_play": "Play",
        "btn_cancel": "Cancel",
        "btn_pause": "Pause",
        "btn_resume": "Resume",
        "status_paused": "Paused - {name}",
        "log_paused": "Download paused.",
        "log_resumed": "Download resumed.",
        "status_idle": "Ready to install Azeroth Universe.",
        "status_checking": "Checking already installed files…",
        "status_downloading": "Downloading: {name}",
        "status_extracting": "Extracting: {name}",
        "status_placing": "Placing files: {name}",
        "status_writing_realmlist": "Writing realmlist…",
        "status_done": "Installation complete! You can launch the game.",
        "status_error": "Error: {error}",
        "status_cancelled": "Installation cancelled.",
        "status_launching": "Launching the game…",
        "status_already_installed": "All files already appear to be installed.",
        "overall_progress": "Overall progress",
        "current_file": "Current file",
        "log_console": "Log",
        "confirm_install_dir_title": "Choose installation folder",
        "error_no_unrar_title": "Extraction tool missing",
        "error_no_unrar_body": (
            "The extraction component (UnRAR.exe) could not be found in the "
            "launcher's tools/ folder. Please reinstall the launcher or "
            "contact Azeroth Universe support."
        ),
        "error_disk_space_title": "Not enough disk space",
        "error_game_not_found_title": "Client not found",
        "error_game_not_found_body": (
            "AzerothUniverse.exe could not be found in the installation folder. Run "
            "the installation first or check the selected folder."
        ),
        "confirm_cancel_title": "Cancel installation?",
        "confirm_cancel_body": "Are you sure you want to stop the current installation?",
        "yes": "Yes",
        "no": "No",
        "settings_saved": "Settings saved.",
        "menu_open_folder": "Open installation folder",
        "footer_opensource": "Azeroth Universe is an open source project, based on TrinityCore (3.3.5a).",
        "speed_label": "{speed}/s",
        "eta_label": "Estimated time remaining: {eta}",
        "eta_inline": "{eta} left",
        "files_progress": "{done} / {total} files",
        "unverified_warning": (
            "Some download links could not be verified in advance. If one "
            "fails, please retry or contact support."
        ),
        "update_available_title": "Launcher update available",
        "update_available_body": (
            "A new launcher version is available ({tag}). Do you want to "
            "download and install it now? The launcher will restart "
            "automatically once the update is applied."
        ),
        "update_downloading": "Downloading launcher update…",
        "update_check_failed": "Could not check for launcher updates.",
        "update_error_title": "Update failed",
        "update_error_body": "The launcher update failed: {error}",
        "update_dev_mode_skip": (
            "A launcher update is available ({tag}), but automatic "
            "installation only works from the compiled executable."
        ),
        "status_badge_tooltip": "Click to see who's currently online.",
        "online_characters_title": "Online characters",
        "online_characters_count": "{count} character(s) online",
        "online_characters_empty": "No character is online right now.",
        "online_characters_unavailable": (
            "The online character list isn't available right now (server "
            "status not configured or offline)."
        ),
        "character_row_subtitle": "Level {level} — {race} {class_name}",
        "btn_close": "Close",
    },
}


# Identifiants numeriques race/classe standard de WoW 3.3.5a (client Wrath
# of the Lich King), tels que stockes dans characters.characters (colonnes
# `race`/`class`). Traduits ici plutot que cotes serveur (status.php) pour
# que le launcher affiche les noms dans la langue choisie par le joueur,
# independamment de la langue du serveur/site web. Les identifiants absents
# (races/classes non jouables, valeurs corrompues) retombent sur "?" plutot
# que de faire planter l'affichage - voir Translator.race_name/class_name.
RACE_NAMES = {
    "fr": {
        1: "Humain", 2: "Orc", 3: "Nain", 4: "Elfe de la nuit", 5: "Mort-vivant",
        6: "Tauren", 7: "Gnome", 8: "Troll", 10: "Elfe de sang", 11: "Draeneï",
    },
    "en": {
        1: "Human", 2: "Orc", 3: "Dwarf", 4: "Night Elf", 5: "Undead",
        6: "Tauren", 7: "Gnome", 8: "Troll", 10: "Blood Elf", 11: "Draenei",
    },
}

CLASS_NAMES = {
    "fr": {
        1: "Guerrier", 2: "Paladin", 3: "Chasseur", 4: "Voleur", 5: "Prêtre",
        6: "Chevalier de la mort", 7: "Chaman", 8: "Mage", 9: "Démoniste", 11: "Druide",
    },
    "en": {
        1: "Warrior", 2: "Paladin", 3: "Hunter", 4: "Rogue", 5: "Priest",
        6: "Death Knight", 7: "Shaman", 8: "Mage", 9: "Warlock", 11: "Druid",
    },
}

# Couleurs standard des classes WoW (identiques a celles utilisees par le
# client de jeu lui-meme, l'armurerie officielle, et a peu pres tous les
# addons/sites communautaires) : simples codes couleur publics, pas des
# assets graphiques Blizzard. Independantes de la langue.
CLASS_COLORS = {
    1: "#C79C6E",   # Guerrier / Warrior
    2: "#F58CBA",   # Paladin
    3: "#ABD473",   # Chasseur / Hunter
    4: "#FFF569",   # Voleur / Rogue
    5: "#FFFFFF",   # Pretre / Priest
    6: "#C41F3B",   # Chevalier de la mort / Death Knight
    7: "#0070DE",   # Chaman / Shaman
    8: "#69CCF0",   # Mage
    9: "#9482C9",   # Demoniste / Warlock
    11: "#FF7D0A",  # Druide / Druid
}
DEFAULT_CLASS_COLOR = "#9aa0ad"  # TEXT_SECONDARY (ui/theme.py) - classe inconnue


# Actualités affichées dans le panneau "Actualités" du launcher. Statique
# pour l'instant (pas de flux/API de news fourni) : à éditer ici au fil des
# annonces, ou à remplacer plus tard par un vrai flux (RSS/JSON) si vous en
# mettez un en place sur azeroth-universe.eu.
NEWS_ITEMS = {
    "fr": [
        {
            "tag": "INFO",
            "date": "2026-08-26",
            "title": "Bienvenue sur Azeroth Universe !",
            "body": (
                "Le Royaume Azeroth Universe est de retour avec de "
                "nouvelles fonctionnalités. Rejoignez-nous pour une "
                "aventure épique en Azeroth."
            ),
        },
    ],
    "en": [
        {
            "tag": "INFO",
            "date": "2026-08-26",
            "title": "Welcome to Azeroth Universe!",
            "body": (
                "The Azeroth Universe realm is back with new features. "
                "Join us for an epic adventure across Azeroth."
            ),
        },
    ],
}


class Translator:
    def __init__(self, lang="fr"):
        self.lang = lang if lang in STRINGS else "fr"

    def set_lang(self, lang):
        if lang in STRINGS:
            self.lang = lang

    def t(self, key, **kwargs):
        text = STRINGS.get(self.lang, STRINGS["fr"]).get(key, key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError):
                return text
        return text

    def news(self):
        return NEWS_ITEMS.get(self.lang, NEWS_ITEMS["fr"])

    def race_name(self, race_id):
        return RACE_NAMES.get(self.lang, RACE_NAMES["fr"]).get(race_id, "?")

    def class_name(self, class_id):
        return CLASS_NAMES.get(self.lang, CLASS_NAMES["fr"]).get(class_id, "?")

    def class_color(self, class_id):
        return CLASS_COLORS.get(class_id, DEFAULT_CLASS_COLOR)
