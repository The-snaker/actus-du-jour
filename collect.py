#!/usr/bin/env python3
"""Collecte les actualités (flux RSS/Atom) listées dans sources.json
et écrit news.json (pour l'appli) et rapport.txt (état de chaque source).
Aucune dépendance externe."""
import html
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

FENETRE_HEURES = 72       # on garde les 3 derniers jours
MAX_PAR_CATEGORIE = 150
MAX_PAR_SOURCE = 12       # évite qu'un seul site occupe toute la page
LONGUEUR_EXTRAIT = 240
ENTETES = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5",
    "Accept-Language": "fr-FR,fr;q=0.9",
}
RE_IMG = re.compile(r"""<img[^>]+?(?:data-src|src)\s*=\s*["']([^"']+)["']""", re.I)
EXT_IMAGE = re.compile(r"\.(jpe?g|png|webp|avif|gif)(\?|$)", re.I)


# Catégorie Esport : on garde, dans de grands flux jeux vidéo, uniquement les articles qui parlent d'esport.
FILTRE_ESPORT_MINUSCULES = re.compile(
    r"e-?sport|league of legends|valorant|counter-?strike|rocket league|karmine|team vitality|gentle mates|"
    r"riot games|dota 2|overwatch champions|call of duty league|rainbow six (?:siege )?(?:major|tournoi|pro league)|"
    r"worlds 20\d\d|tournoi (?:pro|international)|ligue pro|lan party|\bcs ?2\b|\bt1 faker\b|\bfaker\b", re.I)
FILTRE_ESPORT_CASSE = re.compile(r"\b(?:LoL|LEC|LCK|LCS|VCT|IEM|BLAST|ESL|EWC|CS2|CS:GO|LFL\b")
FENETRE_FILTRE_HEURES = 168   # les flux filtrés sont rares : on remonte à 7 jours


def parle_esport(article):
    texte = f"{article['titre']} {article['extrait']}"
    return bool(FILTRE_ESPORT_MINUSCULES.search(texte) or FILTRE_ESPORT_CASSE.search(texte))


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


def image_valide(url):
    """Garde une adresse d'image https exploitable, sinon None."""
    if not url:
        return None
    url = html.unescape(url.strip())
    if url.startswith("//"):
        url = "https:" + url
    if url.startswith("http://"):
        url = "https://" + url[7:]
    if not url.startswith("https://"):
        return None
    if re.search(r"(pixel|1x1|spacer|blank|tracking|logo)", url, re.I):
        return None
    return url


def trouver_image(el, html_brut):
    """Cherche l'image d'un article : balises média, pièce jointe, puis <img> du texte."""
    for c in el.iter():
        k = nom_balise(c)
        url = c.get("url") or c.get("href")
        genre = (c.get("type") or c.get("medium") or "").lower()
        if k in ("thumbnail",) and url:
            return image_valide(url)
        if k in ("content", "enclosure", "link") and url:
            if genre.startswith("image") or (not genre and EXT_IMAGE.search(url)) \
                    or (k == "link" and c.get("rel") == "enclosure" and genre.startswith("image")):
                img = image_valide(url)
                if img:
                    return img
        if k == "image" and c.text and c.text.strip().startswith(("http", "//")):
            img = image_valide(c.text)
            if img:
                return img
    for m in RE_IMG.finditer(html_brut or ""):
        img = image_valide(m.group(1))
        if img:
            return img
    return None


def reparer(contenu):
    """Tente de rendre lisible un flux mal formé (esperluettes, caractères
    interdits, préfixes XML non déclarés, déclaration d'encodage fausse)."""
    texte = contenu.decode("utf-8", "replace")
    texte = re.sub(r"^\s*<\?xml[^>]*\?>", "", texte)
    texte = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", texte)
    texte = re.sub(r"&(?!(?:[a-zA-Z][a-zA-Z0-9]*|#\d+|#x[0-9a-fA-F]+);)", "&amp;", texte)
    declares = set(re.findall(r"xmlns:(\w+)\s*=", texte))
    utilises = set(re.findall(r"</?(\w+):\w", texte)) - {"xml", "xmlns"}
    for p in utilises - declares:
        texte = re.sub(rf"(</?){p}:", rf"\1{p}_", texte)
        texte = re.sub(rf"(\s){p}:(\w+\s*=)", rf"\1{p}_\2", texte)
    return texte.encode("utf-8")


def analyser(contenu):
    """Retourne la liste des articles d'un flux RSS ou Atom."""
    articles = []
    try:
        racine = ET.fromstring(contenu)
    except ET.ParseError:
        racine = ET.fromstring(reparer(contenu))
    for el in racine.iter():
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
        brut = " ".join(champs.get(k, "") for k in
                        ("description", "summary", "encoded", "content"))
        extrait = nettoyer(champs.get("description") or champs.get("summary")
                           or champs.get("encoded") or champs.get("content"))
        if titre and lien and date:
            articles.append({"titre": titre, "lien": lien, "date": date,
                             "extrait": couper(extrait, LONGUEUR_EXTRAIT),
                             "image": trouver_image(el, brut)})
    return articles


def traiter(tache):
    categorie, source = tache
    try:
        req = urllib.request.Request(source["url"], headers=ENTETES)
        with urllib.request.urlopen(req, timeout=20) as r:
            articles = analyser(r.read())
        return categorie, source, articles, None
    except Exception as e:
        return categorie, source, [], f"{type(e).__name__}: {e}"


