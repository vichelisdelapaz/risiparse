#!/usr/bin/python3

import unicodedata
import pathlib
import re
import sys
import argparse
import logging
from risiparse import html_to_pdf, sites_selectors

from typing import List

def write_html(
        title:str,
        author: str,
        posts: List,
        output_dir: str,
) -> None:
    title_slug = slugify(title, title=True)
    author_slug = slugify(author, title=False)
    ext = "html"
    i = 0
    full_title = f"{author_slug}-{title_slug}-{i}"
    html_path = (
        pathlib.Path(output_dir) /
        "risitas-html" /
        (full_title + f".{ext}")
    )
    while html_path.exists():
        i += 1
        full_title = f"{author_slug}-{title_slug}-{i}"
        html_path = (
            pathlib.Path(output_dir) /
            "risitas-html" /
            (full_title + f".{ext}")
        )
    with open(html_path, "w", encoding="utf-8") as f:
        html = (
            """<!DOCTYPE html>
            <html lang='fr'>
            <head>
            <meta charset='UTF-8'>
            <meta name='viewport' content='width=device-width, initial-scale=1.0'>
            <title>Risitas</title>
            </head>
            <body>"""
        )
        f.write(html)
        for x in posts:
            f.write(str(x[0]))
        html = (
            """</body>
            </html>"""
        )
        f.write(html)


def _remove_risitas(title: str) -> str:
    regexp = re.compile(r"\[risitas\]", re.IGNORECASE)
    return regexp.sub("", title).strip()


def _replace_whitespaces(title: str) -> str:
    title_dashes = title.replace(" ", "-")
    return title_dashes


def slugify(
        string: str,
        allow_unicode=False,
        title:bool = False
) -> str:
    if title:
        string = _remove_risitas(string)
        string = _replace_whitespaces(string)
    if allow_unicode:
        string = unicodedata.normalize('NFKC', string)
    else:
        string = unicodedata.normalize(
            'NFKD', string
        ).encode(
            'ascii', 'ignore'
        ).decode('ascii')
    string = re.sub(r'[^\w\s-]', '', string.lower())
    return re.sub(r'[-\s]+', '-', string).strip('-_')


def _strip_www_component(url :str) -> str:
    domain = re.sub(r"www." , "", url)
    return domain


def get_domain(url: str) -> str:
    domain = url.split("/")[2]
    domain = _strip_www_component(domain)
    return domain


def make_dirs(output_dir: str) -> None:
    (
        pathlib.Path(output_dir) / "risitas-html"
    ).mkdir(exist_ok=True, parents=True)
    (
        pathlib.Path(output_dir) / "risitas-pdf"
    ).mkdir(exist_ok=True, parents=True)


def get_selectors_and_site(link: str) -> None:
    domain = get_domain(link)
    selectors = ""
    site = ""
    if domain == "jeuxvideo.com":
        selectors = sites_selectors.Jvc
        site = "jvc"
    elif domain == "jvarchive.com":
        selectors = sites_selectors.Jvarchive
        site = "jvarchive"
    elif domain == "2sucres.org":
        selectors = sites_selectors.Deuxsucres
        site = "2sucres"
    return selectors, site


def create_pdfs(output_dir: str) -> None:
    html_folder_path = pathlib.Path(output_dir) / "risitas-html"
    htmls = list(html_folder_path.glob("*.html"))
    if htmls:
        app = html_to_pdf.QtWidgets.QApplication([])
        page = html_to_pdf.PdfPage(output_dir)
        logging.info(f"Creating pdfs...")
        page.convert(htmls)
        sys.exit(app.exec_())


def read_links(links_file: str) -> List:
    with open(links_file) as f:
        page_links = [line.strip() for line in f if line.strip() != '']
    return page_links


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    default_links = str(
        (pathlib.Path().cwd() / "risitas-links")
    )
    parser.add_argument(
        "--all-messages",
        action="store_true",
        default=False,
        help=(
            "Download all the messages from the author."
            "Default : False"
        )
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        default=False,
        help="Default : False"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Verbose output, Default : False"
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        default=False,
        help="Default : False"
    )
    parser.add_argument(
        "-l","--links",
        action="store",
        default=default_links,
        help="The links file, Default : current dir/risitas-links"
    )
    # Take a list of identifiers
    parser.add_argument(
        '-i',
        '--identifiers',
        nargs='+',
        help=(
            "Give a list of words that are going to be matched by the script,"
            "example: a message that has the keyword 'hors-sujet',"
            "by adding 'hors-sujet' with this option,"
            "the script will match the message that has this keyword. "
            "Default : chapitre"
        ),
        required=False,
        default=["chapitre"],
        type=str
    )
    # Authors if author has multiple accounts
    parser.add_argument(
        '--authors',
        nargs='+',
        help=(
            "List of authors to be matched, by default the author of "
            "the first post author is considered as the author throughout the whole risitas "
            "Default : Empty"
        ),
        required=False,
        default=[],
        type=str
    )
    # Images
    parser.add_argument(
        '--no-resize-images',
        help=(
            "When the script 'thinks' that the post contains images"
            "and that they are chapters posted in screenshot,"
            "it will try to display them to their full width "
            "Default : False"
        ),
        action="store_true",
        required=False,
        default=False
    )
    parser.add_argument(
        '--download-images',
        help=(
            "Whether to download images locally"
            "If set, this will change all img[src] link to point to the local images"
            "Default : False"
        ),
        action="store_true",
        required=False,
        default=False
    )
    # Output dir
    parser.add_argument(
        '-o',
        '--output-dir',
        action="store",
        help="Output dir, Default is current dir",
        default=str(pathlib.Path.home())
    )
    args = parser.parse_args()
    return args


