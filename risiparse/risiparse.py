#!/usr/bin/python3

"""This is the main module containing the core routines for risiparse"""

from typing import List, Optional
import sys
import logging
import pathlib
import re
import requests
import waybackpy

from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from risiparse.sites_selectors import Noelshack, Jvc, Jvarchive, Webarchive
from risiparse.utils.utils import (
    slugify,
    get_domain,
    make_app_dirs,
    get_selectors_and_site,
    create_pdfs,
    parse_input_links,
    get_args,
    strip_webarchive_link,
    replace_youtube_frames,
    contains_webarchive,
    set_file_logging
)
from risiparse.utils.log import ColorFormatter
from risiparse.utils.database import update_db, read_db, delete_db

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.DEBUG)

FMT = '%(asctime)s:%(levelname)s: %(message)s'

STDOUT_HANDLER = logging.StreamHandler()
STDOUT_HANDLER.setLevel(logging.INFO)
STDOUT_HANDLER.setFormatter(ColorFormatter(FMT))

LOGGER.addHandler(STDOUT_HANDLER)

DEFAULT_TIMEOUT = 5  # seconds


class TimeoutHTTPAdapter(HTTPAdapter):
    """This takes care of the default timeout for all requests"""
    def __init__(self, *args, **kwargs):
        self.timeout = DEFAULT_TIMEOUT
        if "timeout" in kwargs:
            self.timeout = kwargs["timeout"]
            del kwargs["timeout"]
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        """Replace the default timeout with our own"""
        timeout = kwargs.get("timeout")
        if timeout is None:
            kwargs["timeout"] = self.timeout
        return super().send(request, **kwargs)


