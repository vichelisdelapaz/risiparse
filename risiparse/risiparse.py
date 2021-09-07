#!/usr/bin/python3

import logging
import requests
import re
import argparse
import pathlib

from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from risiparse.sites_selectors import Noelshack
from risiparse.utils.utils import (
    write_html,
    get_domain,
    make_dirs,
    get_selectors_and_site,
    create_pdfs,
    read_links,
    get_args
)
from typing import List
from colorama import Fore, Back, Style

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s: %(message)s'
)

DEFAULT_TIMEOUT = 5 # seconds

class TimeoutHTTPAdapter(HTTPAdapter):
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

    def __init__(self, site):
        self.site = site
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
            page_number: int = 1
    ) -> BeautifulSoup:
        page_link_number = [m.span() for m in re.finditer(r"\d*\d", page_link)]
        page_link = (
            page_link[:page_link_number[3][0]]
            + str(page_number) +
            page_link[page_link_number[3][1]:]
        )
        logging.info(f"Going to page {Fore.GREEN}{page_link}{Style.RESET_ALL}")
        page = self.http.get(page_link)
        soup = BeautifulSoup(page.content, features="lxml")
        return soup


    def download_img_page(self, page_link: str):
        page = self.http.get(page_link)
        soup = BeautifulSoup(page.content, features="lxml")
        img_link = soup.select_one(
            Noelshack.IMG_SELECTOR.value
        ).attrs["src"]
        return img_link


    def _change_src_path(self, img:str, img_folder_path: pathlib.Path, file_name: str) -> None:
        img.attrs["src"] = str(img_folder_path) + "/" + file_name


    def _image_exists(self, file_name: str, img_folder: pathlib.Path) -> bool:
        img_path = img_folder / file_name
        if img_path.exists():
            return True
        else:
            return False


    def download_images(self, soup: BeautifulSoup) -> None:
        img_folder_path = pathlib.Path.cwd() / "risitas-html" / "images"
        img_folder_path.mkdir(exist_ok=True)
        for x in soup:
            imgs = x[0].select("img")
            for img in imgs:
                link = img.attrs["src"]
                file_name = link[link.rfind("/"):][1:]
                if not self._image_exists(file_name, img_folder_path):
                    logging.info("Image not in cache, downloading...")
                    image = self.http.get(img.attrs["src"])
                    file_name = image.url[image.url.rfind("/"):][1:]
                    img_file_path = img_folder_path / file_name
                    img_file_path.write_bytes(image.content)
                self._change_src_path(img, img_folder_path, file_name)


class RisitasInfo():
    """
    This gets the author name and the total number of pages and the title.
    This assumes that the author didn't delete his account
    """

    def __init__(self, page_soup, selectors):
        self.soup = page_soup
        self.selectors = selectors
        self.author = self.get_author_name(self.soup)
        self.pages_number = self.get_total_pages(self.soup)
        self.title = self.get_title(self.soup)


    def get_author_name(self, soup: BeautifulSoup) -> str:
        author = soup.select_one(
            self.selectors.AUTHOR_SELECTOR.value
        ).text.strip()
        logging.info(f"The risitas author is : {Fore.YELLOW}{author}{Style.RESET_ALL}")
        return author


    def get_total_pages(self, soup: BeautifulSoup) -> int:
        topic_symbol = soup.select_one(
            self.selectors.TOTAL_SELECTOR.value
        ).text
        topic_pages = int(topic_symbol)
        return topic_pages


    def get_title(self, soup: BeautifulSoup) -> str:
        title = soup.select_one(
            self.selectors.TITLE_SELECTOR.value
        ).text.strip()
        return title


