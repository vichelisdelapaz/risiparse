#!/usr/bin/python3

"""This module contains all the database logic"""

import sqlite3
import re
import pathlib
import logging
import sys

HOME = pathlib.Path.home()


if sys.platform == "win32":
    (HOME / "AppData/Roaming" / 'risiparse').mkdir(exist_ok=True)
    DB_PATH = HOME / "AppData/Roaming" / 'risiparse' / 'risiparse.db'
elif sys.platform == "linux":
    (HOME / ".local/share" / 'risiparse').mkdir(exist_ok=True)
    DB_PATH = HOME / ".local/share" / 'risiparse' / 'risiparse.db'
elif sys.platform == "darwin":
    (HOME / "Library/Application Support" / 'risiparse').mkdir(exist_ok=True)
    DB_PATH = (
        HOME /
        "Library/Application Support" /
        'risiparse' /
        'risiparse.db'
    )

logging.debug("The database is at : '%s'", DB_PATH)


def _replace_page_number(page_link: str) -> str:
    """
    The link stored in the database has a variable page number
    so we replace the the page number in the link by % to match
    the link.
    """
    page_link_number = [
              m.span() for m in re.finditer(r"\d*\d", page_link)
    ]
    page_link = (
              page_link[:page_link_number[3][0]]
              + '%'
    )
    return page_link


def create_db() -> None:
    """Create the database"""
    con = sqlite3.connect(DB_PATH)
    try:
        con.execute(
            '''create table if not exists risitas
            (id integer primary key autoincrement,
            title varchar,
            page_link varchar,
            file_path varchar,
            total_pages integer,
            post_cursor integer)'''
        )
    except sqlite3.OperationalError as operational_error:
        logging.exception(operational_error)
    con.close()


def read_db(page_link: str):
    """Fetch records from the database"""
    create_db()
    con = sqlite3.connect(DB_PATH)
    page_link_normalized = _replace_page_number(page_link)
    try:
        cursor = con.execute(
            '''select * from risitas where page_link LIKE ? limit 1''',
            (page_link_normalized, )
        )
        row = cursor.fetchone()
    except sqlite3.OperationalError as operational_error:
        logging.exception(operational_error)
    con.close()
    return row


def update_db(
        title: str,
        page_link: str,
        file_path: 'pathlib.Path',
        total_pages: int,
        post_cursor: int,
) -> None:
    """Updates records in the database"""
    create_db()
    con = sqlite3.connect(DB_PATH)
    page_link_normalized = _replace_page_number(page_link)
    cursor_existing_row = con.execute(
        '''select id from risitas where page_link like ? limit 1''',
        (page_link_normalized, )
    ).fetchone()
    if cursor_existing_row:
        try:
            with con:
                cursor = con.execute(
                    '''UPDATE risitas
                    SET title = ?,
                    page_link = ?,
                    file_path = ?,
                    total_pages = ?,
                    post_cursor = ?
                    WHERE id = ?''',
                    (
                        title,
                        page_link,
                        str(file_path),
                        total_pages,
                        post_cursor,
                        cursor_existing_row[0],
                    )
                )
                con.commit()
                logging.info(
                    "A risitas has been updated in the database!"
                )
                logging.debug(
                    "Id: %d "
                    "Title: %s "
                    "Total pages : %d",
                    cursor.lastrowid,
                    title,
                    total_pages,
                )
        except sqlite3.OperationalError as operational_error:
            logging.exception(operational_error)
    else:
        try:
            with con:
                cursor = con.execute(
                    '''INSERT INTO risitas
                    (title,
                    page_link,
                    file_path,
                    total_pages,
                    post_cursor)
                    VALUES (?, ?, ?, ?, ?)''',
                    (
                        title,
                        page_link,
                        str(file_path),
                        total_pages,
                        post_cursor,
                    )
                )
                con.commit()
                logging.info(
                    "A new risitas has been inserted in the database "
                    "at %s", DB_PATH
                )
                logging.debug(
                    "Id: %d "
                    "Title: %s "
                    "Total pages : %d",
                    cursor.lastrowid,
                    title,
                    total_pages,
                )
        except sqlite3.OperationalError as operational_error:
            logging.exception(operational_error)
    con.close()


def delete_db() -> None:
    """Delete the database"""
    DB_PATH.unlink()
    logging.info("Deleted database at %s", DB_PATH)
