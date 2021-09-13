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
usage: risiparse.py [-h] [--all-messages] [--no-pdf] [--debug] [--no-download] [-l LINKS [LINKS ...]] [-i IDENTIFIERS [IDENTIFIERS ...]] [--authors AUTHORS [AUTHORS ...]]
                    [--no-resize-images] [--download-images] [--no-match-author] [-o OUTPUT_DIR]

optional arguments:
  -h, --help            show this help message and exit
  --all-messages        Download all the messages from the author. Default : False
  --no-pdf              Default : False
  --debug               Verbose output, Default : False
  --no-download         Default : False
  -l LINKS [LINKS ...], --links LINKS [LINKS ...]
                        The links file, or links from standard input. Default : current dir/risitas-links
  -i IDENTIFIERS [IDENTIFIERS ...], --identifiers IDENTIFIERS [IDENTIFIERS ...]
                        Give a list of words that are going to be matched by the script, example: a message that has the keyword 'hors-sujet', by adding 'hors-sujet' with this option,the
                        script will match the message that has this keyword. Default : chapitre
  --authors AUTHORS [AUTHORS ...]
                        List of authors to be matched, by default the author of the first post author is considered as the author throughout the whole risitas Default : Empty
  --no-resize-images    When the script 'thinks' that the post contains imagesand that they are chapters posted in screenshot, it will try to display them to their full width Default : False
  --download-images     Whether to download images locally. If set, this will change all img[src] link to point to the local images Default : False
  --no-match-author     If the name of the author is pogo and the current post author is pogo111, it will be downloaded, this disables this feature Default : False
  -o OUTPUT_DIR, --output-dir OUTPUT_DIR
                        Output dir, Default is current dir
```

Le script essaiera de télécharger les posts de l'auteur ou d'un nom ressemblant à l'auteur, ex : pogo, pogo111, pogo112, les messages dont le nom de l'auteur contient pogo seront matchés et téléchargés. Utile si l'auteur s'est fait ban.

En l'état actuel le script ne copie pas les messages au fur et à mesure, c'est à dire que si vous relancez le téléchargement d'un même risitas
il va retélécharger tous les messages.
Et si par exemple un message a été 410 entre 2 téléchargements, il faudrait juste copier l'html du message manquant à la main dans le
fichier html que vous venez de télécharger.

Aussi si il y'a des images qui ont été 404ed, le script essaiera de trouver une version de l'image
sur webarchive, à activer avec --download-images

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

Ne pas oublier de mettre l'option `--debug` si rien n'a l'air de se passer pour avoir les détails.

Enfin download-images s'assure que les images soit téléchargés, ce qui est utile pour risicompare et aussi
pour télécharger les sticker sur webarchive lorsque ceux-ci ont été 404ed.

Télécharger les risitas à partir de répertoire courant/risitas-links, dans rep courant/risitas-html puis convertir dans rep courant/risitas-pdf, les images susceptibles d'être des chapitres seront agrandis.

```
risiparse
```

Télécharger tous les messages de l'auteur

```
risiparse --all-messages
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

Télécharger les messages contenant les mots clés suivants,
peut aussi inclure un regexp. Voir les regexp de python

```
risiparse -i "chapitre" "partie" "chapitre \d"
```

Télécharger les images localement et les utiliser dans l'html, utile dans le future
si j'ai le temps de développer un GUI

```
risiparse --download-images
```
