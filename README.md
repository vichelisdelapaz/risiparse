# Risiparse

Un script qui permet de télécharger les risitas en html et de les convertir en pdf.

Testé sous arch linux.

## Installation

```
git clone https://github.com/vichelisdelapaz/risiparse
cd risiparse
pip3 install -r requirements.txt
```

## Utilisation

```
kenny $ python3 risiparse.py -h
usage: risiparse.py [-h] [-b] [-p] [--disable-html] [-l LINKS] [-i IDENTIFIERS [IDENTIFIERS ...]]
                    [--no-resize-images] [-o OUTPUT_DIR]

optional arguments:
  -h, --help            show this help message and exit
  -b, --bulk            Use this option if you want to download all the messages from the author.
                        Default : False
  -p, --create-pdf      Enable/Disable Pdf creation, Default : True
  --disable-html        Enable/Disable Html Download, Default : False
  -l LINKS, --links LINKS
                        The links file, Default : current dir/risitas-links
  -i IDENTIFIERS [IDENTIFIERS ...], --identifiers IDENTIFIERS [IDENTIFIERS ...]
                        Give a list of words that are going to be matched by the script, example: a
                        message that has the keyword 'hors-sujet', by adding 'hors-sujet' with this
                        option, the script will match the message that has this keyword. Default :
                        Chapitre
  --no-resize-images    When the script 'thinks' that the post contains images and that they are
                        chapters posted in screenshot, it will try to display them to their full width,
                        Default : False
  -o OUTPUT_DIR, --output-dir OUTPUT_DIR
                        Output dir, Default is current dir
```

Télécharger les risitas à partir de répertoire courant/risitas-links, dans rep courant/risitas-html puis convertir dans rep courant/risitas-pdf, les images susceptibles d'être des chapitres seront agrandis.

```
python3 risiparse.py
```

Télécharger tous les messages de l'auteur

```
python3 risiparse.py --bulk
```

Ne pas télécharger les risitas, créer des pdfs depuis un répertoire contenant risitas-html

```
python3 risiparse.py  --disable-html -o <foo>
```

Télécharger uniquement les risitas en html, à partir d'un fichier contenant des liens vers les risitas

```
python3 risiparse.py  -p -l <links-file>
```

Télécharger les risitas sans agrandir les images qui pourraient être des chapitres.

```
python3 risiparse.py  --no-resize-images
```

Télécharger les messages contenant les mots clés suivants,
peut aussi inclure un regexp. Voir les regexp de python

```
python3 risiparsE.py -i chapitre partie
```