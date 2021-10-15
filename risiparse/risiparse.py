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
    write_html_template
)
from risiparse.utils.utils_page_downloader import (
    get_page_link,
    get_webarchive_link,
    get_webarchive_page_link,
    image_exists,
    change_img_src_path
)
from risiparse.utils.utils_posts import (
    check_post_length,
    check_post_identifiers,
    contains_blockquote,
    print_chapter_added,
    contains_paragraph
)
from risiparse.utils.log import ColorFormatter, set_file_logging
from risiparse.utils.database import update_db, read_db, delete_db

LOGGER = logging.getLogger()
LOGGER.handlers.clear()
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

    # The send method expects 7 parameters, here they are just in kwargs
    # pylint will throw an error if there are too many parameters.
    # So we just disable it here.
    # pylint: disable=arguments-differ
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
            page_link = get_page_link(
                page_number,
                page_link
            )
        else:
            webarchive_link = get_webarchive_page_link(
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

    def download_img_page(self, page_link: str) -> Optional[str]:
        """Get the full scale image link"""
        page = self.http.get(page_link)
        soup = BeautifulSoup(page.content, features="lxml")
        img_link = None
        try:
            img_link = soup.select_one(
                Noelshack.IMG_SELECTOR.value
            ).attrs["src"]
        except AttributeError as image_404:
            logging.exception(image_404)
        return img_link

    def get_webarchive_img(
            self,
            link: str,
    ) -> requests.models.Response | None:
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
                    link = get_webarchive_link(img)
                else:
                    link = img.attrs["src"]
                file_name = link[link.rfind("/"):][1:]
                if not image_exists(file_name, img_folder_path):
                    logging.info(
                        "Image not in cache, downloading "
                        "%s", file_name
                    )
                    image = None
                    try:
                        image = self.http.get(link)
                        status_code = image.status_code
                    # Connection refused or others errors.
                    except requests.exceptions.ConnectionError as con_error:
                        logging.exception(con_error)
                        continue
                    except requests.exceptions.InvalidSchema as invalid_schema:
                        logging.exception(invalid_schema)
                        continue
                    if status_code == 404:
                        image = self.get_webarchive_img(link)
                        if not image:
                            continue
                    file_name = image.url[image.url.rfind("/"):][1:]
                    img_file_path = img_folder_path / file_name
                    img_file_path.write_bytes(image.content)
                change_img_src_path(img, img_folder_path, file_name)


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
                    "need to sort the post after this "
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

    # Disabling too many instances for now.
    # Refactoring later
    # pylint: disable=too-many-instance-attributes
    def __init__(
            self,
            risitas_info: 'RisitasInfo',
            downloader: PageDownloader,
            args,
    ):
        self.risitas_html: List['BeautifulSoup'] = []
        self.risitas_raw_text: List[str] = []
        self.downloader = downloader
        self.risitas_info = risitas_info
        self.args = args
        self.past_post_cursor_page = False
        self.added_post = False
        self.post_cursor = 0
        self.count = 0
        self.duplicates = 0

    def _check_post_author(
            self,
            post: BeautifulSoup,
            no_match_author: bool,
            is_web_archive: bool,
            authors: List[str]
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
            "%s", post_author, authors
        )
        if not no_match_author:
            for author in authors:
                author_root = re.sub(r"\d*", "", author)
                if author_root in post_author:
                    return True
        return bool(post_author in authors)

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

    def _check_post_is_image(self, soup: BeautifulSoup) -> bool:
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
        for img in imgs:
            try:
                img.attrs.pop("width")
                img.attrs.pop("height")
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
                    original_src = img.attrs['src']
                    img.attrs["src"] = self.downloader.download_img_page(
                        img.attrs["alt"]
                    )
                    if not img.attrs["src"]:
                        img.attrs["src"] = original_src
        elif self.risitas_info.domain == Jvarchive.SITE.value:
            for img in imgs:
                img.attrs["src"] = img.attrs["alt"]
        return image_soup

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
            append_to_html: bool,
            post_cursor: int,
            post_cursor_db: int,
    ) -> bool:
        """Go to the nth post if post_cursor in the database"""
        skip_post = False
        if append_to_html and not self.past_post_cursor_page:
            if post_cursor <= post_cursor_db:
                if post_cursor == 19:
                    self.past_post_cursor_page = True
                skip_post = True
            else:
                self.past_post_cursor_page = True
        return skip_post

    def is_risitas_post(
            self,
            post,
            risitas_html,
            is_domain_webarchive: bool,
            authors: List[str]
    ) -> bool:
        """Check if the given post is a risitas"""
        is_part_of_risitas = False
        for _ in range(1):
            is_author = self._check_post_author(
                post,
                self.args.no_match_author,
                is_domain_webarchive,
                authors
            )
            if not is_author and not is_domain_webarchive:
                break
            if self.args.all_posts:
                self.count += 1
                self.risitas_html.append((risitas_html, ))
                break
            contains_identifiers = check_post_identifiers(
                post,
                self.args.identifiers
            )
            is_short = check_post_length(post)
            if contains_blockquote(risitas_html):
                break
            contains_image = self._check_post_is_image(post)
            if (
                    not contains_identifiers and
                    self.count > 1 and
                    not contains_image
                    and is_short
            ):
                break
            if is_short and not contains_image:
                break
            is_duplicate = self._check_post_duplicates(
                risitas_html,
                contains_image
            )
            if is_duplicate:
                first_lines = risitas_html.select_one('p').text[0:50].strip()
                logging.error(
                    "The current post '%s' is a duplicate!",
                    first_lines
                )
                self.duplicates += 1
                break
        else:
            return not is_part_of_risitas
        return is_part_of_risitas

    def get_posts(
            self,
            soup: BeautifulSoup,
            risitas_authors: List,
            append_to_html: bool,
            post_cursor_db: int,
    ) -> None:
        """
        Check conditions to see if it's a post relevant to the risitas
        """
        is_domain_webarchive = bool(
            self.risitas_info.domain == "web.archive.org"
        )
        posts = soup.select(self.risitas_info.selectors.POST_SELECTOR.value)
        self.added_post = False
        for post_cursor, post in enumerate(posts):
            if self._skip_post(append_to_html, post_cursor, post_cursor_db):
                continue
            risitas_html = post.select_one(
                self.risitas_info.selectors.RISITAS_TEXT_SELECTOR.value
            )
            if is_domain_webarchive and not contains_paragraph(risitas_html):
                risitas_html = self._get_webarchive_post_html(post)
            if not self.is_risitas_post(
                    post,
                    risitas_html,
                    is_domain_webarchive,
                    risitas_authors
            ):
                continue
            contains_image = self._check_post_is_image(risitas_html)
            if contains_image:
                if not self.args.no_resize_images:
                    risitas_html = self._get_fullscale_image(risitas_html)
            print_chapter_added(risitas_html)
            self.added_post = True
            self.risitas_html.append((risitas_html, contains_image))
            self.risitas_raw_text.append(risitas_html.text)
            self.count += 1
            self.post_cursor = post_cursor