class PageDownloader():
    """Handle all the downloads made by risiparse"""

    def __init__(self, domain: str):
        self.domain = domain
        self.webarchive = bool(self.domain == Webarchive.SITE.value)
        self.http = requests.Session()
        self.retries = Retry(
            total=5,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=1
        )
        self.adapter = TimeoutHTTPAdapter(max_retries=self.retries)
        self.http.mount("https://", self.adapter)

    def download_topic_page(
            self,
            page_link: str,
            page_number: int = 1,
    ) -> Optional['BeautifulSoup']:
        """Download the soup of the current page"""
        if not self.webarchive:
            page_link = self._get_page_link(
                page_number,
                page_link
            )
        else:
            webarchive_link = self._get_webarchive_page_link(
                page_number,
                page_link
            )
            if webarchive_link:
                page_link = webarchive_link
        logging.info("Going to page %s", page_link)
        try:
            page = self.http.get(page_link)
        except requests.exceptions.RetryError as retry_error:
            logging.exception(retry_error)
            logging.error(
                "The retries for %s have failed, "
                "being rate limited/server overloaded", page_link
            )
            return None
        page_status = page.status_code
        if page_status == 410:
            logging.error(
                "The page has been 410ed, try "
                "with one from jvarchive or webarchive"
            )
        if self.webarchive and page_status == 404:
            logging.error(
                "The Wayback Machine has not archived "
                "%s", page_link
            )
            return None
        soup = BeautifulSoup(page.content, features="lxml")
        return soup

    def download_img_page(self, page_link: str) -> str:
        """Get the full scale image link"""
        page = self.http.get(page_link)
        soup = BeautifulSoup(page.content, features="lxml")
        img_link = soup.select_one(
            Noelshack.IMG_SELECTOR.value
        ).attrs["src"]
        return img_link

    def _change_src_path(
            self,
            img: 'BeautifulSoup',
            img_folder_path: pathlib.Path,
            file_name: str
    ) -> None:
        img.attrs["src"] = str(img_folder_path) + "/" + file_name

    def _image_exists(
            self,
            file_name: str,
            img_folder: pathlib.Path
    ) -> bool:
        img_path = img_folder / file_name
        return bool(img_path.exists())

    def _get_page_link(
            self,
            page_number: int,
            page_link: str,
    ) -> str:
        page_link_number = [
               m.span() for m in re.finditer(r"\d*\d", page_link)
        ]
        page_link = (
               page_link[:page_link_number[3][0]]
               + str(page_number) +
               page_link[page_link_number[3][1]:]
        )
        return page_link

    def _get_webarchive_page_link(
            self,
            page_number: int,
            page_link: str
    ) -> Optional[str]:
        if page_number == 1:
            return None
        page_link_splitted = page_link.rsplit("/")
        if len(page_link) == 11:
            page_link = (
                "/".join(page_link_splitted[:-2]) + f"/{page_number}/"
            )
        else:
            page_link = (
                "/".join(page_link_splitted[:-1]) + f"/{page_number}/"
            )
        return page_link

    def get_webarchive_img(
            self,
            link: str,
    ) -> Optional['requests.models.Response']:
        """Get the image from webarchive."""
        logging.error(
            "The image at %s "
            "has been 404ed! Trying on "
            "webarchive...", link
        )
        user_agent = (
            "Mozilla/5.0 (Windows NT 5.1; rv:40.0) "
            "Gecko/20100101 Firefox/40.0"
        )
        try:
            wayback = waybackpy.Url(link, user_agent)
            oldest_archive = wayback.oldest()
            oldest_archive_url = oldest_archive.archive_url
            image = self.http.get(oldest_archive_url)
            status_code = image.status_code
        except waybackpy.exceptions.WaybackError as wayback_error:
            logging.exception(wayback_error)
            return None
        if status_code != 200:
            logging.error(
                "The image at %s "
                "on the oldest archive could "
                "not been downloaded", oldest_archive_url
            )
            return None
        return image

    def get_webarchive_link(
            self,
            img: BeautifulSoup
    ) -> str:
        """Strip the redundant part in the webarchive link
           to get a clean url
        """
        archive_link = img.attrs["src"]
        contains_webarchive_link = contains_webarchive(
            archive_link
        )
        if contains_webarchive_link:
            link = strip_webarchive_link(archive_link)
        else:
            link = archive_link
        return link

    def download_images(
            self,
            soup: BeautifulSoup,
            output_dir: pathlib.Path,
    ) -> None:
        """Download all the images and stores them."""
        img_folder_path = output_dir / "risitas-html" / "images"
        img_folder_path.mkdir(exist_ok=True)
        for page in soup:
            imgs = page[0].select("img")
            for img in imgs:
                if self.webarchive:
                    link = self.get_webarchive_link(img)
                else:
                    link = img.attrs["src"]
                file_name = link[link.rfind("/"):][1:]
                if not self._image_exists(file_name, img_folder_path):
                    logging.info(
                        "Image not in cache, downloading "
                        "%s", file_name
                    )
                    try:
                        image = self.http.get(link)
                        status_code = image.status_code
                    # Connection refused or others errors.
                    except requests.exceptions.ConnectionError as con_error:
                        logging.exception(con_error)
                        continue
                    if status_code == 404:
                        image = self.get_webarchive_img(link)
                        if not image:
                            continue
                    file_name = image.url[image.url.rfind("/"):][1:]
                    img_file_path = img_folder_path / file_name
                    img_file_path.write_bytes(image.content)
                self._change_src_path(img, img_folder_path, file_name)


