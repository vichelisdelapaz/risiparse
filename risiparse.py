#!/usr/bin/python3

import logging
import argparse
import requests
import re
import time
import random
import sites_selectors
import pathlib
import html_to_pdf
import sys
import os

from bs4 import BeautifulSoup
from utils.utils import write_html, is_jvc_url, make_dirs
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from typing import List

logging.basicConfig(level=logging.INFO,format='%(asctime)s:%(levelname)s: %(message)s')

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


    def download_topic_page(self, page_link: str, page_number: int = 1) -> BeautifulSoup:
        page_link_number = [m.span() for m in re.finditer(r"\d*\d", page_link)]
        page_link = page_link[:page_link_number[3][0]] + str(page_number) + page_link[page_link_number[3][1]:]
        logging.info(f"Going to page {page_link}")
        page = self.http.get(page_link)
        soup = BeautifulSoup(page.content, features="lxml")
        return soup


    def download_img_page(self, page_link: str):
        page = self.http.get(page_link)
        soup = BeautifulSoup(page.content, features="lxml")
        img_link = soup.select_one(Noelshack.IMG_SELECTOR.value).attrs["src"]
        return img_link


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
        author = soup.select_one(self.selectors.AUTHOR_SELECTOR.value).text.strip()
        logging.info(f"The risitas author is : {author}")
        return author


    def get_total_pages(self, soup: BeautifulSoup) -> int:
        topic_symbol = soup.select_one(self.selectors.TOTAL_SELECTOR.value).text
        if topic_symbol == "»":
            topic_symbol = soup.select_one(self.selectors.TOTAL_SELECTOR1.value).text
        topic_pages = int(topic_symbol)
        return topic_pages


    def get_title(self, soup: BeautifulSoup) -> str:
        title = soup.select_one(self.selectors.TITLE_SELECTOR.value).text.strip()
        return title


