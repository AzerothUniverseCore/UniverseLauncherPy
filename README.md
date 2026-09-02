# Endpoint de statut serveur (badge "Serveur en ligne")

Le badge en haut à droite du launcher affiche "Statut non configuré" tant
qu'aucune URL de statut n'est renseignée. Pour l'activer, il faut héberger
un petit script sur **votre site web** (pas dans le launcher) qui répond en
JSON, puis pointer le launcher dessus.

## Étapes

1. Créez un compte MySQL dédié en lecture seule (voir le commentaire en
   haut de `status.php` pour la commande exacte).
2. Copiez `status.php` sur votre hébergement, par exemple à
   `https://azeroth-universe.eu/api/status.php`.
3. Renseignez les identifiants MySQL dans les variables d'environnement de
   votre hébergement (`AU_STATUS_DB_HOST`, `AU_STATUS_DB_NAME`,
   `AU_STATUS_DB_USER`, `AU_STATUS_DB_PASS`), ou à défaut directement dans
   le fichier - mais ne le publiez alors jamais sur un dépôt Git public.
4. Testez dans un navigateur : `https://azeroth-universe.eu/api/status.php`
   doit répondre quelque chose comme
   `{"online":true,"players":3,"characters":[{"name":"Foo","race":1,"class":2,"level":80}, ...]}`.
5. Dans `AzerothUniverseLauncher/config.py`, mettez à jour :

   ```python
   STATUS_URL = "https://azeroth-universe.eu/api/status.php"
   ```

6. Relancez le launcher : le badge doit passer de "Statut non configuré" à
   "Serveur en ligne" / "Serveur hors ligne" avec le nombre de joueurs. Un
   clic sur le badge ouvre la liste des personnages actuellement en ligne
   (nom, niveau, race, classe), remplie à partir de "characters".

## Vous n'utilisez pas PHP ?

Le contrat est juste une URL HTTP qui répond en JSON
`{"online": bool, "players": int|null, "characters": [{"name": str, "race": int, "class": int, "level": int}, ...]|null}`
n'importe quelle techno peut l'implémenter (Node/Express, Python/Flask, une
Cloud Function, etc.), tant que la logique reste la même : compter (et,
pour "characters", lister nom/race/classe/niveau) les lignes `online = 1`
dans la table `characters.characters` de la base UniverseEmu/TrinityCore,
avec un compte MySQL en lecture seule dédié à cet usage. Le champ
"characters" est optionnel côté launcher (une réponse qui ne le contient
pas fonctionne toujours, seule la fenêtre "Personnages en ligne" restera
vide) : pas besoin de le mettre à jour dans l'urgence si vous avez un
endpoint existant.