class RisitasInfo():
    """
    This gets the author name and the total number of pages and the title.
    """

    def __init__(self, page_soup: BeautifulSoup, selectors, domain: str):
        self.soup = page_soup
        self.selectors = selectors
        self.domain = domain
        self.author = self.get_author_name(self.soup)
        self.total_pages = self.get_total_pages(self.soup)
        self.title = self.get_title(self.soup)

    def get_author_name(self, soup: BeautifulSoup) -> str:
        """Get the author name"""
        if self.domain == "jeuxvideo.com":
            author = soup.select_one(
                self.selectors.DELETED_AUTHOR_SELECTOR.value
            ).text.strip()
            if author == "Pseudo supprimé":
                logging.error(
                    "The author has deleted his account, "
                    "need to sort the message after this "
                    "and look if he posted with an "
                    "other account"
                )
                return author
        try:
            author = soup.select_one(
                self.selectors.AUTHOR_SELECTOR.value
            ).text.strip()
        except AttributeError as author_not_found:
            author = "unknown"
            logging.exception(author_not_found)
            logging.error(
                "Can't get the risitas "
                "author, set author to '%s'", author
            )
        if not author and self.domain == Webarchive.SITE.value:
            author = "Pseudo supprimé"
        logging.info(
            "The risitas author is : %s", author
        )
        return author

    def get_total_pages(self, soup: BeautifulSoup) -> int:
        """Get the number of pages to parse"""
        try:
            topic_symbol = soup.select_one(
                self.selectors.TOTAL_SELECTOR.value
            ).text
            if self.domain == Jvc.SITE.value:
                if topic_symbol == "»":
                    topic_symbol = soup.select_one(
                        self.selectors.TOTAL_SELECTOR_ALTERNATIVE.value
                    ).text
        except AttributeError:
            topic_symbol = None
        if not topic_symbol and self.domain == Webarchive.SITE.value:
            logging.info(
                "This risitas has only one "
                "page!"
            )
            topic_pages = 1
        else:
            topic_pages = int(topic_symbol)
        return topic_pages

    def get_title(self, soup: BeautifulSoup) -> str:
        """Get the title of the risitas"""
        try:
            title = soup.select_one(
                self.selectors.TITLE_SELECTOR.value
            ).text.strip()
        except AttributeError as title_not_found:
            logging.exception(title_not_found)
            logging.error(
                "Can't get the title "
                "author, setting the title to "
                "the page title"
            )
            title = soup.select_one(
                self.selectors.PAGE_TITLE_SELECTOR.value
            ).text.strip()
        return title