class Posts():
    """Get a post author and content"""


    def __init__(
            self,
            selectors: BeautifulSoup,
            downloader: PageDownloader,
            site:str,
            bulk: bool = False,
            no_resize_images: bool = False
    ):
        self.risitas_html = []
        self.risitas_raw_text = []
        self.count = 0
        self.duplicates = 0
        self.selectors = selectors
        self.bulk = bulk
        self.downloader = downloader
        self.site = site
        self.no_resize_images = no_resize_images


    def _check_post_author(self, post: BeautifulSoup, risitas_author: str) -> bool:
        # This is needed cuz deleted accounts are not handled
        # the same way for whatever reason...
        try:
            current_author = post.select_one(self.selectors.CURRENT_AUTHOR_SELECTOR.value).text.strip()
        except AttributeError as e:
            # Commenting exception, because I think
            # this will spook the user more than help them
            #logging.exception(f"Author Probably deleted his account")
            logging.info(f"Author Probably deleted his account")
            return False
        logging.debug(f"The current author is {current_author} and the risitas author is {risitas_author}")
        return True if current_author == risitas_author else False


    def _check_post_length(self, post: BeautifulSoup) -> bool:
        """Check the post length to see if this is a chapter
        or an offtopic message"""
        p = post.text.strip().replace("\n", "")
        return True if len(p) < 1000 else False


    def _check_post_identifiers(self, post: BeautifulSoup, identifiers: List) -> bool:
        identifiers = "|".join(identifiers)
        regexp = re.compile(identifiers, re.IGNORECASE)
        # Adding this to avoid reply, search for beginning of text
        try:
            post_paragraph_text = post.select_one("p").text[0:200]
        except AttributeError as e:
            #logging.exception("The post doesn't contains text, probably some image")
            logging.info("The post doesn't contains text, probably some image")
            return False
        return True if regexp.search(post_paragraph_text) else False


    def _check_post_duplicates(self, risitas_html: str, contains_images: bool) -> bool:
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
            if ( risitas_html.text.lower() == self.risitas_raw_text[-i].lower()  or
                 risitas_html.text[0:50].lower() == self.risitas_raw_text[-i][0:50].lower()
            ):
                ret_val = True
        return ret_val


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
                        len(soup.select(self.selectors.NOELSHACK_IMG_SELECTOR.value)) > 2 and not
                        soup.select("blockquote") and len(soup.text.strip()) < 300

                ):
                    ret_val = True
                    break
            elif not paragraph.text.strip():
                if (
                        len(soup.select(self.selectors.NOELSHACK_IMG_SELECTOR.value)) > 2 and not
                        soup.select("blockquote") and len(soup.text.strip()) < 300
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
                    #logging.exception(f"This is a jvc smiley! {e}")
                    logging.info(f"This is a jvc smiley! {e}")
        if self.site == "jvc":
            for img in imgs:
                img.attrs["src"] = self.downloader.download_img_page(img.attrs["alt"])
        else:
            for img in imgs:
                img.attrs["src"] = img.attrs["alt"]
        return image_soup


    def get_posts(self, soup: BeautifulSoup, risitas_author: str, identifiers: List) -> None:
        posts = soup.select(self.selectors.MESSAGE_SELECTOR.value)
        # Counter necessary to keep the first post in risitas
        # This post usually have no identifiers and is used
        # as an intro
        for post in posts:
            is_author = self._check_post_author(post, risitas_author)
            risitas_html = post.select_one(self.selectors.RISITAS_TEXT_SELECTOR.value)
            if not is_author:
                continue
            contains_image = self._check_chapter_image(risitas_html)
            if contains_image:
                logging.info(f"The current post contains chapters posted in screenshots!")
                logging.debug(f"{risitas_html}")
                if not self.no_resize_images:
                    risitas_html = self._get_fullscale_image(risitas_html)
            if self.bulk:
                self.count += 1
                self.risitas_html.append(risitas_html)
                continue
            contains_identifiers = self._check_post_identifiers(post, identifiers)
            is_short = self._check_post_length(post)
            if not contains_identifiers and self.count > 1 and not contains_image:
                continue
            if is_short and not contains_image:
                continue
            is_duplicate = self._check_post_duplicates(risitas_html, contains_image)
            if is_duplicate:
                logging.info(
                    (
                        f"The current post {risitas_html.select_one('p').text[0:50]} "
                        "is a duplicate!"
                    )
                )
                self.duplicates += 1
                continue
            # Can't select p from jvarchive  because the attributes are malformed...
            try:
                pretty_print = risitas_html.select_one('p').text[0:50].strip().replace("\n", "")
                logging.info(f"Added {pretty_print}")
            except AttributeError as e:
                #logging.exception("Can't log text because this is an image from jvarchive")
                logging.info("Can't log text because this is an image from jvarchive")
            self.risitas_html.append((risitas_html, contains_image))
            self.risitas_raw_text.append(risitas_html.text)
            self.count += 1


def main(args) ->  None:
    # Make sure all directories are there
    make_dirs(args.output_dir)
    identifiers = args.identifiers
    page_link = []
    bulk = args.bulk
    with open(args.links) as f:
        for link in f:
            page_link.append(link.strip())
    if not args.disable_html:
        for link in page_link:
            time.sleep(5)
            is_jvc = is_jvc_url(link)
            site = ""
            if is_jvc:
                selectors = sites_selectors.Jvc
                site = "jvc"
            else:
                selectors = sites_selectors.Jvarchive
                site = "jvarchive"
            page_number: int = 1
            page_downloader = PageDownloader()
            soup = page_downloader.download_topic_page(link)
            logging.info(soup, link)
            risitas_info = RisitasInfo(soup, selectors)
            risitas_author = risitas_info.author
            risitas_title = risitas_info.title
            post = Posts(selectors, page_downloader, site, bulk, args.no_resize_images)
            for _ in range(risitas_info.pages_number):
                soup = page_downloader.download_topic_page(
                    link, page_number
                )
                post.get_posts(soup, risitas_author,identifiers)
                page_number += 1
            logging.info(f"The number of post downloaded for {risitas_title} is : {post.count}")
            if not bulk:
                logging.info(f"The number of duplicates for {risitas_title} is : {post.duplicates}")
            write_html(risitas_title, risitas_author, post.risitas_html, args.output_dir, args.bulk)
    if args.create_pdf:
        html_folder_path = pathlib.Path(args.output_dir) / "risitas-html"
        htmls = list(html_folder_path.glob("*"))
        if htmls:
            app = html_to_pdf.QtWidgets.QApplication([])
            page = html_to_pdf.PdfPage(args.output_dir)
            logging.info(f"Creating pdfs...")
            page.convert(htmls)
            sys.exit(app.exec_())



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    default_links = str((pathlib.Path().cwd() / "risitas-links"))
    # Optional argument flag which defaults to False
    parser.add_argument("-b", "--bulk", action="store_true", default=False, help="Use this option if you want to download all the messages from the author. Default : False")
    parser.add_argument("-p", "--create-pdf", action="store_true", default=True, help="Enable/Disable Pdf creation, Default : True")
    parser.add_argument("--disable-html", action="store_true", default=False, help="Enable/Disable Html Download, Default : False")
    parser.add_argument("-l","--links", action="store", default=default_links, help="The links file, Default : current dir/risitas-links")
    # Take a list of identifiers
    parser.add_argument('-i','--identifiers', nargs='+', help="Give a list of words that are going to be matched by the script, example: a message that has the keyword 'hors-sujet', by adding 'hors-sujet' with this option, the script will match the message that has this keyword. Default : Chapitre" , required=False, default="chapitre")
    # Images
    parser.add_argument('--no-resize-images', help="When the script 'thinks' that the post contains images and that they are chapters posted in screenshot, it will try to display them to their full width, Default : False" ,action="store_true", required=False, default=False)
    # Output dir
    parser.add_argument('-o','--output-dir',action="store" , help="Output dir, Default is current dir" , default=str(pathlib.Path.cwd()))
    args = parser.parse_args()
    main(args)