class RisitasPostsDownload():
    """Handle the download of posts"""

    def __init__(self, page_downloader, args):
        self.page_downloader = page_downloader
        self.args = args
        self.page_number = 0
        self.posts = None
        self.authors = []
        self.append_to_html = False
        self.post_cursor = 0

    def disable_database_webarchive(self, domain) -> None:
        """
        If webarchive, no database because the risitas will never get updated.
        Jeuxvideo.com forbids archive by webarchive, only jvarchive works.
        """
        if domain == Webarchive.SITE.value:
            self.args.no_database = True

    def get_risitas_info(
            self,
            link: str,
            domain: str,
    ) -> 'RisitasInfo':
        """Get informations about the risitas."""
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

    def _set_init_post_cursor(
        self,
        row
    ) -> None:
        """
        Set the post cursor for the first time,
        from the database if it exists else it is set to 0
        """
        if not self.args.no_database:
            if row:
                if not self.page_number:
                    self.page_number = row[4]
                self.append_to_html = True
                self.post_cursor = row[5]
            else:
                self.post_cursor = 0

    def _set_post_cursor(
        self,
        page: int,
        total_pages: int,
    ) -> None:
        """
        Set the post cursor that is going to be in the database,
        if no then the post cursor is going to be 0
        """
        at_end_of_risitas = bool(page + 1 == total_pages)
        if (
                self.posts.post_cursor and
                at_end_of_risitas and
                self.posts.added_post
        ):
            self.post_cursor = self.posts.post_cursor
        else:
            self.post_cursor = 0

    def log_posts_downloaded_and_duplicates(
            self,
    ) -> None:
        """Log number of post downloaded and duplicates."""
        logging.info(
            "The number of posts downloaded for "
            "%s "
            "is : %d", self.posts.risitas_info.title, self.posts.count
        )
        if not self.posts.args.all_posts:
            logging.info(
                "The number of duplicates for "
                "%s "
                "is : %d", self.posts.risitas_info.title, self.posts.duplicates
            )

    def download_posts(
            self,
            link: str,
            total_pages: int,
            row,
    ):
        """Download all the relevant posts for the current risitas"""
        for page in range(total_pages):
            self._set_init_post_cursor(row)
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
                self.append_to_html,
                self.post_cursor,
            )
            self.page_number += 1
            self._set_post_cursor(
                page,
                total_pages
            )
        self.log_posts_downloaded_and_duplicates()
        return self.posts.risitas_html