class Posts():
    """Get a post author and content"""


    def __init__(
            self,
            selectors: BeautifulSoup,
            downloader: PageDownloader,
            site:str,
            all_messages: bool = False,
            no_resize_images: bool = False
    ):
        self.risitas_html = []
        self.risitas_raw_text = []
        self.count = 0
        self.duplicates = 0
        self.selectors = selectors
        self.all_messages = all_messages
        self.downloader = downloader
        self.site = site
        self.no_resize_images = no_resize_images
        self.authors = []


    def _check_post_author(
            self,
            post: BeautifulSoup,
            authors: List
    ) -> bool:
        # This is needed cuz deleted accounts are not handled
        # the same way for whatever reason...
        try:
            author = post.select_one(
                self.selectors.AUTHOR_SELECTOR.value
            ).text.strip()
        except AttributeError as e:
            logging.debug(f"Author deleted his account")
            return False
        logging.debug(
            f"The current author is {Fore.BLUE}{author}{Style.RESET_ALL} " +
            f"and the risitas author is {Fore.BLUE}{authors}{Style.RESET_ALL}"
        )
        for author in authors:
            if re.match(self.authors[0], author):
                return True
        return True if author in authors else False


    def _check_post_length(self, post: BeautifulSoup) -> bool:
        """Check the post length to see if this is a chapter
        or an offtopic message"""
        p = post.text.strip().replace("\n", "")
        return True if len(p) < 1000 else False


    def _check_post_identifiers(
            self,
            post: BeautifulSoup,
            identifiers: List
    ) -> bool:
        identifiers = "|".join(identifiers)
        regexp = re.compile(identifiers, re.IGNORECASE)
        try:
            post_paragraph_text = post.select_one("p").text[0:200]
        except AttributeError as e:
            logging.exception(
                "The post doesn't contains text, probably some image"
            )
            return False
        contains_identifiers = regexp.search(post_paragraph_text)
        if contains_identifiers and not post.select_one("blockquote"):
            return True
        else:
            return False


    def _check_post_duplicates(
            self,
            risitas_html: str,
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
                else:
                    ret_val = False
            return ret_val
        for i in range(len(self.risitas_raw_text)):
            if (
                    risitas_html.text.lower() ==
                    self.risitas_raw_text[-i].lower() or
                    risitas_html.text[0:100].lower() ==
                    self.risitas_raw_text[-i][0:100].lower()
            ):
                ret_val = True
        return ret_val


    def _contains_blockquote(self, risitas_html: BeautifulSoup) -> bool:
        return True if risitas_html.select("blockquote") else False


    def _check_chapter_image(self, soup: BeautifulSoup) -> bool:
        ret_val = False
        paragraphs = soup.select("p")
        if not paragraphs and self.site == "jvarchive":
            a = soup.select("a")
            if a:
                return True
        # Need to check alt startswith https
        for paragraph in paragraphs:
            if re.search(r"screen|repost|supprime", paragraph.text):
                if (
                        len(
                            soup.select(self.selectors.NOELSHACK_IMG_SELECTOR.value)
                        ) >= 3 and not soup.select("blockquote") and
                        len(soup.text.strip()) < 300

                ):
                    ret_val = True
                    break
            elif not paragraph.text.strip():
                if (
                        len(
                            soup.select(self.selectors.NOELSHACK_IMG_SELECTOR.value)
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
                except KeyError as e:
                    logging.exception(f"This is a jvc smiley! {e}")
        if self.site == "jvc":
            for img in imgs:
                if re.search("fichiers", img.attrs["alt"]):
                    img.attrs["src"] = img.attrs["alt"]
                else:
                    img.attrs["src"] = self.downloader.download_img_page(
                        img.attrs["alt"]
                    )
        else:
            for img in imgs:
                img.attrs["src"] = img.attrs["alt"]
        return image_soup


    def get_posts(
            self,
            soup: BeautifulSoup,
            risitas_authors: List,
            identifiers: List
    ) -> None:
        posts = soup.select(self.selectors.MESSAGE_SELECTOR.value)
        # Counter necessary to keep the first post in risitas
        # This post usually have no identifiers and is used
        # as an intro
        for post in posts:
            if not self.authors:
                self.authors = risitas_authors
            is_author = self._check_post_author(post, risitas_authors)
            risitas_html = post.select_one(
                self.selectors.RISITAS_TEXT_SELECTOR.value
            )
            if not is_author:
                continue
            contains_image = self._check_chapter_image(risitas_html)
            if contains_image:
                logging.debug(f"The current post contains images!")
                if not self.no_resize_images:
                    risitas_html = self._get_fullscale_image(risitas_html)
            if self.all_messages:
                self.count += 1
                self.risitas_html.append((risitas_html, ))
                continue
            contains_identifiers = self._check_post_identifiers(post, identifiers)
            is_short = self._check_post_length(post)
            contains_blockquote = self._contains_blockquote(risitas_html)
            if contains_blockquote:
                continue
            if not contains_identifiers and self.count > 1 and not contains_image and is_short:
                continue
            if is_short and not contains_image:
                continue
            is_duplicate = self._check_post_duplicates(risitas_html, contains_image)
            if is_duplicate:
                logging.info(
                    (
                        "The current post "
                        f"{Fore.RED}{risitas_html.select_one('p').text[0:50].strip()}{Style.RESET_ALL} "
                        "is a duplicate!"
                    )
                )
                self.duplicates += 1
                continue
            # Can't select p from jvarchive  because the attributes are malformed...
            try:
                pretty_print = risitas_html.select_one(
                    'p'
                ).text[0:50].strip().replace("\n", "")
                if not pretty_print:
                    logging.debug("Added some images, maybe chapters in screenshot?")
                else:
                    logging.info(f"Added {Fore.BLUE}{pretty_print}{Style.RESET_ALL}")
            except AttributeError as e:
                logging.exception(
                    "Can't log text because this is an image from jvarchive"
                )
            self.risitas_html.append((risitas_html, contains_image))
            self.risitas_raw_text.append(risitas_html.text)
            self.count += 1


def main() ->  None:
    args = get_args()
    make_dirs(args.output_dir)
    all_messages = args.all_messages
    download_images = args.download_images
    page_links = read_links(args.links)
    identifiers = args.identifiers
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    if not args.no_download:
        for link in page_links:
            selectors, site = get_selectors_and_site(link)
            page_number: int = 1
            page_downloader = PageDownloader(site)
            soup = page_downloader.download_topic_page(link)
            risitas_info = RisitasInfo(soup, selectors)
            authors = [risitas_info.author] + args.authors
            posts = Posts(
                selectors,
                page_downloader,
                site,
                all_messages,
                args.no_resize_images
            )
            for _ in range(risitas_info.pages_number):
                soup = page_downloader.download_topic_page(
                    link, page_number
                )
                posts.get_posts(soup, authors,identifiers)
                page_number += 1
            logging.info(
                f"The number of posts downloaded for {Fore.BLUE}{risitas_info.title}{Style.RESET_ALL} "
                f"is : {posts.count}"
            )
            if not all_messages:
                logging.info(
                    f"The number of duplicates for {Fore.BLUE}{risitas_info.title}{Style.RESET_ALL} "
                    f"is : {posts.duplicates}"
                )
            if download_images:
                page_downloader.download_images(posts.risitas_html)
            write_html(
                risitas_info.title,
                risitas_info.author,
                posts.risitas_html,
                args.output_dir,
            )
    if not args.no_pdf:
        create_pdfs(args.output_dir)


if __name__ == "__main__":
    main()