class Posts():
    """Get a post author and content"""

    def __init__(
            self,
            risitas_info: 'RisitasInfo',
            downloader: PageDownloader,
            args: 'argparse.Namespace',
    ):
        self.risitas_html: List['BeautifulSoup'] = []
        self.risitas_raw_text: List[str] = []
        self.downloader = downloader
        self.risitas_info = risitas_info
        self.args = args
        self.authors: List[str] = []
        self.past_message = False
        self.message_cursor = 0
        self.count = 0
        self.duplicates = 0

    def _check_post_author(
            self,
            post: BeautifulSoup,
            no_match_author: bool,
            is_web_archive: bool
    ) -> bool:
        # This is needed cuz deleted accounts are not handled
        # the same way for whatever reason...
        try:
            post_author = post.select_one(
                self.risitas_info.selectors.AUTHOR_SELECTOR.value
            ).text.strip()
        except AttributeError:
            if not is_web_archive:
                logging.debug("Author deleted his account")
                post_author = post.select_one(
                    self.risitas_info.selectors.DELETED_AUTHOR_SELECTOR.value
                ).text.strip()
            else:
                return False
        logging.debug(
            "The current author is "
            "%s "
            "and the risitas author is "
            "%s", post_author, self.authors
        )
        if not no_match_author:
            for author in self.authors:
                author_root = re.sub(r"\d*", "", author)
                if author_root in post_author:
                    return True
        return bool(post_author in self.authors)

    def _check_post_length(self, post: BeautifulSoup) -> bool:
        """Check the post length to see if this is a chapter
        or an offtopic message"""
        paragraph = post.text.strip().replace("\n", "")
        return bool(len(paragraph) < 1000)

    def _check_post_identifiers(
            self,
            post: BeautifulSoup,
            identifiers: List
    ) -> bool:
        identifiers_joined = "|".join(identifiers)
        regexp = re.compile(identifiers_joined, re.IGNORECASE)
        try:
            post_paragraph_text = post.select_one("p").text[0:200]
        except AttributeError as text_error:
            logging.exception(
                "The post doesn't contains text, probably some image %s",
                text_error
            )
            return False
        contains_identifiers = regexp.search(post_paragraph_text)
        return bool(
            contains_identifiers and not post.select_one("blockquote")
        )

    def _check_post_duplicates(
            self,
            risitas_html: 'BeautifulSoup',
            contains_images: bool
    ) -> bool:
        if not self.risitas_raw_text:
            return False
        ret_val = False
        if contains_images:
            for part in self.risitas_html:
                if part[1] is True and risitas_html == part[0]:
                    ret_val = True
                    break
            return ret_val
        for i in range(len(self.risitas_raw_text)):
            ret_val = bool(
                risitas_html.text.lower() ==
                self.risitas_raw_text[-i].lower() or
                risitas_html.text[0:100].lower() ==
                self.risitas_raw_text[-i][0:100].lower()
            )
        return ret_val

    def _contains_blockquote(self, risitas_html: BeautifulSoup) -> bool:
        return bool(risitas_html.select("blockquote"))

    def _check_chapter_image(self, soup: BeautifulSoup) -> bool:
        ret_val = False
        paragraphs = soup.select("p")
        if not paragraphs and self.risitas_info.domain == Jvarchive.SITE.value:
            link = soup.select("a")
            if link:
                return True
        # Need to check alt startswith https
        for paragraph in paragraphs:
            if re.search(r"screen|repost|supprime", paragraph.text):
                if (
                        len(
                            soup.select(
                                self.risitas_info.
                                selectors.
                                NOELSHACK_IMG_SELECTOR.value
                            )
                        ) >= 3 and not soup.select("blockquote") and
                        len(soup.text.strip()) < 300

                ):
                    ret_val = True
                    break
            elif not paragraph.text.strip():
                if (
                        len(
                            soup.select(
                                self.
                                risitas_info.
                                selectors.
                                NOELSHACK_IMG_SELECTOR.value
                            )
                        ) >= 3 and not soup.select("blockquote") and
                        len(soup.text.strip()) < 300
                ):
                    ret_val = True
            else:
                ret_val = False
        return ret_val

    def _get_fullscale_image(self, soup: BeautifulSoup) -> BeautifulSoup:
        image_soup = soup
        imgs = image_soup.select(
            self.risitas_info.selectors.NOELSHACK_IMG_SELECTOR.value
        )
        remove_attrs = ["width", "height"]
        for remove_attr in remove_attrs:
            for img in imgs:
                try:
                    img.attrs.pop(remove_attr)
                    logging.info(
                        "Displaying %s at full scale!", img.attrs["src"]
                    )
                except KeyError as missing_attribute:
                    logging.exception(
                        "This is a jvc smiley! %s",
                        missing_attribute
                    )
        if self.risitas_info.domain == Jvc.SITE.value:
            for img in imgs:
                if re.search("fichiers", img.attrs["alt"]):
                    img.attrs["src"] = img.attrs["alt"]
                else:
                    img.attrs["src"] = self.downloader.download_img_page(
                        img.attrs["alt"]
                    )
        elif self.risitas_info.domain == Jvarchive.SITE.value:
            for img in imgs:
                img.attrs["src"] = img.attrs["alt"]
        return image_soup

    def _print_chapter_added(
            self,
            risitas_html: BeautifulSoup
    ) -> None:
        try:
            pretty_print = risitas_html.select_one(
                'p'
            ).text[0:50].strip().replace("\n", "")
            if not pretty_print and len(risitas_html.select("p")) > 1:
                pretty_print = risitas_html.select("p")[1].text[
                    0:50].strip().replace("\n", "")
            if not pretty_print:
                logging.debug(
                    "Added some images, maybe chapters in screenshot?"
                )
            else:
                logging.info(
                    "Adding "
                    "%s", pretty_print
                )
        except AttributeError as jvarchive_image:
            logging.exception(
                "Can't log text because this "
                "is an image from jvarchive %s", jvarchive_image
            )

    def _get_webarchive_post_html(
            self,
            post: BeautifulSoup
    ) -> BeautifulSoup:
        new_html = []
        risitas_html = post.select_one(
            self.
            risitas_info.selectors.RISITAS_TEXT_SELECTOR_ALTERNATIVE.value
        )
        if risitas_html and risitas_html.p:
            return risitas_html
        risitas_html = post.select(
            self.
            risitas_info.selectors.RISITAS_TEXT_SELECTOR_ALTERNATIVE2.value
        )
        if not risitas_html:
            risitas_html = post.select(
                self.
                risitas_info.selectors.RISITAS_TEXT_SELECTOR_ALTERNATIVE3.value
            )
        for paragraph in risitas_html:
            new_html.append(str(paragraph))
            new_html_joined = "".join(new_html)
            risitas_html = BeautifulSoup(new_html_joined, features="lxml")
        try:
            # This is needed cuz beautifulsoup
            # add a html,body tag automatically
            risitas_html.html.wrap(
                risitas_html.new_tag(
                    "div",
                    attrs={"class": "txt-msg text-enrichi-forum"}
                )
            )
            risitas_html.html.body.unwrap()
            risitas_html.html.unwrap()
        except AttributeError:
            pass
        return risitas_html

    def _skip_post(
            self,
            append: bool,
            message_cursor: int,
            message_cursor_db: int,
    ) -> bool:
        skip_post = False
        if append and not self.past_message:
            if message_cursor <= message_cursor_db:
                if message_cursor == 19:
                    self.past_message = True
                skip_post = True
        return skip_post

    def _contains_paragraph(self, risitas_html: 'bs4') -> Optional["bs4"]:
        contains_paragraph = None
        try:
            contains_paragraph = risitas_html.select("p")
        except AttributeError:
            pass
        return contains_paragraph

    def _is_risitas_post(
            self,
            post,
            risitas_html,
            is_domain_webarchive
    ) -> bool:
        is_author = self._check_post_author(
            post,
            self.args.no_match_author,
            is_domain_webarchive
        )
        if not is_author and not is_domain_webarchive:
            return False
        if self.args.all_messages:
            self.count += 1
            self.risitas_html.append((risitas_html, ))
            return False
        contains_identifiers = self._check_post_identifiers(
               post,
               self.args.identifiers
        )
        is_short = self._check_post_length(post)
        contains_blockquote = self._contains_blockquote(risitas_html)
        if contains_blockquote:
            return False
        contains_image = self._check_chapter_image(post)
        if (
                  not contains_identifiers and
                  self.count > 1 and
                  not contains_image
                  and is_short
        ):
            return False
        if is_short and not contains_image:
            return False
        is_duplicate = self._check_post_duplicates(
               risitas_html,
               contains_image
        )
        if is_duplicate:
               first_lines = risitas_html.select_one('p').text[0:50].strip()
               logging.error("The current post '%s' is a duplicate!", first_lines)
               self.duplicates += 1
               return False
        return True

    def get_posts(
            self,
            soup: BeautifulSoup,
            risitas_authors: List,
            append: bool,
            message_cursor_db: int,
    ) -> None:
        is_domain_webarchive = bool(
            self.risitas_info.domain == "web.archive.org"
        )
        posts = soup.select(self.risitas_info.selectors.MESSAGE_SELECTOR.value)
        if not self.authors:
            self.authors = risitas_authors
        self.added_message = False
        for message_cursor, post in enumerate(posts):
            if self._skip_post(append, message_cursor, message_cursor_db):
                continue
            risitas_html = post.select_one(
                self.risitas_info.selectors.RISITAS_TEXT_SELECTOR.value
            )
            contains_paragraph = self._contains_paragraph(risitas_html)
            if is_domain_webarchive and not contains_paragraph:
                risitas_html = self._get_webarchive_post_html(post)
            contains_image = self._check_chapter_image(post)
            if not self._is_risitas_post(
                    post,
                    risitas_html,
                    is_domain_webarchive
            ):
                continue
            self._print_chapter_added(risitas_html)
            self.added_message = True
            self.risitas_html.append((risitas_html, contains_image))
            self.risitas_raw_text.append(risitas_html.text)
            self.count += 1
            self.message_cursor = message_cursor


