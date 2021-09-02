#!/usr/bin/python3

import unicodedata
import pathlib
import re
from typing import List

def write_html(title:str, author: str, posts: List, output_dir: str) -> None:
    title_slug = slugify(title, title=True)
    author_slug = slugify(author, title=False)
    ext = "html"
    i = 0
    full_title = f"{author_slug}-{title_slug}-{i}"
    html_path = pathlib.Path(output_dir) / "risitas-html" / (full_title + f".{ext}")
    while html_path.exists():
        i += 1
        full_title = f"{author_slug}-{title_slug}-{i}"
        html_path = pathlib.Path(output_dir) / "risitas-html" / (full_title + f".{ext}")
    with open(html_path, "w", encoding="utf-8") as f:
        html = """
        <!DOCTYPE html>
        <html lang="fr">
        <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Risitas</title>
        </head>
        <body>
        """
        f.write(html)
        for x in posts:
            f.write(str(x[0]))
        html = """
        </body>
        </html>
        """
        f.write(html)


def _remove_risitas(title: str) -> str:
    regexp = re.compile(r"\[risitas\]", re.IGNORECASE)
    return regexp.sub("", title).strip()


def _replace_whitespaces(title: str) -> str:
    title_dashes = title.replace(" ", "-")
    return title_dashes


def slugify(string: str, allow_unicode=False, title:bool = False) -> str:
    if title:
        string = _remove_risitas(string)
        string = _replace_whitespaces(string)
    if allow_unicode:
        string = unicodedata.normalize('NFKC', string)
    else:
        string = unicodedata.normalize('NFKD', string).encode('ascii', 'ignore').decode('ascii')
    string = re.sub(r'[^\w\s-]', '', string.lower())
    return re.sub(r'[-\s]+', '-', string).strip('-_')


def is_jvc_url(url: str) -> bool:
    domain = url.split("/")[2]
    return domain == "jeuxvideo.com" or domain == "www.jeuxvideo.com"


def make_dirs(output_dir: str) -> None:
    (pathlib.Path(output_dir) / "risitas-html").mkdir(exist_ok=True, parents=True)
    (pathlib.Path(output_dir) / "risitas-pdf").mkdir(exist_ok=True, parents=True)