MAX_TENDANCES = 100


def format_vues(n):
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".replace(".", ",").replace(",0", "") + " M"
    if n >= 1000:
        return f"{n // 1000} k"
    return str(n)


def collecter_tendances():
    """Vidéos tendance de YouTube en France (API officielle, gratuite avec une clé).
    La clé est lue dans la variable d'environnement YT_API_KEY (secret GitHub).
    L'ordre est celui de YouTube : le classement « Tendances »."""
    cle = os.environ.get("YT_API_KEY", "").strip()
    if not cle:
        raise ValueError("clé YT_API_KEY absente (secret GitHub non configuré)")
    videos, jeton = [], ""
    while len(videos) < MAX_TENDANCES:
        url = ("https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics"
               "&chart=mostPopular&regionCode=FR&maxResults=50&hl=fr&key=" + cle + jeton)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=ENTETES), timeout=20) as r:
                rep = json.load(r)
        except urllib.error.HTTPError as e:
            raise ValueError(f"YouTube a répondu {e.code}") from None   # n'affiche jamais la clé
        videos += rep.get("items", [])
        if not rep.get("nextPageToken"):
            break
        jeton = "&pageToken=" + rep["nextPageToken"]
    sortie = []
    for v in videos[:MAX_TENDANCES]:
        sn, st = v.get("snippet", {}), v.get("statistics", {})
        date = lire_date(sn.get("publishedAt"))
        if not (v.get("id") and sn.get("title") and date):
            continue
        miniatures = sn.get("thumbnails", {})
        image = next((miniatures[k]["url"] for k in ("high", "medium", "standard", "default")
                      if k in miniatures), None)
        vues = f"{format_vues(st['viewCount'])} de vues · " if st.get("viewCount") else ""
        sortie.append({"source": sn.get("channelTitle") or "YouTube",
                       "titre": nettoyer(sn["title"]),
                       "lien": "https://www.youtube.com/watch?v=" + v["id"],
                       "extrait": couper(vues + re.sub(r"\s+", " ", re.sub(r"https?://\S+", "", nettoyer(sn.get("description")))).strip(), LONGUEUR_EXTRAIT),
                       "image": image_valide(image),
                       "date": date.isoformat()})
    return sortie


def main():
    chemin = sys.argv[1] if len(sys.argv) > 1 else "sources.json"
    with open(chemin, encoding="utf-8") as f:
        sources = json.load(f)

    taches = [(c, s) for c, liste in sources.items() for s in liste]
    with ThreadPoolExecutor(max_workers=16) as pool:
        resultats = list(pool.map(traiter, taches))

    limite = datetime.now(timezone.utc) - timedelta(hours=FENETRE_HEURES)
    sortie = {c: [] for c in sources}
    rapport, ok_par_cat = [], {c: 0 for c in sources}
    for categorie, source, articles, erreur in resultats:
        if source.get("filtre") == "esport":
            seuil = datetime.now(timezone.utc) - timedelta(hours=FENETRE_FILTRE_HEURES)
            retenus = [a for a in articles if a["date"] >= seuil and parle_esport(a)]
        else:
            retenus = [a for a in articles if a["date"] >= limite]
        recents = sorted(retenus, key=lambda a: a["date"], reverse=True)[:MAX_PAR_SOURCE]
        if erreur:
            rapport.append(f"KO   [{categorie}] {source['nom']} - {source['url']} - {erreur}")
        elif not articles:
            rapport.append(f"VIDE [{categorie}] {source['nom']} - {source['url']} - aucun article lisible")
        else:
            ok_par_cat[categorie] += 1
            avec_image = sum(1 for a in recents if a["image"])
            rapport.append(f"OK   [{categorie}] {source['nom']} - {len(recents)} récent(s), {avec_image} avec image")
        for a in recents:
            sortie[categorie].append({
                "source": source["nom"], "titre": a["titre"], "lien": a["lien"],
                "extrait": a["extrait"], "image": a["image"],
                "date": a["date"].isoformat()})

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

    try:
        sortie["Tendances Youtube"] = collecter_tendances()
        etat = f"OK   [Tendances Youtube] YouTube Tendances France - {len(sortie['Tendances Youtube'])} sujet(s)"
        if not sortie["Tendances Youtube"]:
            raise ValueError("aucun sujet lisible")
    except Exception as e:
        etat = f"KO   [Tendances Youtube] YouTube Tendances France - {type(e).__name__}: {e}"
        try:   # on garde les tendances de la dernière collecte réussie
            with open("news.json", encoding="utf-8") as f:
                sortie["Tendances Youtube"] = json.load(f)["categories"].get("Tendances Youtube", [])
        except Exception:
            sortie["Tendances Youtube"] = []
    rapport.append(etat)
    total += len(sortie["Tendances Youtube"])

    maintenant = datetime.now(timezone.utc).isoformat()
    resume = " | ".join(f"{c}: {ok_par_cat[c]}/{len(sources[c])} sources OK" for c in sources)
    with open("rapport.txt", "w", encoding="utf-8") as f:
        f.write(f"Rapport du {maintenant}\n{resume}\n" + "\n".join(sorted(rapport)) + "\n")

    if total == 0:
        print("Aucun article collecté : news.json conservé tel quel.")
        sys.exit(1)
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump({"genere_le": maintenant, "categories": sortie}, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{total} articles collectés ({len(taches)} sources). {resume}")


if __name__ == "__main__":
    main()
