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
 *     {"online": true,  "players": 12}
 *     {"online": false, "players": null}   (base injoignable / realm down)
 *
 * -----------------------------------------------------------------------
 * SECURITE - A LIRE AVANT DE METTRE EN LIGNE
 * -----------------------------------------------------------------------
 * 1. Creez un compte MySQL DEDIE, en LECTURE SEULE, limite a une seule
 *    requete SELECT sur la table characters.characters. Ne mettez JAMAIS
 *    ici les identifiants utilises par le core UniverseEmu/TrinityCore
 *    lui-meme. Exemple (a executer une fois dans MySQL) :
 *
 *      CREATE USER 'launcher_readonly'@'localhost' IDENTIFIED BY 'un_mot_de_passe_long_et_unique';
 *      GRANT SELECT (online) ON characters.characters TO 'launcher_readonly'@'localhost';
 *      FLUSH PRIVILEGES;
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
$DB_NAME = getenv('AU_STATUS_DB_NAME') ?: 'characters'; // base "characters" de TrinityCore/UniverseEmu
$DB_USER = getenv('AU_STATUS_DB_USER') ?: 'launcher_readonly';
$DB_PASS = getenv('AU_STATUS_DB_PASS') ?: 'CHANGEZ_MOI';
$CACHE_FILE = sys_get_temp_dir() . '/au_status_cache.json';
$CACHE_SECONDS = 15;
// ------------------------------------------------------------------------

function respond($online, $players) {
    echo json_encode(['online' => $online, 'players' => $players]);
    exit;
}

// Cache fichier tres simple : evite une requete SQL a chaque appel si
// plusieurs joueurs rafraichissent leur launcher au meme moment.
if (is_file($GLOBALS['CACHE_FILE']) && (time() - filemtime($GLOBALS['CACHE_FILE'])) < $GLOBALS['CACHE_SECONDS']) {
    $cached = json_decode(file_get_contents($GLOBALS['CACHE_FILE']), true);
    if (is_array($cached)) {
        respond($cached['online'], $cached['players']);
    }
}

try {
    $pdo = new PDO(
        "mysql:host={$DB_HOST};dbname={$DB_NAME};charset=utf8mb4",
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

    file_put_contents($CACHE_FILE, json_encode(['online' => true, 'players' => $players]));
    respond(true, $players);

} catch (Exception $e) {
    // Base injoignable (serveur de jeu hors ligne, maintenance...) : on
    // repond quand meme avec un JSON valide "hors ligne" plutot qu'une
    // erreur HTTP 500 que le launcher ne saurait pas interpreter.
    file_put_contents($CACHE_FILE, json_encode(['online' => false, 'players' => null]));
    respond(false, null);
}
