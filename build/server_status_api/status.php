<?php
/**
 * status.php
 * ----------
 * Exemple d'endpoint de statut serveur pour le badge "Serveur en ligne" du
 * launcher Azeroth Universe (voir core/server_status.py cote launcher).
 *
 * A HEBERGER SUR VOTRE SITE WEB (par ex. https://azeroth-universe.eu/api/status.php),
 * PAS dans le dossier du launcher - ce fichier tourne sur VOTRE serveur, pas
 * sur la machine des joueurs (le launcher ne peut pas se connecter
 * directement a votre base de donnees MySQL, et ne le devrait pas).
 *
 * Une fois en place et teste, renseignez son URL publique dans
 * AzerothUniverseLauncher/config.py :
 *
 *     STATUS_URL = "https://azeroth-universe.eu/api/status.php"
 *
 * Contrat JSON attendu par le launcher :
 *     {"online": true,  "players": 12, "characters": [{"name": "Foo", "level": 80, "race": 1, "class": 2}, ...]}
 *     {"online": false, "players": null, "characters": null}   (base injoignable / realm down)
 *
 * "characters" alimente la fenetre "Personnages en ligne" qui s'ouvre quand
 * on clique sur le badge de statut (voir ui/main_window.py,
 * OnlineCharactersDialog). Cote launcher, ce champ est traite comme
 * OPTIONNEL (core/server_status.py accepte son absence sans planter) : une
 * ancienne version de ce script, deployee avant cet ajout, continue donc de
 * fonctionner sans avoir besoin d'etre mise a jour dans l'urgence - le badge
 * fonctionnera normalement, seule la liste de personnages restera vide.
 * `race`/`class` sont les identifiants numeriques standard de WoW 3.3.5a
 * (le launcher fait la traduction en texte localise, voir i18n.py).
 *
 * -----------------------------------------------------------------------
 * SECURITE - A LIRE AVANT DE METTRE EN LIGNE
 * -----------------------------------------------------------------------
 * 1. Creez un compte MySQL DEDIE, en LECTURE SEULE, limite aux quelques
 *    colonnes necessaires de la table characters (remplacez auc_chars
 *    ci-dessous par le nom REEL de votre base "characters" si different).
 *    Ne mettez JAMAIS ici les identifiants utilises par le core
 *    UniverseEmu/TrinityCore lui-meme. Exemple (a executer une fois dans
 *    MySQL) :
 *
 *      CREATE USER 'launcher_readonly'@'%' IDENTIFIED BY 'un_mot_de_passe_long_et_unique';
 *      GRANT SELECT (online, name, race, class, level) ON auc_chars.characters TO 'launcher_readonly'@'%';
 *      FLUSH PRIVILEGES;
 *
 *    Hote '%' (plutot que 'localhost') : ce script se connecte presque
 *    toujours en TCP (meme vers 127.0.0.1), pas via un socket Unix local -
 *    hors MySQL/MariaDB ne fait correspondre 'utilisateur'@'localhost'
 *    QU'AUX connexions par socket Unix. Une connexion TCP, meme depuis la
 *    meme machine, doit correspondre a '%' ou a l'adresse IP exacte
 *    ('127.0.0.1'), sans quoi la connexion est refusee (erreur "Access
 *    denied") et le badge affichera "hors ligne" en permanence.
 *
 *    (Si un compte 'launcher_readonly' existe deja avec seulement le droit
 *    SELECT sur `online`, relancez simplement ce meme GRANT : MySQL ajoute
 *    les colonnes manquantes aux privileges existants, il n'annule rien.)
 *
 *    Volontairement PAS `account` (identifie le joueur), ni les colonnes de
 *    position/localisation (`map`, `zone`, `position_x/y/z`...) : ce
 *    endpoint est public, n'importe qui peut l'appeler sans etre connecte -
 *    on n'expose que ce qu'un site "qui est en ligne" affiche d'habitude
 *    (nom de personnage, niveau, race, classe), jamais de quoi retrouver un
 *    joueur precis en jeu ou relier un personnage a son compte.
 *
 * 2. Ne committez jamais ce fichier avec de vrais identifiants dans un
 *    depot public (Git). Idealement, lisez-les depuis des variables
 *    d'environnement plutot que de les coder en dur ci-dessous.
 * 3. Ce endpoint sera appele par TOUS les launchers de vos joueurs environ
 *    une fois par minute chacun (voir STATUS_POLL_INTERVAL_MS cote
 *    launcher) : le cache de 15 secondes ci-dessous evite de marteler la
 *    base si vous avez beaucoup de joueurs connectes simultanement.
 */

