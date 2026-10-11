# Actus du jour — guide de reprise du projet

À lire en premier pour continuer à améliorer ou déboguer le site. L'utilisateur ne code pas : Claude fait tout, en français, de façon directe.

## Où est tout
- Site : https://the-snaker.github.io/actus-du-jour/ (GitHub Pages, branche main)
- Dépôt : https://github.com/The-snaker/actus-du-jour (compte The-snaker). Le code source vit dans ce dépôt, c'est la référence.
- Pour reprendre : attacher le dépôt à la session (add_repo The-snaker/actus-du-jour avec accès push), puis lire LISEZMOI.md.

## Fichiers
- index.html : tout le site (HTML, CSS, JS sans framework), modes PC/mobile, recherche, favoris, bouton d'actualisation.
- collect.py : collecteur Python sans dépendance. Lit sources.json (flux RSS) + l'API YouTube, écrit news.json et rapport.txt.
- sources.json : 8 catégories de flux RSS (15 max chacune).
- .github/workflows/daily.yml : GitHub Actions, cron « 7 */5 * * * » (00h07, 05h07, 10h07, 15h07, 20h07 UTC), lancement manuel possible, se relance aussi quand sources.json ou collect.py changent.
- sw.js : cache hors ligne. Changer le numéro de version (const V) à chaque publication visible, sinon les visiteurs gardent l'ancienne version.
- news.json et rapport.txt : produits par le robot ; rapport.txt liste chaque source OK / KO / VIDE. C'est le premier outil de débogage.

## Onglets (ordre voulu)
Tout, Tendances Youtube, Politique française, Jeux-Vidéo, High-Tech, Cinéma, Sport (foot européen), Québec (centré Montréal), Aéronautique, Finance. L'ordre est celui des clés de SLUG dans index.html.
- Tendances Youtube : 100 vidéos tendance en France via YouTube Data API v3 (chart=mostPopular, regionCode=FR). Ordre YouTube conservé, pas de regroupement par jour, exclu de « Tout ». Si l'appel échoue, le dernier classement est conservé.

## Affichage
- PC : catégories en colonne à gauche (sticky). Mobile : les onglets passent à la ligne, tous visibles sans défiler, en haut de page (non collés).
- La catégorie ouverte est gardée dans l'adresse (#sport, #tend…) et dans sessionStorage : une actualisation reste dessus.
- Leçon : les descriptions YouTube contiennent des liens longs qui faisaient déborder les cartes et poussaient l'image hors écran. Les colonnes de grille utilisent minmax(0,1fr) et overflow-wrap:anywhere ; les liens sont retirés dans collect.py. En cas d'image « absente » sur mobile, vérifier d'abord le débordement avec le navigateur intégré (viewport mobile 375 px) avant de soupçonner l'URL de l'image.
- Miniatures YouTube : hqdefault.jpg, avec adresses de secours (img.youtube.com, mqdefault) dans index.html.

## Secrets et jetons (jamais dans le dépôt ni dans une conversation)
- Secret GitHub YT_API_KEY (Settings > Secrets > Actions) : clé YouTube Data API v3. Claude ne peut pas le modifier (le proxy de session bloque les secrets) : l'utilisateur le fait.
- Jeton GitHub optionnel, saisi dans les Réglages du site, stocké seulement dans le navigateur de l'utilisateur : permet au bouton d'actualisation de lancer une collecte immédiate (permission Actions : Read and write, limité à ce dépôt).

## Décisions et contraintes
- 100 % gratuit exigé. Twitter/X, TikTok, Snapchat écartés (API payantes ou inaccessibles) : remplacés par YouTube Tendances.
- Mises à jour toutes les 5 h. L'écart 20h→00h UTC est de 4 h (24 h ne se divisent pas en 5 h).
- Les flux RSS cassent avec le temps : retirer ou remplacer les sources KO de rapport.txt, quelques fois par an.
- Depuis la session Claude, les sites de presse sont inaccessibles par le shell (proxy) : on teste via GitHub Actions et rapport.txt.
- Branche claude-test-acces à supprimer par l'utilisateur dans GitHub (Branches).

## Améliorations possibles
Notifications, emballage Android (Play Store), élargir Aéronautique à l'espace et la défense, vérification mensuelle automatique de l'état des flux.
