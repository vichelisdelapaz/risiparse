#!/usr/bin/python3

"""This module just regroup some routines"""

from typing import List, Union
import tempfile
import unicodedata
import pathlib
import re
import sys
import argparse
import logging

from urllib.parse import urlparse
from PyPDF2 import PdfFileMerger, PdfFileReader
from bs4 import BeautifulSoup
from risiparse import html_to_pdf, sites_selectors


def write_html(
        title: str,
        author: str,
        posts: List,
        output_dir: 'pathlib.Path',
) -> 'pathlib.Path':
    title_slug = slugify(title, title=True)
    author_slug = slugify(author, title=False)
    ext = "html"
    i = 0
    full_title = f"{author_slug}-{title_slug}-{i}"
    html_path = (
        output_dir /
        "risitas-html" /
        (full_title + f".{ext}")
    )
    while html_path.exists():
        i += 1
        full_title = f"{author_slug}-{title_slug}-{i}"
        html_path = (
            output_dir /
            "risitas-html" /
            (full_title + f".{ext}")
        )
    with open(html_path, "w", encoding="utf-8") as f:
        html = (
            """<!DOCTYPE html>
            <html lang='fr'>
            <head>
            <meta charset='UTF-8'>
            <meta name='viewport' \
            content='width=device-width, initial-scale=1.0'>
            <title>Risitas</title>
            </head>
            <body>"""
        )
        f.write(html)
        for paragraph in posts:
            f.write(str(paragraph[0]).replace("’", "'"))
        html = (
            """</body>
            </html>"""
        )
        f.write(html)
        logging.info(f"Wrote {html_path}")
    return html_path


def append_html(html_path: 'pathlib.Path', risitas_html: 'BeautifulSoup'):
    with open(html_path, encoding='utf-8') as f:
        soup = BeautifulSoup(f, features="lxml")
    for new_chapter in risitas_html:
        soup.body.insert(len(soup.body.contents), new_chapter[0])
        logging.debug(f"Appending {new_chapter[0]} ...")
    with open(html_path, "w", encoding='utf-8') as f:
        f.write(soup.decode().replace("’", "'"))
    logging.info(f"The chapters have been appended to {html_path}")


def _remove_risitas(title: str) -> str:
    regexp = re.compile(r"\[risitas\]", re.IGNORECASE)
    return regexp.sub("", title).strip()


def _replace_whitespaces(title: str) -> str:
    title_dashes = title.replace(" ", "-")
    return title_dashes


