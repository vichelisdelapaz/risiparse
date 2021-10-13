#!/usr/bin/python3

"""Regroup all page_downloader related routines"""

from typing import Optional
import pathlib
import re

from bs4 import BeautifulSoup
from .utils import strip_webarchive_link, contains_webarchive


def change_img_src_path(
    img: 'BeautifulSoup',
    img_folder_path: pathlib.Path,
    file_name: str
) -> None:
    """Change image src path"""
    img.attrs["src"] = str(img_folder_path) + "/" + file_name


def image_exists(
    file_name: str,
    img_folder: pathlib.Path
) -> bool:
    """Check if image exits in an image folder"""
    img_path = img_folder / file_name
    return bool(img_path.exists())


def get_page_link(
    page_number: int,
    page_link: str,
) -> str:
    """Get the page link of a jvc/jvarchive link"""
    page_link_number = [
            m.span() for m in re.finditer(r"\d*\d", page_link)
    ]
    page_link = (
            page_link[:page_link_number[3][0]]
            + str(page_number) +
            page_link[page_link_number[3][1]:]
    )
    return page_link


def get_webarchive_page_link(
    page_number: int,
    page_link: str
) -> Optional[str]:
    """Get the page link of a werbarchive link"""
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


def get_webarchive_link(
    img: BeautifulSoup
) -> str:
    """
    Strip the redundant part in the webarchive link
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
