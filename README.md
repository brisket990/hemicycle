# Hémicycle des votes

Site : https://brisket990.github.io/hemicycle/

Affiche chaque scrutin public de l'Assemblée nationale sous forme d'hémicycle :
un point par député, vert = pour, rouge = contre, gris = abstention,
cercle vide = présent sans voter, gris clair = absent.

Les données viennent directement de l'open data officiel
(data.assemblee-nationale.fr), sans retouche.

## Installation

```bash
cd hemicycle
python3 update.py              # télécharge et convertit (~1 à 2 min)
python3 -m http.server 8080    # puis ouvrir http://IP-du-serveur:8080
```

Python 3.8+ suffit, aucune dépendance. Vous pouvez aussi servir le dossier
avec votre reverse proxy habituel (nginx, Caddy…) : ce sont des fichiers statiques.

## Mise à jour automatique

```
0 7 * * *  cd /chemin/hemicycle && python3 update.py >> update.log 2>&1
```

## Si le téléchargement échoue

L'Assemblée change parfois l'emplacement de ses fichiers. Récupérez les
nouvelles adresses sur data.assemblee-nationale.fr (rubriques « Scrutins »
et « Députés actifs ») et passez-les en variables :

```bash
AN_URL_SCRUTINS="https://…/Scrutins.json.zip" \
AN_URL_ACTEURS="https://…/AMO10_….json.zip" python3 update.py
```

`AN_LEGISLATURE` (par défaut 17) change la législature.

## Informations affichées par scrutin

Objet du vote, texte et lecture, article, numéro et auteur de l'amendement,
demandeur du scrutin, majorité requise, lien vers le dossier, et l'exposé
sommaire de l'auteur quand il existe. Tout vient des fichiers officiels
(scrutins, agenda, dossiers législatifs, amendements). L'heure affichée est
celle de l'ouverture de la séance : l'heure exacte de chaque vote n'est pas publiée.

## Limites

- Seuls les scrutins publics ont un détail par député ; les votes à main levée n'apparaissent pas.
- Les votes par délégation comptent comme présents.
- Le plan des sièges vient de la page officielle « Situez votre député » ; si elle change de structure, le site revient automatiquement à l'affichage par groupe.
- Sur le plan, chaque siège montre son occupant actuel : pour un vote ancien, un député remplacé depuis n'y figure pas (il reste compté dans les totaux).
