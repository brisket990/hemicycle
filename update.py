#!/usr/bin/env python3
"""
Télécharge les scrutins et les députés depuis l'open data de l'Assemblée nationale
et les convertit en petits fichiers JSON lus par index.html.

Usage :  python3 update.py            (écrit dans ./data/)
Cron :   0 7 * * *  cd /chemin/hemicycle && python3 update.py >> update.log 2>&1

Aucune dépendance : bibliothèque standard Python 3.8+.
"""
import io, json, os, sys, zipfile, urllib.request, datetime

LEGISLATURE = os.environ.get("AN_LEGISLATURE", "17")
BASE = f"https://data.assemblee-nationale.fr/static/openData/repository/{LEGISLATURE}"
URL_SCRUTINS = os.environ.get("AN_URL_SCRUTINS", f"{BASE}/loi/scrutins/Scrutins.json.zip")
URL_ACTEURS = os.environ.get(
    "AN_URL_ACTEURS",
    f"{BASE}/amo/deputes_actifs_mandats_actifs_organes/AMO10_deputes_actifs_mandats_actifs_organes.json.zip",
)
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
    with urllib.request.urlopen(req, timeout=300) as r:
        return zipfile.ZipFile(io.BytesIO(r.read()))


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
        typ = txt((s.get("typeVote") or {}).get("libelleTypeVote"))
        index.append({"n": num, "date": date, "titre": titre, "sort": sort, "type": typ})
        details[num] = {"n": num, "date": date, "titre": titre, "sort": sort, "type": typ, "groupes": groupes}
    index.sort(key=lambda x: (x["date"], x["n"]), reverse=True)
    print(f"  {len(index)} scrutins")
    return index, details


def write(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def main():
    os.makedirs(os.path.join(OUT, "s"), exist_ok=True)
    groupes, deputes = load_acteurs()
    index, details = load_scrutins()
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
