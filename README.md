# Risiparse

Un script qui permet de télécharger les risitas en html et de les convertir en pdf.

Sites supportés : Jeuxvideo.com, Jvarchive.com, Webarchive (Risific)

Pour Webarchive (Risific) voir:

- https://web.archive.org/web/20210526014645/https://risific.fr/

Toujours pour webarchive:

Après il y'a une erreur pour certaines page (même avec le retry à différents niveaux j'ai toujours un 503),
le script renvoie une erreur 503 pour certaines pages (rate limit?, serveur surchargé?), j'arrive à 
en faire charger certains sur mon navigateur en spammant un peu la page.

Si la page se charge dans le navigateur, la solution serait de télécharger l'html (clique droit-> sauvegarder page)
puis utiliser risicompare pour rajouter les parties manquantes.

Ca n'arrive que pour quelques pages dans certains risitas sur webarchive, le comportement sera alors de
signaler que tel page a pas pu être téléchargé et de continuer avec les autres.

Enfin il se peut aussi que la page n'ait tout simplement pas été indexée par la wayback machine et dans ce
cas y'a rien à faire.

Besoin de plus d'infos, sur ce problème n'hésitez pas à m'envoyer un MP ou ouvrir une issue.

2sucres ne marche pas car javascript, faut sortir selenium dans ce cas-là

## Installation

```
python3 -m pip install risiparse
```

## Comment avoir un risitas sans message manquant ni message hors-sujet ?

Voir https://github.com/vichelisdelapaz/risicompare

## Utilisation

```
kenny $ risiparse -h
usage: risiparse.py [-h] [--all-posts] [--no-pdf] [--debug] [--no-download]
                    [-l LINKS [LINKS ...]] [--create-pdfs CREATE_PDFS [CREATE_PDFS ...]]
                    [-i IDENTIFIERS [IDENTIFIERS ...]] [--authors AUTHORS [AUTHORS ...]]
                    [--no-resize-images] [--download-images] [--no-match-author]
                    [--clear-database] [--no-database] [-o OUTPUT_DIR]

options:
  -h, --help            show this help message and exit
  --all-posts           Download all the posts from the author, Default : False
  --no-pdf              Only download html, Default : False
  --debug               Verbose output for the stdout, the debug file always has verbose
                        output on, Default : False
  --no-download         Create pdfs directly from current dir/risitas-html or one specified
                        by -o, Default : False
  -l LINKS [LINKS ...], --links LINKS [LINKS ...]
                        The links file, or links from standard input, Default : current
                        dir/risitas-links
  --create-pdfs CREATE_PDFS [CREATE_PDFS ...]
                        A list of html files path to create pdfs from If this option is not
                        specified with --no-download the pdfs will be created for all html
                        files in risitas-html
  -i IDENTIFIERS [IDENTIFIERS ...], --identifiers IDENTIFIERS [IDENTIFIERS ...]
                        A list of words that are going to be matched by the script, example:
                        a message that has the keyword 'hors-sujet', by adding 'hors-sujet'
                        with this option, the script will match the message that has this
                        keyword, Default : 'chapitre'
  --authors AUTHORS [AUTHORS ...]
                        List of authors to be matched, by default the author of the first
                        post author is considered as the author throughout the whole risitas
  --no-resize-images    When the script 'thinks' that the post contains images and that they
                        are chapters posted in screenshot, it will try to display them to
                        their full scale, Default : False
  --download-images     Whether to download images locally If set, this will change all
                        img[src] link to point to the local images Also this will try to
                        download risitas stickers on webarchive if they have been 404ed,
                        Default : False
  --no-match-author     If the name of the author is pogo and the current post author is
                        pogo111, it will be downloaded this disables this feature, Default :
                        False
  --clear-database      If set, will remove the database, Default : False
  --no-database         If set, this will download a new html file instead of appending to an
                        existing one and not modify records in the database, Default : False
  -o OUTPUT_DIR, --output-dir OUTPUT_DIR
                        Output dir, Default is current dir
```


Cas d'utilisation typique:

La commande ci-dessous permet de télécharger les risitas dans un html puis de les convertir en pdf,
risitas-links est un fichier avec un lien par ligne, -o spécifie le répertoire ou les fichiers doivent
être téléchargés puis convertis dans ~/tmp.

```
risiparse -l risitas-links -o ~/tmp --download-images
```

La hiérarchie suivante sera créée

