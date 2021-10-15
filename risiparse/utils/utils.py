#!/usr/bin/python3

"""This module just regroup some routines"""

from typing import List, Type, Dict
import tempfile
import unicodedata
import pathlib
import re
import argparse
import logging

from urllib.parse import urlparse
from PyPDF2 import PdfFileMerger
from bs4 import BeautifulSoup
from risiparse import html_to_pdf, sites_selectors
from risiparse.sites_selectors import Webarchive


def _replace_whitespaces(title: str) -> str:
    title_dashes = title.replace(" ", "-")
    return title_dashes


def _remove_risitas(title: str) -> str:
    regexp = re.compile(r"\[risitas\]", re.IGNORECASE)
    return regexp.sub("", title).strip()


def slugify(
        string: str,
        allow_unicode: bool = False,
        title: bool = False
) -> str:
    """Slugify the html file name"""
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
    """Strip www"""
    domain = re.sub(r"www.", "", url)
    return domain


def get_domain(url: str) -> str:
    """Get a url domain"""
    domain = url.split("/")[2]
    domain = _strip_www_component(domain)
    return domain


def make_app_dirs(output_dir: 'pathlib.Path') -> None:
    """Create the dirs where the htmls and pdfs are stored"""
    (output_dir / "risitas-html").mkdir(exist_ok=True, parents=True)
    (output_dir / "risitas-pdf").mkdir(exist_ok=True, parents=True)


def get_selectors_and_site(
        link: str
) -> (
    Type['sites_selectors.Jvc'] |
    Type['sites_selectors.Jvarchive'] |
    Type['sites_selectors.Webarchive']
):
    """Select which set of selectors to use"""
    domain = get_domain(link)
    if domain == "jeuxvideo.com":
        return sites_selectors.Jvc
    if domain == "jvarchive.com":
        return sites_selectors.Jvarchive
    if domain == "web.archive.org":
        return sites_selectors.Webarchive
    raise ValueError(
        f"The domain in the {link} doesn't match any domain supported!"
    )


def html_is_too_big(html: pathlib.Path, size: int = 3670016) -> bool:
    """Check if an html file is too big"""
    return bool(html.stat().st_size >= size)


def split_big_html(
        html: pathlib.Path,
        html_part_tmpdir: str,
        splitted_pdfs: Dict[str, List[pathlib.Path]],
        divs_step: int = 30
) -> Dict[str, List[pathlib.Path]]:
    """Split an html file into smaller htmls"""
    (pathlib.Path(f"{html_part_tmpdir}") / "risitas-pdf").mkdir(exist_ok=True)
    data = BeautifulSoup(
        html.read_text(encoding='utf-8'), features="lxml"
    )
    divs = data.select("div")
    start = 0
    end = divs_step
    for _ in range(0, len(divs), divs_step):
        file_path = pathlib.Path(
            f"{html_part_tmpdir}/{html.name}"
            f"-part-{start}-to-{end}.html"
        )
        with open(file_path, "w", encoding='utf-8') as file:
            for div in divs[start:end]:
                file.write(div.decode())
                logging.debug("Appended div to %s", file_path)
        pdf_path = str(html).replace("html", "pdf")
        if pdf_path not in splitted_pdfs:
            splitted_pdfs[pdf_path] = [file_path]
        else:
            splitted_pdfs[pdf_path].append(file_path)
        start = end
        end += divs_step
        file_path = pathlib.Path(f"{html}-part-{start}-to-{end}.html")
    return splitted_pdfs


def merge_pdfs(
        splitted_pdfs: Dict[str, List[pathlib.Path]],
        html_part_tmpdir: str,
        app
) -> None:
    """Create pdfs from smaller htmls and merge them back"""
    if splitted_pdfs:
        for pdf_file_name, htmls_part in splitted_pdfs.items():
            merger = PdfFileMerger()
            output_dir = pathlib.Path(f"{html_part_tmpdir}")
            page = html_to_pdf.PdfPage(output_dir)
            page.convert(htmls_part)
            app.exec()
            pdfs_to_merge = page.get_pdfs_path()
            for filename in pdfs_to_merge:
                merger.append(str(filename))
            with open(f"{pdf_file_name}", 'wb') as final_pdf:
                merger.write(final_pdf)
                logging.info("Merged pdf parts into %s", pdf_file_name)