def slugify(
        string: str,
        allow_unicode: bool = False,
        title: bool = False
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


def _strip_www_component(url: str) -> str:
    domain = re.sub(r"www.", "", url)
    return domain


def get_domain(url: str) -> str:
    domain = url.split("/")[2]
    domain = _strip_www_component(domain)
    return domain


def make_dirs(output_dir: 'pathlib.Path') -> None:
    (output_dir / "risitas-html").mkdir(exist_ok=True, parents=True)
    (output_dir / "risitas-pdf").mkdir(exist_ok=True, parents=True)


def get_selectors_and_site(
        link: str
) -> tuple[
    Union[
        'sites_selectors.Jvc',
        'sites_selectors.Jvarchive',
        'sites_selectors.Webarchive'
    ],
    str
]:
    domain = get_domain(link)
    if domain == "jeuxvideo.com":
        selectors = sites_selectors.Jvc
    elif domain == "jvarchive.com":
        selectors = sites_selectors.Jvarchive
    elif domain == "web.archive.org":
        selectors = sites_selectors.Webarchive
    return selectors


def create_pdfs(
        output_dir: 'pathlib.Path',
        html_user: List['pathlib.Path'] = None,
        html_download: List['pathlib.Path'] = None,
        all_pdfs = False,
) -> None:
    html_folder_path = output_dir / "risitas-html"
    htmls = []
    pdf_to_create = dict()
    if not html_user and not html_download and all_pdfs:
        htmls = list(html_folder_path.glob("*.html"))
    elif html_user:
        htmls = html_user
    elif html_download:
        htmls = html_download
    # Testing if htmls are too big
    html_part_tmpdir = tempfile.TemporaryDirectory()
    (pathlib.Path(f"{html_part_tmpdir.name}") / "risitas-pdf").mkdir()
    for html in htmls:
        if html.stat().st_size >= 3670016:
            logging.info(
                f"The html file {html} is too big and will be splitted into multiple parts, "
                "then pdfs will be created and merged back into one single pdf."
            )
            data = BeautifulSoup(
                html.read_text(encoding='utf-8'), features="lxml"
            )
            divs = data.select("div")
            start = 0
            end = 30
            for _ in range(0, len(divs), 30):
                file_path = pathlib.Path(
                    f"{html_part_tmpdir.name}/{html.name}"
                    f"-part-{start}-to-{end}.html"
                )
                with open(file_path, "w", encoding='utf-8') as f:
                    for count, div in enumerate(divs[start:end], 1):
                        f.write(div.decode())
                        logging.debug(f"Appended div to {file_path}")
                pdf_path = str(html).replace("html", "pdf")
                if pdf_path not in pdf_to_create:
                    pdf_to_create[pdf_path] = [file_path]
                else:
                    pdf_to_create[pdf_path].append(file_path)
                start = end
                end += 30
                file_path = pathlib.Path(f"{html}-part-{start}-to-{end}.html")
            htmls.remove(html)
    app = html_to_pdf.QtWidgets.QApplication([])
    if htmls:
        page = html_to_pdf.PdfPage(output_dir)
        logging.info("Creating pdfs...")
        page.convert(htmls)
        app.exec()
    if pdf_to_create:
        for k, v in pdf_to_create.items():
            merger = PdfFileMerger()
            output_dir = pathlib.Path(f"{html_part_tmpdir.name}")
            page = html_to_pdf.PdfPage(output_dir)
            page.convert(v)
            app.exec()
            pdfs_to_merge = page.get_pdfs_path()
            for filename in pdfs_to_merge:
                merger.append(filename)
            with open(f"{k}", 'wb') as f:
                merger.write(f)
                logging.info(f"Merged pdf parts into {k}")


def read_links(links_file: pathlib.Path) -> List:
    links_file = links_file.expanduser().resolve()
    with open(links_file, encoding='utf-8') as f:
        page_links = [line.strip() for line in f if line.strip() != '']
    return page_links


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    default_links = [pathlib.Path().cwd() / "risitas-links"]
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
        help="Default : False, only download html"
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
        help=(
            "Default : False, Create pdfs directly from current dir "
            "or one specified by -o"
        )
    )
    # Links
    parser.add_argument(
        "-l", "--links",
        action="store",
        nargs='+',
        default=default_links,
        help=(
            "The links file, or links from standard input, "
            "Default : current dir/risitas-links"
        )
    )
    # Pdfs to create
    parser.add_argument(
        "--create-pdfs",
        nargs='+',
        help=(
            "A list of html files path to create pdfs from "
            "If this option is not specified with --no-download "
            "the pdfs will be created for all html files in risitas-html"
        ),
        type=lambda p: pathlib.Path(p).expanduser().resolve()
    )
    # Take a list of identifiers
    parser.add_argument(
        '-i',
        '--identifiers',
        nargs='+',
        help=(
            "Give a list of words that are going to be matched by the script, "
            "example: a message that has the keyword 'hors-sujet', "
            "by adding 'hors-sujet' with this option, "
            "the script will match the message that has this keyword. "
            "Default : 'chapitre'"
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
            "the first post author is considered as the author "
            "throughout the whole risitas, "
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
            "When the script 'thinks' that the post contains images "
            "and that they are chapters posted in screenshot, "
            "it will try to display them to their full width, "
            "Default : False"
        ),
        action="store_true",
        required=False,
        default=False
    )
    parser.add_argument(
        '--download-images',
        help=(
            "Whether to download images locally "
            "If set, this will change all img[src] link to point "
            "to the local images "
            "Also this will try to download risitas sticker on webarchive "
            "if they have been 404ed, "
            "Default : False"
        ),
        action="store_true",
        required=False,
        default=False
    )
    # Match author
    parser.add_argument(
        "--no-match-author",
        action="store_true",
        default=False,
        help=(
            "If the name of the author is pogo and the current "
            "post author is pogo111, it will be downloaded "
            "this disables this feature, "
            "Default : False"
        )
    )
    # Clear database
    parser.add_argument(
        "--clear-database",
        action="store_true",
        default=False,
        help=(
            "If set, will remove the database, "
            "Default : False"
        )
    )
    # Don't use the database
    parser.add_argument(
        "--no-database",
        action="store_true",
        default=False,
        help=(
            "If set, this will download a new html file "
            "instead of appending to an existing one and not modify records "
            "in the database, "
            "Default : False"
        )
    )
    # Output dir
    parser.add_argument(
        '-o',
        '--output-dir',
        action="store",
        help="Output dir, Default is current dir",
        default=pathlib.Path.cwd(),
        type=pathlib.Path
    )
    args = parser.parse_args()
    return args


def contains_webarchive(archive_link: str) -> bool:
    return bool("web.archive.org" in archive_link)


def replace_youtube_embed(youtube_link: str) -> str:
    archive_link_parse = urlparse(youtube_link)
    video_id = archive_link_parse.path[
        archive_link_parse.path.rfind("/"):
    ][1:]
    video_component = f"/watch?v={video_id}"
    youtube_link = archive_link_parse._replace(
        path=video_component, query=""
    ).geturl()
    return youtube_link


def strip_webarchive_link(archive_link: str) -> str:
    archive_link_parsed = urlparse(archive_link)
    splitted_link = archive_link_parsed.geturl().split("/")[5:]
    new_link = "/".join(splitted_link)
    return new_link


def replace_youtube_frames(soup: 'BeautifulSoup') -> 'BeautifulSoup':
    for page in soup:
        current_post = page[0]
        frames = current_post.select(".embed-youtube > iframe")
        spans = current_post.select(".embed-youtube")
        bs = BeautifulSoup()
        for frame, span in zip(frames, spans):
            archive_link = frame.attrs["src"]
            embed_link = strip_webarchive_link(archive_link)
            youtube_link = replace_youtube_embed(embed_link)
            p = bs.new_tag("p")
            a = bs.new_tag("a", href=youtube_link)
            a.string = f"{youtube_link}"
            p.append(a)
            span.replace_with(p)
    return soup


def parse_input_links(links):
    links_file = pathlib.Path(links[0])
    if len(links) == 1 and links_file.exists():
        page_links = read_links(links_file)
    else:
        page_links = links
    return page_links