```
|── risiparse-2021-09-13.log
├── risitas-html
|   ├── images
│   ├── cybercuck1997-au-bout-du-monde-un-khey-au-japon-0.html
│   ├── don_deaurghane-bidasse-sur-le-campustm-0.html
│   ├── don_deaurghane-bidasse-sur-le-campustm-1.html
│   ├── don_deaurghane-bidasse-sur-le-campustm-2.html
│   ├── kelemorph-ma-vie-avec-une-sourde-0.html
│   ├── pogo112-risitas-mon-ancienne-vie-de-celestin-kikouj-0.html
│   └── turkissou9-un-celestin-a-istanbul-0.html
└── risitas-pdf
    ├── brummiekid-lerasmus-en-angleterre-malaise-aventures-et-progres-0.pdf
    ├── cybercuck1997-au-bout-du-monde-un-khey-au-japon-0.pdf
    ├── cybercuck1997-au-bout-du-monde-un-khey-au-japon-1.pdf
    ├── don_deaurghane-bidasse-sur-le-campustm-0.pdf
    ├── kelemorph-ma-vie-avec-une-sourde-0.pdf
    ├── pogo112-risitas-mon-ancienne-vie-de-celestin-kikouj-0.pdf
    └── turkissou9-un-celestin-a-istanbul-0.pdf
```

Si vous relancez la commande le script va directement aller à la dernière page du risitas et vérifier
si il y'a de nouveaux chapitres, le nombre de page, la position du message de l'auteur est gardé 
dans une base de données.

Ce qui veut dire qu'il est possible d'automatiser le script avec un cronjob/script pour le lancer
à une intervalle précise.

```
risiparse -l risitas-links -o ~/tmp
```

Ne pas oublier de mettre l'option `--debug` si rien n'a l'air de se passer pour avoir les détails.

Enfin download-images s'assure que les images soit téléchargées, ce qui est utile pour risicompare et aussi
pour télécharger les sticker sur webarchive lorsque ceux-ci ont été 404ed.

Le script essaiera de télécharger les posts de l'auteur ou d'un nom ressemblant à l'auteur, ex : pogo, pogo111, pogo112, les posts dont le nom de l'auteur contient pogo seront matchés et téléchargés. Utile si l'auteur s'est fait ban.

## Bugs connus

*Ca à l'air d'être règlé après être passé sur le webengine de pyside6 sorti fin septembre*

Lors de la création de pdfs, le script peut se bloquer indéfiniment et le seul moyen de reprendre le contrôle
est de le tuer via le gestionnaire de tâches (penser à quitter le terminal si SIGKILL ne marche pas)
d'ou ça vient? De Qt la page se charge à 80% et ne progresse plus pour une raison que j'ignore
et je ne vais pas implémenter un hack, la vrai solution c'est de regarder dans le code de Qt/chromium.

Vu que ce bug arrive 1 fois sur 10 ça devrait pas trop poser de problème dans la pratique, pour une utilisation
du script avec cron/gestionnaire de tâches il faudra juste spécifier --no-pdf et après surveiller lors de la création des pdfs si il
y'a un problème ou alors utiliser pandoc ou autre solution.

## Autres examples

Télécharger les risitas à partir de répertoire courant/risitas-links, dans rep courant/risitas-html puis convertir dans rep courant/risitas-pdf, les images susceptibles d'être des chapitres seront agrandis.

```
risiparse
```

Télécharger tous les posts de l'auteur, utile si l'approche automatique en a manqué certains
voir risicompare.

```
risiparse --all-posts
```

Ne pas télécharger les risitas, créer des pdfs depuis des fichiers htmls donnés en input, avec -o
foo, les pdfs seront créés dans foo/risitas-pdf/risitas1...

```
risiparse  --no-download -o <foo> --create-pdfs <html_file_path1>,<html_file_path2>, ... <html_file_pathN>
```

Ne pas télécharger les risitas, créer des pdfs depuis un répertoire contenant risitas-html

```
risiparse  --no-download -o <foo>
```

Télécharger uniquement les risitas en html, à partir d'un fichier contenant des liens vers les risitas

```
risiparse  --no-pdf -l <links-file> or <link1> <link2> ... <linkn>
```

Télécharger les risitas sans agrandir les images qui pourraient être des chapitres.

```
risiparse  --no-resize-images
```

Télécharger les posts contenant les mots clés suivants,
peut aussi inclure un regexp. Voir les regexp de python

```
risiparse -i "chapitre" "partie" "chapitre \d"
```

Télécharger les risitas avec une liste d'auteurs fournis, utile si l'auteur utilise des comptes
différents

```
risiparse -l <link1> --no-pdf --authors Example1 Example2
```

Télécharger les images localement et les utiliser dans l'html, utile pour risicompare
et télécharger les images sur wayback machine si ils ont été 404ed, ce qui est surtout
utile pour les vieux risitas.

```
risiparse --download-images --no-pdf
```

Télécharger les risitas sans utiliser la base de données

```
risiparse --no-database
```

En cas de problème avec la base de données, après si y'a un problème autre va falloir
plonger les mains dans le cambouis et utiliser sqlite3 pour éditer à la main.

```
risiparse --clear-database
```

## Tests

```
tox
```