class RisitasPostsDownload():
    """Handle the download of posts"""

    def __init__(self, page_downloader, args):
        self.page_downloader = page_downloader
        self.args = args
        self.page_number = 0
        self.posts = None
        self.authors = []
        self.append = False
        self.message_cursor = 0

    def disable_database_webarchive(self, domain) -> None:
        if domain == Webarchive.SITE.value:
            self.args.no_database = True

    def replace_webarchive_youtube_frame(
            self,
            domain,
            risitas_html
    ) -> List[str]:
        if domain == Webarchive.SITE.value:
            risitas_html = replace_youtube_frames(risitas_html)
        return risitas_html

    def get_risitas_info(
            self,
            link: str,
            domain: str,
    ) -> 'RisitasInfo':
        selectors = get_selectors_and_site(link)
        soup = self.page_downloader.download_topic_page(
            link,
            1,
        )
        risitas_info = RisitasInfo(soup, selectors, domain)
        self.authors = [risitas_info.author] + self.args.authors
        self.posts = Posts(
            risitas_info,
            self.page_downloader,
            self.args,
        )
        return risitas_info

    def _set_init_message_cursor(
        self,
        row: tuple[str]
    ) -> None:
        if not self.args.no_database:
            if row[0]:
                if not self.page_number:
                    self.page_number = row[0][6]
                self.append = True
                self.message_cursor = row[0][7]
            else:
                self.message_cursor = 0

    def _set_post_message_cursor(
        self,
        page: int,
        total_pages: int,
    ) -> None:
        if (
                self.posts.message_cursor and
                page + 1 == total_pages and
                self.posts.added_message
        ):
            self.message_cursor = self.posts.message_cursor

    def log_posts_downloaded_and_duplicates(
            self,
            all_messages: bool,
            risitas_info: 'Risitasinfo',
            posts: 'Posts'
    ) -> None:
        logging.info(
            "The number of posts downloaded for "
            "%s "
            "is : %d", risitas_info.title, posts.count
        )
        if not all_messages:
            logging.info(
                "The number of duplicates for "
                "%s "
                "is : %d", risitas_info.title, posts.duplicates
            )

    def download_posts(
            self,
            link: str,
            total_pages: int,
            row: tuple[str]
    ):
        for page in range(total_pages):
            self._set_init_message_cursor(row)
            if not self.page_number:
                self.page_number = 1
            soup = self.page_downloader.download_topic_page(
                link, self.page_number
            )
            if not soup:
                self.page_number += 1
                continue
            self.posts.get_posts(
                soup,
                self.authors,
                self.append,
                self.message_cursor,
            )
            self.page_number += 1
            self._set_post_message_cursor(
                page,
                total_pages
            )
        return self.posts.risitas_html


