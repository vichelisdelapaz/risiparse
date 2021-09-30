#!/usr/bin/python3

"""This is the main module containing the core routines for risiparse"""

from typing import List, Optional
import sys
import logging
import datetime
import pathlib
import re
import requests
import waybackpy

from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from risiparse.sites_selectors import Noelshack, Jvc, Jvarchive, Webarchive
from risiparse.utils.utils import (
    write_html,
    append_html,
    get_domain,
    make_dirs,
    get_selectors_and_site,
    create_pdfs,
    parse_input_links,
    get_args,
    strip_webarchive_link,
    replace_youtube_frames,
    contains_webarchive
)
from risiparse.utils.log import ColorFormatter
from risiparse.utils.database import update_db, read_db, delete_db

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

FMT = '%(asctime)s:%(levelname)s: %(message)s'

STDOUT_HANDLER = logging.StreamHandler()
STDOUT_HANDLER.setLevel(logging.INFO)
STDOUT_HANDLER.setFormatter(ColorFormatter(FMT))

TODAY = datetime.date.today()

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
        logging.info(f"Going to page {page_link}")
        try:
            page = self.http.get(page_link)
        except requests.exceptions.RetryError as e:
            logging.exception(e)
            logging.error(
                f"The retries for {page_link} have failed, "
                f"being rate limited/server overloaded"
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
                f"The Wayback Machine has not archived "
                f"{page_link}"
            )
            return None
        soup = BeautifulSoup(page.content, features="lxml")
        return soup

    def download_img_page(self, page_link: str) -> str:
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
        logging.error(
            f"The image at {link} "
            "has been 404ed! Trying on "
            "webarchive..."
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
        except waybackpy.exceptions.WaybackError as e:
            logging.exception(e)
            return None
        if status_code != 200:
            logging.error(
                f"The image at {oldest_archive_url} "
                "on the oldest archive could "
                "not been downloaded"
            )
            return None
        return image

    def get_webarchive_link(
            self,
            img: BeautifulSoup
    ) -> str:
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
                        f"{file_name}"
                    )
                    try:
                        image = self.http.get(link)
                        status_code = image.status_code
                    # Connection refused or others errors.
                    except requests.exceptions.ConnectionError as e:
                        logging.exception(e)
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
        except AttributeError as e:
            author = "unknown"
            logging.exception(e)
            logging.error(
                "Can't get the risitas "
                f"author, set author to '{author}'"
            )
        if not author and self.domain == Webarchive.SITE.value:
            author = "Pseudo supprimé"
        logging.info(
            f"The risitas author is : {author}"
        )
        return author

    def get_total_pages(self, soup: BeautifulSoup) -> int:
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
        try:
            title = soup.select_one(
                self.selectors.TITLE_SELECTOR.value
            ).text.strip()
        except AttributeError as e:
            logging.exception(e)
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
            selectors: BeautifulSoup,
            downloader: PageDownloader,
            domain: str,
            all_messages: bool = False,
            no_resize_images: bool = False,
    ):
        self.risitas_html: List['BeautifulSoup'] = []
        self.risitas_raw_text: List[str] = []
        self.count = 0
        self.duplicates = 0
        self.selectors = selectors
        self.all_messages = all_messages
        self.downloader = downloader
        self.no_resize_images = no_resize_images
        self.authors: List[str] = []
        self.domain = domain
        self.webarchive = bool(domain == Webarchive.SITE.value)
        self.past_message = False
        self.message_cursor = 0

    def _check_post_author(
            self,
            post: BeautifulSoup,
            no_match_author: bool,
    ) -> bool:
        # This is needed cuz deleted accounts are not handled
        # the same way for whatever reason...
        try:
            post_author = post.select_one(
                self.selectors.AUTHOR_SELECTOR.value
            ).text.strip()
        except AttributeError:
            if not self.webarchive:
                logging.debug("Author deleted his account")
                post_author = post.select_one(
                    self.selectors.DELETED_AUTHOR_SELECTOR.value
                ).text.strip()
            else:
                return False
        logging.debug(
            "The current author is "
            "{post_author} "
            "and the risitas author is "
            "{self.authors}"
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
        p = post.text.strip().replace("\n", "")
        return bool(len(p) < 1000)

    def _check_post_identifiers(
            self,
            post: BeautifulSoup,
            identifiers: List
    ) -> bool:
        identifiers_joined = "|".join(identifiers)
        regexp = re.compile(identifiers_joined, re.IGNORECASE)
        try:
            post_paragraph_text = post.select_one("p").text[0:200]
        except AttributeError as e:
            logging.exception(
                f"The post doesn't contains text, probably some image {e}"
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
        if not paragraphs and self.domain == Jvarchive.SITE.value:
            a = soup.select("a")
            if a:
                return True
        # Need to check alt startswith https
        for paragraph in paragraphs:
            if re.search(r"screen|repost|supprime", paragraph.text):
                if (
                        len(
                            soup.select(
                                self.selectors.NOELSHACK_IMG_SELECTOR.value
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
                                self.selectors.NOELSHACK_IMG_SELECTOR.value
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
        imgs = image_soup.select(self.selectors.NOELSHACK_IMG_SELECTOR.value)
        remove_attrs = ["width", "height"]
        for remove_attr in remove_attrs:
            for img in imgs:
                try:
                    img.attrs.pop(remove_attr)
                    logging.info(
                        f"Displaying {img.attrs['src']} at full scale!"
                    )
                except KeyError as e:
                    logging.exception(f"This is a jvc smiley! {e}")
        if self.domain == Jvc.SITE.value:
            for img in imgs:
                if re.search("fichiers", img.attrs["alt"]):
                    img.attrs["src"] = img.attrs["alt"]
                else:
                    img.attrs["src"] = self.downloader.download_img_page(
                        img.attrs["alt"]
                    )
        elif self.domain == Jvarchive.SITE.value:
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
                    f"{pretty_print}"
                )
        except AttributeError as e:
            logging.exception(
                f"Can't log text because this "
                f"is an image from jvarchive {e}"
            )

    def _get_webarchive_post_html(
            self,
            post: BeautifulSoup
    ) -> BeautifulSoup:
        new_html = []
        risitas_html = post.select_one(
            self.selectors.RISITAS_TEXT_SELECTOR_ALTERNATIVE.value
        )
        if risitas_html and risitas_html.p:
            return risitas_html
        risitas_html = post.select(
               self.selectors.RISITAS_TEXT_SELECTOR_ALTERNATIVE2.value
        )
        if not risitas_html:
            risitas_html = post.select(
                self.selectors.RISITAS_TEXT_SELECTOR_ALTERNATIVE3.value
            )
        for paragraph in risitas_html:
            new_html.append(str(paragraph))
            new_html_joined = "".join(new_html)
            risitas_html = BeautifulSoup(new_html_joined, features="lxml")
            # This is needed cuz beautifulsoup
            # add a html,body tag automatically
        try:
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

    def get_posts(
            self,
            soup: BeautifulSoup,
            risitas_authors: List,
            identifiers: List,
            no_match_author: bool,
            append: bool,
            message_cursor_db: int,
    ) -> None:
        posts = soup.select(self.selectors.MESSAGE_SELECTOR.value)
        # Counter necessary to keep the first post in risitas
        # This post usually have no identifiers and is used
        # as an intro
        if not self.authors:
            self.authors = risitas_authors
        self.added_message = False
        for message_cursor, post in enumerate(posts):
            # We go to the last page recorded in the db
            # And we skip the messages according to the cursor
            # position in the database
            if append and not self.past_message:
                if message_cursor <= message_cursor_db:
                    if message_cursor == 19:
                        self.past_message = True
                    continue
                else:
                    self.past_message = True
            is_author = self._check_post_author(post, no_match_author)
            risitas_html = post.select_one(
                self.selectors.RISITAS_TEXT_SELECTOR.value
            )
            try:
                contains_paragraph = risitas_html.select("p")
            except AttributeError:
                contains_paragraph = None
            if self.webarchive and not contains_paragraph:
                risitas_html = self._get_webarchive_post_html(post)
            if not is_author and not self.webarchive:
                continue
            contains_image = self._check_chapter_image(risitas_html)
            if contains_image:
                logging.debug("The current post contains images!")
                if not self.no_resize_images:
                    risitas_html = self._get_fullscale_image(risitas_html)
            if self.all_messages:
                self.count += 1
                self.risitas_html.append((risitas_html, ))
                continue
            contains_identifiers = self._check_post_identifiers(
                post,
                identifiers
            )
            is_short = self._check_post_length(post)
            contains_blockquote = self._contains_blockquote(risitas_html)
            if contains_blockquote:
                continue
            if (
                    not contains_identifiers and
                    self.count > 1 and
                    not contains_image
                    and is_short
            ):
                continue
            if is_short and not contains_image:
                continue
            is_duplicate = self._check_post_duplicates(
                risitas_html,
                contains_image
            )
            if is_duplicate:
                logging.info(
                    (
                        "The current post "
                        f"{risitas_html.select_one('p').text[0:50].strip()}"
                        "is a duplicate!"
                    )
                )
                self.duplicates += 1
                continue
            self._print_chapter_added(risitas_html)
            self.added_message = True
            self.risitas_html.append((risitas_html, contains_image))
            self.risitas_raw_text.append(risitas_html.text)
            self.count += 1
            self.message_cursor = message_cursor


def main() -> None:
    args = get_args()
    output_dir = args.output_dir.expanduser().resolve()

    # File logging
    log_file = output_dir / f"risiparse-{TODAY}.log"
    FILE_HANDLER = logging.FileHandler(log_file)
    FILE_HANDLER.setLevel(logging.DEBUG)
    FILE_HANDLER.setFormatter(logging.Formatter(FMT))
    LOGGER.addHandler(FILE_HANDLER)

    all_messages = args.all_messages
    download_images = args.download_images
    identifiers = args.identifiers
    no_match_author = args.no_match_author
    no_resize_images = args.no_resize_images
    clear_database = args.clear_database
    no_database = args.no_database
    create_pdfs_user = args.create_pdfs
    no_download = args.no_download
    htmls_file_path = None
    if clear_database:
        delete_db()
        sys.exit()
    make_dirs(output_dir)
    if args.debug:
        STDOUT_HANDLER.setLevel(logging.DEBUG)
        FILE_HANDLER.setLevel(logging.DEBUG)
    if not no_download:
        page_links = parse_input_links(args.links)
        htmls_file_path = []
        for link in page_links:
            # This part is just used to get the risitas info
            domain = get_domain(link)
            if domain == Webarchive.SITE.value:
                no_database = True
            selectors = get_selectors_and_site(link)
            page_number: int = 1
            page_downloader = PageDownloader(domain)
            soup = page_downloader.download_topic_page(
                link,
                page_number,
            )
            risitas_info = RisitasInfo(soup, selectors, domain)
            authors = [risitas_info.author] + args.authors
            posts = Posts(
                selectors,
                page_downloader,
                domain,
                all_messages,
                no_resize_images,
            )
            total_pages = risitas_info.total_pages
            if not no_database:
                row = read_db(link)
                if row[0]:
                    page_number = 0
                    # +1 to evaluate the page itself
                    total_pages = risitas_info.total_pages - row[0][6] + 1
            for page in range(total_pages):
                append = False
                message_cursor_db = 0
                if not no_database:
                    if row[0]:
                        if not page_number:
                            page_number = row[0][6]
                        append = True
                        message_cursor_db = row[0][7]
                    else:
                        message_cursor_db = 0
                soup = page_downloader.download_topic_page(
                    link, page_number
                )
                if not soup:
                    page_number += 1
                    continue
                posts.get_posts(
                    soup,
                    authors,
                    identifiers,
                    no_match_author,
                    append,
                    message_cursor_db
                )
                page_number += 1
                if (
                        posts.message_cursor and
                        page + 1 == total_pages and
                        posts.added_message
                ):
                    message_cursor = posts.message_cursor
                else:
                    message_cursor = 0
            if not posts.risitas_html and not no_database:
                logging.info("There is no new chapters available!")
                continue
            logging.info(
                "The number of posts downloaded for "
                f"{risitas_info.title} "
                f"is : {posts.count}"
            )
            risitas_html = posts.risitas_html
            if not all_messages:
                logging.info(
                    "The number of duplicates for "
                    f"{risitas_info.title} "
                    f"is : {posts.duplicates}"
                )
            if download_images:
                page_downloader.download_images(
                    risitas_html,
                    output_dir,
                )
            if domain == Webarchive.SITE.value:
                risitas_html = replace_youtube_frames(risitas_html)
            if append and not no_database:
                file_path = pathlib.Path(row[0][4])
                htmls_file_path.append(file_path)
                append_html(file_path, risitas_html)
            else:
                file_path = write_html(
                    risitas_info.title,
                    risitas_info.author,
                    risitas_html,
                    output_dir,
                )
                htmls_file_path.append(file_path)
            if not no_database:
                update_db(
                    domain,
                    risitas_info.title,
                    link,
                    file_path,
                    risitas_info.total_pages,
                    risitas_info.total_pages,
                    message_cursor,
                    authors,
                )
    if not args.no_pdf:
        create_pdfs(output_dir, create_pdfs_user, htmls_file_path, no_download)
