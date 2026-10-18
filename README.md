# Hémicycle des votes (auto-hébergé)

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

## Limites

- Seuls les scrutins publics ont un détail par député ; les votes à main levée n'apparaissent pas.
- Les votes par délégation comptent comme présents.
- Les sièges sont rangés par groupe, de gauche à droite, pas à la place physique de chaque député.
