#!/usr/bin/python3

"""Regroup all posts related utils"""

from typing import List
import logging
import re

from bs4 import BeautifulSoup, Tag


def check_post_length(post: BeautifulSoup) -> bool:
    """Check the post length to see if this is a chapter
    or an offtopic post"""
    paragraph = post.text.strip().replace("\n", "")
    return bool(len(paragraph) < 1000)


def check_post_identifiers(
    post: BeautifulSoup,
    identifiers: List[str]
) -> bool:
    """Check if the post contains an identifier"""
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


def contains_blockquote(risitas_html: BeautifulSoup) -> bool:
    """Check if the post contains blockquote"""
    return bool(risitas_html.select("blockquote"))


def print_chapter_added(
    risitas_html: BeautifulSoup
) -> None:
    """Print the chapters added"""
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


def contains_paragraph(risitas_html: Tag) -> bool:
    """Check if post contains a paragraph"""
    has_paragraph = False
    try:
        has_paragraph = bool(risitas_html.select("p"))
    except AttributeError:
        pass
    return has_paragraph
