#!/usr/bin/env python3
"""
Télécharge les scrutins et les députés depuis l'open data de l'Assemblée nationale
et les convertit en petits fichiers JSON lus par index.html.

Usage :  python3 update.py            (écrit dans ./data/)
Cron :   0 7 * * *  cd /chemin/hemicycle && python3 update.py >> update.log 2>&1

Aucune dépendance : bibliothèque standard Python 3.8+.
"""
import io, json, os, re, sys, html, tempfile, zipfile, urllib.request, datetime

LEGISLATURE = os.environ.get("AN_LEGISLATURE", "17")
BASE = f"https://data.assemblee-nationale.fr/static/openData/repository/{LEGISLATURE}"
URL_SCRUTINS = os.environ.get("AN_URL_SCRUTINS", f"{BASE}/loi/scrutins/Scrutins.json.zip")
URL_ACTEURS = os.environ.get(
    "AN_URL_ACTEURS",
    f"{BASE}/amo/deputes_actifs_mandats_actifs_organes/AMO10_deputes_actifs_mandats_actifs_organes.json.zip",
)
URL_DOSSIERS = os.environ.get("AN_URL_DOSSIERS", f"{BASE}/loi/dossiers_legislatifs/Dossiers_Legislatifs.json.zip")
URL_AGENDA = os.environ.get("AN_URL_AGENDA", f"{BASE}/vp/reunions/Agenda.json.zip")
URL_AMENDEMENTS = os.environ.get("AN_URL_AMENDEMENTS", f"{BASE}/loi/amendements_div_legis/Amendements.json.zip")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def arr(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def txt(x):
    """Les champs AN sont parfois {'#text': ...} ou {'@xsi:nil': 'true'}."""
    if isinstance(x, dict):
        return x.get("#text") or ""
    return x or ""


def download(url):
    print(f"Téléchargement {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "hemicycle-local/1.0"})
    tmp = tempfile.TemporaryFile()
    with urllib.request.urlopen(req, timeout=600) as r:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            tmp.write(chunk)
    tmp.seek(0)
    return zipfile.ZipFile(tmp)


def iter_json(zf):
    for name in zf.namelist():
        if name.endswith(".json"):
            with zf.open(name) as f:
                try:
                    yield name, json.load(f)
                except json.JSONDecodeError:
                    print(f"  ignoré (JSON invalide) : {name}")


def load_acteurs():
    zf = download(URL_ACTEURS)
    groupes, deputes = {}, {}
    for name, d in iter_json(zf):
        if "organe" in d:
            o = d["organe"]
            if o.get("codeType") == "GP":
                groupes[txt(o.get("uid"))] = {
                    "abrege": o.get("libelleAbrege") or o.get("libelleAbrev") or "",
                    "libelle": o.get("libelle") or "",
                }
        elif "acteur" in d:
            a = d["acteur"]
            uid = txt(a.get("uid"))
            ident = (a.get("etatCivil") or {}).get("ident") or {}
            gp = ""
            for m in arr((a.get("mandats") or {}).get("mandat")):
                if m.get("typeOrgane") == "GP" and not txt(m.get("dateFin")):
                    gp = txt(((m.get("organes") or {}).get("organeRef")))
            deputes[uid] = {"nom": f"{ident.get('prenom', '')} {ident.get('nom', '')}".strip(), "gp": gp}
    print(f"  {len(deputes)} députés, {len(groupes)} groupes")
    return groupes, deputes


def votants(decompte, key):
    bloc = (decompte or {}).get(key) or {}
    return [txt(v.get("acteurRef")) for v in arr(bloc.get("votant")) if isinstance(v, dict)]


def notice(msg):
    """Visible dans l'onglet Actions de GitHub (et dans la console ailleurs)."""
    print(f"::notice::{msg}" if os.environ.get("GITHUB_ACTIONS") else msg)


def strip_html(x, limit=1500):
    t = re.sub(r"<br\s*/?>|</p>", "\n", txt(x) or "", flags=re.I)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    t = re.sub(r"[ \t\xa0]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n\n", t).strip()
    return t if len(t) <= limit else t[:limit].rsplit(" ", 1)[0] + " […]"


TEXTE_RE = re.compile(r"((?:du |de la |des )?(?:projet|proposition) de (?:loi|résolution)[^()]*?)\s*(?:\(([^)]*)\))?\.?$", re.I)


def analyse_titre(titre):
    """Découpe le titre officiel en champs, sans rien ajouter."""
    t = titre.strip()
    low = t.lower()
    if "sous-amendement" in low:
        nature = "Sous-amendement"
    elif "amendement" in low:
        nature = "Amendement"
    elif "motion de censure" in low:
        nature = "Motion de censure"
    elif "motion" in low:
        nature = "Motion"
    elif low.startswith("l'ensemble") or "l'ensemble du" in low or "l'ensemble de la" in low:
        nature = "Vote sur l'ensemble du texte"
    elif low.startswith("l'article") or low.startswith("les articles"):
        nature = "Article"
    elif "déclaration du gouvernement" in low:
        nature = "Déclaration du Gouvernement"
    else:
        nature = ""
    info = {"nature": nature}
    m = re.search(r"amendement n[°o]\s*(\d+)", t, re.I)
    if m:
        info["amendement"] = int(m.group(1))
    m = re.search(r"\b(?:à|après|avant) l'article ((?:premier|liminaire|\d+)(?:\s+(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies|(?-i:[A-Z])))*)\b", t, re.I) \
        or re.search(r"^l'article ((?:premier|liminaire|\d+)(?:\s+(?:bis|ter|quater|quinquies|(?-i:[A-Z])))*)\b", t, re.I)
    if m:
        info["article"] = m.group(1)
    m = TEXTE_RE.search(t)
    if m:
        info["texte"] = re.sub(r"^(du|de la|des) ", "", m.group(1).strip(), flags=re.I)
        if m.group(2):
            info["lecture"] = m.group(2)
    return info


def load_scrutins():
    zf = download(URL_SCRUTINS)
    index, details = [], {}
    for name, d in iter_json(zf):
        s = d.get("scrutin")
        if not s:
            continue
        num = int(txt(s.get("numero")) or 0)
        groupes = []
        for g in arr(((((s.get("ventilationVotes") or {}).get("organe") or {}).get("groupes") or {}).get("groupe"))):
            dn = (g.get("vote") or {}).get("decompteNominatif") or {}
            groupes.append({
                "po": txt(g.get("organeRef")),
                "nb": int(txt(g.get("nombreMembresGroupe")) or 0),
                "pour": votants(dn, "pours"),
                "contre": votants(dn, "contres"),
                "abst": votants(dn, "abstentions"),
                "nv": votants(dn, "nonVotants"),
            })
        titre = txt(s.get("titre")) or txt((s.get("objet") or {}).get("libelle"))
        sort = txt((s.get("sort") or {}).get("code"))
        date = txt(s.get("dateScrutin"))
        tv = s.get("typeVote") or {}
        typ = txt(tv.get("libelleTypeVote"))
        syn = s.get("syntheseVote") or {}
        obj = s.get("objet") or {}
        info = analyse_titre(titre)
        info.update({
            "majorite": txt(tv.get("typeMajorite")),
            "demandeur": txt((s.get("demandeur") or {}).get("texte")),
            "votants": txt(syn.get("nombreVotants")),
            "exprimes": txt(syn.get("suffragesExprimes")),
            "requis": txt(syn.get("nbrSuffragesRequis")),
            "seance": txt(s.get("seanceRef")),
            "seanceNum": txt(s.get("quantiemeJourSeance")),
            "dossierRef": txt(obj.get("dossierLegislatif")),
        })
        info = {k: v for k, v in info.items() if v not in ("", None)}
        index.append({"n": num, "date": date, "titre": titre, "sort": sort, "type": typ})
        details[num] = {"n": num, "date": date, "titre": titre, "sort": sort, "type": typ, "info": info, "groupes": groupes}
    index.sort(key=lambda x: (x["date"], x["n"]), reverse=True)
    print(f"  {len(index)} scrutins")
    return index, details


REF_TEXTE = re.compile(r"^(PRJL|PION|PNRE|RION|TAP|PRO|RAPP|AVIS|TA)\w*\d")


def refs_textes(obj, out):
    """Toutes les références de textes citées dans un dossier (actes, textes associés, adoptés…)."""
    if isinstance(obj, dict):
        for v in obj.values():
            refs_textes(v, out)
    elif isinstance(obj, list):
        for v in obj:
            refs_textes(v, out)
    elif isinstance(obj, str) and REF_TEXTE.match(obj):
        out.add(obj)


def enrich_dossiers(details):
    zf = download(URL_DOSSIERS)
    dossiers, par_texte = {}, {}
    for _, d in iter_json(zf):
        dp = d.get("dossierParlementaire")
        if not dp:
            continue
        uid = txt(dp.get("uid"))
        t = dp.get("titreDossier") or {}
        info = {"titre": txt(t.get("titre")), "chemin": txt(t.get("titreChemin"))}
        dossiers[uid] = info
        refs = set()
        refs_textes(dp.get("actesLegislatifs"), refs)
        for r in refs:
            par_texte.setdefault(r, info)
    direct = 0
    for d in details.values():
        i = d["info"]
        doss = dossiers.get(i.get("dossierRef")) or par_texte.get(i.get("texteRef"))
        if doss:
            i["dossier"] = doss
            direct += 1
    # Même texte (même libellé officiel) => même dossier
    par_nom = {}
    for d in details.values():
        i = d["info"]
        if "dossier" in i and i.get("texte"):
            par_nom.setdefault((i["texte"].lower(), i.get("lecture", "")), i["dossier"])
            par_nom.setdefault((i["texte"].lower(), ""), i["dossier"])
    propage = 0
    for d in details.values():
        i = d["info"]
        if "dossier" not in i and i.get("texte"):
            doss = par_nom.get((i["texte"].lower(), i.get("lecture", ""))) or par_nom.get((i["texte"].lower(), ""))
            if doss:
                i["dossier"] = doss
                propage += 1
    notice(f"Dossiers : {len(dossiers)} lus, {len(par_texte)} textes indexés, {direct} scrutins reliés directement, {propage} par le même texte, sur {len(details)}")


def enrich_agenda(details):
    seances = {d["info"].get("seance") for d in details.values()} - {None}
    zf = download(URL_AGENDA)
    debut = {}
    for _, d in iter_json(zf):
        r = d.get("reunion")
        if not r:
            continue
        uid = txt(r.get("uid"))
        if uid in seances:
            debut[uid] = txt(r.get("timeStampDebut"))
    n = 0
    for d in details.values():
        ts = debut.get(d["info"].get("seance"))
        if ts:
            d["info"]["debutSeance"] = ts
            n += 1
    notice(f"Agenda : heure de début trouvée pour {n} scrutins sur {len(details)}")


def enrich_amendements(details):
    voulus = {}
    for d in details.values():
        i = d["info"]
        if "amendement" in i and "seance" in i:
            voulus.setdefault((i["seance"], i["amendement"]), []).append(d)
    zf = download(URL_AMENDEMENTS)
    lus = trouves = 0
    for name in zf.namelist():
        if not name.endswith(".json"):
            continue
        try:
            with zf.open(name) as f:
                a = json.load(f).get("amendement")
        except Exception:
            continue
        if not a:
            continue
        lus += 1
        seance = txt(a.get("seanceDiscussionRef"))
        m = re.match(r"\d+", txt((a.get("identification") or {}).get("numeroLong")) or "")
        cible = voulus.get((seance, int(m.group(0)))) if (seance and m) else None
        if not cible:
            continue
        contenu = ((a.get("corps") or {}).get("contenuAuteur") or {})
        expose = strip_html(contenu.get("exposeSommaire"))
        auteur = txt((a.get("signataires") or {}).get("libelle"))
        texte_ref = txt(a.get("texteLegislatifRef"))
        for d in cible:
            if texte_ref:
                d["info"]["texteRef"] = texte_ref
            if expose:
                d["info"]["expose"] = expose
            if auteur:
                d["info"]["auteur"] = strip_html(auteur, 300)
        trouves += 1
    notice(f"Amendements : {lus} lus, {trouves} reliés à un scrutin sur {len(voulus)} amendements votés")


def write(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def main():
    os.makedirs(os.path.join(OUT, "s"), exist_ok=True)
    groupes, deputes = load_acteurs()
    index, details = load_scrutins()
    for etape in (enrich_agenda, enrich_amendements, enrich_dossiers):
        try:
            etape(details)
        except Exception as e:
            notice(f"{etape.__name__} ignoré : {e}")
    for num, d in details.items():
        write(os.path.join(OUT, "s", f"{num}.json"), d)
    write(os.path.join(OUT, "deputes.json"), {"groupes": groupes, "deputes": deputes})
    write(os.path.join(OUT, "index.json"), {
        "legislature": LEGISLATURE,
        "maj": datetime.datetime.now().isoformat(timespec="minutes"),
        "source": URL_SCRUTINS,
        "scrutins": index,
    })
    print("Terminé.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Erreur : {e}", file=sys.stderr)
        print("Si l'URL a changé, vérifiez-la sur data.assemblee-nationale.fr et passez-la via "
              "AN_URL_SCRUTINS / AN_URL_ACTEURS.", file=sys.stderr)
        sys.exit(1)