def create_pdfs(
        output_dir: 'pathlib.Path',
        htmls_file_path: List['pathlib.Path'],
) -> None:
    """Create pdfs from a list of htmls"""
    app = html_to_pdf.QtWidgets.QApplication([])
    splitted_pdfs: Dict[str, List[pathlib.Path]] = {}
    html_folder_path = output_dir / "risitas-html"
    if not htmls_file_path:
        htmls_file_path = list(html_folder_path.glob("*.html"))
    with tempfile.TemporaryDirectory() as html_part_tmpdir:
        for html in htmls_file_path:
            if html_is_too_big(html):
                logging.info(
                    "The html file %s is too big and will be splitted "
                    "into multiple parts, then pdfs will be created and "
                    "merged back into one single pdf.", html
                )
                splitted_pdfs = splitted_pdfs | split_big_html(
                    html,
                    html_part_tmpdir,
                    splitted_pdfs
                )
                htmls_file_path.remove(html)
        logging.debug("Splitted pdfs is %s", splitted_pdfs)
        merge_pdfs(splitted_pdfs, html_part_tmpdir, app)
    if htmls_file_path:
        page = html_to_pdf.PdfPage(output_dir)
        page.convert(htmls_file_path)
        app.exec()


def read_links(links_file: pathlib.Path) -> List[str]:
    """Get all the links in a text file."""
    links_file = links_file.expanduser().resolve()
    with open(links_file, encoding='utf-8') as file:
        page_links = [line.strip() for line in file if line.strip() != '']
    return page_links


def get_args() -> argparse.Namespace:
    """Parse arguments given on the command line"""
    parser = argparse.ArgumentParser()
    default_links = [pathlib.Path().cwd() / "risitas-links"]
    parser.add_argument(
        "--all-posts",
        action="store_true",
        default=False,
        help=(
            "Download all the posts from the author, "
            "Default : False"
        )
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        default=False,
        help="Only download html, Default : False"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help=(
            "Verbose output for the stdout, the debug file always has "
            "verbose output on, Default : False"
        )
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        default=False,
        help=(
            "Create pdfs directly from "
            "current dir/risitas-html "
            "or one specified by -o, Default : False"
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
            "A list of words that are going to be matched by the script, "
            "example: a message that has the keyword 'hors-sujet', "
            "by adding 'hors-sujet' with this option, "
            "the script will match the message that has this keyword, "
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
            "throughout the whole risitas"
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
            "it will try to display them to their full scale, "
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
            "Also this will try to download risitas stickers on webarchive "
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
        type=lambda p: pathlib.Path(p).expanduser().resolve()
    )
    args = parser.parse_args()
    return args


def contains_webarchive(archive_link: str) -> bool:
    """Check if link domain is webarchive"""
    return bool("web.archive.org" in archive_link)


def replace_youtube_embed(youtube_link: str) -> str:
    """On webarchive site, the youtube videos
    are displayed as frames not links, this replace
    the frames by the youtube link"""
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
    """Remove the webarchive part to get the clean jeuxvideo.com link"""
    archive_link_parsed = urlparse(archive_link)
    splitted_link = archive_link_parsed.geturl().split("/")[5:]
    new_link = "/".join(splitted_link)
    return new_link


def replace_youtube_frames(soup: 'BeautifulSoup') -> 'BeautifulSoup':
    """Replace youtube frames by the link of the video"""
    for page in soup:
        current_post = page[0]
        frames = current_post.select(".embed-youtube > iframe")
        spans = current_post.select(".embed-youtube")
        beautiful_soup = BeautifulSoup()
        for frame, span in zip(frames, spans):
            archive_link = frame.attrs["src"]
            embed_link = strip_webarchive_link(archive_link)
            youtube_link = replace_youtube_embed(embed_link)
            paragraph = beautiful_soup.new_tag("p")
            link = beautiful_soup.new_tag("a", href=youtube_link)
            link.string = f"{youtube_link}"
            paragraph.append(link)
            span.replace_with(paragraph)
    return soup


def parse_input_links(links: List[str]) -> List[str]:
    """Parse the links given on the command line."""
    links_file = pathlib.Path(links[0])
    if len(links) == 1 and links_file.exists():
        page_links = read_links(links_file)
    else:
        page_links = links
    return page_links


def replace_webarchive_youtube_frame(
    domain,
    risitas_html
) -> List[str]:
    """
    Youtube frames are displayed in webarchive
    instead of a link, this fix it
    """
    if domain == Webarchive.SITE.value:
        risitas_html = replace_youtube_frames(risitas_html)
    return risitas_html


def write_html_template(
        html_file,
        begin: bool = False,
        end: bool = False,
) -> None:
    """Write html template"""
    if begin:
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
    elif end:
        html = (
            """</body>
              </html>"""
        )
    html_file.write(html)