def get_database_risitas_page(row: tuple, total_pages: int):
    if row[0]:
        risitas_database_pages = row[0][6]
        total_pages = (
            total_pages - risitas_database_pages + 1
        )
    return total_pages


class RisitasHtmlFile():
    """Handle all hte html file I/O"""

    htmls_file_path = []

    def __init__(self, risitas_html, risitas_info, args, row):
        self.html_file_path = pathlib.Path()
        self.risitas_html = risitas_html
        self.risitas_info = risitas_info
        self.args = args
        self.row = row

    def append_to_or_write_html_file(
            self,
            append: bool,
    ) -> None:
        """
        Create or append an html file, side effect is to
        collect html_file_path to convert them to pdf
        """
        if append and not self.args.no_database:
            self.html_file_path = pathlib.Path(self.row[0][4])
            self.htmls_file_path.append(self.html_file_path)
            self.append_html()
        else:
            self.write_html()
            self.htmls_file_path.append(self.html_file_path)

    def _write_html_template(
            self,
            html_file: '_io.TextIOWrapper',
            begin: bool = False,
            end: bool = False,
    ):
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
            html_file.write(html)
        elif end:
            html = (
            """</body>
               </html>"""
            )
            html_file.write(html)

    def _increment_html_file_name(self) -> None:
        title_slug = slugify(self.risitas_info.title, title=True)
        author_slug = slugify(self.risitas_info.author, title=False)
        ext = "html"
        i = 0
        full_title = f"{author_slug}-{title_slug}-{i}"
        html_path = (
            self.args.output_dir /
            "risitas-html" /
            (full_title + f".{ext}")
        )
        while html_path.exists():
            i += 1
            full_title = f"{author_slug}-{title_slug}-{i}"
            html_path = (
                self.args.output_dir /
                "risitas-html" /
                (full_title + f".{ext}")
            )
        self.html_file_path = html_path

    def write_html(
            self,
    ) -> None:
        """Produce an html file from the risitas soup"""
        self._increment_html_file_name()
        with open(self.html_file_path, "w", encoding="utf-8") as html_file:
            self._write_html_template(html_file, begin=True, end=False)
            for paragraph in self.risitas_html:
                html_file.write(str(paragraph[0]).replace("’", "'"))
            self._write_html_template(html_file, begin=False, end=True)
            logging.info("Wrote %s", self.html_file_path)

    def append_html(self) -> None:
        with open(self.html_file_path, encoding='utf-8') as html_file:
            soup = BeautifulSoup(html_file, features="lxml")
        for new_chapter in self.risitas_html:
            soup.body.insert(len(soup.body.contents), new_chapter[0])
            logging.debug("Appending %s ...", new_chapter[0])
        with open(self.html_file_path, "w", encoding='utf-8') as html_file:
            html_file.write(soup.decode().replace("’", "'"))
        logging.info(
            "The chapters have been appended to %s",
            self.html_file_path
        )