def get_database_risitas_page(row, total_pages: int) -> int:
    """
    Compute the page number if in database,
    (ex: 57 in the database and 60 currently),
    this will output 3 -> 3 pages to download posts.
    If no database return the page number given by risitas info
    """
    if row:
        risitas_database_pages = row[4]
        total_pages = (
            total_pages - risitas_database_pages + 1
        )
    return total_pages


class RisitasHtmlFile():
    """Handle all hte html file I/O"""

    htmls_file_path: List['pathlib.Path'] = []

    def __init__(self, risitas_html, risitas_info, args, row):
        self.html_file_path = pathlib.Path()
        self.risitas_html = risitas_html
        self.risitas_info = risitas_info
        self.args = args
        self.row = row

    def append_to_or_write_html_file(
            self,
            append_to_html: bool,
    ) -> None:
        """
        Create or append an html file, side effect is to
        collect html_file_path in order to convert them to pdf
        """
        if append_to_html and not self.args.no_database:
            self.html_file_path = pathlib.Path(self.row[3])
            self.htmls_file_path.append(self.html_file_path)
            self.append_html()
        else:
            self.write_html()
            self.htmls_file_path.append(self.html_file_path)

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
        """Produce an html file from the risitas soup."""
        self._increment_html_file_name()
        with open(self.html_file_path, "w", encoding="utf-8") as html_file:
            write_html_template(html_file, begin=True, end=False)
            for paragraph in self.risitas_html:
                html_file.write(str(paragraph[0]).replace("’", "'"))
            write_html_template(html_file, begin=False, end=True)
            logging.info("Wrote %s", self.html_file_path)

    def append_html(self) -> None:
        """Append new chapters to an existing html file."""
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


def download_risitas(args) -> List['pathlib.Path'] | List:
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
        row = None
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
            posts_downloader.append_to_html,
        )
        if not args.no_database:
            update_db(
                risitas_info.title,
                link,
                risitas_html_file.html_file_path,
                risitas_info.total_pages,
                posts_downloader.post_cursor,
            )
    if risitas_html_file:
        return risitas_html_file.htmls_file_path
    return []


def main() -> None:
    """Entry point of risiparse"""
    args = get_args()
    htmls_file_path: List['pathlib.Path'] = []
    set_file_logging(args.output_dir, LOGGER, FMT)
    if args.clear_database:
        delete_db()
        sys.exit()
    make_app_dirs(args.output_dir)
    if args.debug:
        STDOUT_HANDLER.setLevel(logging.DEBUG)
    if not args.no_download:
        htmls_file_path = download_risitas(args)
    if args.create_pdfs:
        htmls_file_path = htmls_file_path + args.create_pdfs
    if not args.no_pdf:
        create_pdfs(args.output_dir, htmls_file_path)