header('Content-Type: application/json; charset=utf-8');
// Le launcher tourne sur la machine du joueur (origine "null"), pas sur
// votre domaine : sans cet en-tete, le navigateur systeme ou certains
// clients HTTP peuvent bloquer la reponse selon le contexte.
header('Access-Control-Allow-Origin: *');

// --- A PERSONNALISER --------------------------------------------------
$DB_HOST = getenv('AU_STATUS_DB_HOST') ?: '127.0.0.1';
// Port MySQL SEPARE de l'hote : ne mettez jamais "host:port" dans
// AU_STATUS_DB_HOST/$DB_HOST ci-dessus (PDO essaierait de resoudre ca
// comme un nom d'hote litteral et la connexion echouerait toujours,
// rapportant le serveur "hors ligne" meme quand tout va bien). Si votre
// MySQL ecoute sur le port par defaut (3306), laissez tel quel.
$DB_PORT = getenv('AU_STATUS_DB_PORT') ?: '3309';
$DB_NAME = getenv('AU_STATUS_DB_NAME') ?: 'auc_chars'; // nom de la base "characters" d'UniverseEmu (auc_chars ici, peut differer selon votre install)
$DB_USER = getenv('AU_STATUS_DB_USER') ?: 'launcher_readonly';
$DB_PASS = getenv('AU_STATUS_DB_PASS') ?: 'CHOISISSEZ_UN_MOT_DE_PASSE_LONG_ET_UNIQUE_ICI'; // doit correspondre EXACTEMENT au mot de passe du compte MySQL 'launcher_readonly' (voir CREATE USER plus haut)
$CACHE_FILE = sys_get_temp_dir() . '/au_status_cache.json';
$CACHE_SECONDS = 15;

// Filet de securite : si $DB_HOST contient malgre tout encore un "host:port"
// colle avec un ":" (habitude classique, mais invalide pour le DSN PDO
// mysql), on le separe automatiquement plutot que de laisser la connexion
// echouer silencieusement a chaque appel.
if (strpos($DB_HOST, ':') !== false) {
    $hostParts = explode(':', $DB_HOST, 2);
    $DB_HOST = $hostParts[0];
    if (!empty($hostParts[1])) {
        $DB_PORT = $hostParts[1];
    }
}
// Nombre maximum de personnages renvoyes dans "characters" : la fenetre du
// launcher scrolle, mais autant eviter une reponse JSON demesuree (et une
// requete plus lourde cote base) si des centaines de joueurs sont en ligne
// en meme temps. Les plus hauts niveaux d'abord (voir ORDER BY plus bas),
// donc les personnages "coupes" par cette limite sont les moins notables.
$MAX_CHARACTERS = 300;
// ------------------------------------------------------------------------

function respond($online, $players, $characters) {
    echo json_encode(['online' => $online, 'players' => $players, 'characters' => $characters]);
    exit;
}