def download_risitas(args) -> List['pathlib.Path']:
    """Download risitas"""
    page_links = parse_input_links(args.links)
    risitas_html_file = None
    for link in page_links:
        domain = get_domain(link)
        page_downloader = PageDownloader(domain)
        posts_downloader = RisitasPostsDownload(page_downloader, args)
        risitas_info = posts_downloader.get_risitas_info(link, domain)
        posts_downloader.disable_database_webarchive(domain)
        total_pages = risitas_info.total_pages
        row = [()]
        if not args.no_database:
            row = read_db(link)
            total_pages = get_database_risitas_page(
                row,
                risitas_info.total_pages
            )
        risitas_html = posts_downloader.download_posts(
            link,
            total_pages,
            row
        )
        if not risitas_html and not args.no_database:
            logging.info("There is no new chapters available!")
            continue
        if args.download_images:
            page_downloader.download_images(
                risitas_html,
                args.output_dir,
            )
        risitas_html_file = RisitasHtmlFile(
            risitas_html,
            risitas_info,
            args,
            row
        )
        risitas_html_file.append_to_or_write_html_file(
            posts_downloader.append,
        )
        if not args.no_database:
            update_db(
                domain,
                risitas_info.title,
                link,
                risitas_html_file.html_file_path,
                risitas_info.total_pages,
                risitas_info.total_pages,
                posts_downloader.message_cursor,
                posts_downloader.authors,
            )
    if risitas_html_file:
        return risitas_html_file.htmls_file_path


def main() -> None:
    args = get_args()
    set_file_logging(args.output_dir, LOGGER, FMT)
    if args.clear_database:
        delete_db()
        sys.exit()
    make_app_dirs(args.output_dir)
    if args.debug:
        STDOUT_HANDLER.setLevel(logging.DEBUG)
    if not args.no_download:
        htmls_file_path = download_risitas(args)
    if not args.no_pdf:
        create_pdfs(args.output_dir, htmls_file_path)
