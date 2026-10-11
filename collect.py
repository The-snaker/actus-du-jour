#!/usr/bin/env python3
"""Collecte les actualités (flux RSS/Atom) listées dans sources.json
et écrit news.json (pour l'appli) et rapport.txt (flux en panne).
Aucune dépendance externe."""
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

FENETRE_HEURES = 72      # on garde les 3 derniers jours
MAX_PAR_CATEGORIE = 150
LONGUEUR_EXTRAIT = 220
UA = "Mozilla/5.0 (compatible; ActusDuJour/1.0)"


def nettoyer(texte):
    texte = html.unescape(re.sub(r"<[^>]+>", " ", texte or ""))
    return re.sub(r"\s+", " ", texte).strip()


def couper(texte, n):
    if len(texte) <= n:
        return texte
    return texte[:n].rsplit(" ", 1)[0].rstrip(",;:. ") + "…"


def lire_date(texte):
    if not texte:
        return None
    texte = texte.strip()
    try:
        d = parsedate_to_datetime(texte)
    except Exception:
        try:
            d = datetime.fromisoformat(texte.replace("Z", "+00:00"))
        except Exception:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def nom_balise(el):
    return el.tag.rsplit("}", 1)[-1]


def analyser(contenu):
    """Retourne la liste des articles d'un flux RSS ou Atom."""
    articles = []
    for el in ET.fromstring(contenu).iter():
        if nom_balise(el) not in ("item", "entry"):
            continue
        champs, lien = {}, None
        for c in el:
            k = nom_balise(c)
            if k == "link":
                if c.get("href"):
                    if c.get("rel") in (None, "alternate"):
                        lien = lien or c.get("href")
                elif c.text:
                    lien = lien or c.text.strip()
            elif k not in champs:
                champs[k] = c.text or ""
        date = lire_date(champs.get("pubDate") or champs.get("published")
                         or champs.get("updated") or champs.get("date"))
        titre = nettoyer(champs.get("title"))
        extrait = nettoyer(champs.get("description") or champs.get("summary")
                           or champs.get("encoded") or champs.get("content"))
        if titre and lien and date:
            articles.append({"titre": titre, "lien": lien, "date": date,
                             "extrait": couper(extrait, LONGUEUR_EXTRAIT)})
    return articles


def traiter(tache):
    categorie, source = tache
    try:
        req = urllib.request.Request(source["url"], headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            articles = analyser(r.read())
        return categorie, source, articles, None
    except Exception as e:
        return categorie, source, [], f"{type(e).__name__}: {e}"


def main():
    chemin = sys.argv[1] if len(sys.argv) > 1 else "sources.json"
    with open(chemin, encoding="utf-8") as f:
        sources = json.load(f)

    taches = [(c, s) for c, liste in sources.items() for s in liste]
    with ThreadPoolExecutor(max_workers=16) as pool:
        resultats = list(pool.map(traiter, taches))

    limite = datetime.now(timezone.utc) - timedelta(hours=FENETRE_HEURES)
    sortie = {c: [] for c in sources}
    rapport = []
    for categorie, source, articles, erreur in resultats:
        recents = [a for a in articles if a["date"] >= limite]
        if erreur:
            rapport.append(f"KO  [{categorie}] {source['nom']} - {source['url']} - {erreur}")
        elif not articles:
            rapport.append(f"VIDE [{categorie}] {source['nom']} - {source['url']} - aucun article lisible")
        else:
            rapport.append(f"OK  [{categorie}] {source['nom']} - {len(recents)} article(s) récent(s)")
        for a in recents:
            sortie[categorie].append({
                "source": source["nom"], "titre": a["titre"], "lien": a["lien"],
                "extrait": a["extrait"], "date": a["date"].isoformat()})

    total = 0
    for categorie, liste in sortie.items():
        vus, uniques = set(), []
        for a in sorted(liste, key=lambda x: x["date"], reverse=True):
            cle = re.sub(r"\W+", "", a["titre"].lower())
            if a["lien"] in vus or cle in vus:
                continue
            vus.update((a["lien"], cle))
            uniques.append(a)
        sortie[categorie] = uniques[:MAX_PAR_CATEGORIE]
        total += len(sortie[categorie])

    maintenant = datetime.now(timezone.utc).isoformat()
    with open("rapport.txt", "w", encoding="utf-8") as f:
        f.write(f"Rapport du {maintenant}\n" + "\n".join(sorted(rapport)) + "\n")

    if total == 0:
        print("Aucun article collecté : news.json conservé tel quel.")
        sys.exit(1)
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump({"genere_le": maintenant, "categories": sortie}, f, ensure_ascii=False, indent=1)
    print(f"{total} articles collectés ({len(taches)} sources).")


if __name__ == "__main__":
    main()
