# Actus du jour : mise en ligne pas à pas

Ce dossier contient tout : le collecteur quotidien, la liste de sources et l'appli (installable sur Android, et déjà utilisable comme site web). Aucun serveur à payer.

## Mise en ligne (une seule fois, environ 15 minutes)

1. Crée un compte gratuit sur github.com.
2. Clique sur « New repository », nomme-le `actus-du-jour`, choisis **Public**, puis « Create repository ».
3. Clique sur « uploading an existing file », glisse **tout le contenu de ce dossier dézippé** (y compris le dossier caché `.github`), puis « Commit changes ».
   Si `.github` n'est pas accepté : « Add file » > « Create new file », tape comme nom `.github/workflows/daily.yml`, colle le contenu du fichier du même nom, puis « Commit ».
4. Va dans **Settings > Pages**. Sous « Branch », choisis `main` et `/ (root)`, puis Save.
5. Va dans l'onglet **Actions**, ouvre « Mise à jour quotidienne », clique sur « Run workflow ». Après 1 à 2 minutes, le fichier `news.json` apparaît dans le dépôt. Ensuite, la mise à jour se fait seule chaque jour vers 6 h/7 h (heure de Paris).
6. Ton site est à l'adresse `https://TON-PSEUDO.github.io/actus-du-jour/`.

## Installer sur Android

Ouvre l'adresse dans Chrome, touche le menu ⋮, puis « Installer l'application » (ou « Ajouter à l'écran d'accueil »). L'icône apparaît avec les autres applis.

## Vérifier les sources

Le fichier `rapport.txt` (mis à jour à chaque collecte) indique pour chaque source `OK`, `KO` ou `VIDE`. Les adresses de flux de départ n'ont pas pu être testées depuis ici : copie-moi le contenu de `rapport.txt` et je corrige les sources en panne et j'ajoute les suivantes, jusqu'à 40 par catégorie.

## Ce que fait l'appli

Elle affiche titre, source, court extrait et lien vers l'article d'origine. Les articles ne sont pas recopiés en entier.