// Cache fichier tres simple : evite une requete SQL a chaque appel si
// plusieurs joueurs rafraichissent leur launcher au meme moment.
if (is_file($GLOBALS['CACHE_FILE']) && (time() - filemtime($GLOBALS['CACHE_FILE'])) < $GLOBALS['CACHE_SECONDS']) {
    $cached = json_decode(file_get_contents($GLOBALS['CACHE_FILE']), true);
    if (is_array($cached)) {
        // isset() plutot qu'un acces direct : le cache peut contenir une
        // ancienne reponse ecrite par une version anterieure de ce script,
        // sans cle "characters" du tout.
        respond($cached['online'], $cached['players'], isset($cached['characters']) ? $cached['characters'] : null);
    }
}

try {
    $pdo = new PDO(
        "mysql:host={$DB_HOST};port={$DB_PORT};dbname={$DB_NAME};charset=utf8mb4",
        $DB_USER, $DB_PASS,
        [PDO::ATTR_TIMEOUT => 3, PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]
    );

    // Nombre de PERSONNAGES actuellement connectes (colonne `online` de la
    // table `characters`, mise a jour par le core a la connexion/deconnexion
    // de chaque personnage). C'est la mesure la plus simple et la plus
    // repandue sur les sites de serveurs prives ; elle peut compter deux
    // fois un joueur qui a deux personnages ouverts en meme temps (rare).
    $stmt = $pdo->query('SELECT COUNT(*) FROM characters WHERE online = 1');
    $players = (int) $stmt->fetchColumn();

    // IMPORTANT : requete separee, dans son PROPRE try/catch, de la requete
    // de comptage ci-dessus. La premiere version de ce bloc mettait les
    // deux requetes dans le meme try : si le compte MySQL n'a pas encore
    // les droits SELECT sur name/race/class/level (ex: GRANT pas encore
    // relance apres la mise a jour de ce script), la requete ci-dessous
    // levait une exception qui faisait retomber TOUT le endpoint sur
    // "hors ligne" - alors meme que le comptage juste au-dessus avait
    // parfaitement reussi et que le serveur etait bel et bien en ligne
    // avec des joueurs dessus. Desormais, un probleme ici degrade juste
    // "characters" a null (liste indisponible) sans jamais casser la
    // detection en ligne/hors ligne ni le nombre de joueurs.
    $characters = null;
    try {
        // Liste nominative pour la fenetre "Personnages en ligne" du
        // launcher : uniquement les colonnes cosmetiques (voir la note
        // SECURITE plus haut), triees par niveau decroissant (les plus
        // hauts niveaux, generalement les plus "notables", passent en
        // premier et ne sont jamais coupes par MAX_CHARACTERS avant les
        // autres).
        $stmt = $pdo->prepare('SELECT name, race, class, level FROM characters WHERE online = 1 ORDER BY level DESC LIMIT :limit');
        $stmt->bindValue(':limit', $MAX_CHARACTERS, PDO::PARAM_INT);
        $stmt->execute();
        $characters = [];
        while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
            $characters[] = [
                'name' => $row['name'],
                'race' => (int) $row['race'],
                'class' => (int) $row['class'],
                'level' => (int) $row['level'],
            ];
        }
    } catch (Exception $e) {
        // Le plus probable : le compte MySQL 'launcher_readonly' n'a
        // encore que l'ancien droit SELECT (online) et pas les nouvelles
        // colonnes (voir la note SECURITE, section 1, pour le GRANT a
        // relancer). $characters reste a null, le reste de la reponse
        // (online/players) n'est pas affecte.
        $characters = null;
    }

    file_put_contents($CACHE_FILE, json_encode(['online' => true, 'players' => $players, 'characters' => $characters]));
    respond(true, $players, $characters);

} catch (Exception $e) {
    // Base entierement injoignable (serveur de jeu hors ligne,
    // maintenance, identifiants invalides...) : on repond quand meme avec
    // un JSON valide "hors ligne" plutot qu'une erreur HTTP 500 que le
    // launcher ne saurait pas interpreter.
    file_put_contents($CACHE_FILE, json_encode(['online' => false, 'players' => null, 'characters' => null]));
    respond(false, null, null);
}
