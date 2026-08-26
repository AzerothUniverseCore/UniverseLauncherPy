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
   doit répondre quelque chose comme `{"online":true,"players":3}`.
5. Dans `AzerothUniverseLauncher/config.py`, mettez à jour :

   ```python
   STATUS_URL = "https://azeroth-universe.eu/api/status.php"
   ```

6. Relancez le launcher : le badge doit passer de "Statut non configuré" à
   "Serveur en ligne" / "Serveur hors ligne" avec le nombre de joueurs.

## Vous n'utilisez pas PHP ?

Le contrat est juste une URL HTTP qui répond en JSON
`{"online": bool, "players": int|null}` - n'importe quelle techno peut
l'implémenter (Node/Express, Python/Flask, une Cloud Function, etc.), tant
que la logique reste la même : compter les lignes `online = 1` dans la
table `characters.characters` de la base UniverseEmu/TrinityCore, avec un
compte MySQL en lecture seule dédié à cet usage.
