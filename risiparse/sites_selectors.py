#!/usr/bin/python3

from enum import Enum

class Jvc(Enum):
    AUTHOR_SELECTOR = ".bloc-header > span"
    DELETED_AUTHOR_SELECTOR = ".bloc-pseudo-msg"
    TOTAL_SELECTOR = ".bloc-liste-num-page > span:nth-last-of-type(2)"
    MESSAGE_SELECTOR = ".conteneur-message"
    RISITAS_TEXT_SELECTOR = "[class='txt-msg text-enrichi-forum']"
    TITLE_SELECTOR = "#bloc-title-forum"
    NOELSHACK_IMG_SELECTOR = "img.img-shack"


class Jvarchive(Enum):
    AUTHOR_SELECTOR = "[class='h4 text-truncate min-width-0 mb-0 text-primary'] > a"
    TOTAL_SELECTOR = ".page-item:nth-last-child(2)"
    MESSAGE_SELECTOR = "[class='card-body pb-0 px-3 px-md-4 pt-3']"
    RISITAS_TEXT_SELECTOR = ".conteneur-message"
    TITLE_SELECTOR = "[class='h2 text-white d-inline align-middle mb-0 mr-2']"
    NOELSHACK_IMG_SELECTOR = "img"


class Noelshack(Enum):
    IMG_SELECTOR = "#elt_to_aff"
